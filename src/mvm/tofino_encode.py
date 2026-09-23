"""Exact decision-tree encoding for Tofino-1 tables (range keys limited to ~20 bits per table).

Per feature f with sorted distinct thresholds t_0 < ... < t_{n-1}, the switch computes an n-bit
thermometer code: bit j = 1 iff f32(x) > t_j, i.e. key(x) >= b_j where b_j is the order-preserving
key (mvm.p4encode.f32_key) of the smallest float32 above t_j.

  coarse table  key[31:12] : range  -> code at the start of each 4096-key bucket segment
  fine table    key[31:12] : exact, key[11:0] : range  -> exact code inside the few buckets that
                contain a boundary b_j (applied first; the coarse table is used on a fine miss)
  leaf table    ternary over the concatenated codes: leaf box lo < x <= hi on feature f needs only
                bit(lo) = 1 and bit(hi) = 0 (the code is monotone), so one entry per leaf.
Both lookups use range keys of at most 20 bits. The result equals tree.apply exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.tree import DecisionTreeClassifier

from mvm.leaves import extract_leaf_boxes
from mvm.p4encode import f32_key

__all__ = ["TofinoEncoding", "FeatureTables"]

BUCKET_BITS = 12
BUCKET = 1 << BUCKET_BITS
K20_MAX = (1 << (32 - BUCKET_BITS)) - 1


def _boundary_key(t: float) -> int:
    v = np.float32(t)
    if float(v) <= t:
        v = np.nextafter(v, np.float32(np.inf))
    return int(f32_key(v))


@dataclass
class FeatureTables:
    index: int
    thresholds: np.ndarray            # sorted distinct float64 thresholds
    bkeys: np.ndarray                 # uint64 boundary keys, sorted
    offset: int                       # first bit of this feature's code in the concatenated key
    coarse: list = field(default_factory=list)  # (k20_lo, k20_hi, code)
    fine: list = field(default_factory=list)    # (bucket, k12_lo, k12_hi, code)

    @property
    def width(self) -> int:
        return len(self.thresholds)

    def code_at(self, key: int) -> int:
        """Thermometer code of one key: bit j set iff key >= bkeys[j] (bits are contiguous from 0)."""
        n = int(np.searchsorted(self.bkeys, key, side="right"))
        return (1 << n) - 1


class TofinoEncoding:
    def __init__(self, tree: DecisionTreeClassifier):
        self.tree = tree
        t = tree.tree_
        self.features: list[FeatureTables] = []
        offset = 0
        for f in range(tree.n_features_in_):
            thr = np.unique(t.threshold[t.feature == f])
            bk = np.array([_boundary_key(x) for x in thr], dtype=np.uint64)
            ft = FeatureTables(f, thr, bk, offset)
            self._build_tables(ft)
            self.features.append(ft)
            offset += ft.width
        self.n_words = max(1, (offset + 63) // 64)

    # --- per-feature tables ----------------------------------------------------------------------
    @staticmethod
    def _build_tables(ft: FeatureTables) -> None:
        if ft.width == 0:
            return
        straddled = sorted({int(b) >> BUCKET_BITS for b in ft.bkeys if int(b) & (BUCKET - 1)})
        # coarse: the code is constant between consecutive "first bucket at or above a boundary"
        starts = sorted({0} | {min(K20_MAX, -(-int(b) // BUCKET)) for b in ft.bkeys})
        for i, s in enumerate(starts):
            e = starts[i + 1] - 1 if i + 1 < len(starts) else K20_MAX
            if e >= s:
                ft.coarse.append((s, e, ft.code_at(s << BUCKET_BITS)))
        # fine: exact sub-ranges inside each straddled bucket
        for s in straddled:
            base = s << BUCKET_BITS
            cuts = sorted({0} | {int(b) - base for b in ft.bkeys if int(b) >> BUCKET_BITS == s})
            for i, lo in enumerate(cuts):
                hi = cuts[i + 1] - 1 if i + 1 < len(cuts) else BUCKET - 1
                ft.fine.append((s, lo, hi, ft.code_at(base + lo)))

    def key_width(self) -> int:
        return sum(ft.width for ft in self.features)

    def n_fine_entries(self) -> int:
        return sum(len(ft.fine) for ft in self.features)

    def n_coarse_entries(self) -> int:
        return sum(len(ft.coarse) for ft in self.features)

    # --- packing helpers -------------------------------------------------------------------------
    def _pack(self, bits: dict[int, int]) -> np.ndarray:
        words = np.zeros(self.n_words, dtype=np.uint64)
        for pos, v in bits.items():
            if v:
                words[pos // 64] |= np.uint64(1) << np.uint64(pos % 64)
        return words

    # --- switch emulation (used by tests and by the offline fidelity check) -----------------------
    def codes_like_switch(self, keys: np.ndarray) -> np.ndarray:
        """Concatenated codes as the switch computes them (fine table first, else coarse)."""
        keys = np.asarray(keys, dtype=np.uint64)
        out = np.zeros((len(keys), self.n_words), dtype=np.uint64)
        for ft in self.features:
            if ft.width == 0:
                continue
            k = keys[:, ft.index]
            k20, k12 = (k >> np.uint64(BUCKET_BITS)).astype(np.int64), (k & np.uint64(BUCKET - 1)).astype(np.int64)
            code = np.zeros(len(k), dtype=object)
            got = np.zeros(len(k), dtype=bool)
            for b, lo, hi, c in ft.fine:
                m = ~got & (k20 == b) & (k12 >= lo) & (k12 <= hi)
                code[m], got[m] = c, True
            for lo, hi, c in ft.coarse:
                m = ~got & (k20 >= lo) & (k20 <= hi)
                code[m], got[m] = c, True
            assert got.all(), "coarse table must cover the whole 20-bit key space"
            for j in range(ft.width):
                bit = np.array([(int(c) >> j) & 1 for c in code], dtype=np.uint64)
                pos = ft.offset + j
                out[:, pos // 64] |= bit << np.uint64(pos % 64)
        return out

    # --- leaf table ------------------------------------------------------------------------------
    def leaf_entries(self) -> list[dict]:
        """One ternary entry per leaf: per-feature (value, mask) ints and packed words for emulation."""
        entries = []
        for box in extract_leaf_boxes(self.tree):
            per_feature, val_bits, mask_bits = [], {}, {}
            for ft in self.features:
                v = m = 0
                lo, hi = box.lo[ft.index], box.hi[ft.index]
                if not np.isneginf(lo):
                    j = int(np.searchsorted(ft.thresholds, lo))
                    assert ft.thresholds[j] == lo
                    v |= 1 << j; m |= 1 << j
                    val_bits[ft.offset + j] = 1; mask_bits[ft.offset + j] = 1
                if not np.isposinf(hi):
                    j = int(np.searchsorted(ft.thresholds, hi))
                    assert ft.thresholds[j] == hi
                    m |= 1 << j
                    mask_bits[ft.offset + j] = 1
                per_feature.append((v, m))
            entries.append({"leaf_id": box.leaf_id, "klass": int(box.klass), "per_feature": per_feature,
                            "value": self._pack(val_bits), "mask": self._pack(mask_bits)})
        return entries
