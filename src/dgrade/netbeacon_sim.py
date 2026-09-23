"""Packet-level emulator of NetBeacon's per-flow state machine (switch.p4 at commit 06c6127).

Replays packets in timestamp order through the data plane's slot logic and reports, per packet,
which model produced the verdict: a phase model of the full per-flow classifier, the verdict
memo, or the per-packet fallback tree. Paths below are relative to ``third_party/NetBeacon/``;
"sw" is ``switch/data_plane/switch.p4``, "hdr" ``headers.p4``, "prs" ``parsers.p4`` and "ctl"
``switch/control_plane/controller.py``. ``docs/g1_netbeacon_features.md`` §3-§4 derives the
semantics copied here.

Switch-faithful arithmetic reproduced:

* ``now = (bit<32>)global_tstamp >> 20`` and ``ipd_now = (bit<32>)global_tstamp >> 10``: the
  cast binds before the shift, so both wrap every 2^32 ns (sw:581, 617, 635). INFERRED.
* ``last_classified = now - stored`` in 32-bit arithmetic (sw:268), which opens an eviction
  window after every wrap; the idle threshold is 256 units (hdr:38, sw:609).
* A takeover does not refresh ``last_classified``; only a packet of the stored flow does
  (sw:610-626).
* Flow identity is the 32-bit CRC hash only, so equal hashes share a slot (sw:547, 583, 606).
* ``bin2`` is an 8-bit register (sw:124); totals, power sum and variance are unsigned 32-bit
  (sw:20-39, 182-216, 640-700); ``total_pkts`` is 16-bit (sw:42).

Modelling choices, stated rather than hidden:

* The recirculated copy that writes the result and flow-hash registers (sw:596-601) is taken
  to arrive before the next packet, i.e. recirculation is instantaneous.
* Controller memo inserts (ctl:40-80) take effect after ``memo_delay_ns`` (default 0).
* The hash is CRC-32 as computed by ``zlib`` over the 13-byte tuple, with each ``@symmetric``
  pair (addresses, ports; sw:16-17) normalised to ascending order. Tofino's CRC32 parameters and
  bf-p4c's symmetric-hash construction are INFERRED; exact slot numbers need hardware checks.
* ``MathUnit`` SQR (sw:181, 218) is modelled as an exact square through ``sqr``; its exactness
  on the switch is unverified.
* Of the parser's rejects (prs:58-85), only non-TCP/UDP protocols and UDP source port 68 are
  modelled; IP options and fragments are assumed absent.
"""

from __future__ import annotations

import zlib
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from dgrade.netbeacon import (
    FLOW_FEATURES,
    FLOW_SIZE_LONG_THRESHOLD,
    PHASES,
    PKT_FEATURES,
    NetBeaconTables,
)

__all__ = [
    "FALLBACK_COLLISION", "FALLBACK_EMPTY", "FALLBACK_SHORT", "MEMO", "NEW_OWNER", "OWNER", "REJECTED",
    "NetBeaconSim", "StubModels", "TableModels", "crc32_flow_hash", "flow_ids", "make_packets", "summarize",
]

# Per-packet outcome codes.
MEMO = 0                # Flow_result hit: verdict from the controller's memo (sw:605)
OWNER = 1               # packet of the flow stored in its slot (sw:625-716)
NEW_OWNER = 2           # first packet of a takeover (sw:608-620)
FALLBACK_COLLISION = 3  # predicted long, but the slot's incumbent is active and undetermined
FALLBACK_SHORT = 4      # predicted short: never takes a slot (sw:608)
REJECTED = 5            # dropped by the parser (prs:58-85)
FALLBACK_EMPTY = 6      # refused a never-claimed slot: zeroed registers look "active" while now < 256
                        # units after each clock wrap (sw:219, 259-268, 609). Not contention.

PACKET_DTYPE = np.dtype([
    ("ts_ns", np.int64), ("src_ip", np.uint32), ("dst_ip", np.uint32), ("src_port", np.uint16),
    ("dst_port", np.uint16), ("proto", np.uint8), ("total_len", np.uint16), ("ttl", np.uint8),
    ("diffserv", np.uint8), ("tcp_window", np.uint16), ("tcp_dataOffset", np.uint8),
    ("udp_length", np.uint16),
])

