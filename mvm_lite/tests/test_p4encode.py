import numpy as np
from sklearn.datasets import make_classification
from sklearn.tree import DecisionTreeClassifier

from mvm.leaves import extract_leaf_boxes
from mvm.p4encode import box_key_ranges, f32_key


def test_key_preserves_float32_order_including_negatives_and_signed_zero():
    vals = np.array([-3e9, -1.5, -1.0, -0.0, 0.0, 1e-30, 0.5, 1.0, 7.0, 3e9], dtype=np.float64)
    keys = f32_key(vals)
    assert keys.dtype == np.uint32
    assert np.all(np.diff(keys.astype(np.int64)) >= 0)
    assert keys[3] == keys[4]  # -0.0 and +0.0 compare equal in the tree, so they share a key


def _tree_and_data(seed=0):
    rng = np.random.default_rng(seed)
    X, y = make_classification(n_samples=6000, n_features=6, n_informative=4, random_state=seed)
    X[:, 0] = np.round(np.abs(X[:, 0]) * 1e7)          # large integer counters (float32 loses precision)
    X[:, 1] = rng.integers(-1, 4, len(X))              # small categorical codes incl. -1
    tree = DecisionTreeClassifier(max_depth=None, random_state=seed).fit(X[:4000], y[:4000])
    return tree, X[4000:]


def test_key_range_lookup_reproduces_tree_apply_exactly():
    tree, X = _tree_and_data()
    keys = f32_key(X)
    got = np.full(len(X), -1)
    for box in extract_leaf_boxes(tree):
        lo, hi = box_key_ranges(box)
        inside = np.all((keys >= lo) & (keys <= hi), axis=1)
        assert not np.any(got[inside] != -1), "leaf key ranges overlap"
        got[inside] = box.leaf_id
    assert np.array_equal(got, tree.apply(X))


def test_key_ranges_are_exact_at_split_thresholds():
    tree, X = _tree_and_data(seed=1)
    t = tree.tree_
    X_edge = np.repeat(X[:1], 3 * t.node_count, axis=0)
    for i, (f, thr) in enumerate(zip(t.feature, t.threshold)):
        if f >= 0:
            f32 = np.float32(thr)
            for j, v in enumerate((np.nextafter(f32, np.float32(-np.inf)), f32, np.nextafter(f32, np.float32(np.inf)))):
                X_edge[3 * i + j, f] = v
    keys = f32_key(X_edge)
    got = np.full(len(X_edge), -1)
    for box in extract_leaf_boxes(tree):
        lo, hi = box_key_ranges(box)
        got[np.all((keys >= lo) & (keys <= hi), axis=1)] = box.leaf_id
    assert np.array_equal(got, tree.apply(X_edge))
