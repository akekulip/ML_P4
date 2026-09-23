"""G2b targeted-displacement arms (docs/preregistration.md, G2b targeted-arm entry).

  g2b_targeted.py --prep DAY
  g2b_targeted.py --job DAY:VSET:ARM[:H]@GRID

VSET top (the 20 largest benign long flows) or vul (the 20 largest that never reach 2048 packets). ARM preempt or
reactive (K1: one holder per victim, given the victim's slot, benign hash unkeyed), b0l:H (H random-slot holders,
benign hash unkeyed, the decision baseline) or k0:H (H random-slot holders, benign hash keyed with an
irreducible polynomial drawn with GRID). GRID is the clock start (GRID/30 of the wrap period) and the draw number.
Analytical abstraction only (see ``dgrade.inject_targeted``). Writes results/g2/t_<job>.npz.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g2_mawi import ART, GRID, OUT, WRAP_NS, CachedModels, load_day

from dgrade.flowstats import FlowIndex
from dgrade.inject import merge_attack
from dgrade.inject_targeted import (
    build_targeted,
    random_holders,
    select_victims,
)
from dgrade.netbeacon import load_tables
from dgrade.netbeacon_sim import NetBeaconSim, flow_ids, hash_unique


def prep(day: str) -> None:
    """Once per day: per-packet flow numbers and the two victim sets (slots from the unkeyed hash)."""
    pk = load_day(day)
    z = np.load(OUT / f"prep_{day}.npz")
    code = FlowIndex(flow_ids(pk, 1 << 62)).code.astype(np.int32)
    idx = FlowIndex(code)
    fh = hash_unique(z["uniq"], "crc", None)[z["inv"]]
    flow_slot = (fh & 0xFFFF).astype(np.int64)[idx.order[idx.start]]
    out = {"code": code}
    for kind in ("top", "vulnerable"):
        v = select_victims(pk, idx, flow_slot, kind)
        out[f"{kind}_flow"] = np.array([x.flow for x in v])
        out[f"{kind}_slot"] = np.array([x.slot for x in v])
        out[f"{kind}_n"] = np.array([x.n_packets for x in v])
        out[f"{kind}_first"] = np.array([x.first_ts for x in v])
        out[f"{kind}_gap"] = np.array([-1 if x.gap_start_ts is None else x.gap_start_ts for x in v])
    np.savez(OUT / f"targeted_prep_{day}.npz", **out)
    print("prepared", day, {k: len(v) for k, v in out.items() if k.endswith("_flow")})


def run(job: str) -> None:
    from dgrade.inject_targeted import Victim
    left, _, g = job.partition("@")
    day, vset, arm, *h = left.split(":")
    g = int(g)
    pk = load_day(day)
    z = np.load(OUT / f"prep_{day}.npz")
    t = np.load(OUT / f"targeted_prep_{day}.npz")
    kind_name = "top" if vset == "top" else "vulnerable"
    victims = [Victim(int(f), int(s), int(n), int(a), None if b < 0 else int(b))
               for f, s, n, a, b in zip(t[f"{kind_name}_flow"], t[f"{kind_name}_slot"], t[f"{kind_name}_n"],
                                        t[f"{kind_name}_first"], t[f"{kind_name}_gap"], strict=True)]
    keyed = arm == "k0"
    fh = hash_unique(z["uniq"], "polyirr" if keyed else "crc", g if keyed else None)[z["inv"]]
    b_slot = (fh & 0xFFFF).astype(np.int64)
    span = int(pk["ts_ns"].max()) + 1
    rng = np.random.default_rng(7919 * g + (0 if vset == "top" else 1))
    failed = 0
    if arm in ("preempt", "reactive"):
        atk = build_targeted(victims, arm, span, rng)
        failed = len(atk.failed)
    elif arm in ("b0l", "k0"):
        atk = random_holders(int(h[0]), span, rng)
    else:
        raise ValueError(f"unknown arm {arm!r}")
    m = merge_attack(pk, b_slot, fh, atk)
    n_a = len(atk.pk)
    long_flag = z["long_flag"]
    fs_b = np.where(long_flag, 100, 0)
    pc_all = np.concatenate([z["pkt_code"].astype(np.int64), np.ones(n_a, dtype=np.int64)])[m.order]
    fs_all = np.concatenate([fs_b, np.full(n_a, 100)])[m.order]
    models = CachedModels(load_tables(ART), pc_all, fs_all, None)
    out = NetBeaconSim(models=models, clock_offset_ns=g * (WRAP_NS // GRID)).run(
        m.pk, force_slot=m.slot, force_hash=m.hash, force_long=m.force_long)
    name = job.replace(":", "_").replace("@", "_at")
    np.savez_compressed(OUT / f"t_{name}.npz", benign_outcome=out["outcome"][~m.is_attacker], n_attacker_packets=n_a,
                        n_holders=len(np.unique(atk.flow)), failed=failed, victim_flow=np.array([v.flow for v in victims]))
    print(job, "done; holders", len(np.unique(atk.flow)), "attacker packets", n_a, "failed", failed)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--job")
    ap.add_argument("--prep")
    a = ap.parse_args()
    prep(a.prep) if a.prep else run(a.job)
