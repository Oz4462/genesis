"""Plate bending — the Kirchhoff closed forms pinned to exact limits and anchors.

A simply-supported circular plate must deflect MORE than a clamped one of identical
geometry (a softer rim): the ratio is exactly (5+nu)/(1+nu). The flexural rigidity D
must scale as t**3, the deflection as R**4 and as 1/t**3, and the concrete steel
anchor (q=0.1 MPa, R=100 mm, t=5 mm, E=210000, nu=0.3) must give, clamped,
w_max = 0.065 mm and sigma_max = 30.0 MPa. Each closed form is checked against a
limit it must obey, the defense against an error in the algebra.

Offline, no LLM, pure math (no FEM, no mesher).

Run:  pytest tests/test_plate_bending.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import math  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from gen.plate_bending import (  # noqa: E402
    circular_plate_clamped,
    circular_plate_simply_supported,
    flexural_rigidity,
    plate_bending_check,
)

# the concrete steel anchor (q in MPa, R/t in mm, E in MPa)
_Q, _R, _T, _E, _NU = 0.1, 100.0, 5.0, 210000.0, 0.3


# --- the flexural rigidity D = E*t^3/(12*(1-nu^2)) ------------------------------

def test_flexural_rigidity_anchor():
    # D = 210000 * 5^3 / (12 * (1 - 0.09)) = 2403846.153846...
    assert math.isclose(
        flexural_rigidity(_E, _T, _NU), 2403846.153846154, rel_tol=1e-12
    )


def test_rigidity_scales_as_thickness_cubed():
    base = flexural_rigidity(_E, _T, _NU)
    assert np.isclose(flexural_rigidity(_E, 2.0 * _T, _NU), 8.0 * base)   # t^3
    assert np.isclose(flexural_rigidity(_E, 3.0 * _T, _NU), 27.0 * base)


# --- the clamped-edge anchor (defense in depth) ---------------------------------

def test_clamped_anchor_deflection_and_stress():
    r = circular_plate_clamped(_Q, _R, _T, _E, _NU)
    # w_max = q*R^4 / (64*D) = 0.1*1e8 / (64*2403846.15) = 0.065 mm (centre)
    assert math.isclose(r["max_deflection"], 0.065, rel_tol=1e-12)
    # sigma_edge = 3*q*R^2 / (4*t^2) = 3*0.1*1e4 / 100 = 30.0 MPa (edge)
    assert math.isclose(r["max_stress"], 30.0, rel_tol=1e-12)
    assert r["max_deflection"] > 0.0 and r["max_stress"] > 0.0   # positive, finite
    assert math.isfinite(r["max_deflection"]) and math.isfinite(r["max_stress"])


def test_simply_supported_anchor():
    r = circular_plate_simply_supported(_Q, _R, _T, _E, _NU)
    # w_max = (5+nu)*q*R^4 / (64*(1+nu)*D) = 5.3/1.3 * 0.065 = 0.265 mm
    assert math.isclose(r["max_deflection"], 0.265, rel_tol=1e-12)
    # sigma_center = 3*(3+nu)*q*R^2 / (8*t^2) = 3*3.3*0.1*1e4 / 200 = 49.5 MPa
    assert math.isclose(r["max_stress"], 49.5, rel_tol=1e-12)


# --- a simply-supported plate deflects MORE than a clamped one ------------------

def test_simply_supported_deflects_more_than_clamped():
    cl = circular_plate_clamped(_Q, _R, _T, _E, _NU)
    ss = circular_plate_simply_supported(_Q, _R, _T, _E, _NU)
    assert ss["max_deflection"] > cl["max_deflection"]            # softer rim
    # the ratio is exactly (5+nu)/(1+nu) — 4.0769... at nu=0.3
    ratio = ss["max_deflection"] / cl["max_deflection"]
    assert math.isclose(ratio, (5.0 + _NU) / (1.0 + _NU), rel_tol=1e-12)
    assert math.isclose(ratio, 5.3 / 1.3, rel_tol=1e-12)


# --- the deflection scales as R^4 and as 1/t^3 ----------------------------------

def test_deflection_scales_as_R_fourth():
    base = circular_plate_clamped(_Q, _R, _T, _E, _NU)["max_deflection"]
    doubled = circular_plate_clamped(_Q, 2.0 * _R, _T, _E, _NU)["max_deflection"]
    assert np.isclose(doubled / base, 16.0)                      # R^4


def test_deflection_scales_as_inverse_t_cubed():
    base = circular_plate_clamped(_Q, _R, _T, _E, _NU)["max_deflection"]
    thicker = circular_plate_clamped(_Q, _R, 2.0 * _T, _E, _NU)["max_deflection"]
    assert np.isclose(thicker / base, 1.0 / 8.0)                 # 1/t^3


def test_stress_scales_as_R_squared_over_t_squared():
    base = circular_plate_clamped(_Q, _R, _T, _E, _NU)["max_stress"]
    bigger = circular_plate_clamped(_Q, 2.0 * _R, _T, _E, _NU)["max_stress"]
    assert np.isclose(bigger / base, 4.0)                        # (2R)^2
    thicker = circular_plate_clamped(_Q, _R, 2.0 * _T, _E, _NU)["max_stress"]
    assert np.isclose(thicker / base, 0.25)                      # 1/(2t)^2


# --- the design check: bending stress vs allowable governs ----------------------

def test_check_reports_deflection_stress_and_safety_factor():
    # clamped anchor: sigma 30 MPa vs allowable 250 -> SF = 8.333, ok
    r = plate_bending_check(_Q, _R, _T, _E, _NU, 250.0, edge="clamped")
    assert math.isclose(r["max_deflection"], 0.065, rel_tol=1e-12)
    assert math.isclose(r["max_stress"], 30.0, rel_tol=1e-12)
    assert math.isclose(r["safety_factor"], 250.0 / 30.0, rel_tol=1e-12)
    assert r["ok"]


def test_check_simply_supported_is_weaker_than_clamped():
    # same geometry & allowable: the simply-supported plate has the lower SF
    cl = plate_bending_check(_Q, _R, _T, _E, _NU, 250.0, edge="clamped")
    ss = plate_bending_check(_Q, _R, _T, _E, _NU, 250.0, edge="simply_supported")
    assert ss["safety_factor"] < cl["safety_factor"]
    assert ss["max_stress"] > cl["max_stress"]                   # 49.5 > 30.0


def test_check_flags_overload():
    safe = plate_bending_check(_Q, _R, _T, _E, _NU, 250.0, edge="clamped")
    over = plate_bending_check(1.0, _R, _T, _E, _NU, 250.0, edge="clamped")
    assert safe["ok"] and safe["safety_factor"] > 1.0
    assert not over["ok"] and over["safety_factor"] < 1.0        # 10x pressure overloads


def test_check_is_deterministic():
    a = plate_bending_check(_Q, _R, _T, _E, _NU, 250.0, edge="clamped")
    b = plate_bending_check(_Q, _R, _T, _E, _NU, 250.0, edge="clamped")
    assert a == b


# --- guards: loud failure, never a guessed value --------------------------------

def test_guards_reject_impossible_inputs():
    with pytest.raises(ValueError):
        flexural_rigidity(0.0, _T, _NU)              # E must be positive
    with pytest.raises(ValueError):
        flexural_rigidity(_E, 0.0, _NU)              # thickness must be positive
    with pytest.raises(ValueError):
        flexural_rigidity(_E, _T, 0.5)               # nu out of (-1, 0.5)
    with pytest.raises(ValueError):
        flexural_rigidity(_E, _T, 1.0)
    with pytest.raises(ValueError):
        circular_plate_clamped(_Q, 0.0, _T, _E, _NU)
    with pytest.raises(ValueError):
        circular_plate_simply_supported(_Q, _R, 0.0, _E, _NU)
    with pytest.raises(ValueError):
        plate_bending_check(_Q, _R, _T, _E, _NU, 0.0)            # allowable positive
    with pytest.raises(ValueError):
        plate_bending_check(_Q, _R, _T, _E, _NU, 250.0, edge="floating")
