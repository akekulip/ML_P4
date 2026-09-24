"""G6 targeted pilot (docs/preregistration.md, G6 addendum; exploratory): known-hash holders against D4/D5.

  g6_targeted.py --job DAY:VSET:ARM@GRID

VSET top or vul (the 20 largest benign long flows, or the 20 largest that never reach 2,048 packets). ARM:
  und1  the shipped one-table design, one holder per victim on the victim's slot (K1, as in G2b)
  d4k1  D4, one holder per victim; the attacker knows both hashes, so the holder's candidates are the victim's two slots
  d4k2  D4, two holders per victim with the victim's two slots as candidates (both hashes known)
  d5k2  D5 (secret second hash), two holders per victim: the attacker knows table A only, so the second candidate is a random table-B slot
Holders start 0.5 s before the victim's first packet (preempt). Analytical abstraction: no hash search, no probing model. Writes results/g2/g6t_<job>.npz.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g2_mawi import ART, GRID, OUT, WRAP_NS, CachedModels, load_day

from dgrade.defences import defence_kwargs
from dgrade.flowstats import FlowIndex
from dgrade.inject import merge_attack
from dgrade.inject_targeted import LEAD_NS, MS, _holders
from dgrade.netbeacon import load_tables
from dgrade.netbeacon_sim import NetBeaconSim, hash_unique

HALF = 32768


def run(job: str) -> None:
    left, _, g = job.partition("@")
    day, vset, arm = left.split(":")
    g = int(g)
    pk = load_day(day)
    z = np.load(OUT / f"prep_{day}.npz")
    t = np.load(OUT / f"targeted_prep_{day}.npz")
    kind = "top" if vset == "top" else "vulnerable"
    two = arm != "und1"
    fh = hash_unique(z["uniq"], "crc", None)[z["inv"]]
    h2seed = 7919 if arm.startswith("d4") else 900_000 + g
    if two:
        b_slot = (fh % HALF).astype(np.int64)
        b_slot2 = HALF + (hash_unique(z["uniq"], "polyirr", h2seed)[z["inv"]] % HALF).astype(np.int64)
    else:
        b_slot, b_slot2 = (fh & 0xFFFF).astype(np.int64), None
    idx = FlowIndex(t["code"])
    vf = t[f"{kind}_flow"]
    first = idx.order[idx.start[vf]]                         # position of each victim's first packet
    per = 2 if arm in ("d4k2", "d5k2") else 1
    rng = np.random.default_rng(7919 * g + (0 if vset == "top" else 1))
    start = np.repeat(t[f"{kind}_first"], per) - LEAD_NS + np.tile(np.arange(per) * 10 * MS, len(vf))
    slotA = np.repeat(b_slot[first], per)
    span = int(pk["ts_ns"].max()) + 1
    atk = _holders(start.astype(np.int64), slotA, span, rng, 250 * MS)
    if two:
        s2 = np.repeat(b_slot2[first], per) if arm != "d5k2" else HALF + rng.integers(0, HALF, len(slotA))
        atk.slot2 = s2[atk.flow]
    m = merge_attack(pk, b_slot, fh, atk, b_slot2)
    n_a = len(atk.pk)
    fs_b = np.where(z["long_flag"], 100, 0)
    pc_all = np.concatenate([z["pkt_code"].astype(np.int64), np.ones(n_a, dtype=np.int64)])[m.order]
    fs_all = np.concatenate([fs_b, np.full(n_a, 100)])[m.order]
    models = CachedModels(load_tables(ART), pc_all, fs_all, None)
    sim = NetBeaconSim(models=models, clock_offset_ns=g * (WRAP_NS // GRID), hash2_seed=h2seed, **defence_kwargs("d4" if two else ""))
    out = sim.run(m.pk, force_slot=m.slot, force_hash=m.hash, force_long=m.force_long, force_slot2=m.slot2)
    name = job.replace(":", "_").replace("@", "_at")
    tmp = OUT / f"g6t_{name}.tmp.npz"
    np.savez_compressed(tmp, benign_outcome=out["outcome"][~m.is_attacker], n_attacker_packets=n_a, victim_flow=vf, holders=len(np.unique(atk.flow)))
    tmp.replace(OUT / f"g6t_{name}.npz")
    print(job, "done; holders", len(np.unique(atk.flow)), "attacker packets", n_a)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    run(ap.parse_args().job)
