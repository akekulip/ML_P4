"""G6 addendum 4, leak arm (exploratory): a hash-aware attacker with partial knowledge of the second table's placement, against D4.

  g6_leak.py --job p:vul:cCmM@GRID      c = candidate table-B slots per victim (the true slot plus c - 1 random others), m = informed holders
  g6_leak.py --job p:vul:ctl@GRID       control: only the table-A slot of each victim is held (no informed table-B holder)

The attacker is *given* the victim's table-A slot and the candidate set; it places one holder on the A slot and m holders on distinct candidates.
Analytical abstraction (no probing procedure, no crafting). Writes results/g2/g6l_<job>.npz.
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
    day, vset, cell = left.split(":")
    g = int(g)
    pk = load_day(day)
    z = np.load(OUT / f"prep_{day}.npz")
    t = np.load(OUT / f"targeted_prep_{day}.npz")
    kind = "top" if vset == "top" else "vulnerable"
    fh = hash_unique(z["uniq"], "crc", None)[z["inv"]]
    b_slot = (fh % HALF).astype(np.int64)
    b_slot2 = HALF + (hash_unique(z["uniq"], "polyirr", 7919)[z["inv"]] % HALF).astype(np.int64)
    idx = FlowIndex(t["code"])
    vf = t[f"{kind}_flow"]
    first = idx.order[idx.start[vf]]
    rng = np.random.default_rng(7919 * g + 3)
    if cell == "ctl":
        c, m = 0, 0
    else:
        c, m = (int(x) for x in cell[1:].split("m"))
    per = 1 + m
    start = np.repeat(t[f"{kind}_first"], per) - LEAD_NS + np.tile(np.arange(per) * 10 * MS, len(vf))
    slotA = np.repeat(b_slot[first], per)
    s2 = HALF + rng.integers(0, HALF, len(slotA))                     # the A-holder's own (unused) second candidate
    if m:
        for i, v in enumerate(first):                                 # informed holders sit on m distinct members of the candidate set
            true = int(b_slot2[v])
            others = HALF + rng.choice(HALF - 1, c - 1, replace=False) if c > 1 else np.array([], dtype=np.int64)
            others = others + (others >= true)                        # skip the true slot when drawing "other" candidates
            cand = np.concatenate([[true], others]).astype(np.int64)
            pick = rng.choice(c, m, replace=False)
            s2[i * per + 1:(i + 1) * per] = cand[pick]
    span = int(pk["ts_ns"].max()) + 1
    atk = _holders(start.astype(np.int64), slotA, span, rng, 250 * MS)
    atk.slot2 = s2[atk.flow]
    mg = merge_attack(pk, b_slot, fh, atk, b_slot2)
    n_a = len(atk.pk)
    fs_b = np.where(z["long_flag"], 100, 0)
    pc_all = np.concatenate([z["pkt_code"].astype(np.int64), np.ones(n_a, dtype=np.int64)])[mg.order]
    fs_all = np.concatenate([fs_b, np.full(n_a, 100)])[mg.order]
    sim = NetBeaconSim(models=CachedModels(load_tables(ART), pc_all, fs_all, None), clock_offset_ns=g * (WRAP_NS // GRID), **defence_kwargs("d4"))
    out = sim.run(mg.pk, force_slot=mg.slot, force_hash=mg.hash, force_long=mg.force_long, force_slot2=mg.slot2)
    name = job.replace(":", "_").replace("@", "_at")
    tmp = OUT / f"g6l_{name}.tmp.npz"
    np.savez_compressed(tmp, benign_outcome=out["outcome"][~mg.is_attacker], n_attacker_packets=n_a, victim_flow=vf,
                        holders=len(np.unique(atk.flow)), c=c, m=m)
    tmp.replace(OUT / f"g6l_{name}.npz")
    print(job, "done; holders", len(np.unique(atk.flow)), "packets", n_a)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    run(ap.parse_args().job)
