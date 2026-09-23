"""Hash arms for G1b: unkeyed CRC32, XOR-salt (negative control), secret polynomial, tabulation."""

import zlib

import numpy as np

from dgrade.netbeacon_sim import (
    FALLBACK_COLLISION,
    NetBeaconSim,
    StubModels,
    crc32_flow_hash,
    crc_poly,
    flow_hash,
    make_packets,
)

REFLECTED_CRC32 = 0xEDB88320


def _tuples(n, seed=0):
    r = np.random.default_rng(seed)
    return (r.integers(1, 2**32 - 1, n), r.integers(1, 2**32 - 1, n), r.integers(1024, 65535, n),
            r.integers(1, 1024, n), np.full(n, 6))


def test_crc_poly_standard_polynomial_equals_zlib():
    for m in (b"", b"a", b"123456789", bytes(range(13))):
        assert crc_poly(m, REFLECTED_CRC32) == zlib.crc32(m)


def test_flow_hash_crc_kind_equals_crc32_flow_hash():
    t = _tuples(200)
    assert np.array_equal(flow_hash(*t, kind="crc"), crc32_flow_hash(*t))


def test_xor_salt_only_shifts_slots_by_one_constant():
    t = _tuples(20_000)
    a, b = flow_hash(*t, kind="crc"), flow_hash(*t, kind="xorsalt", key_seed=3)
    assert not np.array_equal(a, b)
    assert np.unique((a ^ b) & 0xFFFF).size == 1          # same collision structure
    assert np.unique(a ^ b).size == 1                      # the full 32-bit tag shifts identically


def test_secret_polynomial_changes_which_tuples_collide():
    t = _tuples(20_000)
    a, b = flow_hash(*t, kind="crc"), flow_hash(*t, kind="poly", key_seed=3)
    assert np.unique((a ^ b) & 0xFFFF).size > 1000


def test_tabulation_is_deterministic_and_seed_dependent():
    t = _tuples(1000)
    a = flow_hash(*t, kind="tab", key_seed=1)
    assert np.array_equal(a, flow_hash(*t, kind="tab", key_seed=1))
    assert not np.array_equal(a, flow_hash(*t, kind="tab", key_seed=2))


def test_hashes_stay_symmetric():
    s, d, sp, dp, p = _tuples(500)
    for kind in ("crc", "xorsalt", "poly", "tab"):
        assert np.array_equal(flow_hash(s, d, sp, dp, p, kind=kind, key_seed=5),
                              flow_hash(d, s, dp, sp, p, kind=kind, key_seed=5))


def _many_flows(n_flows=300):
    """Flows run one after another, 10 ms apart, so an owner's slot stays protected (< 256 units)
    and later flows hashing to it are refused: real collisions, not universal takeovers."""
    parts = [make_packets(ts_ns=k * 10_000_000 + np.arange(4) * 1_000_000, src_ip=0x0A000000 + k,
                          dst_ip=0x0B000001, src_port=1000 + k, dst_port=80, proto=6, total_len=100)
             for k in range(n_flows)]
    return np.concatenate(parts)


def test_xor_salt_leaves_every_outcome_unchanged():
    pk = _many_flows()
    kw = {"models": StubModels(), "n_slots": 64, "clock_offset_ns": 300 * (1 << 20)}
    a = NetBeaconSim(**kw).run(pk)
    b = NetBeaconSim(hash_kind="xorsalt", hash_seed=9, **kw).run(pk)
    assert np.sum(a["outcome"] == FALLBACK_COLLISION) > 50      # the scenario really has collisions
    assert np.array_equal(a["outcome"], b["outcome"])
    assert not np.array_equal(a["slot"], b["slot"])


def test_secret_polynomial_changes_outcomes():
    pk = _many_flows()
    kw = {"models": StubModels(), "n_slots": 64, "clock_offset_ns": 300 * (1 << 20)}
    a = NetBeaconSim(**kw).run(pk)
    b = NetBeaconSim(hash_kind="poly", hash_seed=9, **kw).run(pk)
    assert not np.array_equal(a["outcome"], b["outcome"])


