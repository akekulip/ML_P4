"""Page-replacement policies for a K-leaf data-plane cache, simulated over a leaf-id stream.

Demand policies (LRU, LFU, DecayedLFU) start cold and install every missed leaf, evicting one
resident leaf when full. StaticTopK is preloaded once and never changes. WindowOracle reloads
each window's true top-K (the brief's "oracle"; not deployable, and not a strict upper bound
because demand policies can adapt inside a window). Belady (MIN with bypass) is the offline
optimum on hit count and bounds every cold demand policy.
"""

from __future__ import annotations

from dataclasses import dataclass

import numba
import numpy as np

__all__ = ["SimResult", "simulate", "simulate_fast", "LRU", "LFU", "DecayedLFU", "StaticTopK", "WindowOracle", "Belady"]


@dataclass(frozen=True)
class SimResult:
    hits: np.ndarray  # bool per request
    inserts: int
    evictions: int
    max_resident: int

    @property
    def hit_rate(self) -> float:
        return float(self.hits.mean()) if len(self.hits) else 0.0

    @property
    def churn(self) -> float:
        """(insertions + evictions) / requests."""
        return (self.inserts + self.evictions) / max(len(self.hits), 1)


class _Policy:
    """Policies keep `resident` (a set-like of leaf ids) and count inserts/evictions."""

    def reset(self, k: int, seq: np.ndarray) -> None:
        self.k, self.inserts, self.evictions = k, 0, 0

    def access(self, t: int, leaf: int) -> bool:
        raise NotImplementedError

    @property
    def n_resident(self) -> int:
        return len(self.resident)


class LRU(_Policy):
    def reset(self, k, seq):
        super().reset(k, seq)
        self.resident: dict[int, None] = {}  # insertion order = recency order

    def access(self, t, leaf):
        if leaf in self.resident:
            del self.resident[leaf]
            self.resident[leaf] = None
            return True
        if len(self.resident) >= self.k:
            del self.resident[next(iter(self.resident))]
            self.evictions += 1
        self.resident[leaf] = None
        self.inserts += 1
        return False


class DecayedLFU(_Policy):
    """Score S_i(t) = gamma * S_i(t-1) + 1[L_t = i], kept lazily; evict the lowest current score
    (ties: least recently accessed). Scores persist for non-resident leaves. gamma=1 is LFU."""

    def __init__(self, gamma: float):
        self.gamma = gamma

    def reset(self, k, seq):
        super().reset(k, seq)
        self.resident: set[int] = set()
        self.score: dict[int, float] = {}
        self.last: dict[int, int] = {}

    def _current(self, leaf: int, t: int) -> float:
        return self.score[leaf] * self.gamma ** (t - self.last[leaf])

    def _evict_key(self, leaf: int) -> float:
        # S * gamma**(t - last) = gamma**t * exp(log S - last * ln gamma): the common factor gamma**t
        # drops out, so this time-free key orders residents exactly and never underflows
        # (gamma**n reaches 0.0 after ~7e4 steps at gamma=0.99; code review 2026-09-22).
        return float(np.log(self.score[leaf]) - self.last[leaf] * np.log(self.gamma))

    def access(self, t, leaf):
        prev = self._current(leaf, t) if leaf in self.score else 0.0
        hit = leaf in self.resident
        if not hit:
            if len(self.resident) >= self.k:
                victim = min(self.resident, key=lambda j: (self._evict_key(j), self.last[j]))
                self.resident.remove(victim)
                self.evictions += 1
            self.resident.add(leaf)
            self.inserts += 1
        self.score[leaf], self.last[leaf] = prev + 1.0, t
        return hit


class LFU(DecayedLFU):
    """Perfect LFU (frequency over the whole history), ties broken by recency."""

    def __init__(self):
        super().__init__(gamma=1.0)


class StaticTopK(_Policy):
    def __init__(self, resident):
        self.initial = list(resident)

    def reset(self, k, seq):
        super().reset(k, seq)
        self.resident = set(self.initial[:k])
        self.inserts = len(self.resident)

    def access(self, t, leaf):
        return leaf in self.resident


class WindowOracle(_Policy):
    def __init__(self, window: int):
        self.window = window

    def reset(self, k, seq):
        super().reset(k, seq)
        self.seq = seq
        self.resident: set[int] = set()

    def access(self, t, leaf):
        if t % self.window == 0:
            ids, counts = np.unique(self.seq[t:t + self.window], return_counts=True)
            order = np.lexsort((ids, -counts))  # count desc, then leaf id asc
            new = set(ids[order[: self.k]].tolist())
            self.inserts += len(new - self.resident)
            self.evictions += len(self.resident - new)
            self.resident = new
        return leaf in self.resident


class Belady(_Policy):
    def reset(self, k, seq):
        super().reset(k, seq)
        n = len(seq)
        self.next_use = np.full(n, np.iinfo(np.int64).max, dtype=np.int64)
        seen: dict[int, int] = {}
        for i in range(n - 1, -1, -1):
            leaf = int(seq[i])
            if leaf in seen:
                self.next_use[i] = seen[leaf]
            seen[leaf] = i
        self.resident: dict[int, int] = {}  # leaf -> next use

    def access(self, t, leaf):
        nxt = int(self.next_use[t])
        if leaf in self.resident:
            self.resident[leaf] = nxt
            return True
        if len(self.resident) >= self.k:
            victim = max(self.resident, key=self.resident.__getitem__)
            if self.resident[victim] <= nxt:
                return False  # the incoming leaf is needed furthest in the future: bypass
            del self.resident[victim]
            self.evictions += 1
        self.resident[leaf] = nxt
        self.inserts += 1
        return False


