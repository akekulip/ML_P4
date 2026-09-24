"""GA-1's alias construction (scripts/ga_alias_check.py): the fold is preserved by design."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ga_alias_check import alias_of

from dgrade.netbeacon_tofino import fold_keys


def test_alias_preserves_the_xor_fold_and_is_a_genuinely_different_tuple():
    rng = np.random.default_rng(0)
    for _ in range(200):
        src, dst = int(rng.integers(1, 2**32)), int(rng.integers(1, 2**32))
        sp, dp = int(rng.integers(1, 65536)), int(rng.integers(1, 65536))
        a_src, a_dst, a_sp, a_dp = alias_of(src, dst, sp, dp)
        uniq = np.array([[min(src, dst), max(src, dst), min(sp, dp), max(sp, dp), 6],
                         [min(a_src, a_dst), max(a_src, a_dst), min(a_sp, a_dp), max(a_sp, a_dp), 6]])
        kf = fold_keys(uniq)
        assert np.array_equal(kf[0], kf[1])
        assert (a_src, a_dst, a_sp, a_dp) != (src, dst, sp, dp)
