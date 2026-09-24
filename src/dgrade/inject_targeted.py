"""Targeted-displacement holders for G2b (docs/preregistration.md, G2b targeted-arm entry).

Analytical abstraction, like :mod:`dgrade.inject`: a K1 adversary is *given* the slot of each victim; no hash
search or crafted packets are modelled. A holder is a long-predicted flow that sends one packet per 250 ms, so
its slot stays active and undetermined, until the slice ends.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from dgrade.flowstats import FlowIndex
from dgrade.inject import MAX_PACKETS_PER_FLOW, Attack, build_fill
from dgrade.netbeacon_sim import PACKET_DTYPE

__all__ = ["TargetedAttack", "Victim", "build_targeted", "random_holders", "select_victims"]

MS = 1_000_000
GAP_NS = 300 * MS             # a victim gap longer than this can be used by a reactive holder
REACT_DELAY_NS = 275 * MS     # holder starts this long after the victim's last packet (idle > 256 units = 268.4 ms)
LEAD_NS = 500 * MS            # a preempting holder starts this long before the victim's first packet


@dataclass
class Victim:
    flow: int
    slot: int
    n_packets: int
    first_ts: int
    gap_start_ts: int | None     # timestamp of the victim's last packet before its first gap longer than GAP_NS


@dataclass
class TargetedAttack(Attack):
    failed: list[int] = field(default_factory=list)      # victim flow numbers with no usable gap (reactive only)


def select_victims(pk: np.ndarray, idx: FlowIndex, flow_slot: np.ndarray, kind: str, k: int = 20) -> list[Victim]:
    """``top``: the k largest flows with more than 50 packets. ``vulnerable``: the k largest flows with 51 to 2047
    packets (never determined, so always exposed to the slot logic)."""
    n = idx.n_pkts
    ok = (n > 50) if kind == "top" else ((n > 50) & (n < 2048))
    if kind not in ("top", "vulnerable"):
        raise ValueError(f"unknown victim kind {kind!r}")
    score = np.where(ok, n, 0)
    out = []
    for f in np.argsort(-score, kind="stable")[:k]:
        if score[f] == 0:
            break
        t = pk["ts_ns"][idx.order[idx.start[f]:idx.start[f] + n[f]]]
        gaps = np.flatnonzero(np.diff(t) > GAP_NS)
        out.append(Victim(int(f), int(flow_slot[f]), int(n[f]), int(t[0]), int(t[gaps[0]]) if len(gaps) else None))
    return out


def _holders(start: np.ndarray, slots: np.ndarray, span_ns: int, rng: np.random.Generator,
             interval_ns: int) -> Attack:
    n_flows = len(start)
    ident = rng.choice(2**32 - 1, n_flows, replace=False).astype(np.uint32) + 1
    n_pk = np.clip((span_ns - start) // interval_ns + 1, 0, MAX_PACKETS_PER_FLOW)
    flow = np.repeat(np.arange(n_flows), n_pk)
    k = np.arange(len(flow)) - np.repeat(np.cumsum(n_pk) - n_pk, n_pk)
    pk = np.zeros(len(flow), dtype=PACKET_DTYPE)
    pk["ts_ns"] = start[flow] + k * interval_ns
    pk["src_ip"] = (0xC6120000 + flow).astype(np.uint32)       # 198.18.0.0/15, the benchmarking block
    pk["dst_ip"], pk["src_port"], pk["dst_port"], pk["proto"] = 0xC6130001, 1024, 80, 6
    pk["total_len"], pk["ttl"], pk["tcp_window"], pk["tcp_dataOffset"] = 60, 64, 1024, 5
    return Attack(pk, flow, slots[flow].astype(np.int64), ident[flow])


def build_targeted(victims: list[Victim], mode: str, span_ns: int, rng: np.random.Generator,
                   interval_ns: int = 250 * MS) -> TargetedAttack:
    """One holder per victim, on the victim's slot. ``preempt`` starts before the victim's first packet;
    ``reactive`` starts inside the victim's first long gap (victims with none are recorded in ``failed``)."""
    if mode not in ("preempt", "reactive"):
        raise ValueError(f"unknown mode {mode!r}")
    keep, start, failed = [], [], []
    for k, v in enumerate(victims):
        if mode == "preempt":
            keep.append(k)
            start.append(v.first_ts - LEAD_NS)      # may be before the slice: the adversary was already holding
        elif v.gap_start_ts is None:
            failed.append(v.flow)
        else:
            keep.append(k)
            start.append(v.gap_start_ts + REACT_DELAY_NS)
    slots = np.array([victims[k].slot for k in keep], dtype=np.int64)
    a = _holders(np.array(start, dtype=np.int64), slots, span_ns, rng, interval_ns)
    return TargetedAttack(a.pk, a.flow, a.slot, a.hash, failed=failed)


def random_holders(h: int, span_ns: int, rng: np.random.Generator, n_slots: int = 65536,
                   interval_ns: int = 250 * MS, ramp_ns: int = 5_000_000_000) -> Attack:
    """H long holder flows on uniformly random slots (B0-L with the unkeyed benign hash, K0 with the keyed one)."""
    return build_fill(h / n_slots, "k0", n_slots, span_ns, rng, interval_ns, ramp_ns)
