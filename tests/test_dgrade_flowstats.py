"""The fast per-flow aggregation must equal a plain pandas reference."""

import numpy as np
import pandas as pd

from dgrade.flowstats import FlowIndex, downgraded_flows


def _reference(oc, f):
    df = pd.DataFrame({"oc": oc, "f": f})
    coll = df.groupby("f").oc.apply(lambda x: bool((x == 3).any()))
    out = {}
    for k, g in df.groupby("f", sort=True):
        o = g.oc.to_numpy()
        owned = np.isin(o, (1, 2))
        seen = np.cumsum(owned) - owned
        out[k] = bool(coll[k]) or bool((((o == 2) | (o == 4)) & (seen > 0)).any())
    return np.array([out[k] for k in sorted(out)])


def test_downgraded_flows_matches_pandas_reference():
    rng = np.random.default_rng(0)
    n = 20_000
    f = rng.integers(0, 700, n)
    oc = rng.choice([0, 1, 2, 3, 4, 6], size=n, p=[0.2, 0.4, 0.05, 0.05, 0.25, 0.05]).astype(np.int8)
    idx = FlowIndex(f)
    assert np.array_equal(downgraded_flows(oc, idx), _reference(oc, f))


def test_flow_index_handles_noncontiguous_ids_and_order():
    f = np.array([7, 3, 7, 3, 9, 7])
    idx = FlowIndex(f)
    assert idx.n_flows == 3
    assert np.array_equal(idx.per_flow_sum(np.ones(6)), [2, 3, 1])      # flows 3, 7, 9
    oc = np.array([2, 2, 3, 2, 1, 2], dtype=np.int8)
    # flow 7: packets 0 (NEW_OWNER), 2 (collision) -> downgraded; flow 3: 1, 3 (NEW_OWNER twice) -> lost slot
    assert np.array_equal(downgraded_flows(oc, idx), [True, True, False])


def test_slot_lost_then_predicted_short_counts_as_downgraded():
    # owner (2), owner (1), then the slot is lost and later packets are predicted short (4): downgraded
    f = np.array([1, 1, 1, 1, 2, 2])
    oc = np.array([2, 1, 4, 4, 2, 1], dtype=np.int8)
    idx = FlowIndex(f)
    assert np.array_equal(downgraded_flows(oc, idx), [True, False])


def test_predicted_short_from_the_start_is_not_downgraded():
    f = np.array([1, 1, 1])
    oc = np.array([4, 4, 4], dtype=np.int8)
    assert not downgraded_flows(oc, FlowIndex(f)).any()


def test_empty_slot_refusal_is_not_downgraded():
    f = np.array([1, 1, 1])
    oc = np.array([6, 6, 2], dtype=np.int8)      # refused an empty slot, then took it: not contention
    assert not downgraded_flows(oc, FlowIndex(f)).any()
