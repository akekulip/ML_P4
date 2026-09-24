"""Compiled-semantics emulator for NetBeacon and D4c on Tofino-1 (docs/preregistration.md, G8 entry).

``netbeacon_sim.NetBeaconSim`` is the abstract emulator that produced the G1 to G7 results and is left untouched. ``TofinoSim`` reproduces what the
compiled D4c P4 program (``p4/dgrade_d4c/switch.p4``, offline compile in ``docs/results_d4c_compile.md``) does that the abstract emulator does not:

* **Pass 2 with a delay.** A takeover packet initialises the feature registers in pass 1 but the tag and the result register are written only after a
  recirculation delay ``claim_delay_ns``. Until then the slot still shows its old tag and result: a further packet of the same flow runs Init again
  (features reset), a second newcomer can take the same slot (the last claim wins while the features hold the later Init), and a flow can end up owning
  both ways (way A is preferred and way B stays pinned by its refreshed last-seen time).
* **Phase recirculations.** Every owner packet that reaches a phase recirculates and its pass 2 rewrites the tag and the result of its way unconditionally, so an
  owner can retake a slot that a newcomer took in between.
* **Owner refresh in the probe.** Every way whose tag equals the packet's tag refreshes its last-seen time in pass 1.
* **Wrapped 12-bit clock** (a never-claimed slot looks held during the first 256 units of each window), no takeover refresh, no rent: only the shipped clock.
* **Fold hash** (:func:`fold_hash_unique`): both CRCs are computed over a message in which the two addresses are XORed into one lane and the two ports into
  another, so tuples with equal folds share slots and the tag. The lane positions and bit order are unverified; the alias structure does not depend on them.

With ``claim_delay_ns = 0`` and the abstract emulator's slot and tag arrays the results equal ``NetBeaconSim`` (two_way, policy ``unclaimed_first``, or one
table) bit for bit; that is the module's hard test. Only fully forced slots are supported (the caller computes tags and slots), and the isolated reference
run stays with the abstract emulator.
"""

from __future__ import annotations

import heapq
from collections import OrderedDict
from dataclasses import dataclass

import numpy as np
import pandas as pd

from dgrade.netbeacon import FLOW_FEATURES, FLOW_SIZE_LONG_THRESHOLD
from dgrade.netbeacon_sim import (
    _BIN1_VALUE,
    _BIN2_VALUE,
    _BIN_MASK,
    _LOG2,
    _M32,
    _PHASE_SHIFT,
    FALLBACK_COLLISION,
    FALLBACK_EMPTY,
    FALLBACK_SHORT,
    MEMO,
    NEW_OWNER,
    OWNER,
    REJECTED,
    NetBeaconSim,
    _canon,
    crc_poly,
    irreducible_reflected_poly,
)

__all__ = ["TofinoSim", "fold_hash_unique", "fold_keys"]

_STD_POLY = 0xEDB88320


def fold_keys(uniq: np.ndarray) -> np.ndarray:
    """XOR-folded key (src ^ dst, sport ^ dport, proto) of each distinct tuple of :func:`dgrade.netbeacon_sim.tuple_table`."""
    a, b, p, q, proto = (uniq[:, k].astype(np.int64) for k in range(5))
    return np.stack([a ^ b, p ^ q, proto], axis=1)


def _fold_message(k) -> bytes:
    """104-bit message, big-endian: protocol in bits 7..0, the port fold in bits 23..8, the address fold in bits 71..40 (lane positions as in the compiled expression)."""
    m = int(k[2]) | (int(k[1]) << 8) | (int(k[0]) << 40)
    return m.to_bytes(13, "big")


def fold_hash_unique(uniq: np.ndarray, poly: int = _STD_POLY) -> np.ndarray:
    """32-bit CRC (reflected, init and final XOR 0xFFFFFFFF) of the fold message of each distinct tuple; equal folds get equal hashes."""
    kf = fold_keys(uniq)
    ku, inv = np.unique(kf, axis=0, return_inverse=True)
    h = np.array([crc_poly(_fold_message(k), poly) for k in ku], dtype=np.uint32)
    return h[inv.reshape(-1)]


def poly_b(seed: int = 7919) -> int:
    """Reflected polynomial of hash B (the compiled program's coefficient 0x09c8be85 for seed 7919)."""
    return irreducible_reflected_poly(np.random.default_rng(seed))


