"""W5 / W6: MVM-Lite on BMv2 -- demand-paged decision-tree leaves with a P4Runtime controller.

1. Train the data-plane DT on grouped seed-0 pools (the W2 protocol: depth and class weight chosen
   on validation macro-F1).
2. Encode every leaf as one range-match entry over 10 order-preserving 32-bit feature keys
   (mvm.p4encode; exact, no quantization).
3. Start simple_switch_grpc (no network interfaces: queries enter as P4Runtime packet-outs and
   answers return as packet-ins), load p4/build/mvm.json.
4. Replay two slices of the chronological replay stream, each spanning an attack-phase change:
   full stream around 04-25 -> 04-26 and benign flows around 04-27 -> 04-28. The table holds K=8
   leaves; the controller runs decayed LFU (gamma=0.99). On a miss it runs the full tree and
   installs / evicts leaf entries in one P4Runtime write.
Checks: fidelity (served prediction == tree.predict), consistency (switch hit == policy says the
leaf is resident), equivalence (hit sequence == offline simulate_fast), table occupancy <= K.
Measurements (BMv2 software switch, NOT ASIC performance): hit round trip, miss service time,
P4Runtime write rates (single and batched).

Usage: w5_bmv2.py [--quick]
"""

from __future__ import annotations

import argparse
import json
import logging
import struct
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier

from mvm.cache import DecayedLFU, simulate_fast
from mvm.features import FEATURE_SETS, TreeEncoder, columns_needed
from mvm.leaves import extract_leaf_boxes
from mvm.metrics import binary_metrics
from mvm.p4encode import box_key_ranges, f32_key
from mvm.p4rt import P4RTClient
from mvm.splits import build_keys, load_rows, replay_order, sample_pools

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("w5")
ROOT = Path(__file__).resolve().parents[1]
PQ = ROOT / "data/processed/network"
OUT = ROOT / "results/w5"
P4B = ROOT / "p4/build"
DEPTHS, CW = [4, 6, 8, 10, 12, 16, None], [None, "balanced"]
K, GAMMA, SEED = 8, 0.99, 0
GRPC, THRIFT = "127.0.0.1:50071", 9291


def train_tree(keys):
    pools, replay = sample_pools(keys, "grouped", SEED)
    fs = FEATURE_SETS["dp"]
    rows = load_rows(PQ, pools, columns_needed(fs))
    tr, va, te = (rows[rows.pool == p] for p in ("train", "val", "test"))
    enc = TreeEncoder(fs).fit(tr, tr.label.to_numpy())
    Xtr, Xva, Xte = enc.transform(tr), enc.transform(va), enc.transform(te)
    cands = [DecisionTreeClassifier(max_depth=d, class_weight=cw, random_state=SEED).fit(Xtr, tr.label) for d in DEPTHS for cw in CW]
    val_f1 = [binary_metrics(va.label.to_numpy(), m.predict(Xva))["macro_f1"] for m in cands]
    tree = cands[int(np.argmax(val_f1))]
    info = {"depth": str(tree.max_depth), "class_weight": str(tree.class_weight), "n_leaves": int(tree.get_n_leaves()),
            "val_macro_f1": float(max(val_f1)), "test_macro_f1": binary_metrics(te.label.to_numpy(), tree.predict(Xte))["macro_f1"]}
    return tree, enc, replay, info


def slice_rows(keys, gidx: np.ndarray, columns) -> pd.DataFrame:
    """Load rows for global indices, preserving order (row_in_file is the row position in its file)."""
    k = keys.iloc[gidx][["file_idx", "row_in_file"]].reset_index(drop=True)
    out = [None] * len(k)
    parts = []
    for f, g in k.groupby("file_idx"):
        df = pd.read_parquet(PQ / f"Network_dataset_{int(f)}.parquet", columns=columns).iloc[g.row_in_file.to_numpy()]
        parts.append(df.set_axis(g.index))
    return pd.concat(parts).sort_index()


