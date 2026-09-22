import numpy as np
from sklearn.datasets import make_classification
from sklearn.tree import DecisionTreeClassifier

from mvm.leaves import extract_leaf_boxes, lookup


def _tree_and_data(depth=6, seed=0):
    X, y = make_classification(n_samples=4000, n_features=6, n_informative=4, random_state=seed)
    tree = DecisionTreeClassifier(max_depth=depth, random_state=seed).fit(X[:3000], y[:3000])
    return tree, X[3000:]


def test_lookup_over_all_leaf_boxes_matches_tree_apply():
    tree, X = _tree_and_data()
    boxes = extract_leaf_boxes(tree)
    assert np.array_equal(lookup(boxes, X), tree.apply(X))


def test_one_box_per_leaf_and_box_class_matches_tree_predict():
    tree, X = _tree_and_data()
    boxes = extract_leaf_boxes(tree)
    assert len(boxes) == tree.get_n_leaves()
    klass = {b.leaf_id: b.klass for b in boxes}
    predicted = np.array([klass[i] for i in lookup(boxes, X)])
    assert np.array_equal(predicted, tree.predict(X))


def test_every_sample_falls_in_exactly_one_box():
    tree, X = _tree_and_data(depth=None)
    boxes = extract_leaf_boxes(tree)
    counts = sum(b.contains(X).astype(int) for b in boxes)
    assert np.all(counts == 1)


def test_samples_on_a_split_threshold_follow_sklearn_left_branch():
    # sklearn sends x <= threshold left; a sample exactly on a threshold must land where apply() puts it
    tree, X = _tree_and_data(depth=3)
    f, t = tree.tree_.feature[0], tree.tree_.threshold[0]
    X_edge = X.copy()
    X_edge[:, f] = t
    assert np.array_equal(lookup(extract_leaf_boxes(tree), X_edge), tree.apply(X_edge))


def test_lookup_on_a_subset_of_boxes_returns_minus_one_for_misses():
    tree, X = _tree_and_data()
    boxes = extract_leaf_boxes(tree)
    resident = boxes[:2]
    got = lookup(resident, X)
    true = tree.apply(X)
    resident_ids = {b.leaf_id for b in resident}
    hit = np.isin(true, list(resident_ids))
    assert np.array_equal(got[hit], true[hit])
    assert np.all(got[~hit] == -1)
