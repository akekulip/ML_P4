"""W8 report: MVM on the Tofino-1 with Vision and Hulk, compared with CPU-only inference.

Reads results/w8/runs/<label>/ (client records, controller log, meta) and writes
docs/results_w8.md plus figures. Labels: a_<slice>_k{8,0}_r1000_rep{1..3} (hit rate and latency at
1k qps) and b_full_k{8,0}_r<rate>_rep{1..3} (load sweep). K=8 is MVM; K=0 is CPU only (every query
answered by Hulk through the same switch and links).
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import matplotlib
import matplotlib.ticker
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from mvm.cache import simulate_fast, simulate_hw_policy

ROOT = Path(__file__).resolve().parents[1]
RUNS, FIG, BUILD = ROOT / "results/w8/runs", ROOT / "figures", ROOT / "hw/build"
REC = np.dtype([("send", "<u8"), ("recv", "<u8"), ("flags", "u1"), ("klass", "u1"), ("leaf", "<u2"), ("t_pipe", "<u4")])
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # validated palette (dataviz)
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e6e6e3", "grid.linewidth": 0.6})
SLICE_NAME = {"full_0425_to_0426": "full stream, 25 to 26 April", "benign_0427_to_0428": "benign flows, 27 to 28 April"}


def load_run(d: Path) -> dict:
    meta = json.loads((d / "meta.json").read_text())
    r = np.fromfile(d / "records.bin", dtype=REC)
    exp = np.load(BUILD / f"expected_{meta['slice']}.npz")
    n = len(r)
    ok = r["recv"] > 0
    rtt = (r["recv"].astype(np.int64) - r["send"].astype(np.int64)) / 1e3  # microseconds
    hit, cpu = r["flags"] == 1, r["flags"] == 2
    span = (r["recv"][ok].max() - r["send"].min()) / 1e9 if ok.any() else np.nan
    # one early log was corrupted by unsynchronized writes from two threads (fixed in the controller);
    # decode leniently and keep only well-formed rows
    raw = (d / "controller.csv").read_bytes().decode("utf-8", errors="replace").replace("\x00", "")
    ctl = [c for c in csv.DictReader(raw.splitlines()) if c.get("event") in ("miss", "credit")
           and all((c.get(f) or "").lstrip("-").isdigit() for f in ("wall_ns", "qid", "installed", "write_done_ns"))]
    misses = [c for c in ctl if c["event"] == "miss"]
    installs = [c for c in misses if c["installed"] == "1"]
    write_ms = [(int(c["write_done_ns"]) - int(c["wall_ns"])) / 1e6 for c in installs]
    return {
        **meta, "n": n, "answered": ok.mean(), "switch_hit": hit.mean(), "cpu": cpu.mean(),
        "fid_klass": (r["klass"][ok] == exp["klass"][:n][ok]).mean() if ok.any() else np.nan,
        "fid_leaf": (r["leaf"][ok] == exp["leaf"][:n][ok]).mean() if ok.any() else np.nan,
        "rtt_hit": rtt[hit & ok], "rtt_cpu": rtt[cpu & ok], "t_pipe": r["t_pipe"][hit & ok].astype(float),
        "answer_rate": ok.sum() / span if span else np.nan, "digests": len(misses), "installs": len(installs),
        "write_ms": np.array(write_ms), "hits_seq": hit, "exp_leaf": exp["leaf"][:n],
    }


runs = {d.name: load_run(d) for d in sorted(RUNS.iterdir()) if (d / "records.bin").exists() and not d.name.startswith("smoke")}
info = json.loads((BUILD / "info.json").read_text())
bench = [json.loads(l) for l in (ROOT / "results/w8/hulk_cpu_bench.txt").read_text().splitlines() if l.startswith("{")]
cpu_model = re.search(r"Model name:\s+(.*)", (ROOT / "results/w8/hulk_cpu_bench.txt").read_text()).group(1)


def group(prefix):
    return [v for k, v in runs.items() if re.fullmatch(prefix, k)]


def pct(a, q):
    return float(np.percentile(a, q)) if len(a) else float("nan")


lines = ["# W8 results: MVM on the Tofino-1 with Vision and Hulk", "",
         f"Tree: data-plane DT, grouped split seed 0, depth {info['depth']} ({info['n_leaves']} leaves), the deepest tree "
         f"whose thermometer key ({info['key_width']} bits) fits the 440-bit ternary budget; validation macro-F1 "
         f"{info['val_macro_f1']:.3f}, test {info['test_macro_f1']:.3f}. Static feature tables: {info['fine_entries']} fine + "
         f"{info['coarse_entries']} coarse entries. Switch: UfiSpace S9180-32X (Tofino-1), SDE 9.13.2. Vision sends queries "
         "(dev port 9, 25G); hits are answered by the switch, misses are forwarded to Hulk (dev port 10, 25G), whose C backend "
         "runs the full tree on CPU and replies through the switch. K=8 is MVM with decayed LFU (gamma 0.99) in the "
         f"switch controller, hits credited from direct counters every 20 ms. K=0 is CPU only: every query goes to Hulk. "
         "Each configuration was run three times from a cold cache.", ""]

# Correctness.
allr = list(runs.values())
lines += ["## Correctness", "",
          f"- Runs: {len(allr)}; queries answered: {sum(int(v['answered'] * v['n']) for v in allr):,} of {sum(v['n'] for v in allr):,}.",
          f"- Served class equals the offline tree on {min(v['fid_klass'] for v in allr):.4%} or more of answered queries in every run; "
          f"served leaf equals the tree's leaf on {min(v['fid_leaf'] for v in allr):.4%} or more.", ""]

# Hit rate vs simulators at 1k qps.
lines += ["## Hit rate at 1,000 queries/s against the simulators (K=8, 30,000 queries, 3 runs)", "",
          "| slice | hardware switch hit rate | ideal decayed LFU (= BMv2) | hardware-policy simulator, lag 0 / 10 / 50 queries |",
          "|---|---|---|---|"]
for sl in SLICE_NAME:
    g = group(rf"a_{sl}_k8_r1000_rep\d")
    if not g:
        continue
    leaf = g[0]["exp_leaf"]
    ideal = simulate_fast("dlfu", leaf, 8, gamma=0.99).hits.mean()
    hw = [simulate_hw_policy(leaf, 8, 0.99, lag, 20).mean() for lag in (0, 10, 50)]
    hr = np.array([v["switch_hit"] for v in g])
    lines.append(f"| {SLICE_NAME[sl]} | {hr.mean():.4f} ± {hr.std():.4f} | {ideal:.4f} | {hw[0]:.4f} / {hw[1]:.4f} / {hw[2]:.4f} |")
lines.append("")

# Latency at 1k qps.
lines += ["## Latency at 1,000 queries/s (all runs pooled)", "",
          "| path | median | 99th percentile |", "|---|---|---|"]
for sl in SLICE_NAME:
    g8, g0 = group(rf"a_{sl}_k8_r1000_rep\d"), group(rf"a_{sl}_k0_r1000_rep\d")
    if not g8:
        continue
    tp = np.concatenate([v["t_pipe"] for v in g8])
    rh = np.concatenate([v["rtt_hit"] for v in g8])
    rc8 = np.concatenate([v["rtt_cpu"] for v in g8])
    rc0 = np.concatenate([v["rtt_cpu"] for v in g0]) if g0 else np.array([])
    lines += [f"| {SLICE_NAME[sl]}: on-chip pipeline (switch hit, ingress to egress) | {pct(tp, 50):.0f} ns | {pct(tp, 99):.0f} ns |",
              f"| {SLICE_NAME[sl]}: round trip at Vision, switch hit (K=8) | {pct(rh, 50):.1f} µs | {pct(rh, 99):.1f} µs |",
              f"| {SLICE_NAME[sl]}: round trip at Vision, miss answered by Hulk CPU (K=8) | {pct(rc8, 50):.1f} µs | {pct(rc8, 99):.1f} µs |",
              f"| {SLICE_NAME[sl]}: round trip at Vision, CPU only (K=0) | {pct(rc0, 50):.1f} µs | {pct(rc0, 99):.1f} µs |"]
lines += ["", f"CPU compute alone (Hulk, {cpu_model}, one core, in memory, same tree): "
          + ", ".join(f"{b['ns_per_query']:.1f} ns per query ({b['qps_one_core'] / 1e6:.1f} M queries/s), {b['mismatches']} mismatches"
                      for b in bench) + ".", ""]

# Controller.
g8 = group(r"a_.*_k8_r1000_rep\d")
w = np.concatenate([v["write_ms"] for v in g8]) if g8 else np.array([])
lines += ["## Control plane (K=8, 1,000 queries/s)", "",
          f"- Digests received per run: {np.mean([v['digests'] for v in g8]):.0f}; leaf installs per run: {np.mean([v['installs'] for v in g8]):.0f}.",
          f"- Controller time from digest receipt to completed table write (delete + insert): median {pct(w, 50):.2f} ms, "
          f"99th percentile {pct(w, 99):.2f} ms.", ""]

# Load sweep.
lines += ["## Load sweep, full stream (3 runs each)", "",
          "| offered queries/s | mode | answered | switch hit rate | answer rate (queries/s) | RTT median | RTT 99th |",
          "|---|---|---|---|---|---|---|"]
sweep = []
for rate in (1000, 5000, 20000, 50000, 100000):
    for k in (8, 0):
        g = group(rf"a_full_0425_to_0426_k{k}_r{rate}_rep\d") if rate == 1000 else group(rf"b_full_k{k}_r{rate}_rep\d")
        if not g:
            continue
        rtt = np.concatenate([np.concatenate([v["rtt_hit"], v["rtt_cpu"]]) for v in g])
        row = {"rate": rate, "k": k, "answered": np.mean([v["answered"] for v in g]), "hit": np.mean([v["switch_hit"] for v in g]),
               "ans_rate": np.mean([v["answer_rate"] for v in g]), "p50": pct(rtt, 50), "p99": pct(rtt, 99)}
        sweep.append(row)
        lines.append(f"| {rate:,} | {'MVM (K=8)' if k else 'CPU only (K=0)'} | {row['answered']:.4f} | {row['hit']:.4f} | "
                     f"{row['ans_rate']:,.0f} | {row['p50']:.1f} µs | {row['p99']:.1f} µs |")
lines.append("")
(ROOT / "docs/results_w8.md").write_text("\n".join(lines))
print("\n".join(lines))

# Figure 1: RTT distributions at 1k qps (full stream).
g8, g0 = group(r"a_full_0425_to_0426_k8_r1000_rep\d"), group(r"a_full_0425_to_0426_k0_r1000_rep\d")
if g8:
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    series = [("switch hit (MVM)", np.concatenate([v["rtt_hit"] for v in g8])),
              ("miss, Hulk CPU (MVM)", np.concatenate([v["rtt_cpu"] for v in g8]))]
    if g0:
        series.append(("CPU only (K=0)", np.concatenate([v["rtt_cpu"] for v in g0])))
    for j, (lab, v) in enumerate(series):
        v = np.sort(v)
        ax.plot(v, np.arange(1, len(v) + 1) / len(v), color=C[j], lw=1.6, label=lab)
    ax.set_xscale("log")
    ax.set(xlabel="round trip measured at Vision (µs)", ylabel="fraction of queries")
    ax.legend(fontsize=7, frameon=False, loc="lower right")
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(FIG / f"w8_rtt_cdf.{ext}", dpi=150)

# Figure 2: load sweep, two panels (answered fraction; median RTT), MVM vs CPU only.
if sweep:
    s = pd.DataFrame(sweep)
    fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.7))
    # every run answered every query, so the left panel shows the MVM switch hit rate instead
    t8 = s[s.k == 8].sort_values("rate")
    axes[0].plot(t8.rate, t8.hit, marker="o", ms=4, color=C[0], lw=1.5, label="MVM (K=8), switch hit rate")
    for j, (k, lab) in enumerate(((8, "MVM (K=8)"), (0, "CPU only (K=0)"))):
        t = s[s.k == k].sort_values("rate")
        axes[1].plot(t.rate, t.p50, marker="o", ms=4, color=C[j], lw=1.5, label=lab)
    for ax in axes:
        ax.set_xscale("log")
        ax.set_xlabel("offered queries per second")
    axes[0].set(ylabel="switch hit rate", ylim=(0, 1.02))
    axes[1].legend(fontsize=7, frameon=False, loc="upper right")
    axes[1].set(ylabel="median round trip (µs)")
    axes[1].set_yscale("log")
    axes[1].set_yticks([30, 50, 100, 200, 300], ["30", "50", "100", "200", "300"])
    axes[1].yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(FIG / f"w8_load_sweep.{ext}", dpi=150)

# Figure 3: rolling switch hit rate vs the ideal simulator (full stream, 1k qps, run 1).
if g8:
    v = g8[0]
    ideal = simulate_fast("dlfu", v["exp_leaf"], 8, gamma=0.99).hits
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    idx = np.arange(len(ideal))
    ax.plot(idx, pd.Series(v["hits_seq"]).rolling(500, min_periods=100).mean(), color=C[0], lw=1.3, label="Tofino switch")
    ax.plot(idx, pd.Series(ideal).rolling(500, min_periods=100).mean(), color=C[1], lw=1.0, ls="--", label="ideal simulator")
    ax.axvline(len(idx) // 2, color="#999", lw=0.8, ls=":")
    ax.set(xlabel="query index", ylabel="hit rate (500-query window)")
    ax.legend(fontsize=7, frameon=False, loc="lower right")
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(FIG / f"w8_rolling_hit_rate.{ext}", dpi=150)
print("figures written")
