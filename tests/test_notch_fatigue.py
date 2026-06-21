"""Notch fatigue — Peterson q and K_f pinned to exact limits and a concrete anchor.

The fatigue notch factor K_f must reduce to its exact limits (q -> 1 so K_f -> K_t for a
blunt notch, q -> 0 so K_f -> 1 for a sharp tiny notch), stay strictly between 1 and K_t
for any finite radius, and hit the textbook anchor K_t=3, r=1 mm, a=0.25 mm -> q=0.8,
K_f=2.6, Se_notched=Se/2.6. Two independent limits bracketing K_f is the defense against
an error in the empirical form. Offline, no LLM, pure python.

Run:  pytest tests/test_notch_fatigue.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.notch_fatigue import (  # noqa: E402
    fatigue_notch_factor,
    notch_endurance_limit,
    notch_fatigue_check,
    notch_sensitivity,
)


# --- the concrete textbook anchor ----------------------------------------------

def test_anchor_kt3_r1_a025():
    # Kt=3, r=1 mm, a=0.25 mm -> q=0.8, K_f=2.6 (Shigley ch.6 worked form)
    assert math.isclose(notch_sensitivity(1.0, 0.25), 0.8, rel_tol=1e-12)
    assert math.isclose(fatigue_notch_factor(3.0, 1.0, 0.25), 2.6, rel_tol=1e-12)
    # Se_notched = Se / 2.6
    assert math.isclose(notch_endurance_limit(200.0, 2.6), 200.0 / 2.6, rel_tol=1e-12)


# --- the limit cases bracketing K_f between 1 and K_t ---------------------------

def test_blunt_notch_q_to_one_kf_to_kt():
    # a/r -> 0 (huge radius): q -> 1, K_f -> K_t (full static concentration felt)
    kt = 3.0
    q = notch_sensitivity(1.0e6, 0.25)
    kf = fatigue_notch_factor(kt, 1.0e6, 0.25)
    assert q > 0.9999
    assert math.isclose(kf, kt, rel_tol=1e-5)


def test_sharp_tiny_notch_q_to_zero_kf_to_one():
    # a/r -> inf (tiny radius): q -> 0, K_f -> 1 (notch barely matters to fatigue)
    q = notch_sensitivity(1.0e-6, 0.25)
    kf = fatigue_notch_factor(3.0, 1.0e-6, 0.25)
    assert q < 1.0e-4
    assert math.isclose(kf, 1.0, rel_tol=1e-4)


def test_kf_strictly_between_one_and_kt_for_finite_radius():
    kt = 3.0
    for r in (0.1, 0.5, 1.0, 2.0, 5.0):
        kf = fatigue_notch_factor(kt, r, 0.25)
        assert 1.0 < kf < kt
    # blunter notch -> larger K_f (closer to K_t)
    assert fatigue_notch_factor(kt, 5.0, 0.25) > fatigue_notch_factor(kt, 0.5, 0.25)


def test_q_is_monotonic_in_radius():
    # blunter (larger r) -> higher sensitivity q
    assert notch_sensitivity(5.0, 0.25) > notch_sensitivity(1.0, 0.25)
    assert notch_sensitivity(1.0, 0.25) > notch_sensitivity(0.2, 0.25)
    assert 0.0 < notch_sensitivity(1.0, 0.25) < 1.0


# --- the design check: local effective stress vs endurance ----------------------

def test_check_reports_kf_q_and_safety_factor():
    # Se=200, nominal=50: local eff = 2.6*50 = 130, SF = 200/130 = 1.5385, ok
    r = notch_fatigue_check(50.0, kt=3.0, notch_radius=1.0,
                            peterson_constant_a=0.25, smooth_endurance_se=200.0)
    assert math.isclose(r["q"], 0.8, rel_tol=1e-12)
    assert math.isclose(r["kf"], 2.6, rel_tol=1e-12)
    assert math.isclose(r["se_notched"], 200.0 / 2.6, rel_tol=1e-12)
    assert math.isclose(r["local_effective_stress"], 130.0, rel_tol=1e-12)
    assert math.isclose(r["safety_factor"], 200.0 / 130.0, rel_tol=1e-12)
    assert r["ok"]


def test_check_safety_factor_equals_se_notched_over_nominal():
    # SF = Se/(Kf*nominal) is identically Se_notched/nominal (an algebraic identity)
    r = notch_fatigue_check(50.0, kt=3.0, notch_radius=1.0,
                            peterson_constant_a=0.25, smooth_endurance_se=200.0)
    assert math.isclose(r["safety_factor"], r["se_notched"] / 50.0, rel_tol=1e-12)


def test_check_flags_overload():
    safe = notch_fatigue_check(50.0, kt=3.0, notch_radius=1.0,
                               peterson_constant_a=0.25, smooth_endurance_se=200.0)
    over = notch_fatigue_check(120.0, kt=3.0, notch_radius=1.0,
                               peterson_constant_a=0.25, smooth_endurance_se=200.0)
    assert safe["ok"] and safe["safety_factor"] > 1.0
    # 120 MPa nominal -> 312 MPa local > 200 MPa endurance -> fails
    assert not over["ok"] and over["safety_factor"] < 1.0


def test_check_is_deterministic():
    a = notch_fatigue_check(50.0, kt=3.0, notch_radius=1.0,
                            peterson_constant_a=0.25, smooth_endurance_se=200.0)
    b = notch_fatigue_check(50.0, kt=3.0, notch_radius=1.0,
                            peterson_constant_a=0.25, smooth_endurance_se=200.0)
    assert a == b


# --- guards: loud failure, never a guessed value --------------------------------

def test_guards_reject_impossible_input():
    with pytest.raises(ValueError):
        notch_sensitivity(0.0, 0.25)                 # radius must be positive
    with pytest.raises(ValueError):
        notch_sensitivity(1.0, -0.1)                 # a must be non-negative
    with pytest.raises(ValueError):
        fatigue_notch_factor(0.5, 1.0, 0.25)         # K_t must be >= 1
    with pytest.raises(ValueError):
        notch_endurance_limit(0.0, 2.6)              # Se must be positive
    with pytest.raises(ValueError):
        notch_endurance_limit(200.0, 0.9)            # K_f must be >= 1
    with pytest.raises(ValueError):
        notch_fatigue_check(0.0, kt=3.0, notch_radius=1.0,
                            peterson_constant_a=0.25, smooth_endurance_se=200.0)
