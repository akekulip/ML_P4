"""W3 report: tables (docs/results_w3.md) and figures from results/w3."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.ticker
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES, W2, FIG = ROOT / "results/w3", ROOT / "results/w2", ROOT / "figures"
DEPTHS = ["4", "6", "8", "10", "12", "16", "None"]
KS = [1, 2, 4, 8, 16, 32, 64]
# Validated categorical palette (dataviz): slots 1-4; contrast WARN -> direct labels / markers.
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e6e6e3", "grid.linewidth": 0.6})

loc = pd.read_parquet(RES / "locality.parquet")
drift = pd.read_parquet(RES / "drift_hourly.parquet")
f1 = []
for mode in ("grouped", "forward"):
    rec = pd.read_json(W2 / mode / "iid_records.json", dtype={"depth": str})
    t = rec[(rec.fs == "dp") & (rec.model == "DT")]
    f1.append(t.pivot_table(index=["seed", "depth"], columns="split", values="macro_f1").reset_index().assign(mode=mode))
f1 = pd.concat(f1).rename(columns={"test": "iid_f1", "val": "val_f1"})
filel = loc[loc.ordering == "file"]


def agg(df, cols):
    g = df.groupby("depth")[cols].agg(["mean", "std"])
    return g.reindex([d for d in DEPTHS if d in g.index])


def ms(m, s, fmt="{:.3f}"):
    return f"{fmt.format(m)} ± {fmt.format(s)}"


lines = ["# W3 / RQ2-RQ3 results: leaf locality under chronological replay", "",
         "Data-plane decision trees from W2, replayed in time order over the replay stream of each split "
         "(grouped: all days; forward: second half of each day). Mean ± sd over 5 seeds. "
         "W_q = fewest leaves serving a fraction q of flows; C(K) = share served by the K most frequent leaves "
         "(the best any fixed K-leaf table can do on that stream); LRU hit = online cache with K entries, cold start. "
         "Training source: stand-in pools (train_test_network.csv not yet available).", ""]

for mode in ("grouped", "forward"):
    fl = filel[filel["mode"] == mode]
    full, ben = fl[fl.stream == "full"], fl[fl.stream == "benign"]
    ff = f1[f1["mode"] == mode].groupby("depth")[["iid_f1", "val_f1"]].mean()
    A = agg(full, ["n_leaves", "W90", "W99", "C8", "H_norm", "lru_K8", "lru_K32"])
    B = agg(ben, ["W90", "W99", "C8", "lru_K8", "lru_K32"])
    lines += [f"## {mode}: working set vs tree size", "",
              "| depth | leaves | IID macro-F1 | full W90 | full W99 | full C(8) | full H_norm | full LRU K=8 | full LRU K=32 | benign W90 | benign W99 | benign C(8) | benign LRU K=8 | benign LRU K=32 |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for d in A.index:
        a, b = A.loc[d], B.loc[d]
        lines.append(f"| {d} | {a[('n_leaves','mean')]:.0f} | {ff.loc[d,'iid_f1']:.3f} | "
                     f"{ms(a[('W90','mean')], a[('W90','std')], '{:.1f}')} | {ms(a[('W99','mean')], a[('W99','std')], '{:.0f}')} | "
                     f"{a[('C8','mean')]:.3f} | {a[('H_norm','mean')]:.3f} | {a[('lru_K8','mean')]:.3f} | {a[('lru_K32','mean')]:.3f} | "
                     f"{ms(b[('W90','mean')], b[('W90','std')], '{:.1f}')} | {ms(b[('W99','mean')], b[('W99','std')], '{:.0f}')} | "
                     f"{b[('C8','mean')]:.3f} | {b[('lru_K8','mean')]:.3f} | {b[('lru_K32','mean')]:.3f} |")
    lines.append("")

    # Ordering robustness.
    lines += [f"### {mode}: LRU hit rate under three flow orderings (mean over seeds)", "",
              "| depth | stream | ordering | " + " | ".join(f"K={k}" for k in KS) + " |", "|---|---|---|" + "---|" * len(KS)]
    om = loc[(loc["mode"] == mode) & loc.stream.isin(["full", "benign"]) & loc.depth.isin(["6", "10", "None"])]
    g = om.groupby(["depth", "stream", "ordering"])[[f"lru_K{k}" for k in KS]].mean()
    for (d, s, o), r in g.iterrows():
        lines.append(f"| {d} | {s} | {o} | " + " | ".join(f"{v:.3f}" for v in r) + " |")
    lines.append("")

    # Per phase (day) and per type.
    per_day = fl[fl.stream.str.startswith("day:") & (fl.depth == "10")].assign(day=lambda x: x.stream.str[4:])
    pdg = per_day.groupby("day")[["n", "leaves_visited", "W90", "W99", "C8", "lru_K8"]].mean()
    lines += [f"### {mode}: per local day (attack phase), depth 10", "", pdg.round(3).to_markdown(), ""]
    per_type = fl[fl.stream.str.startswith("type:") & (fl.depth == "10")].assign(type=lambda x: x.stream.str[5:])
    ptg = per_type.groupby("type")[["n", "leaves_visited", "W90", "W99", "C8"]].mean()
    lines += [f"### {mode}: per attack type, depth 10 (are classes concentrated in few leaves?)", "", ptg.round(3).to_markdown(), ""]

    # Pareto frontier: IID macro-F1 vs benign W90 (the stream where capacity matters).
    pts = pd.DataFrame({"f1": ff.iid_f1, "W90_full": A[("W90", "mean")], "W90_benign": B[("W90", "mean")]}).dropna()
    nd = [d for d in pts.index if not any((pts.f1 >= pts.loc[d, "f1"]) & (pts.W90_benign <= pts.loc[d, "W90_benign"])
                                          & ((pts.f1 > pts.loc[d, "f1"]) | (pts.W90_benign < pts.loc[d, "W90_benign"])))]
    lines += [f"Pareto-optimal depths ({mode}; IID macro-F1 vs benign W90): {', '.join(nd)}", ""]

dr = drift[(drift["mode"] == "grouped") & (drift.depth == "10")]
top = dr.nlargest(8, "js_prev")[["hour", "js_prev", "attack_frac", "n"]]
lines += ["## Hourly drift of the leaf distribution (grouped, seed 0, depth 10)", "",
          f"Median hourly JS divergence {dr.js_prev.median():.3f}; the eight largest jumps:", "", top.round(3).to_markdown(index=False), ""]

(ROOT / "docs/results_w3.md").write_text("\n".join(lines))
print("\n".join(lines))

# Figure 1: leaf rank-frequency, full vs benign (grouped, seed 0).
mask = np.load(W2 / "grouped/replay_mask_seed0.npy")
from mvm.splits import build_keys, replay_order  # noqa: E402

keys = build_keys(ROOT / "data/processed/network", ROOT / "data/processed/keys.parquet")
label = keys.label.to_numpy()[replay_order(keys, mask)]
fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.7), sharey=True)
for j, d in enumerate(["6", "10", "None"]):
    leaf = np.load(W2 / f"grouped/leaves/seed0_dp_DT_depth{d}.npy")
    for ax, sel, name in ((axes[0], slice(None), "full replay stream"), (axes[1], label == 0, "benign flows only")):
        _, c = np.unique(leaf[sel], return_counts=True)
        p = np.sort(c)[::-1] / c.sum()
        ax.loglog(np.arange(1, len(p) + 1), p, color=C[j], lw=1.6, label=f"depth {d} ({len(p)} leaves used)")
        ax.set(title=name, xlabel="leaf rank")
axes[0].set_ylabel("share of flows")
for ax in axes:
    ax.legend(fontsize=7, frameon=False, loc="lower left")
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(FIG / f"w3_rank_frequency.{ext}", dpi=150)

# Figure 2: Pareto, IID macro-F1 vs W90 (full and benign), grouped, with switch-table capacities.
fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.8), sharey=True)
fl = filel[filel["mode"] == "grouped"]
ff = f1[f1["mode"] == "grouped"].groupby("depth").iid_f1.agg(["mean", "std"]).reindex(DEPTHS)
for ax, s, title in ((axes[0], "full", "full replay stream"), (axes[1], "benign", "benign flows only")):
    w = fl[fl.stream == s].groupby("depth").W90.agg(["mean", "std"]).reindex(DEPTHS)
    ax.errorbar(w["mean"], ff["mean"], xerr=w["std"], yerr=ff["std"], fmt="o-", color=C[0], ms=4, lw=1.2, capsize=2)
    for i, d in enumerate(DEPTHS):
        ax.annotate(f"d={d}", (w.loc[d, "mean"], ff.loc[d, "mean"]), textcoords="offset points",
                    xytext=(5, 5 if i % 2 else -11), fontsize=7, color="#555")
    for k in (8, 32, 64):
        ax.axvline(k, color="#999", lw=0.8, ls=":")
        ax.annotate(f"K={k}", (k, 0.97), xycoords=("data", "axes fraction"), xytext=(2, 0), textcoords="offset points",
                    fontsize=7, color="#666")
    ax.set_xscale("log")
    ticks = [2, 4, 8, 16, 32, 64]
    ax.set_xticks(ticks, [str(t) for t in ticks])
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set(xlabel="W90: leaves serving 90% of flows (log)", title=title)
axes[0].set_ylabel("macro-F1, IID test (grouped)")
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(FIG / f"w3_pareto_f1_vs_w90.{ext}", dpi=150)

# Figure 3: LRU hit rate vs K under three orderings, against C(K) (best fixed table), depth 10, grouped.
fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.8), sharey=True)
names = {"file": "file order", "shuffle_within_second": "shuffled within second", "flow_end": "flow-end time"}
g = loc[(loc["mode"] == "grouped") & (loc.depth == "10")]
for ax, s in ((axes[0], "full"), (axes[1], "benign")):
    for j, (o, lab) in enumerate(names.items()):
        r = g[(g.stream == s) & (g.ordering == o)][[f"lru_K{k}" for k in KS]].mean()
        ax.plot(KS, r.values, marker="o", ms=3.5, color=C[j], lw=1.5, label=f"LRU, {lab}")
    ck = g[(g.stream == s) & (g.ordering == "file")][[f"C{k}" for k in KS]].mean()
    ax.plot(KS, ck.values, color=C[3], lw=1.5, ls="--", marker="D", ms=3, label="best fixed table C(K)")
    ax.set_xscale("log", base=2)
    ax.set_xticks(KS, [str(k) for k in KS])
    ax.set(xlabel="resident leaves K", title=f"{'full replay stream' if s == 'full' else 'benign flows only'} (depth 10)")
axes[0].set_ylabel("hit rate")
axes[1].legend(fontsize=7, frameon=False, loc="lower right")
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(FIG / f"w3_lru_orderings.{ext}", dpi=150)

# Figure 4: hourly drift (two stacked panels, shared time axis; no dual y-axis).
dr = dr.sort_values("hour")
x = pd.to_datetime(dr.hour, format="%Y-%m-%d %H")
fig, axes = plt.subplots(2, 1, figsize=(7.16, 3.6), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
axes[0].plot(x, dr.js_prev, color=C[0], lw=1.0, marker=".", ms=3)
axes[0].set_ylabel("JS divergence\nvs previous hour")
axes[1].plot(x, dr.attack_frac, color=C[1], lw=1.0, marker=".", ms=3)
axes[1].set(ylabel="attack share", ylim=(-0.05, 1.05))
axes[0].set_title("Hourly change of the leaf distribution (grouped split, depth 10, seed 0; Canberra time)")
fig.autofmt_xdate()
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(FIG / f"w3_hourly_drift.{ext}", dpi=150)
print("figures written")
