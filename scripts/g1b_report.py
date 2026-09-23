"""G1b report: hash arms on benign PeerRush, following docs/preregistration.md (change log, 2026-09-23).

Reads results/g1/g1b_*.npz (made by ``g1_netbeacon.py --job KIND[:SEED]@GRID``) and writes
docs/results_g1b.md. Every run is paired with the isolated reference at the same clock start.
Primary metric L = macro-F1(isolated) - macro-F1(contended) over all flows.
"""

from __future__ import annotations

import glob
import itertools
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import beta

from dgrade.flowstats import FlowIndex, downgraded_flows
from dgrade.netbeacon_sim import flow_ids

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/g1"
N_CLASS = 3
TUPLE_ONLY = 1 << 62
BIG = 0.004                     # p_big threshold, fixed in the pre-registration
EQUIV_L, EQUIV_SHARE = 0.002, 0.001   # share bound is 0.1 percentage points as a fraction
DRAWS = 30
GRID = 30
KEYED = ("xorsalt", "poly", "polyirr")   # each has a clock-varied arm (seed == grid) and a fixed-clock arm (grid 0)


def class_of(result: np.ndarray) -> np.ndarray:
    r = result.astype(np.int64)
    return np.where(r == 0, -1, (r - 1) % 50)


def confusion(truth, pred, perm) -> np.ndarray:
    p = np.where(pred < 0, 3, np.asarray(perm)[np.clip(pred, 0, N_CLASS - 1)])
    return np.bincount(truth.astype(np.int64) * 4 + p, minlength=12).reshape(3, 4)


def macro_f1(cm) -> float:
    f = []
    for c in range(N_CLASS):
        tp, fp, fn = cm[c, c], cm[:, c].sum() - cm[c, c], cm[c].sum() - cm[c, c]
        f.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return float(np.mean(f))


def cp_interval(k: int, n: int, a: float = 0.05) -> tuple[float, float]:
    lo = 0.0 if k == 0 else beta.ppf(a / 2, k, n - k + 1)
    hi = 1.0 if k == n else beta.ppf(1 - a / 2, k + 1, n - k)
    return float(lo), float(hi)