@dataclass
class TofinoSim(NetBeaconSim):
    claim_delay_ns: int = 0             # recirculation delay between the takeover packet (pass 1) and the tag and result write (pass 2)
    ways: int = 2                       # 2 = D4c (table A in slots below n_slots/2, table B above); 1 = the one-table NetBeacon

    def run(self, pk: np.ndarray, isolate=None, force_slot=None, force_hash=None, force_long=None, force_slot2=None) -> dict[str, np.ndarray]:
        if isolate is not None:
            raise ValueError("TofinoSim does not run the isolated reference; use NetBeaconSim")
        if force_slot is None or force_hash is None:
            raise ValueError("TofinoSim needs force_slot and force_hash (the caller computes tags and slots)")
        if not self.wrap_window or self.takeover_refresh or self.fix_ipd_wrap or self.rent is not None or self.two_way:
            raise ValueError("TofinoSim reproduces the shipped wrapped clock only (wrap_window=True, no D1, no rent); choose the layout with ``ways``")
        if self.ways not in (1, 2):
            raise ValueError("ways must be 1 or 2")
        pk = np.asarray(pk)
        if np.any(np.diff(pk["ts_ns"]) < 0):
            raise ValueError("packets must be in timestamp order")
        n, S = len(pk), self.n_slots
        two = self.ways == 2
        slot = np.asarray(force_slot, dtype=np.int64)
        fh = np.asarray(force_hash, dtype=np.uint32)
        slot2 = None
        if two:
            if S % 2 or force_slot2 is None:
                raise ValueError("two ways need an even n_slots and force_slot2")
            slot2 = np.asarray(force_slot2, dtype=np.int64)
            if np.any(slot >= S // 2) or np.any(slot2 < S // 2) or np.any(slot2 >= S):
                raise ValueError("table A slots must lie below n_slots/2 and table B slots in [n_slots/2, n_slots)")
        offset = int(self.clock_offset_ns) if self.clock_offset_ns is not None else 0
        pkt_code = self.models.pkt_codes(pk)
        long_ = self.models.flow_size(pk) > FLOW_SIZE_LONG_THRESHOLD
        if force_long is not None:
            long_ = long_ | np.asarray(force_long, dtype=bool)
        t32 = (pk["ts_ns"].astype(np.int64) + offset) & _M32
        now_a, ipd_a = t32 >> 20, t32 >> 10
        rejected = ~np.isin(pk["proto"], (6, 17)) | ((pk["proto"] == 17) & (pk["src_port"] == 68))

        r_tag, r_res, r_lastc, claimed = [0] * S, [0] * S, [0] * S, [False] * S
        r_pk, r_by, r_mn, r_mx, r_ps = [0] * S, [0] * S, [0] * S, [0] * S, [0] * S
        r_lts, r_mipd, r_b1, r_b2, r_epoch = [0] * S, [0] * S, [0] * S, [0] * S, [-1] * S
        f_tag = [-1] * S                                # tag of the flow whose Init last reset the feature registers of the slot
        pend_by_slot: dict[int, list[int]] = {}         # slot -> tags of claims still in flight
        cnt = {"takeovers": 0, "reinit_same_flow": 0, "second_newcomer": 0, "dual_owner_claims": 0, "contaminated_packets": 0, "owner_packets": 0}
        dual_flows: set[int] = set()

        outcome = np.empty(n, dtype=np.int8)
        vkind = np.zeros(n, dtype=np.int8)
        vepoch = np.full(n, -1, dtype=np.int64)
        vevent = np.zeros(n, dtype=np.int64)
        memo_val = np.zeros(n, dtype=np.int64)
        epoch_init: list[int] = []
        epoch_events: list[list[int]] = []
        ev_phase: list[int] = []
        ev_pkt: list[int] = []
        ev_feat: list[tuple] = []
        ev_code: dict[int, int] = {}

        memo: OrderedDict = OrderedDict()
        memo_dir: dict = {}
        pending: list = []                              # memo digests (time, key, dirs, result)
        claims: list = []                               # in-flight pass-2 writes: (time, seq, kind, slot, tag, value)
        seq = 0
        sq, timeout, delay = self.square, self.timeout_units, int(self.claim_delay_ns)

        chunk = 1 << 20
        for base in range(0, n, chunk):
            end = min(base + chunk, n)
            sl = slice(base, end)
            src, dst = pk["src_ip"][sl].tolist(), pk["dst_ip"][sl].tolist()
            sp, dp, pr = pk["src_port"][sl].tolist(), pk["dst_port"][sl].tolist(), pk["proto"][sl].tolist()
            ln, ts = pk["total_len"][sl].tolist(), pk["ts_ns"][sl].tolist()
            fh_l, sl_l, lg_l = fh[sl].tolist(), slot[sl].tolist(), long_[sl].tolist()
            sl2_l = slot2[sl].tolist() if two else None
            pc_l, rj_l = pkt_code[sl].tolist(), rejected[sl].tolist()
            nw_l, ip_l = now_a[sl].tolist(), ipd_a[sl].tolist()
            for j in range(end - base):
                i = base + j
                while pending and pending[0][0] <= ts[j]:
                    _, key, dirs, res = pending.pop(0)
                    self._memo_insert(memo, memo_dir, key, dirs, res, self.memo_size)
                while claims and claims[0][0] <= ts[j]:            # pass-2 writes that have landed
                    _, _, kind, x, tag, val = heapq.heappop(claims)
                    if kind == "claim":
                        r_tag[x], r_res[x], claimed[x] = tag, val, True
                        lst = pend_by_slot.get(x)
                        if lst:
                            lst.remove(tag)
                            if not lst:
                                del pend_by_slot[x]
                    else:                                                       # a result write from a later phase
                        r_res[x] = val
                if rj_l[j]:
                    outcome[i] = REJECTED
                    continue
                d5 = (src[j], dst[j], sp[j], dp[j], pr[j])
                if d5 in memo_dir:
                    outcome[i], vkind[i], memo_val[i] = MEMO, 1, memo_dir[d5]
                    continue
                h, L, now = fh_l[j], ln[j], nw_l[j]
                cands = (sl_l[j], sl2_l[j]) if two else (sl_l[j],)
                own = [r_tag[x] == h for x in cands]
                for k, x in enumerate(cands):                       # the probe refreshes last-seen in every way whose tag matches
                    if own[k]:
                        r_lastc[x] = now
                s = -1
                if own[0]:
                    s = cands[0]
                elif two and own[1]:
                    s = cands[1]
                if s < 0:                                           # newcomer
                    if not lg_l[j]:
                        outcome[i] = FALLBACK_SHORT
                        continue
                    held = [r_res[x] < 50 and ((now - r_lastc[x]) & _M32) < timeout for x in cands]
                    if two:
                        if held[0]:
                            s = cands[1] if not held[1] else -1
                        elif held[1]:
                            s = cands[0]
                        elif claimed[cands[0]] and not claimed[cands[1]]:
                            s = cands[1]
                        else:
                            s = cands[0]
                    else:
                        s = -1 if held[0] else cands[0]
                    if s < 0:
                        outcome[i] = FALLBACK_COLLISION if any(claimed[x] for x in cands) else FALLBACK_EMPTY
                        continue
                    outcome[i] = NEW_OWNER                          # pass 1: Init the features now, claim the tag and result in pass 2
                    cnt["takeovers"] += 1
                    lst = pend_by_slot.setdefault(s, [])
                    if lst:
                        cnt["reinit_same_flow" if h in lst else "second_newcomer"] += 1
                    lst.append(h)
                    r_pk[s], r_by[s], r_mn[s], r_mx[s] = 1, L, L, L
                    r_ps[s] = sq(L >> 2)
                    r_lts[s], r_mipd[s] = ip_l[j], _M32
                    r_b1[s] = int((L & _BIN_MASK) == _BIN1_VALUE)
                    r_b2[s] = int((L & _BIN_MASK) == _BIN2_VALUE)
                    r_epoch[s] = len(epoch_init)
                    epoch_init.append(i)
                    epoch_events.append([])
                    f_tag[s] = h
                    seq += 1
                    heapq.heappush(claims, (ts[j] + delay, seq, "claim", s, h, pc_l[j]))
                    continue
                outcome[i] = OWNER
                cnt["owner_packets"] += 1
                if two and own[0] and own[1] and h not in dual_flows:
                    dual_flows.add(h)
                    cnt["dual_owner_claims"] += 1
                if f_tag[s] != h:
                    cnt["contaminated_packets"] += 1
                e = r_epoch[s]
                if r_res[s] < 50:
                    if (L & _BIN_MASK) == _BIN1_VALUE:
                        r_b1[s] = (r_b1[s] + 1) & 0xFFFF
                    if (L & _BIN_MASK) == _BIN2_VALUE:
                        r_b2[s] = (r_b2[s] + 1) & 0xFF
                    r_pk[s] = (r_pk[s] + 1) & 0xFFFF
                    r_by[s] = (r_by[s] + L) & _M32
                    r_mn[s], r_mx[s] = min(r_mn[s], L), max(r_mx[s], L)
                    r_ps[s] = (r_ps[s] + sq(L >> 2)) & _M32
                    ipd = (ip_l[j] - r_lts[s]) & _M32
                    r_lts[s] = ip_l[j]
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
                        if N != 2048:                       # every phase recirculation rewrites tag and result in pass 2, whatever the slot holds by then
                            seq += 1
                            heapq.heappush(claims, (ts[j] + delay, seq, "claim", s, h, r_res[s]))
                        if N == 2048:
                            code = int(self.models.phase_codes(2048, pd.DataFrame([feat], columns=FLOW_FEATURES))[0])
                            ev_code[ev] = code
                            if code:
                                seq += 1
                                heapq.heappush(claims, (ts[j] + delay, seq, "claim", s, h, code))
                            if code > 50:
                                canon = _canon(d5)
                                dirs = (d5, (d5[1], d5[0], d5[3], d5[2], d5[4]))
                                pending.append((ts[j] + self.memo_delay_ns, canon, dirs, code))
                                pending.sort(key=lambda x: x[0])
                vkind[i], vepoch[i], vevent[i] = 2, e, len(epoch_events[e])

        codes = self._evaluate_events(ev_phase, ev_feat, ev_code)
        out = self._resolve(pk, fh, slot, outcome, vkind, vepoch, vevent, memo_val, pkt_code,
                            epoch_init, epoch_events, ev_phase, ev_pkt, codes, long_)
        out["clock_offset_ns"] = offset
        out["race"] = dict(cnt)
        return out
