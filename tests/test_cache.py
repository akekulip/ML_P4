import numpy as np
import pytest

from mvm.cache import LFU, LRU, Belady, DecayedLFU, StaticTopK, WindowOracle, simulate


def hits(policy, seq, k):
    return simulate(policy, np.array(seq), k).hits.tolist()


def test_lru_trace():
    r = simulate(LRU(), np.array([1, 2, 1, 3, 2, 1]), k=2)
    assert r.hits.tolist() == [False, False, True, False, False, False]
    assert (r.inserts, r.evictions) == (5, 3)


def test_lfu_keeps_frequent_leaf_where_lru_drops_it():
    assert hits(LFU(), [1, 2, 1, 3, 2, 1], 2) == [False, False, True, False, False, True]


def test_decayed_lfu_forgets_old_popularity_lfu_does_not():
    seq = [1, 1, 1, 2, 3, 2, 3]
    assert hits(DecayedLFU(gamma=0.1), seq, 2) == [False, True, True, False, False, True, True]
    assert hits(LFU(), seq, 2) == [False, True, True, False, False, False, False]


def test_decayed_lfu_with_gamma_one_is_lfu():
    rng = np.random.default_rng(1)
    seq = rng.zipf(1.5, 3000) % 50
    assert simulate(DecayedLFU(gamma=1.0), seq, 8).hits.tolist() == simulate(LFU(), seq, 8).hits.tolist()


def test_static_top_k_never_changes():
    r = simulate(StaticTopK(resident=[1, 2]), np.array([1, 2, 3, 1, 3]), k=2)
    assert r.hits.tolist() == [True, True, False, True, False]
    assert (r.inserts, r.evictions) == (2, 0)


def test_window_oracle_loads_each_windows_top_k():
    r = simulate(WindowOracle(window=3), np.array([1, 1, 2, 3, 3, 3]), k=1)
    assert r.hits.tolist() == [True, True, False, True, True, True]
    assert (r.inserts, r.evictions) == (2, 1)


def test_belady_may_bypass_the_incoming_leaf():
    assert hits(Belady(), [1, 2, 1, 2], 1) == [False, False, True, False]
    assert hits(LRU(), [1, 2, 1, 2], 1) == [False, False, False, False]


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_belady_bounds_every_cold_demand_policy(seed):
    rng = np.random.default_rng(seed)
    seq = rng.zipf(1.3, 5000) % 200
    best = simulate(Belady(), seq, 16).hits.sum()
    for p in (LRU(), LFU(), DecayedLFU(gamma=0.99)):
        assert best >= simulate(p, seq, 16).hits.sum()


def test_resident_set_never_exceeds_k():
    rng = np.random.default_rng(3)
    seq = rng.integers(0, 100, 2000)
    for p in (LRU(), LFU(), DecayedLFU(gamma=0.9), Belady(), WindowOracle(window=100)):
        r = simulate(p, seq, 10)
        assert r.max_resident <= 10
        assert r.inserts - r.evictions <= 10


@pytest.mark.parametrize("k", [1, 3, 8, 32])
def test_lru_hits_exactly_when_reuse_distance_below_k(k):
    from mvm.locality import reuse_distance

    seq = np.random.default_rng(k).zipf(1.4, 4000) % 90
    rd = reuse_distance(seq)
    assert simulate(LRU(), seq, k).hits.tolist() == ((rd >= 0) & (rd < k)).tolist()


FAST_CASES = [("lfu", LFU, {}), ("dlfu", DecayedLFU, {"gamma": 0.9}), ("dlfu", DecayedLFU, {"gamma": 0.999}),
              ("belady", Belady, {}), ("lru", LRU, {})]


@pytest.mark.parametrize("kind,cls,kw", FAST_CASES)
@pytest.mark.parametrize("k", [1, 4, 16])
def test_fast_simulator_matches_reference_policy(kind, cls, kw, k):
    from mvm.cache import simulate_fast

    seq = np.random.default_rng(k * 31 + len(kind)).zipf(1.3, 6000) % 120
    ref = simulate(cls(**kw), seq, k)
    fast = simulate_fast(kind, seq, k, **kw)
    assert fast.hits.tolist() == ref.hits.tolist()
    assert (fast.inserts, fast.evictions) == (ref.inserts, ref.evictions)
    assert fast.max_resident <= k


@pytest.mark.parametrize("fast", [False, True])
def test_decayed_lfu_keeps_true_order_after_long_idle_gap(fast):
    # A: 50 accesses, then B: 1 access, then C hits for 100k flows (gamma**100k underflows to 0.0).
    # Decayed scores: A ~ 39.5*g^(t-49) > B = g^(t-50), so the new leaf D must evict B, not A.
    from mvm.cache import simulate_fast

    seq = np.array([0] * 50 + [1] + [2] * 100_000 + [3, 0, 1])
    r = simulate_fast("dlfu", seq, 3, gamma=0.99) if fast else simulate(DecayedLFU(gamma=0.99), seq, 3)
    assert r.hits[-2:].tolist() == [True, False]  # A still resident, B was evicted
