"""Two-table (d-left) slot admission, D4 (docs/preregistration.md, D4 entry).

Total capacity S is split into table A (slots 0..S/2-1) and table B (S/2..S-1) with independent hashes. A packet
finds its flow in either candidate slot; a newcomer takes a takeable candidate and is refused only when both are held.
Slots are forced here so that collisions are known.
"""

import numpy as np
import pytest

from dgrade.netbeacon_sim import (
    FALLBACK_COLLISION,
    NEW_OWNER,
    OWNER,
    NetBeaconSim,
    StubModels,
    make_packets,
)

MS = 1_000_000
S = 8        # total slots: table A = 0..3, table B = 4..7


def flow(n, sport, t0=0, gap=10 * MS):
    return make_packets(ts_ns=t0 + np.arange(n, dtype=np.int64) * gap, src_ip=0x0A000001, dst_ip=0x0A000002,
                        src_port=sport, dst_port=80, proto=6, total_len=100)


def run(flows, cands, two_way=True):
    """flows: list of packet arrays (sport identifies the flow); cands: sport -> (slot A, slot B)."""
    pk = np.concatenate(flows)
    pk = pk[np.argsort(pk["ts_ns"], kind="stable")]
    a = np.array([cands[int(p)][0] for p in pk["src_port"]], dtype=np.int64)
    b = np.array([cands[int(p)][1] for p in pk["src_port"]], dtype=np.int64)
    h = (pk["src_port"].astype(np.uint32) + 1000).astype(np.uint32)
    sim = NetBeaconSim(models=StubModels(), n_slots=S, clock_offset_ns=300 * (1 << 20), two_way=two_way)
    out = sim.run(pk, force_slot=a, force_hash=h, force_long=np.ones(len(pk), dtype=bool), force_slot2=b)
    return pk, out["outcome"]


def first(pk, oc, sport):
    return oc[np.flatnonzero(pk["src_port"] == sport)[0]]


def test_newcomer_takes_second_candidate_when_first_is_held():
    a, b = flow(20, 1), flow(5, 2, t0=50 * MS)
    pk, oc = run([a, b], {1: (0, 4), 2: (0, 5)})
    assert first(pk, oc, 1) == NEW_OWNER and first(pk, oc, 2) == NEW_OWNER
    pk1, oc1 = run([a, b], {1: (0, 4), 2: (0, 5)}, two_way=False)     # one table: same first slot, so a collision
    assert first(pk1, oc1, 2) == FALLBACK_COLLISION


def test_refused_only_when_both_candidates_are_held():
    a, b, c = flow(30, 1), flow(30, 2), flow(5, 3, t0=100 * MS)
    pk, oc = run([a, b, c], {1: (0, 4), 2: (0, 5), 3: (0, 5)})   # flow 1 holds slot 0, flow 2 is pushed to slot 5
    assert first(pk, oc, 2) == NEW_OWNER
    assert first(pk, oc, 3) == FALLBACK_COLLISION
    assert np.all(oc[pk["src_port"] == 3] == FALLBACK_COLLISION)


def test_owner_in_table_b_keeps_its_slot_and_hits_it():
    a, b = flow(20, 1), flow(20, 2, t0=50 * MS)
    pk, oc = run([a, b], {1: (0, 4), 2: (0, 5)})
    later = oc[np.flatnonzero(pk["src_port"] == 2)[1:]]
    assert np.all(later == OWNER)
    assert np.all(oc[np.flatnonzero(pk["src_port"] == 1)[1:]] == OWNER)       # flow 1 is not disturbed


def test_newcomer_prefers_a_never_claimed_slot_over_taking_an_idle_one():
    a = flow(3, 1)                                   # goes idle after 20 ms; slot 0 is claimed
    b = flow(5, 2, t0=2000 * MS)                     # arrives long after the idle timeout
    pk, oc = run([a, b], {1: (0, 4), 2: (0, 5)})
    assert first(pk, oc, 2) == NEW_OWNER
    a_late = flow(3, 1, t0=2100 * MS)
    pk, oc = run([a, b, a_late], {1: (0, 4), 2: (0, 5)})
    assert np.all(oc[np.flatnonzero(pk["src_port"] == 1)[3:]] == OWNER)       # flow 1 still owns slot 0: B took slot 5


