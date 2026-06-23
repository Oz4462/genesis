"""Depth-audit + characterization for notch_fatigue.py (Peterson/Neuber notch-sensitivity closed forms).

This is the authoritative facade-detector for the notch-fatigue module (legacy
tests/test_notch_fatigue.py is left untouched; no churn).

Proves the three textbook closed forms are GENUINELY COMPUTED (not canned constants):
- Peterson q = 1 / (1 + a/r)
- K_f = 1 + q * (K_t - 1)
- Se_notched = Se / K_f

Pins the exact documented anchor K_t=3, r=1 mm, a=0.25 mm → q=0.8, K_f=2.6, Se_notched=Se/2.6.

Proves inputs are consumed: output changes with every driving parameter; monotone
in radius (larger r → blunter → higher q and K_f approaching K_t; smaller r → sharper
→ lower q and K_f approaching 1).

For any finite r>0 and a>0, K_f is strictly 1 < K_f < K_t (when K_t>1).

Proves notch_fatigue_check composes correctly: safety_factor == Se / (K_f * nominal)
== se_notched / nominal (algebraic identity), local_effective == K_f * nominal,
and ok flips exactly at the safety_factor=1 boundary (nominal just below/above Se_notched).

Adds property-based tests (Hypothesis) for the invariants (monotonicity, strict bounds,
identity) plus determinism.

Adds NEGATIVE tests for EVERY documented guard asserting the exact ValueError message:
- non-positive notch_radius
- negative peterson_constant_a
- K_t < 1
- non-positive Se
- K_f < 1
- non-positive nominal alternating stress

The module is REAL on inspection and under test (closed forms + fail-loud). Only edit
src/gen/notch_fatigue.py if a test exposes a genuine numeric or guard defect; otherwise
no source changes.

Offline, no LLM, pure Python + hypothesis (already a declared dev dep).

Run:  pytest tests/test_notch_fatigue_depth.py -q --tb=line
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402
from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from gen.notch_fatigue import (  # noqa: E402
    fatigue_notch_factor,
    notch_endurance_limit,
    notch_fatigue_check,
    notch_sensitivity,
)


# --- concrete textbook anchor (must be byte-stable) -------------------------------

def test_anchor_kt3_r1_a025():
    """K_t=3, notch_radius=1 mm, peterson_constant_a=0.25 mm → q=0.8, K_f=2.6,
    notch_endurance_limit(Se, 2.6) = Se/2.6 exactly (per docstring and Shigley)."""
    assert math.isclose(notch_sensitivity(1.0, 0.25), 0.8, rel_tol=1e-12)
    assert math.isclose(fatigue_notch_factor(3.0, 1.0, 0.25), 2.6, rel_tol=1e-12)
    assert math.isclose(notch_endurance_limit(200.0, 2.6), 200.0 / 2.6, rel_tol=1e-12)


# --- inputs are consumed (no dead params) + monotonicity --------------------------

def test_notch_sensitivity_consumes_radius_and_a_and_is_monotone():
    """q must change when r or a changes (input consumed). Larger r (blunter) → q↑;
    smaller r (sharper) → q↓. q in (0,1) for positive finite inputs."""
    base = notch_sensitivity(1.0, 0.25)
    assert notch_sensitivity(2.0, 0.25) > base   # r larger → q larger
    assert notch_sensitivity(0.5, 0.25) < base   # r smaller → q smaller
    assert notch_sensitivity(1.0, 0.5) < base    # a larger → q smaller
    assert 0.0 < base < 1.0


def test_fatigue_notch_factor_consumes_all_and_monotone_in_radius():
    """K_f changes with kt, r, a. For fixed kt>1 and a>0, larger r yields strictly
    larger K_f (closer to K_t); smaller r yields strictly smaller K_f (closer to 1)."""
    kt = 3.0
    a = 0.25
    base = fatigue_notch_factor(kt, 1.0, a)
    # each input moves the output
    assert fatigue_notch_factor(4.0, 1.0, a) != base
    assert fatigue_notch_factor(kt, 2.0, a) != base
    assert fatigue_notch_factor(kt, 1.0, 0.5) != base
    # monotone in radius
    assert fatigue_notch_factor(kt, 5.0, a) > fatigue_notch_factor(kt, 0.5, a)
    assert fatigue_notch_factor(kt, 10.0, a) > fatigue_notch_factor(kt, 1.0, a)


# --- property-based invariants (Hypothesis) ---------------------------------------

@settings(max_examples=150)
@given(
    r=st.floats(min_value=1e-4, max_value=1e4),
    a=st.floats(min_value=1e-6, max_value=5.0),  # a>0 ensures strict inequality
    kt=st.floats(min_value=1.0001, max_value=8.0),
)
def test_kf_strictly_between_1_and_kt_for_finite_r_and_positive_a(r, a, kt):
    """PROPERTY: for any finite r>0 and material a>0 with K_t>1, the fatigue factor
    is strictly weaker than the full static raiser: 1 < K_f < K_t.
    (When a=0 the formula yields K_f == K_t which is correct but not strict.)"""
    kf = fatigue_notch_factor(kt, r, a)
    assert 1.0 < kf < kt


@settings(max_examples=100)
@given(
    r=st.floats(min_value=0.01, max_value=100.0),
    a=st.floats(min_value=0.0, max_value=2.0),
    kt=st.floats(min_value=1.0, max_value=5.0),
)
def test_kf_monotonic_in_radius_property(r, a, kt):
    """PROPERTY: increasing radius (blunter notch) never decreases K_f.
    (Uses rel_tol to tolerate floating point at extremes.)"""
    kf_small = fatigue_notch_factor(kt, r, a)
    kf_large = fatigue_notch_factor(kt, r * 4.0, a)
    assert kf_large >= kf_small - 1e-12


@settings(max_examples=80)
@given(
    se=st.floats(min_value=10.0, max_value=500.0),
    kf=st.floats(min_value=1.0, max_value=6.0),
)
def test_endurance_limit_identity(se, kf):
    """PROPERTY: Se_notched * K_f == Se (the definition inverted)."""
    se_n = notch_endurance_limit(se, kf)
    assert math.isclose(se_n * kf, se, rel_tol=1e-12)


# --- check composition: identities and boundary flip ------------------------------

def test_check_composes_from_primitives_and_sf_identities():
    """notch_fatigue_check must be the composition of the three primitives.
    safety_factor must equal both Se/(K_f·nominal) and se_notched/nominal."""
    nominal = 50.0
    kt = 3.0
    r = 1.0
    a = 0.25
    se = 200.0
    res = notch_fatigue_check(nominal, kt, r, a, se)

    # matches the sub-functions
    q = notch_sensitivity(r, a)
    kf = fatigue_notch_factor(kt, r, a)
    se_n = notch_endurance_limit(se, kf)
    assert math.isclose(res["q"], q, rel_tol=1e-12)
    assert math.isclose(res["kf"], kf, rel_tol=1e-12)
    assert math.isclose(res["se_notched"], se_n, rel_tol=1e-12)
    assert math.isclose(res["local_effective_stress"], kf * nominal, rel_tol=1e-12)

    # the two algebraic expressions for safety_factor are identical
    assert math.isclose(res["safety_factor"], se / (kf * nominal), rel_tol=1e-12)
    assert math.isclose(res["safety_factor"], res["se_notched"] / nominal, rel_tol=1e-12)
    assert res["ok"] is True


def test_check_ok_flips_exactly_at_sf_equals_one():
    """ok must be True just below the endurance boundary and False just above.
    Boundary nominal == se_notched must be ok (sf >= 1)."""
    kt, r, a, se = 3.0, 1.0, 0.25, 200.0
    kf = fatigue_notch_factor(kt, r, a)
    se_notched = notch_endurance_limit(se, kf)  # = 200/2.6 ≈ 76.923

    # just safe
    just_below = notch_fatigue_check(se_notched * 0.999, kt, r, a, se)
    assert just_below["ok"] and just_below["safety_factor"] > 1.0

    # exactly at limit → ok (sf >= 1)
    at_limit = notch_fatigue_check(se_notched, kt, r, a, se)
    assert at_limit["ok"] and math.isclose(at_limit["safety_factor"], 1.0, rel_tol=1e-12)

    # just unsafe
    just_above = notch_fatigue_check(se_notched * 1.001, kt, r, a, se)
    assert (not just_above["ok"]) and just_above["safety_factor"] < 1.0


def test_check_is_deterministic():
    """Same inputs → identical dict (A5 reproducibility for this pure function)."""
    args = (50.0, 3.0, 1.0, 0.25, 200.0)
    a = notch_fatigue_check(*args)
    b = notch_fatigue_check(*args)
    assert a == b


@settings(max_examples=60)
@given(
    nominal=st.floats(min_value=1e-3, max_value=200.0),
    kt=st.floats(min_value=1.0, max_value=5.0),
    r=st.floats(min_value=1e-3, max_value=50.0),
    a=st.floats(min_value=0.0, max_value=2.0),
    se=st.floats(min_value=10.0, max_value=800.0),
)
def test_check_safety_factor_property(nominal, kt, r, a, se):
    """PROPERTY: for any valid positive inputs the two expressions for safety_factor
    remain identical and ok == (safety_factor >= 1)."""
    res = notch_fatigue_check(nominal, kt, r, a, se)
    kf = res["kf"]
    sf1 = se / (kf * nominal)
    sf2 = res["se_notched"] / nominal
    assert math.isclose(res["safety_factor"], sf1, rel_tol=1e-9)
    assert math.isclose(res["safety_factor"], sf2, rel_tol=1e-9)
    assert res["ok"] == (res["safety_factor"] >= 1.0)


# --- guards: loud failure with exact documented messages (no silent defaults) -----

def test_notch_sensitivity_rejects_non_positive_radius():
    for bad in (0.0, -0.1, -1e-9):
        with pytest.raises(ValueError, match="notch radius must be positive"):
            notch_sensitivity(bad, 0.25)


def test_notch_sensitivity_rejects_negative_peterson_a():
    with pytest.raises(ValueError, match="Peterson constant a must be non-negative"):
        notch_sensitivity(1.0, -0.0001)
    # a == 0 is valid (full sensitivity)
    assert math.isclose(notch_sensitivity(1.0, 0.0), 1.0, rel_tol=1e-12)


def test_fatigue_notch_factor_rejects_kt_below_one():
    for bad in (0.0, 0.999, -5.0):
        with pytest.raises(ValueError, match="stress-concentration factor K_t must be >= 1"):
            fatigue_notch_factor(bad, 1.0, 0.25)


def test_notch_endurance_limit_rejects_non_positive_se():
    for bad in (0.0, -10.0):
        with pytest.raises(ValueError, match="smooth endurance limit Se must be positive"):
            notch_endurance_limit(bad, 2.0)


def test_notch_endurance_limit_rejects_kf_below_one():
    for bad in (0.0, 0.5, 0.999):
        with pytest.raises(ValueError, match="fatigue notch factor K_f must be >= 1"):
            notch_endurance_limit(200.0, bad)


def test_check_rejects_non_positive_nominal_stress():
    for bad in (0.0, -1.0, -0.001):
        with pytest.raises(ValueError, match="nominal alternating stress must be positive"):
            notch_fatigue_check(bad, 3.0, 1.0, 0.25, 200.0)


def test_check_propagates_sub_guards_with_exact_messages():
    """When a sub-function guard fires inside check, the exact message surfaces."""
    with pytest.raises(ValueError, match="stress-concentration factor K_t must be >= 1"):
        notch_fatigue_check(50.0, kt=0.5, notch_radius=1.0, peterson_constant_a=0.25, smooth_endurance_se=200.0)

    with pytest.raises(ValueError, match="notch radius must be positive"):
        notch_fatigue_check(50.0, kt=3.0, notch_radius=0.0, peterson_constant_a=0.25, smooth_endurance_se=200.0)

    with pytest.raises(ValueError, match="Peterson constant a must be non-negative"):
        notch_fatigue_check(50.0, kt=3.0, notch_radius=1.0, peterson_constant_a=-1.0, smooth_endurance_se=200.0)

    with pytest.raises(ValueError, match="smooth endurance limit Se must be positive"):
        notch_fatigue_check(50.0, kt=3.0, notch_radius=1.0, peterson_constant_a=0.25, smooth_endurance_se=0.0)
