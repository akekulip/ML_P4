"""W7: every number the report quotes, computed from the result files (docs/report/numbers.json).

Headline model: the data-plane DT depth selected on validation macro-F1 (grouped split, majority
vote over seeds), per the protocol. Caching numbers use the grouped split, full stream, K=8.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from mvm.metrics import binary_from_counts

ROOT = Path(__file__).resolve().parents[1]
W2, W3, W4, W5 = (ROOT / f"results/w{i}" for i in (2, 3, 4, 5))
DEPTHS = ["4", "6", "8", "10", "12", "16", "None"]
FAMILIES = ["DT", "LR", "RF", "HGB"]


def recs(mode):
    return pd.read_json(W2 / mode / "iid_records.json", dtype={"depth": str, "config": str})


def val_selected_depth(r):
    dt = r[(r.fs == "dp") & (r.model == "DT") & (r.split == "val")]
    best = dt.loc[dt.groupby("seed").macro_f1.idxmax()].depth
    return best.value_counts().idxmax(), best.value_counts().to_dict()


def family_test(r, fs, kind, depth=None):
    t = r[(r.fs == fs) & (r.model == kind) & (r.split == "test")]
    if kind == "DT":
        t = t[t.depth == depth]
    return t


N = {}
g, f, rnd = recs("grouped"), recs("forward"), recs("random")
D, votes = val_selected_depth(g)
N["val_depth"], N["val_depth_votes"] = D, votes
N["val_depth_forward"], N["val_depth_forward_votes"] = val_selected_depth(f)
for mode, r in (("grouped", g), ("forward", f), ("random", rnd)):
    d = val_selected_depth(r)[0]
    for fs in ("dp", "full", "dp_ports", "full_ids"):
        for kind in FAMILIES:
            t = family_test(r, fs, kind, d)
            if len(t):
                N[f"{mode}.{fs}.{kind}.macro_f1"] = [float(t.macro_f1.mean()), float(t.macro_f1.std())]
                N[f"{mode}.{fs}.{kind}.benign_recall"] = float(t.benign_recall.mean())
                N[f"{mode}.{fs}.{kind}.attack_recall"] = float(t.attack_recall.mean())
    sweep = r[(r.fs == "dp") & (r.model == "DT") & (r.split == "test")].groupby("depth")
    N[f"{mode}.dp.DT.sweep"] = {d: {"leaves": float(x.n_leaves.mean()), "f1": float(x.macro_f1.mean()), "sd": float(x.macro_f1.std())}
                                for d, x in sweep}
    ctx = r[(r.split == "test") & (r.fs == "dp")]
    N[f"{mode}.dp.test_seen_frac"] = float(ctx.test_seen_frac.mean())
    N[f"{mode}.dp.bayes_ceiling"] = float(ctx.bayes_ceiling_test.mean())
    ccp = r[(r.fs == "dp") & (r.model == "DT-ccp") & (r.split == "test")]
    if len(ccp):
        best = ccp.loc[ccp.macro_f1.idxmax()]
        N[f"{mode}.dp.ccp_best"] = {"leaves": int(best.n_leaves), "f1": float(best.macro_f1)}

# Replay (forward split primary): seed-0 whole-stream macro-F1 and always-attack baseline.
for mode in ("grouped", "forward"):
    rep = pd.read_parquet(W2 / mode / "replay_counts.parquet")
    atk = rep.type != "normal"
    rep["tp"], rep["fn"] = np.where(atk, rep.pred_attack, 0), np.where(atk, rep.n - rep.pred_attack, 0)
    rep["fp"], rep["tn"] = np.where(~atk, rep.pred_attack, 0), np.where(~atk, rep.n - rep.pred_attack, 0)
    s0 = rep[rep.seed == 0]
    for (fs, kind, cfg), x in s0[s0.fs == "dp"].groupby(["fs", "model", "config"]):
        c = x[["tp", "fp", "fn", "tn"]].sum().to_numpy(float)
        m = binary_from_counts(*c)
        N[f"replay.{mode}.{kind}.{cfg}.macro_f1"] = float(m["macro_f1"])
        N[f"replay.{mode}.{kind}.{cfg}.benign_recall"] = float(m["benign_recall"])
    base = s0[(s0.fs == "dp") & (s0.model == "DT") & (s0.config == D)]
    n_att, n_ben = base[base.type != "normal"].n.sum(), base[base.type == "normal"].n.sum()
    N[f"replay.{mode}.always_attack.macro_f1"] = float(binary_from_counts(n_att, n_ben, 0, 0)["macro_f1"])
    inj = base[base.type == "injection"]
    if len(inj):
        N[f"replay.{mode}.DT.injection_recall"] = float(inj.pred_attack.sum() / inj.n.sum())

# Locality (grouped, file order), mean over seeds.
loc = pd.read_parquet(W3 / "locality.parquet")
fo = loc[(loc["mode"] == "grouped") & (loc.ordering == "file")]
for d in DEPTHS:
    for s in ("full", "benign"):
        x = fo[(fo.depth == d) & (fo.stream == s)]
        N[f"loc.{d}.{s}"] = {k: float(x[k].mean()) for k in ("n_leaves", "W90", "W99", "C8", "H_norm", "lru_K8", "lru_K32")}
pt = fo[fo.stream.str.startswith("type:") & (fo.depth == D)].assign(t=lambda x: x.stream.str[5:]).groupby("t").W90.mean()
N["loc.per_type_W90"] = {k: float(v) for k, v in pt.items()}
att = pt.drop(["normal", "mitm"], errors="ignore")
N["loc.attack_W90_range"] = [float(att.min()), float(att.max())]
ords = loc[(loc["mode"] == "grouped") & (loc.depth == D) & (loc.stream == "full")].groupby("ordering")[["lru_K1", "lru_K8"]].mean()
N["loc.orderings"] = ords.to_dict(orient="index")

# Caching (grouped, full stream, K=8).
w4 = pd.read_parquet(W4 / "summary.parquet")
cd = D if D in ("6", "10", "None") else "10"
N["cache_depth"] = cd
for s in ("full", "benign"):
    x = w4[(w4["mode"] == "grouped") & (w4.stream == s) & (w4.depth == cd)]
    hr = x.groupby(["policy", "K"]).hit_rate.mean()
    ch = x.groupby(["policy", "K"]).churn.mean()
    N[f"cache.{s}"] = {p: {int(k): float(hr[(p, k)]) for k in (1, 4, 8, 32)} for p in hr.index.get_level_values(0).unique()}
    N[f"cache.{s}.churn_K8"] = {p: float(ch[(p, 8)]) for p in ch.index.get_level_values(0).unique()}
    N[f"cache.{s}.CK8"] = N[f"loc.{cd}.{s}"]["C8"]
rec_path = W4 / "recovery.parquet"
if rec_path.exists():
    rec = pd.read_parquet(rec_path)
    r = rec[rec.stream == "full"].groupby("policy")[["excess_misses_10k", "flows_to_recover"]].agg(["mean", "max"])
    N["recovery.full"] = {p: {"excess_mean": float(r.loc[p, ("excess_misses_10k", "mean")]),
                              "excess_max": float(r.loc[p, ("excess_misses_10k", "max")]),
                              "flows_mean": float(r.loc[p, ("flows_to_recover", "mean")]),
                              "flows_max": float(r.loc[p, ("flows_to_recover", "max")])} for p in r.index}

# BMv2.
s5 = W5 / "summary.json"
if s5.exists():
    N["bmv2"] = json.loads(s5.read_text())
    N["bmv2.total_queries"] = sum(v["queries"] for v in N["bmv2"]["slices"].values())

out = ROOT / "docs/report/numbers.json"
out.write_text(json.dumps(N, indent=1, default=str))
print(json.dumps({k: N[k] for k in ("val_depth", "val_depth_votes", "val_depth_forward", "cache_depth")}, indent=1))
print("written", out)
