"""W3 / RQ2-RQ3: leaf-level locality of the data-plane DTs under chronological replay.

Inputs: W2 leaf streams (results/w2/{mode}/leaves/seed{s}_dp_DT_depth{d}.npy) and replay masks.
For every (split mode, seed, depth) and flow ordering it measures, on several streams:
  frequency metrics (order-free): leaves visited, C(K), W90/W95/W99, normalized leaf entropy
  order metrics: reuse-distance quantiles and LRU hit rate for every K (hit iff 0 <= rd < K)
Orderings (methodology review M4): file order as replayed; a within-second shuffle; flow-end
time (ts + duration, when the switch could first classify a completed flow).
Streams: full, benign-only, one per local day (attack phase), one per attack type.
Also writes hourly Jensen-Shannon drift of the leaf distribution (file order, seed 0).

One (mode, seed) unit runs per process, driven by experiments/overnight.sh. No multiprocessing
Pool: on 2026-09-22 a forked Pool deadlocked and OOM-killed workers left a spawned Pool hung.

Usage:
  w3_locality.py --job MODE SEED          one unit -> results/w3/parts/{mode}_seed{seed}.parquet
  w3_locality.py --quick                  smoke test on 2M rows, one depth, into a temp dir
  w3_locality.py --merge                  combine the 10 parts (fails if any is missing)
"""

from __future__ import annotations

import argparse
import logging
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from mvm.locality import coverage, normalized_entropy, reuse_distance, working_set
from mvm.splits import build_keys, iter_replay, replay_order

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("w3")
ROOT = Path(__file__).resolve().parents[1]
W2 = ROOT / "results/w2"
OUT = ROOT / "results/w3"
KS = [1, 2, 4, 8, 16, 32, 64]
DEPTHS = ["4", "6", "8", "10", "12", "16", "None"]
MODES = ["grouped", "forward"]
SEEDS = [0, 1, 2, 3, 4]
KEY_COLS = ["global_idx", "file_idx", "ts", "duration", "label", "type", "day", "hour"]


def load_keys() -> pd.DataFrame:
    """Only the columns W3 needs (the full key table is ~5 GB per process)."""
    build_keys(ROOT / "data/processed/network", ROOT / "data/processed/keys.parquet")  # no-op if cached
    keys = pd.read_parquet(ROOT / "data/processed/keys.parquet", columns=KEY_COLS)
    for c in ("type", "day", "hour"):  # parquet round-trips these as strings; codes are what we use
        keys[c] = keys[c].astype("category")
    assert np.array_equal(keys.global_idx.to_numpy(), np.arange(len(keys))), "row position != global_idx"
    return keys


def n_leaves_table() -> pd.DataFrame:
    rows = []
    for mode in MODES:
        rec = pd.read_json(W2 / mode / "iid_records.json", dtype={"depth": str})
        t = rec[(rec.fs == "dp") & (rec.model == "DT") & (rec.split == "test")]
        rows.append(t[["seed", "depth", "n_leaves"]].assign(mode=mode))
    return pd.concat(rows, ignore_index=True)


def stream_metrics(leaf: np.ndarray, n_leaves: int, order_free: bool) -> dict:
    out = {"n": len(leaf)}
    if len(leaf) == 0:
        return out
    if order_free:
        out.update(leaves_visited=int(len(np.unique(leaf))), H_norm=normalized_entropy(leaf, n_leaves),
                   W90=working_set(leaf, .9), W95=working_set(leaf, .95), W99=working_set(leaf, .99),
                   **{f"C{k}": coverage(leaf, k) for k in KS})
    rd = reuse_distance(leaf)
    hit = rd >= 0
    out.update(cold_frac=float((~hit).mean()),
               rd_median=float(np.median(rd[hit])) if hit.any() else np.nan,
               rd_p90=float(np.percentile(rd[hit], 90)) if hit.any() else np.nan,
               **{f"lru_K{k}": float(((rd >= 0) & (rd < k)).mean()) for k in KS})
    return out


def check_part(rows: pd.DataFrame) -> None:
    """Sanity invariants; raise on violation so the driver marks the unit failed."""
    assert len(rows) > 0, "empty part"
    lru = rows.filter(like="lru_K")
    assert ((lru >= 0) & (lru <= 1)).all().all(), "LRU hit rate outside [0, 1]"
    assert (lru.diff(axis=1).iloc[:, 1:] >= -1e-12).all().all(), "LRU hit rate not monotone in K"
    fo = rows[rows.ordering == "file"].dropna(subset=["C1"])
    cov = fo[[f"C{k}" for k in KS]]
    assert ((cov >= 0) & (cov <= 1 + 1e-9)).all().all(), "C(K) outside [0, 1]"
    assert (cov.diff(axis=1).iloc[:, 1:] >= -1e-12).all().all(), "C(K) not monotone in K"
    assert (fo.W90 <= fo.leaves_visited).all() and (fo.W90 <= fo.W99).all(), "W90 inconsistent"
    assert (fo.leaves_visited <= fo.n_leaves).all(), "more leaves visited than the tree has"
    assert ((fo.H_norm >= -1e-9) & (fo.H_norm <= 1 + 1e-9)).all(), "entropy outside [0, 1]"


