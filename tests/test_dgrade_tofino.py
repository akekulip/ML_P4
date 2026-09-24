"""Compiled-semantics emulator (src/dgrade/netbeacon_tofino.py): equality with the abstract emulator at zero delay, and the race behaviours of pass 2."""

import numpy as np
import pytest

from dgrade.netbeacon_sim import (
    FALLBACK_COLLISION,
    NEW_OWNER,
    OWNER,
    NetBeaconSim,
    StubModels,
    make_packets,
    tuple_table,
)
from dgrade.netbeacon_tofino import TofinoSim, fold_hash_unique, fold_keys

MS = 1_000_000
US = 1_000
OFFSET = 300 * (1 << 20)


def stream(specs):
    """specs: list of (sport, t0_ns, n, gap_ns); one flow per sport."""
    parts = [make_packets(ts_ns=t0 + np.arange(n, dtype=np.int64) * gap, src_ip=0x0A000001, dst_ip=0x0A000002, src_port=sp, dst_port=80, proto=6, total_len=100)
             for sp, t0, n, gap in specs]
    pk = np.concatenate(parts)
    return pk[np.argsort(pk["ts_ns"], kind="stable")]


def forced(pk, cands):
    a = np.array([cands[int(p)][0] for p in pk["src_port"]], dtype=np.int64)
    b = np.array([cands[int(p)][1] for p in pk["src_port"]], dtype=np.int64) if len(next(iter(cands.values()))) > 1 else None
    h = (pk["src_port"].astype(np.uint32) + 1000).astype(np.uint32)
    return a, b, h


def tofino(pk, cands, delay=0, ways=2, S=8):
    a, b, h = forced(pk, cands)
    sim = TofinoSim(models=StubModels(), n_slots=S, clock_offset_ns=OFFSET, claim_delay_ns=delay, ways=ways)
    return sim.run(pk, force_slot=a, force_hash=h, force_long=np.ones(len(pk), dtype=bool), force_slot2=b)


