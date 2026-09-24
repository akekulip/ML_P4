"""Nominal versus realised fill load, and the PeerRush launcher's job pairing."""

import subprocess
from pathlib import Path

import numpy as np

from dgrade.inject import build_fill

ROOT = Path(__file__).resolve().parents[1]


def test_random_slot_fill_targets_the_poisson_share_of_distinct_slots():
    n_slots, f = 65536, 0.83
    atk = build_fill(f, "k0", n_slots, 10 * 10**9, np.random.default_rng(0))
    distinct = len(np.unique(atk.slot)) / n_slots
    assert abs(distinct - (1 - np.exp(-f))) < 0.01          # about 0.56, not 0.83


def test_k1_fill_targets_distinct_slots():
    atk = build_fill(0.5, "k1", 4096, 10 * 10**9, np.random.default_rng(0))
    assert len(np.unique(atk.slot)) == round(0.5 * 4096)


def test_launcher_pairs_every_defended_job_with_undefended_and_no_attack_runs():
    out = subprocess.run([str(ROOT / "scripts/run_g5.sh"), "--dry-run"], capture_output=True, text=True)
    assert out.returncode == 0 and "pairing ok" in out.stdout, out.stdout + out.stderr


def test_d1_components_each_change_one_setting():
    from dgrade.defences import defence_kwargs
    assert defence_kwargs("d1w") == {"wrap_window": False}
    assert defence_kwargs("d1t") == {"takeover_refresh": True}
    assert defence_kwargs("d1i") == {"fix_ipd_wrap": True}
