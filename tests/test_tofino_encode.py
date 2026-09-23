import numpy as np
from sklearn.datasets import make_classification
from sklearn.tree import DecisionTreeClassifier

from mvm.leaves import extract_leaf_boxes
from mvm.p4encode import f32_key
from mvm.tofino_encode import TofinoEncoding


def _tree_and_data(seed=0, depth=10):
    rng = np.random.default_rng(seed)
    X, y = make_classification(n_samples=8000, n_features=10, n_informative=6, random_state=seed)
    X[:, 0] = np.round(np.abs(X[:, 0]) * 3e7)     # large counters: 20-bit buckets straddle thresholds
    X[:, 1] = rng.integers(-1, 5, len(X))          # small codes incl. -1
    tree = DecisionTreeClassifier(max_depth=depth, random_state=seed).fit(X[:5000], y[:5000])
    return tree, X[5000:]


def _switch_leaf(enc, X):
    """Emulate the switch: per-feature fine table first, else coarse table -> thermometer codes;
    then the ternary leaf table (one entry per leaf)."""
    keys = f32_key(X)
    codes = enc.codes_like_switch(keys)
    leaf = np.full(len(X), -1)
    for e in enc.leaf_entries():
        m = np.all((codes & e["mask"]) == e["value"], axis=1)
        assert not np.any(leaf[m] != -1), "two leaf entries matched one sample"
        leaf[m] = e["leaf_id"]
    return leaf


def test_switch_emulation_equals_tree_apply_exactly():
    tree, X = _tree_and_data()
    enc = TofinoEncoding(tree)
    assert np.array_equal(_switch_leaf(enc, X), tree.apply(X))


def test_exact_at_every_threshold_even_inside_straddled_buckets():
    tree, X = _tree_and_data(seed=1)
    t = tree.tree_
    rows = []
    for f, thr in zip(t.feature, t.threshold):
        if f >= 0:
            f32 = np.float32(thr)
            for v in (np.nextafter(f32, np.float32(-np.inf)), f32, np.nextafter(f32, np.float32(np.inf))):
                r = X[0].copy(); r[f] = v; rows.append(r)
    Xe = np.array(rows)
    enc = TofinoEncoding(tree)
    assert enc.n_fine_entries() > 0, "test data should exercise the fine (straddled-bucket) tables"
    assert np.array_equal(_switch_leaf(enc, Xe), tree.apply(Xe))


def test_one_ternary_entry_per_leaf_and_key_width_is_threshold_count():
    tree, _ = _tree_and_data()
    enc = TofinoEncoding(tree)
    assert len(enc.leaf_entries()) == tree.get_n_leaves()
    n_thr = sum(len(np.unique(tree.tree_.threshold[tree.tree_.feature == f])) for f in range(tree.n_features_in_))
    assert enc.key_width() == n_thr
