"""G6 on PeerRush: two-choice tables D4/D5/D4s (8,192 slots in total) -> docs/results_g6_pr.md (docs/preregistration.md, G6 entry).

Loss = macro-F1 of the isolated reference at the same clock start minus macro-F1 of the contended benign packets. For arm X at draw g:
E_X = Loss(X, fill f) - Loss(X, no attack); benign gain G_X = Loss(und, 0) - Loss(X, 0); mitigation = E_und - E_X; recovery R = 1 - mean(E_X)/mean(E_und),
paired by clock start. Two intervals: percentile bootstrap over draws and a bootstrap over benign flows (all draws share one capture).
Accuracy verdict at f = 25% for D4: strong pass (lower bound of R >= 0.5), weak pass (lower bound of mitigation > 0, lower bound of R < 0.5;
flow-cluster interval for mitigation must also exclude zero), falsified (upper bound of R < 0.25), else inconclusive. M1: upper bound of the
no-attack loss increase at most 0.01.
"""

from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np

from dgrade.netbeacon_sim import FALLBACK_COLLISION, tuple_table
from g4_peerrush_report import N_CLASS, class_of, confusion, macro_f1

ROOT = Path(__file__).resolve().parents[1]
G1, G5 = ROOT / "results/g1", ROOT / "results/g5"
ARMS = ["d4", "d4s", "d5"]
N_BOOT, N_FLOW_BOOT, LVL = 4000, 200, 97.5          # Holm-conservative two-sided level


def pct(v: np.ndarray, lvl: float = LVL) -> tuple[float, float]:
    v = v[np.isfinite(v)]
    return float(np.percentile(v, (100 - lvl) / 2)), float(np.percentile(v, 100 - (100 - lvl) / 2))


