"""Offline NetBeacon (USENIX Sec'23) models: exported trees and the shipped switch tables.

Two views of the same classifiers, both loaded from ``third_party/NetBeacon`` (commit 06c6127):

* the exported models (``model_generation/models``): sklearn trees as graphviz ``.dot`` files
  (:func:`load_dot_tree`) and the XGBoost text dump of the flow-size predictor
  (:func:`load_xgb_dump`), bundled by :class:`NetBeaconModels`;
* the shipped control-plane tables (``switch/control_plane/*.pkl``) evaluated the way the data
  plane matches them (:class:`TableModel`, :func:`load_tables`): feature value -> ternary feature
  table -> range-mark code -> ternary model table -> action data.

Paths in citations are relative to ``third_party/NetBeacon``. Data-plane feature definitions are
in ``docs/g1_netbeacon_features.md``.
"""

from __future__ import annotations

import pickle
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np

__all__ = [
    "FLOW_FEATURES",
    "FLOW_FEATURE_BITS",
    "FLOW_SIZE_LONG_THRESHOLD",
    "PHASES",
    "PKT_FEATURES",
    "PKT_FEATURE_BITS",
    "DotTree",
    "FeatureTable",
    "NetBeaconModels",
    "NetBeaconTables",
    "TableModel",
    "XGBModel",
    "load_dot_tree",
    "load_tables",
    "load_xgb_dump",
]

# Phase schedule: model_representation.py:100 and switch.p4:639-702 (1024 has a P4 branch but no model).
PHASES: tuple[int, ...] = (2, 4, 8, 32, 256, 512, 2048)

# Per-packet keys in model-table column order (model_representation.py:11-12, controller.py:254).
PKT_FEATURES: tuple[str, ...] = (
    "proto", "total_len", "diffserv", "ttl", "tcp_dataOffset", "tcp_window", "udp_length",
)
PKT_FEATURE_BITS: dict[str, int] = dict(zip(PKT_FEATURES, (8, 16, 8, 8, 4, 16, 16)))
# Width of each feature's range-mark metadata field (headers.p4:219-225: feat8,5,9,7,4,3,6).
_PKT_ENCODE_BITS: dict[str, int] = dict(zip(PKT_FEATURES, (8, 144, 24, 64, 8, 48, 72)))

# Per-flow keys in model-table column order (model_representation.py:58-61, controller.py:255).
FLOW_FEATURES: tuple[str, ...] = (
    "pkt_size_max", "flow_iat_min", "bin_5", "bin_3", "pkt_size_var_approx", "pkt_size_avg",
    "pkt_size_min",
)
FLOW_FEATURE_BITS: dict[str, int] = dict(zip(FLOW_FEATURES, (16, 32, 8, 16, 32, 32, 16)))
# headers.p4:227-233: feat13, feat15, feat11, feat10, feat16, feat12, feat14.
_FLOW_ENCODE_BITS: dict[str, int] = dict(zip(FLOW_FEATURES, (80, 72, 24, 32, 80, 72, 48)))

FLOW_SIZE_LONG_THRESHOLD = 50  # switch.p4:608 `if(ig_md.flow_size>50)`
_DETERMINED_OFFSET = 50  # controller.py:234-235 adds 50 to every 2048-phase result


Rows = Mapping[str, object]  # pandas DataFrame or dict of array-likes keyed by feature name


def _n_rows(rows: Rows) -> int:
    if hasattr(rows, "columns"):  # pandas DataFrame: .values is an attribute, not dict.values()
        return len(rows)
    return len(next(iter(rows.values())))


def _column(rows: Rows, name: str) -> np.ndarray:
    try:
        return np.asarray(rows[name], dtype=np.float64)
    except KeyError as e:
        raise KeyError(f"rows lack feature {name!r}") from e


# ------------------------------------------------------------------------------ sklearn .dot


