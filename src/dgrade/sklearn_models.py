"""Retrained NetBeacon-style models (scikit-learn trees) behind the emulator's models interface (docs/preregistration.md, G7).

Same contract as :class:`dgrade.netbeacon_sim.TableModels`: ``pkt_codes(pk)`` returns class + 1 per packet, ``flow_size(pk)`` a score in 0..100
(the tree's probability of a long flow times 100, rounded; a flow is long if the score is above 50), ``phase_codes(phase, feats)`` returns class + 1
(plus 50 at phase 2048, as the controller adds 50) and zeros at phases with no model. These are retrained models, not the shipped ones; the
emulator evaluates the trees directly, so no switch-table quantisation of the retrained trees is modelled.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dgrade.netbeacon import FLOW_FEATURES, PKT_FEATURES

__all__ = ["SklearnModels"]


class SklearnModels:
    def __init__(self, pkt, size, phases: dict):
        self.pkt, self.size, self.phases = pkt, size, phases

    @staticmethod
    def _pkt_matrix(pk: np.ndarray) -> np.ndarray:
        return np.stack([pk[f].astype(np.int64) for f in PKT_FEATURES], axis=1)

    def _unique(self, pk: np.ndarray):
        X = self._pkt_matrix(pk)
        u, inv = np.unique(X, axis=0, return_inverse=True)
        return u, inv.reshape(-1)

    def pkt_codes(self, pk: np.ndarray) -> np.ndarray:
        u, inv = self._unique(pk)
        return (self.pkt.predict(u).astype(np.int64) + 1)[inv]

    def flow_size(self, pk: np.ndarray) -> np.ndarray:
        u, inv = self._unique(pk)
        proba = self.size.predict_proba(u)
        col = list(self.size.classes_).index(1) if 1 in list(self.size.classes_) else None
        score = np.zeros(len(u)) if col is None else proba[:, col]
        return np.round(score * 100).astype(np.int64)[inv]

    def phase_codes(self, phase: int, feats: pd.DataFrame) -> np.ndarray:
        if phase not in self.phases:
            return np.zeros(len(feats), dtype=np.int64)
        X = feats[list(FLOW_FEATURES)].to_numpy() if hasattr(feats, "columns") else np.asarray(feats)
        return self.phases[phase].predict(X).astype(np.int64) + 1 + (50 if phase == 2048 else 0)
