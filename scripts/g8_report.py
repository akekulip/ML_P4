"""G8 agreement gate -> docs/results_g8_compiled_semantics.md (docs/preregistration.md, G8 entry).

Compares the compiled-semantics emulator (fold hash, delta=0) against the abstract-emulator G6 results, paired by clock start. MAWI: R on excess
downgraded flows, benign gain, D4c vs D4s ordering. PeerRush: mitigation of the macro-F1 excess at f=25%. Then the delta sweep (sorted hash) as a
descriptive race-probability check.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np

from dgrade.flowstats import FlowIndex, downgraded_flows
from dgrade.netbeacon_sim import FALLBACK_COLLISION

ROOT = Path(__file__).resolve().parents[1]
G2, G5, G1 = ROOT / "results/g2", ROOT / "results/g5", ROOT / "results/g1"


def boot_ci(x: np.ndarray, lvl: float = 95.0, n: int = 4000, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    b = [rng.choice(x, len(x)).mean() for _ in range(n)]
    return float(np.percentile(b, (100 - lvl) / 2)), float(np.percentile(b, 100 - (100 - lvl) / 2))


def mawi_section() -> list[str]:
    idx = FlowIndex(np.load(G2 / "targeted_prep_p.npz")["code"])
    L = ["## MAWI: compiled-semantics agreement (primary day, oracle gate, fold hash, delta = 0)", "",
         "| f | arm | draws | E_compiled (flows) | E_abstract (flows, G6) | benign gain | R_compiled [CI] | R_abstract (G6) | |R diff| |", "|---|---|---|---|---|---|---|---|---|"]
    Rc = {}
    for f in (0, 10):
        for arm in ("und", "d4c"):
            if f == 0:
                continue
            eu, ex, gain = [], [], []
            for g in range(10):
                a_u0 = downgraded_flows(np.load(G2 / f"g8_p_fold_0_und_0_at{g}.npz")["benign_outcome"], idx).sum()
                a_uf = downgraded_flows(np.load(G2 / f"g8_p_fold_0_und_{f}_at{g}.npz")["benign_outcome"], idx).sum()
                a_x0 = downgraded_flows(np.load(G2 / f"g8_p_fold_0_{arm}_0_at{g}.npz")["benign_outcome"], idx).sum()
                a_xf = downgraded_flows(np.load(G2 / f"g8_p_fold_0_{arm}_{f}_at{g}.npz")["benign_outcome"], idx).sum()
                eu.append(a_uf - a_u0)
                ex.append(a_xf - a_x0)
                gain.append(a_u0 - a_x0)
            if not eu:
                continue
            eu, ex, gain = np.array(eu, float), np.array(ex, float), np.array(gain, float)
            r = 1 - ex.mean() / eu.mean()
            rng = np.random.default_rng(1)
            n = len(eu)
            rb = np.array([1 - ex[i].mean() / eu[i].mean() for i in (rng.integers(0, n, n) for _ in range(4000))])
            lo, hi = np.percentile(rb, [2.5, 97.5])
            Rc[(f, arm)] = r
            g6r = {("10", "und"): None, ("10", "d4c"): 0.77}.get((str(f), arm))
            L.append(f"| {f}% | {arm} | {n} | {ex.mean():,.0f} | {eu.mean():,.0f} | {gain.mean():+,.0f} | {r:+.2f} [{lo:+.2f}, {hi:+.2f}] | "
                     f"{'-' if g6r is None else f'{g6r:+.2f}'} | {'-' if g6r is None else f'{abs(r - g6r):.2f}'} |")
    L += ["", "## MAWI: M1 (no attack), compiled semantics", "", "| arm | draws | downgraded-packet share change vs undefended (pp) |", "|---|---|---|"]
    for arm in ("d4c",):
        d = []
        for g in range(10):
            pa = downgraded_flows(np.load(G2 / f"g8_p_fold_0_und_0_at{g}.npz")["benign_outcome"], idx)[idx.code].mean()
            pb = downgraded_flows(np.load(G2 / f"g8_p_fold_0_{arm}_0_at{g}.npz")["benign_outcome"], idx)[idx.code].mean()
            d.append((pb - pa) * 100)
        d = np.array(d)
        L.append(f"| {arm} | {len(d)} | {d.mean():+.3f} [{boot_ci(d)[0]:+.3f}, {boot_ci(d)[1]:+.3f}] |")
    return L, Rc


def peerrush_section() -> list[str]:
    from g4_peerrush_report import N_CLASS, class_of, confusion, macro_f1
    lab = np.load(G1 / "stream.npz")["lab"]
    iso0 = np.load(G1 / "g1b_iso_at0.npz")
    keep = iso0["outcome"] != 5
    truth = lab[keep].astype(np.int64)
    perm = max(itertools.permutations(range(N_CLASS)), key=lambda p: macro_f1(confusion(truth, class_of(iso0["result"][keep]), p)))

    def f1_run(p: Path) -> float | None:
        if not p.exists():
            return None
        pred = class_of(np.load(p)["result"][keep])
        pp = np.where(pred < 0, N_CLASS, np.asarray(perm)[np.clip(pred, 0, N_CLASS - 1)])
        cm = np.bincount(truth * (N_CLASS + 1) + pp, minlength=N_CLASS * (N_CLASS + 1)).reshape(N_CLASS, N_CLASS + 1)
        return macro_f1(cm)

    def f1_iso(g: int) -> float | None:
        p = G1 / f"g1b_iso_at{g}.npz"
        return f1_run(p) if p.exists() else None

    L = ["", "## PeerRush: compiled-semantics agreement (8,192 slots, fold hash, delta = 0)", "",
         "Loss = macro-F1 of the isolated abstract-emulator reference at the same clock minus macro-F1 of the compiled-semantics contended packets.", "",
         "| f | arm | draws | mitigation_compiled [CI] | mitigation_abstract (G6) | |diff| (gate: <= 0.004) |", "|---|---|---|---|---|---|"]
    for f in (25,):
        for arm in ("d4c",):
            mit = []
            for g in range(10):
                iso = f1_iso(g)
                l_u0 = f1_run(G5 / f"g8_fold_0_und_0_at{g}.npz")
                l_uf = f1_run(G5 / f"g8_fold_0_und_{f}_at{g}.npz")
                l_x0 = f1_run(G5 / f"g8_fold_0_{arm}_0_at{g}.npz")
                l_xf = f1_run(G5 / f"g8_fold_0_{arm}_{f}_at{g}.npz")
                if None in (iso, l_u0, l_uf, l_x0, l_xf):
                    continue
                e_u = (iso - l_uf) - (iso - l_u0)
                e_x = (iso - l_xf) - (iso - l_x0)
                mit.append(e_u - e_x)
            if not mit:
                L.append(f"| {f}% | {arm} | 0 | no runs | +0.0122 | n/a |")
                continue
            mit = np.array(mit)
            lo, hi = boot_ci(mit)
            L.append(f"| {f}% | {arm} | {len(mit)} | {mit.mean():+.4f} [{lo:+.4f}, {hi:+.4f}] | +0.0122 | {abs(mit.mean() - 0.0122):.4f} |")
    return L


def delta_section() -> list[str]:
    idx = FlowIndex(np.load(G2 / "targeted_prep_p.npz")["code"])
    clocks = (0, 3, 6)
    L = ["", "## Recovery R against the recirculation delay (MAWI primary day, f = 10%, sorted hash, clocks 0/3/6)", "",
         ("Prediction (G8, before this run): R unchanged for delta <= 10 microseconds, degrading as delta approaches the packet gaps of active flows "
          "(holders send one packet per 250 ms; benign long flows send several per second)."), "",
         "| delta (us) | draws | E_und | E_d4c | R [CI] |", "|---|---|---|---|---|"]
    for d in (0, 1, 10, 100, 1000):
        eu, ex = [], []
        for g in clocks:
            a0 = G2 / f"g8_p_sorted_{d}_und_0_at{g}.npz"; af = G2 / f"g8_p_sorted_{d}_und_10_at{g}.npz"
            x0 = G2 / f"g8_p_sorted_{d}_d4c_0_at{g}.npz"; xf = G2 / f"g8_p_sorted_{d}_d4c_10_at{g}.npz"
            if not all(p.exists() for p in (a0, af, x0, xf)):
                continue
            eu.append(downgraded_flows(np.load(af)["benign_outcome"], idx).sum() - downgraded_flows(np.load(a0)["benign_outcome"], idx).sum())
            ex.append(downgraded_flows(np.load(xf)["benign_outcome"], idx).sum() - downgraded_flows(np.load(x0)["benign_outcome"], idx).sum())
        if not eu:
            continue
        eu, ex = np.array(eu, float), np.array(ex, float)
        r = 1 - ex.mean() / eu.mean()
        rng = np.random.default_rng(2)
        n = len(eu)
        rb = np.array([1 - ex[i].mean() / eu[i].mean() for i in (rng.integers(0, n, n) for _ in range(4000))])
        lo, hi = np.percentile(rb, [2.5, 97.5])
        L.append(f"| {d} | {n} | {eu.mean():,.0f} | {ex.mean():,.0f} | {r:+.2f} [{lo:+.2f}, {hi:+.2f}] |")
    L += ["", "## Race counters over the same sweep", "",
         "| delta (us) | arm | draws | takeovers (mean) | re-Init same flow | second newcomer | dual-owner claims | contaminated packets |",
         "|---|---|---|---|---|---|---|---|"]
    for d in (1, 10, 100, 1000):
        for arm in ("und", "d4c"):
            races = []
            for g in (0, 3, 6):
                p = G2 / f"g8_p_sorted_{d}_{arm}_10_at{g}.npz"
                if p.exists():
                    races.append(json.loads(str(np.load(p)["race"])))
            if not races:
                continue
            keys = races[0].keys()
            m = {k: np.mean([r[k] for r in races]) for k in keys}
            L.append(f"| {d} | {arm} | {len(races)} | {m['takeovers']:.0f} | {m['reinit_same_flow']:.0f} | {m['second_newcomer']:.0f} | "
                     f"{m['dual_owner_claims']:.0f} | {m['contaminated_packets']:.0f} |")
    return L


def main() -> None:
    L = ["# G8: compiled-semantics agreement gate and race measurements", "",
         ("Generated by `scripts/g8_report.py`. `TofinoSim` (`src/dgrade/netbeacon_tofino.py`) against the abstract-emulator G6 results, "
          "paired by clock start. Fold hash and delta = 0 first (the agreement gate); the delta sweep (sorted hash) is descriptive only.")]
    mawi_lines, _ = mawi_section()
    L += mawi_lines
    L += peerrush_section()
    L += delta_section()
    (ROOT / "docs/results_g8_compiled_semantics.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
