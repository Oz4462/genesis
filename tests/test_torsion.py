"""Torsion of a circular shaft — the closed forms pinned to exact limits and anchors.

The surface shear stress of a solid shaft must equal BOTH 16*T/(pi*d**3) and T*(d/2)/J
with J = pi*d**4/32 (an algebraic identity), the hollow J must reduce to the solid J
when the bore is zero, and the twist must scale linearly with L and 1/G. Two
expressions of the same quantity agreeing to machine precision is the defense against
an error in either.

Offline, no LLM, pure math (no FEM, no mesher).

Run:  pytest tests/test_torsion.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import math  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from gen.torsion import (  # noqa: E402
    angle_of_twist,
    max_shaft_shear_stress,
    polar_moment_hollow,
    polar_moment_solid,
    shaft_torsion_check,
    torsional_shear_stress,
)


# --- the surface-stress identity (defense in depth) -----------------------------

def test_surface_stress_equals_16T_over_pi_d3_and_Tr_over_J():
    # T = 100000 N*mm on a d = 20 mm solid shaft -> tau = 63.66 MPa (concrete anchor)
    t, d = 100000.0, 20.0
    j = polar_moment_solid(d)
    via_formula = max_shaft_shear_stress(t, d)
    via_tr_over_j = torsional_shear_stress(t, d / 2.0, j)
    assert math.isclose(via_formula, via_tr_over_j, rel_tol=1e-12)   # the identity
    assert math.isclose(via_formula, 63.661977236758, rel_tol=1e-9)  # the anchor


def test_polar_moment_solid_anchor():
    # J = pi*d**4/32; d = 20 -> 15707.9632679...
    assert math.isclose(polar_moment_solid(20.0), 15707.963267948966, rel_tol=1e-12)


# --- hollow J reduces to solid J ------------------------------------------------

def test_hollow_reduces_to_solid_when_bore_is_zero():
    for d in (10.0, 20.0, 50.0):
        assert math.isclose(polar_moment_hollow(d, 0.0), polar_moment_solid(d), rel_tol=1e-12)


def test_hollow_removes_the_inner_core():
    # a hollow shaft is the solid outer minus the solid inner (superposition of J)
    big, bore = 40.0, 20.0
    expected = polar_moment_solid(big) - polar_moment_solid(bore)
    assert math.isclose(polar_moment_hollow(big, bore), expected, rel_tol=1e-12)
    # anchor: D=40, d=20 -> 235619.449...
    assert math.isclose(polar_moment_hollow(40.0, 20.0), 235619.44901923448, rel_tol=1e-12)


# --- the shear stress is linear in the radius -----------------------------------

def test_shear_stress_is_linear_in_radius():
    j = polar_moment_solid(20.0)
    assert torsional_shear_stress(100000.0, 0.0, j) == 0.0          # zero on the axis
    inner = torsional_shear_stress(100000.0, 5.0, j)
    outer = torsional_shear_stress(100000.0, 10.0, j)
    assert np.isclose(outer, 2.0 * inner)                          # doubles with radius


# --- the angle of twist scales linearly -----------------------------------------

def test_twist_scales_linearly_with_length_and_inverse_G():
    t, g, j = 100000.0, 80000.0, polar_moment_solid(20.0)
    base = angle_of_twist(t, 1000.0, g, j)
    assert np.isclose(angle_of_twist(t, 2000.0, g, j), 2.0 * base)  # linear in L
    assert np.isclose(angle_of_twist(t, 1000.0, 2.0 * g, j), 0.5 * base)  # linear in 1/G
    # anchor: T=100000, L=1000, G=80000, d=20 -> 0.0795775 rad (4.5595 deg)
    assert math.isclose(base, 0.07957747154594766, rel_tol=1e-12)


# --- the design check: shear vs strength governs --------------------------------

def test_check_reports_stress_twist_and_safety_factor():
    # shear_strength 100 MPa vs tau 63.66 MPa -> SF = 1.5708, ok
    r = shaft_torsion_check(100000.0, 20.0, 1000.0, 80000.0, shear_strength=100.0)
    assert math.isclose(r["max_shear"], 63.661977236758, rel_tol=1e-9)
    assert math.isclose(r["twist_angle"], 0.07957747154594766, rel_tol=1e-12)
    assert math.isclose(r["polar_moment"], 15707.963267948966, rel_tol=1e-12)
    assert math.isclose(r["safety_factor"], 100.0 / 63.661977236758, rel_tol=1e-9)
    assert r["ok"]


def test_check_flags_overload():
    safe = shaft_torsion_check(100000.0, 20.0, 1000.0, 80000.0, shear_strength=100.0)
    over = shaft_torsion_check(300000.0, 20.0, 1000.0, 80000.0, shear_strength=100.0)
    assert safe["ok"] and safe["safety_factor"] > 1.0
    assert not over["ok"] and over["safety_factor"] < 1.0           # 3x torque overloads


def test_check_is_deterministic():
    a = shaft_torsion_check(100000.0, 20.0, 1000.0, 80000.0, shear_strength=100.0)
    b = shaft_torsion_check(100000.0, 20.0, 1000.0, 80000.0, shear_strength=100.0)
    assert a == b


# --- guards: loud failure, never a guessed value --------------------------------

def test_guards_reject_impossible_geometry():
    with pytest.raises(ValueError):
        polar_moment_solid(0.0)
    with pytest.raises(ValueError):
        polar_moment_hollow(20.0, 20.0)          # bore not smaller than outer
    with pytest.raises(ValueError):
        polar_moment_hollow(20.0, 25.0)          # bore larger than outer
    with pytest.raises(ValueError):
        polar_moment_hollow(-1.0, 0.0)
    with pytest.raises(ValueError):
        torsional_shear_stress(100000.0, 5.0, 0.0)   # J must be positive
    with pytest.raises(ValueError):
        max_shaft_shear_stress(100000.0, 0.0)
    with pytest.raises(ValueError):
        angle_of_twist(100000.0, 1000.0, 0.0, 100.0)  # G must be positive
    with pytest.raises(ValueError):
        shaft_torsion_check(100000.0, 20.0, 1000.0, 80000.0, shear_strength=0.0)
