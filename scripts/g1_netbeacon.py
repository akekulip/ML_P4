"""Gate G1 (docs/preregistration.md, H1): NetBeacon's full model against its per-packet fallback on
benign PeerRush traffic. Nothing is generated: the six captures are replayed as they were recorded.

  g1_netbeacon.py --stream          build and cache the merged packet stream
  g1_netbeacon.py --job iso         isolated run: every flow gets its own slot (full-model reference)
  g1_netbeacon.py --job SEED        published provisioning (65,536 slots); SEED sets the clock start
  g1_netbeacon.py --report          write docs/results_g1.md from the saved runs

Each capture is shifted to start at t = 0 and given its own address range, so flows from different
captures never share a 5-tuple. Class labels come from the capture. Runs are separate processes.
"""

from __future__ import annotations

import argparse
import glob
import itertools
from pathlib import Path

import numpy as np
import pandas as pd

from dgrade.netbeacon import load_tables
from dgrade.netbeacon_sim import (
    FALLBACK_COLLISION,
    FALLBACK_EMPTY,
    REJECTED,
    NetBeaconSim,
    TableModels,
    flow_ids,
)
from dgrade.pcap import read_pcap

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/raw/bos_datasets/PeerRush/source"
OUT = ROOT / "results/g1"
ART = ROOT / "third_party/NetBeacon"
APPS = {"eMule": 0, "uTorrent": 1, "Vuze": 2}      # PeerRush/labels.json in the BoS release
N_CLASS = 3
TUPLE_ONLY = 1 << 62   # no idle splitting: the switch identifies a flow by its hash alone (switch.p4:606)


def build_stream() -> tuple[np.ndarray, np.ndarray]:
    parts, labels = [], []
    for k, f in enumerate(sorted(glob.glob(str(DATA / "*/*/*.pcap")))):
        pk, _ = read_pcap(f)
        pk["ts_ns"] -= pk["ts_ns"].min()
        pk["src_ip"] = pk["src_ip"] % (1 << 24) + (k + 1) * (1 << 24)   # keep the low 24 bits, split by capture
        pk["dst_ip"] = pk["dst_ip"] % (1 << 24) + (k + 1) * (1 << 24)
        parts.append(pk)
        labels.append(np.full(len(pk), APPS[Path(f).parts[-3]], dtype=np.int8))
    pk, lab = np.concatenate(parts), np.concatenate(labels)
    o = np.argsort(pk["ts_ns"], kind="stable")
    return pk[o], lab[o]


def load_stream() -> tuple[np.ndarray, np.ndarray]:
    p = OUT / "stream.npz"
    if not p.exists():
        OUT.mkdir(parents=True, exist_ok=True)
        pk, lab = build_stream()
        np.savez(p, pk=pk, lab=lab)
    z = np.load(p)
    return z["pk"], z["lab"]


def run_job(job: str) -> None:
    pk, _ = load_stream()
    models = TableModels(load_tables(ART))
    if job == "iso":
        sim = NetBeaconSim(models=models, seed=0)
        out = sim.run(pk, isolate=flow_ids(pk, TUPLE_ONLY))
    else:
        out = NetBeaconSim(models=models, seed=int(job)).run(pk)
    np.savez(OUT / f"run_{job}.npz", outcome=out["outcome"], result=out["result"], source=out["source"].astype(str),
             offset=out["clock_offset_ns"])
    print(job, "done", np.bincount(out["outcome"], minlength=7))


def class_of(result: np.ndarray) -> np.ndarray:
    """Class index from ``ig_md.result``: 1..3 are class+1, 51..53 are determined (+50); 0 is no verdict."""
    r = result.astype(np.int64)
    return np.where(r == 0, -1, (r - 1) % 50)


def confusion(truth: np.ndarray, pred: np.ndarray, perm: tuple[int, ...]) -> np.ndarray:
    """3 x 4 counts; column 3 is 'no verdict or invalid'. ``perm[i]`` is the app of NetBeacon class i."""
    p = np.where(pred < 0, 3, np.asarray(perm)[np.clip(pred, 0, N_CLASS - 1)])
    return np.bincount(truth.astype(np.int64) * 4 + p, minlength=12).reshape(3, 4)


def macro_f1(cm: np.ndarray) -> float:
    f = []
    for c in range(N_CLASS):
        tp, fp, fn = cm[c, c], cm[:, c].sum() - cm[c, c], cm[c].sum() - cm[c, c]
        f.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return float(np.mean(f))


