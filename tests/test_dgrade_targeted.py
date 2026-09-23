"""Victim selection and holder construction for the G2b targeted arms (analytical abstraction)."""

import numpy as np

from dgrade.flowstats import FlowIndex
from dgrade.inject_targeted import build_targeted, random_holders, select_victims
from dgrade.netbeacon_sim import make_packets

MS = 1_000_000
SPAN = 20 * 10**9


def _stream():
    """Flow 0: 3000 packets, no gaps. Flow 1: 500 packets with a 400 ms gap after packet 100.
    Flow 2: 1500 packets with a 350 ms gap after packet 10. Flow 3: 60 packets, no gap. Flow 4: 30 packets (short)."""
    parts, fid = [], []
    t = np.arange(3000) * 2 * MS
    parts.append(t)
    fid.append(np.full(3000, 0))
    t1 = np.concatenate([np.arange(101) * 10 * MS, 1000 * MS + 400 * MS + np.arange(399) * 10 * MS])
    parts.append(t1)
    fid.append(np.full(len(t1), 1))
    t2 = np.concatenate([np.arange(11) * 5 * MS, 100 * MS + 350 * MS + np.arange(1489) * 5 * MS])
    parts.append(t2)
    fid.append(np.full(len(t2), 2))
    parts.append(np.arange(60) * 30 * MS)
    fid.append(np.full(60, 3))
    parts.append(np.arange(30) * 30 * MS)
    fid.append(np.full(30, 4))
    ts = np.concatenate(parts)
    f = np.concatenate(fid)
    o = np.argsort(ts, kind="stable")
    pk = make_packets(ts_ns=ts[o], src_ip=f[o] + 1, dst_ip=99, src_port=1000, dst_port=80, proto=6, total_len=100)
    return pk, f[o]


def test_select_top_and_vulnerable_sets():
    pk, f = _stream()
    idx = FlowIndex(f)
    slots = np.array([10, 11, 12, 13, 14])
    top = select_victims(pk, idx, slots, "top", k=3)
    assert [v.flow for v in top] == [0, 2, 1]                       # by packet count, long flows only
    vul = select_victims(pk, idx, slots, "vulnerable", k=3)
    assert [v.flow for v in vul] == [2, 1, 3]                       # below 2048 packets, more than 50
    assert vul[0].slot == 12 and top[0].slot == 10


def test_preempt_holders_start_before_the_victim_and_follow_its_slot():
    pk, f = _stream()
    idx = FlowIndex(f)
    v = select_victims(pk, idx, np.array([10, 11, 12, 13, 14]), "vulnerable", k=2)
    a = build_targeted(v, "preempt", span_ns=SPAN, rng=np.random.default_rng(0))
    assert len(np.unique(a.flow)) == 2
    for k, vic in enumerate(v):
        t = np.sort(a.pk["ts_ns"][a.flow == k])
        assert t[0] == vic.first_ts - 500 * MS and np.all(np.diff(t) == 250 * MS) and t[-1] <= SPAN
        assert np.all(a.slot[a.flow == k] == vic.slot)


def test_reactive_holders_start_in_the_victims_first_long_gap_and_skip_gapless_victims():
    pk, f = _stream()
    idx = FlowIndex(f)
    v = select_victims(pk, idx, np.array([10, 11, 12, 13, 14]), "vulnerable", k=3)      # flows 2, 1, 3
    a = build_targeted(v, "reactive", span_ns=SPAN, rng=np.random.default_rng(0))
    assert a.failed == [3]                                                              # flow 3 has no gap over 300 ms
    starts = {v[k].flow: a.pk["ts_ns"][a.flow == k].min() for k in np.unique(a.flow)}
    assert starts[2] == 10 * 5 * MS + 275 * MS                                          # last packet before the gap + 275 ms
    assert starts[1] == 100 * 10 * MS + 275 * MS
    assert starts[2] < 100 * MS + 350 * MS                                              # inside the gap, before the victim returns


def test_random_holders_count_slots_and_cadence():
    a = random_holders(200, span_ns=SPAN, rng=np.random.default_rng(1), n_slots=1000)
    assert len(np.unique(a.flow)) == 200 and np.all(a.slot < 1000)
    assert a.slot[np.unique(a.flow, return_index=True)[1]].min() >= 0
    assert np.all(np.diff(np.sort(a.pk["ts_ns"][a.flow == 0])) == 250 * MS)


def test_preempt_holder_may_start_before_the_slice_when_the_victim_starts_at_zero():
    pk, f = _stream()
    idx = FlowIndex(f)
    v = select_victims(pk, idx, np.array([10, 11, 12, 13, 14]), "top", k=1)      # flow 0 starts at t = 0
    a = build_targeted(v, "preempt", span_ns=SPAN, rng=np.random.default_rng(0))
    assert a.pk["ts_ns"].min() == -500 * MS
