"""G2b fill arms: holder flows injected into the pre-registered MAWI slices (docs/preregistration.md, G2b).

  g2b_mawi.py --job DAY:GATE:MODE:F@GRID

DAY p or r; GATE oracle or model; MODE k1 (hash known: the shipped CRC places benign flows, the adversary is
*given* distinct slots), b0l (the decision baseline B0-L: same benign hash as k1, but the adversary's long flows
land on uniform random slots) or k0 (secret hash: an irreducible-polynomial CRC keyed with GRID places benign
flows, the adversary lands on uniform random slots); F is the percentage of the 65,536 slots aimed at (1, 5, 10, 25, 50,
75, 90); GRID is both the clock start (GRID/30 of the wrap period) and the draw number. Analytical abstraction
only (see ``dgrade.inject``). The paired no-attack baseline is the G2a run at the same clock and hash.
Writes results/g2/b_<job>.npz with the benign packets' outcomes and per-flow attacker outcomes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g2_mawi import ART, GRID, OUT, WRAP_NS, CachedModels, load_day

from dgrade.defences import defence_kwargs
from dgrade.inject import build_fill, merge_attack
from dgrade.netbeacon import load_tables
from dgrade.netbeacon_sim import (
    NEW_OWNER,
    OWNER,
    NetBeaconSim,
    hash_unique,
)


def run(job: str) -> None:
    job, _, ns = job.partition("~")              # optional table size (load sweep), e.g. p:oracle:b0l:10@3+d4~32768; default 65,536
    n_slots = int(ns) if ns else 65536
    left, _, g = job.partition("@")
    g, _, dfn = g.partition("+")                 # optional defence suffix, e.g. p:oracle:b0l:10@3+d3c16
    day, gate, mode, f = left.split(":")
    g, f = int(g), int(f)
    pk = load_day(day)
    z = np.load(OUT / f"prep_{day}.npz")
    if mode not in ("k1", "b0l", "k0"):
        raise ValueError(f"unknown mode {mode!r}")
    kind, hseed = ("polyirr", g) if mode == "k0" else ("crc", None)
    fh = hash_unique(z["uniq"], kind, hseed)[z["inv"]]
    two = dfn in ("d4", "d5", "d4s", "d4a", "d4c", "d4d1", "d4age")                    # D4/D5: two half-size tables (same total capacity), independent second hash
    h2seed = 7919 if dfn == "d4" else 900_000 + g
    if two:
        if mode != "b0l":
            raise ValueError("D4/D5 are run against the B0-L fill only")
        half = n_slots // 2
        b_slot = (fh % half).astype(np.int64)
        b_slot2 = half + (b_slot if dfn == "d4s" else (hash_unique(z["uniq"], "polyirr", h2seed)[z["inv"]] % half).astype(np.int64))
    else:
        b_slot, b_slot2 = (fh & (n_slots - 1)).astype(np.int64), None
    span = int(pk["ts_ns"].max()) + 1
    rng = np.random.default_rng(1000 * f + g)
    atk = build_fill(f / 100, "k1" if mode == "k1" else "k0", n_slots, span, rng, tables=2 if two else 1)
    if dfn == "d4s":
        atk.slot2 = n_slots // 2 + atk.slot
    m = merge_attack(pk, b_slot, fh, atk, b_slot2)
    n_b, n_a = len(pk), len(atk.pk)
    long_flag = z["long_flag"] if gate == "oracle" else None
    fs_b = np.where(long_flag, 100, 0) if long_flag is not None else z["flow_score"].astype(np.int64)
    # attacker packets get a benign-looking per-packet verdict; their flow-size gate is forced long
    pc_all = np.concatenate([z["pkt_code"].astype(np.int64), np.ones(n_a, dtype=np.int64)])[m.order]
    fs_all = np.concatenate([fs_b, np.full(n_a, 100)])[m.order]
    models = CachedModels(load_tables(ART), pc_all, fs_all, None)
    sim = NetBeaconSim(models=models, n_slots=n_slots, clock_offset_ns=g * (WRAP_NS // GRID), hash2_seed=h2seed,
                       **defence_kwargs(dfn))
    out = sim.run(m.pk, force_slot=m.slot, force_hash=m.hash, force_long=m.force_long, force_slot2=m.slot2)
    oc = out["outcome"]
    pos = np.empty(len(m.order), dtype=np.int64)
    pos[m.order] = np.arange(len(m.order))
    a_oc = oc[pos[n_b:]]                                   # attacker outcomes in attacker-packet order
    owned = np.bincount(atk.flow, weights=np.isin(a_oc, (OWNER, NEW_OWNER)).astype(float))
    npk = np.bincount(atk.flow).astype(float)
    name = job.replace(":", "_").replace("@", "_at").replace("+", "_p_") + (f"_n{n_slots}" if ns else "")
    tmp = OUT / f"b_{name}.tmp.npz"                        # atomic write
    np.savez_compressed(tmp, benign_outcome=oc[~m.is_attacker], atk_owned=owned, atk_packets=npk,
                        atk_slot_first=atk.slot[np.unique(atk.flow, return_index=True)[1]], n_attacker_packets=n_a)
    tmp.replace(OUT / f"b_{name}.npz")
    print(job, "done; attacker flows holding a slot for >=90% of their packets:", float(np.mean(owned >= 0.9 * npk)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    run(ap.parse_args().job)
