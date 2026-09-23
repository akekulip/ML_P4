"""Tests for the pcap reader (src/dgrade/pcap.py)."""

import struct

import numpy as np

from dgrade.pcap import read_pcap


def _ipv4(src, dst, proto, payload, ttl=64, tos=0, flags_frag=0, ihl=5):
    opts = b"\x01" * (4 * (ihl - 5))
    total = 4 * ihl + len(payload)
    hdr = struct.pack("!BBHHHBBH4s4s", (4 << 4) | ihl, tos, total, 0, flags_frag, ttl, proto, 0,
                      src.to_bytes(4, "big"), dst.to_bytes(4, "big"))
    return hdr + opts + payload


def _eth(ip, vlan=False):
    head = b"\x00" * 12 + (b"\x81\x00\x00\x05" if vlan else b"")
    return head + b"\x08\x00" + ip


def _pcap(frames, tmp_path, nano=False):
    magic = 0xA1B23C4D if nano else 0xA1B2C3D4
    out = struct.pack("<IHHiIII", magic, 2, 4, 0, 0, 65535, 1)
    for i, f in enumerate(frames):
        out += struct.pack("<IIII", 100 + i, 5 * i, len(f), len(f)) + f
    p = tmp_path / "t.pcap"
    p.write_bytes(out)
    return p


def test_reads_tcp_and_udp_fields(tmp_path):
    tcp = struct.pack("!HHIIBBHHH", 1234, 80, 0, 0, 5 << 4, 0x10, 29200, 0, 0)
    udp = struct.pack("!HHHH", 5353, 53, 8 + 4, 0) + b"abcd"
    frames = [_eth(_ipv4(0x0A000001, 0x0A000002, 6, tcp, ttl=60, tos=0x28)),
              _eth(_ipv4(0x0A000003, 0x0A000004, 17, udp), vlan=True)]
    pk, stats = read_pcap(_pcap(frames, tmp_path))
    assert len(pk) == 2 and stats["kept"] == 2
    assert pk["ts_ns"][0] == 100 * 10**9 and pk["ts_ns"][1] == 101 * 10**9 + 5000
    assert (pk["src_port"][0], pk["dst_port"][0], pk["tcp_window"][0], pk["tcp_dataOffset"][0]) == (1234, 80, 29200, 5)
    assert (pk["ttl"][0], pk["diffserv"][0], pk["total_len"][0]) == (60, 0x28, 40)
    assert (pk["proto"][1], pk["udp_length"][1], pk["tcp_window"][1]) == (17, 12, 0)


def test_nanosecond_pcap(tmp_path):
    udp = struct.pack("!HHHH", 1, 2, 8, 0)
    pk, _ = read_pcap(_pcap([_eth(_ipv4(1, 2, 17, udp))], tmp_path, nano=True))
    assert pk["ts_ns"][0] == 100 * 10**9


def test_drops_what_netbeacon_parser_rejects(tmp_path):
    udp = struct.pack("!HHHH", 1, 2, 8, 0)
    frames = [_eth(_ipv4(1, 2, 17, udp, flags_frag=0x2000)),        # more-fragments set
              _eth(_ipv4(1, 2, 17, udp, ihl=6)),                     # IP options
              _eth(_ipv4(1, 2, 1, b"\x08\x00\x00\x00")),             # ICMP
              b"\x00" * 12 + b"\x86\xdd" + b"\x00" * 40,             # IPv6
              _eth(_ipv4(1, 2, 17, udp))]
    pk, stats = read_pcap(_pcap(frames, tmp_path))
    assert len(pk) == 1
    assert stats == {"records": 5, "kept": 1, "not_ipv4": 1, "fragment": 1, "ip_options": 1, "not_tcp_udp": 1,
                     "truncated": 0}
    assert np.all(pk["proto"] == 17)


def test_sort_by_time_orders_packets_and_counts_reordering(tmp_path):
    udp = struct.pack("!HHHH", 1, 2, 8, 0)
    frames = [_eth(_ipv4(1, 2, 17, udp)) for _ in range(4)]
    # record times 100, 105 (i=1), then rewrite so that packet 2 is older than packet 1
    p = _pcap(frames, tmp_path)
    data = bytearray(p.read_bytes())
    rec = 24 + 2 * (16 + len(frames[0]))
    struct.pack_into("<II", data, rec, 100, 1)                # packet 2 now earlier than packet 1
    p.write_bytes(bytes(data))
    plain, st0 = read_pcap(p)
    srt, st1 = read_pcap(p, sort_by_time=True)
    assert not np.all(np.diff(plain["ts_ns"]) >= 0)
    assert np.all(np.diff(srt["ts_ns"]) >= 0) and len(srt) == len(plain)
    assert st1["reordered"] == 1 and "reordered" not in st0