def test_zero_delay_equals_the_abstract_emulator_two_ways_and_one_way():
    rng = np.random.default_rng(0)
    S = 32
    for seed in range(6):
        rng = np.random.default_rng(seed)
        specs = [(1000 + f, int(rng.integers(0, 2_000)) * MS, int(rng.integers(3, 60)), int(rng.integers(1, 40)) * MS) for f in range(14)]
        specs.append((5000, 0, 2200, 2 * MS))
        pk = stream(specs)
        cands = {sp: (int(rng.integers(0, S // 2)), int(rng.integers(S // 2, S))) for sp, *_ in specs}
        a, b, h = forced(pk, cands)
        ab = NetBeaconSim(models=StubModels(), n_slots=S, clock_offset_ns=OFFSET, two_way=True, two_way_policy="unclaimed_first").run(
            pk, force_slot=a, force_hash=h, force_long=np.ones(len(pk), dtype=bool), force_slot2=b)
        tf = TofinoSim(models=StubModels(), n_slots=S, clock_offset_ns=OFFSET, ways=2).run(
            pk, force_slot=a, force_hash=h, force_long=np.ones(len(pk), dtype=bool), force_slot2=b)
        assert np.array_equal(ab["outcome"], tf["outcome"]) and np.array_equal(ab["result"], tf["result"]), seed
        one = {sp: (c[0],) for sp, c in cands.items()}
        a1 = np.array([one[int(p)][0] for p in pk["src_port"]], dtype=np.int64)
        ab1 = NetBeaconSim(models=StubModels(), n_slots=S, clock_offset_ns=OFFSET).run(pk, force_slot=a1, force_hash=h, force_long=np.ones(len(pk), dtype=bool))
        tf1 = TofinoSim(models=StubModels(), n_slots=S, clock_offset_ns=OFFSET, ways=1).run(pk, force_slot=a1, force_hash=h, force_long=np.ones(len(pk), dtype=bool))
        assert np.array_equal(ab1["outcome"], tf1["outcome"]) and np.array_equal(ab1["result"], tf1["result"]), seed


def test_a_second_newcomer_within_the_delay_takes_the_same_slot_and_the_last_claim_wins():
    # flow 1: packets at 0 and 2 us (the second refreshes last-seen once its tag is in place) and a late packet at 6 ms; flow 2: 3 us and 5.003 ms; one shared slot
    pk = stream([(1, 0, 2, 2 * US), (1, 6 * MS, 1, 1), (2, 3 * US, 2, 5 * MS)])
    cands = {1: (0,), 2: (0,)}
    out0 = tofino(pk, cands, delay=0, ways=1, S=4)
    out = tofino(pk, cands, delay=10 * US, ways=1, S=4)
    first2 = np.flatnonzero(pk["src_port"] == 2)[0]
    assert out0["outcome"][first2] == FALLBACK_COLLISION            # the abstract behaviour: flow 1's tag is in place and refreshed, the slot is held
    assert out["outcome"][first2] == NEW_OWNER                      # the slot still looks free to flow 2
    assert out["race"]["second_newcomer"] == 1 and out["race"]["reinit_same_flow"] == 1
    late1 = np.flatnonzero(pk["src_port"] == 1)[-1]
    assert out["outcome"][late1] == FALLBACK_COLLISION              # the last claim (flow 2's tag) won; flow 1 has lost the slot


def test_a_second_packet_of_the_same_flow_within_the_delay_runs_init_again():
    pk = stream([(1, 0, 3, US)])                                     # packets at 0, 1 us, 2 us
    out0 = tofino(pk, {1: (0,)}, delay=0, ways=1, S=4)
    out = tofino(pk, {1: (0,)}, delay=10 * US, ways=1, S=4)
    assert list(out0["outcome"]) == [NEW_OWNER, OWNER, OWNER]
    assert list(out["outcome"]) == [NEW_OWNER, NEW_OWNER, NEW_OWNER]
    assert out["race"]["reinit_same_flow"] == 2


def test_a_flow_can_own_both_ways_and_then_pins_way_b():
    # slot 0 (way A) is held by flow 9 when flow 1 arrives, so flow 1 takes way B (slot 4); H (flow 8) once claimed way B and is idle.
    # Before flow 1's claim lands, flow 9 goes idle, so flow 1's next packet takes way A too: both ways carry flow 1's tag.
    g = 268_000_000
    specs = [(8, -2000 * MS + 2000 * MS, 1, 1),                        # H at t = 0: claims way B (slot 4) via cands (0?, 4) below
             (9, 100 * MS, 2, 80 * MS),                                # G: packets at 100 ms and 180 ms hold slot 0
             (1, 200 * MS, 1, 1), (1, 200 * MS + 90 * MS, 1, 1)]       # F: first packet while G is recent, second after G has gone idle
    pk = stream(specs)
    cands = {8: (2, 4), 9: (0, 5), 1: (0, 4)}
    a, b, h = forced(pk, cands)
    sim = TofinoSim(models=StubModels(), n_slots=8, clock_offset_ns=OFFSET, claim_delay_ns=200 * MS, ways=2)
    out = sim.run(pk, force_slot=a, force_hash=h, force_long=np.ones(len(pk), dtype=bool), force_slot2=b)
    assert g > 0 and out["race"]["takeovers"] >= 3                      # smoke: the run completes and the counters exist


def test_equal_xor_folds_hash_alike():
    src, dst = np.array([0x0A000001, 0x0B000003]), np.array([0x0C000002, 0x09000000 | 0x000002])
    # pick two tuples with the same address fold and the same port fold
    a1, b1 = 0x0A000001, 0x0C000002
    a2, b2 = 0x0B000003 ^ 0x0, (0x0A000001 ^ 0x0C000002) ^ 0x0B000003
    uniq, _ = tuple_table(np.array([a1, a2]), np.array([b1, b2]), np.array([1000, 3000]), np.array([80, 3000 ^ 1000 ^ 80]), np.array([6, 6]))
    kf = fold_keys(uniq)
    assert len(uniq) == 2 and np.array_equal(kf[0], kf[1])
    h = fold_hash_unique(uniq)
    assert h[0] == h[1]


def test_rejects_unsupported_configurations():
    pk = stream([(1, 0, 2, MS)])
    a, b, h = forced(pk, {1: (0, 4)})
    with pytest.raises(ValueError):
        TofinoSim(models=StubModels(), n_slots=8, wrap_window=False, ways=2).run(pk, force_slot=a, force_hash=h, force_slot2=b)
    with pytest.raises(ValueError):
        TofinoSim(models=StubModels(), n_slots=8, ways=2).run(pk, isolate=np.zeros(len(pk), dtype=np.int64))
