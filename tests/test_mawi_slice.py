import gzip
import importlib.util
import struct
from pathlib import Path

spec = importlib.util.spec_from_file_location("mawi_slice", Path(__file__).resolve().parents[1] / "scripts/mawi_slice.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _pcap(times, caplen=10):
    out = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 96, 1)
    for t in times:
        out += struct.pack("<IIII", int(t), int((t % 1) * 1e6), caplen, caplen) + b"x" * caplen
    return out


def test_slice_keeps_first_seconds_and_whole_records():
    raw = _pcap([100.0, 100.5, 119.9, 120.0, 220.1, 300.0])
    out, info = mod.slice_pcap(raw, 120.0)
    assert info["packets_kept"] == 4 and info["covers_slice"] and info["linktype"] == 1
    assert len(out) == 24 + 4 * (16 + 10)


def test_truncated_download_and_gzip(tmp_path):
    raw = _pcap([1.0 + i for i in range(200)])
    p = tmp_path / "t.pcap.gz"
    p.write_bytes(gzip.compress(raw)[:-40])                   # truncated gzip stream
    got = mod.decompress_partial(p)
    out, info = mod.slice_pcap(got[:-3], 50.0)                # and a cut record at the end
    assert info["packets_kept"] == 51 and info["covers_slice"]
    assert len(out) % 26 == 24 % 26 or len(out) == 24 + 51 * 26


def test_short_download_reports_it_does_not_cover_the_slice():
    _, info = mod.slice_pcap(_pcap([1.0, 2.0, 3.0]), 120.0)
    assert not info["covers_slice"]
