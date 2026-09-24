"""Pull stage count and per-stage resources out of a bf-p4c build directory.

usage: python extract.py <build_dir> <compile_log>
Reads only files the compiler wrote; prints a markdown fragment.
"""
import glob
import json
import os
import re
import sys

COLS = ["Hash Bit", "Hash Dist Unit", "Gateway", "SRAM", "TCAM", "Meter ALU", "VLIW Instr",
        "Exact Match Input xbar", "Ternary Match Input xbar"]


def mau_table(path):
    lines = open(path).read().splitlines()
    hdr_i = next(i for i, l in enumerate(lines) if l.startswith("| Stage Number"))
    hdr = [c.strip() for c in lines[hdr_i].strip("|").split("|")]
    rows = {}
    for l in lines[hdr_i + 2:]:
        if not l.startswith("|"):
            break
        cells = [c.strip() for c in l.strip("|").split("|")]
        if cells[0] == "":
            continue
        rows[cells[0]] = dict(zip(hdr, cells))
    return rows


def stages(path):
    txt = open(path).read()
    got = re.findall(r"Number of stages in table allocation: (\d+)\n\s+Number of stages for ingress table allocation: (\d+)\n\s+Number of stages for egress table allocation: (\d+)", txt)
    return got


def main():
    b, log = sys.argv[1], sys.argv[2]
    logs = os.path.join(b, "pipe", "logs")
    print(f"build: `{b}`  log: `{log}`\n")
    ltxt = open(log).read()
    print("compile tail: `" + [l for l in ltxt.splitlines() if "generated" in l or "error" in l.lower()][-1] + "`\n")
    ts = os.path.join(logs, "table_summary.log")
    if not os.path.exists(ts):
        print("NO table_summary.log (compile did not reach placement)")
        return
    st = stages(ts)
    print(f"table_summary.log placement rounds (total, ingress, egress): {st}; FINAL = {st[-1]}\n")
    rows = mau_table(os.path.join(logs, "mau.resources.log"))
    print("| stage | " + " | ".join(COLS) + " |")
    print("|---" * (len(COLS) + 1) + "|")
    for k, r in rows.items():
        print(f"| {k} | " + " | ".join(r.get(c, "?") for c in COLS) + " |")
    m = json.load(open(os.path.join(logs, "metrics.json")))
    ph = m["phv"]
    occ = {f"{d['bit_width']}b": d["containers_occupied"] for d in ph["normal"]}
    tag = {f"{d['bit_width']}b": d["containers_occupied"] for d in ph["tagalong"]}
    print(f"\nPHV containers occupied (normal) {occ}, (tagalong) {tag}")
    summ = sorted(glob.glob(os.path.join(logs, "phv_allocation_summary_*.log")))[-1]
    for l in open(summ):
        if "Overall PHV Usage" in l:
            print(f"{os.path.basename(summ)}: `{l.strip()}`")
    print(f"mau totals: srams={m['mau']['srams']} tcams={m['mau']['tcams']} map_rams={m['mau']['map_rams']} logical_tables={m['mau']['logical_tables']}")
    warns = [l for l in ltxt.splitlines() if "warning" in l]
    nosize = sum("No size defined" in l for l in warns)
    print(f"\nwarnings: {len(warns) - 1 if warns and 'generated' in warns[-1] else len(warns)} ({nosize} 'No size defined')")
    for l in warns:
        if "No size defined" not in l and "generated" not in l:
            print("  - `" + l.split("scratchpad/d4c_compile/")[-1] + "`")


main()
