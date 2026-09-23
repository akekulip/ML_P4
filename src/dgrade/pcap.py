"""Read a classic pcap into the packet array used by :mod:`dgrade.netbeacon_sim`.

Keeps only what NetBeacon's parser accepts (third_party/NetBeacon/switch/data_plane/parsers.p4
:58-85): IPv4 without options and without fragmentation, carrying TCP or UDP. Everything else is
counted and dropped, so it never reaches the emulated pipeline, as on the switch. Ethernet
(linktype 1, with one optional 802.1Q tag) and raw IPv4 (linktypes 101 and 228) are supported.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

from dgrade.netbeacon_sim import PACKET_DTYPE

__all__ = ["read_pcap"]

_MAGIC = {0xA1B2C3D4: ("<", 1000), 0xD4C3B2A1: (">", 1000),
          0xA1B23C4D: ("<", 1), 0x4D3CB2A1: (">", 1)}  # byte order, ns per sub-second unit


def _be16(buf: np.ndarray, off: np.ndarray) -> np.ndarray:
    return (buf[off].astype(np.int64) << 8) | buf[off + 1]


def read_pcap(path: str | Path, sort_by_time: bool = False) -> tuple[np.ndarray, dict[str, int]]:
    """Return (packets, counts of kept and dropped records). Packets are in file order unless
    ``sort_by_time``: then a stable sort by timestamp is applied (real captures such as MAWI are not
    strictly time-ordered) and ``stats["reordered"]`` counts packets that arrived earlier than their predecessor."""
    data = Path(path).read_bytes()
    magic = struct.unpack("<I", data[:4])[0]
    if magic not in _MAGIC:
        raise ValueError(f"{path}: not a classic pcap (magic {magic:#x})")
    endian, unit_ns = _MAGIC[magic]
    linktype = struct.unpack(endian + "I", data[20:24])[0]
    if linktype not in (1, 101, 228):
        raise ValueError(f"{path}: unsupported linktype {linktype}")

    rec = struct.Struct(endian + "IIII")
    offs, sec, sub, caplen = [], [], [], []
    pos, end = 24, len(data)
    while pos + 16 <= end:
        s, u, cl, _ = rec.unpack_from(data, pos)
        offs.append(pos + 16)
        sec.append(s)
        sub.append(u)
        caplen.append(cl)
        pos += 16 + cl
    buf = np.frombuffer(data, dtype=np.uint8)
    offs, caplen = np.asarray(offs, dtype=np.int64), np.asarray(caplen, dtype=np.int64)
    ts = np.asarray(sec, dtype=np.int64) * 10**9 + np.asarray(sub, dtype=np.int64) * unit_ns
    n = len(offs)
    stats = {"records": n, "kept": 0, "not_ipv4": 0, "fragment": 0, "ip_options": 0, "not_tcp_udp": 0,
             "truncated": 0}

    if linktype == 1:
        et = np.where(caplen >= 14, _be16(buf, np.minimum(offs + 12, len(buf) - 2)), 0)
        vlan = et == 0x8100
        et = np.where(vlan & (caplen >= 18), _be16(buf, np.minimum(offs + 16, len(buf) - 2)), et)
        ip = offs + np.where(vlan, 18, 14)
    else:
        et = np.full(n, 0x0800)
        ip = offs.copy()
    iplen = caplen - (ip - offs)
    ok = (et == 0x0800) & (iplen >= 20)
    ok &= (buf[np.minimum(ip, len(buf) - 1)] >> 4) == 4
    stats["not_ipv4"] = int(np.sum(~ok))

    ipc = np.minimum(ip, len(buf) - 20)
    ihl = buf[ipc] & 0x0F
    frag = _be16(buf, ipc + 6) & 0x3FFF          # MF flag or a fragment offset
    proto = buf[ipc + 9]
    opt, frg = ok & (ihl != 5), ok & (ihl == 5) & (frag != 0)
    stats["ip_options"], stats["fragment"] = int(opt.sum()), int(frg.sum())
    ok &= (ihl == 5) & (frag == 0)
    tu = np.isin(proto, (6, 17))
    stats["not_tcp_udp"] = int(np.sum(ok & ~tu))
    ok &= tu
    need = np.where(proto == 6, 40, 28)
    trunc = ok & (iplen < need)
    stats["truncated"] = int(trunc.sum())
    ok &= ~trunc

    idx = np.flatnonzero(ok)
    p, l4 = ip[idx], ip[idx] + 20
    out = np.zeros(len(idx), dtype=PACKET_DTYPE)
    out["ts_ns"] = ts[idx]
    out["total_len"] = _be16(buf, p + 2)
    out["diffserv"], out["ttl"], out["proto"] = buf[p + 1], buf[p + 8], buf[p + 9]
    out["src_ip"] = (_be16(buf, p + 12) << 16) | _be16(buf, p + 14)
    out["dst_ip"] = (_be16(buf, p + 16) << 16) | _be16(buf, p + 18)
    out["src_port"], out["dst_port"] = _be16(buf, l4), _be16(buf, l4 + 2)
    is_tcp = out["proto"] == 6
    out["tcp_dataOffset"] = np.where(is_tcp, buf[np.minimum(l4 + 12, len(buf) - 1)] >> 4, 0)
    out["tcp_window"] = np.where(is_tcp, _be16(buf, np.minimum(l4 + 14, len(buf) - 2)), 0)
    out["udp_length"] = np.where(~is_tcp, _be16(buf, np.minimum(l4 + 4, len(buf) - 2)), 0)
    stats["kept"] = len(idx)
    if sort_by_time:
        stats["reordered"] = int(np.sum(np.diff(out["ts_ns"]) < 0))
        out = out[np.argsort(out["ts_ns"], kind="stable")]
    return out, stats