@dataclass(frozen=True)
class DotTree:
    """A decision tree parsed from sklearn ``export_graphviz`` output.

    Semantics follow sklearn: at a split, go left iff ``x <= threshold``; a leaf predicts the
    class at ``argmax(value)`` (first index on ties). Inputs are compared in float64, which is
    exact for the integer features the data plane sees (sklearn itself casts inputs to float32).
    """

    feature_names: list[str]  # features used by splits, in order of first appearance
    classes: list  # class label at each value index
    thresholds: dict[str, list[float]]  # sorted unique split thresholds per used feature
    feature: np.ndarray  # per node: index into feature_names, -1 at leaves
    threshold: np.ndarray
    left: np.ndarray
    right: np.ndarray
    value: np.ndarray  # (n_nodes, n_classes)

    @property
    def n_leaves(self) -> int:
        return int(np.sum(self.feature < 0))

    def apply(self, rows: Rows) -> np.ndarray:
        """Leaf node id reached by each row."""
        n = _n_rows(rows)
        X = np.stack([_column(rows, f) for f in self.feature_names], axis=1) if self.feature_names else None
        node = np.zeros(n, dtype=np.int64)
        active = self.feature[node] >= 0
        while active.any():
            idx = np.nonzero(active)[0]
            nd = node[idx]
            go_left = X[idx, self.feature[nd]] <= self.threshold[nd]
            node[idx] = np.where(go_left, self.left[nd], self.right[nd])
            active = self.feature[node] >= 0
        return node

    def predict(self, rows: Rows) -> np.ndarray:
        leaf_class = np.argmax(self.value, axis=1)
        labels = np.asarray(self.classes)
        return labels[leaf_class[self.apply(rows)]]


_DOT_NODE = re.compile(r'^(\d+) \[label="(.*?)"')
_DOT_EDGE = re.compile(r"^(\d+) -> (\d+)")
_DOT_SPLIT = re.compile(r"^(.+?) <= (\S+)$")
_DOT_VALUE = re.compile(r"value = \[([^\]]*)\]")
_DOT_CLASS = re.compile(r"class = (.*)$")


def _label(s: str):
    s = s.strip()
    return int(s) if re.fullmatch(r"-?\d+", s) else s


def load_dot_tree(path: str | Path) -> DotTree:
    """Parse an sklearn ``export_graphviz`` file (with ``feature_names``) into a :class:`DotTree`.

    The first edge out of a split node is its left (True) child, as sklearn writes them and as
    NetBeacon's own converter assumes (model_generation/tree_to_table/rf.py:60-66).
    """
    nodes: dict[int, tuple[str | None, float, list[float], object]] = {}
    children: dict[int, list[int]] = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if m := _DOT_EDGE.match(line):
            children.setdefault(int(m.group(1)), []).append(int(m.group(2)))
        elif m := _DOT_NODE.match(line):
            parts = m.group(2).split("\\n")
            split = _DOT_SPLIT.match(parts[0])
            value = [float(v) for v in _DOT_VALUE.search(m.group(2)).group(1).replace(",", " ").split()]
            klass = next((_label(c.group(1)) for p in parts if (c := _DOT_CLASS.match(p))), None)
            if split:
                nodes[int(m.group(1))] = (split.group(1), float(split.group(2)), value, klass)
            else:
                nodes[int(m.group(1))] = (None, np.nan, value, klass)

    n = max(nodes) + 1
    if sorted(nodes) != list(range(n)):
        raise ValueError(f"{path}: node ids are not 0..{n - 1}")
    feature_names = list(dict.fromkeys(f for f, *_ in (nodes[i] for i in range(n)) if f is not None))
    n_classes = len(nodes[0][2])
    feature = np.full(n, -1, dtype=np.int64)
    threshold = np.full(n, np.nan)
    left = np.full(n, -1, dtype=np.int64)
    right = np.full(n, -1, dtype=np.int64)
    value = np.zeros((n, n_classes))
    thresholds: dict[str, set[float]] = {f: set() for f in feature_names}
    labels: dict[int, object] = {}
    for i in range(n):
        f, t, v, klass = nodes[i]
        value[i] = v
        if klass is not None:
            k = int(np.argmax(v))
            if labels.setdefault(k, klass) != klass:
                raise ValueError(f"{path}: class index {k} labelled both {labels[k]!r} and {klass!r}")
        if f is None:
            continue
        kids = children.get(i, [])
        if len(kids) != 2:
            raise ValueError(f"{path}: split node {i} has {len(kids)} children")
        feature[i] = feature_names.index(f)
        threshold[i] = t
        left[i], right[i] = kids
        thresholds[f].add(t)
    classes = [labels.get(k, k) for k in range(n_classes)]
    return DotTree(
        feature_names=feature_names,
        classes=classes,
        thresholds={f: sorted(s) for f, s in thresholds.items()},
        feature=feature, threshold=threshold, left=left, right=right, value=value,
    )


