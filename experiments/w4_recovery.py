"""W4 / RQ4: adaptation after attack-phase changes, measured in flows (not hours).

Hourly bins hide adaptation (an hour holds ~10^4-10^5 flows and caches re-adapt within it), so
this re-simulates K=8, depth 10, grouped split, seeds 0-2, and measures at every local-day boundary:
  flows_to_recover  flows until a 500-flow bin's hit rate reaches (steady - 0.05), where steady is
                    the policy's hit rate over the rest of that day
  excess_misses_10k misses in the first 10,000 flows of the day minus the steady-state miss count
Static placement is excluded: it never adapts, so recovery is undefined for it.
Output: results/w4/recovery.parquet; docs/results_w4.md gets a regenerated recovery section.
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


def recovery_rows(hits: np.ndarray, day: np.ndarray, **tag) -> list[dict]:
    rows = []
    starts = np.flatnonzero(np.r_[True, day[1:] != day[:-1]])
    ends = np.r_[starts[1:], len(day)]
    for a, b in zip(starts, ends):
        if b - a < 2 * HORIZON:
            continue  # too few flows that day to separate transient from steady state
        steady = hits[a + HORIZON:b].mean()
        n_bins = (b - a) // BIN
        rates = hits[a:a + n_bins * BIN].reshape(n_bins, BIN).mean(axis=1)
        ok = np.flatnonzero(rates >= steady - 0.05)
        first = hits[a:a + HORIZON]
        rows.append({**tag, "day_start": int(a), "flows_in_day": int(b - a), "steady_hit_rate": float(steady),
                     "first_bin_hit_rate": float(rates[0]),
                     "flows_to_recover": int(ok[0] * BIN) if len(ok) else np.nan,
                     "excess_misses_10k": float((~first).sum() - (1 - steady) * HORIZON)})
    return rows


def main():
    keys = pd.read_parquet(ROOT / "data/processed/keys.parquet", columns=["global_idx", "file_idx", "ts", "label", "day"])
    keys["day"] = keys["day"].astype("category")
    rows = []
    for seed in (0, 1, 2):
        mask = np.load(W2 / "grouped" / f"replay_mask_seed{seed}.npy")
        meta = keys.iloc[replay_order(keys, mask)]
        day_all, label = meta.day.cat.codes.to_numpy(), meta.label.to_numpy()
        day_names = list(meta.day.cat.categories)
        leaf_all = np.load(W2 / "grouped" / "leaves" / f"seed{seed}_dp_DT_depth{DEPTH}.npy")
        for stream, m in (("full", slice(None)), ("benign", label == 0)):
            leaf, day = leaf_all[m], day_all[m]
            for pol, (kind, kw) in POLICIES.items():
                hits = simulate_fast(kind, leaf, K, **kw).hits
                for r in recovery_rows(hits, day, seed=seed, stream=stream, policy=pol):
                    r["day"] = day_names[day[r["day_start"]]]
                    rows.append(r)
        log.info("seed %d done", seed)
    rec = pd.DataFrame(rows)
    assert len(rec) and rec.steady_hit_rate.between(0, 1).all()
    rec.to_parquet(OUT / "recovery.parquet", index=False)

    lines = ["", "## Adaptation after each local-day (attack-phase) boundary, measured in flows", "",
             f"Grouped split, depth {DEPTH}, K={K}, seeds 0-2 (mean). flows_to_recover = flows until a {BIN}-flow bin "
             "reaches the day's steady hit rate minus 0.05; excess misses = misses in the first 10,000 flows beyond "
             "the steady-state rate. Days with fewer than 20,000 flows in the stream are skipped. Static placement is "
             "excluded (it never adapts).", ""]
    for stream in ("full", "benign"):
        t = rec[rec.stream == stream]
        if t.empty:
            continue
        f = t.groupby(["day", "policy"]).flows_to_recover.mean().unstack("policy")
        e = t.groupby(["day", "policy"]).excess_misses_10k.mean().unstack("policy")
        cols = [p for p in POLICIES if p in f.columns]
        lines += [f"### {stream} stream: flows to recover", "", f[cols].round(0).to_markdown(), "",
                  f"### {stream} stream: excess misses in the first 10,000 flows", "", e[cols].round(0).to_markdown(), ""]
    doc = ROOT / "docs/results_w4.md"
    text = doc.read_text()
    marker = "## Recovery after each local-day boundary"
    if marker in text:  # replace the hour-granularity section, which cannot resolve adaptation
        text = text[: text.index(marker)].rstrip() + "\n"
    doc.write_text(text + "\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