def simulate(policy: _Policy, leaf_ids: np.ndarray, k: int) -> SimResult:
    """Replay a leaf-id stream through a K-entry cache under `policy`."""
    policy.reset(k, leaf_ids)
    hits = np.zeros(len(leaf_ids), dtype=bool)
    max_resident = policy.n_resident
    for t, leaf in enumerate(leaf_ids.tolist()):
        hits[t] = policy.access(t, leaf)
        max_resident = max(max_resident, policy.n_resident)
    return SimResult(hits, policy.inserts, policy.evictions, max_resident)


# ---------------------------------------------------------------------------------------------
# Fast simulators for the W4 sweep (numba). Each reproduces the reference policy above exactly
# (hits, inserts, evictions); tests/test_cache.py checks this on random streams.
# ---------------------------------------------------------------------------------------------

@numba.njit(cache=True)
def _decayed_lfu_kernel(seq, n_ids, k, gamma):
    n = len(seq)
    lng = np.log(gamma)
    hits = np.zeros(n, dtype=np.bool_)
    score = np.zeros(n_ids)
    last = np.full(n_ids, -1, dtype=np.int64)
    resident = np.full(k, -1, dtype=np.int64)
    is_res = np.zeros(n_ids, dtype=np.bool_)
    n_res = inserts = evictions = 0
    for t in range(n):
        leaf = seq[t]
        prev = score[leaf] * gamma ** (t - last[leaf]) if last[leaf] >= 0 else 0.0
        if is_res[leaf]:
            hits[t] = True
        else:
            if n_res >= k:
                best, best_s, best_l = -1, np.inf, np.iinfo(np.int64).max
                for j in range(k):
                    r = resident[j]
                    s = np.log(score[r]) - last[r] * lng  # time-free eviction key, see DecayedLFU
                    if s < best_s or (s == best_s and last[r] < best_l):
                        best, best_s, best_l = j, s, last[r]
                is_res[resident[best]] = False
                resident[best] = leaf
                evictions += 1
            else:
                resident[n_res] = leaf
                n_res += 1
            is_res[leaf] = True
            inserts += 1
        score[leaf] = prev + 1.0
        last[leaf] = t
    return hits, inserts, evictions, n_res


@numba.njit(cache=True)
def _belady_kernel(seq, next_use, n_ids, k):
    n = len(seq)
    hits = np.zeros(n, dtype=np.bool_)
    nxt_of = np.zeros(n_ids, dtype=np.int64)
    resident = np.full(k, -1, dtype=np.int64)
    is_res = np.zeros(n_ids, dtype=np.bool_)
    n_res = inserts = evictions = 0
    for t in range(n):
        leaf, nxt = seq[t], next_use[t]
        if is_res[leaf]:
            hits[t] = True
            nxt_of[leaf] = nxt
            continue
        if n_res >= k:
            best, best_n = -1, -1
            for j in range(k):
                if nxt_of[resident[j]] > best_n:
                    best, best_n = j, nxt_of[resident[j]]
            if best_n <= nxt:
                continue  # the incoming leaf is needed furthest in the future: bypass
            is_res[resident[best]] = False
            resident[best] = leaf
            evictions += 1
        else:
            resident[n_res] = leaf
            n_res += 1
        is_res[leaf] = True
        nxt_of[leaf] = nxt
        inserts += 1
    return hits, inserts, evictions, n_res


def simulate_fast(kind: str, leaf_ids: np.ndarray, k: int, gamma: float = 1.0) -> SimResult:
    """Fast equivalent of simulate() for kind in {lru, lfu, dlfu, belady}."""
    ids, dense = np.unique(np.asarray(leaf_ids), return_inverse=True)
    dense = dense.astype(np.int64)
    if kind == "lru":  # hit iff reuse distance < k (proven equivalent in tests)
        from mvm.locality import reuse_distance

        rd = reuse_distance(dense)
        hits = (rd >= 0) & (rd < k)
        inserts = int((~hits).sum())
        n_res = min(k, len(ids))
        return SimResult(hits, inserts, inserts - n_res, n_res)
    if kind in ("lfu", "dlfu"):
        h, ins, ev, n_res = _decayed_lfu_kernel(dense, len(ids), k, 1.0 if kind == "lfu" else float(gamma))
        return SimResult(h, int(ins), int(ev), int(n_res))
    if kind == "belady":
        n = len(dense)
        next_use = np.full(n, np.iinfo(np.int64).max, dtype=np.int64)
        last_seen = np.full(len(ids), -1, dtype=np.int64)
        _fill_next_use(dense, next_use, last_seen)
        h, ins, ev, n_res = _belady_kernel(dense, next_use, len(ids), k)
        return SimResult(h, int(ins), int(ev), int(n_res))
    raise ValueError(kind)


@numba.njit(cache=True)
def _fill_next_use(seq, next_use, last_seen):
    for i in range(len(seq) - 1, -1, -1):
        if last_seen[seq[i]] >= 0:
            next_use[i] = last_seen[seq[i]]
        last_seen[seq[i]] = i