def boundary_slice(keys, order: np.ndarray, mask_rows: np.ndarray, new_day: str, n_side: int) -> np.ndarray:
    """n_side replay flows (restricted by mask_rows) before and after the first flow of new_day."""
    sub = order[mask_rows]
    day = keys.day.to_numpy()[sub].astype(str)
    b = int(np.argmax(day == new_day))
    assert day[b] == new_day and b > 0, new_day
    return sub[max(0, b - n_side): b + n_side]


def start_switch():
    log_f = open(OUT / "bmv2.log", "w")
    proc = subprocess.Popen(["simple_switch_grpc", "--no-p4", "--thrift-port", str(THRIFT), "--log-level", "warn",
                             "--", "--grpc-server-addr", GRPC, "--cpu-port", "255"], stdout=log_f, stderr=subprocess.STDOUT)
    time.sleep(2)
    assert proc.poll() is None, "simple_switch_grpc exited at startup; see results/w5/bmv2.log"
    return proc


def replay_slice(c: P4RTClient, name, X, key32, tree, leaf_true, pred_true, ranges_of):
    md_out, md_in = c.packet_md("packet_out")["query_id"], c.packet_md("packet_in")
    pol = DecayedLFU(gamma=GAMMA)
    pol.reset(K, None)
    installed = {}
    recs = []
    for t in range(len(key32)):
        t0 = time.perf_counter()
        c.packet_out(struct.pack(">10I", *key32[t].tolist()), {md_out: t})
        pkt = c.packet_in.get(timeout=10)
        rtt = time.perf_counter() - t0
        m = {x.metadata_id: int.from_bytes(x.value, "big") for x in pkt.metadata}
        assert m[md_in["query_id"]] == t, "out-of-order packet-in"
        sw_hit, sw_class, sw_leaf = m[md_in["hit"]], m[md_in["klass"]], m[md_in["leaf_id"]]
        before = set(pol.resident)
        p_hit = pol.access(t, int(leaf_true[t]))
        after = set(pol.resident)
        backend_s = write_s = 0.0
        if sw_hit:
            served = sw_class
        else:
            t1 = time.perf_counter()
            served = int(tree.predict(X[t:t + 1])[0])  # backend: the full tree
            t2 = time.perf_counter()
            dels = [installed.pop(l) for l in before - after]
            ins = []
            for l in after - before:
                lo, hi, klass = ranges_of[l]
                installed[l] = c.range_entry("leaf_tbl", list(zip(lo, hi)), "leaf_hit", {"leaf_id": l, "klass": klass})
                ins.append(installed[l])
            if dels:
                c.write(dels, "DELETE")
            if ins:
                c.write(ins, "INSERT")
            write_s = time.perf_counter() - t2
            backend_s = t2 - t1
        recs.append({"slice": name, "t": t, "switch_hit": bool(sw_hit), "policy_hit": bool(p_hit),
                     "switch_leaf": sw_leaf if sw_hit else -1, "true_leaf": int(leaf_true[t]),
                     "served": served, "tree_pred": int(pred_true[t]), "rtt_ms": rtt * 1e3,
                     "backend_ms": backend_s * 1e3, "write_ms": write_s * 1e3,
                     "service_ms": (time.perf_counter() - t0) * 1e3, "n_installed": len(installed)})
    if installed:
        c.write(list(installed.values()), "DELETE")
    assert c.read_table_count("leaf_tbl") == 0
    return pd.DataFrame(recs)


