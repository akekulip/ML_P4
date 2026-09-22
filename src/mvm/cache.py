"""Page-replacement policies for a K-leaf data-plane cache, simulated over a leaf-id stream.

Demand policies (LRU, LFU, DecayedLFU) start cold and install every missed leaf, evicting one
resident leaf when full. StaticTopK is preloaded once and never changes. WindowOracle reloads
each window's true top-K (the brief's "oracle"; not deployable, and not a strict upper bound
because demand policies can adapt inside a window). Belady (MIN with bypass) is the offline
optimum on hit count and bounds every cold demand policy.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = ["SimResult", "simulate", "LRU", "LFU", "DecayedLFU", "StaticTopK", "WindowOracle", "Belady"]


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

    def access(self, t, leaf):
        prev = self._current(leaf, t) if leaf in self.score else 0.0
        hit = leaf in self.resident
        if not hit:
            if len(self.resident) >= self.k:
                victim = min(self.resident, key=lambda j: (self._current(j, t), self.last[j]))
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
