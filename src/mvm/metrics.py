"""Classification metrics and confusion-matrix bootstrap confidence intervals.

Binary metrics are functions of the 2x2 confusion matrix, so an i.i.d. bootstrap of the test set
is a multinomial resample of its four cell counts: exact and fast. Use it only for i.i.d. test
pools; the chronological replay is serially dependent and is reported per day instead.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score, balanced_accuracy_score, f1_score, recall_score

__all__ = ["binary_from_counts", "binary_metrics", "bootstrap_ci", "multiclass_metrics"]


def binary_from_counts(tp, fp, fn, tn) -> dict[str, np.ndarray]:
    """Vectorized over arrays of counts. Positive class = attack (label 1)."""
    tp, fp, fn, tn = (np.asarray(v, dtype=float) for v in (tp, fp, fn, tn))
    with np.errstate(divide="ignore", invalid="ignore"):
        prec_a, rec_a = tp / (tp + fp), tp / (tp + fn)
        prec_b, rec_b = tn / (tn + fn), tn / (tn + fp)
        f1_a = 2 * prec_a * rec_a / (prec_a + rec_a)
        f1_b = 2 * prec_b * rec_b / (prec_b + rec_b)
        mcc = (tp * tn - fp * fn) / np.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return {
        # an undefined per-class F1 (no predictions or no instances of that class) counts as 0
        "macro_f1": (np.nan_to_num(f1_a) + np.nan_to_num(f1_b)) / 2,
        "mcc": np.nan_to_num(mcc),
        "attack_precision": np.nan_to_num(prec_a),
        "attack_recall": np.nan_to_num(rec_a),
        "attack_f1": np.nan_to_num(f1_a),
        "benign_recall": np.nan_to_num(rec_b),
        "balanced_accuracy": np.nan_to_num((rec_a + rec_b) / 2),
    }


def _counts(y, pred):
    y, pred = np.asarray(y), np.asarray(pred)
    return (int(((y == 1) & (pred == 1)).sum()), int(((y == 0) & (pred == 1)).sum()),
            int(((y == 1) & (pred == 0)).sum()), int(((y == 0) & (pred == 0)).sum()))


def binary_metrics(y, pred, score=None) -> dict[str, float]:
    tp, fp, fn, tn = _counts(y, pred)
    m = {k: float(v) for k, v in binary_from_counts(tp, fp, fn, tn).items()}
    m.update(tp=tp, fp=fp, fn=fn, tn=tn)
    if score is not None:
        m["pr_auc"] = float(average_precision_score(y, score))
    return m


def bootstrap_ci(y, pred, n_boot: int = 2000, seed: int = 0, alpha: float = 0.05) -> dict[str, list[float]]:
    """Percentile CIs for every binary metric via multinomial resampling of confusion counts."""
    c = np.array(_counts(y, pred), dtype=float)
    draws = np.random.default_rng(seed).multinomial(int(c.sum()), c / c.sum(), size=n_boot)
    boot = binary_from_counts(*draws.T)
    lo, hi = 100 * alpha / 2, 100 * (1 - alpha / 2)
    return {k: [float(np.percentile(v, lo)), float(np.percentile(v, hi))] for k, v in boot.items()}


def multiclass_metrics(y, pred, labels) -> dict:
    return {
        "macro_f1": float(f1_score(y, pred, average="macro", labels=labels, zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "per_class_recall": dict(zip(labels, map(float, recall_score(y, pred, average=None, labels=labels, zero_division=0)))),
    }