def report() -> None:
    pk, lab = load_stream()
    fid = flow_ids(pk, TUPLE_ONLY)
    iso = np.load(OUT / "run_iso.npz")
    runs = {int(Path(p).stem.split("_")[1]): np.load(p) for p in glob.glob(str(OUT / "run_[0-9]*.npz"))}
    seeds = sorted(runs)
    keep = iso["outcome"] != REJECTED
    truth, iso_cls = lab[keep], class_of(iso["result"][keep])
    perms = list(itertools.permutations(range(N_CLASS)))
    scores = {p: macro_f1(confusion(truth, iso_cls, p)) for p in perms}
    perm = max(scores, key=scores.get)
    second = sorted(scores.values())[-2]
    n_flows = len(np.unique(fid[keep]))
    sec = (pk["ts_ns"][keep] // 10**9).astype(np.int64)

    rows, boot_in = [], []
    for s in seeds:
        r = runs[s]
        oc = r["outcome"][keep]
        con_cls = class_of(r["result"][keep])
        f = fid[keep]
        coll = pd.Series(oc == FALLBACK_COLLISION).groupby(f).any()
        empt = pd.Series(oc == FALLBACK_EMPTY).groupby(f).any()
        down = coll
        d_pk = down.reindex(f).to_numpy()
        cm_full = confusion(truth[d_pk], iso_cls[d_pk], perm)
        cm_con = confusion(truth[d_pk], con_cls[d_pk], perm)
        rows.append({"seed": s, "flows": n_flows, "downgraded_flows": int(down.sum()),
                     "downgraded_flow_share": float(down.mean()),
                     "downgraded_packet_share": float(d_pk.mean()),
                     "flows_with_empty_refusal": int(empt.sum()),
                     "f1_all_isolated": macro_f1(confusion(truth, iso_cls, perm)),
                     "f1_all_contended": macro_f1(confusion(truth, con_cls, perm)),
                     "f1_down_full": macro_f1(cm_full), "f1_down_fallback": macro_f1(cm_con),
                     "gap_down": macro_f1(cm_full) - macro_f1(cm_con)})
        if s == seeds[0]:
            boot_in = (truth, iso_cls, con_cls, d_pk, sec)
    df = pd.DataFrame(rows)

    truth, iso_cls, con_cls, d_pk, sec = boot_in
    idx = np.flatnonzero(d_pk)
    blocks = np.unique(sec[idx])
    cf = {b: confusion(truth[idx][sec[idx] == b], iso_cls[idx][sec[idx] == b], perm) for b in blocks}
    cc = {b: confusion(truth[idx][sec[idx] == b], con_cls[idx][sec[idx] == b], perm) for b in blocks}
    rng = np.random.default_rng(0)
    gaps = []
    for _ in range(1000):
        pick = rng.choice(blocks, len(blocks))
        gaps.append(macro_f1(sum(cf[b] for b in pick)) - macro_f1(sum(cc[b] for b in pick)))
    lo, hi = np.percentile(gaps, [2.5, 97.5])

    m = df.mean(numeric_only=True)
    L = ["# Gate G1 results: NetBeacon full model against its per-packet fallback (benign PeerRush)", "",
         ("Generated by `scripts/g1_netbeacon.py --report` from `results/g1/`. Traffic is the six recorded PeerRush "
         "captures replayed together (4.85 M packets after the parser filter, one hour, shifted to a common start); "
         "nothing is generated. Table size 65,536 slots, NetBeacon's shipped timeout and hash."), "",
         (f"- Flows: {n_flows:,}. Seeds: {len(seeds)} (each seed sets the switch-clock start; the hash is unkeyed, so "
         "slots do not change between seeds)."),
         (f"- Class numbering: NetBeacon's class index was mapped to the app by the permutation that maximises the "
         f"isolated run's macro-F1: {dict(zip(range(3), [list(APPS)[i] for i in perm]))} "
         f"(F1 {scores[perm]:.3f}; next best {second:.3f}). This one choice used the labels and is fixed for all numbers."),
         "", "## Downgrade under benign load", "",
         "| seed | downgraded flows | share of flows | share of packets | flows refused an empty slot |", "|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['seed']} | {r['downgraded_flows']:,} | {r['downgraded_flow_share']:.4%} | "
                 f"{r['downgraded_packet_share']:.4%} | {r['flows_with_empty_refusal']:,} |")
    L += ["", ("A flow is downgraded when an active incumbent refused it a slot (collision). Empty-slot refusals are "
          "reported separately and are not counted."), "",
          "## Accuracy: packet-level macro-F1", "",
          "| population | full model (isolated) | fallback (contended run) | gap |", "|---|---|---|---|",
          f"| all flows | {m.f1_all_isolated:.4f} | {m.f1_all_contended:.4f} | {m.f1_all_isolated - m.f1_all_contended:+.4f} |",
          f"| downgraded flows only (mean of seeds) | {m.f1_down_full:.4f} | {m.f1_down_fallback:.4f} | {m.gap_down:+.4f} |",
          "", (f"Seed-0 downgraded-flow gap {rows[0]['gap_down']:+.4f}, 95% CI [{lo:+.4f}, {hi:+.4f}] "
          "(1,000 resamples of 1-second blocks)."), "",
          "## H1 status (pre-registered pass ≥ 0.10 on one victim; falsified < 0.03 on all)", ""]
    g = m.gap_down
    L.append("This measures only the benign-only population on PeerRush, one victim task. "
             + ("Gap ≥ 0.10: H1 pass on this task." if g >= 0.10 else
                "Gap < 0.03: this task is consistent with H1's falsifier." if g < 0.03 else
                "Gap between 0.03 and 0.10: neither pass nor falsified on this task."))
    L += ["", ("The pre-registered H1 population is flows downgraded under attack; that needs the attack model and is not "
          "part of G1. This result is the benign reference.")]
    (ROOT / "docs/results_g1.md").write_text("\n".join(L) + "\n")
    df.to_csv(OUT / "summary.csv", index=False)
    print("\n".join(L))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream", action="store_true")
    ap.add_argument("--job")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.stream:
        pk, lab = load_stream()
        print(len(pk), np.bincount(lab))
    elif a.job:
        run_job(a.job)
    elif a.report:
        report()