_M32 = 0xFFFFFFFF
_TIMEOUT_UNITS = 256            # hdr:38
_PHASE_SHIFT = {2: 3, 4: 2, 8: 1, 32: -1, 256: -4, 512: -5, 1024: -6, 2048: -7}  # sw:642-700
_LOG2 = {2: 1, 4: 2, 8: 3, 32: 5, 256: 8, 512: 9, 1024: 10, 2048: 11}
_BIN1_VALUE, _BIN2_VALUE, _BIN_MASK = 48, 80, 0xFFF0  # bin table reversed by ctl:263


def make_packets(**cols) -> np.ndarray:
    """Build a packet array, broadcasting scalars. Defaults: TTL 64, DSCP 0, TCP window 65535
    and data offset 5 for TCP, UDP length = total_len - 20 for UDP."""
    n = max(np.size(v) for v in cols.values())
    out = np.zeros(n, dtype=PACKET_DTYPE)
    out["ttl"] = 64
    for k, v in cols.items():
        out[k] = np.broadcast_to(np.asarray(v), n)
    tcp, udp = out["proto"] == 6, out["proto"] == 17
    if "tcp_window" not in cols:
        out["tcp_window"] = np.where(tcp, 65535, 0)
    if "tcp_dataOffset" not in cols:
        out["tcp_dataOffset"] = np.where(tcp, 5, 0)
    if "udp_length" not in cols:
        out["udp_length"] = np.where(udp, out["total_len"].astype(np.int64) - 20, 0)
    return out


def crc32_flow_hash(src_ip, dst_ip, src_port, dst_port, proto, salt: int | None = None) -> np.ndarray:
    """32-bit flow hash of sw:547 with both ``@symmetric`` pairs normalised. ``salt`` prepends a
    4-byte per-boot key (the keyed-hash baseline)."""
    a, b = np.minimum(src_ip, dst_ip), np.maximum(src_ip, dst_ip)
    p, q = np.minimum(src_port, dst_port), np.maximum(src_port, dst_port)
    tup = np.stack([a, b, p, q, proto], axis=1).astype(np.int64)
    uniq, inv = np.unique(tup, axis=0, return_inverse=True)
    prefix = b"" if salt is None else int(salt & _M32).to_bytes(4, "big")
    h = np.array([zlib.crc32(prefix + int(r[0]).to_bytes(4, "big") + int(r[1]).to_bytes(4, "big")
                             + int(r[2]).to_bytes(2, "big") + int(r[3]).to_bytes(2, "big") + bytes([int(r[4])]))
                  for r in uniq], dtype=np.uint32)
    return h[inv.reshape(-1)]


class StubModels:
    """Constant models for state-machine tests: every packet gets ``pkt_code`` and flow-size
    score ``flow_size``; phase N returns a code below 50, phase 2048 returns 60 (determined)."""

    def __init__(self, flow_size: int = 80, pkt_code: int = 1):
        self.fs, self.pc = flow_size, pkt_code

    def pkt_codes(self, pk: np.ndarray) -> np.ndarray:
        return np.full(len(pk), self.pc, dtype=np.int64)

    def flow_size(self, pk: np.ndarray) -> np.ndarray:
        return np.full(len(pk), self.fs, dtype=np.int64)

    def phase_codes(self, phase: int, feats: pd.DataFrame) -> np.ndarray:
        if phase not in PHASES:
            return np.zeros(len(feats), dtype=np.int64)
        return np.full(len(feats), 60 if phase == 2048 else 10 + PHASES.index(phase), dtype=np.int64)


