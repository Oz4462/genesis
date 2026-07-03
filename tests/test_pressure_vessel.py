"""Pressure-vessel wall stress — closed forms pinned to their exact limit cases.

The thin-wall hoop must be exactly twice the axial stress (why a pipe splits along
its length); the Lame thick-wall radial stress must hit its two boundary conditions
exactly (sigma_r(r_i) = -p_i, sigma_r(r_o) = 0); the thick-wall inner-wall hoop must
exceed the thin-wall estimate and converge to it as t/r -> 0; and the anchor
p=10 MPa, r=500 mm, t=10 mm must give hoop = 500 MPa.

Offline, no LLM, pure python.

Run:  pytest tests/test_pressure_vessel.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import math  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from gen.core.errors import GeometryError  # noqa: E402
from gen.pressure_vessel import (  # noqa: E402
    pressure_vessel_check,
    thick_wall_cylinder_stresses,
    thin_wall_cylinder,
    thin_wall_sphere,
)


# --- thin-wall membrane theory: the known anchor + the hoop=2*axial law ----------

def test_thin_cylinder_anchor():
    # p=10 MPa, r=500 mm, t=10 mm -> hoop = 500 MPa, axial = 250 MPa
    r = thin_wall_cylinder(10.0, 500.0, 10.0)
    assert math.isclose(r["hoop_stress"], 500.0)
    assert math.isclose(r["axial_stress"], 250.0)


def test_thin_cylinder_hoop_is_twice_axial():
    r = thin_wall_cylinder(7.3, 412.0, 9.1)        # arbitrary positive geometry
    assert math.isclose(r["hoop_stress"], 2.0 * r["axial_stress"])


def test_thin_sphere_is_half_cylinder_hoop():
    cyl = thin_wall_cylinder(10.0, 500.0, 10.0)["hoop_stress"]
    sph = thin_wall_sphere(10.0, 500.0, 10.0)
    assert math.isclose(sph, 250.0)
    assert math.isclose(sph, cyl / 2.0)


# --- Lame thick-wall: exact boundary conditions ----------------------------------

def test_lame_boundary_conditions_exact():
    p, ri, ro = 10.0, 100.0, 200.0
    inner = thick_wall_cylinder_stresses(p, ri, ro, ri)
    outer = thick_wall_cylinder_stresses(p, ri, ro, ro)
    assert math.isclose(inner["radial_stress"], -p)      # sigma_r(r_i) = -p_i
    assert abs(outer["radial_stress"]) < 1e-9            # sigma_r(r_o) = 0


def test_lame_hoop_max_at_inner_wall():
    p, ri, ro = 10.0, 100.0, 200.0
    hoops = [
        thick_wall_cylinder_stresses(p, ri, ro, r)["hoop_stress"]
        for r in np.linspace(ri, ro, 6)
    ]
    # hoop is strictly decreasing from inner to outer wall -> max at the inner wall
    assert all(earlier > later for earlier, later in zip(hoops, hoops[1:]))
    closed = p * (ro ** 2 + ri ** 2) / (ro ** 2 - ri ** 2)
    assert math.isclose(hoops[0], closed)                # 16.6667 MPa here


# --- thick exceeds thin and the two converge as t/r -> 0 -------------------------

def test_thick_hoop_higher_than_thin_estimate():
    p = 10.0
    for ri, t in [(500.0, 10.0), (100.0, 100.0)]:
        ro = ri + t
        thick = thick_wall_cylinder_stresses(p, ri, ro, ri)["hoop_stress"]
        thin = p * ri / t
        assert thick > thin                              # Lame inner hoop is larger


def test_thin_case_gap_is_one_percent():
    # t/r = 0.02 -> Lame hoop ~1.01% above the thin-wall membrane estimate
    p, ri, t = 10.0, 500.0, 10.0
    ro = ri + t
    thick = thick_wall_cylinder_stresses(p, ri, ro, ri)["hoop_stress"]
    thin = p * ri / t
    gap = 100.0 * (thick - thin) / thin
    assert math.isclose(gap, 1.0099009900990099, rel_tol=1e-9)


def test_thick_case_gap_is_large():
    # t/r = 1.0 -> Lame hoop is 66.67% above the thin-wall estimate (thin is unsafe)
    p, ri, t = 10.0, 100.0, 100.0
    ro = ri + t
    thick = thick_wall_cylinder_stresses(p, ri, ro, ri)["hoop_stress"]
    thin = p * ri / t
    gap = 100.0 * (thick - thin) / thin
    assert math.isclose(gap, 200.0 / 3.0, rel_tol=1e-9)


def test_thin_thick_converge_as_wall_gets_thin():
    p, ri = 1000.0, 1000.0
    gaps = []
    for tr in [0.5, 0.1, 0.05, 0.01, 0.001]:
        ro = ri * (1.0 + tr)
        t = ro - ri
        thick = thick_wall_cylinder_stresses(p, ri, ro, ri)["hoop_stress"]
        thin = p * ri / t
        gaps.append(100.0 * (thick - thin) / thin)
    # the percentage gap shrinks monotonically toward zero as t/r -> 0
    assert all(earlier > later for earlier, later in zip(gaps, gaps[1:]))
    assert gaps[-1] < 0.06                                # < 0.06% at t/r = 0.001


# --- the design check ------------------------------------------------------------

def test_check_thin_anchor_governs_at_half():
    # 500 MPa hoop vs 250 MPa yield -> safety_factor = 0.5, not ok
    r = pressure_vessel_check(10.0, 500.0, 10.0, 250.0, model="thin")
    assert math.isclose(r["max_hoop"], 500.0)
    assert math.isclose(r["safety_factor"], 0.5)
    assert not r["ok"]


def test_check_safe_when_yield_exceeds_hoop():
    r = pressure_vessel_check(10.0, 500.0, 10.0, 600.0, model="thin")
    assert r["ok"] and r["safety_factor"] > 1.0


def test_check_thick_is_more_conservative_than_thin():
    thin = pressure_vessel_check(10.0, 500.0, 10.0, 250.0, model="thin")
    thick = pressure_vessel_check(10.0, 500.0, 10.0, 250.0, model="thick")
    assert thick["max_hoop"] > thin["max_hoop"]          # Lame inner hoop is larger
    assert thick["safety_factor"] < thin["safety_factor"]


# --- guards & determinism --------------------------------------------------------

def test_geometry_guards():
    with pytest.raises(GeometryError):
        thin_wall_cylinder(10.0, 0.0, 10.0)
    with pytest.raises(GeometryError):
        thin_wall_sphere(10.0, 500.0, -1.0)
    with pytest.raises(GeometryError):
        thick_wall_cylinder_stresses(10.0, 200.0, 100.0, 150.0)   # r_o <= r_i
    with pytest.raises(GeometryError):
        thick_wall_cylinder_stresses(10.0, 100.0, 200.0, 250.0)   # r outside wall


def test_check_guards():
    with pytest.raises(GeometryError):
        pressure_vessel_check(10.0, 500.0, 10.0, 250.0, model="medium")
    with pytest.raises(ValueError):
        pressure_vessel_check(10.0, 500.0, 10.0, 0.0)
    with pytest.raises(GeometryError):
        pressure_vessel_check(10.0, -1.0, 10.0, 250.0)


def test_is_deterministic():
    a = thick_wall_cylinder_stresses(10.0, 100.0, 200.0, 150.0)
    b = thick_wall_cylinder_stresses(10.0, 100.0, 200.0, 150.0)
    assert a == b
