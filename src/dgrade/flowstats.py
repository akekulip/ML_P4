"""Fast per-flow aggregation over a packet stream, used by the G1 and G1b reports.

A :class:`FlowIndex` is built once per stream (sorting packets by flow); every run then costs a few
vectorised passes instead of a pandas groupby.
"""

from __future__ import annotations

import numpy as np

from dgrade.netbeacon_sim import FALLBACK_COLLISION, FALLBACK_SHORT, NEW_OWNER, OWNER

__all__ = ["FlowIndex", "downgraded_flows"]


class FlowIndex:
    """Contiguous flow numbers ``0..n_flows-1`` (ascending by flow id) for a packet array."""

    def __init__(self, flow_id: np.ndarray):
        uniq, self.code = np.unique(np.asarray(flow_id), return_inverse=True)
        self.code = self.code.reshape(-1)
        self.n_flows = len(uniq)
        self.order = np.argsort(self.code, kind="stable")          # packets grouped by flow, in time order
        counts = np.bincount(self.code, minlength=self.n_flows)
        self.start = np.concatenate([[0], np.cumsum(counts)[:-1]])
        self.seg = np.repeat(np.arange(self.n_flows), counts)      # flow number per sorted packet
        self.n_pkts = counts

    def per_flow_sum(self, x: np.ndarray) -> np.ndarray:
        return np.bincount(self.code, weights=np.asarray(x, dtype=np.float64), minlength=self.n_flows)


def downgraded_flows(outcome: np.ndarray, idx: FlowIndex) -> np.ndarray:
    """Boolean per flow: refused a slot by an active holder, or displaced after holding one (took a slot
    again, or fell back as "predicted short" once it had held one). Empty-slot refusals and flows that
    were predicted short from their first packet are not counted (docs/preregistration.md)."""
    oc = np.asarray(outcome)[idx.order]
    coll = np.bincount(idx.seg, weights=(oc == FALLBACK_COLLISION), minlength=idx.n_flows) > 0
    owned = ((oc == OWNER) | (oc == NEW_OWNER)).astype(np.int64)
    cs = np.cumsum(owned)
    seen = cs - owned - (cs[idx.start] - owned[idx.start])[idx.seg]     # owned packets earlier in the same flow
    # A flow that held a slot and later takes one again, or is answered as "predicted short" although it
    # once held one (a stored hash mismatch there means the slot was lost), was displaced by contention.
    lost = np.bincount(idx.seg, weights=(((oc == NEW_OWNER) | (oc == FALLBACK_SHORT)) & (seen > 0)),
                       minlength=idx.n_flows) > 0
    return coll | lost
