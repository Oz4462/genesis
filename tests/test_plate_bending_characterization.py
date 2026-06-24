"""Depth-audit (facade-killer) for plate_bending.py — Kirchhoff circular-plate forms.

The legacy tests/test_plate_bending.py pin the anchors directly; this file is the
INDEPENDENT facade-detector. It re-derives every closed form from first principles
inside the test (the flexural rigidity, both edge solutions, the clamped steel anchor)
and asserts the module agrees — so a hollowed-out module that returned a canned
constant, ignored an input, or silently mis-scaled would FAIL here.

Two things are proven for each formula:
  (a) the output CHANGES meaningfully and in the RIGHT way when a driving input
      changes (it is genuinely computed, not a frozen constant), and
  (b) the documented fail-loud guards fire EXACTLY (ValueError on every impossible
      input and on an unknown edge string) — "a gate without a test does not exist".

Property-based (Hypothesis) tests pin the invariants over a swept input space rather
than a single anchor: D ∝ t³, w ∝ R⁴ and ∝ 1/t³, the (5+ν)/(1+ν) softer-rim ratio,
and safety_factor = allowable/max_stress with the ok flag flipping across the boundary.

Offline, no LLM, pure math (no FEM, no mesher).

Run:  pytest tests/test_plate_bending_characterization.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402
from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from gen.plate_bending import (  # noqa: E402
    circular_plate_clamped,
    circular_plate_simply_supported,
    flexural_rigidity,
    plate_bending_check,
)

# the concrete steel anchor (q in MPa, R/t in mm, E in MPa) from the module docstring
_Q, _R, _T, _E, _NU = 0.1, 100.0, 5.0, 210000.0, 0.3


# Independent re-derivations of the closed forms (the "second opinion" the module
# must agree with — written out longhand so a copy of the module's own bug cannot hide).
def _ref_rigidity(e: float, t: float, nu: float) -> float:
    return e * t ** 3 / (12.0 * (1.0 - nu ** 2))


def _ref_clamped_w(q: float, r: float, t: float, e: float, nu: float) -> float:
    return q * r ** 4 / (64.0 * _ref_rigidity(e, t, nu))


def _ref_clamped_sigma(q: float, r: float, t: float) -> float:
    return 3.0 * q * r ** 2 / (4.0 * t ** 2)


def _ref_ss_w(q: float, r: float, t: float, e: float, nu: float) -> float:
    return (5.0 + nu) * q * r ** 4 / (64.0 * (1.0 + nu) * _ref_rigidity(e, t, nu))


# --- the clamped steel anchor: the headline numbers, recomputed ------------------

def test_clamped_anchor_matches_docstring_numbers():
    r = circular_plate_clamped(_Q, _R, _T, _E, _NU)
    # w_max = q*R^4/(64*D) -> 0.065 mm at the centre
    assert math.isclose(r["max_deflection"], 0.065, rel_tol=1e-12)
    # sigma_edge = 3*q*R^2/(4*t^2) = 3*0.1*1e4/100 -> 30.0 MPa at the edge
    assert math.isclose(r["max_stress"], 30.0, rel_tol=1e-12)
    # and it agrees with the independent re-derivation, not just the rounded anchor
    assert math.isclose(r["max_deflection"], _ref_clamped_w(_Q, _R, _T, _E, _NU),
                        rel_tol=1e-12)
    assert math.isclose(r["max_stress"], _ref_clamped_sigma(_Q, _R, _T), rel_tol=1e-12)


# --- a simply-supported plate is softer: deflects MORE, exact ratio --------------

def test_simply_supported_deflects_more_with_exact_ratio():
    cl = circular_plate_clamped(_Q, _R, _T, _E, _NU)
    ss = circular_plate_simply_supported(_Q, _R, _T, _E, _NU)
    assert ss["max_deflection"] > cl["max_deflection"]  # softer rim
    ratio = ss["max_deflection"] / cl["max_deflection"]
    # (5+nu)/(1+nu) = 5.3/1.3 = 4.0769... at nu=0.3
    assert math.isclose(ratio, (5.0 + _NU) / (1.0 + _NU), rel_tol=1e-12)
    assert math.isclose(ratio, 4.076923076923077, rel_tol=1e-12)


# --- the scaling laws are genuinely computed, not canned -------------------------

def test_rigidity_scales_as_thickness_cubed():
    base = flexural_rigidity(_E, _T, _NU)
    assert math.isclose(flexural_rigidity(_E, 2.0 * _T, _NU), 8.0 * base, rel_tol=1e-12)
    assert math.isclose(flexural_rigidity(_E, 3.0 * _T, _NU), 27.0 * base, rel_tol=1e-12)


def test_deflection_scales_as_R_fourth_and_inverse_t_cubed():
    base = circular_plate_clamped(_Q, _R, _T, _E, _NU)["max_deflection"]
    bigger_R = circular_plate_clamped(_Q, 2.0 * _R, _T, _E, _NU)["max_deflection"]
    thicker = circular_plate_clamped(_Q, _R, 2.0 * _T, _E, _NU)["max_deflection"]
    assert math.isclose(bigger_R / base, 16.0, rel_tol=1e-12)   # R^4
    assert math.isclose(thicker / base, 1.0 / 8.0, rel_tol=1e-12)  # 1/t^3


# --- the design check: safety_factor = allowable/max_stress, ok flips ------------

def test_check_safety_factor_definition_and_flip():
    # clamped anchor stress is 30 MPa; sweep the allowable across THAT exact stress.
    # Use the module's own computed stress as the boundary (it is 30.0+fp-epsilon),
    # so the >= boundary is tested exactly rather than against a rounded literal.
    stress = circular_plate_clamped(_Q, _R, _T, _E, _NU)["max_stress"]
    just_below = plate_bending_check(_Q, _R, _T, _E, _NU, stress * 0.99, edge="clamped")
    just_above = plate_bending_check(_Q, _R, _T, _E, _NU, stress * 1.01, edge="clamped")
    at_boundary = plate_bending_check(_Q, _R, _T, _E, _NU, stress, edge="clamped")
    assert math.isclose(just_above["safety_factor"], 1.01, rel_tol=1e-12)
    assert not just_below["ok"] and just_below["safety_factor"] < 1.0
    assert just_above["ok"] and just_above["safety_factor"] > 1.0
    assert at_boundary["ok"]  # ok = safety_factor >= 1 (boundary inclusive)


def test_check_edge_choice_changes_governing_stress():
    # The edge string genuinely selects a different formula (not ignored).
    cl = plate_bending_check(_Q, _R, _T, _E, _NU, 250.0, edge="clamped")
    ss = plate_bending_check(_Q, _R, _T, _E, _NU, 250.0, edge="simply_supported")
    assert cl["max_stress"] != ss["max_stress"]
    assert ss["max_stress"] > cl["max_stress"]            # 49.5 > 30.0
    assert ss["safety_factor"] < cl["safety_factor"]      # softer -> weaker


# --- NEGATIVE: every documented guard fails loud, never a guessed value ----------

def test_guards_reject_impossible_inputs():
    with pytest.raises(ValueError):
        flexural_rigidity(0.0, _T, _NU)                   # non-positive E
    with pytest.raises(ValueError):
        flexural_rigidity(-1.0, _T, _NU)
    with pytest.raises(ValueError):
        flexural_rigidity(_E, 0.0, _NU)                   # non-positive thickness
    with pytest.raises(ValueError):
        flexural_rigidity(_E, _T, 0.5)                    # nu at the open upper bound
    with pytest.raises(ValueError):
        flexural_rigidity(_E, _T, -1.0)                   # nu at the open lower bound
    with pytest.raises(ValueError):
        flexural_rigidity(_E, _T, 1.0)                    # nu well outside
    with pytest.raises(ValueError):
        circular_plate_clamped(_Q, 0.0, _T, _E, _NU)      # non-positive radius
    with pytest.raises(ValueError):
        circular_plate_clamped(_Q, _R, 0.0, _E, _NU)      # non-positive thickness
    with pytest.raises(ValueError):
        circular_plate_simply_supported(_Q, -1.0, _T, _E, _NU)
    with pytest.raises(ValueError):
        plate_bending_check(_Q, _R, _T, _E, _NU, 0.0)     # non-positive allowable
    with pytest.raises(ValueError):
        plate_bending_check(_Q, _R, _T, _E, _NU, -5.0)
    with pytest.raises(ValueError):
        plate_bending_check(_Q, _R, _T, _E, _NU, 250.0, edge="floating")  # unknown edge


# --- property-based: the invariants hold across a swept input space --------------

_pos = st.floats(min_value=1e-3, max_value=1e6, allow_nan=False, allow_infinity=False)
_nu = st.floats(min_value=-0.95, max_value=0.49, allow_nan=False, allow_infinity=False)


@settings(max_examples=200)
@given(q=_pos, r=_pos, t=_pos, e=_pos, nu=_nu)
def test_property_clamped_matches_independent_derivation(q, r, t, e, nu):
    out = circular_plate_clamped(q, r, t, e, nu)
    assert math.isclose(out["max_deflection"], _ref_clamped_w(q, r, t, e, nu),
                        rel_tol=1e-9)
    assert math.isclose(out["max_stress"], _ref_clamped_sigma(q, r, t), rel_tol=1e-9)
    assert out["max_deflection"] > 0.0 and out["max_stress"] > 0.0


@settings(max_examples=200)
@given(e=_pos, t=_pos, nu=_nu, k=st.floats(min_value=1.1, max_value=20.0))
def test_property_rigidity_is_cubic_in_thickness(e, t, nu, k):
    # D(k*t)/D(t) = k^3 exactly, independent of E and nu — proves t enters cubed.
    base = flexural_rigidity(e, t, nu)
    scaled = flexural_rigidity(e, k * t, nu)
    assert math.isclose(scaled / base, k ** 3, rel_tol=1e-9)


@settings(max_examples=200)
@given(q=_pos, r=_pos, t=_pos, e=_pos, nu=_nu)
def test_property_simply_supported_softer_by_exact_ratio(q, r, t, e, nu):
    cl = circular_plate_clamped(q, r, t, e, nu)["max_deflection"]
    ss = circular_plate_simply_supported(q, r, t, e, nu)["max_deflection"]
    # ratio is purely (5+nu)/(1+nu) > 1 for nu in (-1, 0.5) — a softer rim always.
    assert ss > cl
    assert math.isclose(ss / cl, (5.0 + nu) / (1.0 + nu), rel_tol=1e-9)


@settings(max_examples=200)
@given(
    q=_pos, r=_pos, t=_pos, e=_pos, nu=_nu,
    allowable=st.floats(min_value=1e-3, max_value=1e6),
)
def test_property_safety_factor_is_allowable_over_stress(q, r, t, e, nu, allowable):
    out = plate_bending_check(q, r, t, e, nu, allowable, edge="clamped")
    assert math.isclose(out["safety_factor"], allowable / out["max_stress"],
                        rel_tol=1e-9)
    assert out["ok"] == (out["safety_factor"] >= 1.0)
