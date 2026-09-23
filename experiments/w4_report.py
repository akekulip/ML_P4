"""W4 report: cache-policy tables (docs/results_w4.md) and figures from results/w4."""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
# W4_RES / W4_OUT let the pre-run gate exercise this report on smoke-test outputs in a scratch dir
RES = Path(os.environ.get("W4_RES", ROOT / "results/w4"))
OUTDIR = Path(os.environ["W4_OUT"]) if "W4_OUT" in os.environ else None
FIG = OUTDIR or ROOT / "figures"
KS = [1, 2, 4, 8, 16, 32, 64]
POLICIES = ["belady", "dlfu_0.99", "dlfu_0.999", "lru", "window_oracle_hour", "lfu", "static_warm"]
LABEL = {"belady": "Belady (offline optimum)", "dlfu_0.99": "decayed LFU, γ=0.99", "dlfu_0.999": "decayed LFU, γ=0.999",
         "lru": "LRU", "window_oracle_hour": "hourly oracle (top-K per hour)", "lfu": "LFU",
         "static_warm": "static top-K from first hour", "best_static": "best static table in hindsight, C(K)"}
# Validated categorical palette (dataviz reference, slots 1-8); >4 series -> legend + markers.
COL = {"belady": "#2a78d6", "dlfu_0.99": "#eb6834", "dlfu_0.999": "#1baf7a", "lru": "#eda100",
       "window_oracle_hour": "#e87ba4", "lfu": "#008300", "static_warm": "#8b5cf6", "best_static": "#555555"}
MK = {"belady": "o", "dlfu_0.99": "s", "dlfu_0.999": "^", "lru": "v", "window_oracle_hour": "D", "lfu": "P",
      "static_warm": "X", "best_static": "*"}
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e6e6e3", "grid.linewidth": 0.6})

s = pd.read_parquet(RES / "summary.parquet")
hourly = pd.read_parquet(RES / "hourly.parquet")
loc_path = ROOT / "results/w3/locality.parquet"
loc = pd.read_parquet(loc_path) if loc_path.exists() else None

lines = ["# W4 / RQ4 results: leaf-cache policies", "",
         "Data-plane DTs from W2 (stand-in training pools), replayed in file order. K = resident leaf entries. "
         "Mean over 5 seeds. Churn counts inserts + evictions per flow (a replacement = one P4Runtime DELETE + one INSERT). Demand policies start cold. Belady is the offline optimum for any policy that "
         "changes at most one entry per miss; the hourly oracle preloads each hour's top-K (not deployable). "
         "'Best static in hindsight' is C(K) from W3: the K most frequent leaves of the whole stream.", ""]

for mode in ("grouped", "forward"):
    for stream in ("full", "benign"):
        for depth in ("6", "10", "None"):
            t = s[(s["mode"] == mode) & (s.stream == stream) & (s.depth == depth)]
            if t.empty:
                continue
            hr = t.groupby(["policy", "K"]).hit_rate.mean().unstack("K").reindex(POLICIES)
            ch = t.groupby(["policy", "K"]).churn.mean().unstack("K").reindex(POLICIES)
            lines += [f"## {mode} / {stream} stream / depth {depth}: hit rate by K (churn = table writes per flow at K=8)", "",
                      "| policy | " + " | ".join(f"K={k}" for k in KS) + " | churn K=8 |", "|---|" + "---|" * (len(KS) + 1)]
            for pol, r in hr.iterrows():
                lines.append(f"| {LABEL[pol]} | " + " | ".join(f"{v:.3f}" for v in r) + f" | {ch.loc[pol, 8]:.4f} |")
            if loc is not None:
                c = loc[(loc["mode"] == mode) & (loc.stream == stream) & (loc.depth == depth) & (loc.ordering == "file")]
                if not c.empty:
                    lines.append("| " + LABEL["best_static"] + " | " + " | ".join(f"{c[f'C{k}'].mean():.3f}" for k in KS) + " | 0 |")
            gap = (hr.loc["belady"] - hr.loc["dlfu_0.99"])
            lines += ["", f"Regret of decayed LFU (γ=0.99) vs Belady, in hit rate: " + ", ".join(f"K={k}: {v:.3f}" for k, v in gap.items()), ""]

lines += ["Recovery after attack-phase changes is in docs/results_w4_recovery.md (experiments/w4_recovery.py).", ""]

(OUTDIR or ROOT / "docs").joinpath("results_w4.md").write_text("\n".join(lines))
print("\n".join(lines))

# Figure 1: hit rate vs K per policy (grouped, depth 10; full and benign).
fig, axes = plt.subplots(1, 2, figsize=(7.16, 3.0), sharey=True)
for ax, stream in zip(axes, ("full", "benign")):
    t = s[(s["mode"] == "grouped") & (s.stream == stream) & (s.depth == "10")]
    for pol in POLICIES:
        r = t[t.policy == pol].groupby("K").hit_rate.mean()
        ax.plot(r.index, r.values, marker=MK[pol], ms=3.5, lw=1.3, color=COL[pol], label=LABEL[pol])
    if loc is not None:
        c = loc[(loc["mode"] == "grouped") & (loc.stream == stream) & (loc.depth == "10") & (loc.ordering == "file")]
        ax.plot(KS, [c[f"C{k}"].mean() for k in KS], ls="--", color=COL["best_static"], marker=MK["best_static"], ms=4,
                lw=1.1, label=LABEL["best_static"])
    ax.set_xscale("log", base=2)
    ax.set_xticks(KS, [str(k) for k in KS])
    ax.set(xlabel="resident leaves K", title=f"{'full replay stream' if stream == 'full' else 'benign flows only'} (depth 10)")
axes[0].set_ylabel("hit rate")
axes[1].legend(fontsize=6.5, frameon=False, loc="lower right")
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(FIG / f"w4_hit_rate_vs_k.{ext}", dpi=150)

# Figure 2: hourly hit rate over time at K=8 for four policies, with attack share below (no dual axis).
h = hourly[(hourly["mode"] == "grouped") & (hourly.stream == "full") & (hourly.depth == "10") & (hourly.K == 8)].copy()
h["rate"] = h.hits / h.n
show = ["belady", "dlfu_0.99", "lru", "static_warm"]
fig, axes = plt.subplots(2, 1, figsize=(7.16, 3.8), sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})
seed0 = h[h.seed == 0]
for pol in show:
    g = seed0[seed0.policy == pol].sort_values("hour")
    axes[0].plot(pd.to_datetime(g.hour, format="%Y-%m-%d %H"), g.rate, lw=1.0, color=COL[pol], label=LABEL[pol])
axes[0].set(ylabel="hourly hit rate, K=8", ylim=(-0.02, 1.02))
axes[0].legend(fontsize=6.5, frameon=False, loc="lower left", ncol=2)
axes[0].set_title("Hit rate across attack phases (grouped split, depth 10, seed 0; Canberra time)")
drift_path = ROOT / "results/w3/drift_hourly.parquet"
if drift_path.exists():
    d = pd.read_parquet(drift_path)
    d = d[(d["mode"] == "grouped") & (d.depth == "10")].sort_values("hour")
    axes[1].plot(pd.to_datetime(d.hour, format="%Y-%m-%d %H"), d.attack_frac, color="#666", lw=1.0)
axes[1].set(ylabel="attack share", ylim=(-0.05, 1.05))
fig.autofmt_xdate()
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(FIG / f"w4_hourly_hit_rate.{ext}", dpi=150)
print("figures written")