def boot_ci(x: np.ndarray, q=(5, 95), n=4000, seed=0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    m = np.array([rng.choice(x, len(x)).mean() for _ in range(n)])
    return tuple(float(v) for v in np.percentile(m, q))


def parse(path: str) -> tuple[str, int | None, int]:
    m = re.match(r"g1b_([a-z]+)(?:_(\d+))?_at(\d+)\.npz", Path(path).name)
    return m.group(1), (int(m.group(2)) if m.group(2) else None), int(m.group(3))


def rule_status(lo: float, hi: float, bound: float) -> str:
    """pass: the interval lies inside +-bound; fail: entirely outside; else inconclusive."""
    if -bound <= lo and hi <= bound:
        return "pass"
    if lo > bound or hi < -bound:
        return "fail"
    return "inconclusive"


def per_flow_conf(idx: FlowIndex, truth, pred, perm) -> np.ndarray:
    p = np.where(pred < 0, 3, np.asarray(perm)[np.clip(pred, 0, N_CLASS - 1)])
    return np.bincount(idx.code * 12 + truth.astype(np.int64) * 4 + p, minlength=idx.n_flows * 12).reshape(-1, 12)


def within_draw_ci(m_iso: np.ndarray, m_con: np.ndarray, n=1000, seed=0) -> tuple[float, float]:
    """95% flow-cluster bootstrap interval of L for one draw: resample flows with replacement."""
    rng = np.random.default_rng(seed)
    F = len(m_iso)
    w = rng.multinomial(F, np.full(F, 1.0 / F), size=n)
    a, b = w @ m_iso, w @ m_con
    ls = [macro_f1(x.reshape(3, 4)) - macro_f1(y.reshape(3, 4)) for x, y in zip(a, b)]
    return tuple(float(v) for v in np.percentile(ls, [2.5, 97.5]))


def main() -> None:
    z = np.load(OUT / "stream.npz")
    pk_all, lab_all = z["pk"], z["lab"]
    iso0 = np.load(OUT / "g1b_iso_at0.npz")
    keep = iso0["outcome"] != 5
    pk, truth = pk_all[keep], lab_all[keep]
    idx = FlowIndex(flow_ids(pk, TUPLE_ONLY))
    perms = list(itertools.permutations(range(N_CLASS)))
    sc = {p: macro_f1(confusion(truth, class_of(iso0["result"][keep]), p)) for p in perms}
    perm = max(sc, key=sc.get)
    top20 = np.argsort(-idx.n_pkts, kind="stable")[:20]
    first = idx.order[idx.start]                     # first packet of each flow

    def cls_ok(cls, tr, pm):
        return np.where(cls < 0, False, np.asarray(pm)[np.clip(cls, 0, N_CLASS - 1)] == tr)

    iso_cache: dict[int, dict] = {}

    def iso(g: int) -> dict:
        if g not in iso_cache:
            r = np.load(OUT / f"g1b_iso_at{g}.npz")
            cls = class_of(r["result"][keep])
            iso_cache[g] = {"cls": cls, "f1": macro_f1(confusion(truth, cls, perm)),
                            "ok": idx.per_flow_sum(cls_ok(cls, truth, perm)), "raw": r["result"]}
        return iso_cache[g]

    rows, outs = [], {}
    for path in sorted(glob.glob(str(OUT / "g1b_*.npz"))):
        if "_p_d" in Path(path).name:          # defended runs (G4) are read by the G4 report
            continue
        kind, seed, g = parse(path)
        if kind == "iso":
            continue
        r = np.load(path)
        oc, con = r["outcome"][keep], class_of(r["result"][keep])
        ref = iso(g)
        flag = downgraded_flows(oc, idx)
        d_pk = flag[idx.code]
        loss = ref["ok"] - idx.per_flow_sum(cls_ok(con, truth, perm))
        rows.append({
            "kind": kind, "seed": seed, "grid": g,
            "L": ref["f1"] - macro_f1(confusion(truth, con, perm)),
            "down_flows": int(flag.sum()), "down_flow_share": float(flag.mean()),
            "down_pkt_share": float(d_pk.mean()),
            "net_pkts_lost": float(loss.sum()), "top20_pkts_lost": float(loss[top20].sum()),
            "gap_down": macro_f1(confusion(truth[d_pk], ref["cls"][d_pk], perm))
            - macro_f1(confusion(truth[d_pk], con[d_pk], perm)),
        })
        outs[(kind, seed, g)] = (oc, flag)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "g1b_summary.csv", index=False)

    def arm(name: str) -> pd.DataFrame:
        if name == "crc":
            return df[df.kind == "crc"].sort_values("grid")
        kind, _, mode = name.partition(":")
        if mode == "varied":
            return df[(df.kind == kind) & ((df.seed == df.grid) | df.seed.isna())].sort_values("grid")
        return df[(df.kind == kind) & (df.grid == 0)].sort_values("seed")

    labels = {"crc": "crc (unkeyed, clock varied)"}
    names = ["crc"] + [f"{k}:{m}" for k in KEYED for m in ("varied", "fixed")] + ["tab:varied"]
    for n_ in names[1:]:
        k, _, m = n_.partition(":")
        labels[n_] = f"{k} ({'clock varied' if m == 'varied' else 'clock fixed at grid 0'})"
    arms = {n_: arm(n_) for n_ in names if len(arm(n_))}
    missing = [labels[n_] for n_ in names if n_ not in arms]
    crc = arms["crc"]
    crc0 = crc[crc.grid == 0].iloc[0]

    L = ["# Gate G1b results: hash arms on benign PeerRush (NetBeacon emulator, 65,536 slots)", "",
         ("Generated by `scripts/g1b_report.py` from `results/g1/g1b_*.npz`, following the addendum in "
          "`docs/preregistration.md` (committed before any run) and its later entries. Same merged PeerRush "
          "stream as G1. Every run is paired with an isolated reference at the same clock start; clock starts are "
          "a 30-point grid over the 4.295 s wrap period. Primary metric L = macro-F1(isolated) − "
          f"macro-F1(contended) over all flows. Class mapping fixed from the isolated run (F1 {sc[perm]:.3f})."), ""]

    gates = [g for g in range(GRID) if (OUT / f"g1b_iso_at{g}.npz").exists()]
    diff = {g: int(np.sum(iso(g)["raw"] != iso0["result"])) for g in gates if g}
    L += ["## Reference gate", "",
          (f"Isolated references were run at {len(gates)} clock starts. Against the reference at grid 0, per-packet "
           f"verdicts differ on {min(diff.values()):,} to {max(diff.values()):,} of {len(pk):,} packets "
           f"(median {int(np.median(list(diff.values()))):,}). The reference therefore depends on the clock, "
           "and every comparison is paired with the reference at its own clock start."), "",
          "## Arms", "", ("| arm | draws | mean L | median L | p_big (L > 0.004) [95% CI] | downgraded flows (share) | "
                          "downgraded packets (share) | net packets lost, mean (of which the 20 largest flows) | "
                          "gap on downgraded flows: median [range] |"), "|---|---|---|---|---|---|---|---|---|"]
    for n_ in missing:
        L.append(f"| {n_} | 0 (expected {DRAWS}) | | | | | | | |")
    for n_, d in arms.items():
        k = int((d.L > BIG).sum())
        lo, hi = cp_interval(k, len(d))
        L.append(f"| {labels[n_]} | {len(d)}{'' if len(d) == DRAWS else f' (expected {DRAWS})'} | {d.L.mean():.5f} | "
                 f"{d.L.median():.5f} | {k}/{len(d)} [{lo:.2f}, {hi:.2f}] | {d.down_flow_share.mean():.4%} | "
                 f"{d.down_pkt_share.mean():.4%} | {d.net_pkts_lost.mean():,.0f} ({d.top20_pkts_lost.mean():,.0f}) | "
                 f"{d.gap_down.median():+.4f} [{d.gap_down.min():+.4f}, {d.gap_down.max():+.4f}] |")

    L += ["", "## Where the shipped hash sits among random hashes", "",
          ("Downgraded-packet share of the keyed draws against the unkeyed hash. The number of downgraded flows is "
           "about the same in every arm; what differs is how many packets they carry. This says nothing about which "
           "flows are hit (the 20 largest flows are not the difference) and the accuracy loss L is not lower for the "
           "shipped hash. Two comparisons: fixed clock (every draw against the unkeyed run at grid 0, "
           f"{crc0.down_pkt_share:.4%}) and clock varied (every draw against the unkeyed run at its own clock)."), "",
          "| arm | draws | draws with a share at or below the unkeyed value | median keyed share | range |",
          "|---|---|---|---|---|"]
    cgs = crc.set_index("grid").down_pkt_share
    for n_ in [f"{k}:{m}" for k in ("poly", "polyirr", "tab") for m in ("fixed", "varied")]:
        if n_ in arms:
            d = arms[n_]
            ref = crc0.down_pkt_share if n_.endswith("fixed") else cgs.loc[d.grid].to_numpy()
            L.append(f"| {labels[n_]} | {len(d)} | {int((d.down_pkt_share.to_numpy() <= ref).sum())} | "
                     f"{d.down_pkt_share.median():.4%} | {d.down_pkt_share.min():.4%} to {d.down_pkt_share.max():.4%} |")

    L += ["", "## Negative control: does an XOR-salt change which flows are downgraded?", "",
          ("CRC is affine over GF(2), so a salt shifts every slot by one constant and collisions are unchanged. "
           "Prediction (pre-registered): outcomes identical to the unkeyed run at the same clock.")]
    xv, xf = arms.get("xorsalt:varied"), arms.get("xorsalt:fixed")
    if xv is not None:
        eq = [np.array_equal(outs[("xorsalt", int(r.seed), int(r.grid))][0], outs[("crc", None, int(r.grid))][0])
              for r in xv.itertuples() if ("crc", None, int(r.grid)) in outs]
        L += ["", f"- Clock varied: {sum(eq)} of {len(eq)} runs have per-packet outcomes identical to the unkeyed run."]
    if xf is not None and ("crc", None, 0) in outs:
        eq = [np.array_equal(outs[("xorsalt", int(r.seed), 0)][0], outs[("crc", None, 0)][0]) for r in xf.itertuples()]
        L += [f"- Clock fixed at grid 0: {sum(eq)} of {len(eq)} salts give identical outcomes."]

    L += ["", "## Is a keyed hash neutral on benign traffic?", "",
          (f"Pre-registered rule, all three: (a) the 90% CI of mean L(keyed) − mean L(unkeyed) lies within ±{EQUIV_L}; "
           f"(b) the CI of the downgraded-packet-share difference lies within ±{EQUIV_SHARE * 100:.1f} percentage "
           "points; (c) the p_big intervals overlap. Each rule is pass, fail (interval entirely outside) or "
           "inconclusive. Any fail gives \"changed distribution\"; all pass gives \"neutral on benign traffic\"; "
           "otherwise \"not shown neutral\". Percentile bootstrap over draws; clock-varied arms are paired by clock. "
           "Rules (a) and (b) compare with the unkeyed run at the same clock (grid 0 for the fixed-clock arms); rule (c) "
           "compares every arm's p_big interval with the clock-varied unkeyed interval. The tabulation hash has a "
           "clock-varied column only."), "",
          "| arm | mean ΔL [90% CI] | (a) | Δ packet share, pp [90% CI] | (b) | (c) p_big overlap | verdict |",
          "|---|---|---|---|---|---|---|"]
    base_ci = cp_interval(int((crc.L > BIG).sum()), len(crc))
    for n_, d in arms.items():
        if n_ == "crc":
            continue
        if n_.endswith("fixed"):
            dl, ds = d.L.to_numpy() - crc0.L, d.down_pkt_share.to_numpy() - crc0.down_pkt_share
        else:
            m = d[d.grid.isin(crc.grid)]
            if len(m) != len(d):
                L.append(f"| {labels[n_]} | dropped {len(d) - len(m)} runs with no unkeyed run at the same clock | | | | | |")
            cg = crc.set_index("grid")
            dl = m.L.to_numpy() - cg.loc[m.grid, "L"].to_numpy()
            ds = m.down_pkt_share.to_numpy() - cg.loc[m.grid, "down_pkt_share"].to_numpy()
        ci_l, ci_s = boot_ci(dl), boot_ci(ds)
        lo, hi = cp_interval(int((d.L > BIG).sum()), len(d))
        overlap = lo <= base_ci[1] and base_ci[0] <= hi
        sa, sb, sc_ = rule_status(*ci_l, EQUIV_L), rule_status(*ci_s, EQUIV_SHARE), "pass" if overlap else "fail"
        verdict = ("changed distribution" if "fail" in (sa, sb, sc_) else
                   "neutral on benign traffic" if (sa, sb, sc_) == ("pass",) * 3 else "not shown neutral")
        L.append(f"| {labels[n_]} | {dl.mean():+.5f} [{ci_l[0]:+.5f}, {ci_l[1]:+.5f}] | {sa} | "
                 f"{ds.mean() * 100:+.2f} [{ci_s[0] * 100:+.2f}, {ci_s[1] * 100:+.2f}] | {sb} | {sc_} | {verdict} |")

    L += ["", "## Within-draw uncertainty (flow-cluster bootstrap, 95%)", "",
          ("Resampling flows within one draw. Shown at clock grid 0, for the unkeyed hash and the first draw of each "
          "other arm."), "", "| run | L | 95% interval |", "|---|---|---|"]
    ref0 = iso(0)
    m_iso = per_flow_conf(idx, truth, ref0["cls"], perm)
    for kind, seed in [("crc", None)] + [(k, 0) for k in (*KEYED, "tab")]:
        f = OUT / (f"g1b_{kind}_at0.npz" if seed is None else f"g1b_{kind}_{seed}_at0.npz")
        if not f.exists():
            continue
        con = class_of(np.load(f)["result"][keep])
        lo, hi = within_draw_ci(m_iso, per_flow_conf(idx, truth, con, perm))
        L.append(f"| {kind}{'' if seed is None else f' seed {seed}'} | "
                 f"{ref0['f1'] - macro_f1(confusion(truth, con, perm)):.5f} | [{lo:.5f}, {hi:.5f}] |")

    big = crc.sort_values("L", ascending=False).iloc[0]
    L += ["", "## G1 re-derived with paired references", "",
          (f"Unkeyed arm at {len(crc)} clock starts, each against its own reference: gap on downgraded flows median "
           f"{crc.gap_down.median():+.4f}, range {crc.gap_down.min():+.4f} to {crc.gap_down.max():+.4f}; L median "
           f"{crc.L.median():.5f}, max {crc.L.max():.5f}. G1 (one reference at seed 0's clock) reported a median of "
           "+0.0386 and a range of +0.0339 to +0.3245."), "",
          "## Flows behind the largest-L unkeyed run", "",
          (f"Grid clock {int(big.grid)}: L = {big.L:.5f}, downgraded packets {big.down_pkt_share:.4%}. Top flows by "
           "net packets lost:"), "",
          "| flow | class (app) | packets | correct under isolation | correct contended | lost |", "|---|---|---|---|---|---|"]
    con = class_of(np.load(OUT / f"g1b_crc_at{int(big.grid)}.npz")["result"][keep])
    ref = iso(int(big.grid))
    con_ok = idx.per_flow_sum(cls_ok(con, truth, perm))
    loss = ref["ok"] - con_ok
    apps = ["eMule", "uTorrent", "Vuze"]
    for f in np.argsort(-loss)[:5]:
        L.append(f"| #{f} (src port {pk['src_port'][first[f]]}, dst port {pk['dst_port'][first[f]]}) | "
                 f"{apps[int(truth[first[f]])]} | {int(idx.n_pkts[f]):,} | {int(ref['ok'][f]):,} | "
                 f"{int(con_ok[f]):,} | {int(loss[f]):,} |")
    (ROOT / "docs/results_g1b.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
