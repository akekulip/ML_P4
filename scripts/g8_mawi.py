"""G8: compiled-semantics emulator on MAWI (docs/preregistration.md, G8 entry) -> results/g2/g8_<job>.npz

  g8_mawi.py --job DAY:HASH:DELAY_US:ARM:F@GRID

HASH sorted (the abstract emulator's hashes: the hard-gate mode) or fold (XOR-folded message, both CRCs); DELAY_US the recirculation delay between the takeover
packet and its pass-2 write; ARM und (one table, 65,536 slots) or d4c (two ways of 32,768, D4c placement); F the B0-L fill in percent (0 = no attack).
Holders and clock starts are drawn as in g2b_mawi.py (seed 1000 F + GRID), so runs pair with the abstract arms. Analytical holder abstraction as before.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g2_mawi import ART, GRID, OUT, WRAP_NS, CachedModels, load_day

from dgrade.inject import build_fill, merge_attack
from dgrade.netbeacon import load_tables
from dgrade.netbeacon_sim import hash_unique
from dgrade.netbeacon_tofino import TofinoSim, fold_hash_unique, poly_b

N_SLOTS = 65536


def run(job: str) -> None:
    left, _, g = job.partition("@")
    day, hmode, dus, arm, f = left.split(":")
    g, f, dus = int(g), int(f), int(dus)
    ways = 2 if arm == "d4c" else 1
    half = N_SLOTS // 2
    h2seed = 900_000 + g                    # matches g2_mawi.py's convention for dfn != "d4"
    pk = load_day(day)
    z = np.load(OUT / f"prep_{day}.npz")
    uniq, inv = z["uniq"], z["inv"]
    if hmode == "sorted":
        tag = hash_unique(uniq, "crc", None)[inv]
        hb = hash_unique(uniq, "polyirr", h2seed)[inv] if ways == 2 else None
    elif hmode == "fold":
        tag = fold_hash_unique(uniq)[inv]
        hb = fold_hash_unique(uniq, poly_b(h2seed))[inv] if ways == 2 else None
    else:
        raise ValueError(f"unknown hash mode {hmode!r}")
    if ways == 2:
        b_slot, b_slot2 = (tag % half).astype(np.int64), half + (hb % half).astype(np.int64)
    else:
        b_slot, b_slot2 = (tag & (N_SLOTS - 1)).astype(np.int64), None
    span = int(pk["ts_ns"].max()) + 1
    if f > 0:
        atk = build_fill(f / 100, "k0", N_SLOTS, span, np.random.default_rng(1000 * f + g), tables=ways)
        m = merge_attack(pk, b_slot, tag, atk, b_slot2)
        n_a = len(atk.pk)
        long_flag = z["long_flag"]
        fs_b = np.where(long_flag, 100, 0)
        pc_all = np.concatenate([z["pkt_code"].astype(np.int64), np.ones(n_a, dtype=np.int64)])[m.order]
        fs_all = np.concatenate([fs_b, np.full(n_a, 100)])[m.order]
        stream, slot, h, long_, slot2, is_atk = m.pk, m.slot, m.hash, m.force_long, m.slot2, m.is_attacker
    else:
        n_a = 0
        pc_all, fs_all = z["pkt_code"].astype(np.int64), np.where(z["long_flag"], 100, 0)
        stream, slot, h, long_, slot2 = pk, b_slot, tag, np.zeros(len(pk), dtype=bool), b_slot2
        is_atk = np.zeros(len(pk), dtype=bool)
    sim = TofinoSim(models=CachedModels(load_tables(ART), pc_all, fs_all, None), n_slots=N_SLOTS, clock_offset_ns=g * (WRAP_NS // GRID),
                    claim_delay_ns=dus * 1000, ways=ways)
    out = sim.run(stream, force_slot=slot, force_hash=h, force_long=long_, force_slot2=slot2)
    name = job.replace(":", "_").replace("@", "_at")
    tmp = OUT / f"g8_{name}.tmp.npz"
    np.savez_compressed(tmp, benign_outcome=out["outcome"][~is_atk], n_attacker_packets=n_a, race=json.dumps(out["race"]))
    tmp.replace(OUT / f"g8_{name}.npz")
    print(job, "done", out["race"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    run(ap.parse_args().job)
