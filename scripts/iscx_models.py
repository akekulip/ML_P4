"""G7: retrained NetBeacon-style models on ISCXVPN2016, gate G7-0 and the table-size rule -> docs/results_g7_gates.md, results/g7/models_fold*.joblib

Cross-fit by session-pair group (docs/preregistration.md, G7 entry): fold f flows are scored by models trained on the other fold (P2P, one capture, is split
by time with flows across the midpoint left out of training). Training rows come from the emulator's own accumulators: one isolated run records every
phase event (features) and the class of its flow. These are retrained models, not the shipped ones.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from g4_peerrush_report import macro_f1

from dgrade.netbeacon import FLOW_FEATURES, PHASES
from dgrade.netbeacon_sim import NEW_OWNER, NetBeaconSim, StubModels, flow_ids
from dgrade.sklearn_models import SklearnModels

OUT = ROOT / "results/g7"
NC = 5
_REC: dict = {}


class RecordingSim(NetBeaconSim):
    """Isolated run that records every phase event (features and packet index)."""

    def _evaluate_events(self, ev_phase, ev_feat, ev_code):
        _REC["phase"], _REC["feat"] = list(ev_phase), list(ev_feat)
        return super()._evaluate_events(ev_phase, ev_feat, ev_code)

    @staticmethod
    def _resolve(pk, fh, slot, outcome, vkind, vepoch, vevent, memo_val, pkt_code, epoch_init, epoch_events, ev_phase, ev_pkt, codes, long_):
        _REC["pkt"] = list(ev_pkt)
        return NetBeaconSim._resolve(pk, fh, slot, outcome, vkind, vepoch, vevent, memo_val, pkt_code, epoch_init, epoch_events, ev_phase, ev_pkt, codes, long_)


def class_of(result: np.ndarray) -> np.ndarray:
    r = result.astype(np.int64)
    return np.where(r == 0, -1, (r - 1) % 50)


def f1(truth: np.ndarray, pred: np.ndarray) -> float:
    p = np.where(pred < 0, NC, pred)
    cm = np.bincount(truth.astype(np.int64) * (NC + 1) + p, minlength=NC * (NC + 1)).reshape(NC, NC + 1)
    f = []
    for c in range(NC):
        tp, fp, fn = cm[c, c], cm[:, c].sum() - cm[c, c], cm[c].sum() - cm[c, c]
        f.append(0.0 if (tp + fp + fn) == 0 else 2 * tp / (2 * tp + fp + fn))
    return float(np.mean(f))


def main() -> None:
    z = np.load(OUT / "stream.npz")
    pk, cap, cls = z["pk"], z["cap"], z["cls"].astype(np.int64)
    caps = json.loads((OUT / "captures.json").read_text())
    group_of_cap = np.array([c["group"] for c in caps["captures"]])
    fid = flow_ids(pk, 1 << 62)
    nf = int(fid.max()) + 1
    first = np.full(nf, len(pk), dtype=np.int64)
    np.minimum.at(first, fid, np.arange(len(pk)))
    flen = np.bincount(fid, minlength=nf)
    fcls, fgrp = cls[first], group_of_cap[cap[first]]
    fts0 = pk["ts_ns"][first]
    fts1 = np.zeros(nf, dtype=np.int64)
    np.maximum.at(fts1, fid, pk["ts_ns"])

    # folds: groups alternate within a class; P2P (one group) is split by time at the median first-packet time
    fold = np.zeros(nf, dtype=np.int8)
    straddle = np.zeros(nf, dtype=bool)
    for c in range(NC):
        groups = sorted(set(fgrp[fcls == c]))
        if len(groups) > 1:
            for gi, g in enumerate(groups):
                fold[(fcls == c) & (fgrp == g)] = gi % 2
        else:
            m = fcls == c
            mid = np.median(fts0[m])
            fold[m] = (fts0[m] >= mid).astype(np.int8)
            straddle[m] = (fts0[m] < mid) & (fts1[m] >= mid)
    fold_pkt = fold[fid]

    # one isolated recording run
    sim = RecordingSim(models=StubModels(80, 1), clock_offset_ns=300 * (1 << 20))
    sim.run(pk, isolate=fid)
    ev_phase, ev_pkt = np.array(_REC["phase"]), np.array(_REC["pkt"])
    ev_feat = np.array(_REC["feat"], dtype=np.int64)
    ev_flow = fid[ev_pkt]

    X_pkt = np.stack([pk[f].astype(np.int64) for f in ("proto", "total_len", "diffserv", "ttl", "tcp_dataOffset", "tcp_window", "udp_length")], axis=1)
    rng = np.random.default_rng(0)
    order = np.lexsort((pk["ts_ns"], fid))                       # packets grouped by flow, time order
    rank = np.empty(len(pk), dtype=np.int64)
    rank[order] = np.arange(len(pk)) - np.repeat(np.cumsum(flen) - flen, flen)   # position of each packet within its flow

    summary: dict = {"folds": {}}
    models_by_fold = {}
    for f in (0, 1):
        train_flow = (fold != f) & ~straddle
        tr = train_flow[fid]
        elig = flen >= 8
        thr = float(np.percentile(flen[train_flow & elig], 80))
        # per-packet fallback tree: a subsample of packets of training flows
        idx = np.flatnonzero(tr)
        idx = rng.choice(idx, min(len(idx), 1_000_000), replace=False)
        pkt_tree = DecisionTreeClassifier(max_depth=9, min_samples_leaf=20, class_weight="balanced", random_state=0).fit(X_pkt[idx], cls[idx])
        # flow-size gate: first eight packets of every training flow, label = flow longer than the 80th-percentile length
        gi = np.flatnonzero(tr & (rank < 8))
        size_tree = DecisionTreeClassifier(max_depth=8, min_samples_leaf=50, class_weight="balanced", random_state=0).fit(
            X_pkt[gi], (flen[fid[gi]] > thr).astype(int))
        phases = {}
        rows_by_phase = {}
        for p in PHASES:
            sel = (ev_phase == p) & train_flow[ev_flow]
            rows_by_phase[p] = int(sel.sum())
            if sel.sum() < 5 or len(np.unique(fcls[ev_flow[sel]])) < 2:
                continue
            depth, leaf = (4, 3) if p == 2048 else (8, 5)
            phases[p] = DecisionTreeClassifier(max_depth=depth, min_samples_leaf=leaf, class_weight="balanced", random_state=0).fit(
                ev_feat[sel], fcls[ev_flow[sel]])
        models_by_fold[f] = SklearnModels(pkt_tree, size_tree, phases)
        joblib.dump(models_by_fold[f], OUT / f"models_fold{f}.joblib")
        summary["folds"][f] = {"gate_threshold_packets": thr, "train_flows": int(train_flow.sum()), "rows_by_phase": rows_by_phase,
                               "phases_trained": sorted(phases)}
        print("fold", f, summary["folds"][f], flush=True)

    # G7-0: isolated full model against per-packet fallback on long flows (held-out flows only)
    res = np.zeros(len(pk), dtype=np.int64)
    fb = np.zeros(len(pk), dtype=np.int64)
    owner = np.zeros(len(pk), dtype=bool)
    for f in (0, 1):
        mdl = models_by_fold[f]
        out = NetBeaconSim(models=mdl, clock_offset_ns=300 * (1 << 20)).run(pk, isolate=fid)
        m = fold_pkt == f
        res[m] = out["result"][m]
        fb[m] = mdl.pkt_codes(pk)[m]
        owner[m] = out["outcome"][m] == NEW_OWNER
    long_pkt = (flen > 50)[fid]
    scored = long_pkt
    full_f1 = f1(cls[scored], class_of(res)[scored])
    fb_f1 = f1(cls[scored], (fb[scored] - 1))
    all_full, all_fb = f1(cls, class_of(res)), f1(cls, fb - 1)
    no_p2p = scored & (cls != 3)
    gap = full_f1 - fb_f1
    verdict = "proceed" if gap >= 0.10 else "descriptive only" if gap >= 0.03 else "KILL"
    summary["G7_0"] = {"full_f1_long": full_f1, "fallback_f1_long": fb_f1, "gap_long": gap, "verdict": verdict, "full_f1_all": all_full, "fallback_f1_all": all_fb,
                       "gap_long_without_p2p": f1(cls[no_p2p], class_of(res)[no_p2p]) - f1(cls[no_p2p], fb[no_p2p] - 1)}

    # table size rule: median number of alive predicted-long flows (flows that took a slot in the isolated run), 10 s samples
    took = np.zeros(nf, dtype=bool)
    took[fid[owner]] = True
    samples = np.arange(10e9, pk["ts_ns"].max(), 10e9)
    alive = np.array([np.sum(took & (fts0 <= t) & (fts1 >= t)) for t in samples])
    med = float(np.median(alive))
    N = 512
    while med > 0.07 * N and N < 65536:
        N *= 2
    summary["occupancy"] = {"median_alive_long": med, "p10": float(np.percentile(alive, 10)), "p90": float(np.percentile(alive, 90)), "max": int(alive.max()),
                            "table_slots": N, "occupancy_at_N": med / N}
    summary["flows"] = {"total": nf, "long_gt50": int((flen > 50).sum()), "by_class_long": {int(c): int(((fcls == c) & (flen > 50)).sum()) for c in range(NC)}}
    (OUT / "gates.json").write_text(json.dumps(summary, indent=1, default=float))

    names = caps["class_names"]
    g0 = summary["G7_0"]
    L = ["# G7 gates: retrained models on ISCXVPN2016 and the table-size rule", "",
         ("Generated by `scripts/iscx_models.py`. Retrained NetBeacon-style models (scikit-learn trees; **not** the shipped ones), cross-fit by session-pair group; "
          "held-out flows only. Classes: " + ", ".join(names) + ". Packet-level macro-F1 against the capture label."), "",
         "## G7-0: does the full-state path beat the per-packet fallback?", "",
         "| population | full model macro-F1 (isolated) | per-packet fallback macro-F1 | gap |", "|---|---|---|---|",
         f"| flows with more than 50 packets (primary) | {g0['full_f1_long']:.3f} | {g0['fallback_f1_long']:.3f} | {g0['gap_long']:+.3f} |",
         f"| flows with more than 50 packets, P2P excluded | | | {g0['gap_long_without_p2p']:+.3f} |",
         f"| all flows | {g0['full_f1_all']:.3f} | {g0['fallback_f1_all']:.3f} | {g0['full_f1_all'] - g0['fallback_f1_all']:+.3f} |", "",
         f"Pre-registered rule: at least 0.10 proceeds, 0.03 to 0.10 is descriptive only, below 0.03 kills the workload. **Verdict: {verdict}.**", "",
         "## Folds and models", "", "| fold | gate threshold (packets) | training flows | phase-event rows (2, 4, 8, 32, 256, 512, 2048) | phase trees trained |", "|---|---|---|---|---|"]
    for f in (0, 1):
        s = summary["folds"][f]
        L.append(f"| {f} | {s['gate_threshold_packets']:.0f} | {s['train_flows']:,} | {', '.join(str(s['rows_by_phase'][p]) for p in PHASES)} | {s['phases_trained']} |")
    o = summary["occupancy"]
    L += ["", "## Table-size rule (from concurrency only)", "",
          (f"Alive flows that took a slot in the isolated run, 10 s samples: median {o['median_alive_long']:.0f}, p10 {o['p10']:.0f}, p90 {o['p90']:.0f}, max {o['max']}. "
           f"Smallest power of two, at least 512, with median occupancy at most 7%: **N = {o['table_slots']:,} slots** (occupancy {o['occupancy_at_N']:.1%})."), "",
          ("Flows: " + f"{nf:,} in total, {summary['flows']['long_gt50']:,} with more than 50 packets."), "",
          "Deviation from the pre-registration, stated: the retrained trees are evaluated directly by the emulator; no switch-table quantisation of them is modelled "
          "(G7-1 is therefore the adapter contract and tree-agreement tests in `tests/test_dgrade_sklearn_models.py`, not a table-versus-tree comparison). "
          "The gate is out-of-fold for scored flows only: the other fold's flows are replayed with the same fold's models."]
    (ROOT / "docs/results_g7_gates.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
