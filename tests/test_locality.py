import numpy as np
import pytest

from mvm.locality import coverage, normalized_entropy, reuse_distance, windowed_js, working_set

SEQ = np.array([0, 0, 0, 1, 1, 2])  # leaf 0: 1/2, leaf 1: 1/3, leaf 2: 1/6


def test_top_k_coverage_on_worked_example():
    assert coverage(SEQ, 1) == pytest.approx(1 / 2)
    assert coverage(SEQ, 2) == pytest.approx(5 / 6)
    assert coverage(SEQ, 3) == pytest.approx(1.0)
    assert coverage(SEQ, 10) == pytest.approx(1.0)


def test_working_set_is_smallest_k_reaching_quantile():
    assert working_set(SEQ, 0.5) == 1
    assert working_set(SEQ, 0.8) == 2
    assert working_set(SEQ, 0.9) == 3


def test_normalized_entropy_counts_unvisited_leaves_of_the_tree():
    assert normalized_entropy(np.array([0, 1, 2, 3]), n_leaves=4) == pytest.approx(1.0)
    assert normalized_entropy(np.array([5, 5, 5]), n_leaves=4) == pytest.approx(0.0)
    assert normalized_entropy(np.array([0, 0, 1, 1]), n_leaves=4) == pytest.approx(0.5)


def test_reuse_distance_counts_distinct_leaves_between_accesses():
    seq = np.array([4, 4, 17, 4, 2, 17])
    assert reuse_distance(seq).tolist() == [-1, 0, -1, 1, -1, 2]


def test_windowed_js_between_consecutive_windows():
    assert windowed_js(np.array([0, 0, 1, 1]), window=2).tolist() == pytest.approx([1.0])
    assert windowed_js(np.array([0, 1, 0, 1, 0, 1]), window=2).tolist() == pytest.approx([0.0, 0.0])
