"""GA-1: XOR-fold identity-aliasing falsification test (docs/preregistration.md, GA entry) -> docs/results_ga_alias.md

Separate research thread, not part of the D4/D4c evaluation. For the 20 largest long flows (more than 50 packets) on PeerRush and on each MAWI
day, builds one alias tuple per victim with an equal XOR fold (src^dst, sport^dport, proto unchanged; a genuinely different 5-tuple), merges the
alias's packets (one per 250 ms, starting mid-victim) into the victim's stream, and replays through TofinoSim (fold hash on) to see whether the
alias is admitted as owner of the victim's slot, whether it updates the victim's features, and whether the victim's verdict changes.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from dgrade.flowstats import FlowIndex, downgraded_flows
from dgrade.netbeacon import load_tables
from dgrade.netbeacon_sim import NEW_OWNER, OWNER, PACKET_DTYPE, TableModels, flow_ids, make_packets, tuple_table
from dgrade.netbeacon_tofino import TofinoSim, fold_hash_unique

INTERVAL_NS = 250_000_000


def alias_of(src: int, dst: int, sp: int, dp: int) -> tuple[int, int, int, int]:
    """A genuinely different 5-tuple with an equal XOR fold: (a^k, b^k) folds to a^b for any k."""
    k1, k2 = 0xA5A5A5A5, 0x1234
    return src ^ k1, dst ^ k1, sp ^ k2, dp ^ k2


def make_alias_packets(t0: int, span_ns: int, src: int, dst: int, sp: int, dp: int, proto: int) -> np.ndarray:
    n = max(1, span_ns // INTERVAL_NS)
    ts = t0 + np.arange(n, dtype=np.int64) * INTERVAL_NS
    return make_packets(ts_ns=ts, src_ip=src, dst_ip=dst, src_port=sp, dst_port=dp, proto=proto, total_len=60)


def run_one(name: str, pk: np.ndarray, victims: list[int], fid: np.ndarray, art) -> list[dict]:
    tables = TableModels(load_tables(art))
    rows = []
    for vf in victims:
        idx = np.flatnonzero(fid == vf)
        v = pk[idx]
        src, dst, sp, dp = int(v["src_ip"][0]), int(v["dst_ip"][0]), int(v["src_port"][0]), int(v["dst_port"][0])
        a_src, a_dst, a_sp, a_dp = alias_of(src, dst, sp, dp)
        t0 = int(v["ts_ns"][len(v) // 2])
        span = int(v["ts_ns"][-1]) - t0
        proto = int(v["proto"][0])
        alias_pk = make_alias_packets(t0, max(span, INTERVAL_NS * 4), a_src, a_dst, a_sp, a_dp, proto)

        def replay(with_alias: bool):
            stream = np.concatenate([v, alias_pk]) if with_alias else v.copy()
            stream = stream[np.argsort(stream["ts_ns"], kind="stable")]
            uniq, inv = tuple_table(stream["src_ip"], stream["dst_ip"], stream["src_port"], stream["dst_port"], stream["proto"])
            tag = fold_hash_unique(uniq)[inv]
            slot = (tag & 0xFFFF).astype(np.int64)
            sim = TofinoSim(models=tables, n_slots=65536, clock_offset_ns=300 * (1 << 20), ways=1)
            out = sim.run(stream, force_slot=slot, force_hash=tag, force_long=np.ones(len(stream), dtype=bool))
            is_alias = np.isin(np.arange(len(stream)), np.array([], dtype=int)) if not with_alias else \
                (stream["src_ip"] == a_src) & (stream["dst_ip"] == a_dst)
            return stream, out, is_alias, tag

        s_no, out_no, _, _ = replay(False)
        s_yes, out_yes, is_alias, tag = replay(True)
        alias_admitted_owner = bool(np.any(np.isin(out_yes["outcome"][is_alias], (OWNER, NEW_OWNER))))
        vic_tag_no_alias = tag[~is_alias][0] if len(tag[~is_alias]) else -1
        same_tag = bool(np.all(tag == tag[0]))          # alias and victim share the identical 32-bit tag, by construction
        last_v_no = out_no["result"][-1]
        last_v_yes = out_yes["result"][~is_alias][-1] if np.any(~is_alias) else out_yes["result"][-1]
        rows.append({"trace": name, "flow": int(vf), "packets": len(v), "same_tag": same_tag,
                     "alias_admitted_owner": alias_admitted_owner, "final_result_no_alias": int(last_v_no),
                     "final_result_with_alias": int(last_v_yes), "verdict_changed": bool(last_v_no != last_v_yes)})
    return rows


def main() -> None:
    from g2_mawi import ART as MAWI_ART, load_day
    all_rows: list[dict] = []

    z = np.load(ROOT / "results/g1/stream.npz")
    pk = z["pk"]
    fid = flow_ids(pk, 1 << 62)
    n_pkts = np.bincount(fid)
    victims = np.argsort(-n_pkts)[:20]
    victims = [int(v) for v in victims if n_pkts[v] > 50][:20]
    all_rows += run_one("PeerRush", pk, victims, fid, MAWI_ART)

    for day, label in (("p", "MAWI-primary"), ("r", "MAWI-replication")):
        pk_d = load_day(day)
        fid_d = flow_ids(pk_d, 1 << 62)
        n_d = np.bincount(fid_d)
        vs = [int(v) for v in np.argsort(-n_d)[:20] if n_d[v] > 50][:20]
        all_rows += run_one(label, pk_d, vs, fid_d, MAWI_ART)

    n_changed = sum(r["verdict_changed"] for r in all_rows)
    n_owner = sum(r["alias_admitted_owner"] for r in all_rows)
    n_tag = sum(r["same_tag"] for r in all_rows)
    L = ["# GA-1: XOR-fold identity-aliasing falsification test", "",
         ("Generated by `scripts/ga_alias_check.py` (docs/preregistration.md, GA entry). Separate research thread, not part of the D4/D4c evaluation "
          "and not referenced from REPORT.md's claims sections. For each of the 20 largest long flows per trace, one alias tuple with an equal "
          "XOR fold is merged in (one packet per 250 ms, from the flow's midpoint). `same_tag` confirms the fold construction (definitional); "
          "`alias_admitted_owner` and `verdict_changed` are the falsification test."), "",
         f"**Summary: {n_tag}/{len(all_rows)} aliases share the victim's tag (definitional check); "
         f"{n_owner}/{len(all_rows)} were admitted as owner of the victim's slot; "
         f"**{n_changed}/{len(all_rows)} victim verdicts changed with the alias present.**", "",
         "| trace | flow | packets | same tag | alias admitted owner | final result, no alias | final result, with alias | verdict changed |",
         "|---|---|---|---|---|---|---|---|"]
    for r in all_rows:
        L.append(f"| {r['trace']} | {r['flow']} | {r['packets']} | {r['same_tag']} | {r['alias_admitted_owner']} | "
                 f"{r['final_result_no_alias']} | {r['final_result_with_alias']} | {r['verdict_changed']} |")
    verdict = ("**FALSIFIED: no verdict changed.** The aliasing is confirmed as a hash property (identical tags) but not shown to be a "
               "security-relevant identity-confusion effect at this packet rate on these traces." if n_changed == 0 else
               f"**NOT falsified: {n_changed} verdict(s) changed.** The identity-aliasing effect materially altered classification outcomes.")
    L += ["", verdict]
    (ROOT / "docs/results_ga_alias.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
