"""W5/W6 report: BMv2 prototype checks, hit rates, latency and write rates (docs/results_w5.md, figures)."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES, FIG = ROOT / "results/w5", ROOT / "figures"
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # validated palette (dataviz)
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e6e6e3", "grid.linewidth": 0.6})
NAMES = {"full_0425_to_0426": "full stream, 04-25 to 04-26", "benign_0427_to_0428": "benign flows, 04-27 to 04-28"}

s = json.loads((RES / "summary.json").read_text())
q = pd.read_parquet(RES / "queries.parquet")
t = s["tree"]
lines = ["# W5 / W6 results: MVM-Lite on BMv2", "",
         f"Tree: data-plane DT chosen on validation (grouped split, seed 0): depth {t['depth']}, class weight "
         f"{t['class_weight']}, {t['n_leaves']} leaves, validation macro-F1 {t['val_macro_f1']:.3f}, test macro-F1 "
         f"{t['test_macro_f1']:.3f}. Switch table: K={s['K']} leaf entries, decayed LFU (gamma={s['gamma']}) in the "
         "controller, cold start per slice. Each slice is the chronological replay stream around an attack-phase change. "
         "BMv2 is a software switch: latencies show behavior, not ASIC performance.", "",
         "## Correctness checks", "", "| check | result |", "|---|---|"]
lines += [f"| {k.replace('_', ' ')} | {'PASS' if v else 'FAIL'} |" for k, v in s["checks"].items()]
lines += ["", "## Hit rate and latency per slice", "",
          "| slice | queries | switch hit rate | simulator hit rate | fidelity | hit RTT p50 / p95 / p99 (ms) | miss service p50 / p95 / p99 (ms) | miss: backend p50 / writes p50 (ms) | mean service (ms) |",
          "|---|---|---|---|---|---|---|---|---|"]
for name, r in s["slices"].items():
    h, m = r["hit_rtt_ms"], r["miss_service_ms"]
    lines.append(f"| {NAMES.get(name, name)} | {r['queries']:,} | {r['hit_rate']:.4f} | {r['sim_hit_rate']:.4f} | {r['fidelity']:.4f} | "
                 f"{h['50']:.3f} / {h['95']:.3f} / {h['99']:.3f} | {m['50']:.3f} / {m['95']:.3f} / {m['99']:.3f} | "
                 f"{r['miss_backend_ms_p50']:.3f} / {r['miss_write_ms_p50']:.3f} | {r['mean_service_ms']:.3f} |")
b = s["write_benchmark"]
lines += ["", f"## P4Runtime write rates on BMv2 ({b['n_entries']} range entries)", "",
          "| operation | entries per second |", "|---|---|",
          f"| single-entry INSERT requests | {b['single_insert_per_s']:,.0f} |",
          f"| single-entry DELETE requests | {b['single_delete_per_s']:,.0f} |",
          f"| INSERT, {b['batch']} entries per request | {b['batched_insert_per_s']:,.0f} |",
          f"| DELETE, {b['batch']} entries per request | {b['batched_delete_per_s']:,.0f} |", ""]
(ROOT / "docs/results_w5.md").write_text("\n".join(lines))
print("\n".join(lines))

# Figure 1: latency CDFs (hit round trip vs miss service time), log x.
fig, ax = plt.subplots(figsize=(3.5, 2.6))
for j, (lab, v) in enumerate((("hit: switch round trip", q[q.switch_hit].rtt_ms),
                               ("miss: round trip + full tree + table writes", q[~q.switch_hit].service_ms))):
    v = np.sort(v.to_numpy())
    ax.plot(v, np.arange(1, len(v) + 1) / len(v), color=C[j], lw=1.6, label=lab)
ax.set_xscale("log")
ax.set(xlabel="controller-observed time per query (ms, BMv2)", ylabel="fraction of queries")
ax.legend(fontsize=6.5, frameon=False, loc="lower right")
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(FIG / f"w5_latency_cdf.{ext}", dpi=150)

# Figure 2: rolling hit rate over each slice (switch), phase change at the midpoint.
fig, axes = plt.subplots(1, len(s["slices"]), figsize=(7.16, 2.6), sharey=True, squeeze=False)
for ax, (name, g) in zip(axes[0], q.groupby("slice", sort=False)):
    roll = g.switch_hit.rolling(500, min_periods=100).mean()
    ax.plot(g.t, roll, color=C[0], lw=1.3, label="BMv2 switch")
    ax.plot(g.t, g.sim_hit.rolling(500, min_periods=100).mean(), color=C[1], lw=1.0, ls="--", label="offline simulator")
    ax.axvline(len(g) // 2, color="#999", lw=0.8, ls=":")
    ax.annotate("new local day", (len(g) // 2, 0.03), xycoords=("data", "axes fraction"), xytext=(3, 0),
                textcoords="offset points", fontsize=7, color="#666")
    ax.set(title=NAMES.get(name, name), xlabel="query index")
axes[0][0].set_ylabel("hit rate (500-query window)")
axes[0][-1].legend(fontsize=7, frameon=False, loc="lower right")
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(FIG / f"w5_rolling_hit_rate.{ext}", dpi=150)
print("figures written")
