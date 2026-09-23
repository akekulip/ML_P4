"""Emulator hooks for G2b: forced slot/identity/long for injected flows, and behaviour switches."""

import numpy as np

from dgrade.netbeacon_sim import (
    FALLBACK_COLLISION,
    FALLBACK_SHORT,
    NEW_OWNER,
    OWNER,
    NetBeaconSim,
    StubModels,
    make_packets,
)

MS = 1_000_000
UNIT = 1 << 20


def flow(n, *, sport, t0=0, gap=MS, src=0x0A000001):
    return make_packets(ts_ns=t0 + np.arange(n, dtype=np.int64) * gap, src_ip=src, dst_ip=0x0A000002,
                        src_port=sport, dst_port=80, proto=6, total_len=100)


def merge(*parts):
    p = np.concatenate(parts)
    return p[np.argsort(p["ts_ns"], kind="stable")]


def test_force_slot_and_hash_make_distinct_tuples_collide():
    a, b = flow(20, sport=1000), flow(4, sport=2000, t0=5 * MS + 1)
    pk = merge(a, b)
    slot = np.where(pk["src_port"] == 1000, 7, 7).astype(np.int64)      # both forced into slot 7
    fh = np.where(pk["src_port"] == 1000, 111, 222).astype(np.uint32)   # different identities
    out = NetBeaconSim(models=StubModels(), clock_offset_ns=300 * UNIT).run(pk, force_slot=slot, force_hash=fh)
    assert np.all(out["outcome"][pk["src_port"] == 2000] == FALLBACK_COLLISION)


def test_unforced_entries_use_the_hash():
    pk = merge(flow(3, sport=1000), flow(3, sport=2000, t0=10 * MS))
    force = np.full(len(pk), -1, dtype=np.int64)
    base = NetBeaconSim(models=StubModels(), clock_offset_ns=300 * UNIT).run(pk)
    out = NetBeaconSim(models=StubModels(), clock_offset_ns=300 * UNIT).run(pk, force_slot=force,
                                                                          force_hash=np.zeros(len(pk), np.uint32))
    assert np.array_equal(base["slot"], out["slot"])


def test_force_long_lets_a_short_predicted_flow_take_a_slot():
    pk = flow(5, sport=1000)
    kw = {"models": StubModels(flow_size=10), "clock_offset_ns": 300 * UNIT}
    assert np.all(NetBeaconSim(**kw).run(pk)["outcome"] == FALLBACK_SHORT)
    out = NetBeaconSim(**kw).run(pk, force_long=np.ones(len(pk), dtype=bool))
    assert out["outcome"][0] == NEW_OWNER and np.all(out["outcome"][1:] == OWNER)


def test_takeover_refresh_switch_blocks_the_immediate_second_takeover():
    a, b, c = flow(1, sport=1000), flow(1, sport=2000, t0=300 * UNIT), flow(1, sport=3000, t0=300 * UNIT + 10)
    pk = merge(a, b, c)
    kw = {"models": StubModels(), "n_slots": 1, "clock_offset_ns": 300 * UNIT}
    base = NetBeaconSim(**kw).run(pk)
    fixed = NetBeaconSim(takeover_refresh=True, **kw).run(pk)
    assert base["outcome"][pk["src_port"] == 3000][0] == NEW_OWNER            # inferred switch behaviour
    assert fixed["outcome"][pk["src_port"] == 3000][0] == FALLBACK_COLLISION


def test_no_wrap_switch_closes_the_eviction_window():
    start = 4000 * UNIT
    a = flow(20, sport=1000, t0=start, gap=UNIT)                # active until 4019 units
    b = flow(3, sport=2000, t0=(1 << 32) + 5 * UNIT)            # 82 units after a's last packet, past the wrap
    pk = merge(a, b)
    base = NetBeaconSim(models=StubModels(), n_slots=1, clock_offset_ns=0).run(pk)
    nowrap = NetBeaconSim(models=StubModels(), n_slots=1, clock_offset_ns=0, wrap_window=False).run(pk)
    assert base["outcome"][pk["src_port"] == 2000][0] == NEW_OWNER            # window open after the wrap
    assert nowrap["outcome"][pk["src_port"] == 2000][0] == FALLBACK_COLLISION  # incumbent is still active
    late = flow(3, sport=3000, t0=start + 20 * UNIT + 300 * UNIT)              # idle > 256 units: legitimate takeover
    p2 = merge(a, late)
    out = NetBeaconSim(models=StubModels(), n_slots=1, clock_offset_ns=0, wrap_window=False).run(p2)
    assert out["outcome"][p2["src_port"] == 3000][0] == NEW_OWNER
