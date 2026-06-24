"""Characterization: pressure_vessel.py closed forms are REALLY computed (not facade).

This is the authoritative facade-detector for T05 (legacy test_pressure_vessel.py left untouched,
no churn). It cross-checks every headline identity and anchor against the module docstring:

- Thin-wall cylinder: hoop = p·r/t is EXACTLY twice axial = p·r/(2·t)
- Anchor: p=10 MPa, r=500 mm, t=10 mm => hoop exactly 500.0 MPa
- Sphere: thin_wall_sphere = cylinder_hoop / 2 (optimal shape)
- Thick-wall Lamé (1833): sigma_r(r_inner) == -p_i and sigma_r(r_outer) == 0 to machine precision
- Inner-wall hoop (thick) > thin-wall estimate; gap shrinks monotonically as t/r -> 0
- pressure_vessel_check('thick') max_hoop >= 'thin' (same inputs); safety_factor = yield/max_hoop;
  ok == (sf >= 1) flips exactly as yield crosses max_hoop

Facade-killer (per team decisions):
(a) changing a driving input (p, r, t, yield, model) produces observably different output
    (proves consumption, not constant stub)
(b) every documented guard fires with the exact error type (GeometryError / ValueError)
    and the behavior is deterministic (A5)

Property-based tests (Hypothesis) cover the invariants over ranges, in addition to concrete
anchors. Negative tests are mandatory ("a gate without a test does not exist").

Pure math, offline, deterministic. Uses only stdlib + declared deps (numpy/hypothesis for
some scaling + properties).

Run:  PYTHONPATH=src python3 -m pytest tests/test_pressure_vessel_characterization.py -q
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.errors import GeometryError  # noqa: E402
from gen.pressure_vessel import (  # noqa: E402
    pressure_vessel_check,
    thick_wall_cylinder_stresses,
    thin_wall_cylinder,
    thin_wall_sphere,
)


# --- thin-wall membrane theory anchors + identities ------------------------------

def test_thin_cylinder_anchor_exactly_500_mpa():
    """p=10 MPa, r=500 mm, t=10 mm -> hoop = p*r/t = 500 MPa exactly (docstring anchor)."""
    r = thin_wall_cylinder(10.0, 500.0, 10.0)
    assert math.isclose(r["hoop_stress"], 500.0, abs_tol=0.0)
    assert math.isclose(r["axial_stress"], 250.0, abs_tol=0.0)


def test_thin_hoop_exactly_twice_axial():
    """hoop = p*r/t is exactly twice axial = p*r/(2*t) (why cylinders split lengthwise)."""
    res = thin_wall_cylinder(7.3, 412.0, 9.1)
    assert math.isclose(res["hoop_stress"], 2.0 * res["axial_stress"], rel_tol=1e-12)


def test_thin_sphere_is_exactly_half_cylinder_hoop():
    """Sphere sigma = p*r/(2*t) == cylinder_hoop / 2 (optimal pressure shape)."""
    cyl = thin_wall_cylinder(10.0, 500.0, 10.0)["hoop_stress"]
    sph = thin_wall_sphere(10.0, 500.0, 10.0)
    assert math.isclose(sph, 250.0, abs_tol=0.0)
    assert math.isclose(sph, cyl / 2.0, rel_tol=1e-12)


# --- Lame thick-wall: exact BCs, max at inner, higher than thin ------------------

def test_lame_radial_boundary_conditions_exact():
    """sigma_r(r_i) == -p_i and sigma_r(r_o) == 0 to machine precision (Lame 1833)."""
    p, ri, ro = 10.0, 100.0, 200.0
    inner = thick_wall_cylinder_stresses(p, ri, ro, ri)
    outer = thick_wall_cylinder_stresses(p, ri, ro, ro)
    assert math.isclose(inner["radial_stress"], -p, rel_tol=1e-12, abs_tol=0.0)
    assert math.isclose(outer["radial_stress"], 0.0, rel_tol=1e-12, abs_tol=1e-12)


def test_lame_inner_hoop_higher_than_thin_estimate():
    """At the inner wall, Lame hoop > thin-wall membrane estimate (conservative)."""
    p = 10.0
    for ri, t in [(500.0, 10.0), (100.0, 100.0), (200.0, 5.0)]:
        ro = ri + t
        thick = thick_wall_cylinder_stresses(p, ri, ro, ri)["hoop_stress"]
        thin = p * ri / t
        assert thick > thin


def test_thick_thin_gap_shrinks_as_tr_to_zero():
    """The relative gap (thick - thin)/thin shrinks as t/r -> 0; documented 1% at 0.02."""
    p, ri = 10.0, 500.0
    gaps = []
    tr_values = [0.1, 0.05, 0.02, 0.01, 0.001]
    for tr in tr_values:
        ro = ri * (1.0 + tr)
        t = ro - ri
        thick = thick_wall_cylinder_stresses(p, ri, ro, ri)["hoop_stress"]
        thin = p * ri / t
        gaps.append(100.0 * (thick - thin) / thin)
    # strictly monotonic shrink
    assert all(earlier > later for earlier, later in zip(gaps, gaps[1:]))
    # at t/r=0.02 the gap is ~1.01% (pinned)
    assert math.isclose(gaps[2], 1.0099009900990099, rel_tol=1e-9)
    # at very thin, gap tiny
    assert gaps[-1] < 0.06


# --- pressure_vessel_check contract (thick vs thin, sf, ok flip) -----------------

def test_check_thick_max_hoop_ge_thin_same_inputs():
    """'thick' inner-wall max_hoop is always >= 'thin' (equal only in limit t/r->0)."""
    thin = pressure_vessel_check(10.0, 500.0, 10.0, 600.0, model="thin")
    thick = pressure_vessel_check(10.0, 500.0, 10.0, 600.0, model="thick")
    assert thick["max_hoop"] > thin["max_hoop"]
    assert thick["safety_factor"] < thin["safety_factor"]


def test_check_safety_factor_and_ok_flip_exactly_at_yield():
    """safety_factor = yield / max_hoop; ok flips from False to True as yield crosses max_hoop."""
    p, ri, t = 10.0, 500.0, 10.0
    maxh_thin = 500.0
    # below yield
    below = pressure_vessel_check(p, ri, t, 499.0, model="thin")
    assert math.isclose(below["max_hoop"], maxh_thin)
    assert math.isclose(below["safety_factor"], 499.0 / 500.0)
    assert below["ok"] is False
    # exactly at yield -> ok ( >= )
    at = pressure_vessel_check(p, ri, t, 500.0, model="thin")
    assert at["ok"] is True
    assert math.isclose(at["safety_factor"], 1.0)
    # above
    above = pressure_vessel_check(p, ri, t, 501.0, model="thin")
    assert above["ok"] is True
    assert above["safety_factor"] > 1.0


def test_check_keys_and_model_roundtrip():
    r = pressure_vessel_check(3.5, 120.0, 4.0, 450.0, model="thick")
    assert r["model"] == "thick"
    assert "max_hoop" in r and "safety_factor" in r and "ok" in r
    assert isinstance(r["ok"], bool)


# --- input consumption (facade killer (a)) ---------------------------------------

def test_inputs_are_consumed_max_hoop_and_sf_change():
    """Different driving inputs produce observably different outputs (not a constant)."""
    base = pressure_vessel_check(10.0, 500.0, 10.0, 600.0, model="thin")
    higher_p = pressure_vessel_check(20.0, 500.0, 10.0, 600.0, model="thin")
    thinner = pressure_vessel_check(10.0, 500.0, 5.0, 600.0, model="thin")
    assert higher_p["max_hoop"] > base["max_hoop"]
    assert thinner["max_hoop"] > base["max_hoop"]
    # yield change affects only sf/ok, not max_hoop
    safer = pressure_vessel_check(10.0, 500.0, 10.0, 1200.0, model="thin")
    assert math.isclose(safer["max_hoop"], base["max_hoop"])
    assert safer["safety_factor"] == 2.0 * base["safety_factor"]


# --- negative / guard paths (facade killer (b) + "gate without test does not exist") ---

def test_geometryerror_on_non_positive_radius_or_thickness():
    with pytest.raises(GeometryError):
        thin_wall_cylinder(10.0, 0.0, 5.0)
    with pytest.raises(GeometryError):
        thin_wall_cylinder(10.0, -3.0, 5.0)
    with pytest.raises(GeometryError):
        thin_wall_sphere(10.0, 100.0, 0.0)
    with pytest.raises(GeometryError):
        thick_wall_cylinder_stresses(10.0, 0.0, 10.0, 5.0)  # r_inner <= 0
    with pytest.raises(GeometryError):
        pressure_vessel_check(10.0, 100.0, -1.0, 300.0)


def test_geometryerror_on_r_outer_le_r_inner():
    with pytest.raises(GeometryError):
        thick_wall_cylinder_stresses(10.0, 100.0, 100.0, 100.0)  # ==
    with pytest.raises(GeometryError):
        thick_wall_cylinder_stresses(10.0, 200.0, 50.0, 100.0)   # <


def test_geometryerror_on_evaluation_radius_outside_wall():
    with pytest.raises(GeometryError):
        thick_wall_cylinder_stresses(10.0, 100.0, 200.0, 99.9)   # < ri
    with pytest.raises(GeometryError):
        thick_wall_cylinder_stresses(10.0, 100.0, 200.0, 200.1)  # > ro


def test_geometryerror_on_unknown_model_string():
    with pytest.raises(GeometryError):
        pressure_vessel_check(10.0, 500.0, 10.0, 600.0, model="lamé")
    with pytest.raises(GeometryError):
        pressure_vessel_check(10.0, 500.0, 10.0, 600.0, model="medium")


def test_valueerror_on_non_positive_yield_strength():
    with pytest.raises(ValueError):
        pressure_vessel_check(10.0, 500.0, 10.0, 0.0)
    with pytest.raises(ValueError):
        pressure_vessel_check(10.0, 500.0, 10.0, -10.0)


# --- determinism (A5 contract) ---------------------------------------------------

def test_deterministic_outputs():
    a = thick_wall_cylinder_stresses(8.0, 80.0, 120.0, 95.0)
    b = thick_wall_cylinder_stresses(8.0, 80.0, 120.0, 95.0)
    assert a == b
    c1 = pressure_vessel_check(4.2, 150.0, 6.0, 380.0, model="thick")
    c2 = pressure_vessel_check(4.2, 150.0, 6.0, 380.0, model="thick")
    assert c1 == c2


# --- property-based invariants (Hypothesis) --------------------------------------

@settings(max_examples=60, deadline=None)
@given(
    p=st.floats(min_value=0.01, max_value=200.0),
    r=st.floats(min_value=5.0, max_value=2000.0),
    t=st.floats(min_value=0.05, max_value=300.0),
)
def test_property_thin_hoop_exactly_twice_axial(p, r, t):
    """For all positive p,r,t: hoop == 2 * axial (exact algebraic identity)."""
    res = thin_wall_cylinder(p, r, t)
    assert math.isclose(res["hoop_stress"], 2.0 * res["axial_stress"], rel_tol=1e-10)


@settings(max_examples=40, deadline=None)
@given(
    p=st.floats(min_value=0.01, max_value=100.0),
    r=st.floats(min_value=10.0, max_value=800.0),
    t=st.floats(min_value=0.1, max_value=100.0),
)
def test_property_sphere_is_exactly_half_cylinder(p, r, t):
    """Sphere stress is always exactly half the cylinder hoop for same p,r,t."""
    cyl_hoop = thin_wall_cylinder(p, r, t)["hoop_stress"]
    sph = thin_wall_sphere(p, r, t)
    assert math.isclose(sph, cyl_hoop / 2.0, rel_tol=1e-10)


@settings(max_examples=30, deadline=None)
@given(
    p=st.floats(min_value=0.1, max_value=50.0),
    ri=st.floats(min_value=10.0, max_value=500.0),
    tr=st.floats(min_value=0.001, max_value=0.5),
)
def test_property_lame_radial_bc_hold_at_boundaries(p, ri, tr):
    """Lame radial BCs hold exactly for any positive geometry (inner=-p, outer~0)."""
    ro = ri * (1.0 + tr)
    inner = thick_wall_cylinder_stresses(p, ri, ro, ri)
    outer = thick_wall_cylinder_stresses(p, ri, ro, ro)
    assert math.isclose(inner["radial_stress"], -p, rel_tol=1e-11, abs_tol=1e-11)
    assert abs(outer["radial_stress"]) < 1e-10


@settings(max_examples=30, deadline=None)
@given(
    p=st.floats(min_value=0.1, max_value=50.0),
    ri=st.floats(min_value=20.0, max_value=600.0),
    t=st.floats(min_value=0.2, max_value=200.0),
    y=st.floats(min_value=10.0, max_value=2000.0),
)
def test_property_thick_hoop_ge_thin_and_sf_ok_semantics(p, ri, t, y):
    """For positive inputs: thick.max_hoop >= thin.max_hoop; sf=y/max (or inf); ok iff sf>=1 or max<=0."""
    thin_r = pressure_vessel_check(p, ri, t, y, model="thin")
    thick_r = pressure_vessel_check(p, ri, t, y, model="thick")
    assert thick_r["max_hoop"] >= thin_r["max_hoop"] - 1e-12
    if thin_r["max_hoop"] > 0.0:
        sf = y / thin_r["max_hoop"]
        assert math.isclose(thin_r["safety_factor"], sf, rel_tol=1e-9)
        assert thin_r["ok"] == (sf >= 1.0)
    # thick is at least as conservative
    if thick_r["max_hoop"] > 0.0:
        assert thick_r["safety_factor"] <= thin_r["safety_factor"] + 1e-9


def test_check_ok_flips_exactly_at_yield_crossing():
    """ok flips from False->True exactly when yield crosses max_hoop (for positive pressure)."""
    p, ri, t = 5.0, 80.0, 2.5
    base_max = p * ri / t  # thin
    below = pressure_vessel_check(p, ri, t, base_max * 0.999, model="thin")
    at = pressure_vessel_check(p, ri, t, base_max, model="thin")
    above = pressure_vessel_check(p, ri, t, base_max * 1.001, model="thin")
    assert below["ok"] is False
    assert at["ok"] is True
    assert above["ok"] is True


# --- accepted documented edge: p<=0 (no guard, yields 'safe' no-stress) ----------
# Pins the p<=0 behavior explicitly (per finding) so it is not an unverified
# silent path. This is accepted per the public API contract: docstring lists
# guards only for r_inner/thickness (GeometryError) and yield_strength (ValueError);
# pressure has no guard because p<=0 corresponds to the no-burst (max_hoop<=0)
# special case already present for safety_factor/inf and ok=True.
# External/negative pressure is disclaimed in module docstring ("does NOT cover
# external pressure") but the math path accepts it without fabricating a value.
# Per L4 scoping + "change nothing if correct", we document+test rather than
# add a source guard (which would be blanket feature-creep).

def test_check_non_positive_pressure_is_accepted_no_stress_edge():
    """p<=0 produces max_hoop<=0, safety_factor=inf, ok=True (no error).
    This pins the behavior the char test previously left unexercised for <=0.
    """
    for p in (0.0, -0.1, -5.0):
        r = pressure_vessel_check(p, 500.0, 10.0, 600.0, model="thin")
        assert r["max_hoop"] <= 0.0
        assert r["safety_factor"] == float("inf")
        assert r["ok"] is True

        r2 = pressure_vessel_check(p, 500.0, 10.0, 600.0, model="thick")
        assert r2["max_hoop"] <= 0.0
        assert r2["safety_factor"] == float("inf")
        assert r2["ok"] is True
