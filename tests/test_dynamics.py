"""Dynamic robot axes — motion over a gait cycle, not one pose. Exact closed-form anchors:
the ZMP dynamic amplification 1 + (z/g)·ω², the swing torque peak |I·θ̈ + m·g·d·sinθ| that resolves
to I·A·ω² − m·g·d·sin A at ω·t = π/2 (sampled exactly), and the physical-pendulum period 2π√(I/mgd).
The dynamic terms are exactly what the STATIC robot screens omit, so fast stepping tips the ZMP and
a fast swing exceeds a hold-rated actuator. Every nonsense input raises.

Offline, no LLM. Run:  pytest tests/test_dynamics.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.dynamics import (  # noqa: E402
    STANDARD_GRAVITY,
    joint_swing_torque_check,
    pendulum_period,
    swing_resonance_check,
    zmp_dynamic_check,
)


def test_pendulum_period_is_the_physical_pendulum_closed_form():
    """T = 2π√(I/(m·g·d)); a point mass at L=1 reduces to 2π√(1/g) ≈ 2.0064 s."""
    assert pendulum_period(1.0, 1.0, 1.0) == pytest.approx(2.0 * math.pi * math.sqrt(1.0 / STANDARD_GRAVITY))
    assert pendulum_period(1.0, 1.0, 1.0) == pytest.approx(2.00644, rel=1e-4)


def test_swing_resonance_passes_below_natural_frequency_fails_above():
    """f_n ≈ 0.4984 Hz for the L=1 leg: a 0.4 Hz cadence rides the passive swing (ok), 0.6 Hz fights it."""
    slow = swing_resonance_check(1.0, 1.0, 1.0, step_frequency=0.4)
    assert slow["natural_frequency_hz"] == pytest.approx(0.49840, rel=1e-4)
    assert slow["ok"] and slow["safety_factor"] == pytest.approx(0.49840 / 0.4, rel=1e-4)
    assert not swing_resonance_check(1.0, 1.0, 1.0, step_frequency=0.6)["ok"]


def test_zmp_dynamic_amplification_tips_a_fast_step_a_slow_one_holds():
    """A 5 cm sway at z=0.9 m: at 1 Hz the dynamic factor 1+(z/g)(2π)² ≈ 4.623 throws the ZMP to
    ±23 cm — off a ±10 cm foot — while at 0.3 Hz it stays on. The static check cannot see this."""
    fast = zmp_dynamic_check(com_height=0.9, com_amplitude=0.05, step_frequency=1.0,
                             support_min_x=-0.10, support_max_x=0.10)
    expected_factor = 1.0 + (0.9 / STANDARD_GRAVITY) * (2.0 * math.pi) ** 2
    assert fast["dynamic_factor"] == pytest.approx(expected_factor)
    assert fast["zmp_excursion"] == pytest.approx(0.05 * expected_factor)
    assert not fast["ok"]
    assert fast["safety_factor"] == pytest.approx(0.10 / (0.05 * expected_factor))

    slow = zmp_dynamic_check(com_height=0.9, com_amplitude=0.05, step_frequency=0.3,
                             support_min_x=-0.10, support_max_x=0.10)
    assert slow["ok"] and slow["safety_factor"] > 1.0


def test_swing_torque_adds_the_inertial_term_the_hold_check_omits():
    """At 2 Hz the limb torque peaks at ω·t = π/2 (sampled exactly): |−I·A·ω² + m·g·d·sin A| =
    I·A·ω² − m·g·d·sin A. The inertial term I·A·ω² is the dynamic torque a static hold check ignores."""
    res = joint_swing_torque_check(inertia=0.1, mass=2.0, com_distance=0.2, amplitude_rad=0.3,
                                   step_frequency=2.0, available_torque=10.0)
    omega = 2.0 * math.pi * 2.0
    assert res["peak_inertial_torque"] == pytest.approx(0.1 * 0.3 * omega ** 2)
    assert res["peak_gravity_torque"] == pytest.approx(2.0 * STANDARD_GRAVITY * 0.2 * math.sin(0.3))
    # the global peak is at wt=pi/2 (an exactly-sampled point), where inertial and gravity oppose
    assert res["peak_required_torque"] == pytest.approx(
        res["peak_inertial_torque"] - res["peak_gravity_torque"], rel=1e-9)
    assert res["ok"] and res["safety_factor"] > 1.0


def test_a_hold_rated_actuator_fails_the_dynamic_swing():
    """A 2 N·m actuator (fine to HOLD the limb) cannot ACCELERATE it through the 2 Hz swing (~3.58 N·m
    peak): the dynamic check fails honestly where the static torque screen would have passed."""
    res = joint_swing_torque_check(inertia=0.1, mass=2.0, com_distance=0.2, amplitude_rad=0.3,
                                   step_frequency=2.0, available_torque=2.0)
    assert not res["ok"]
    assert res["peak_required_torque"] == pytest.approx(3.5782, rel=1e-3)


def test_nonsense_inputs_raise():
    with pytest.raises(ValueError):
        pendulum_period(0.0, 1.0, 1.0)                      # non-positive inertia
    with pytest.raises(ValueError):
        zmp_dynamic_check(0.9, 0.05, 1.0, 0.10, -0.10)      # inverted support polygon
    with pytest.raises(ValueError):
        zmp_dynamic_check(0.9, 0.05, 1.0, -0.10, 0.10, com_offset=0.5)  # offset outside support
    with pytest.raises(ValueError):
        joint_swing_torque_check(0.1, 2.0, 0.2, 4.0, 2.0, 10.0)         # amplitude > pi
    with pytest.raises(ValueError):
        joint_swing_torque_check(0.1, 2.0, 0.2, 0.3, 2.0, 10.0, n_samples=4)  # too few samples


# --- acceptance: a humanoid-leg Specification auto-fires the dynamic axes through the gate -------

from gen.core.state import Quantity, Specification, ValueOrigin  # noqa: E402
from gen.physics_selection import evaluate_spec_physics, select_physics_checks  # noqa: E402


def _q(qid: str, value: float, unit: str, measurand: str) -> Quantity:
    return Quantity(id=qid, name=qid, value=value, unit=unit,
                    origin=ValueOrigin.DECISION, rationale="x", measurand=measurand)


def _dyn_leg(step_frequency: float) -> Specification:
    """A walking humanoid leg: CoM sway + cadence, a swinging limb, an actuator capability."""
    qs = [
        _q("cx", 0.0, "m", "balance.com_x"), _q("ch", 0.9, "m", "balance.com_height"),
        _q("smin", -0.10, "m", "balance.support_min_x"), _q("smax", 0.10, "m", "balance.support_max_x"),
        _q("ca", 0.05, "m", "gait.com_amplitude"), _q("sf", step_frequency, "Hz", "gait.step_frequency"),
        _q("li", 0.1, "kg*m^2", "limb.inertia"), _q("lm", 2.0, "kg", "limb.mass"),
        _q("ld", 0.2, "m", "limb.com_distance"), _q("sa", 0.3, "rad", "swing.amplitude"),
        _q("at", 10.0, "N*m", "actuator.available_torque"),
    ]
    return Specification(run_id="dyn_leg", idea="walking humanoid leg", quantities=qs)


def test_dynamic_axes_auto_select_and_units_resolve():
    """The measurand tags alone select all three dynamic validators, and kg*m^2 / Hz / rad resolve
    (no gap) — the dynamic axes are wired into the same auto-selection as every other measurand."""
    checks, gaps = select_physics_checks(_dyn_leg(0.3))
    assert {"swing_resonance", "zmp_dynamic", "joint_swing_torque"} <= {c.validator for c in checks}
    assert gaps == []


def test_same_leg_walks_slow_ok_but_tips_when_it_steps_fast():
    """At 0.3 Hz the leg's ZMP stays under the foot and the swing torque fits — the gate passes. At
    1.0 Hz the SAME centred leg throws its ZMP off the foot: the gate fails on zmp_dynamic. This is
    the dynamic tip-over the static zmp_balance_check (CoM centred) cannot see."""
    slow = evaluate_spec_physics(_dyn_leg(0.3))
    assert slow["gate"].passed and slow["gaps"] == []
    fast = evaluate_spec_physics(_dyn_leg(1.0))
    assert not fast["gate"].passed
    assert any("zmp_dynamic" in f.detail for f in fast["gate"].failures)
