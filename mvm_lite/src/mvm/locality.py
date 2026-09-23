"""Inference-locality metrics over a chronological sequence of leaf ids."""

from __future__ import annotations

import numba
import numpy as np

__all__ = ["coverage", "working_set", "normalized_entropy", "reuse_distance", "windowed_js"]


def _sorted_probs(leaf_ids: np.ndarray) -> np.ndarray:
    _, counts = np.unique(leaf_ids, return_counts=True)
    return np.sort(counts)[::-1] / counts.sum()


def coverage(leaf_ids: np.ndarray, k: int) -> float:
    """C(K): fraction of inferences served by the K most frequent leaves."""
    return float(_sorted_probs(leaf_ids)[:k].sum())


def working_set(leaf_ids: np.ndarray, q: float) -> int:
    """W_q: smallest number of leaves whose combined frequency reaches q."""
    cum = np.cumsum(_sorted_probs(leaf_ids))
    return int(np.searchsorted(cum, q - 1e-12) + 1)


def normalized_entropy(leaf_ids: np.ndarray, n_leaves: int) -> float:
    """H(L) / log(n_leaves); n_leaves is the tree's total leaf count, visited or not."""
    if n_leaves <= 1:
        return 0.0
    p = _sorted_probs(leaf_ids)
    return float(-(p * np.log(p)).sum() / np.log(n_leaves))


def reuse_distance(leaf_ids: np.ndarray) -> np.ndarray:
    """Distinct leaves seen strictly between consecutive accesses to the same leaf; -1 = first access.

    Under LRU with capacity K, an access hits iff 0 <= reuse distance < K, so one pass gives the
    LRU hit rate for every K. Fenwick tree over positions holding a 1 at each leaf's most recent
    access: O(n log n), compiled with numba.
    """
    ids, dense = np.unique(np.asarray(leaf_ids), return_inverse=True)
    return _reuse_distance_dense(dense.astype(np.int64), len(ids))


@numba.njit(cache=True)
def _reuse_distance_dense(seq, n_ids):
    n = len(seq)
    tree = np.zeros(n + 1, dtype=np.int64)
    last = np.full(n_ids, -1, dtype=np.int64)
    out = np.full(n, -1, dtype=np.int64)
    for i in range(n):
        leaf = seq[i]
        p = last[leaf]
        if p >= 0:
            s = 0  # prefix(i) - prefix(p + 1)
            j = i
            while j > 0:
                s += tree[j]
                j -= j & -j
            j = p + 1
            while j > 0:
                s -= tree[j]
                j -= j & -j
            out[i] = s
            j = p + 1
            while j <= n:
                tree[j] -= 1
                j += j & -j
        j = i + 1
        while j <= n:
            tree[j] += 1
            j += j & -j
        last[leaf] = i
    return out


def windowed_js(leaf_ids: np.ndarray, window: int) -> np.ndarray:
    """Jensen-Shannon divergence (base 2, in [0, 1]) between leaf distributions of consecutive windows."""
    ids, inverse = np.unique(leaf_ids, return_inverse=True)
    n_win = len(leaf_ids) // window
    dists = np.zeros((n_win, len(ids)))
    for w in range(n_win):
        dists[w] = np.bincount(inverse[w * window:(w + 1) * window], minlength=len(ids)) / window
    return np.array([_js(dists[w - 1], dists[w]) for w in range(1, n_win)])


def _js(p: np.ndarray, q: np.ndarray) -> float:
    m = (p + q) / 2

    def kl(a: np.ndarray, b: np.ndarray) -> float:
        nz = a > 0
        return float((a[nz] * np.log2(a[nz] / b[nz])).sum())

    return 0.5 * kl(p, m) + 0.5 * kl(q, m)
