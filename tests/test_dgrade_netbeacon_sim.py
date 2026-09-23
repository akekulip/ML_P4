"""Tests for the packet-level NetBeacon state-machine emulator (src/dgrade/netbeacon_sim.py).

State-machine tests use stub models so that verdicts are known; one test runs the real shipped
tables end to end. Timestamps are absolute nanoseconds; the switch sees their low 32 bits.
"""

import os
import time
import zlib
from pathlib import Path

import numpy as np
import pytest

from dgrade.netbeacon_sim import (
    FALLBACK_COLLISION,
    FALLBACK_SHORT,
    MEMO,
    NEW_OWNER,
    OWNER,
    REJECTED,
    NetBeaconSim,
    StubModels,
    crc32_flow_hash,
    make_packets,
    summarize,
)

MS = 1_000_000
ARTIFACT = Path(__file__).resolve().parents[1] / "third_party" / "NetBeacon"


def flow(n, *, src=0x0A000001, dst=0x0A000002, sport=1000, dport=80, proto=6, t0=0, gap=MS, length=100):
    ts = t0 + np.arange(n, dtype=np.int64) * gap
    return make_packets(ts_ns=ts, src_ip=src, dst_ip=dst, src_port=sport, dst_port=dport, proto=proto,
                        total_len=length)


def merge(*parts):
    p = np.concatenate(parts)
    return p[np.argsort(p["ts_ns"], kind="stable")]


def run(pkts, **kw):
    kw.setdefault("models", StubModels())
    # start the clock past the first 256 units so that empty (zero) slots are claimable
    kw.setdefault("clock_offset_ns", 300 * (1 << 20))
    return NetBeaconSim(**kw).run(pkts)


def test_crc_matches_zlib_on_normalised_tuple():
    h = crc32_flow_hash(np.array([0x0A000002]), np.array([0x0A000001]), np.array([80]), np.array([1000]),
                        np.array([6]))
    b = (0x0A000001).to_bytes(4, "big") + (0x0A000002).to_bytes(4, "big") + (80).to_bytes(2, "big") \
        + (1000).to_bytes(2, "big") + bytes([6])
    assert int(h[0]) == zlib.crc32(b)


def test_hash_is_symmetric():
    a = crc32_flow_hash(np.array([1]), np.array([2]), np.array([10]), np.array([20]), np.array([6]))
    b = crc32_flow_hash(np.array([2]), np.array([1]), np.array([20]), np.array([10]), np.array([6]))
    assert a[0] == b[0]


def test_lone_long_flow_gets_phase_verdicts_then_memo():
    out = run(flow(2100))
    src = out["source"]
    assert src[0] == "pkt" and out["outcome"][0] == NEW_OWNER
    for n in (2, 4, 8, 32, 256, 512, 2048):
        assert src[n - 1] == f"phase-{n}", n
    assert src[2] == "phase-2"          # sticky between phases
    assert src[1023] == "phase-512"     # 1024 has no Flow_Tree entries: result is kept
    assert all(s == "memo" for s in src[2048:])
    assert np.all(out["outcome"][2048:] == MEMO)
    assert out["result"][2047] > 50


def test_collision_with_active_incumbent_falls_back():
    sim = NetBeaconSim(models=StubModels(), n_slots=1, clock_offset_ns=300 * (1 << 20))
    a = flow(50, sport=1000)
    b = flow(5, sport=2000, t0=10 * MS + 1)
    out = sim.run(merge(a, b))
    is_b = out["src_port"] == 2000
    assert np.all(out["outcome"][is_b] == FALLBACK_COLLISION)
    assert np.all(out["source"][is_b] == "pkt")


def test_takeover_after_idle_timeout():
    sim = NetBeaconSim(models=StubModels(), n_slots=1, clock_offset_ns=300 * (1 << 20))
    a = flow(5, sport=1000)
    b = flow(5, sport=2000, t0=5 * MS + 300 * (1 << 20))   # a idle for > 256 units of 2^20 ns
    out = sim.run(merge(a, b))
    is_b = out["src_port"] == 2000
    assert out["outcome"][is_b][0] == NEW_OWNER
    assert np.all(out["outcome"][is_b][1:] == OWNER)


def test_wrap_opens_eviction_window():
    # incumbent last refreshed at now = 4000 units; after the 2^32-ns wrap now is small, so
    # now - stored wraps to >= 2^32 - 4096 >= 256 and the active incumbent is evictable
    unit = 1 << 20
    start = 4000 * unit
    sim = NetBeaconSim(models=StubModels(), n_slots=1, clock_offset_ns=0)
    a = flow(20, sport=1000, t0=start, gap=unit)             # active until 4019 units
    b = flow(3, sport=2000, t0=(1 << 32) + 5 * unit)          # 5 units after the wrap
    out = sim.run(merge(a, b))
    assert out["outcome"][out["src_port"] == 2000][0] == NEW_OWNER