# ------------------------------------------------------------------------------ XGBoost dump


@dataclass(frozen=True)
class _Booster:
    feature: np.ndarray  # index into XGBModel.feature_names, -1 at leaves
    threshold: np.ndarray
    yes: np.ndarray
    no: np.ndarray
    missing: np.ndarray
    leaf: np.ndarray


@dataclass(frozen=True)
class XGBModel:
    """An XGBoost model parsed from its text dump (``[f<thr] yes=,no=,missing=``, strict ``<``).

    ``margin`` is the plain sum of leaf values over boosters; the dump carries no ``base_score``,
    and NetBeacon's table converter uses the same plain sum (tree_to_table/xgb.py:86-89).

    NetBeacon's decision rule (the flow-size gate):
        score = round(sigmoid(margin) * 100)   -- model_generation/tree_to_table/xgb.py:89, the
                                                  action value of Flow_Size_Tree (switch.p4:438-460)
        long  = score > 50                     -- switch.p4:608 ``if(ig_md.flow_size>50)``
    Only flows predicted long may take a storage slot (switch.p4:606-624).
    """

    feature_names: list[str]
    thresholds: dict[str, list[float]]
    boosters: tuple[_Booster, ...]

    @property
    def n_leaves(self) -> int:
        return int(sum(np.sum(b.feature < 0) for b in self.boosters))

    def margin(self, rows: Rows) -> np.ndarray:
        X = np.stack([_column(rows, f) for f in self.feature_names], axis=1)
        total = np.zeros(X.shape[0])
        for b in self.boosters:
            node = np.zeros(X.shape[0], dtype=np.int64)
            active = b.feature[node] >= 0
            while active.any():
                idx = np.nonzero(active)[0]
                nd = node[idx]
                x = X[idx, b.feature[nd]]
                nxt = np.where(x < b.threshold[nd], b.yes[nd], b.no[nd])
                node[idx] = np.where(np.isnan(x), b.missing[nd], nxt)
                active = b.feature[node] >= 0
            total += b.leaf[node]
        return total

    def score(self, rows: Rows) -> np.ndarray:
        """Flow_Size_Tree action value: round(sigmoid(margin)*100), half-to-even like xgb.py:89."""
        return np.round(1 / (1 + np.exp(-self.margin(rows))) * 100).astype(np.int64)

    def predict_long(self, rows: Rows, threshold: int = FLOW_SIZE_LONG_THRESHOLD) -> np.ndarray:
        """True where NetBeacon predicts a long flow: score > threshold (switch.p4:608)."""
        return self.score(rows) > threshold


_XGB_SPLIT = re.compile(r"^(\d+):\[(.+?)<(\S+)\] yes=(\d+),no=(\d+),missing=(\d+)")
_XGB_LEAF = re.compile(r"^(\d+):leaf=(\S+)")


