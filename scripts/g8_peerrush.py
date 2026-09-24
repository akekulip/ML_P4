"""G8: compiled-semantics emulator on PeerRush (docs/preregistration.md, G8 entry) -> results/g5/g8_<job>.npz

  g8_peerrush.py --job HASH:DELAY_US:ARM:F@GRID

HASH sorted or fold; DELAY_US recirculation delay; ARM und (8,192 slots, one table) or d4c (two ways of 4,096); F the fill in percent (0 = no attack).
Pairs with g5_peerrush.py's arms (same holder seed 1000*F+GRID). Writes benign-packet verdicts only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g2_mawi import ART, GRID, WRAP_NS, CachedModels

from dgrade.inject import merge_attack
from g5_peerrush import rotating_holders
from dgrade.netbeacon import load_tables
from dgrade.netbeacon_sim import TableModels, hash_unique, tuple_table
from dgrade.netbeacon_tofino import TofinoSim, fold_hash_unique, poly_b

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/g5"
N_SLOTS = 8192


def run(job: str) -> None:
    left, _, g = job.partition("@")
    hmode, dus, arm, f = left.split(":")
    g, f, dus = int(g), int(f), int(dus)
    ways = 2 if arm == "d4c" else 1
    half = N_SLOTS // 2
    h2seed = 7919 if arm == "d4" else 900_000 + g
    z = np.load(ROOT / "results/g1/stream.npz")
    pk = z["pk"]
    models = TableModels(load_tables(ART))
    uniq, inv = tuple_table(pk["src_ip"], pk["dst_ip"], pk["src_port"], pk["dst_port"], pk["proto"])
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
    pc, fs = models.pkt_codes(pk).astype(np.int64), models.flow_size(pk).astype(np.int64)
    span = int(pk["ts_ns"].max()) + 1
    if f > 0:
        atk = rotating_holders(f / 100, span, np.random.default_rng(1000 * f + g), tables=ways)
        m = merge_attack(pk, b_slot, tag, atk, b_slot2)
        n_a = len(atk.pk)
        pc_all = np.concatenate([pc, np.ones(n_a, dtype=np.int64)])[m.order]
        fs_all = np.concatenate([fs, np.full(n_a, 100)])[m.order]
        stream, slot, h, long_, slot2, is_atk = m.pk, m.slot, m.hash, m.force_long, m.slot2, m.is_attacker
    else:
        n_a, pc_all, fs_all = 0, pc, fs
        stream, slot, h, long_, slot2 = pk, b_slot, tag, np.zeros(len(pk), dtype=bool), b_slot2
        is_atk = np.zeros(len(pk), dtype=bool)
    sim = TofinoSim(models=CachedModels(load_tables(ART), pc_all, fs_all, None), n_slots=N_SLOTS,
                    clock_offset_ns=g * (WRAP_NS // GRID), claim_delay_ns=dus * 1000, ways=ways)
    out = sim.run(stream, force_slot=slot, force_hash=h, force_long=long_, force_slot2=slot2)
    name = job.replace(":", "_").replace("@", "_at")
    tmp = OUT / f"g8_{name}.tmp.npz"
    np.savez_compressed(tmp, result=out["result"][~is_atk].astype(np.int16), outcome=out["outcome"][~is_atk],
                        n_attacker_packets=n_a, race=json.dumps(out["race"]))
    tmp.replace(OUT / f"g8_{name}.npz")
    print(job, "done", out["race"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    run(ap.parse_args().job)
