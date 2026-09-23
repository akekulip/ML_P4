"""Training / validation / IID-test pools and the chronological replay stream.

Pools mirror the class mix of TON_IoT Train_Test_Network (normal 300k, 20k per attack type) as a
stand-in until that file is available. Val/test pools use the same mix at 1/5 scale, and the
total pooled per type is capped at 50% of its eligible rows.

Split modes (methodology review 2026-09-22):
  random   rows sampled independently; exact-duplicate flows leak across pools (kept only to
           quantify that inflation)
  grouped  each distinct data-plane feature vector is eligible for exactly one pool, fixed by
           hash (60/20/20), so no test vector was seen in training and val groups never reach test
  forward  grouped, and pools draw only from the first half (by ts) of each local day; the
           replay covers only the second halves, so no within-day future is used for training
Every pooled row is removed from the replay. Days are Canberra local time (Australia/Sydney).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from mvm.features import DP_CAT, DP_NUM

__all__ = ["SPLIT_MODES", "TRAIN_MIX", "build_keys", "sample_pools", "load_rows", "iter_replay", "replay_order"]

SPLIT_MODES = ("random", "grouped", "forward")
TRAIN_MIX = {"normal": 300_000, "default": 20_000}
EVAL_SCALE = 5
TZ = "Australia/Sydney"
N_FILES = 23


def build_keys(parquet_dir: Path, out: Path) -> pd.DataFrame:
    """One row per flow in global file order: ids, label/type, ts, duration, local day/hour,
    first-half-of-day flag and a hash of the data-plane feature vector. Cached to `out`."""
    if out.exists():
        return pd.read_parquet(out)
    parts, offset = [], 0
    for f in range(1, N_FILES + 1):
        df = pd.read_parquet(parquet_dir / f"Network_dataset_{f}.parquet",
                             columns=["file_idx", "row_in_file", "ts", "label", "type", *DP_NUM, *DP_CAT])
        k = pd.DataFrame({
            "global_idx": np.arange(offset, offset + len(df), dtype=np.int64),
            "file_idx": df.file_idx.astype(np.int16), "row_in_file": df.row_in_file.astype(np.int32),
            "ts": df.ts, "duration": df.duration, "label": df.label, "type": df.type.astype("category"),
            "malformed": df.src_bytes.isna(),
            "vkey": pd.util.hash_pandas_object(df[DP_NUM + DP_CAT], index=False).to_numpy(),
        })
        parts.append(k)
        offset += len(df)
    keys = pd.concat(parts, ignore_index=True)
    local = pd.to_datetime(keys.ts, unit="s", utc=True).dt.tz_convert(TZ)
    keys["day"] = local.dt.strftime("%Y-%m-%d").astype("category")
    keys["hour"] = local.dt.strftime("%Y-%m-%d %H").astype("category")
    order = keys.sort_values(["ts", "global_idx"], kind="stable")
    rank = order.groupby("day", observed=True).cumcount()
    size = order.groupby("day", observed=True)["ts"].transform("size")
    keys["first_half"] = False
    keys.loc[order.index, "first_half"] = (rank < size / 2).to_numpy()
    keys["group_pool"] = pd.Categorical.from_codes(
        np.digitize(keys.vkey.to_numpy() % 1000, [600, 800]), ["train", "val", "test"])
    keys.to_parquet(out, index=False)
    return keys


def _quota(t: str, n_eligible: dict[str, int]) -> dict[str, int]:
    tr = TRAIN_MIX.get(t, TRAIN_MIX["default"])
    q = {"train": tr, "val": tr // EVAL_SCALE, "test": tr // EVAL_SCALE}
    total = sum(n_eligible.values())
    cap = total // 2
    if sum(q.values()) > cap:  # rare class: scale down to half of what is available
        scale = cap / sum(q.values())
        q = {p: int(v * scale) for p, v in q.items()}
    return {p: min(v, n_eligible.get(p, 0)) for p, v in q.items()}


def sample_pools(keys: pd.DataFrame, mode: str, seed: int) -> tuple[pd.DataFrame, np.ndarray]:
    """Return (pooled rows with a `pool` column, boolean replay mask over global_idx)."""
    assert mode in SPLIT_MODES
    rng = np.random.default_rng(seed)
    cand = keys[~keys.malformed]
    if mode == "forward":
        cand = cand[cand.first_half]
    parts = []
    for t, g in cand.groupby("type", observed=True):
        if mode == "random":
            elig = {"train": g, "val": g, "test": g}
            n_elig = {"train": len(g) * 3 // 5, "val": len(g) // 5, "test": len(g) // 5}
        else:
            elig = {p: g[g.group_pool == p] for p in ("train", "val", "test")}
            n_elig = {p: len(v) for p, v in elig.items()}
        q = _quota(t, n_elig)
        if mode == "random":
            idx = rng.permutation(len(g))[: sum(q.values())]
            labels = np.repeat(["train", "val", "test"], [q["train"], q["val"], q["test"]])
            parts.append(g.iloc[idx].assign(pool=labels))
        else:
            for p, rows in elig.items():
                pick = rng.choice(len(rows), size=q[p], replace=False)
                parts.append(rows.iloc[pick].assign(pool=p))
    pools = pd.concat(parts, ignore_index=True)
    replay = ~keys.malformed.to_numpy()
    replay[pools.global_idx.to_numpy()] = False
    if mode == "forward":
        replay &= ~keys.first_half.to_numpy()
    return pools, replay


def load_rows(parquet_dir: Path, pools: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Load the pooled rows (all requested columns) by key, file by file."""
    out = []
    for f, sel in pools.groupby("file_idx"):
        df = pd.read_parquet(parquet_dir / f"Network_dataset_{int(f)}.parquet", columns=columns)
        out.append(df.merge(sel[["row_in_file", "pool"]], on="row_in_file"))
    return pd.concat(out, ignore_index=True)


def iter_replay(parquet_dir: Path, keys: pd.DataFrame, replay: np.ndarray, columns: list[str]):
    """Yield (chunk, local_hour, global_idx) per source file for replay rows, in time order
    (stable sort by ts; within-second order is file order)."""
    for f in range(1, N_FILES + 1):
        kf = keys[keys.file_idx == f]
        m = replay[kf.global_idx.to_numpy()]
        df = pd.read_parquet(parquet_dir / f"Network_dataset_{f}.parquet", columns=columns)[m]
        kf = kf[m]
        order = np.argsort(df.ts.to_numpy(), kind="stable")
        yield df.iloc[order], kf.hour.to_numpy()[order], kf.global_idx.to_numpy()[order]


def replay_order(keys: pd.DataFrame, replay: np.ndarray) -> np.ndarray:
    """global_idx of replay rows in exactly the order iter_replay yields them
    (file by file, stable-sorted by ts within each file)."""
    sel = keys[replay[keys.global_idx.to_numpy()]]
    order = np.lexsort((sel.ts.to_numpy(), sel.file_idx.to_numpy()))  # lexsort is stable
    return sel.global_idx.to_numpy()[order]
