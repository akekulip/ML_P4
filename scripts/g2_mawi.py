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


class OracleGate(TableModels):
    """Shipped tables, except that the flow-size gate is the true long-flow label."""

    def __init__(self, tables, long_flag: np.ndarray):
        super().__init__(tables)
        self.long_flag = long_flag

    def flow_size(self, pk: np.ndarray) -> np.ndarray:
        return np.where(self.long_flag, 100, 0)


def run(job: str) -> None:
    left, _, g = job.partition("@")
    day, gate, kind, *seed = left.split(":")
    hseed = int(seed[0]) if seed else None
    pk = load_day(day)
    tables = load_tables(ART)
    if gate == "oracle":
        fid = flow_ids(pk, 1 << 62)
        models = OracleGate(tables, (np.bincount(fid)[fid] > 50))
    else:
        models = TableModels(tables)
    sim = NetBeaconSim(models=models, clock_offset_ns=int(g) * (WRAP_NS // GRID), hash_kind=kind, hash_seed=hseed)
    out = sim.run(pk)
    sec = (pk["ts_ns"] // 10**9).astype(np.int64)
    oc = out["outcome"]
    per_sec = {name: np.bincount(sec, weights=(oc == code), minlength=120)
               for name, code in (("collision", FALLBACK_COLLISION), ("empty", FALLBACK_EMPTY), ("short", FALLBACK_SHORT),
                                  ("takeover", NEW_OWNER), ("owner", OWNER), ("memo", MEMO))}
    per_sec["long_pred"] = np.bincount(sec, weights=out["predicted_long"], minlength=120)
    per_sec["packets"] = np.bincount(sec, minlength=120).astype(float)
    name = job.replace(":", "_").replace("@", "_at")
    np.savez_compressed(OUT / f"a_{name}.npz", outcome=oc, **per_sec)
    print(job, "done", np.bincount(oc, minlength=7), f"predicted long {out['predicted_long'].mean():.3f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    run(ap.parse_args().job)
