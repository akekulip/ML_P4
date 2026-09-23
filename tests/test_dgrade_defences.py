"""G4 defences in the emulator: credit-based rent admission (D3), its age-only and literal-rate variants, D1's IPD fix."""

import numpy as np
import pytest

from dgrade.netbeacon_sim import (
    FALLBACK_COLLISION,
    NEW_OWNER,
    NetBeaconSim,
    StubModels,
    make_packets,
)

MS = 1_000_000
S = 1_000_000_000


def flow(sport, t0, n, gap_ns):
    return make_packets(ts_ns=t0 + np.arange(n, dtype=np.int64) * gap_ns, src_ip=0x0A000001, dst_ip=0x0A000002,
                        src_port=sport, dst_port=80, proto=6, total_len=100)


def merge(*parts):
    p = np.concatenate(parts)
    return p[np.argsort(p["ts_ns"], kind="stable")]


def run(pk, **kw):
    return NetBeaconSim(models=StubModels(), n_slots=1, clock_offset_ns=1000 * S, wrap_window=False, **kw).run(pk)


def outcome_of(out, pk, sport, k=0):
    return out["outcome"][pk["src_port"] == sport][k]


def test_rent_requires_the_unwrapped_clock():
    with pytest.raises(ValueError):
        NetBeaconSim(models=StubModels(), n_slots=1, rent="credit").run(flow(1, 0, 3, MS))


def test_young_incumbent_is_protected_even_if_slow():
    slow = flow(1000, 0, 20, 250 * MS)                       # 4 pkt/s, 4.75 s long
    new = flow(2000, 500 * MS, 2, MS)                        # arrives at 0.5 s, before the 1 s grace ends
    pk = merge(slow, new)
    assert outcome_of(run(pk, rent="credit", rent_rmin=16), pk, 2000) == FALLBACK_COLLISION


def test_slow_incumbent_is_evicted_after_grace_and_a_fast_one_is_not():
    slow = flow(1000, 0, 40, 250 * MS)                       # 4 pkt/s
    fast = flow(1001, 0, 400, 25 * MS)                       # 40 pkt/s
    new_slow = flow(2000, 3 * S, 2, MS)
    a = merge(slow, new_slow)
    b = merge(fast, new_slow)
    out_a = run(a, rent="credit", rent_rmin=16)
    out_b = run(b, rent="credit", rent_rmin=16)
    assert outcome_of(out_a, a, 2000) == NEW_OWNER            # rate 4 < 16 and older than 1 s: evictable
    assert outcome_of(out_b, b, 2000) == FALLBACK_COLLISION   # rate 40 >= 16: keeps the slot
    off = run(a)                                              # undefended: an active incumbent is never refused
    assert outcome_of(off, a, 2000) == FALLBACK_COLLISION


def test_age_only_variant_evicts_a_fast_incumbent_too():
    fast = flow(1001, 0, 400, 25 * MS)
    new = flow(2000, 3 * S, 2, MS)
    pk = merge(fast, new)
    assert outcome_of(run(pk, rent="age"), pk, 2000) == NEW_OWNER


def test_literal_rate_variant_uses_packets_over_age():
    slow = flow(1000, 0, 40, 250 * MS)
    fast = flow(1001, 0, 400, 25 * MS)
    new = flow(2000, 3 * S, 2, MS)
    a, b = merge(slow, new), merge(fast, new)
    assert outcome_of(run(a, rent="rate", rent_rmin=16), a, 2000) == NEW_OWNER
    assert outcome_of(run(b, rent="rate", rent_rmin=16), b, 2000) == FALLBACK_COLLISION


def test_credit_is_capped_so_a_burst_cannot_bank_unlimited_credit():
    burst = flow(1000, 0, 2000, MS)                          # 2000 packets in 2 s, then silence
    late = flow(1000, 20 * S, 3, 250 * MS)                   # trickles at 4 pkt/s later
    new = flow(2000, 30 * S, 2, MS)
    pk = merge(burst, late, new)
    # without a cap 2000 packets at r_min = 8 would bank 250 s of credit and the trickler would stay protected
    assert outcome_of(run(pk, rent="credit", rent_rmin=8, rent_cap_s=2.0), pk, 2000) == NEW_OWNER


def test_defence_off_matches_the_default_behaviour():
    slow = flow(1000, 0, 40, 250 * MS)
    new = flow(2000, 3 * S, 2, MS)
    pk = merge(slow, new)
    a = run(pk)
    b = run(pk, rent=None)
    assert np.array_equal(a["outcome"], b["outcome"])


def test_fix_ipd_wrap_removes_the_wrapped_gap():
    # two packets straddling the 2^32 ns boundary: with the bug the gap reads about 2^32 minus a small number
    from dgrade.netbeacon_sim import _M32
    t = np.array([(1 << 32) - 1000, (1 << 32) + 1000], dtype=np.int64)
    pk = make_packets(ts_ns=t, src_ip=1, dst_ip=2, src_port=5, dst_port=6, proto=6, total_len=100)

    class Rec(StubModels):
        def __init__(self):
            super().__init__()
            self.seen = []

        def phase_codes(self, phase, feats):
            self.seen.append(int(feats["flow_iat_min"].iloc[0]))
            return super().phase_codes(phase, feats)
    buggy, fixed = Rec(), Rec()
    NetBeaconSim(models=buggy, clock_offset_ns=0).run(pk)
    NetBeaconSim(models=fixed, clock_offset_ns=0, fix_ipd_wrap=True).run(pk)
    assert buggy.seen[0] > _M32 // 2 and fixed.seen[0] < 10


def test_defence_names_map_to_emulator_switches():
    from dgrade.defences import defence_kwargs
    assert defence_kwargs(None) == {} and defence_kwargs("") == {}
    d1 = defence_kwargs("d1")
    assert d1["wrap_window"] is False and d1["takeover_refresh"] is True and d1["fix_ipd_wrap"] is True
    assert defence_kwargs("d3c16")["rent"] == "credit" and defence_kwargs("d3c16")["rent_rmin"] == 16.0
    assert defence_kwargs("d3r8")["rent"] == "rate" and defence_kwargs("d3a")["rent"] == "age"
    with pytest.raises(ValueError):
        defence_kwargs("d9")