def test_hash_seed_and_clock_are_independent():
    pk = _many_flows(20)
    a = NetBeaconSim(models=StubModels(), hash_kind="poly", hash_seed=1, clock_offset_ns=12345).run(pk)
    b = NetBeaconSim(models=StubModels(), hash_kind="poly", hash_seed=2, clock_offset_ns=12345).run(pk)
    assert a["clock_offset_ns"] == b["clock_offset_ns"] == 12345
    c = NetBeaconSim(models=StubModels(), hash_kind="poly", hash_seed=1, clock_offset_ns=999).run(pk)
    assert np.array_equal(a["slot"], c["slot"])


# ---- irreducible polynomials and seed requirements (code review 2026-09-23) ----

import pytest

from dgrade.netbeacon_sim import is_irreducible


def test_irreducible_counts_match_known_values():
    # number of monic irreducible polynomials over GF(2): degree 4 -> 3, 8 -> 30, 10 -> 99
    for deg, count in ((4, 3), (8, 30), (10, 99)):
        n = sum(is_irreducible((1 << deg) | low, deg) for low in range(1 << deg))
        assert n == count, (deg, n)


def test_known_reducible_and_irreducible_degree_32():
    assert not is_irreducible((1 << 32) | 1, 32)                                  # x^32 + 1 = (x+1)^32


def test_standard_crc32_polynomial_is_irreducible():
    # cross-checked once against sympy (not a repo dependency): the IEEE polynomial is irreducible
    assert is_irreducible((1 << 32) | 0x04C11DB7, 32)


def test_polyirr_arm_is_irreducible_deterministic_and_symmetric():
    t = _tuples(2000)
    a = flow_hash(*t, kind="polyirr", key_seed=4)
    assert np.array_equal(a, flow_hash(*t, kind="polyirr", key_seed=4))
    assert not np.array_equal(a, flow_hash(*t, kind="polyirr", key_seed=5))
    s, d, sp, dp, p = t
    assert np.array_equal(a, flow_hash(d, s, dp, sp, p, kind="polyirr", key_seed=4))
    from dgrade.netbeacon_sim import irreducible_reflected_poly
    for seed in range(5):
        r = irreducible_reflected_poly(np.random.default_rng(seed))
        normal = int(f"{r:032b}"[::-1], 2)
        assert is_irreducible((1 << 32) | normal, 32)


def test_keyed_kinds_require_a_seed():
    with pytest.raises(ValueError):
        NetBeaconSim(models=StubModels(), hash_kind="poly").run(_many_flows(3))
    with pytest.raises(ValueError):
        NetBeaconSim(models=StubModels(), hash_kind="poly", hash_seed=1, keyed=True).run(_many_flows(3))


def test_hash_seed_changes_slots_and_the_legacy_seed_does_not():
    pk = _many_flows(50)
    kw = {"models": StubModels(), "hash_kind": "poly", "clock_offset_ns": 1}
    a = NetBeaconSim(seed=1, hash_seed=7, **kw).run(pk)["slot"]
    assert np.array_equal(a, NetBeaconSim(seed=2, hash_seed=7, **kw).run(pk)["slot"])
    assert not np.array_equal(a, NetBeaconSim(seed=1, hash_seed=8, **kw).run(pk)["slot"])


def test_hash_unique_composes_to_flow_hash():
    from dgrade.netbeacon_sim import hash_unique, tuple_table
    t = _tuples(3000)
    uniq, inv = tuple_table(*t)
    for kind in ("crc", "xorsalt", "poly", "polyirr", "tab"):
        assert np.array_equal(hash_unique(uniq, kind, 6)[inv], flow_hash(*t, kind=kind, key_seed=6))
