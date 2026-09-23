"""W4 / RQ4: leaf-cache policies for a K-entry switch table, replayed over the W2 leaf streams.

For each (split mode, seed) unit, data-plane DTs of depth 6, 10 and unlimited, streams full and
benign-only (file order), K in {1..64}, and policies:
  lru, lfu, dlfu_0.99, dlfu_0.999   online demand policies, cold start
  static_warm                        top-K leaves of the stream's first local hour, never changed
  window_oracle_hour                 each hour's true top-K preloaded (not deployable)
  belady                             offline optimum (MIN with bypass); upper bound for demand policies
Outputs per unit: summary rows (hit rate, inserts, evictions, churn) and hourly hit counts, from
which the report derives regret vs Belady (recovery after phase changes: experiments/w4_recovery.py).

Usage: w4_cache.py --job MODE SEED | --quick | --merge   (driven by experiments/overnight.sh)
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from mvm.cache import simulate_fast
from mvm.splits import replay_order

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("w4")
ROOT = Path(__file__).resolve().parents[1]
W2, OUT = ROOT / "results/w2", ROOT / "results/w4"
KS = [1, 2, 4, 8, 16, 32, 64]
DEPTHS = ["6", "10", "None"]
MODES, SEEDS = ["grouped", "forward"], [0, 1, 2, 3, 4]
DEMAND = {"lru": {}, "lfu": {}, "dlfu_0.99": {"gamma": 0.99}, "dlfu_0.999": {"gamma": 0.999}}


def load_keys() -> pd.DataFrame:
    keys = pd.read_parquet(ROOT / "data/processed/keys.parquet", columns=["global_idx", "file_idx", "ts", "label", "hour"])
    keys["hour"] = keys["hour"].astype("category")
    return keys


def static_warm(leaf, hour, k):
    """Top-K leaves of the first hour, fixed for the whole stream (inserted once)."""
    in_warm = hour == hour[0]
    ids, cnt = np.unique(leaf[in_warm], return_counts=True)
    top = ids[np.lexsort((ids, -cnt))[:k]]
    hits = np.isin(leaf, top) & ~in_warm  # the table is installed only after the warm-up hour
    return hits, len(top), 0


def window_oracle(leaf, hour, k):
    """Each hour's true top-K preloaded at the start of the hour."""
    hits = np.zeros(len(leaf), bool)
    prev, ins, ev = set(), 0, 0
    bounds = np.flatnonzero(np.r_[True, hour[1:] != hour[:-1], True])
    for a, b in zip(bounds[:-1], bounds[1:]):
        ids, cnt = np.unique(leaf[a:b], return_counts=True)
        top = ids[np.lexsort((ids, -cnt))[:k]]
        hits[a:b] = np.isin(leaf[a:b], top)
        cur = set(top.tolist())
        ins, ev, prev = ins + len(cur - prev), ev + len(prev - cur), cur
    return hits, ins, ev


def run_policies(leaf, hour):
    """Yield (policy, K, hits, inserts, evictions) for every policy and K."""
    for k in KS:
        for name, kw in DEMAND.items():
            r = simulate_fast(name.split("_")[0], leaf, k, **kw)
            yield name, k, r.hits, r.inserts, r.evictions
        yield ("static_warm", k, *static_warm(leaf, hour, k))
        yield ("window_oracle_hour", k, *window_oracle(leaf, hour, k))
        r = simulate_fast("belady", leaf, k)
        yield "belady", k, r.hits, r.inserts, r.evictions


def check_summary(s: pd.DataFrame) -> None:
    assert len(s) > 0, "empty summary"
    assert s.hit_rate.between(0, 1).all(), "hit rate outside [0, 1]"
    idx = ["mode", "seed", "depth", "stream", "K"]
    p = s.pivot_table(index=idx, columns="policy", values="hits")
    for pol in DEMAND:
        assert (p["belady"] >= p[pol]).all(), f"Belady below {pol}"
    for pol in ("lru", "belady"):  # both have the inclusion property: monotone in K
        m = s[s.policy == pol].sort_values("K").groupby(["mode", "seed", "depth", "stream"]).hit_rate
        assert (m.diff().dropna() >= -1e-12).all(), f"{pol} not monotone in K"


