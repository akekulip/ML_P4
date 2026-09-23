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
        out[k] = bool(coll[k]) or bool(((o == 2) & (seen > 0)).any())
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