def load_xgb_dump(path: str | Path) -> XGBModel:
    """Parse an XGBoost ``dump_model`` text file into an :class:`XGBModel`."""
    raw: list[dict[int, tuple]] = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line.startswith("booster"):
            raw.append({})
        elif m := _XGB_SPLIT.match(line):
            raw[-1][int(m.group(1))] = ("split", m.group(2), float(m.group(3)),
                                        int(m.group(4)), int(m.group(5)), int(m.group(6)))
        elif m := _XGB_LEAF.match(line):
            raw[-1][int(m.group(1))] = ("leaf", float(m.group(2)))
    feature_names = list(dict.fromkeys(
        nd[1] for tree in raw for _, nd in sorted(tree.items()) if nd[0] == "split"))
    thresholds: dict[str, set[float]] = {f: set() for f in feature_names}
    boosters = []
    for tree in raw:
        n = max(tree) + 1
        feature = np.full(n, -1, dtype=np.int64)
        thr = np.full(n, np.nan)
        yes = np.full(n, -1, dtype=np.int64)
        no = np.full(n, -1, dtype=np.int64)
        miss = np.full(n, -1, dtype=np.int64)
        leaf = np.zeros(n)
        for i, nd in tree.items():
            if nd[0] == "leaf":
                leaf[i] = nd[1]
            else:
                _, f, t, y, nn, mm = nd
                feature[i] = feature_names.index(f)
                thr[i], yes[i], no[i], miss[i] = t, y, nn, mm
                thresholds[f].add(t)
        boosters.append(_Booster(feature, thr, yes, no, miss, leaf))
    return XGBModel(feature_names, {f: sorted(s) for f, s in thresholds.items()}, tuple(boosters))


# ------------------------------------------------------------------------------ model bundle

_MODELS = Path("model_generation") / "models"
_TABLES = Path("switch") / "control_plane"


@dataclass(frozen=True)
class NetBeaconModels:
    pkt_model: DotTree  # per-packet fallback tree (Pkt_Tree)
    phase_models: dict[int, DotTree]  # per-flow tree for each phase, keyed by packet count
    flow_size_model: XGBModel  # short/long flow predictor (Flow_Size_Tree)

    @classmethod
    def load(cls, artifact_dir: str | Path) -> NetBeaconModels:
        d = Path(artifact_dir) / _MODELS
        return cls(
            pkt_model=load_dot_tree(d / "class_pkt_1rf_0.dot"),
            phase_models={p: load_dot_tree(d / f"class_flow_phase_{p}pkt_1rf_0.dot") for p in PHASES},
            flow_size_model=load_xgb_dump(d / "flow_size_predict_1xgb.txt"),
        )


# ------------------------------------------------------------------------------ shipped tables


_ENCODE_CHUNK = 4096  # distinct key values matched per block in FeatureTable.encode


@dataclass(frozen=True)
class FeatureTable:
    """One feature (range-mark) table, e.g. Feat5 on hdr.ipv4.total_len (switch.p4:297-304).

    Entries are ``[priority, value, mask]`` ternary keys whose action writes ``mark`` into a
    ``encode_bits``-wide metadata field. The lowest ``$MATCH_PRIORITY`` wins: the generator emits
    the narrower ``[t_i, end)`` entry one priority number below the wider ``[start, end)`` entry
    that it must override (tree_to_table/utils.py:124-137), and the bin tables put the specific
    entry at 1 and match-all at 2 (controller.py:131-136). A miss runs ``noaction`` and leaves the
    field at 0, its reset value (switch.p4:559-572).
    """

    name: str
    key_bits: int
    encode_bits: int
    priority: np.ndarray
    value: np.ndarray
    mask: np.ndarray
    mark: tuple[int, ...]

    def encode(self, x: np.ndarray) -> np.ndarray:
        """Range-mark code (python int, object array) for integer key values ``x``.

        Matching runs on the distinct key values, in chunks, so memory is
        O(chunk x entries) regardless of ``len(x)``.
        """
        uniq, inv = np.unique(np.asarray(x, dtype=np.int64), return_inverse=True)
        codes = np.zeros(len(uniq), dtype=object)
        if len(self.mark) == 0:
            return codes[inv.reshape(-1)]
        marks = np.asarray(self.mark, dtype=object)
        width = (1 << self.encode_bits) - 1
        want = self.value & self.mask
        for s in range(0, len(uniq), _ENCODE_CHUNK):
            u = uniq[s:s + _ENCODE_CHUNK]
            hit = (u[:, None] & self.mask[None, :]) == want[None, :]
            prio = np.where(hit, self.priority[None, :], np.iinfo(np.int64).max)
            best = np.argmin(prio, axis=1)
            tie = (prio == prio[np.arange(len(u)), best][:, None]) & hit
            for r in np.nonzero(tie.sum(axis=1) > 1)[0]:
                if len(set(marks[tie[r]])) > 1:
                    raise ValueError(f"{self.name}: value {u[r]} hits equal-priority entries with different marks")
            any_hit = hit.any(axis=1)
            codes[s:s + _ENCODE_CHUNK][any_hit] = [int(m) & width for m in marks[best[any_hit]]]
        return codes[inv.reshape(-1)]


