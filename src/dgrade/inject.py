"""Analytical holder-flow injection for G2b (docs/preregistration.md, G2b entry).

This models an adversary as an *abstraction*: attacker flows are given the slot indices they occupy (K1, an
adversary with slot control, an upper bound) or land on uniformly random slots (K0, a secret hash). No hash
search, no crafted headers for a real network. Each flow sends one packet per ``interval_ns`` from a random
start inside the ramp until the slice ends, so it stays active and undetermined; flows are stopped before 2048
packets (rotation cost is computed analytically because the slice is shorter than one rotation).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from dgrade.netbeacon_sim import PACKET_DTYPE

__all__ = ["Attack", "Merged", "build_fill", "merge_attack"]

MAX_PACKETS_PER_FLOW = 2000


@dataclass
class Attack:
    pk: np.ndarray        # attacker packets, PACKET_DTYPE
    flow: np.ndarray      # attacker flow number per packet
    slot: np.ndarray      # slot per packet
    hash: np.ndarray      # 32-bit identity per packet (distinct per flow)


@dataclass
class Merged:
    pk: np.ndarray
    slot: np.ndarray
    hash: np.ndarray
    force_long: np.ndarray
    is_attacker: np.ndarray


def build_fill(f: float, mode: str, n_slots: int, span_ns: int, rng: np.random.Generator,
               interval_ns: int = 250_000_000, ramp_ns: int = 5_000_000_000) -> Attack:
    """Holder flows aimed at a fraction ``f`` of the table. ``mode``: ``k1`` distinct given slots, ``k0`` uniform slots."""
    n_flows = round(f * n_slots)
    if mode == "k1":
        slots = rng.choice(n_slots, n_flows, replace=False)
    elif mode == "k0":
        slots = rng.integers(0, n_slots, n_flows)
    else:
        raise ValueError(f"unknown mode {mode!r}")
    ident = rng.choice(2**32 - 1, n_flows, replace=False).astype(np.uint32) + 1
    start = rng.integers(0, ramp_ns, n_flows)
    n_pk = np.minimum((span_ns - start) // interval_ns + 1, MAX_PACKETS_PER_FLOW)
    flow = np.repeat(np.arange(n_flows), n_pk)
    k = np.arange(len(flow)) - np.repeat(np.cumsum(n_pk) - n_pk, n_pk)
    pk = np.zeros(len(flow), dtype=PACKET_DTYPE)
    pk["ts_ns"] = start[flow] + k * interval_ns
    pk["src_ip"] = (0xC6120000 + flow).astype(np.uint32)       # 198.18.0.0/15, the benchmarking block
    pk["dst_ip"], pk["src_port"], pk["dst_port"], pk["proto"] = 0xC6130001, 1024, 80, 6
    pk["total_len"], pk["ttl"], pk["tcp_window"], pk["tcp_dataOffset"] = 60, 64, 1024, 5
    return Attack(pk, flow, slots[flow].astype(np.int64), ident[flow])


def merge_attack(benign: np.ndarray, b_slot: np.ndarray, b_hash: np.ndarray, atk: Attack) -> Merged:
    """Benign and attacker packets in one stable time-ordered stream, with per-packet slot, identity and long flag."""
    pk = np.concatenate([benign, atk.pk])
    slot = np.concatenate([b_slot, atk.slot])
    h = np.concatenate([b_hash, atk.hash])
    is_atk = np.concatenate([np.zeros(len(benign), dtype=bool), np.ones(len(atk.pk), dtype=bool)])
    o = np.argsort(pk["ts_ns"], kind="stable")
    return Merged(pk[o], slot[o], h[o], is_atk[o].copy(), is_atk[o])
