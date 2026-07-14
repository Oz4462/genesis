"""Linear elastic fracture mechanics — the closed forms pinned to exact limits and anchors.

The stress intensity K = Y*sigma*sqrt(pi*a) must hit the anchor 100*sqrt(pi) for
Y=1,sigma=100,a=1; the critical crack size must INVERT the K formula exactly (plug a_c back
-> K == K_IC to machine precision); the fracture-check safety factor must be K_IC/K; and the
Paris closed-form life must match a direct trapezoid integration of da/dN to well under a
percent. A closed form agreeing with an independent numeric integration is the defense
against an algebra error in either.

Offline, no LLM, pure math (no FEM, no mesher).

Run:  pytest tests/test_fracture.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import math  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from gen.fracture import (  # noqa: E402
    critical_crack_size,
    fracture_check,
    paris_life,
    stress_intensity,
)


# --- the stress intensity identity and its concrete anchor ----------------------

def test_stress_intensity_anchor():
    # Y=1, sigma=100 MPa, a=1 mm -> K = 100*sqrt(pi) = 177.245... MPa*sqrt(mm)
    k = stress_intensity(1.0, 100.0, 1.0)
    assert math.isclose(k, 100.0 * math.sqrt(math.pi), rel_tol=1e-12)
    assert math.isclose(k, 177.2453850905516, rel_tol=1e-12)


def test_stress_intensity_scales_with_sqrt_a():
    # K ~ sqrt(a): quadrupling the crack length doubles K
    base = stress_intensity(1.12, 100.0, 1.0)
    assert np.isclose(stress_intensity(1.12, 100.0, 4.0), 2.0 * base)   # sqrt(4) = 2
    assert stress_intensity(1.0, 100.0, 0.0) == 0.0                     # zero crack, zero K


# --- the critical crack size inverts K = K_IC exactly ---------------------------

def test_critical_crack_size_inverts_the_K_formula():
    # plug a_c back into K -> must equal K_IC to machine precision (the exact inverse)
    for y, sigma, kic in ((1.0, 100.0, 2000.0), (1.12, 250.0, 1500.0), (1.5, 80.0, 900.0)):
        a_c = critical_crack_size(kic, y, sigma)
        assert math.isclose(stress_intensity(y, sigma, a_c), kic, rel_tol=1e-12)


def test_critical_crack_size_anchor():
    # KIC=2000, Y=1, sigma=100 -> a_c = (1/pi)*(2000/100)**2 = 400/pi = 127.3239... mm
    a_c = critical_crack_size(2000.0, 1.0, 100.0)
    assert math.isclose(a_c, 400.0 / math.pi, rel_tol=1e-12)
    assert math.isclose(a_c, 127.32395447351628, rel_tol=1e-12)


def test_critical_crack_size_shrinks_with_stress():
    # a_c ~ 1/sigma**2: doubling the stress quarters the critical crack size
    low = critical_crack_size(2000.0, 1.0, 100.0)
    high = critical_crack_size(2000.0, 1.0, 200.0)
    assert np.isclose(high, low / 4.0)


# --- the design check: fast fracture vs toughness governs -----------------------

def test_fracture_check_reports_K_ac_and_safety_factor():
    # sigma=100, a=1, KIC=2000, Y=1.12 -> K=198.5148, a_c=101.5019, SF=10.0748, ok
    r = fracture_check(100.0, 1.0, 2000.0, geometry_factor_y=1.12)
    assert math.isclose(r["stress_intensity"], 198.51483130141781, rel_tol=1e-12)
    assert math.isclose(r["critical_crack_size"], 101.50187697187201, rel_tol=1e-12)
    assert math.isclose(r["safety_factor"], 2000.0 / r["stress_intensity"], rel_tol=1e-12)
    assert math.isclose(r["safety_factor"], 10.074813991924218, rel_tol=1e-9)
    assert r["ok"]


def test_fracture_check_safety_factor_is_kic_over_k():
    # the safety factor is exactly K_IC/K, and ok flips at a == a_c (K == K_IC)
    kic, y, sigma = 1500.0, 1.0, 200.0
    a_c = critical_crack_size(kic, y, sigma)
    below = fracture_check(sigma, 0.9 * a_c, kic, geometry_factor_y=y)
    above = fracture_check(sigma, 1.1 * a_c, kic, geometry_factor_y=y)
    assert below["ok"] and below["safety_factor"] > 1.0
    assert not above["ok"] and above["safety_factor"] < 1.0


# --- the Paris life matches a direct numeric integration ------------------------

def _paris_life_trapezoid(c, m, ds, ai, af, y=1.12, n=200_000):
    """Independent reference: trapezoid integration of dN = da / (C*dK**m),
    dK = Y*delta_sigma*sqrt(pi*a). No shared algebra with the closed form."""
    a = np.linspace(ai, af, n + 1)
    dk = y * ds * np.sqrt(np.pi * a)
    integrand = 1.0 / (c * dk ** m)
    h = (af - ai) / n
    # composite trapezoid sum (np.trapz was renamed np.trapezoid in numpy 2.0)
    return float(h * (integrand[0] / 2.0 + integrand[1:-1].sum() + integrand[-1] / 2.0))


def test_paris_closed_form_matches_numeric_integration_m3():
    c, m, ds, y = 1e-11, 3.0, 100.0, 1.12
    ai, af = 1.0, 10.0
    closed = paris_life(c, m, ds, ai, af, geometry_factor_y=y)
    numeric = _paris_life_trapezoid(c, m, ds, ai, af, y=y)
    assert math.isclose(closed, numeric, rel_tol=1e-2)        # well under 1%
    assert math.isclose(closed, 17480.851358949647, rel_tol=1e-9)   # anchor


def test_paris_closed_form_matches_numeric_integration_m4():
    # a different exponent exercises the general power form, not a special case
    c, m, ds, y = 1e-11, 4.0, 100.0, 1.12
    ai, af = 1.0, 10.0
    closed = paris_life(c, m, ds, ai, af, geometry_factor_y=y)
    numeric = _paris_life_trapezoid(c, m, ds, ai, af, y=y)
    assert math.isclose(closed, numeric, rel_tol=1e-2)


def test_larger_initial_crack_gives_fewer_cycles():
    # a deeper starting flaw is closer to failure -> shorter remaining crack-growth life
    c, m, ds = 1e-11, 3.0, 100.0
    shallow = paris_life(c, m, ds, 1.0, 10.0)
    deep = paris_life(c, m, ds, 4.0, 10.0)
    assert deep < shallow
    assert shallow > 0.0 and deep > 0.0


# --- guards: loud failure, never a guessed value --------------------------------

def test_paris_m_equals_2_uses_logarithmic_closed_form():
    # m == 2: power form divides by zero → ln(a_f/a_i)/(C*(Y*ds*√π)**2)
    import math

    c, m, ds, ai, af, y = 1e-11, 2.0, 100.0, 1.0, 10.0, 1.12
    closed = paris_life(c, m, ds, ai, af, geometry_factor_y=y)
    expected = math.log(af / ai) / (c * (y * ds * math.sqrt(math.pi)) ** 2)
    assert math.isclose(closed, expected, rel_tol=1e-12)
    assert closed > 0.0


def test_paris_rejects_non_growing_crack():
    with pytest.raises(ValueError):
        paris_life(1e-11, 3.0, 100.0, 10.0, 1.0)      # a_final < a_initial
    with pytest.raises(ValueError):
        paris_life(1e-11, 3.0, 100.0, 5.0, 5.0)       # a_final == a_initial


def test_guards_reject_impossible_inputs():
    with pytest.raises(ValueError):
        stress_intensity(1.0, 100.0, -1.0)            # negative crack length
    with pytest.raises(ValueError):
        critical_crack_size(2000.0, 1.0, 0.0)         # zero stress -> unbounded a_c
    with pytest.raises(ValueError):
        critical_crack_size(0.0, 1.0, 100.0)          # non-positive toughness
    with pytest.raises(ValueError):
        fracture_check(0.0, 1.0, 2000.0)              # non-positive stress
    with pytest.raises(ValueError):
        paris_life(0.0, 3.0, 100.0, 1.0, 10.0)        # non-positive C
    with pytest.raises(ValueError):
        paris_life(1e-11, 3.0, 0.0, 1.0, 10.0)        # non-positive delta_stress


def test_check_is_deterministic():
    a = fracture_check(100.0, 1.0, 2000.0)
    b = fracture_check(100.0, 1.0, 2000.0)
    assert a == b