@dataclass(frozen=True)
class TableModel:
    """A NetBeacon model evaluated from its shipped tables, as the switch would.

    ``features`` are the model table's ternary key fields in column order; the model table is an
    unprioritised ternary table (controller.py:185-196, 206-218, 237-250 set no priority), so a
    key that hits more than one entry is ambiguous and raises. For phase models the feature and
    model tables are also keyed on ``total_pkts: exact`` (switch.p4:338-392, 511-530), which here
    is fixed to ``phase``.

    ``kind == "class"``: action data is the leaf class-probability vector; the controller writes
    ``result = argmax + 1`` (controller.py:217, 229) plus 50 in the 2048 phase (controller.py:234).
    ``predict`` maps the argmax index through ``classes`` (taken from the matching ``.dot``
    model by :func:`load_tables`), so its labels are comparable with :meth:`DotTree.predict`.
    ``kind == "flow_size"``: action data is the flow-size score (tree_to_table/xgb.py:89).
    """

    kind: str
    features: tuple[FeatureTable, ...]
    values: tuple[tuple[int, ...], ...]  # per feature, per model-table entry
    masks: tuple[tuple[int, ...], ...]
    actions: tuple
    phase: int | None = None
    classes: tuple = ()  # class label per argmax index; used only when kind == "class"

    def _keys(self, rows: Rows) -> dict[str, np.ndarray]:
        out = {}
        for ft in self.features:
            col = _column(rows, ft.name)
            if not np.all(np.isfinite(col)) or np.any(col != np.floor(col)):
                raise ValueError(f"{ft.name}: data-plane keys are integers")
            if np.any(col < 0) or np.any(col >= (1 << ft.key_bits)):
                raise ValueError(f"{ft.name}: value outside the {ft.key_bits}-bit key")
            out[ft.name] = col.astype(np.int64)
        return out

    def encode(self, rows: Rows) -> dict[str, np.ndarray]:
        """Range-mark code of every feature, as the feature tables write them."""
        keys = self._keys(rows)
        return {ft.name: ft.encode(keys[ft.name]) for ft in self.features}

    def match(self, rows: Rows) -> np.ndarray:
        """Index of the model-table entry hit by each row, -1 on a miss."""
        codes = self.encode(rows)
        n = _n_rows(rows)
        hit = np.ones((n, len(self.actions)), dtype=bool)
        for j, ft in enumerate(self.features):
            uniq, inv = np.unique(codes[ft.name], return_inverse=True)
            vm = list(zip(self.values[j], self.masks[j]))
            table = np.array([[(int(u) & m) == (v & m) for v, m in vm] for u in uniq], dtype=bool)
            hit &= table[inv.reshape(-1)]
        count = hit.sum(axis=1)
        if np.any(count > 1):
            r = int(np.argmax(count > 1))
            raise ValueError(f"row {r} hits {int(count[r])} model-table entries")
        return np.where(count == 1, np.argmax(hit, axis=1), -1)

    def _class_index(self, rows: Rows) -> np.ndarray:
        """Argmax index of the hit entry's class probabilities; -1 on a miss."""
        idx = self.match(rows)
        per_entry = np.array([int(np.argmax(a)) for a in self.actions], dtype=np.int64)
        return np.where(idx >= 0, per_entry[idx], -1)

    def predict(self, rows: Rows) -> np.ndarray:
        """Class label (via ``classes``) or flow-size score; -1 on a miss."""
        if self.kind == "class":
            ci = self._class_index(rows)
            labels = np.asarray(self.classes, dtype=object)
            out = np.array([labels[i] if i >= 0 else -1 for i in ci], dtype=object)
            return out.astype(np.int64) if all(isinstance(c, int) for c in self.classes) else out
        idx = self.match(rows)
        per_entry = np.array([int(a) for a in self.actions], dtype=np.int64)
        return np.where(idx >= 0, per_entry[idx], -1)

    def result_codes(self, rows: Rows) -> np.ndarray:
        """``ig_md.result`` written by a hit (controller rule); 0 where the table misses."""
        if self.kind != "class":
            raise ValueError("result codes exist only for class tables")
        ci = self._class_index(rows)
        add = _DETERMINED_OFFSET if self.phase == 2048 else 0
        return np.where(ci >= 0, ci + 1 + add, 0)