def main() -> None:
    z = np.load(G1 / "stream.npz")
    pk, lab = z["pk"], z["lab"]
    _, inv = tuple_table(pk["src_ip"], pk["dst_ip"], pk["src_port"], pk["dst_port"], pk["proto"])
    iso0 = np.load(G1 / "g1b_iso_at0.npz")
    keep = iso0["outcome"] != 5
    truth, flow = lab[keep].astype(np.int64), inv[keep]
    nf = int(flow.max()) + 1
    perm = max(itertools.permutations(range(N_CLASS)), key=lambda p: macro_f1(confusion(truth, class_of(iso0["result"][keep]), p)))

    cm_cache: dict[str, np.ndarray | None] = {}
    oc_cache: dict[str, float | None] = {}

    def cm(name: str, iso: bool = False) -> np.ndarray | None:
        path = (G1 if iso else G5) / name
        if name not in cm_cache:
            try:
                pred = class_of(np.load(path)["result"][keep])
            except (FileNotFoundError, EOFError, ValueError, OSError):
                cm_cache[name] = None
                return None
            p = np.where(pred < 0, 3, np.asarray(perm)[np.clip(pred, 0, N_CLASS - 1)])
            cm_cache[name] = np.bincount(flow * 12 + truth * 4 + p, minlength=nf * 12).reshape(nf, 12).astype(np.float32)
        return cm_cache[name]

    def refusal(f: int, arm: str, g: int) -> float | None:
        name = key(f, arm, g)
        if name not in oc_cache:
            try:
                oc_cache[name] = float(np.mean(np.load(G5 / name)["outcome"] == FALLBACK_COLLISION))
            except (FileNotFoundError, EOFError, ValueError, OSError):
                oc_cache[name] = None
        return oc_cache[name]

    def key(f: int, arm: str, g: int) -> str:
        return f"pr_{f}_{arm}_at{g}.npz"

    rng = np.random.default_rng(1)
    Wmat = np.stack([np.bincount(rng.integers(0, nf, nf), minlength=nf) for _ in range(N_FLOW_BOOT)]).astype(np.float32)
    wcache: dict[str, np.ndarray] = {}
    memo: dict[tuple, float] = {}

    def f1_of(name: str, iso: bool, k: int | None) -> float:
        if k is None:
            return macro_f1(cm(name, iso).sum(0).reshape(3, 4))
        if name not in wcache:
            wcache[name] = Wmat @ cm(name, iso)
        return macro_f1(wcache[name][k].reshape(3, 4))

    def loss(f: int, arm: str, g: int, k=None) -> float:
        if (f, arm, g, k) not in memo:
            memo[(f, arm, g, k)] = f1_of(f"g1b_iso_at{g}.npz", True, k) - f1_of(key(f, arm, g), False, k)
        return memo[(f, arm, g, k)]

    def avail(f: int, arm: str, clocks) -> list[int]:
        need = [(f, "und"), (0, "und"), (f, arm), (0, arm)]
        return [g for g in clocks if cm(f"g1b_iso_at{g}.npz", True) is not None and all(cm(key(a, b, g)) is not None for a, b in need)]

    def quantities(f: int, arm: str, cs: list[int], k=None) -> dict[str, float]:
        e_u = np.array([loss(f, "und", g, k) - loss(0, "und", g, k) for g in cs])
        e_x = np.array([loss(f, arm, g, k) - loss(0, arm, g, k) for g in cs])
        gain = np.array([loss(0, "und", g, k) - loss(0, arm, g, k) for g in cs])
        return {"e_u": e_u, "e_x": e_x, "gain": gain}

    def stat(name: str, q: dict, ix) -> float:
        if name == "R":
            return 1 - q["e_x"][ix].mean() / q["e_u"][ix].mean()
        if name == "mit":
            return (q["e_u"][ix] - q["e_x"][ix]).mean()
        if name == "gain":
            return q["gain"][ix].mean()
        if name == "m1":
            return -q["gain"][ix].mean()          # no-attack loss increase = loss_arm0 - loss_und0
        raise KeyError(name)

    def cell(name: str, f: int, arm: str, cs: list[int]) -> tuple[float, tuple, tuple]:
        q = quantities(f, arm, cs)
        n = len(cs)
        rg = np.random.default_rng(0)
        draw = np.array([stat(name, q, rg.integers(0, n, n)) for _ in range(N_BOOT)])
        fl = []
        for k in range(N_FLOW_BOOT):
            qk = quantities(f, arm, cs, k)
            fl.append(stat(name, qk, np.arange(n)))
        return stat(name, q, np.arange(n)), pct(draw), pct(np.array(fl))

    L = ["# G6 on PeerRush: two-choice tables at equal capacity (8,192 slots in total)", "",
         ("Generated by `scripts/g6_pr_report.py` from `results/g5/` and the isolated references in `results/g1/`. Loss = macro-F1 of the isolated "
          "reference minus macro-F1 of the contended benign packets at the same clock start. Each interval cell reads: point [draw interval] / "
          f"[benign-flow interval], at the Holm-conservative {LVL}% two-sided level. E = loss under fill minus loss with no attack for the same arm; "
          "benign gain = undefended no-attack loss minus the arm's no-attack loss, kept apart from mitigation. f is the nominal holder load per "
          "slot; D4 holders share identities and start times with the undefended draw but have their own slots."), ""]

    L += ["## M1: no-attack cost (loss of the arm minus loss of the undefended table; pass if the upper bound is at most 0.01)", "",
          "| arm | draws | benign gain (loss_und − loss_arm) | cost | M1 | collision-refusal share, und / arm |", "|---|---|---|---|---|---|"]
    for arm in ARMS:
        cs = [g for g in range(30) if cm(f"g1b_iso_at{g}.npz", True) is not None and cm(key(0, arm, g)) is not None and cm(key(0, "und", g)) is not None]
        if len(cs) < 3:
            continue
        q = quantities(0, arm, cs)
        n = len(cs)
        rg = np.random.default_rng(0)
        dr = np.array([(-q["gain"][ix]).mean() for ix in (rg.integers(0, n, n) for _ in range(N_BOOT))])
        fl = np.array([(-quantities(0, arm, cs, k)["gain"]).mean() for k in range(N_FLOW_BOOT)])
        cost = float((-q["gain"]).mean())
        up = max(pct(dr)[1], pct(fl)[1])
        ru = np.mean([refusal(0, "und", g) for g in cs])
        ra = np.mean([refusal(0, arm, g) for g in cs])
        L.append(f"| {arm} | {n} | {-cost:+.4f} | {cost:+.4f} [{pct(dr)[0]:+.4f}, {pct(dr)[1]:+.4f}] / [{pct(fl)[0]:+.4f}, {pct(fl)[1]:+.4f}] | "
                 f"{'pass' if up <= 0.01 else 'fail'} | {ru:.2%} / {ra:.2%} |")

    verdicts = []
    for f in (10, 25):
        L += ["", f"## Fill f = {f}% (nominal; distinct slots targeted about {1 - np.exp(-f / 100):.0%})", ""]
        L += ["| arm | draws | E_und | E_arm | mitigation | recovery R | collision-refusal share under fill, und / arm |", "|---|---|---|---|---|---|---|"]
        for arm in ARMS:
            cs = avail(f, arm, range(30))
            if len(cs) < 3:
                continue
            ex_u = cell("R", f, arm, cs)
            q = quantities(f, arm, cs)
            mit = cell("mit", f, arm, cs)
            ru = np.mean([refusal(f, "und", g) for g in cs])
            ra = np.mean([refusal(f, arm, g) for g in cs])
            fmt = lambda c: f"{c[0]:+.4f} [{c[1][0]:+.4f}, {c[1][1]:+.4f}] / [{c[2][0]:+.4f}, {c[2][1]:+.4f}]"
            L.append(f"| {arm} | {len(cs)} | {q['e_u'].mean():+.4f} | {q['e_x'].mean():+.4f} | {fmt(mit)} | "
                     f"{ex_u[0]:+.2f} [{ex_u[1][0]:+.2f}, {ex_u[1][1]:+.2f}] / [{ex_u[2][0]:+.2f}, {ex_u[2][1]:+.2f}] | {ru:.2%} / {ra:.2%} |")
            if f == 25 and arm == "d4":
                strong = ex_u[1][0] >= 0.5
                weak = mit[1][0] > 0 and mit[2][0] > 0
                fals = ex_u[1][1] < 0.25
                verdicts.append("**H-D4-acc verdict (D4, f = 25%, " + f"{len(cs)} draws): "
                                + ("strong pass" if strong else "weak pass (resolved positive, at-least-half not resolved)" if weak
                                   else "falsified" if fals else "inconclusive") + ".**")
    if verdicts:
        L += [""] + verdicts
    L += ["", "PeerRush f = 10% macro-F1 is descriptive (the undefended excess narrowly fails the G5 power gate). Emulator result on one capture; "
          "no claim about a 65,536-slot PeerRush deployment or about deployability on Tofino-1."]
    (ROOT / "docs/results_g6_pr.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
