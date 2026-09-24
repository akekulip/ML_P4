"""Job lists for the pre-registered G6 grid (docs/preregistration.md, G6 entry), in priority order, with a pairing check.

  g6_jobs.py mawi|pr [--check]

Every defended job with f > 0 needs an undefended partner and a no-attack partner of the same arm at the same clock (and table size).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
C3 = range(30)
C10 = range(10)
C10x3 = range(0, 30, 3)


def mawi_jobs() -> list[str]:
    j: list[str] = []
    atk = lambda d, f, g, arm="", n="": f"g2b_mawi.py {d}:oracle:b0l:{f}@{g}" + (f"+{arm}" if arm else "") + (f"~{n}" if n else "")
    base = lambda d, g, arm="", n="": f"g2_mawi.py {d}:oracle:crc@{g}" + (f"+{arm}" if arm else "") + (f"~{n}" if n else "")
    for g in C3:                                                   # M1: primary mechanism test
        j += [base("p", g, "d4"), atk("p", 10, g, "d4")]
    for g in C10:                                                  # M2: f = 25, 50 and the replication day
        j += [atk("p", 25, g, "d4"), atk("p", 50, g, "d4")]
        j += [base("r", g, "d4"), atk("r", 10, g, "d4"), atk("r", 25, g, "d4")]
    for arm in ("d5", "d4s"):                                      # M3: D5 equivalence and the same-hash control
        for g in C3:
            j += [base("p", g, arm), atk("p", 10, g, arm)]
    for n in (32768, 16384, 8192):                                 # M4: load sweep (undefended and D4 at the smaller table)
        for g in C10:
            j += [base("p", g, "", n), atk("p", 10, g, "", n), base("p", g, "d4", n), atk("p", 10, g, "d4", n)]
    return j


def mawi2_jobs() -> list[str]:
    """Post-review additions (docs/preregistration.md, G6 addendum): fixed-budget sweep, model gate, D4s replication, doubled table, D4a."""
    j: list[str] = []
    atk = lambda d, f, g, arm="", n="", gate="oracle": f"g2b_mawi.py {d}:{gate}:b0l:{f}@{g}" + (f"+{arm}" if arm else "") + (f"~{n}" if n else "")
    base = lambda d, g, arm="", n="", gate="oracle": f"g2_mawi.py {d}:{gate}:crc@{g}" + (f"+{arm}" if arm else "") + (f"~{n}" if n else "")
    for n, f in ((32768, 20), (16384, 40), (8192, 80)):            # fixed holder count: 6,554 holders whatever the table size
        for g in C10:
            j += [atk("p", f, g, "", n), atk("p", f, g, "d4", n)]
    for g in C10:                                                  # shipped flow-size gate
        j += [atk("p", 10, g, "", "", "model"), base("p", g, "d4", "", "model"), atk("p", 10, g, "d4", "", "model")]
    for g in C10:                                                  # D4s on the replication day
        j += [base("r", g, "d4s"), atk("r", 10, g, "d4s")]
    for g in range(10, 30):                                        # doubled table: primary day to 30 draws
        j += [base("p", g, "", 131072), atk("p", 5, g, "", 131072)]
    for g in C10:                                                  # doubled table on the replication day
        j += [base("r", g, "", 131072), atk("r", 5, g, "", 131072)]
    for g in C3:                                                   # placement ablation
        j += [base("p", g, "d4a"), atk("p", 10, g, "d4a")]
    return j


def mawi3_jobs() -> list[str]:
    """D4c placement (docs/preregistration.md, G6 addendum 2)."""
    atk = lambda d, f, g, arm: f"g2b_mawi.py {d}:oracle:b0l:{f}@{g}+{arm}"
    base = lambda d, g, arm: f"g2_mawi.py {d}:oracle:crc@{g}+{arm}"
    return [x for g in C3 for x in (base("p", g, "d4c"), atk("p", 10, g, "d4c"))] + [x for g in C10 for x in (base("r", g, "d4c"), atk("r", 10, g, "d4c"))]


def mawi4_jobs() -> list[str]:
    """D4 + D1 clock, without and with age rent (docs/preregistration.md, G6 addendum 3; exploratory)."""
    atk = lambda f, g, arm, n="": f"g2b_mawi.py p:oracle:b0l:{f}@{g}+{arm}" + (f"~{n}" if n else "")
    base = lambda g, arm, n="": f"g2_mawi.py p:oracle:crc@{g}+{arm}" + (f"~{n}" if n else "")
    j: list[str] = []
    for arm in ("d4d1", "d4age"):
        for g in C10:
            j += [base(g, arm), atk(10, g, arm)]
        for n, f in ((32768, 20), (16384, 40), (8192, 80)):
            for g in C10:
                j += [base(g, arm, n), atk(f, g, arm, n)]
    return j


def pr_jobs() -> list[str]:
    j = [f"25:und@{g}" for g in C3 if g >= 10 and g not in (12, 18, 24)]          # extend undefended f = 25% to 30 draws
    j += [f"25:d4@{g}" for g in C3] + [f"0:d4@{g}" for g in C3] + [f"10:d4@{g}" for g in C3]
    for arm in ("d4s",):
        j += [f"{f}:{arm}@{g}" for g in C10x3 for f in (0, 10, 25)]
    j += [f"{f}:d5@{g}" for g in C10x3 for f in (0, 10)]
    return j


def check(kind: str, jobs: list[str]) -> list[str]:
    have = {p.name for p in (ROOT / ("results/g5" if kind == "pr" else "results/g2")).glob("*.npz")}
    bad: list[str] = []
    if kind == "pr":
        names = have | {f"pr_{x.replace(':', '_').replace('@', '_at')}.npz" for x in jobs}
        for x in jobs:
            f, rest = x.split(":"); arm, g = rest.split("@")
            if arm != "und" and int(f) > 0:
                for need in (f"pr_{f}_und_at{g}.npz", f"pr_0_{arm}_at{g}.npz", f"pr_0_und_at{g}.npz"):
                    if need not in names:
                        bad.append(f"{x}: missing {need}")
    else:
        # MAWI names: b_<d>_oracle_b0l_<f>_at<g>[_p_<arm>][_n<N>].npz and a_<d>_oracle_crc_at<g>[_p_<arm>][_n<N>].npz
        for x in jobs:
            _, spec = x.split(" ", 1)
            body, _, n = spec.partition("~")
            head, _, arm = body.partition("+")
            left, g = head.split("@")
            d, gate, mode, *f = left.split(":")
            suf = (f"_p_{arm}" if arm else "") + (f"_n{n}" if n else "")
            if mode == "b0l" and arm:
                partners = [f"b_{d}_{gate}_b0l_{f[0]}_at{g}" + (f"_n{n}" if n else "") + ".npz",
                            f"a_{d}_{gate}_crc_at{g}{suf}.npz"]
                for need in partners:
                    if need not in have and not any(need == _name(k, y) for k, y in _all_mawi(jobs)):
                        bad.append(f"{x}: missing {need}")
    return bad


def _name(_k: str, spec: str) -> str:
    script, s = spec.split(" ", 1)
    body, _, n = s.partition("~")
    head, _, arm = body.partition("+")
    left, g = head.split("@")
    d, gate, mode, *f = left.split(":")
    suf = (f"_p_{arm}" if arm else "") + (f"_n{n}" if n else "")
    return (f"b_{d}_{gate}_b0l_{f[0]}_at{g}{suf}.npz" if mode == "b0l" else f"a_{d}_{gate}_crc_at{g}{suf}.npz")


def _all_mawi(jobs):
    return [("mawi", y) for y in jobs]


if __name__ == "__main__":
    kind = sys.argv[1]
    jobs = mawi_jobs() if kind == "mawi" else mawi2_jobs() if kind == "mawi2" else mawi3_jobs() if kind == "mawi3" else mawi4_jobs() if kind == "mawi4" else pr_jobs()
    if "--check" in sys.argv:
        bad = check(kind, jobs)
        print("\n".join(bad) if bad else f"pairing ok ({len(jobs)} jobs)")
        sys.exit(1 if bad else 0)
    print("\n".join(jobs))
