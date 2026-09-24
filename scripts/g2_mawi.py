"""G2a: NetBeacon slot behaviour on the pre-registered MAWI slices, no attacker (docs/preregistration.md).

  g2_mawi.py --job DAY:GATE:KIND[:SEED]@GRID

DAY is p (2022-09-14) or r (2023-03-15); GATE is model (the shipped flow-size model) or oracle (a flow may
take a slot iff it truly has more than 50 packets in the slice, NetBeacon's own long-flow definition);
KIND is crc, xorsalt, poly, polyirr or tab (SEED required for all but crc); GRID picks the clock start
(GRID/30 of the 4.295 s wrap period). Writes results/g2/a_<job>.npz with per-second counts.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from dgrade.defences import defence_kwargs
from dgrade.netbeacon import load_tables
from dgrade.netbeacon_sim import (
    FALLBACK_COLLISION,
    FALLBACK_EMPTY,
    FALLBACK_SHORT,
    MEMO,
    NEW_OWNER,
    OWNER,
    NetBeaconSim,
    TableModels,
    flow_ids,
    hash_unique,
    tuple_table,
)
from dgrade.pcap import read_pcap

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/g2"
ART = ROOT / "third_party/NetBeacon"
DAYS = {"p": "202209141400", "r": "202303151400"}
WRAP_NS, GRID = 1 << 32, 30


def load_day(day: str) -> np.ndarray:
    cache = OUT / f"stream_{day}.npy"
    if cache.exists():
        return np.load(cache)
    OUT.mkdir(parents=True, exist_ok=True)
    pk, _ = read_pcap(ROOT / f"data/raw/mawi/{DAYS[day]}_120s.pcap", sort_by_time=True)
    pk["ts_ns"] -= pk["ts_ns"].min()
    np.save(cache, pk)
    return pk


class CachedModels(TableModels):
    """Shipped tables with the per-packet lookups precomputed once per day; ``long_flag`` (oracle gate) replaces the
    flow-size score with the true long-flow label."""

    def __init__(self, tables, pkt_code, flow_score, long_flag=None):
        super().__init__(tables)
        self.pc, self.fs, self.long_flag = pkt_code, flow_score, long_flag

    def pkt_codes(self, pk):
        return self.pc

    def flow_size(self, pk):
        return self.fs if self.long_flag is None else np.where(self.long_flag, 100, 0)


def prep(day: str) -> None:
    """Once per day: distinct tuples, oracle long-flow flags, and the shipped model's per-packet lookups."""
    pk = load_day(day)
    uniq, inv = tuple_table(pk["src_ip"], pk["dst_ip"], pk["src_port"], pk["dst_port"], pk["proto"])
    fid = flow_ids(pk, 1 << 62)
    tables = TableModels(load_tables(ART))
    np.savez(OUT / f"prep_{day}.npz", uniq=uniq, inv=inv.astype(np.int32), long_flag=(np.bincount(fid)[fid] > 50),
             pkt_code=tables.pkt_codes(pk).astype(np.int16), flow_score=tables.flow_size(pk).astype(np.int16))
    print("prepared", day, len(uniq), "distinct tuples")


def run(job: str) -> None:
    job, _, ns = job.partition("~")              # optional table size, e.g. p:oracle:crc@3+d4~32768 (load sweep); default 65,536
    n_slots = int(ns) if ns else 65536
    left, _, g = job.partition("@")
    g, _, dfn = g.partition("+")                 # optional defence suffix, e.g. p:oracle:crc@3+d3c16
    day, gate, kind, *seed = left.split(":")
    hseed = int(seed[0]) if seed else None
    pk = load_day(day)
    z = np.load(OUT / f"prep_{day}.npz")
    models = CachedModels(load_tables(ART), z["pkt_code"].astype(np.int64), z["flow_score"].astype(np.int64),
                          z["long_flag"] if gate == "oracle" else None)
    fh = hash_unique(z["uniq"], kind, hseed)[z["inv"]]
    rekey = float(dfn[3:]) if dfn.startswith("d5r") else None                        # G6 addendum 4: D5 with the second hash redrawn every `rekey` seconds
    dfn_base = "d5" if rekey else dfn
    two = dfn_base in ("d4", "d5", "d4s", "d4a", "d4c", "d4d1", "d4age")               # D4/D5: two half-size tables (same total capacity), independent second hash
    h2seed = 7919 if dfn == "d4" else 900_000 + int(g)
    if two:
        half = n_slots // 2
        slot = (fh % half).astype(np.int64)
        slot2 = half + (slot if dfn == "d4s" else (hash_unique(z["uniq"], "polyirr", h2seed)[z["inv"]] % half).astype(np.int64))
        if rekey:                                   # flows resident in table B lose their state at each rotation: their slot moves with the epoch
            epoch = ((pk["ts_ns"] - pk["ts_ns"].min()) // int(rekey * 10**9)).astype(np.int64)
            for e in range(1, int(epoch.max()) + 1):
                he = (hash_unique(z["uniq"], "polyirr", 900_000 + 1000 * e + int(g))[z["inv"]] % half).astype(np.int64)
                slot2 = np.where(epoch == e, half + he, slot2)
    else:
        slot, slot2 = (fh & (n_slots - 1)).astype(np.int64), None
    sim = NetBeaconSim(models=models, n_slots=n_slots, clock_offset_ns=int(g) * (WRAP_NS // GRID), hash2_seed=h2seed,
                       **defence_kwargs(dfn_base))
    out = sim.run(pk, force_slot=slot, force_hash=fh, force_slot2=slot2)
    sec = (pk["ts_ns"] // 10**9).astype(np.int64)
    oc = out["outcome"]
    per_sec = {name: np.bincount(sec, weights=(oc == code), minlength=120)
               for name, code in (("collision", FALLBACK_COLLISION), ("empty", FALLBACK_EMPTY), ("short", FALLBACK_SHORT),
                                  ("takeover", NEW_OWNER), ("owner", OWNER), ("memo", MEMO))}
    per_sec["long_pred"] = np.bincount(sec, weights=out["predicted_long"], minlength=120)
    per_sec["packets"] = np.bincount(sec, minlength=120).astype(float)
    name = job.replace(":", "_").replace("@", "_at").replace("+", "_p_") + (f"_n{n_slots}" if ns else "")
    tmp = OUT / f"a_{name}.tmp.npz"                        # atomic write
    np.savez_compressed(tmp, outcome=oc, **per_sec)
    tmp.replace(OUT / f"a_{name}.npz")
    print(job, "done", np.bincount(oc, minlength=7), f"predicted long {out['predicted_long'].mean():.3f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--job")
    ap.add_argument("--prep")
    a = ap.parse_args()
    prep(a.prep) if a.prep else run(a.job)
