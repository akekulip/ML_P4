"""W4 / RQ4: adaptation after attack-phase changes, measured in flows (not hours).

Hourly bins hide adaptation (an hour holds ~10^4-10^5 flows and caches re-adapt within it), so
this re-simulates K=8, depth 10, grouped split, seeds 0-2, and measures at every local-day boundary:
  excess_misses_10k (primary) misses in the first 10,000 flows of the phase minus the policy's
                    steady-state miss rate x 10,000; steady = the rest of that day
  flows_to_recover  flows until a 500-flow bin's miss rate is at most max(1.5 x steady miss rate,
                    steady miss rate + 0.002) (a relative test: an absolute 5-point margin passed
                    bins with 3x the steady miss rate; code review 2026-09-22)
Only true phase boundaries count: days whose set of attack types (>= 1% of the day's flows in the
full stream) differs from the previous day's. The first day of the stream is a cold start and is skipped.
Static placement is excluded: it never adapts, so recovery is undefined for it.
Output: results/w4/recovery.parquet and docs/results_w4_recovery.md (a separate doc, so rerunning
w4_report.py cannot overwrite it).
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from mvm.cache import simulate_fast
from mvm.splits import replay_order

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("w4r")
ROOT = Path(__file__).resolve().parents[1]
W2, OUT = ROOT / "results/w2", ROOT / "results/w4"
K, DEPTH, BIN, HORIZON = 8, "10", 500, 10_000
POLICIES = {"belady": ("belady", {}), "dlfu_0.99": ("dlfu", {"gamma": 0.99}), "lru": ("lru", {}), "lfu": ("lfu", {})}


def phase_days(day_codes: np.ndarray, typ_codes: np.ndarray) -> set[int]:
    """Day codes that start a new attack phase: attack-type set (>= 1% of the day) differs from the previous day's."""
    days = np.unique(day_codes)
    sets = {}
    for d in days:
        t = typ_codes[day_codes == d]
        ids, cnt = np.unique(t, return_counts=True)
        sets[d] = frozenset(ids[cnt >= 0.01 * len(t)].tolist())
    return {d for prev, d in zip(days[:-1], days[1:]) if sets[d] != sets[prev]}


def recovery_rows(hits: np.ndarray, day: np.ndarray, boundaries: set[int], **tag) -> list[dict]:
    rows = []
    starts = np.flatnonzero(np.r_[True, day[1:] != day[:-1]])
    ends = np.r_[starts[1:], len(day)]
    for a, b in zip(starts, ends):
        if a == 0 or day[a] not in boundaries or b - a < 2 * HORIZON:
            continue  # cold start, not a phase change, or too few flows to separate transient from steady
        steady = hits[a + HORIZON:b].mean()
        steady_miss = 1 - steady
        n_bins = (b - a) // BIN
        miss = 1 - hits[a:a + n_bins * BIN].reshape(n_bins, BIN).mean(axis=1)
        ok = np.flatnonzero(miss <= max(1.5 * steady_miss, steady_miss + 0.002))
        rates = 1 - miss
        first = hits[a:a + HORIZON]
        rows.append({**tag, "day_start": int(a), "flows_in_day": int(b - a), "steady_hit_rate": float(steady),
                     "first_bin_hit_rate": float(rates[0]),
                     "flows_to_recover": int(ok[0] * BIN) if len(ok) else np.nan,
                     "excess_misses_10k": float((~first).sum() - (1 - steady) * HORIZON)})
    return rows


def main():
    keys = pd.read_parquet(ROOT / "data/processed/keys.parquet", columns=["global_idx", "file_idx", "ts", "label", "day", "type"])
    keys["day"] = keys["day"].astype("category")
    keys["type"] = keys["type"].astype("category")
    rows = []
    for seed in (0, 1, 2):
        mask = np.load(W2 / "grouped" / f"replay_mask_seed{seed}.npy")
        meta = keys.iloc[replay_order(keys, mask)]
        day_all, label = meta.day.cat.codes.to_numpy(), meta.label.to_numpy()
        day_names = list(meta.day.cat.categories)
        typ_all = meta.type.cat.codes.to_numpy()
        boundaries = phase_days(day_all, np.where(label == 1, typ_all, -1))  # attack types only
        leaf_all = np.load(W2 / "grouped" / "leaves" / f"seed{seed}_dp_DT_depth{DEPTH}.npy")
        for stream, m in (("full", slice(None)), ("benign", label == 0)):
            leaf, day = leaf_all[m], day_all[m]
            for pol, (kind, kw) in POLICIES.items():
                hits = simulate_fast(kind, leaf, K, **kw).hits
                for r in recovery_rows(hits, day, boundaries, seed=seed, stream=stream, policy=pol):
                    r["day"] = day_names[day[r["day_start"]]]
                    rows.append(r)
        log.info("seed %d done", seed)
    rec = pd.DataFrame(rows)
    assert len(rec) and rec.steady_hit_rate.between(0, 1).all()
    rec.to_parquet(OUT / "recovery.parquet", index=False)

    lines = ["# W4 / RQ4: adaptation after attack-phase changes (measured in flows)", "",
             f"Grouped split, depth {DEPTH}, K={K}, seeds 0-2 (mean). Only days that start a new attack phase "
             "(the set of attack types with >= 1% of the day's flows differs from the previous day) are counted; "
             "the stream's first day is a cold start and is skipped. Excess misses (primary) = misses in the first "
             "10,000 flows of the phase beyond the policy's steady-state rate for the rest of that day. "
             f"Flows to recover = flows until a {BIN}-flow bin's miss rate is at most max(1.5 x steady, steady + 0.002). "
             "Static placement is excluded (it never adapts).", ""]
    for stream in ("full", "benign"):
        t = rec[rec.stream == stream]
        if t.empty:
            continue
        e = t.groupby(["day", "policy"]).excess_misses_10k.mean().unstack("policy")
        f = t.groupby(["day", "policy"]).flows_to_recover.mean().unstack("policy")
        st = t.groupby(["day", "policy"]).steady_hit_rate.mean().unstack("policy")
        cols = [p for p in POLICIES if p in f.columns]
        lines += [f"## {stream} stream: excess misses in the first 10,000 flows of each phase", "", e[cols].round(0).to_markdown(), "",
                  f"## {stream} stream: flows to recover", "", f[cols].round(0).to_markdown(), "",
                  f"## {stream} stream: steady hit rate for the rest of the day", "", st[cols].round(3).to_markdown(), ""]
    (ROOT / "docs/results_w4_recovery.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
