"""Cut the pre-registered slice from a partially downloaded MAWI trace (docs/preregistration.md, G2).

  mawi_slice.py PART.pcap.gz OUT.pcap [SECONDS]

Decompresses the (truncated) gzip stream, keeps the packets whose timestamp is within SECONDS
(default 120.0) of the first packet, stops at the last whole record, and writes a classic pcap.
Prints the link type, the time span the download covered, and the packet count kept.
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path


def decompress_partial(path: Path) -> bytes:
    d, out = zlib.decompressobj(16 + zlib.MAX_WBITS), []
    with open(path, "rb") as f:
        while chunk := f.read(1 << 24):
            out.append(d.decompress(chunk))
    return b"".join(out)


def slice_pcap(raw: bytes, seconds: float) -> tuple[bytes, dict]:
    magic = struct.unpack("<I", raw[:4])[0]
    if magic not in (0xA1B2C3D4, 0xA1B23C4D):
        raise ValueError(f"unsupported pcap magic {magic:#x}")
    unit = 1e-6 if magic == 0xA1B2C3D4 else 1e-9
    linktype = struct.unpack("<I", raw[20:24])[0]
    rec = struct.Struct("<IIII")
    pos, n, t0, last_ts, kept_end, kept = 24, 0, None, None, 24, 0
    while pos + 16 <= len(raw):
        s, u, cl, _ = rec.unpack_from(raw, pos)
        if pos + 16 + cl > len(raw):
            break                                            # truncated record at the end of the download
        ts = s + u * unit
        if t0 is None:
            t0 = ts
        last_ts = ts
        n += 1
        if ts - t0 <= seconds:
            kept_end, kept = pos + 16 + cl, n
        pos += 16 + cl
    info = {"linktype": linktype, "first_ts": t0, "download_span_s": last_ts - t0, "records_in_download": n,
            "packets_kept": kept, "slice_s": seconds, "covers_slice": (last_ts - t0) > seconds}
    return raw[:kept_end], info


if __name__ == "__main__":
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    secs = float(sys.argv[3]) if len(sys.argv) > 3 else 120.0
    out, info = slice_pcap(decompress_partial(src), secs)
    dst.write_bytes(out)
    print(info, f"-> {dst} ({len(out) / 1e6:.0f} MB)")
