"""Analytical injection of holder flows for G2b. Abstraction only: slots are supplied, never searched for."""

import numpy as np

from dgrade.inject import build_fill, merge_attack
from dgrade.netbeacon_sim import PACKET_DTYPE, make_packets

MS = 1_000_000
SPAN = 120_000_000_000


def test_fill_flow_count_slots_and_cadence():
    rng = np.random.default_rng(0)
    a = build_fill(0.10, "k1", n_slots=1000, span_ns=10 * 10**9, rng=rng, interval_ns=250 * MS, ramp_ns=10**9)
    assert len(np.unique(a.flow)) == 100
    assert len(np.unique(a.slot[np.unique(a.flow, return_index=True)[1]])) == 100      # K1: distinct slots
    for f in (0, 17, 99):
        t = np.sort(a.pk["ts_ns"][a.flow == f])
        assert np.all(np.diff(t) == 250 * MS)
        assert t[0] < 10**9 and t[-1] <= 10 * 10**9
    assert a.pk.dtype == PACKET_DTYPE and np.all(a.slot >= 0) and np.all(a.slot < 1000)


def test_k0_slots_are_uniform_with_repeats_and_k1_has_none():
    rng = np.random.default_rng(1)
    k0 = build_fill(0.5, "k0", n_slots=200, span_ns=10**9, rng=rng, interval_ns=250 * MS, ramp_ns=10**8)
    first = np.unique(k0.flow, return_index=True)[1]
    assert len(np.unique(k0.slot[first])) < 100                                          # birthday collisions
    k1 = build_fill(0.5, "k1", n_slots=200, span_ns=10**9, rng=rng, interval_ns=250 * MS, ramp_ns=10**8)
    first = np.unique(k1.flow, return_index=True)[1]
    assert len(np.unique(k1.slot[first])) == 100


def test_identities_are_distinct_and_flows_stop_before_2048_packets():
    rng = np.random.default_rng(2)
    a = build_fill(0.02, "k0", n_slots=5000, span_ns=1000 * 10**9, rng=rng, interval_ns=250 * MS, ramp_ns=10**9)
    assert len(np.unique(a.hash)) == len(np.unique(a.flow))                              # one identity per flow
    counts = np.bincount(a.flow)
    assert counts.max() <= 2000                                                          # rotated before 2048 packets


def test_merge_orders_by_time_and_flags_attacker_packets():
    rng = np.random.default_rng(3)
    ben = make_packets(ts_ns=np.arange(0, 5 * 10**9, 10 * MS), src_ip=1, dst_ip=2, src_port=10, dst_port=20, proto=6,
                       total_len=100)
    bslot = np.full(len(ben), 5, dtype=np.int64)
    bhash = np.full(len(ben), 7, dtype=np.uint32)
    a = build_fill(0.01, "k1", n_slots=1000, span_ns=5 * 10**9, rng=rng, interval_ns=250 * MS, ramp_ns=10**9)
    m = merge_attack(ben, bslot, bhash, a)
    assert len(m.pk) == len(ben) + len(a.pk)
    assert np.all(np.diff(m.pk["ts_ns"]) >= 0)
    assert m.is_attacker.sum() == len(a.pk) and np.all(m.force_long[m.is_attacker]) and not m.force_long[~m.is_attacker].any()
    assert np.all(m.slot >= 0) and np.array_equal(m.pk["ts_ns"][~m.is_attacker], ben["ts_ns"])
