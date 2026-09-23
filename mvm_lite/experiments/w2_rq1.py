"""W2 / RQ1: can a compact DT on network-observable features detect attacks competitively?

Protocol per split mode (random | grouped | forward; see mvm/splits.py) and seed:
  - pools (train / val / IID test) with the Train_Test class mix; pooled rows leave the replay
  - hyperparameters chosen on val macro-F1 only; LR / RF / HGB grids searched on seed 0 and the
    seed-0 choice refit on later seeds; every DT depth and ccp alpha is recorded (RQ3 needs them)
  - IID test metrics + per-type recall + "seen vs novel vector" split + Bayes ceiling
  - chronological replay: every seed replays the data-plane DTs (leaf streams saved for W3/W4);
    seed 0 also replays the chosen LR / RF / HGB / DT of every feature set. Counts are kept per
    local hour x type so the report can block-bootstrap over hours (the stream is serially dependent).

Usage: uv run python experiments/w2_rq1.py --split grouped [--seeds 0 1 2 3 4] [--quick]
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

from mvm.features import FEATURE_SETS, TreeEncoder, columns_needed
from mvm.metrics import binary_metrics, multiclass_metrics
from mvm.splits import build_keys, iter_replay, load_rows, sample_pools

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("w2")
ROOT = Path(__file__).resolve().parents[1]
PQ = ROOT / "data/processed/network"
KEYS = ROOT / "data/processed/keys.parquet"
DEPTHS = [4, 6, 8, 10, 12, 16, None]
CW = [None, "balanced"]
GRIDS = {
    "LR": [dict(C=c, cw=cw) for c in (0.01, 0.1, 1.0, 10.0) for cw in CW],
    "RF": [dict(depth=d, cw=cw) for d in (8, 16, None) for cw in CW],
    "HGB": [dict(leaves=l, cw=cw) for l in (31, 127) for cw in CW],
}
N_JOBS = 32
TYPES = ["normal", "backdoor", "ddos", "dos", "injection", "mitm", "password", "ransomware", "scanning", "xss"]


def make_model(kind: str, g: dict, fs, seed: int):
    if kind == "LR":
        n_num, n_cat, n_oct = len(fs.numeric), len(fs.categorical), 4 * len(fs.ips)
        num = list(range(n_num)) + list(range(n_num + n_cat, n_num + n_cat + n_oct))
        cat = list(range(n_num, n_num + n_cat))
        signed_log = FunctionTransformer(lambda x: np.sign(x) * np.log1p(np.abs(x)))
        pre = ColumnTransformer([("num", make_pipeline(signed_log, StandardScaler()), num),
                                 ("cat", OneHotEncoder(handle_unknown="ignore"), cat)])
        return make_pipeline(pre, LogisticRegression(C=g["C"], class_weight=g["cw"], max_iter=3000))
    if kind == "RF":
        return RandomForestClassifier(100, max_depth=g["depth"], class_weight=g["cw"], n_jobs=N_JOBS, random_state=seed)
    if kind == "HGB":
        return HistGradientBoostingClassifier(max_leaf_nodes=g["leaves"], class_weight=g["cw"], random_state=seed)
    raise ValueError(kind)


def cfg_name(kind: str, **kw) -> str:
    return kind + "(" + ",".join(f"{k}={v}" for k, v in kw.items()) + ")"


def row_hash(X: np.ndarray) -> np.ndarray:
    return pd.util.hash_pandas_object(pd.DataFrame(X), index=False).to_numpy()


def bayes_ceiling(h: np.ndarray, y: np.ndarray) -> float:
    """Best achievable accuracy when identical vectors carry different labels."""
    t = pd.DataFrame({"h": h, "y": y}).groupby(["h", "y"]).size().groupby(level=0).max()
    return float(t.sum() / len(y))


def run_seed(seed, rows, mode, grid_choice, records, fitted):
    tr, va, te = (rows[rows.pool == p] for p in ("train", "val", "test"))
    ytr, yva, yte = tr.label.to_numpy(), va.label.to_numpy(), te.label.to_numpy()
    for fs_name, fs in FEATURE_SETS.items():
        enc = TreeEncoder(fs).fit(tr, ytr)
        Xtr, Xva, Xte = enc.transform(tr), enc.transform(va), enc.transform(te)
        seen = np.isin(row_hash(Xte), row_hash(Xtr))
        common = {"seed": seed, "split_mode": mode, "fs": fs_name,
                  "test_seen_frac": float(seen.mean()),
                  "bayes_ceiling_test": bayes_ceiling(row_hash(Xte), yte)}

        def record(kind, cfg, model, **extra):
            for split, X, y, types in (("val", Xva, yva, va.type), ("test", Xte, yte, te.type)):
                pred = model.predict(X)
                r = {**common, "model": kind, "config": cfg, "split": split, **extra,
                     **binary_metrics(y, pred, model.predict_proba(X)[:, 1])}
                correct = pred == y
                r["per_type_recall"] = pd.Series(correct).groupby(types.to_numpy()).mean().to_dict()
                if split == "test":
                    for tag, m in (("seen", seen), ("novel", ~seen)):
                        if m.sum() > 0 and len(np.unique(y[m])) == 2:
                            r[f"macro_f1_{tag}"] = binary_metrics(y[m], pred[m])["macro_f1"]
                            r[f"n_{tag}"] = int(m.sum())
                records.append(r)

        for d in DEPTHS:
            best = max((DecisionTreeClassifier(max_depth=d, class_weight=cw, random_state=seed).fit(Xtr, ytr) for cw in CW),
                       key=lambda m: binary_metrics(yva, m.predict(Xva))["macro_f1"])
            record("DT", cfg_name("DT", depth=d, cw=best.class_weight), best, depth=str(d), n_leaves=int(best.get_n_leaves()))
            if fs_name == "dp" or seed == 0:
                fitted[(fs_name, "DT", str(d))] = (enc, best)

        if seed == 0 and fs_name in ("dp", "full"):
            full_tree = DecisionTreeClassifier(random_state=0).fit(Xtr, ytr)
            alphas = full_tree.cost_complexity_pruning_path(Xtr, ytr).ccp_alphas
            pos = alphas[(alphas > 0) & (alphas < alphas[-1])]
            for a in np.r_[0.0, np.geomspace(pos.min(), pos.max(), 20)]:
                m = DecisionTreeClassifier(ccp_alpha=a, random_state=0).fit(Xtr, ytr)
                record("DT-ccp", cfg_name("DT", ccp_alpha=f"{a:.3g}"), m, ccp_alpha=float(a),
                       n_leaves=int(m.get_n_leaves()), depth=str(m.get_depth()))

        for kind, grid in GRIDS.items():
            if seed == 0:
                scored = []
                for g in grid:
                    m = make_model(kind, g, fs, 0).fit(Xtr, ytr)
                    scored.append((binary_metrics(yva, m.predict(Xva))["macro_f1"], g, m))
                    log.info("[%s] seed0 %s %s %s val macro-F1 %.4f", mode, fs_name, kind, g, scored[-1][0])
                _, g, m = max(scored, key=lambda s: s[0])
                grid_choice[f"{fs_name}/{kind}"] = g
                fitted[(fs_name, kind, "best")] = (enc, m)
            else:
                g = grid_choice[f"{fs_name}/{kind}"]
                m = make_model(kind, g, fs, seed).fit(Xtr, ytr)
            record(kind, cfg_name(kind, **g), m)

        if fs_name in ("dp", "full"):
            ytr_m, yva_m, yte_m = tr.type.to_numpy(), va.type.to_numpy(), te.type.to_numpy()
            cands = [(d, cw, DecisionTreeClassifier(max_depth=d, class_weight=cw, random_state=seed).fit(Xtr, ytr_m))
                     for d in DEPTHS for cw in CW]
            d, cw, m = max(cands, key=lambda c: multiclass_metrics(yva_m, c[2].predict(Xva), TYPES)["macro_f1"])
            records.append({**common, "model": "DT-multiclass", "config": f"depth={d},cw={cw}", "split": "test",
                            "multiclass": multiclass_metrics(yte_m, m.predict(Xte), TYPES)})
        log.info("[%s] seed %d fs %s done", mode, seed, fs_name)


def run_replay(keys, replay, fitted, seed, out: Path, max_chunks=None):
    cols = columns_needed(FEATURE_SETS["full_ids"])
    counts, leaves = {}, {}
    for i, (chunk, hour, gidx) in enumerate(iter_replay(PQ, keys, replay, cols)):
        if max_chunks is not None and i >= max_chunks:
            break
        if len(chunk) == 0:  # e.g. forward split: a file lying wholly in first halves of days
            continue
        typ = chunk.type.to_numpy()
        enc_cache = {}
        for (fs_name, kind, cfg), (enc, m) in fitted.items():
            if fs_name not in enc_cache:
                enc_cache[fs_name] = enc.transform(chunk)
            X = enc_cache[fs_name]
            pred = m.predict(X).astype(np.int8)
            if kind == "DT" and fs_name == "dp":
                leaf = m.apply(X)
                assert leaf.max() < np.iinfo(np.int16).max
                leaves.setdefault(cfg, []).append(leaf.astype(np.int16))
            g = pd.DataFrame({"hour": hour, "type": typ, "p": pred}).groupby(["hour", "type"], observed=True).p.agg(["size", "sum"])
            for (h, t), (n, s) in g.iterrows():
                key = (fs_name, kind, cfg, h, t)
                a = counts.get(key, (0, 0))
                counts[key] = (a[0] + int(n), a[1] + int(s))
        log.info("seed %d replay chunk %d done (%d rows)", seed, i + 1, len(chunk))
    (out / "leaves").mkdir(parents=True, exist_ok=True)
    for cfg, parts in leaves.items():
        np.save(out / "leaves" / f"seed{seed}_dp_DT_depth{cfg}.npy", np.concatenate(parts))
    np.save(out / f"replay_mask_seed{seed}.npy", replay)
    return pd.DataFrame([{"seed": seed, "fs": k[0], "model": k[1], "config": k[2], "hour": k[3], "type": k[4],
                          "n": v[0], "pred_attack": v[1]} for k, v in counts.items()])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["random", "grouped", "forward"], required=True)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--quick", action="store_true", help="smoke test: tiny grids, 1 replay chunk")
    args = ap.parse_args()
    global DEPTHS, GRIDS
    out = ROOT / "results/w2" / (args.split + ("_quick" if args.quick else ""))
    if args.quick:
        DEPTHS = [4, None]
        GRIDS = {k: v[:1] for k, v in GRIDS.items()}
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    keys = build_keys(PQ, KEYS)
    cols = columns_needed(FEATURE_SETS["full_ids"])
    records, grid_choice, replays = [], {}, []
    for seed in args.seeds:
        pools, replay = sample_pools(keys, args.split, seed)
        pools.groupby(["type", "pool"], observed=True).size().unstack().to_csv(out / f"pool_sizes_seed{seed}.csv")
        rows = load_rows(PQ, pools, cols)
        fitted = {}
        run_seed(seed, rows, args.split, grid_choice, records, fitted)
        pd.DataFrame(records).to_json(out / "iid_records.json", orient="records", indent=1)
        json.dump(grid_choice, open(out / "grid_choice.json", "w"), indent=1, default=str)
        replays.append(run_replay(keys, replay, fitted, seed, out, max_chunks=1 if args.quick else None))
        pd.concat(replays).to_parquet(out / "replay_counts.parquet", index=False)
    log.info("[%s] W2 finished in %.1f min", args.split, (time.time() - t0) / 60)


if __name__ == "__main__":
    main()