class TableModels:
    """The shipped tables (:func:`dgrade.netbeacon.load_tables`) behind the models interface."""

    def __init__(self, tables: NetBeaconTables):
        self.t = tables

    @staticmethod
    def _pkt_rows(pk: np.ndarray) -> dict[str, np.ndarray]:
        return {f: pk[f].astype(np.int64) for f in PKT_FEATURES}

    def pkt_codes(self, pk: np.ndarray) -> np.ndarray:
        return self.t.pkt.result_codes(self._pkt_rows(pk))

    def flow_size(self, pk: np.ndarray) -> np.ndarray:
        s = self.t.flow_size.predict(self._pkt_rows(pk))
        return np.where(s < 0, 0, s)  # a Flow_Size_Tree miss leaves flow_size = 0 (sw:577)

    def phase_codes(self, phase: int, feats: pd.DataFrame) -> np.ndarray:
        if phase not in self.t.phases:  # 1024: no Flow_Tree entries (sw:687-694)
            return np.zeros(len(feats), dtype=np.int64)
        return self.t.phases[phase].result_codes(feats)


def sqr(x: int) -> int:
    """MathUnit SQR, modelled as an exact 32-bit square (unverified on the switch)."""
    return (x * x) & _M32


@dataclass
class NetBeaconSim:
    models: object
    n_slots: int = 65536                 # hdr:35
    timeout_units: int = _TIMEOUT_UNITS
    memo_size: int = 1500                # ctl:32 Register_Table_Size / 2 (ctl:53)
    memo_delay_ns: int = 0
    clock_offset_ns: int | None = None   # switch clock at ts_ns == 0; None draws one from ``seed``
    keyed: bool = False
    seed: int | None = None
    square: Callable[[int], int] = field(default=sqr)

    def run(self, pk: np.ndarray, isolate: np.ndarray | None = None) -> dict[str, np.ndarray]:
        """Replay ``pk``. With ``isolate`` (a flow id per packet, e.g. from :func:`flow_ids`), every
        flow gets its own slot and a never-claimed slot is always claimable: the counterfactual
        "this flow had a slot", used as the full-model reference for H1."""
        pk = np.asarray(pk)
        if np.any(np.diff(pk["ts_ns"]) < 0):
            raise ValueError("packets must be in timestamp order")
        n = len(pk)
        rng = np.random.default_rng(self.seed)
        salt = int(rng.integers(0, 2**32)) if self.keyed else None
        offset = int(rng.integers(0, 2**32)) if self.clock_offset_ns is None else int(self.clock_offset_ns)
        if isolate is None:
            fh = crc32_flow_hash(pk["src_ip"], pk["dst_ip"], pk["src_port"], pk["dst_port"], pk["proto"], salt)
            S = self.n_slots
            slot = (fh & (S - 1)) if S & (S - 1) == 0 else fh % S
        else:
            iso = np.asarray(isolate, dtype=np.int64)
            fh = (iso + 1).astype(np.uint32)
            slot, S = iso, int(iso.max()) + 1 if n else 1
        pkt_code = self.models.pkt_codes(pk)
        long_ = self.models.flow_size(pk) > FLOW_SIZE_LONG_THRESHOLD
        t32 = (pk["ts_ns"].astype(np.int64) + offset) & _M32
        now_a, ipd_a = (t32 >> 20).tolist(), (t32 >> 10).tolist()
        rejected = ~np.isin(pk["proto"], (6, 17)) | ((pk["proto"] == 17) & (pk["src_port"] == 68))

        r_hash, r_res, r_lastc, claimed = [0] * S, [0] * S, [0] * S, [False] * S
        r_pk, r_by, r_mn, r_mx, r_ps = [0] * S, [0] * S, [0] * S, [0] * S, [0] * S
        r_lts, r_mipd, r_b1, r_b2, r_epoch = [0] * S, [0] * S, [0] * S, [0] * S, [-1] * S

        outcome = np.empty(n, dtype=np.int8)
        vkind = np.zeros(n, dtype=np.int8)     # 0 per-packet, 1 memo, 2 stored epoch value
        vepoch = np.full(n, -1, dtype=np.int64)
        vevent = np.zeros(n, dtype=np.int64)   # number of the epoch's phase events so far
        memo_val = np.zeros(n, dtype=np.int64)
        epoch_init: list[int] = []             # takeover packet index per epoch
        epoch_events: list[list[int]] = []     # event ids per epoch
        ev_phase: list[int] = []
        ev_pkt: list[int] = []
        ev_feat: list[tuple] = []
        ev_code: dict[int, int] = {}           # 2048 events are evaluated at once (they gate)

        memo: OrderedDict = OrderedDict()      # canonical key -> result (ctl:48-80)
        memo_dir: dict = {}                    # directional 5-tuple -> result
        pending: list = []                     # (time, key, dirs, result)

        src, dst = pk["src_ip"].tolist(), pk["dst_ip"].tolist()
        sp, dp, pr = pk["src_port"].tolist(), pk["dst_port"].tolist(), pk["proto"].tolist()
        ln, ts = pk["total_len"].tolist(), pk["ts_ns"].tolist()
        fh_l, sl_l, lg_l, pc_l, rj_l = fh.tolist(), slot.tolist(), long_.tolist(), pkt_code.tolist(), rejected.tolist()
        sq = self.square

        for i in range(n):
            while pending and pending[0][0] <= ts[i]:
                _, key, dirs, res = pending.pop(0)
                self._memo_insert(memo, memo_dir, key, dirs, res, self.memo_size)
            if rj_l[i]:
                outcome[i] = REJECTED
                continue
            d5 = (src[i], dst[i], sp[i], dp[i], pr[i])
            if d5 in memo_dir:                                   # sw:605
                outcome[i], vkind[i], memo_val[i] = MEMO, 1, memo_dir[d5]
                continue
            s, h, L, now = sl_l[i], fh_l[i], ln[i], now_a[i]
            if h != r_hash[s]:                                    # new flow at this slot (sw:606)
                lastc = (now - r_lastc[s]) & _M32                 # sw:268
                if not lg_l[i]:
                    outcome[i] = FALLBACK_SHORT
                elif r_res[s] < 50 and lastc < self.timeout_units and (claimed[s] or isolate is None):
                    outcome[i] = FALLBACK_COLLISION if claimed[s] else FALLBACK_EMPTY
                else:                                             # takeover (sw:610-620)
                    outcome[i] = NEW_OWNER
                    claimed[s] = True
                    r_hash[s], r_pk[s], r_by[s], r_mn[s], r_mx[s] = h, 1, L, L, L
                    r_ps[s] = sq(L >> 2)
                    r_lts[s], r_mipd[s] = ipd_a[i], _M32
                    r_b1[s] = int((L & _BIN_MASK) == _BIN1_VALUE)
                    r_b2[s] = int((L & _BIN_MASK) == _BIN2_VALUE)
                    r_res[s] = pc_l[i]                            # recirculated copy (sw:596-601)
                    r_epoch[s] = len(epoch_init)
                    epoch_init.append(i)
                    epoch_events.append([])
                continue                                          # verdict: Pkt_Tree (sw:623, 722)
            outcome[i] = OWNER
            r_lastc[s] = now                                      # sw:626
            e = r_epoch[s]
            if r_res[s] < 50:                                     # sw:627
                if (L & _BIN_MASK) == _BIN1_VALUE:
                    r_b1[s] = (r_b1[s] + 1) & 0xFFFF
                if (L & _BIN_MASK) == _BIN2_VALUE:
                    r_b2[s] = (r_b2[s] + 1) & 0xFF                # 8-bit (sw:124)
                r_pk[s] = (r_pk[s] + 1) & 0xFFFF
                r_by[s] = (r_by[s] + L) & _M32
                r_mn[s], r_mx[s] = min(r_mn[s], L), max(r_mx[s], L)
                r_ps[s] = (r_ps[s] + sq(L >> 2)) & _M32
                ipd = (ipd_a[i] - r_lts[s]) & _M32                # sw:142
                r_lts[s] = ipd_a[i]
                r_mipd[s] = min(r_mipd[s], ipd)
                N = r_pk[s]
                if N in _PHASE_SHIFT:
                    avg = r_by[s] >> _LOG2[N]
                    k = _PHASE_SHIFT[N]
                    pw = (r_ps[s] << k) & _M32 if k > 0 else r_ps[s] >> -k
                    var = (pw - sq(avg)) & _M32
                    feat = (r_mx[s], r_mipd[s], r_b2[s], r_b1[s], var, avg, r_mn[s])
                    ev = len(ev_phase)
                    ev_phase.append(N)
                    ev_pkt.append(i)
                    ev_feat.append(feat)
                    epoch_events[e].append(ev)
                    if N == 2048:
                        code = int(self.models.phase_codes(2048, pd.DataFrame([feat], columns=FLOW_FEATURES))[0])
                        ev_code[ev] = code
                        if code:
                            r_res[s] = code
                        if code > 50:                             # digest (sw:710-712)
                            canon = _canon(d5)
                            dirs = (d5, (d5[1], d5[0], d5[3], d5[2], d5[4]))
                            pending.append((ts[i] + self.memo_delay_ns, canon, dirs, code))
                            pending.sort(key=lambda x: x[0])
            vkind[i], vepoch[i], vevent[i] = 2, e, len(epoch_events[e])

        codes = self._evaluate_events(ev_phase, ev_feat, ev_code)
        out = self._resolve(pk, fh, slot, outcome, vkind, vepoch, vevent, memo_val, pkt_code,
                            epoch_init, epoch_events, ev_phase, ev_pkt, codes, long_)
        out["clock_offset_ns"] = offset
        return out

    @staticmethod
    def _memo_insert(memo, memo_dir, key, dirs, res, size):
        if key in memo:                                           # ctl:50-52
            return
        if len(memo) >= size and len(memo) > 0:                   # FIFO: drop the first 10 (ctl:53-72)
            for _ in range(min(10, len(memo))):
                _, (old_dirs, _) = memo.popitem(last=False)
                for dd in old_dirs:
                    memo_dir.pop(dd, None)
        memo[key] = (dirs, res)
        for dd in dirs:
            memo_dir[dd] = res

    def _evaluate_events(self, ev_phase, ev_feat, ev_code) -> np.ndarray:
        codes = np.zeros(len(ev_phase), dtype=np.int64)
        if not ev_phase:
            return codes
        ph = np.asarray(ev_phase)
        F = pd.DataFrame(ev_feat, columns=FLOW_FEATURES)
        for p in np.unique(ph):
            idx = np.flatnonzero(ph == p)
            if p == 2048:
                codes[idx] = [ev_code[int(j)] for j in idx]
            else:
                c = np.asarray(self.models.phase_codes(int(p), F.iloc[idx].reset_index(drop=True)))
                if np.any(c >= 50):
                    raise ValueError(f"phase {p} returned a determined code; only 2048 may")
                codes[idx] = c
        return codes

    @staticmethod
    def _resolve(pk, fh, slot, outcome, vkind, vepoch, vevent, memo_val, pkt_code,
                 epoch_init, epoch_events, ev_phase, ev_pkt, codes, long_) -> dict[str, np.ndarray]:
        # Sticky stored value per (epoch, number of events so far): a Flow_Tree miss keeps it.
        state_val, state_src = [], []
        for e, init in enumerate(epoch_init):
            v, sname = int(pkt_code[init]), "pkt"
            vals, srcs = [v], [sname]
            for ev in epoch_events[e]:
                if codes[ev]:
                    v, sname = int(codes[ev]), f"phase-{ev_phase[ev]}"
                elif v == 0:
                    # Flow_Tree missed on a stored 0: Pkt_Tree runs on the phase packet and the
                    # recirculated copy stores its verdict (sw:598, 712, 722, 729)
                    v, sname = int(pkt_code[ev_pkt[ev]]), "pkt"
                vals.append(v)
                srcs.append(sname)
            state_val.append(vals)
            state_src.append(srcs)
        n = len(pk)
        result = pkt_code.astype(np.int64).copy()
        source = np.array(["pkt"] * n, dtype=object)
        source[outcome == REJECTED] = "none"
        result[outcome == REJECTED] = 0
        m = vkind == 1
        result[m], source[m] = memo_val[m], "memo"
        for i in np.flatnonzero(vkind == 2):
            v = state_val[vepoch[i]][vevent[i]]
            if v:  # a stored 0 lets Pkt_Tree run (sw:722)
                result[i], source[i] = v, state_src[vepoch[i]][vevent[i]]
        out = {name: pk[name] for name in pk.dtype.names}
        out.update(flow_hash=fh, slot=slot, outcome=outcome, result=result, source=source,
                   predicted_long=long_)
        return out


