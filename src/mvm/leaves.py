"""Decision-tree leaves as axis-aligned boxes: one box = one MVM page.

A sample reaches leaf L iff, for every feature f, lo[f] < x[f] <= hi[f], where the bounds come
from the split thresholds on L's root-to-leaf path (sklearn sends x <= threshold left). Leaves of
one tree are disjoint and cover the feature space, so any subset can be resident with no
priorities or dependency closure.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.tree import DecisionTreeClassifier

__all__ = ["LeafBox", "extract_leaf_boxes", "lookup"]


@dataclass(frozen=True)
class LeafBox:
    leaf_id: int  # sklearn node index, same id space as tree.apply()
    lo: np.ndarray  # exclusive lower bound per feature
    hi: np.ndarray  # inclusive upper bound per feature
    klass: int  # predicted class label at this leaf

    def contains(self, X: np.ndarray) -> np.ndarray:
        """Boolean mask of rows of X that fall inside this box."""
        Xf = _as_tree_input(X)
        return np.all((Xf > self.lo) & (Xf <= self.hi), axis=1)


def _as_tree_input(X: np.ndarray) -> np.ndarray:
    # sklearn compares float32-cast inputs against float64 thresholds; mirror that exactly.
    return np.asarray(X, dtype=np.float32).astype(np.float64)


def extract_leaf_boxes(tree: DecisionTreeClassifier) -> list[LeafBox]:
    """Return one LeafBox per leaf of a fitted tree, in node-index order."""
    t = tree.tree_
    n_features = tree.n_features_in_
    boxes: list[LeafBox] = []
    stack = [(0, np.full(n_features, -np.inf), np.full(n_features, np.inf))]
    while stack:
        node, lo, hi = stack.pop()
        left, right = t.children_left[node], t.children_right[node]
        if left == -1:
            klass = tree.classes_[int(np.argmax(t.value[node][0]))]
            boxes.append(LeafBox(int(node), lo, hi, klass))
            continue
        f, thr = t.feature[node], t.threshold[node]
        hi_left = hi.copy()
        hi_left[f] = min(hi[f], thr)
        lo_right = lo.copy()
        lo_right[f] = max(lo[f], thr)
        stack.append((left, lo, hi_left))
        stack.append((right, lo_right, hi))
    return sorted(boxes, key=lambda b: b.leaf_id)


def lookup(boxes: list[LeafBox], X: np.ndarray) -> np.ndarray:
    """Leaf id for each row of X among the given boxes; -1 where no box matches (a miss)."""
    out = np.full(len(X), -1, dtype=np.int64)
    for b in boxes:
        out[b.contains(X)] = b.leaf_id
    return out
