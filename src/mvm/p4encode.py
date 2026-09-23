"""Exact integer encoding of decision-tree leaves for switch range-match tables.

sklearn compares float32-cast inputs against float64 thresholds. Each feature is sent to the
switch as a 32-bit key that preserves float32 order (positive floats: set the sign bit; negative
floats: invert all bits), and each leaf box becomes one inclusive key range per feature. A range
match on keys then reproduces the tree's comparisons exactly: no quantization, 100% fidelity.
"""

from __future__ import annotations

import numpy as np

from mvm.leaves import LeafBox

__all__ = ["f32_key", "box_key_ranges", "KEY_MIN", "KEY_MAX"]

KEY_MIN, KEY_MAX = np.uint32(0), np.uint32(0xFFFFFFFF)


def f32_key(x) -> np.ndarray:
    """Order-preserving uint32 key of float32(x); -0.0 and +0.0 map to the same key."""
    v = np.asarray(x, dtype=np.float32) + np.float32(0.0)  # -0.0 + 0.0 == +0.0
    bits = v.view(np.uint32)
    neg = (bits >> 31).astype(bool)
    return np.where(neg, ~bits, bits | np.uint32(0x80000000)).astype(np.uint32)


def _largest_f32_at_most(t: float) -> np.float32:
    v = np.float32(t)
    if float(v) > t:
        v = np.nextafter(v, np.float32(-np.inf))
    return v


def _smallest_f32_above(t: float) -> np.float32:
    v = np.float32(t)
    if float(v) <= t:
        v = np.nextafter(v, np.float32(np.inf))
    return v


def box_key_ranges(box: LeafBox) -> tuple[np.ndarray, np.ndarray]:
    """Inclusive per-feature key ranges [lo, hi] with key(x) in range  <=>  box.lo < f32(x) <= box.hi."""
    lo = np.array([KEY_MIN if np.isneginf(t) else f32_key(_smallest_f32_above(t)) for t in box.lo], dtype=np.uint32)
    hi = np.array([KEY_MAX if np.isposinf(t) else f32_key(_largest_f32_at_most(t)) for t in box.hi], dtype=np.uint32)
    return lo, hi
