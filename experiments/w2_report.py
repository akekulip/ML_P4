"""W2 report: tables (results/w2/tables.md) and figures from results/w2/{grouped,forward,random}.

Intervals: IID = mean ± sd over seeds (primary). Replay = 95% block bootstrap over local hours
(the stream is serially dependent), seed-0 models; data-plane DTs also mean ± sd over seeds.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from mvm.metrics import binary_from_counts

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results/w2"
FIG = ROOT / "figures"
MODES = [m for m in ("grouped", "forward", "random") if (RES / m / "iid_records.json").exists()]
FAMILIES = ["DT", "LR", "RF", "HGB"]
# Validated palette (dataviz: CVD + normal-vision PASS; contrast WARN -> direct labels + markers).
COLORS = {"DT": "#2a78d6", "RF": "#eb6834", "LR": "#1baf7a", "HGB": "#eda100", "DT-ccp": "#e87ba4"}
MARKERS = {"DT": "o", "RF": "s", "LR": "^", "HGB": "v", "DT-ccp": "D"}
FS_ORDER = ["dp", "full", "dp_ports", "full_ids"]
FS_LABEL = {"dp": "data-plane", "full": "full (Zeek)", "dp_ports": "data-plane + ports", "full_ids": "full + ports + IPs"}
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e6e6e3", "grid.linewidth": 0.6})


def load(mode):
    rec = pd.read_json(RES / mode / "iid_records.json", dtype={"depth": str, "config": str})
    rep = pd.read_parquet(RES / mode / "replay_counts.parquet")
    atk = rep.type != "normal"
    rep["tp"] = np.where(atk, rep.pred_attack, 0)
    rep["fn"] = np.where(atk, rep.n - rep.pred_attack, 0)
    rep["fp"] = np.where(~atk, rep.pred_attack, 0)
    rep["tn"] = np.where(~atk, rep.n - rep.pred_attack, 0)
    return rec, rep


def best_rows(test, val, fs, kind):
    """Test rows of the val-selected configuration (DT: val-best depth on seed 0)."""
    t = test[(test.fs == fs) & (test.model == kind)]
    if kind == "DT":
        v = val[(val.fs == fs) & (val.model == "DT") & (val.seed == 0)]
        t = t[t.depth == v.loc[v.macro_f1.idxmax(), "depth"]]
    return t


def hour_bootstrap(counts: pd.DataFrame, n_boot=2000, seed=0):
    c = counts.groupby("hour")[["tp", "fp", "fn", "tn"]].sum().to_numpy(float)
    idx = np.random.default_rng(seed).integers(0, len(c), size=(n_boot, len(c)))
    b = binary_from_counts(*c[idx].sum(axis=1).T)
    return {k: (np.percentile(v, 2.5), np.percentile(v, 97.5)) for k, v in b.items()}


def pm(s):
    return f"{s.mean():.4f} ± {s.std():.4f}" if len(s) > 1 else f"{s.mean():.4f}"


lines = ["# W2 / RQ1 results", "",
         "Split modes: **grouped** (each distinct data-plane vector in one pool; primary IID), "
         "**forward** (grouped + pools from first half of each local day, replay = second halves; primary replay), "
         "**random** (row-level; shown only to quantify duplicate leakage). "
         "Training source: stand-in pools with the Train_Test class mix (train_test_network.csv not yet available).", ""]
data = {m: load(m) for m in MODES}

for mode in MODES:
    rec, rep = data[mode]
    b = rec[rec.model.isin(FAMILIES + ["DT-ccp"])]
    test, val = b[b.split == "test"], b[b.split == "val"]
    lines += [f"## {mode}: IID test, val-selected configuration per family ({test.seed.nunique()} seeds, mean ± sd)", "",
              "| features | model | config (seed 0) | macro-F1 | novel-vector macro-F1 | MCC | attack recall | benign recall | PR-AUC | leaves |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for fs in FS_ORDER:
        for kind in FAMILIES:
            t = best_rows(test, val, fs, kind)
            if t.empty:
                continue
            leaves = f"{t.n_leaves.mean():.0f}" if kind == "DT" else "–"
            nov = pm(t.macro_f1_novel.dropna()) if "macro_f1_novel" in t and t.macro_f1_novel.notna().any() else "–"
            lines.append(f"| {FS_LABEL[fs]} | {kind} | {t[t.seed == 0].config.iloc[0]} | {pm(t.macro_f1)} | {nov} | "
                         f"{t.mcc.mean():.4f} | {t.attack_recall.mean():.4f} | {t.benign_recall.mean():.4f} | "
                         f"{t.pr_auc.mean():.4f} | {leaves} |")
    ctx = test.groupby("fs")[["test_seen_frac", "bayes_ceiling_test"]].mean()
    lines += ["", "Test vectors also present in training, and Bayes accuracy ceiling (label conflicts on identical vectors):", "",
              ctx.round(4).to_markdown(), ""]

    lines += [f"### {mode}: DT depth sweep, data-plane features", "",
              "| depth | leaves | macro-F1 | MCC | attack recall | benign recall |", "|---|---|---|---|---|---|"]
    for d, g in test[(test.fs == "dp") & (test.model == "DT")].groupby("depth", sort=False):
        lines.append(f"| {d} | {g.n_leaves.mean():.0f} | {pm(g.macro_f1)} | {g.mcc.mean():.4f} | "
                     f"{g.attack_recall.mean():.4f} | {g.benign_recall.mean():.4f} |")
    lines.append("")

    mc = rec[rec.model == "DT-multiclass"]
    if not mc.empty:
        lines += [f"### {mode}: 10-class DT (IID test, mean over seeds)", ""]
        for fs, g in mc.groupby("fs"):
            m = pd.DataFrame(list(g.multiclass))
            pcr = pd.DataFrame(list(m.per_class_recall)).mean()
            lines.append(f"- **{FS_LABEL[fs]}** ({g.config.iloc[0]}): macro-F1 {pm(m.macro_f1)}, balanced acc "
                         f"{m.balanced_accuracy.mean():.4f}; recall: " + ", ".join(f"{k} {v:.3f}" for k, v in pcr.items()))
        lines.append("")

    # Replay: whole stream, seed-0 models, hour-block bootstrap.
    s0 = rep[rep.seed == 0]
    first = s0.groupby(["fs", "model", "config"]).size().index[0]
    base = s0[(s0.fs == first[0]) & (s0.model == first[1]) & (s0.config == first[2])]
    stream_n = base.groupby("type").n.sum()
    n_att, n_ben = stream_n.drop("normal", errors="ignore").sum(), stream_n.get("normal", 0)
    aa = binary_from_counts(n_att, n_ben, 0, 0)
    lines += [f"### {mode}: chronological replay (seed-0 models; 95% block bootstrap over local hours)", "",
              "| features | model | config | flows | macro-F1 [95% CI] | MCC | attack recall | benign recall |",
              "|---|---|---|---|---|---|---|---|",
              f"| – | always-attack | – | {int(n_att + n_ben):,} | {float(aa['macro_f1']):.4f} | {float(aa['mcc']):.4f} | 1.0000 | 0.0000 |"]
    for (fs, kind, cfg), g in s0.groupby(["fs", "model", "config"]):
        if kind == "DT" and cfg not in ("8", "12", "None"):
            continue
        s = g[["tp", "fp", "fn", "tn"]].sum()
        m = binary_from_counts(*s)
        ci = hour_bootstrap(g)["macro_f1"]
        lines.append(f"| {FS_LABEL[fs]} | {kind} | {cfg} | {int(s.sum()):,} | {float(m['macro_f1']):.4f} "
                     f"[{ci[0]:.4f}, {ci[1]:.4f}] | {float(m['mcc']):.4f} | {float(m['attack_recall']):.4f} | "
                     f"{float(m['benign_recall']):.4f} |")
    dts = rep[(rep.fs == "dp") & (rep.model == "DT")].groupby(["config", "seed"])[["tp", "fp", "fn", "tn"]].sum()
    f1 = pd.Series(binary_from_counts(*dts.to_numpy(float).T)["macro_f1"], index=dts.index)
    lines += ["", "Data-plane DT replay macro-F1 across seeds: " +
              ", ".join(f"depth {c}: {pm(v)}" for c, v in f1.groupby(level=0)), ""]

    # Per-type replay recall.
    v = val[(val.fs == "dp") & (val.model == "DT") & (val.seed == 0)]
    best_d = v.loc[v.macro_f1.idxmax(), "depth"]
    sel = s0[(s0.fs == "dp") & (((s0.model == "DT") & (s0.config == best_d)) | s0.model.isin(["RF", "LR", "HGB"]))]
    pt = sel.assign(correct=np.where(sel.type == "normal", sel.n - sel.pred_attack, sel.pred_attack)) \
        .groupby(["model", "type"])[["correct", "n"]].sum()
    pt = (pt.correct / pt.n).unstack(0)
    trained = pd.read_csv(RES / mode / "pool_sizes_seed0.csv", index_col=0)["train"]
    pt["train_rows"] = trained.reindex(pt.index).fillna(0).astype(int)
    pt["replay_rows"] = stream_n.reindex(pt.index).astype(int)
    lines += [f"### {mode}: replay per-type recall, data-plane features (DT = depth {best_d}; seed 0)", "",
              pt.round(4).to_markdown(), ""]

    # IID per-type recall reweighted to the replay's class mix.
    lines += [f"### {mode}: IID per-type recall reweighted to the replay's class mix (seed 0)", "",
              "| features | model | reweighted macro-F1 | IID macro-F1 |", "|---|---|---|---|"]
    for fs in ("dp", "full"):
        for kind in FAMILIES:
            t0 = best_rows(test, val, fs, kind)
            t0 = t0[t0.seed == 0]
            if t0.empty:
                continue
            r = pd.Series(t0.per_type_recall.iloc[0])
            n = stream_n.reindex(r.index).fillna(0)
            att = r.index != "normal"
            tp, fn = (r[att] * n[att]).sum(), ((1 - r[att]) * n[att]).sum()
            tn = r.get("normal", 0) * n.get("normal", 0)
            fp = n.get("normal", 0) - tn
            lines.append(f"| {FS_LABEL[fs]} | {kind} | {float(binary_from_counts(tp, fp, fn, tn)['macro_f1']):.4f} | "
                         f"{t0.macro_f1.iloc[0]:.4f} |")
    lines.append("")

if {"random", "grouped"} <= set(MODES):
    lines += ["## Duplicate leakage: random vs grouped split (IID test macro-F1, data-plane features)", "",
              "| model | random | grouped | inflation |", "|---|---|---|---|"]
    for kind in FAMILIES:
        vals = {}
        for mode in ("random", "grouped"):
            b = data[mode][0]
            b = b[b.model.isin(FAMILIES)]
            vals[mode] = best_rows(b[b.split == "test"], b[b.split == "val"], "dp", kind).macro_f1.mean()
        lines.append(f"| {kind} | {vals['random']:.4f} | {vals['grouped']:.4f} | {vals['random'] - vals['grouped']:+.4f} |")
    lines.append("")

(RES / "tables.md").write_text("\n".join(lines))
print("\n".join(lines))

# Figure 1: macro-F1 vs leaves (main split), depth sweep + ccp path; other families as reference lines.
main_mode = "grouped" if "grouped" in MODES else MODES[0]
rec = data[main_mode][0]
b = rec[rec.model.isin(FAMILIES + ["DT-ccp"])]
test, val = b[b.split == "test"], b[b.split == "val"]
fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.9), sharey=True)
for ax, fs in zip(axes, ["dp", "full"]):
    t = test[test.fs == fs]
    g = t[t.model == "DT"].groupby("depth", sort=False).agg(x=("n_leaves", "mean"), y=("macro_f1", "mean"), e=("macro_f1", "std"))
    c = t[t.model == "DT-ccp"].sort_values("n_leaves")
    if not c.empty:
        ax.plot(c.n_leaves, c.macro_f1, color=COLORS["DT-ccp"], marker=MARKERS["DT-ccp"], ms=3, lw=1.2, label="DT, ccp pruning")
    ax.errorbar(g.x, g.y, yerr=g.e, color=COLORS["DT"], marker=MARKERS["DT"], ms=4, lw=1.5, capsize=2, label="DT, max depth")
    for x, y, d in zip(g.x, g.y, g.index):
        ax.annotate(f"d={d}", (x, y), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=7, color="#555")
    xmin = min(g.x.min(), c.n_leaves.min() if not c.empty else g.x.min())
    for kind in ("RF", "HGB", "LR"):
        y = best_rows(test, val, fs, kind).macro_f1.mean()
        ax.axhline(y, color=COLORS[kind], lw=1.1, ls="--")
        ax.text(xmin, y + 0.003, f"{kind} {y:.3f}", color="#333", fontsize=7)
    ax.set_xscale("log")
    ax.set(xlabel="leaves (log scale)", title=f"{FS_LABEL[fs]} (Bayes acc. ceiling {t.bayes_ceiling_test.mean():.3f})")
axes[0].set_ylabel(f"macro-F1, IID test ({main_mode} split)")
axes[0].legend(loc="lower right", fontsize=7, frameon=False)
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(FIG / f"w2_f1_vs_leaves.{ext}", dpi=150)

# Figure 2: feature-set ablation, one panel per split mode.
fig, axes = plt.subplots(1, len(MODES), figsize=(2.4 * len(MODES) + 0.6, 2.8), sharey=True, squeeze=False)
for ax, mode in zip(axes[0], MODES):
    b = data[mode][0]
    b = b[b.model.isin(FAMILIES)]
    test, val = b[b.split == "test"], b[b.split == "val"]
    for j, kind in enumerate(FAMILIES):
        ys = [best_rows(test, val, fs, kind).macro_f1 for fs in FS_ORDER]
        ax.errorbar(np.arange(4) + (j - 1.5) * 0.15, [y.mean() for y in ys], yerr=[y.std() for y in ys],
                    fmt=MARKERS[kind], color=COLORS[kind], ms=4, capsize=2, label=kind)
    ax.set_xticks(range(4), ["dp", "full", "dp+\nports", "full+\nIDs"], fontsize=7)
    ax.set_title(f"{mode} split")
axes[0][0].set_ylabel("macro-F1 (IID test)")
axes[0][-1].legend(fontsize=7, frameon=False, loc="lower right")
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(FIG / f"w2_feature_ablation.{ext}", dpi=150)
print("figures written")
