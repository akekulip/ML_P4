import dataclasses
import hashlib
import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.tree import DecisionTreeClassifier, export_graphviz

from dgrade.netbeacon import (
    FLOW_FEATURE_BITS,
    PHASES,
    PKT_FEATURE_BITS,
    NetBeaconModels,
    load_dot_tree,
    load_tables,
    load_xgb_dump,
)

ARTIFACT = Path(__file__).resolve().parents[1] / "third_party" / "NetBeacon"
ARTIFACT_COMMIT = "06c6127"
PKL_SHA256 = {
    "bin_table_and_class_flow.pkl": "5706cb3815878d28bf2e2762464942ac6a5b2a800b371cbb3a817b605dc252b7",
    "flow_size_and_class_pkt.pkl": "e5a43b58fe8d05c6ebb0bb33bb01a31bf384afe0d6b647fc0ea15a00e021444b",
}
ALLOW_MISSING = "DGRADE_ALLOW_MISSING_ARTIFACTS"


def _artifact_problem():
    """None if third_party/NetBeacon is the pinned checkout, else a description of what is wrong."""
    if not ARTIFACT.is_dir():
        return f"{ARTIFACT} is missing; clone NetBeacon at commit {ARTIFACT_COMMIT} there"
    for name, want in PKL_SHA256.items():
        f = ARTIFACT / "switch" / "control_plane" / name
        if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest() != want:
            return f"{f} is missing or differs from the commit-{ARTIFACT_COMMIT} file"
    if (ARTIFACT / ".git").exists():
        head = subprocess.run(["git", "-C", str(ARTIFACT), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=False).stdout.strip()
        if not head.startswith(ARTIFACT_COMMIT):
            return f"{ARTIFACT} is at commit {head or '?'}, expected {ARTIFACT_COMMIT}"
    return None


@pytest.fixture(scope="module")
def artifact_ok():
    problem = _artifact_problem()
    if problem is None:
        return
    if os.environ.get(ALLOW_MISSING) == "1":
        pytest.skip(problem)
    pytest.fail(f"{problem}. Set {ALLOW_MISSING}=1 to skip the artifact tests instead.")


needs_artifact = pytest.mark.usefixtures("artifact_ok")


# ---------------------------------------------------------------- dot parser


def test_dot_tree_matches_sklearn_on_integer_data(tmp_path):
    rng = np.random.default_rng(0)
    X = rng.integers(0, 200, size=(3000, 4)).astype(float)
    y = (X[:, 0] > 90).astype(int) + (X[:, 2] > 150).astype(int)
    names = ["a", "b", "c", "d"]
    clf = DecisionTreeClassifier(max_depth=6, random_state=0).fit(X, y)
    dot = tmp_path / "t.dot"
    export_graphviz(clf, out_file=str(dot), feature_names=names, class_names=["0", "1", "2"])
    tree = load_dot_tree(dot)
    Xt = rng.integers(0, 200, size=(2000, 4)).astype(float)
    rows = pd.DataFrame(Xt, columns=names)
    assert np.array_equal(tree.predict(rows), clf.predict(Xt))
    assert tree.classes == [0, 1, 2]
    used = [names[i] for i in clf.tree_.feature if i >= 0]
    assert tree.feature_names == list(dict.fromkeys(used))


DOT_EDGE = """digraph Tree {
0 [label="x <= 10.0\\ngini = 0.5\\nsamples = 4\\nvalue = [2, 2]\\nclass = 0"] ;
1 [label="gini = 0.0\\nsamples = 2\\nvalue = [2, 0]\\nclass = 0"] ;
0 -> 1 [labeldistance=2.5, labelangle=45, headlabel="True"] ;
2 [label="gini = 0.0\\nsamples = 2\\nvalue = [0, 2]\\nclass = 1"] ;
0 -> 2 [labeldistance=2.5, labelangle=-45, headlabel="False"] ;
}
"""


def test_dot_tree_goes_left_on_equality_and_accepts_dict_rows(tmp_path):
    p = tmp_path / "e.dot"
    p.write_text(DOT_EDGE)
    tree = load_dot_tree(p)
    assert tree.feature_names == ["x"]
    assert list(tree.predict({"x": np.array([9, 10, 10.5, 11])})) == [0, 0, 1, 1]


# ---------------------------------------------------------------- xgb parser

XGB_DUMP = """booster[0]:
0:[f<10] yes=1,no=2,missing=1
\t1:leaf=-1.0
\t2:[g<3] yes=3,no=4,missing=3
\t\t3:leaf=0.5
\t\t4:leaf=2.0
booster[1]:
0:[g<5] yes=1,no=2,missing=1
\t1:leaf=0.25
\t2:leaf=-0.25
"""


def test_xgb_dump_is_strict_less_than_and_sums_boosters(tmp_path):
    p = tmp_path / "x.txt"
    p.write_text(XGB_DUMP)
    m = load_xgb_dump(p)
    rows = {"f": np.array([9, 10, 10, 10]), "g": np.array([0, 2, 3, 5])}
    assert np.allclose(m.margin(rows), [-1.0 + 0.25, 0.5 + 0.25, 2.0 + 0.25, 2.0 - 0.25])
    assert m.feature_names == ["f", "g"]


def test_xgb_predict_long_uses_rounded_sigmoid_percent_strictly_above_threshold(tmp_path):
    p = tmp_path / "x.txt"
    p.write_text(XGB_DUMP)
    m = load_xgb_dump(p)
    rows = {"f": np.array([9, 10, 10]), "g": np.array([5, 2, 5])}
    # margins -1.25 -> 22, 0.75 -> 68, 1.75 -> 85 (round(sigmoid*100))
    assert list(m.score(rows)) == [22, 68, 85]
    assert list(m.predict_long(rows, 50)) == [False, True, True]
    assert list(m.predict_long(rows, 68)) == [False, False, True]


# ---------------------------------------------------------------- shipped models


@needs_artifact
def test_models_load_from_artifact():
    models = NetBeaconModels.load(ARTIFACT)
    assert set(models.phase_models) == set(PHASES) == {2, 4, 8, 32, 256, 512, 2048}
    assert set(models.pkt_model.feature_names) <= set(PKT_FEATURE_BITS)
    for tree in models.phase_models.values():
        assert set(tree.feature_names) <= set(FLOW_FEATURE_BITS)
        assert tree.classes == [0, 1, 2]
    assert models.pkt_model.classes == [0, 1, 2]
    assert set(models.flow_size_model.feature_names) <= set(PKT_FEATURE_BITS)
    assert models.flow_size_model.n_leaves == 182


# ---------------------------------------------------------------- table fidelity

N_ROWS = 12000


def _straddle_rows(thresholds, bits, n, seed):
    """Integer rows in each key's data-plane domain, mixed around every threshold."""
    rng = np.random.default_rng(seed)
    cols = {}
    for name, nbits in bits.items():
        top = (1 << nbits) - 1
        thr = np.asarray(sorted(thresholds.get(name, [])), dtype=float)
        near = np.concatenate([np.floor(thr), np.ceil(thr), np.floor(thr) - 1, np.ceil(thr) + 1,
                               np.floor(thr - 0.5), np.ceil(thr + 0.5), [0, top]])
        near = np.clip(near, 0, top).astype(np.int64)
        lo = int(max(0, thr.min() - 10)) if thr.size else 0
        hi = int(min(top, thr.max() + 10)) if thr.size else top
        pick = rng.random(n)
        col = np.where(pick < 0.45, rng.choice(near, n),
                       np.where(pick < 0.8, rng.integers(lo, hi + 1, n), rng.integers(0, top + 1, n)))
        cols[name] = col.astype(np.int64)
    return pd.DataFrame(cols)


def _leaf_rows(tree, bits, seed):
    """Integer points inside every leaf box (both edges), so every leaf is exercised at least once."""
    rng = np.random.default_rng(seed)
    out = []

    def walk(node, lo, hi):
        f = tree.feature[node]
        if f < 0:
            for edge in ("low", "high"):
                row, ok = {}, True
                for name, nbits in bits.items():
                    a = int(np.floor(lo.get(name, -1.0))) + 1
                    b = int(min(np.floor(hi.get(name, np.inf)), (1 << nbits) - 1))
                    if a > b:
                        ok = False
                        break
                    row[name] = a if edge == "low" else b
                    if name not in lo and name not in hi:
                        row[name] = int(rng.integers(0, (1 << nbits)))
                if ok:
                    out.append(row)
            return
        name, t = tree.feature_names[f], tree.threshold[node]
        walk(tree.left[node], lo, {**hi, name: min(hi.get(name, np.inf), t)})
        walk(tree.right[node], {**lo, name: max(lo.get(name, -1.0), t)}, hi)

    walk(0, {}, {})
    return pd.DataFrame(out)


def _xgb_leaf_rows(model, bits, seed):
    """Integer points at both edges of every leaf box of every booster (yes-branch iff x < thr)."""
    rng = np.random.default_rng(seed)
    out = []
    for b in model.boosters:
        def walk(node, lo, hi, b=b):
            f = b.feature[node]
            if f < 0:
                for edge in ("low", "high"):
                    row, ok = {}, True
                    for name, nbits in bits.items():
                        a = int(np.ceil(lo.get(name, 0.0)))
                        z = int(min(np.ceil(hi.get(name, np.inf)) - 1, (1 << nbits) - 1))
                        if a > z:
                            ok = False
                            break
                        row[name] = a if edge == "low" else z
                        if name not in lo and name not in hi:
                            row[name] = int(rng.integers(0, 1 << nbits))
                    if ok:
                        out.append(row)
                return
            name, t = model.feature_names[f], b.threshold[node]
            walk(b.yes[node], lo, {**hi, name: min(hi.get(name, np.inf), t)})
            walk(b.no[node], {**lo, name: max(lo.get(name, 0.0), t)}, hi)

        walk(0, {}, {})
    return pd.DataFrame(out)


@pytest.fixture(scope="module")
def shipped(artifact_ok):
    return NetBeaconModels.load(ARTIFACT), load_tables(ARTIFACT)


@needs_artifact
def test_pkt_tables_match_dot_tree_on_every_row(shipped):
    models, tables = shipped
    thr = {**models.pkt_model.thresholds}
    for k, v in models.flow_size_model.thresholds.items():
        thr[k] = list(thr.get(k, [])) + list(v)
    rows = _straddle_rows(thr, PKT_FEATURE_BITS, N_ROWS, seed=1)
    rows = pd.concat([rows, _leaf_rows(models.pkt_model, PKT_FEATURE_BITS, seed=1)], ignore_index=True)
    assert len(set(tables.pkt.match(rows))) == len(tables.pkt.actions)  # every table entry hit
    got = tables.pkt.predict(rows)
    want = models.pkt_model.predict(rows)
    assert (got == want).mean() == 1.0, rows[got != want].head()


@needs_artifact
def test_flow_size_table_matches_xgb_score_on_every_row(shipped):
    models, tables = shipped
    thr = {**models.flow_size_model.thresholds}
    for k, v in models.pkt_model.thresholds.items():
        thr[k] = list(thr.get(k, [])) + list(v)
    rows = _straddle_rows(thr, PKT_FEATURE_BITS, N_ROWS, seed=2)
    rows = pd.concat([rows, _xgb_leaf_rows(models.flow_size_model, PKT_FEATURE_BITS, seed=2)], ignore_index=True)
    assert len(set(tables.flow_size.match(rows))) == len(tables.flow_size.actions) == 182
    got = tables.flow_size.predict(rows)
    want = models.flow_size_model.score(rows)
    assert (got == want).mean() == 1.0, rows[got != want].head()


@needs_artifact
@pytest.mark.parametrize("phase", PHASES)
def test_phase_tables_match_dot_tree_on_every_row(shipped, phase):
    models, tables = shipped
    tree = models.phase_models[phase]
    rows = _straddle_rows(tree.thresholds, FLOW_FEATURE_BITS, N_ROWS, seed=100 + phase)
    rows = pd.concat([rows, _leaf_rows(tree, FLOW_FEATURE_BITS, seed=phase)], ignore_index=True)
    assert len(set(tables.phases[phase].match(rows))) == len(tables.phases[phase].actions)
    got = tables.phases[phase].predict(rows)
    want = tree.predict(rows)
    assert (got == want).mean() == 1.0, rows[got != want].head()


@needs_artifact
def test_result_codes_follow_controller_rule(shipped):
    # controller.py:217 result=argmax+1; controller.py:229-235 +50 only at the 2048 phase
    models, tables = shipped
    rows = _straddle_rows(models.pkt_model.thresholds, PKT_FEATURE_BITS, 500, seed=3)
    idx = [tables.pkt.classes.index(c) for c in tables.pkt.predict(rows)]
    assert np.array_equal(tables.pkt.result_codes(rows), np.array(idx) + 1)
    for phase in PHASES:
        rows = _straddle_rows(models.phase_models[phase].thresholds, FLOW_FEATURE_BITS, 500, seed=phase)
        add = 50 if phase == 2048 else 0
        t = tables.phases[phase]
        idx = [t.classes.index(c) for c in t.predict(rows)]
        assert np.array_equal(t.result_codes(rows), np.array(idx) + 1 + add)


@needs_artifact
def test_table_model_rejects_values_outside_key_width(shipped):
    _, tables = shipped
    rows = {k: np.zeros(1, dtype=np.int64) for k in PKT_FEATURE_BITS}
    rows["ttl"] = np.array([256])
    with pytest.raises(ValueError):
        tables.pkt.predict(rows)


@needs_artifact
def test_table_classes_come_from_the_dot_models_and_are_applied(shipped):
    models, tables = shipped
    assert tables.pkt.classes == tuple(models.pkt_model.classes)
    for p in PHASES:
        assert tables.phases[p].classes == tuple(models.phase_models[p].classes)
    relabelled = dataclasses.replace(tables.pkt, classes=("a", "b", "c"))
    rows = _straddle_rows(models.pkt_model.thresholds, PKT_FEATURE_BITS, 300, seed=4)
    idx = tables.pkt.predict(rows)  # classes are (0, 1, 2), so labels equal indices here
    assert list(relabelled.predict(rows)) == [("a", "b", "c")[i] for i in idx]
    assert np.array_equal(relabelled.result_codes(rows), tables.pkt.result_codes(rows))


def _encode_reference(ft, x):
    """Per-row brute force: lowest priority among matching entries, 0 on a miss."""
    out = []
    width = (1 << ft.encode_bits) - 1
    for v in x:
        hits = [(int(p), m) for p, val, mask, m in zip(ft.priority, ft.value, ft.mask, ft.mark)
                if (int(v) & int(mask)) == (int(val) & int(mask))]
        out.append(min(hits)[1] & width if hits else 0)
    return out


@needs_artifact
@pytest.mark.parametrize("name", ["pkt_size_var_approx", "pkt_size_max"])
def test_feature_encode_scales_to_a_million_rows(shipped, name):
    _, tables = shipped
    ft = next(f for f in tables.phases[2].features if f.name == name)
    rng = np.random.default_rng(5)
    top = (1 << ft.key_bits) - 1
    near = np.clip(np.concatenate([ft.value, ft.value - 1, ft.value + 1]), 0, top)
    x = np.where(rng.random(1_000_000) < 0.5, rng.choice(near, 1_000_000), rng.integers(0, top + 1, 1_000_000))
    codes = ft.encode(x)
    assert codes.shape == (1_000_000,)
    sample = rng.choice(len(x), 3000, replace=False)
    assert list(codes[sample]) == _encode_reference(ft, x[sample])


DOT_LEAF = """digraph Tree {
0 [label="gini = 0.0\\nsamples = 3\\nvalue = [0, 3]\\nclass = 1"] ;
}
"""


def test_splitless_dot_tree_accepts_dataframe_rows(tmp_path):
    p = tmp_path / "leaf.dot"
    p.write_text(DOT_LEAF)
    tree = load_dot_tree(p)
    assert tree.feature_names == []
    assert list(tree.predict(pd.DataFrame({"x": [1, 2, 3]}))) == [1, 1, 1]
    assert list(tree.predict({"x": np.array([1, 2])})) == [1, 1]