@dataclass(frozen=True)
class NetBeaconTables:
    pkt: TableModel  # Pkt_Tree
    flow_size: TableModel  # Flow_Size_Tree
    phases: dict[int, TableModel]  # Flow_Tree restricted to total_pkts == phase


def _feature_table(name: str, entries: list, key_bits: int, encode_bits: int, phase: int | None) -> FeatureTable:
    if phase is not None:
        entries = [e for e in entries if int(e[4]) == phase]
    return FeatureTable(
        name=name, key_bits=key_bits, encode_bits=encode_bits,
        priority=np.array([int(e[0]) for e in entries], dtype=np.int64),
        value=np.array([int(e[1]) for e in entries], dtype=np.int64),
        mask=np.array([int(e[2]) for e in entries], dtype=np.int64),
        mark=tuple(int(e[3]) for e in entries),
    )


def _model_columns(rows: list, n_features: int, offset: int) -> tuple[tuple, tuple, tuple]:
    values = tuple(tuple(int(r[offset + 2 * j]) for r in rows) for j in range(n_features))
    masks = tuple(tuple(int(r[offset + 2 * j + 1]) for r in rows) for j in range(n_features))
    actions = tuple(r[offset + 2 * n_features] for r in rows)
    return values, masks, actions


def load_tables(artifact_dir: str | Path) -> NetBeaconTables:
    """Load the shipped ``.pkl`` tables and label class tables with the ``.dot`` models' classes.

    The pickles are written with protocol 2 (model_generation/model_representation.py:53, 130)
    and read by controller.py:257-261; ``encoding="latin1"`` keeps any Python-2-era str or
    numpy payload decodable.
    """
    models = NetBeaconModels.load(artifact_dir)
    d = Path(artifact_dir) / _TABLES
    with open(d / "flow_size_and_class_pkt.pkl", "rb") as f:
        feat_pkt, flow_size_rows, pkt_rows = pickle.load(f, encoding="latin1")
    with open(d / "bin_table_and_class_flow.pkl", "rb") as f:
        _bin_table, feat_flow, flow_rows = pickle.load(f, encoding="latin1")

    pkt_fts = tuple(
        _feature_table(n, feat_pkt[n], PKT_FEATURE_BITS[n], _PKT_ENCODE_BITS[n], None) for n in PKT_FEATURES)
    v, m, a = _model_columns(pkt_rows, len(PKT_FEATURES), 0)
    pkt = TableModel("class", pkt_fts, v, m, a, classes=tuple(models.pkt_model.classes))
    v, m, a = _model_columns(flow_size_rows, len(PKT_FEATURES), 0)
    flow_size = TableModel("flow_size", pkt_fts, v, m, a)

    phases = {}
    for p in PHASES:
        fts = tuple(
            _feature_table(n, feat_flow[n], FLOW_FEATURE_BITS[n], _FLOW_ENCODE_BITS[n], p) for n in FLOW_FEATURES)
        v, m, a = _model_columns([r for r in flow_rows if int(r[0]) == p], len(FLOW_FEATURES), 1)
        phases[p] = TableModel("class", fts, v, m, a, phase=p, classes=tuple(models.phase_models[p].classes))
    return NetBeaconTables(pkt=pkt, flow_size=flow_size, phases=phases)