def test_forced_slots_must_lie_in_their_own_table():
    a = flow(3, 1)
    with pytest.raises(ValueError):
        run([a], {1: (5, 4)})                        # table A slot outside 0..3
    with pytest.raises(ValueError):
        run([a], {1: (0, 2)})                        # table B slot outside 4..7


def test_two_way_needs_even_capacity_and_no_rent():
    with pytest.raises(ValueError):
        NetBeaconSim(models=StubModels(), n_slots=7, two_way=True).run(flow(3, 1))
    with pytest.raises(ValueError):
        NetBeaconSim(models=StubModels(), n_slots=8, two_way=True, rent="credit", wrap_window=False).run(flow(3, 1))


def test_hash_derived_candidates_work_without_forcing():
    pk = np.concatenate([flow(40, s, t0=s * MS) for s in range(1, 6)])
    pk = pk[np.argsort(pk["ts_ns"], kind="stable")]
    out = NetBeaconSim(models=StubModels(), n_slots=64, clock_offset_ns=300 * (1 << 20), two_way=True).run(pk)
    assert np.count_nonzero(out["outcome"] == NEW_OWNER) == 5      # five flows, ample room: every flow gets a slot
    assert not np.any(out["outcome"] == FALLBACK_COLLISION)


def test_stays_in_table_a_when_a_is_takeable_and_b_is_held():
    b_holder, a_new = flow(30, 1), flow(5, 2, t0=50 * MS)
    pk, oc = run([b_holder, a_new], {1: (3, 5), 2: (0, 5)})   # flow 1 took A slot 3 (free); flow 2's B candidate 5 is free too
    pk, oc = run([flow(30, 9), b_holder, a_new], {9: (2, 5), 1: (3, 5), 2: (0, 5)})   # flow 9 holds slot 2, flow 1 slot 3; flow 2 -> slot 0
    assert first(pk, oc, 2) == NEW_OWNER


def test_both_takeable_and_claimed_prefers_the_longest_idle():
    old, newer = flow(3, 1), flow(3, 2, t0=1000 * MS)          # both go idle; flow 1 idled earlier
    late = flow(2, 3, t0=3000 * MS)
    pk, oc = run([old, newer, late], {1: (0, 4), 2: (1, 5), 3: (0, 5)})
    # flow 3 sees slot 0 (idle since ~20 ms) and slot 5 (never claimed): a never-claimed slot wins over an idle one
    pk2, oc2 = run([old, newer, late, flow(2, 4, t0=0)], {1: (0, 4), 2: (1, 5), 3: (0, 5), 4: (2, 5)})
    assert first(pk, oc, 3) == NEW_OWNER and first(pk2, oc2, 3) == NEW_OWNER


def test_two_way_works_with_an_unwrapped_clock():
    a, b = flow(20, 1), flow(5, 2, t0=50 * MS)
    pk = np.concatenate([a, b])
    pk = pk[np.argsort(pk["ts_ns"], kind="stable")]
    cs = {1: (0, 4), 2: (0, 5)}
    sl = np.array([cs[int(p)][0] for p in pk["src_port"]]); s2 = np.array([cs[int(p)][1] for p in pk["src_port"]])
    h = (pk["src_port"].astype(np.uint32) + 1000).astype(np.uint32)
    out = NetBeaconSim(models=StubModels(), n_slots=S, clock_offset_ns=300 * (1 << 20), two_way=True, wrap_window=False).run(
        pk, force_slot=sl, force_hash=h, force_long=np.ones(len(pk), dtype=bool), force_slot2=s2)
    assert out["outcome"][np.flatnonzero(pk["src_port"] == 2)[0]] == NEW_OWNER


def test_same_hash_in_both_tables_is_rejected():
    with pytest.raises(ValueError):
        NetBeaconSim(models=StubModels(), n_slots=8, two_way=True, hash_kind="polyirr", hash_seed=7919).run(flow(3, 1))


def test_two_table_holders_are_paired_with_the_one_table_draw():
    from dgrade.inject import build_fill
    one = build_fill(0.1, "k0", 4096, 20 * 10**9, np.random.default_rng(5))
    two = build_fill(0.1, "k0", 4096, 20 * 10**9, np.random.default_rng(5), tables=2)
    assert np.array_equal(one.pk["ts_ns"], two.pk["ts_ns"]) and np.array_equal(one.hash, two.hash)
    assert np.all(two.slot < 2048) and np.all(two.slot2 >= 2048) and np.all(two.slot2 < 4096)