def _canon(d5):
    a, b = (d5[0], d5[2]), (d5[1], d5[3])
    return (min(a, b), max(a, b), d5[4])


def flow_ids(pk, idle_ns: int = 256_000_000) -> np.ndarray:
    """Flow id per packet: the bidirectional 5-tuple (the two endpoint (address, port) pairs in
    sorted order, plus the protocol), split whenever a packet follows its predecessor by more
    than ``idle_ns``. The 256 ms default matches BoS's flow splitting."""
    a = np.stack([pk["src_ip"].astype(np.int64), pk["src_port"].astype(np.int64)], axis=1)
    b = np.stack([pk["dst_ip"].astype(np.int64), pk["dst_port"].astype(np.int64)], axis=1)
    swap = (a[:, 0] > b[:, 0]) | ((a[:, 0] == b[:, 0]) & (a[:, 1] > b[:, 1]))
    lo, hi = np.where(swap[:, None], b, a), np.where(swap[:, None], a, b)
    key = np.stack([lo[:, 0], lo[:, 1], hi[:, 0], hi[:, 1], pk["proto"].astype(np.int64)], axis=1)
    _, kid = np.unique(key, axis=0, return_inverse=True)
    kid = kid.reshape(-1)
    order = np.lexsort((pk["ts_ns"], kid))
    ks, ts = kid[order], pk["ts_ns"].astype(np.int64)[order]
    new = np.ones(len(ks), dtype=bool)
    new[1:] = (ks[1:] != ks[:-1]) | (np.diff(ts) > idle_ns)
    fid = np.empty(len(ks), dtype=np.int64)
    fid[order] = np.cumsum(new) - 1
    return fid