def run_unit(keys, mode, seed, depths=DEPTHS, max_rows=None):
    mask = np.load(W2 / mode / f"replay_mask_seed{seed}.npy")
    meta = keys.iloc[replay_order(keys, mask)]
    label = meta.label.to_numpy()
    hour, hour_names = meta.hour.cat.codes.to_numpy(), np.asarray(meta.hour.cat.categories)
    n = len(meta) if max_rows is None else min(max_rows, len(meta))
    label, hour = label[:n], hour[:n]
    summary, hourly = [], []
    for depth in depths:
        leaf_all = np.load(W2 / mode / "leaves" / f"seed{seed}_dp_DT_depth{depth}.npy")
        assert len(leaf_all) == len(meta)
        leaf_all = leaf_all[:n]
        for sname, m in (("full", slice(None)), ("benign", label == 0)):
            leaf, hr = leaf_all[m], hour[m]
            h_codes, h_inv = np.unique(hr, return_inverse=True)
            n_h = np.bincount(h_inv)
            for pol, k, hits, ins, ev in run_policies(leaf, hr):
                summary.append({"mode": mode, "seed": seed, "depth": depth, "stream": sname, "policy": pol, "K": k,
                                "n": len(leaf), "hits": int(hits.sum()), "hit_rate": float(hits.mean()),
                                "inserts": int(ins), "evictions": int(ev), "churn": (ins + ev) / len(leaf)})
                if seed in (0, 1, 2):  # hourly series for recovery analysis (3 seeds keep files small)
                    hh = np.bincount(h_inv, weights=hits, minlength=len(h_codes))
                    hourly.append(pd.DataFrame({"mode": mode, "seed": seed, "depth": depth, "stream": sname,
                                                "policy": pol, "K": k, "hour": hour_names[h_codes],
                                                "n": n_h, "hits": hh.astype(np.int64)}))
        log.info("%s seed %d depth %s done", mode, seed, depth)
    return pd.DataFrame(summary), (pd.concat(hourly, ignore_index=True) if hourly else pd.DataFrame())


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--job", nargs=2, metavar=("MODE", "SEED"))
    g.add_argument("--quick", action="store_true")
    g.add_argument("--merge", action="store_true")
    args = ap.parse_args()
    if args.merge:
        parts = [OUT / "parts" / f"{m}_seed{s}.parquet" for m in MODES for s in SEEDS]
        missing = [p.name for p in parts if not p.exists()]
        assert not missing, f"missing parts: {missing}"
        s = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
        check_summary(s)
        s.to_parquet(OUT / "summary.parquet", index=False)
        hourly = [p.with_suffix(".hourly.parquet") for p in parts]
        pd.concat([pd.read_parquet(h) for h in hourly if h.exists()], ignore_index=True).to_parquet(OUT / "hourly.parquet", index=False)
        log.info("merged %d parts", len(parts))
        return
    keys = load_keys()
    if args.quick:
        s, h = run_unit(keys, "grouped", 0, depths=["10"], max_rows=1_000_000)
        check_summary(s)
        assert len(h) > 0 and (h.hits <= h.n).all(), "hourly invalid"
        log.info("QUICK OK: %d summary rows, %d hourly rows", len(s), len(h))
        return
    mode, seed = args.job[0], int(args.job[1])
    part = OUT / "parts" / f"{mode}_seed{seed}.parquet"
    if part.exists():
        log.info("%s exists, skipping", part.name)
        return
    s, h = run_unit(keys, mode, seed)
    check_summary(s)
    part.parent.mkdir(parents=True, exist_ok=True)
    if len(h):
        h.to_parquet(part.with_suffix(".hourly.parquet"), index=False)
    s.to_parquet(part.with_suffix(".tmp"), index=False)
    part.with_suffix(".tmp").rename(part)
    log.info("UNIT OK %s seed %d", mode, seed)


if __name__ == "__main__":
    main()