def write_benchmark(c: P4RTClient, n=1000, batch=100):
    ents = [c.range_entry("leaf_tbl", [(10 * i, 10 * i + 9)] + [(0, 0xFFFFFFFF)] * 9, "leaf_hit", {"leaf_id": i, "klass": 1})
            for i in range(n)]
    res = {}
    t = time.perf_counter()
    for e in ents:
        c.write([e], "INSERT")
    res["single_insert_per_s"] = n / (time.perf_counter() - t)
    t = time.perf_counter()
    for e in ents:
        c.write([e], "DELETE")
    res["single_delete_per_s"] = n / (time.perf_counter() - t)
    t = time.perf_counter()
    for i in range(0, n, batch):
        c.write(ents[i:i + batch], "INSERT")
    res["batched_insert_per_s"] = n / (time.perf_counter() - t)
    assert c.read_table_count("leaf_tbl") == n
    t = time.perf_counter()
    for i in range(0, n, batch):
        c.write(ents[i:i + batch], "DELETE")
    res["batched_delete_per_s"] = n / (time.perf_counter() - t)
    res.update(n_entries=n, batch=batch)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="gate: 1,000 queries per slice, small write benchmark")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    n_side = 500 if args.quick else 15_000
    keys = build_keys(PQ, ROOT / "data/processed/keys.parquet")
    tree, enc, replay, info = train_tree(keys)
    log.info("tree: %s", info)
    order = replay_order(keys, replay)
    label = keys.label.to_numpy()[order]
    slices = {"full_0425_to_0426": boundary_slice(keys, order, np.ones(len(order), bool), "2019-04-26", n_side),
              "benign_0427_to_0428": boundary_slice(keys, order, label == 0, "2019-04-28", n_side)}
    boxes = extract_leaf_boxes(tree)
    ranges_of = {b.leaf_id: (*box_key_ranges(b), int(b.klass)) for b in boxes}
    cols = columns_needed(FEATURE_SETS["dp"])
    proc = start_switch()
    try:
        c = P4RTClient(GRPC, P4B / "mvm.p4info.txt")
        c.set_pipeline(P4B / "mvm.json")
        frames = []
        for name, g in slices.items():
            X = enc.transform(slice_rows(keys, g, cols))
            key32 = f32_key(X)
            leaf_true, pred_true = tree.apply(X), tree.predict(X)
            df = replay_slice(c, name, X, key32, tree, leaf_true, pred_true, ranges_of)
            sim = simulate_fast("dlfu", leaf_true, K, gamma=GAMMA).hits
            df["sim_hit"] = sim
            frames.append(df)
            log.info("%s: %d queries, switch hit rate %.4f, sim %.4f", name, len(df), df.switch_hit.mean(), sim.mean())
        q = pd.concat(frames, ignore_index=True)
        bench = write_benchmark(c, n=200 if args.quick else 1000, batch=100)
        c.close()
    finally:
        proc.terminate()
        proc.wait(10)

    checks = {
        "fidelity_served_eq_tree": bool((q.served == q.tree_pred).all()),
        "consistency_switch_eq_policy": bool((q.switch_hit == q.policy_hit).all()),
        "hit_leaf_correct": bool((q[q.switch_hit].switch_leaf == q[q.switch_hit].true_leaf).all()),
        "equivalence_switch_eq_simulator": bool((q.switch_hit == q.sim_hit).all()),
        "occupancy_le_K": bool((q.n_installed <= K).all()),
    }
    summary = {"tree": info, "K": K, "gamma": GAMMA, "checks": checks, "write_benchmark": bench, "slices": {}}
    for name, g in q.groupby("slice"):
        hit, miss = g[g.switch_hit], g[~g.switch_hit]
        summary["slices"][name] = {
            "queries": len(g), "hit_rate": float(g.switch_hit.mean()), "sim_hit_rate": float(g.sim_hit.mean()),
            "fidelity": float((g.served == g.tree_pred).mean()),
            "hit_rtt_ms": {p: float(np.percentile(hit.rtt_ms, p)) for p in (50, 95, 99)} if len(hit) else {},
            "miss_service_ms": {p: float(np.percentile(miss.service_ms, p)) for p in (50, 95, 99)} if len(miss) else {},
            "miss_write_ms_p50": float(miss.write_ms.median()) if len(miss) else None,
            "miss_backend_ms_p50": float(miss.backend_ms.median()) if len(miss) else None,
            "mean_service_ms": float(g.service_ms.mean()),
            "table_writes_per_query": float((~g.switch_hit).mean()),
        }
    tag = "_quick" if args.quick else ""
    q.to_parquet(OUT / f"queries{tag}.parquet", index=False)
    (OUT / f"summary{tag}.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    failed = [k for k, v in checks.items() if not v]
    if failed:
        log.error("CHECKS FAILED: %s", failed)
        sys.exit(1)
    log.info("W5 %s OK", "QUICK" if args.quick else "RUN")


if __name__ == "__main__":
    main()
