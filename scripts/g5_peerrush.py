"""G5: labelled fill attack on PeerRush with a load-matched table (docs/preregistration.md, G5 amendments).

  g5_peerrush.py --job F:ARM@GRID

F is the fill fraction in percent of 8,192 slots (0 = no attack); ARM is und (shipped design) or a defence from dgrade.defences (d1, d3c8, d3c16);
GRID is the clock start (GRID/30 of the wrap period) and the draw number. Holders are random-slot long flows at 4 packets/s that rotate every 490 s
(analytical abstraction, see dgrade.inject). Writes results/g5/pr_<job>.npz with the verdicts of the benign packets.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g2_mawi import ART, CachedModels

from dgrade.defences import defence_kwargs
from dgrade.inject import Attack, build_fill, merge_attack
from dgrade.netbeacon import load_tables
from dgrade.netbeacon_sim import (
    NetBeaconSim,
    TableModels,
    hash_unique,
    tuple_table,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/g5"
N_SLOTS = 8192
WRAP_NS, GRID = 1 << 32, 30
ROT_NS = 490 * 10**9
NS = 10**9


def rotating_holders(f: float, span_ns: int, rng: np.random.Generator) -> Attack:
    parts = []
    for r in range(int(np.ceil(span_ns / ROT_NS))):
        a = build_fill(f, "k0", N_SLOTS, min(500 * NS, span_ns - r * ROT_NS), rng)
        a.pk["ts_ns"] += r * ROT_NS
        parts.append(a)
    off = np.cumsum([0] + [len(np.unique(p.flow)) for p in parts[:-1]])
    pk = np.concatenate([p.pk for p in parts])
    flow = np.concatenate([p.flow + o for p, o in zip(parts, off, strict=True)])
    return Attack(pk, flow, np.concatenate([p.slot for p in parts]), np.concatenate([p.hash for p in parts]))


def run(job: str) -> None:
    left, _, g = job.partition("@")
    f, arm = left.split(":")
    f, g = int(f), int(g)
    z = np.load(ROOT / "results/g1/stream.npz")
    pk = z["pk"]
    models = TableModels(load_tables(ART))
    uniq, inv = tuple_table(pk["src_ip"], pk["dst_ip"], pk["src_port"], pk["dst_port"], pk["proto"])
    fh = hash_unique(uniq, "crc", None)[inv]
    b_slot = (fh & (N_SLOTS - 1)).astype(np.int64)
    pc, fs = models.pkt_codes(pk).astype(np.int64), models.flow_size(pk).astype(np.int64)
    span = int(pk["ts_ns"].max()) + 1
    if f > 0:
        atk = rotating_holders(f / 100, span, np.random.default_rng(1000 * f + g))
        m = merge_attack(pk, b_slot, fh, atk)
        n_a = len(atk.pk)
        pc_all = np.concatenate([pc, np.ones(n_a, dtype=np.int64)])[m.order]
        fs_all = np.concatenate([fs, np.full(n_a, 100)])[m.order]
        stream, slot, h, long_, is_atk = m.pk, m.slot, m.hash, m.force_long, m.is_attacker
    else:
        n_a, pc_all, fs_all = 0, pc, fs
        stream, slot, h, long_, is_atk = pk, b_slot, fh, np.zeros(len(pk), dtype=bool), np.zeros(len(pk), dtype=bool)
    sim = NetBeaconSim(models=CachedModels(load_tables(ART), pc_all, fs_all, None), n_slots=N_SLOTS,
                       clock_offset_ns=g * (WRAP_NS // GRID), **defence_kwargs("" if arm == "und" else arm))
    out = sim.run(stream, force_slot=slot, force_hash=h, force_long=long_)
    OUT.mkdir(parents=True, exist_ok=True)
    name = job.replace(":", "_").replace("@", "_at")
    np.savez_compressed(OUT / f"pr_{name}.npz", result=out["result"][~is_atk].astype(np.int16),
                        outcome=out["outcome"][~is_atk], n_attacker_packets=n_a)
    print(job, "done; attacker packets", n_a)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    run(ap.parse_args().job)
