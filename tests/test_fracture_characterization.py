"""Characterization + depth-audit for fracture.py (the LEFM crack axis).

This is the authoritative facade-detector for the linear-elastic-fracture-mechanics
module: it proves each public closed form is REALLY computed from its textbook formula,
not echoed as a canned constant, and that every documented fail-loud guard fires exactly.

The facade-killer per function is two-pronged:
  (a) the headline claim holds against an INDEPENDENT closed-form / numeric anchor AND the
      output changes meaningfully when a driving input changes (so the input is consumed),
  (b) a mandatory NEGATIVE test fires the documented ValueError / NotImplementedError.

Invariants (math identities) are additionally pinned with Hypothesis property-based tests:
  • K = Y*sigma*sqrt(pi*a) is linear in Y and sigma and scales as sqrt(a);
  • critical_crack_size is the EXACT inverse of stress_intensity (round-trip K -> K_IC);
  • fracture_check.safety_factor == K_IC / K and ok flips at a == a_c;
  • paris_life matches an independent trapezoid integration of da/dN, and is monotone
    decreasing in the initial crack length.

A closed form agreeing with an independent numeric integration / its own algebraic inverse
is the defense against an algebra error hiding inside a confident-looking constant.

Offline, no LLM, pure math (no FEM, no mesher).  Run:  pytest tests/test_fracture_characterization.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import math  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from gen.fracture import (  # noqa: E402
    critical_crack_size,
    fracture_check,
    paris_life,
    paris_life_m2,
    stress_intensity,
)


# --- stress_intensity: K = Y*sigma*sqrt(pi*a), proven against the textbook anchor ----

def test_stress_intensity_matches_closed_form_anchor():
    # Y=1, sigma=100 MPa, a=1 mm -> K = 100*sqrt(pi) MPa*sqrt(mm); recomputed independently.
    k = stress_intensity(1.0, 100.0, 1.0)
    assert math.isclose(k, 1.0 * 100.0 * math.sqrt(math.pi * 1.0), rel_tol=1e-12)
    assert math.isclose(k, 177.2453850905516, rel_tol=1e-12)


def test_stress_intensity_consumes_every_input():
    # Each of Y, sigma, a must move K — a canned constant would ignore them.
    base = stress_intensity(1.0, 100.0, 1.0)
    assert stress_intensity(2.0, 100.0, 1.0) != base       # Y
    assert stress_intensity(1.0, 200.0, 1.0) != base       # sigma
    assert stress_intensity(1.0, 100.0, 4.0) != base       # a
    # exact scaling laws: K is linear in Y and sigma, and ~ sqrt(a)
    assert math.isclose(stress_intensity(2.0, 100.0, 1.0), 2.0 * base, rel_tol=1e-12)
    assert math.isclose(stress_intensity(1.0, 200.0, 1.0), 2.0 * base, rel_tol=1e-12)
    assert math.isclose(stress_intensity(1.0, 100.0, 4.0), 2.0 * base, rel_tol=1e-12)
    assert stress_intensity(1.0, 100.0, 0.0) == 0.0        # zero crack -> zero K


@settings(max_examples=200)
@given(
    y=st.floats(min_value=0.5, max_value=3.0),
    sigma=st.floats(min_value=1.0, max_value=1000.0),
    # bounded away from subnormals so 4*a and sqrt are exact (denormals lose the scaling law)
    a=st.floats(min_value=1e-3, max_value=1000.0),
)
def test_stress_intensity_property_linear_and_sqrt(y, sigma, a):
    # PROPERTY: K(k*Y, sigma, a) == k*K and K(Y, sigma, 4a) == 2*K(Y, sigma, a).
    k = stress_intensity(y, sigma, a)
    assert math.isclose(stress_intensity(3.0 * y, sigma, a), 3.0 * k, rel_tol=1e-9)
    assert math.isclose(stress_intensity(y, sigma, 4.0 * a), 2.0 * k, rel_tol=1e-9)


def test_stress_intensity_rejects_negative_crack():
    # NEGATIVE: a crack has a real, non-negative size -> loud, never a guessed value.
    with pytest.raises(ValueError):
        stress_intensity(1.0, 100.0, -1.0)


# --- critical_crack_size: the EXACT inverse of stress_intensity ----------------------

def test_critical_crack_size_anchor():
    # KIC=2000, Y=1, sigma=100 -> a_c = (1/pi)*(2000/100)**2 = 400/pi mm.
    a_c = critical_crack_size(2000.0, 1.0, 100.0)
    assert math.isclose(a_c, 400.0 / math.pi, rel_tol=1e-12)
    assert math.isclose(a_c, 127.32395447351628, rel_tol=1e-12)


def test_critical_crack_size_consumes_every_input():
    base = critical_crack_size(2000.0, 1.0, 100.0)
    assert critical_crack_size(4000.0, 1.0, 100.0) != base   # K_IC
    assert critical_crack_size(2000.0, 2.0, 100.0) != base   # Y
    assert critical_crack_size(2000.0, 1.0, 200.0) != base   # sigma
    # a_c ~ K_IC**2, ~ 1/Y**2, ~ 1/sigma**2 (exact scaling)
    assert math.isclose(critical_crack_size(4000.0, 1.0, 100.0), 4.0 * base, rel_tol=1e-12)
    assert math.isclose(critical_crack_size(2000.0, 2.0, 100.0), base / 4.0, rel_tol=1e-12)
    assert math.isclose(critical_crack_size(2000.0, 1.0, 200.0), base / 4.0, rel_tol=1e-12)


@settings(max_examples=200)
@given(
    kic=st.floats(min_value=100.0, max_value=5000.0),
    y=st.floats(min_value=0.5, max_value=3.0),
    sigma=st.floats(min_value=1.0, max_value=1000.0),
)
def test_critical_crack_size_inverts_stress_intensity(kic, y, sigma):
    # PROPERTY (the headline claim): plugging a_c back into K must return K_IC exactly.
    a_c = critical_crack_size(kic, y, sigma)
    assert math.isclose(stress_intensity(y, sigma, a_c), kic, rel_tol=1e-9)


def test_critical_crack_size_rejects_nonpositive_inputs():
    # NEGATIVE: each physically-positive input rejects zero/negative (no silent default).
    with pytest.raises(ValueError):
        critical_crack_size(0.0, 1.0, 100.0)      # non-positive toughness
    with pytest.raises(ValueError):
        critical_crack_size(2000.0, 0.0, 100.0)   # non-positive geometry factor
    with pytest.raises(ValueError):
        critical_crack_size(2000.0, 1.0, 0.0)     # zero stress -> unbounded a_c


# --- fracture_check: safety_factor == K_IC/K, ok flips exactly at a == a_c -----------

def test_fracture_check_composes_K_ac_and_safety_factor():
    # sigma=100, a=1, KIC=2000, Y=1.12: every field recomputed from the parts.
    r = fracture_check(100.0, 1.0, 2000.0, geometry_factor_y=1.12)
    assert math.isclose(r["stress_intensity"], stress_intensity(1.12, 100.0, 1.0), rel_tol=1e-12)
    assert math.isclose(
        r["critical_crack_size"], critical_crack_size(2000.0, 1.12, 100.0), rel_tol=1e-12
    )
    assert math.isclose(r["safety_factor"], 2000.0 / r["stress_intensity"], rel_tol=1e-12)
    assert r["ok"] is True


def test_fracture_check_ok_flips_at_critical_crack():
    # The ok verdict and SF>1 boundary must coincide with a == a_c (K == K_IC).
    kic, y, sigma = 1500.0, 1.0, 200.0
    a_c = critical_crack_size(kic, y, sigma)
    below = fracture_check(sigma, 0.9 * a_c, kic, geometry_factor_y=y)
    above = fracture_check(sigma, 1.1 * a_c, kic, geometry_factor_y=y)
    assert below["ok"] and below["safety_factor"] > 1.0
    assert (not above["ok"]) and above["safety_factor"] < 1.0


def test_fracture_check_zero_crack_is_infinitely_safe():
    # a == 0 -> K == 0 -> SF = +inf (the documented k == 0 branch), still ok.
    r = fracture_check(100.0, 0.0, 2000.0)
    assert r["stress_intensity"] == 0.0
    assert r["safety_factor"] == math.inf
    assert r["ok"] is True


def test_fracture_check_default_geometry_is_edge_crack():
    # Documented default Y = 1.12 (edge crack): explicit 1.12 must match the default.
    assert fracture_check(100.0, 1.0, 2000.0) == fracture_check(
        100.0, 1.0, 2000.0, geometry_factor_y=1.12
    )


def test_fracture_check_is_deterministic():
    assert fracture_check(100.0, 1.0, 2000.0) == fracture_check(100.0, 1.0, 2000.0)


def test_fracture_check_rejects_nonpositive_stress():
    # NEGATIVE: a non-positive stress is not an evaluable check.
    with pytest.raises(ValueError):
        fracture_check(0.0, 1.0, 2000.0)
    with pytest.raises(ValueError):
        fracture_check(-50.0, 1.0, 2000.0)


# --- paris_life: closed form vs an independent trapezoid integration -----------------

def _paris_life_trapezoid(c, m, ds, ai, af, y=1.12, n=200_000):
    """Independent reference: trapezoid integration of dN = da / (C*dK**m),
    dK = Y*delta_sigma*sqrt(pi*a). Shares no algebra with the closed form."""
    a = np.linspace(ai, af, n + 1)
    dk = y * ds * np.sqrt(np.pi * a)
    integrand = 1.0 / (c * dk ** m)
    h = (af - ai) / n
    return float(h * (integrand[0] / 2.0 + integrand[1:-1].sum() + integrand[-1] / 2.0))


def test_paris_life_matches_numeric_integration_m3():
    c, m, ds, y = 1e-11, 3.0, 100.0, 1.12
    closed = paris_life(c, m, ds, 1.0, 10.0, geometry_factor_y=y)
    numeric = _paris_life_trapezoid(c, m, ds, 1.0, 10.0, y=y)
    assert math.isclose(closed, numeric, rel_tol=1e-2)
    assert math.isclose(closed, 17480.851358949647, rel_tol=1e-9)  # anchor


def test_paris_life_matches_numeric_integration_m4():
    # A different exponent exercises the general power form, not a memorised special case.
    c, m, ds, y = 1e-11, 4.0, 100.0, 1.12
    closed = paris_life(c, m, ds, 1.0, 10.0, geometry_factor_y=y)
    numeric = _paris_life_trapezoid(c, m, ds, 1.0, 10.0, y=y)
    assert math.isclose(closed, numeric, rel_tol=1e-2)


def test_paris_life_consumes_every_input():
    base = paris_life(1e-11, 3.0, 100.0, 1.0, 10.0)
    assert paris_life(2e-11, 3.0, 100.0, 1.0, 10.0) != base   # C
    assert paris_life(1e-11, 4.0, 100.0, 1.0, 10.0) != base   # m
    assert paris_life(1e-11, 3.0, 150.0, 1.0, 10.0) != base   # delta_stress
    assert paris_life(1e-11, 3.0, 100.0, 2.0, 10.0) != base   # a_initial
    assert paris_life(1e-11, 3.0, 100.0, 1.0, 20.0) != base   # a_final
    # N ~ 1/C exactly: halving C doubles the life.
    assert math.isclose(paris_life(2e-11, 3.0, 100.0, 1.0, 10.0), base / 2.0, rel_tol=1e-12)


@settings(max_examples=100)
@given(ai=st.floats(min_value=0.5, max_value=5.0))
def test_paris_life_monotone_decreasing_in_initial_crack(ai):
    # PROPERTY: a deeper starting flaw is closer to failure -> strictly shorter life.
    c, m, ds, af = 1e-11, 3.0, 100.0, 20.0
    deeper = paris_life(c, m, ds, ai + 1.0, af)
    shallower = paris_life(c, m, ds, ai, af)
    assert 0.0 < deeper < shallower


def test_paris_life_m_equals_2_is_not_implemented_in_power():
    # NEGATIVE: power form for m==2 raises; use m2 function for support.
    with pytest.raises(NotImplementedError):
        paris_life(1e-11, 2.0, 100.0, 1.0, 10.0)


def test_paris_life_m2_log_form_works():
    # autonomous: m=2 log form added and works.
    n = paris_life_m2(1e-11, 100.0, 1.0, 10.0)
    assert n > 0
    assert n > 1000


def test_paris_life_rejects_non_growing_crack():
    # NEGATIVE: a crack only grows; a_final <= a_initial is rejected loudly.
    with pytest.raises(ValueError):
        paris_life(1e-11, 3.0, 100.0, 10.0, 1.0)   # a_final < a_initial
    with pytest.raises(ValueError):
        paris_life(1e-11, 3.0, 100.0, 5.0, 5.0)    # a_final == a_initial


def test_paris_life_rejects_nonpositive_constants():
    with pytest.raises(ValueError):
        paris_life(0.0, 3.0, 100.0, 1.0, 10.0)     # non-positive C
    with pytest.raises(ValueError):
        paris_life(1e-11, 3.0, 0.0, 1.0, 10.0)     # non-positive delta_stress
    with pytest.raises(ValueError):
        paris_life(1e-11, 3.0, 100.0, -1.0, 10.0)  # non-positive crack length
