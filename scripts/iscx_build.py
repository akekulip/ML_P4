"""G7: build the ISCXVPN2016 packet stream (docs/preregistration.md, G7 entry) -> results/g7/stream.npz

Reads the 29 source captures (a pcapng is converted with editcap into data/interim first; raw files are untouched), keeps what NetBeacon's
parser accepts (dgrade.pcap.read_pcap), shifts every capture to start at t = 0, remaps addresses per capture (so flows of different captures
never share a 5-tuple), and merges all packets in timestamp order. Per packet: capture id, class id, session-group id.
Classes: Messaging (Chat + Email), Streaming, File transfer, P2P, VoIP. Session group = capture name without its trailing a/b/A/B/digit suffix.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dgrade.pcap import read_pcap

RAW = ROOT / "data/raw/bos_datasets/ISCXVPN2016/source"
INTERIM = ROOT / "data/interim/ISCXVPN2016"
OUT = ROOT / "results/g7"
CLASSES = {"Chat": 0, "Email": 0, "Streaming": 1, "FTP": 2, "P2P": 3, "VoIP": 4}
CLASS_NAMES = ["Messaging", "Streaming", "File transfer", "P2P", "VoIP"]


def group_of(cap: str) -> str:
    g = cap.removeprefix("vpn_")
    return re.sub(r"(\d*[ab]|_[AB]|\d+)$", "", g)


def main() -> None:
    caps = sorted((d.name, p) for d in RAW.iterdir() if d.is_dir() for p in sorted(d.glob("*.pcap")))
    parts, meta = [], []
    for i, (folder, path) in enumerate(caps):
        src = path
        if path.read_bytes()[:4] == b"\n\r\r\n":                          # pcapng: convert with editcap
            src = INTERIM / path.name
            subprocess.run(["editcap", "-F", "pcap", str(path), str(src)], check=True, capture_output=True)
        pk, st = read_pcap(src, sort_by_time=True)
        pk["ts_ns"] -= pk["ts_ns"].min()
        pk["src_ip"] ^= np.uint32((i + 1) << 20)                             # per-capture address remap (flows of different captures stay distinct)
        pk["dst_ip"] ^= np.uint32((i + 1) << 20)
        parts.append((pk, np.full(len(pk), i, dtype=np.int16), np.full(len(pk), CLASSES[folder], dtype=np.int8)))
        meta.append({"capture": path.stem, "folder": folder, "class": CLASSES[folder], "group": group_of(path.stem), "packets": int(len(pk)),
                     "duration_s": float(pk["ts_ns"].max() / 1e9), "read_stats": st})
        print(path.stem, folder, len(pk), st["records"], flush=True)
    pk = np.concatenate([p[0] for p in parts])
    cap = np.concatenate([p[1] for p in parts])
    cls = np.concatenate([p[2] for p in parts])
    o = np.argsort(pk["ts_ns"], kind="stable")
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez(OUT / "stream.npz", pk=pk[o], cap=cap[o], cls=cls[o])
    (OUT / "captures.json").write_text(json.dumps({"class_names": CLASS_NAMES, "captures": meta}, indent=1))
    print("packets", len(pk), "captures", len(meta), "groups", sorted({m["group"] for m in meta}))


if __name__ == "__main__":
    main()