def summarize(out: dict[str, np.ndarray], idle_ns: int = 256_000_000) -> pd.DataFrame:
    """Per flow (:func:`flow_ids`): packets, share verdicted by the full model (phase or memo),
    and ``downgraded`` (docs/preregistration.md): the flow had a path to the full model (some
    packet predicted long; Flow_Size_Tree runs on every packet, sw:593, 608), yet a packet was
    refused a slot by an active incumbent, or the flow lost its slot and had to retake it (state
    reset). Refusals at never-claimed slots (FALLBACK_EMPTY) are counted but are not contention."""
    fid = flow_ids(out, idle_ns)
    df = pd.DataFrame({k: out[k] for k in ("src_ip", "dst_ip", "src_port", "dst_port", "proto", "outcome",
                                           "source", "predicted_long")})
    df["flow_id"] = fid
    df = df[df.outcome != REJECTED]
    rows = []
    for f, g in df.groupby("flow_id", sort=False):
        oc = g.outcome.to_numpy()
        coll = int(np.sum(oc == FALLBACK_COLLISION))
        owned = np.isin(oc, (NEW_OWNER, OWNER))
        first_owned = int(np.argmax(owned)) if owned.any() else len(oc)
        resets = int(np.sum(oc[first_owned + 1:] == NEW_OWNER))
        eligible = bool(g.predicted_long.any())
        first = g.iloc[0]
        rows.append({"flow_id": int(f), "src_ip": first.src_ip, "dst_ip": first.dst_ip,
                     "src_port": first.src_port, "dst_port": first.dst_port, "proto": first.proto,
                     "n_pkts": len(g), "frac_full": float(np.mean(g.source.to_numpy() != "pkt")),
                     "predicted_long": eligible, "collisions": coll, "resets": resets,
                     "empty_refusals": int(np.sum(oc == FALLBACK_EMPTY)),
                     "downgraded": eligible and (coll > 0 or resets > 0)})
    return pd.DataFrame(rows)