def test_takeover_inherits_old_timestamp():
    # b takes the slot but does not refresh last_classified, so c can take it from b at once
    unit = 1 << 20
    sim = NetBeaconSim(models=StubModels(), n_slots=1, clock_offset_ns=300 * unit)
    a = flow(1, sport=1000)
    b = flow(1, sport=2000, t0=300 * unit)
    c = flow(1, sport=3000, t0=300 * unit + 10)
    out = sim.run(merge(a, b, c))
    assert out["outcome"][out["src_port"] == 3000][0] == NEW_OWNER


def test_short_predicted_flows_never_take_a_slot():
    out = run(flow(10), models=StubModels(flow_size=10))
    assert np.all(out["outcome"] == FALLBACK_SHORT)
    assert np.all(out["source"] == "pkt")


def test_rejected_protocols():
    out = run(flow(3, proto=1))
    assert np.all(out["outcome"] == REJECTED)


def test_keyed_hash_changes_slots():
    p = merge(*[flow(1, sport=1000 + i, t0=i) for i in range(200)])
    s0 = run(p)["slot"]
    s1 = run(p, keyed=True, seed=7)["slot"]
    assert np.mean(s0 != s1) > 0.9


def test_summarize_marks_collided_long_flows_downgraded():
    sim = NetBeaconSim(models=StubModels(), n_slots=1, clock_offset_ns=300 * (1 << 20))
    out = sim.run(merge(flow(50, sport=1000), flow(5, sport=2000, t0=10 * MS + 1)))
    s = summarize(out)
    by_port = {int(r.src_port): r for r in s.itertuples()}
    assert not by_port[1000].downgraded and by_port[1000].frac_full > 0.9
    assert by_port[2000].downgraded and by_port[2000].frac_full == 0.0


def test_throughput_one_million_packets():
    rng = np.random.default_rng(0)
    n = 1_000_000
    pk = make_packets(ts_ns=np.sort(rng.integers(0, 60_000 * MS, n)), src_ip=rng.integers(1, 2**32 - 1, n),
                      dst_ip=0x0A000002, src_port=rng.integers(1024, 65535, n), dst_port=443, proto=6,
                      total_len=rng.integers(40, 1500, n))
    t = time.time()
    run(pk)
    assert time.time() - t < 60


@pytest.mark.skipif(not ARTIFACT.exists() and os.environ.get("DGRADE_ALLOW_MISSING_ARTIFACTS") == "1",
                    reason="artifact absent and skipping allowed")
def test_real_tables_end_to_end():
    from dgrade.netbeacon import load_tables
    from dgrade.netbeacon_sim import TableModels
    out = run(flow(2100, length=120), models=TableModels(load_tables(ARTIFACT)))
    assert out["source"][1] == "phase-2"
    assert set(np.unique(out["source"])) <= {"pkt", "memo"} | {f"phase-{n}" for n in (2, 4, 8, 32, 256, 512, 2048)}


# ---- fixes from the code review of 2026-09-23 ----

from dgrade.netbeacon_sim import FALLBACK_EMPTY, flow_ids


