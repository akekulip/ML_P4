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


def pr_jobs() -> list[str]:
    j = [f"25:und@{g}" for g in C3 if g >= 10 and g not in (12, 18, 24)]          # extend undefended f = 25% to 30 draws
    j += [f"25:d4@{g}" for g in C3] + [f"0:d4@{g}" for g in C3] + [f"10:d4@{g}" for g in C3]
    for arm in ("d4s",):
        j += [f"{f}:{arm}@{g}" for g in C10x3 for f in (0, 10, 25)]
    j += [f"{f}:d5@{g}" for g in C10x3 for f in (0, 10)]
    return j


def check(kind: str, jobs: list[str]) -> list[str]:
    have = {p.name for p in (ROOT / ("results/g2" if kind == "mawi" else "results/g5")).glob("*.npz")}
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
            d, _, mode, *f = left.split(":")
            suf = (f"_p_{arm}" if arm else "") + (f"_n{n}" if n else "")
            if mode == "b0l" and arm:
                partners = [f"b_{d}_oracle_b0l_{f[0]}_at{g}" + (f"_n{n}" if n else "") + ".npz",
                            f"a_{d}_oracle_crc_at{g}{suf}.npz"]
                for need in partners:
                    if need not in have and not any(need == _name(k, y) for k, y in _all_mawi(jobs)):
                        bad.append(f"{x}: missing {need}")
    return bad


def _name(_k: str, spec: str) -> str:
    script, s = spec.split(" ", 1)
    body, _, n = s.partition("~")
    head, _, arm = body.partition("+")
    left, g = head.split("@")
    d, _, mode, *f = left.split(":")
    suf = (f"_p_{arm}" if arm else "") + (f"_n{n}" if n else "")
    return (f"b_{d}_oracle_b0l_{f[0]}_at{g}{suf}.npz" if mode == "b0l" else f"a_{d}_oracle_crc_at{g}{suf}.npz")


def _all_mawi(jobs):
    return [("mawi", y) for y in jobs]


if __name__ == "__main__":
    kind = sys.argv[1]
    jobs = mawi_jobs() if kind == "mawi" else pr_jobs()
    if "--check" in sys.argv:
        bad = check(kind, jobs)
        print("\n".join(bad) if bad else f"pairing ok ({len(jobs)} jobs)")
        sys.exit(1 if bad else 0)
    print("\n".join(jobs))
