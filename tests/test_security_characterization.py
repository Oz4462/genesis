"""Depth-audit (facade-detector) for ``src/gen/security.py``.

Goal: prove the three crypto-sizing validators COMPUTE their numbers from the
cited closed forms — they are not constant stubs that echo an anchor. For each
validator the test asserts (a) the headline output changes meaningfully and in
the closed-form-predicted way when a driving input changes, and (b) every
documented fail-loud / abstention path fires exactly (the mandatory negatives).

Closed forms cross-checked:
  * birthday bound (Katz & Lindell): p ≈ q²/2^(n+1) — quadratic in q, halves per
    extra space bit; safety_factor = max/p; clamps at 1.0 outside the regime.
  * NIST SP 800-57 Part 1 Rev. 5 Table 2: AES-128 ≡ RSA-3072 ≡ ECC-P-256 = 128;
    ECC strength = key_bits/2 for ANY size; symmetric strength = key length;
    RSA modulus below 1024 → 0 (below every standardized row).
  * NIST SP 800-38D §8.3: AES-GCM random-IV budget = 2^32 invocations/key;
    safety_factor = max/n, inclusive at the limit.

Offline, no LLM, no numpy. Run:  pytest tests/test_security_characterization.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402
from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from gen.security import (  # noqa: E402
    GCM_IV_COLLISION_BOUND,
    GCM_RANDOM_IV_MAX_INVOCATIONS,
    REQUIRED_SECURITY_BITS,
    birthday_bound_check,
    birthday_collision_probability,
    gcm_invocation_budget_check,
    key_security_check,
    security_strength_bits,
)


# ============================================================ birthday bound
# The closed form is p = q²/2^(n+1). A facade that returned a constant would
# fail every scaling assertion below; only genuine arithmetic survives them.

def test_birthday_probability_matches_closed_form_for_many_points():
    # Cross-check against an independently-computed q²/2^(n+1) at several points
    # well inside the p « 1 regime (so no clamping masks the arithmetic).
    for space_bits, q in [(40.0, 1000.0), (64.0, 2.0 ** 20), (80.0, 5000.0),
                          (96.0, 2.0 ** 30), (50.0, 1.0)]:
        expected = (q * q) / (2.0 ** (space_bits + 1.0))
        assert birthday_collision_probability(space_bits, q) == pytest.approx(expected)


def test_birthday_probability_is_quadratic_in_uses():
    # Doubling the number of draws must QUADRUPLE the probability (q² law).
    base = birthday_collision_probability(80.0, 1000.0)
    quad = birthday_collision_probability(80.0, 2000.0)
    assert quad == pytest.approx(4.0 * base)
    # Tripling -> 9x. A constant stub cannot reproduce this ratio.
    assert birthday_collision_probability(80.0, 3000.0) == pytest.approx(9.0 * base)


def test_birthday_probability_halves_per_extra_space_bit():
    # Each added bit of space doubles 2^(n+1), so p halves — the input is consumed.
    p_n = birthday_collision_probability(64.0, 12345.0)
    p_n1 = birthday_collision_probability(65.0, 12345.0)
    assert p_n1 == pytest.approx(p_n / 2.0)


def test_birthday_probability_clamps_at_one_outside_regime():
    # Far outside p « 1 the approximation is capped, never returns >1 nonsense.
    assert birthday_collision_probability(4.0, 1000.0) == 1.0
    assert 0.0 < birthday_collision_probability(4.0, 1.0) < 1.0


def test_birthday_bound_check_safety_factor_is_max_over_p():
    # safety_factor = max_collision_prob / p exactly — and tracks the input p.
    res = birthday_bound_check(96.0, 2.0 ** 32)  # p = 2^-33, bound = 2^-32
    assert res["collision_probability"] == pytest.approx(2.0 ** -33)
    assert res["safety_factor"] == pytest.approx(res["max_collision_prob"] / res["collision_probability"])
    assert res["safety_factor"] == pytest.approx(2.0)
    assert res["ok"] is True
    # More uses -> smaller safety factor -> eventually fails. Driving input alive.
    worse = birthday_bound_check(96.0, 2.0 ** 33)  # p = 2^-31 = 2x bound
    assert worse["safety_factor"] == pytest.approx(0.5) and worse["ok"] is False


def test_birthday_bound_zero_uses_is_infinite_safety():
    res = birthday_bound_check(96.0, 0.0)
    assert res["collision_probability"] == 0.0
    assert res["safety_factor"] == float("inf") and res["ok"] is True


def test_birthday_default_bound_is_the_nist_2pow_minus_32():
    assert GCM_IV_COLLISION_BOUND == 2.0 ** -32
    assert birthday_bound_check(96.0, 10.0)["max_collision_prob"] == 2.0 ** -32


def test_birthday_negatives_fire_exactly():
    with pytest.raises(ValueError):
        birthday_collision_probability(0.0, 5.0)       # non-positive space
    with pytest.raises(ValueError):
        birthday_collision_probability(-1.0, 5.0)
    with pytest.raises(ValueError):
        birthday_collision_probability(64.0, -1.0)     # negative uses
    with pytest.raises(ValueError):
        birthday_bound_check(96.0, 10.0, max_collision_prob=0.0)   # bound <= 0
    with pytest.raises(ValueError):
        birthday_bound_check(96.0, 10.0, max_collision_prob=1.5)   # bound > 1


# ===================================================== SP 800-57 key strength

def test_the_128_bit_equivalence_row_is_computed():
    # AES-128 ≡ RSA-3072 ≡ ECC-P-256 — the literal Table-2 row.
    assert security_strength_bits("symmetric", 128.0) == 128.0
    assert security_strength_bits("rsa", 3072.0) == 128.0
    assert security_strength_bits("ecc", 256.0) == 128.0


def test_all_rsa_table_rows_and_boundaries():
    # Each documented row, plus that values just below a row take the lower row's
    # strength (the standard's granularity) — proving a table lookup, not a constant.
    assert security_strength_bits("rsa", 15360.0) == 256.0
    assert security_strength_bits("rsa", 7680.0) == 192.0
    assert security_strength_bits("rsa", 3072.0) == 128.0
    assert security_strength_bits("rsa", 2048.0) == 112.0
    assert security_strength_bits("rsa", 1024.0) == 80.0
    assert security_strength_bits("rsa", 3071.0) == 112.0   # just under 3072 -> 112
    assert security_strength_bits("rsa", 1023.0) == 0.0     # below every row
    assert security_strength_bits("dh", 2048.0) == 112.0    # DH shares the table


def test_symmetric_strength_equals_key_length_for_arbitrary_sizes():
    # strength == key length for any key — not a hardcoded 128.
    for k in (80.0, 112.0, 192.0, 256.0, 333.0):
        assert security_strength_bits("symmetric", k) == k


def test_ecc_strength_is_half_key_bits_for_arbitrary_sizes():
    for k in (160.0, 224.0, 256.0, 384.0, 521.0):
        assert security_strength_bits("ecc", k) == pytest.approx(k / 2.0)


def test_key_security_check_safety_factor_and_default():
    assert REQUIRED_SECURITY_BITS == 128
    weak = key_security_check("rsa", 2048.0)          # 112 < 128 default
    assert weak["strength_bits"] == 112.0 and weak["ok"] is False
    assert weak["safety_factor"] == pytest.approx(112.0 / 128.0)
    # Same key passes against a declared legacy 112-bit requirement.
    legacy = key_security_check("rsa", 2048.0, required_bits=112.0)
    assert legacy["ok"] is True and legacy["safety_factor"] == pytest.approx(1.0)


def test_key_security_negatives_fire_exactly():
    with pytest.raises(ValueError):
        security_strength_bits("kyber", 1024.0)        # unknown mechanism, never guessed
    with pytest.raises(ValueError):
        security_strength_bits("symmetric", 0.0)       # non-positive key
    with pytest.raises(ValueError):
        key_security_check("symmetric", 128.0, required_bits=0.0)  # non-positive requirement


# ============================================================== GCM budget

def test_gcm_budget_constant_and_safety_factor():
    assert GCM_RANDOM_IV_MAX_INVOCATIONS == 2 ** 32
    at = gcm_invocation_budget_check(float(2 ** 32))      # inclusive at the limit
    assert at["ok"] is True and at["safety_factor"] == pytest.approx(1.0)
    over = gcm_invocation_budget_check(float(2 ** 32) + 1.0)
    assert over["ok"] is False
    # safety_factor = max/n exactly and tracks n (half the budget -> SF 2).
    half = gcm_invocation_budget_check(float(2 ** 31))
    assert half["safety_factor"] == pytest.approx(2.0)
    assert gcm_invocation_budget_check(0.0)["safety_factor"] == float("inf")


def test_gcm_negatives_fire_exactly():
    with pytest.raises(ValueError):
        gcm_invocation_budget_check(-1.0)                # negative count
    with pytest.raises(ValueError):
        gcm_invocation_budget_check(10.0, max_invocations=0.0)  # non-positive budget


# ======================================================= property-based laws

@given(
    space_bits=st.floats(min_value=20.0, max_value=200.0),
    q=st.floats(min_value=1.0, max_value=1e6),
)
@settings(max_examples=200)
def test_property_birthday_matches_closed_form(space_bits, q):
    # Invariant: p == min(q²/2^(n+1), 1) for all valid inputs — the headline claim.
    expected = min((q * q) / (2.0 ** (space_bits + 1.0)), 1.0)
    assert birthday_collision_probability(space_bits, q) == pytest.approx(expected, rel=1e-9, abs=0.0)


@given(q=st.floats(min_value=1.0, max_value=1e7), space_bits=st.floats(min_value=80.0, max_value=180.0))
@settings(max_examples=150)
def test_property_birthday_quadratic_scaling(q, space_bits):
    # Doubling q quadruples p whenever we stay in the unclamped p « 1 regime.
    base = birthday_collision_probability(space_bits, q)
    doubled = birthday_collision_probability(space_bits, 2.0 * q)
    if doubled < 1.0:  # only meaningful before the clamp engages
        assert doubled == pytest.approx(4.0 * base, rel=1e-9)


@given(k=st.floats(min_value=1.0, max_value=4096.0))
@settings(max_examples=100)
def test_property_ecc_is_half_and_symmetric_is_identity(k):
    assert security_strength_bits("ecc", k) == pytest.approx(k / 2.0)
    assert security_strength_bits("symmetric", k) == pytest.approx(k)


@given(n=st.floats(min_value=0.0, max_value=1e12))
@settings(max_examples=100)
def test_property_gcm_safety_factor_is_max_over_n(n):
    res = gcm_invocation_budget_check(n)
    if n == 0.0:
        assert res["safety_factor"] == float("inf")
    else:
        assert res["safety_factor"] == pytest.approx(GCM_RANDOM_IV_MAX_INVOCATIONS / n)
    # ok iff within budget — the gate is consistent with the computed number.
    assert res["ok"] == (n <= GCM_RANDOM_IV_MAX_INVOCATIONS)


@given(
    mech=st.sampled_from(["symmetric", "ecc", "rsa"]),
    k=st.floats(min_value=64.0, max_value=16384.0),
    req=st.floats(min_value=1.0, max_value=256.0),
)
@settings(max_examples=150)
def test_property_key_security_ok_iff_strength_meets_requirement(mech, k, req):
    res = key_security_check(mech, k, required_bits=req)
    assert res["ok"] == (res["strength_bits"] >= req)
    assert res["safety_factor"] == pytest.approx(res["strength_bits"] / req)
    assert math.isfinite(res["safety_factor"])