class RecordingModels(StubModels):
    """Stub that records the feature rows each phase sees."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.seen = {}

    def phase_codes(self, phase, feats):
        self.seen.setdefault(phase, []).extend(feats.to_dict("records"))
        return super().phase_codes(phase, feats)


def test_refusal_at_an_empty_slot_is_not_a_collision():
    sim = NetBeaconSim(models=StubModels(), clock_offset_ns=0)
    out = sim.run(flow(5))                       # now < 256 units: the switch refuses even an empty slot
    assert np.all(out["outcome"] == FALLBACK_EMPTY)
    assert not summarize(out).iloc[0].downgraded


def test_clock_offset_is_recorded_and_random_by_default():
    a = NetBeaconSim(models=StubModels(), seed=1).run(flow(3))
    b = NetBeaconSim(models=StubModels(), seed=2).run(flow(3))
    assert a["clock_offset_ns"] != b["clock_offset_ns"]


def test_phase_features_match_switch_arithmetic():
    lens = [100, 200, 80, 90, 48, 60, 1500, 40]
    ts = np.array([0, 1000, 3000, 6000, 10_000, 15_000, 21_000, 28_000], dtype=np.int64) * 1024
    pk = make_packets(ts_ns=ts, src_ip=1, dst_ip=2, src_port=10, dst_port=20, proto=6, total_len=lens)
    m = RecordingModels()
    run(pk, models=m, clock_offset_ns=300 * (1 << 20))
    f2, f8 = m.seen[2][0], m.seen[8][0]
    assert (f2["pkt_size_max"], f2["pkt_size_min"], f2["pkt_size_avg"]) == (200, 100, 150)
    sq = sum((x >> 2) ** 2 for x in lens[:2])
    assert f2["pkt_size_var_approx"] == ((sq << 3) - 150 ** 2) & 0xFFFFFFFF
    assert f2["flow_iat_min"] == 1000
    assert f8["flow_iat_min"] == 1000 and f8["pkt_size_avg"] == sum(lens) >> 3
    assert f8["bin_3"] == 2 and f8["bin_5"] == 2          # [48,64): 48 and 60; [80,96): 80 and 90
    sq8 = sum((x >> 2) ** 2 for x in lens)
    assert f8["pkt_size_var_approx"] == ((sq8 << 1) - (sum(lens) >> 3) ** 2) & 0xFFFFFFFF


def test_negative_variance_wraps_unsigned():
    pk = make_packets(ts_ns=np.array([0, 1024]), src_ip=1, dst_ip=2, src_port=10, dst_port=20, proto=6,
                      total_len=[43, 43])
    m = RecordingModels()
    run(pk, models=m, clock_offset_ns=300 * (1 << 20))
    v = m.seen[2][0]["pkt_size_var_approx"]
    assert v == (((2 * 10 ** 2) << 3) - 43 ** 2) & 0xFFFFFFFF


def test_bin5_wraps_at_256():
    m = RecordingModels()
    run(flow(256, length=85), models=m)
    assert m.seen[256][0]["bin_5"] == 0


def test_stored_zero_and_flow_tree_miss_takes_the_phase_packet_verdict():
    class Missing(StubModels):
        def pkt_codes(self, pk):
            c = np.full(len(pk), 2, dtype=np.int64)
            c[0] = 0                                  # takeover packet misses Pkt_Tree: stored 0
            return c

        def phase_codes(self, phase, feats):
            return np.zeros(len(feats), dtype=np.int64)  # every Flow_Tree lookup misses

    out = run(flow(6), models=Missing())
    # packet 2 is a phase packet: Pkt_Tree gives 2, which the recirculated copy stores (sw:598, 722)
    assert out["result"][1] == 2 and out["result"][2] == 2


def test_memo_fifo_drops_ten_oldest():
    # 21 flows are determined in order; the 21st insert finds 20 entries and drops the 10 oldest
    sim = NetBeaconSim(models=StubModels(), memo_size=20, clock_offset_ns=300 * (1 << 20))
    fl = [flow(2048, sport=1000 + k, t0=k * 3 * MS, gap=10_000) for k in range(21)]
    late = [flow(1, sport=1000, t0=1000 * MS), flow(1, sport=1015, t0=1000 * MS + 1)]
    out = sim.run(merge(*fl, *late))
    last = {int(p): s for p, s in zip(out["src_port"], out["source"])}
    assert last[1000] == "phase-2048"   # dropped from the memo; its slot still holds the verdict
    assert last[1015] == "memo"


def test_udp_source_port_68_rejected():
    out = run(flow(2, proto=17, sport=68))
    assert np.all(out["outcome"] == REJECTED)


def test_out_of_order_timestamps_rejected():
    with pytest.raises(ValueError):
        run(flow(3)[::-1])


def test_flow_ids_split_on_idle_gap_and_keep_directions_apart():
    a = flow(3, gap=MS)
    b = flow(2, t0=10 * 1000 * MS)                    # same tuple, 10 s later: a new flow
    c = flow(2, sport=80, dport=1000, t0=20 * MS)     # A:80 -> B:1000 differs from A:1000 -> B:80
    pk = merge(a, b, c)
    fid = flow_ids(pk, idle_ns=256 * MS)
    assert len(np.unique(fid)) == 3


def test_isolated_run_gives_every_flow_a_slot():
    pk = merge(flow(50, sport=1000), flow(5, sport=2000, t0=10 * MS + 1))
    fid = flow_ids(pk, idle_ns=256 * MS)
    iso = NetBeaconSim(models=StubModels(), n_slots=1, seed=0).run(pk, isolate=fid)
    assert not np.any(np.isin(iso["outcome"], [FALLBACK_COLLISION, FALLBACK_EMPTY]))


def test_downgrade_counts_flows_predicted_long_on_any_packet():
    class LateLong(StubModels):
        def flow_size(self, pk):
            return np.where(pk["src_port"] == 2000, np.where(np.arange(len(pk)) % 2, 80, 10), 80)

    sim = NetBeaconSim(models=LateLong(), n_slots=1, clock_offset_ns=300 * (1 << 20))
    pk = merge(flow(50, sport=1000), flow(6, sport=2000, t0=10 * MS + 1))
    s = summarize(sim.run(pk))
    assert bool(s[s.src_port == 2000].iloc[0].downgraded)
