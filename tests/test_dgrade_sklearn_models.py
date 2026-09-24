"""Retrained NetBeacon-style models behind the emulator's models interface (src/dgrade/sklearn_models.py)."""

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier

from dgrade.netbeacon import FLOW_FEATURES, PHASES, PKT_FEATURES
from dgrade.netbeacon_sim import make_packets
from dgrade.sklearn_models import SklearnModels


def _fit(n_feat, classes=3, seed=0, depth=4):
    rng = np.random.default_rng(seed)
    X = rng.integers(0, 2000, (600, n_feat))
    y = (X[:, 0] // 700 + (X[:, -1] > 900)) % classes
    return DecisionTreeClassifier(max_depth=depth, random_state=0).fit(X, y), X


def _models():
    pkt, _ = _fit(len(PKT_FEATURES))
    size = DecisionTreeClassifier(max_depth=3, random_state=0).fit(
        np.random.default_rng(1).integers(0, 1500, (400, len(PKT_FEATURES))), np.random.default_rng(2).integers(0, 2, 400))
    phases = {p: _fit(len(FLOW_FEATURES), seed=p)[0] for p in PHASES}
    return SklearnModels(pkt, size, phases)


def _packets(n=300):
    rng = np.random.default_rng(3)
    return make_packets(ts_ns=np.arange(n) * 1000, src_ip=1, dst_ip=2, src_port=rng.integers(1, 60000, n), dst_port=80,
                        proto=rng.choice([6, 17], n), total_len=rng.integers(40, 1500, n))


def test_pkt_codes_are_class_plus_one_and_match_the_tree():
    m = _models()
    pk = _packets()
    X = np.stack([pk[f].astype(np.int64) for f in PKT_FEATURES], axis=1)
    assert np.array_equal(m.pkt_codes(pk), m.pkt.predict(X).astype(np.int64) + 1)


def test_flow_size_is_a_score_between_zero_and_one_hundred_and_matches_the_tree_probability():
    m = _models()
    pk = _packets()
    s = m.flow_size(pk)
    assert s.min() >= 0 and s.max() <= 100
    X = np.stack([pk[f].astype(np.int64) for f in PKT_FEATURES], axis=1)
    assert np.array_equal(s, np.round(m.size.predict_proba(X)[:, 1] * 100).astype(np.int64))


def test_phase_codes_follow_the_switch_convention():
    m = _models()
    rng = np.random.default_rng(4)
    F = pd.DataFrame(rng.integers(0, 2000, (200, len(FLOW_FEATURES))), columns=FLOW_FEATURES)
    for p in PHASES:
        c = m.phase_codes(p, F)
        ref = m.phases[p].predict(F.to_numpy()).astype(np.int64) + 1 + (50 if p == 2048 else 0)
        assert np.array_equal(c, ref)
        assert (c >= 50).all() if p == 2048 else (c < 50).all()
    assert np.array_equal(m.phase_codes(1024, F), np.zeros(200, dtype=np.int64))       # no Flow_Tree entries at 1024


def test_agrees_with_the_tree_at_thresholds_and_random_rows():
    m = _models()
    t = m.phases[32].tree_
    thr = np.unique(np.round(t.threshold[t.feature >= 0]).astype(np.int64))
    rows = [np.full(len(FLOW_FEATURES), 500)]
    for f in range(len(FLOW_FEATURES)):
        for v in thr[:20]:
            for d in (-1, 0, 1):
                r = np.full(len(FLOW_FEATURES), 500); r[f] = max(int(v) + d, 0); rows.append(r)
    rows += list(np.random.default_rng(5).integers(0, 2000, (12000, len(FLOW_FEATURES))))
    F = pd.DataFrame(np.array(rows), columns=FLOW_FEATURES)
    assert np.array_equal(m.phase_codes(32, F), m.phases[32].predict(F.to_numpy()).astype(np.int64) + 1)