def run_unit(keys: pd.DataFrame, mode: str, seed: int, depths=DEPTHS, max_rows=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    mask = np.load(W2 / mode / f"replay_mask_seed{seed}.npy")
    gidx = replay_order(keys, mask)
    meta = keys.iloc[gidx]
    # integer category codes, never Python strings: 22M-row str arrays cost ~1.5 GB each and put
    # workers into the OOM killer on 2026-09-22
    label = meta.label.to_numpy()
    typ, typ_names = meta.type.cat.codes.to_numpy(), list(meta.type.cat.categories)
    day, day_names = meta.day.cat.codes.to_numpy(), list(meta.day.cat.categories)
    hour, hour_names = meta.hour.cat.codes.to_numpy(), np.asarray(meta.hour.cat.categories)
    ts = meta.ts.to_numpy()
    end = ts + meta.duration.fillna(0).to_numpy()
    n = len(gidx) if max_rows is None else min(max_rows, len(gidx))
    label, typ, day, hour, ts, end = (a[:n] for a in (label, typ, day, hour, ts, end))
    rng = np.random.default_rng(1000 + seed)
    orderings = {
        "file": np.arange(n),
        "shuffle_within_second": np.lexsort((rng.random(n), ts)),
        "flow_end": np.argsort(end, kind="stable"),
    }
    nl = n_leaves_table()
    rows, drift = [], []
    for depth in depths:
        leaf_all = np.load(W2 / mode / "leaves" / f"seed{seed}_dp_DT_depth{depth}.npy")
        assert len(leaf_all) == len(gidx), (mode, seed, depth, len(leaf_all), len(gidx))
        leaf_all = leaf_all[:n]
        n_leaves = int(nl[(nl["mode"] == mode) & (nl.seed == seed) & (nl.depth == depth)].n_leaves.iloc[0])
        for oname, perm in orderings.items():
            leaf, lab, dy, ty = leaf_all[perm], label[perm], day[perm], typ[perm]
            streams = {"full": slice(None), "benign": lab == 0}
            streams |= {f"day:{day_names[d]}": dy == d for d in np.unique(dy)}
            if oname == "file":  # per-type streams: frequency metrics only need one ordering
                streams |= {f"type:{typ_names[t]}": ty == t for t in np.unique(ty)}
            for sname, m in streams.items():
                rows.append({"mode": mode, "seed": seed, "depth": depth, "n_leaves": n_leaves,
                             "ordering": oname, "stream": sname,
                             **stream_metrics(leaf[m], n_leaves, order_free=(oname == "file"))})
            del leaf, lab, dy, ty
        if seed == 0:  # hourly leaf-distribution drift, file order
            h_codes, h_inv = np.unique(hour, return_inverse=True)
            l_ids, l_inv = np.unique(leaf_all, return_inverse=True)
            counts = np.zeros((len(h_codes), len(l_ids)))
            np.add.at(counts, (h_inv, l_inv), 1)
            p = counts / counts.sum(axis=1, keepdims=True)
            att = np.bincount(h_inv, weights=label, minlength=len(h_codes)) / counts.sum(axis=1)
            for i in range(1, len(h_codes)):
                a, b = p[i - 1], p[i]
                mid = (a + b) / 2
                js = 0.5 * np.sum(a[a > 0] * np.log2(a[a > 0] / mid[a > 0])) + 0.5 * np.sum(b[b > 0] * np.log2(b[b > 0] / mid[b > 0]))
                drift.append({"mode": mode, "depth": depth, "hour": str(hour_names[h_codes[i]]), "js_prev": float(js),
                              "n": int(counts[i].sum()), "top8_share": float(np.sort(counts[i])[::-1][:8].sum() / counts[i].sum()),
                              "attack_frac": float(att[i])})
        log.info("%s seed %d depth %s done", mode, seed, depth)
    return pd.DataFrame(rows), pd.DataFrame(drift)


def verify_alignment(keys: pd.DataFrame) -> None:
    """replay_order must reproduce iter_replay's order exactly, over every file (seed 0, each mode)."""
    for mode in MODES:
        mask = np.load(W2 / mode / "replay_mask_seed0.npy")
        parts = [g for _, _, g in iter_replay(ROOT / "data/processed/network", keys, mask, ["ts", "src_bytes", "row_in_file"])]
        assert np.array_equal(replay_order(keys, mask), np.concatenate(parts)), mode


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
        loc = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
        check_part(loc)
        loc.to_parquet(OUT / "locality.parquet", index=False)
        drifts = [pd.read_parquet(p.with_suffix(".drift.parquet")) for p in parts]
        pd.concat([d for d in drifts if len(d)], ignore_index=True).to_parquet(OUT / "drift_hourly.parquet", index=False)
        log.info("merged %d parts, %d rows", len(parts), len(loc))
        return

    keys = load_keys()
    if args.quick:
        verify_alignment(keys)
        rows, drift = run_unit(keys, "grouped", 0, depths=["10"], max_rows=2_000_000)
        check_part(rows)
        assert len(drift) > 0 and drift.js_prev.between(0, 1 + 1e-9).all(), "drift invalid"
        with tempfile.TemporaryDirectory() as d:
            rows.to_parquet(Path(d) / "q.parquet")
            assert len(pd.read_parquet(Path(d) / "q.parquet")) == len(rows)
        log.info("QUICK OK: %d rows, %d drift rows", len(rows), len(drift))
        return

    mode, seed = args.job[0], int(args.job[1])
    part = OUT / "parts" / f"{mode}_seed{seed}.parquet"
    if part.exists():
        log.info("%s exists, skipping", part.name)
        return
    rows, drift = run_unit(keys, mode, seed)
    check_part(rows)
    part.parent.mkdir(parents=True, exist_ok=True)
    drift.to_parquet(part.with_suffix(".drift.parquet"), index=False)
    rows.to_parquet(part.with_suffix(".tmp"), index=False)
    part.with_suffix(".tmp").rename(part)  # atomic: a part file exists only when complete
    log.info("UNIT OK %s seed %d", mode, seed)


if __name__ == "__main__":
    main()
