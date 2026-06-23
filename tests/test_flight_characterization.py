"""Depth-audit characterization tests for ``src/gen/flight.py``.

These tests are *facade-killers*: for each of the four closed-form validators
they (a) prove the headline claim REALLY holds against an independent closed-form
or hand-computed anchor and that the output changes meaningfully when a driving
input changes (the input is consumed, not canned), and (b) fire the documented
fail-loud guard exactly. Property-based tests pin the algebraic identities and
monotonicity invariants across the input space.

The confirmed real defect under audit: ``rotor_hover_check`` documents "Raises
ValueError on ... a negative thrust" but ``max_total_thrust`` was never validated,
so a negative thrust silently produced a negative thrust-to-weight ratio. The
guard is now in place; ``test_rotor_hover_negative_thrust_raises`` is the
regression that pins it.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402
from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from gen.flight import (  # noqa: E402
    AIR_DENSITY_SEA_LEVEL,
    STANDARD_GRAVITY,
    attitude_pd_check,
    battery_endurance_check,
    current_budget_check,
    ideal_induced_power,
    induced_velocity,
    rotor_hover_check,
)


# --------------------------------------------------------------------------- #
# induced_velocity / ideal_induced_power — momentum-theory primitives
# --------------------------------------------------------------------------- #

def test_induced_velocity_matches_closed_form():
    """v_i = sqrt(T/(2·ρ·A)) — anchored against an independent hand computation."""
    thrust, area, rho = 40.0, 0.2, 1.225
    expected = math.sqrt(thrust / (2.0 * rho * area))
    assert induced_velocity(thrust, area, rho) == pytest.approx(expected)


def test_ideal_induced_power_identity_pinned():
    """P_ideal ≡ T·v_i ≡ T^(3/2)/sqrt(2·ρ·A) to machine precision (the docstring
    promise that the two algebraic forms are identical)."""
    thrust, area, rho = 25.0, 0.15, 1.1
    v_i = induced_velocity(thrust, area, rho)
    closed_form = thrust ** 1.5 / math.sqrt(2.0 * rho * area)
    assert ideal_induced_power(thrust, area, rho) == pytest.approx(thrust * v_i)
    assert ideal_induced_power(thrust, area, rho) == pytest.approx(closed_form)


@given(
    thrust=st.floats(min_value=0.0, max_value=1e4),
    area=st.floats(min_value=1e-3, max_value=10.0),
    rho=st.floats(min_value=0.1, max_value=2.0),
)
def test_induced_power_identity_property(thrust, area, rho):
    """The T·v_i ≡ T^1.5/sqrt(2ρA) identity holds for ALL valid inputs."""
    closed_form = thrust ** 1.5 / math.sqrt(2.0 * rho * area)
    assert ideal_induced_power(thrust, area, rho) == pytest.approx(closed_form, rel=1e-9, abs=1e-12)


def test_induced_velocity_guards():
    with pytest.raises(ValueError):
        induced_velocity(10.0, 0.0)          # non-positive disk area
    with pytest.raises(ValueError):
        induced_velocity(10.0, 0.2, 0.0)     # non-positive density
    with pytest.raises(ValueError):
        induced_velocity(-1.0, 0.2)          # negative thrust


# --------------------------------------------------------------------------- #
# rotor_hover_check — the lift + control-margin screen (THE FIXED MODULE)
# --------------------------------------------------------------------------- #

def test_rotor_hover_headline_against_closed_form():
    """T/W ratio, hover power and safety factor recomputed from scratch."""
    mass, area, n, max_thrust, fm = 1.5, 0.05, 4.0, 60.0, 0.6
    res = rotor_hover_check(mass, area, n, max_thrust, figure_of_merit=fm)

    weight = mass * STANDARD_GRAVITY
    assert res["weight_n"] == pytest.approx(weight)
    assert res["thrust_weight_ratio"] == pytest.approx(max_thrust / weight)

    per_rotor = weight / n
    v_i = math.sqrt(per_rotor / (2.0 * AIR_DENSITY_SEA_LEVEL * area))
    assert res["induced_velocity"] == pytest.approx(v_i)
    p_hover = n * per_rotor * v_i / fm
    assert res["hover_power_w"] == pytest.approx(p_hover)
    assert res["safety_factor"] == pytest.approx((max_thrust / weight) / 2.0)
    # T/W = 60 / (1.5·g) ≈ 4.08 ≥ 2 → passes
    assert res["ok"] is True


def test_rotor_hover_input_is_consumed():
    """Driving inputs genuinely change the output (not a canned constant):
    more thrust raises the ratio; a smaller disk raises induced velocity and
    hover power (v_i ∝ 1/sqrt(A))."""
    base = rotor_hover_check(1.0, 0.05, 4.0, 40.0)
    more_thrust = rotor_hover_check(1.0, 0.05, 4.0, 50.0)
    assert more_thrust["thrust_weight_ratio"] > base["thrust_weight_ratio"]

    smaller_disk = rotor_hover_check(1.0, 0.02, 4.0, 40.0)
    assert smaller_disk["induced_velocity"] > base["induced_velocity"]
    assert smaller_disk["hover_power_w"] > base["hover_power_w"]


def test_rotor_hover_thrust_weight_gate_flips():
    """The T/W ≥ 2 gate honestly flips on the boundary-driving input."""
    weight = 1.0 * STANDARD_GRAVITY
    just_below = rotor_hover_check(1.0, 0.05, 4.0, 2.0 * weight - 0.1)
    just_above = rotor_hover_check(1.0, 0.05, 4.0, 2.0 * weight + 0.1)
    assert just_below["ok"] is False
    assert just_above["ok"] is True


def test_rotor_hover_zero_thrust_is_evaluable():
    """0.0 thrust is a meaningful evaluable case (ratio 0, ok False), NOT an error
    — matching the documented allowance."""
    res = rotor_hover_check(1.0, 0.05, 4.0, 0.0)
    assert res["thrust_weight_ratio"] == 0.0
    assert res["safety_factor"] == 0.0
    assert res["ok"] is False


def test_rotor_hover_negative_thrust_raises():
    """REGRESSION for the fixed defect: a negative max_total_thrust must fail loud
    rather than silently yield a negative thrust-to-weight ratio."""
    with pytest.raises(ValueError):
        rotor_hover_check(1.0, 0.05, 4.0, -10.0)


def test_rotor_hover_other_guards():
    with pytest.raises(ValueError):
        rotor_hover_check(0.0, 0.05, 4.0, 40.0)            # non-positive mass
    with pytest.raises(ValueError):
        rotor_hover_check(1.0, 0.05, 0.0, 40.0)            # rotor count < 1
    with pytest.raises(ValueError):
        rotor_hover_check(1.0, 0.0, 4.0, 40.0)             # non-positive disk area
    with pytest.raises(ValueError):
        rotor_hover_check(1.0, 0.05, 4.0, 40.0, figure_of_merit=1.5)   # FM > 1
    with pytest.raises(ValueError):
        rotor_hover_check(1.0, 0.05, 4.0, 40.0, figure_of_merit=0.0)   # FM ≤ 0
    with pytest.raises(ValueError):
        rotor_hover_check(1.0, 0.05, 4.0, 40.0, min_thrust_weight=0.0)  # band ≤ 0


@given(max_thrust=st.floats(min_value=-1e4, max_value=-1e-6))
def test_rotor_hover_any_negative_thrust_raises(max_thrust):
    """Property: the guard fires for the WHOLE negative half-line, never a
    silent negative ratio."""
    with pytest.raises(ValueError):
        rotor_hover_check(1.0, 0.05, 4.0, max_thrust)


# --------------------------------------------------------------------------- #
# battery_endurance_check — energy budget
# --------------------------------------------------------------------------- #

def test_battery_endurance_against_closed_form():
    """endurance[min] = capacity·usable / power · 60; hand-computed anchor."""
    cap, power, req, usable = 100.0, 200.0, 10.0, 0.8
    res = battery_endurance_check(cap, power, req, usable_fraction=usable)
    # usable = 80 Wh; endurance = 80/200·60 = 24 min
    assert res["usable_wh"] == pytest.approx(80.0)
    assert res["endurance_min"] == pytest.approx(24.0)
    assert res["safety_factor"] == pytest.approx(24.0 / 10.0)
    assert res["ok"] is True


def test_battery_endurance_input_is_consumed():
    """More power → less endurance; more capacity → more endurance."""
    base = battery_endurance_check(100.0, 200.0, 10.0)
    more_power = battery_endurance_check(100.0, 400.0, 10.0)
    more_cap = battery_endurance_check(200.0, 200.0, 10.0)
    assert more_power["endurance_min"] < base["endurance_min"]
    assert more_cap["endurance_min"] > base["endurance_min"]


def test_battery_endurance_gate_flips():
    res_fail = battery_endurance_check(100.0, 200.0, 30.0)   # need 30 min, have 24
    assert res_fail["ok"] is False
    res_pass = battery_endurance_check(100.0, 200.0, 20.0)
    assert res_pass["ok"] is True


def test_battery_endurance_guards():
    with pytest.raises(ValueError):
        battery_endurance_check(0.0, 200.0, 10.0)        # capacity
    with pytest.raises(ValueError):
        battery_endurance_check(100.0, 0.0, 10.0)        # power
    with pytest.raises(ValueError):
        battery_endurance_check(100.0, 200.0, 0.0)       # required time
    with pytest.raises(ValueError):
        battery_endurance_check(100.0, 200.0, 10.0, usable_fraction=1.5)  # fraction > 1
    with pytest.raises(ValueError):
        battery_endurance_check(100.0, 200.0, 10.0, usable_fraction=0.0)  # fraction ≤ 0


# --------------------------------------------------------------------------- #
# current_budget_check — electric brownout budget
# --------------------------------------------------------------------------- #

def test_current_budget_against_closed_form():
    """I = P/V; battery_max = C·Ah; safety_factor = min(ESC, battery) margin."""
    # I = 444/22.2 = 20 A; battery_max = 30·5 = 150 A → sf_batt = 7.5
    # ESC limit 40 A → sf_esc = 2.0 → the ESC is the binding margin.
    res = current_budget_check(444.0, 22.2, 40.0, 5.0, 30.0)
    assert res["current_a"] == pytest.approx(20.0)
    assert res["battery_max_a"] == pytest.approx(150.0)
    assert res["safety_factor"] == pytest.approx(2.0)   # min(2.0, 7.5)
    assert res["ok"] is True


def test_current_budget_battery_binds_when_smaller():
    """The SMALLER margin (the one that browns out first) is reported — here the
    battery, proving min() actually selects the binding constraint."""
    # I = 20 A; ESC 100 A (sf 5.0); battery 1 Ah · 30C = 30 A (sf 1.5) → battery binds
    res = current_budget_check(444.0, 22.2, 100.0, 1.0, 30.0)
    assert res["safety_factor"] == pytest.approx(1.5)
    assert res["ok"] is True


def test_current_budget_gate_fails_on_brownout():
    # I = 40 A, ESC 30 A → sf_esc = 0.75 < 1 → fails
    res = current_budget_check(888.0, 22.2, 30.0, 5.0, 30.0)
    assert res["current_a"] == pytest.approx(40.0)
    assert res["safety_factor"] < 1.0
    assert res["ok"] is False


def test_current_budget_guards():
    with pytest.raises(ValueError):
        current_budget_check(0.0, 22.2, 40.0, 5.0, 30.0)     # power
    with pytest.raises(ValueError):
        current_budget_check(444.0, 0.0, 40.0, 5.0, 30.0)    # voltage
    with pytest.raises(ValueError):
        current_budget_check(444.0, 22.2, 0.0, 5.0, 30.0)    # ESC limit
    with pytest.raises(ValueError):
        current_budget_check(444.0, 22.2, 40.0, 0.0, 30.0)   # capacity
    with pytest.raises(ValueError):
        current_budget_check(444.0, 22.2, 40.0, 5.0, 0.0)    # C-rating


# --------------------------------------------------------------------------- #
# attitude_pd_check — 2nd-order damping band
# --------------------------------------------------------------------------- #

def test_attitude_pd_against_closed_form():
    """ωn = sqrt(Kp/I), ζ = Kd/(2·sqrt(Kp·I)) — anchored to a clean ζ = 0.5 design.
    Choose I=1, Kp=4 → ωn=2; want ζ=0.5 → Kd = 0.5·2·sqrt(4·1) = 2."""
    res = attitude_pd_check(inertia=1.0, kp=4.0, kd=2.0)
    assert res["natural_frequency_rad_s"] == pytest.approx(2.0)
    assert res["damping_ratio"] == pytest.approx(0.5)
    assert res["ok"] is True


def test_attitude_pd_input_is_consumed():
    """More Kd → more damping; more Kp at fixed Kd → less damping (ζ ∝ 1/sqrt(Kp))
    but higher natural frequency."""
    base = attitude_pd_check(1.0, 4.0, 2.0)
    more_kd = attitude_pd_check(1.0, 4.0, 3.0)
    more_kp = attitude_pd_check(1.0, 9.0, 2.0)
    assert more_kd["damping_ratio"] > base["damping_ratio"]
    assert more_kp["damping_ratio"] < base["damping_ratio"]
    assert more_kp["natural_frequency_rad_s"] > base["natural_frequency_rad_s"]


def test_attitude_pd_band_flips():
    """The 0.4–0.8 band honestly rejects over- and under-damped designs."""
    # Under-damped: tiny Kd → ζ well below 0.4
    under = attitude_pd_check(1.0, 4.0, 0.4)   # ζ = 0.1
    assert under["damping_ratio"] == pytest.approx(0.1)
    assert under["ok"] is False
    # Over-damped: large Kd → ζ above 0.8
    over = attitude_pd_check(1.0, 4.0, 4.0)    # ζ = 1.0
    assert over["damping_ratio"] == pytest.approx(1.0)
    assert over["ok"] is False


def test_attitude_pd_nonpositive_kd_is_evaluable():
    """A zero/negative Kd yields ζ ≤ 0 and honestly FAILS (does not raise) — a
    meaningful gain choice per the docstring."""
    res = attitude_pd_check(1.0, 4.0, 0.0)
    assert res["damping_ratio"] == 0.0
    assert res["ok"] is False
    neg = attitude_pd_check(1.0, 4.0, -1.0)
    assert neg["damping_ratio"] < 0.0
    assert neg["ok"] is False


def test_attitude_pd_guards():
    with pytest.raises(ValueError):
        attitude_pd_check(0.0, 4.0, 2.0)                    # inertia
    with pytest.raises(ValueError):
        attitude_pd_check(1.0, 0.0, 2.0)                    # Kp
    with pytest.raises(ValueError):
        attitude_pd_check(1.0, 4.0, 2.0, zeta_min=0.8, zeta_max=0.4)  # bad band
    with pytest.raises(ValueError):
        attitude_pd_check(1.0, 4.0, 2.0, zeta_min=0.0)      # band lower ≤ 0


@settings(max_examples=50)
@given(
    inertia=st.floats(min_value=1e-3, max_value=1e3),
    kp=st.floats(min_value=1e-3, max_value=1e3),
    kd=st.floats(min_value=0.0, max_value=1e3),
)
def test_attitude_pd_definitions_property(inertia, kp, kd):
    """Property: ωn and ζ always match their closed-form definitions, and the
    standard relation ζ = Kd/(2·I·ωn) holds (cross-check via a second form)."""
    res = attitude_pd_check(inertia, kp, kd, zeta_min=1e-6, zeta_max=1e9)
    omega_n = math.sqrt(kp / inertia)
    zeta = kd / (2.0 * math.sqrt(kp * inertia))
    assert res["natural_frequency_rad_s"] == pytest.approx(omega_n, rel=1e-9)
    assert res["damping_ratio"] == pytest.approx(zeta, rel=1e-9, abs=1e-12)
    # Equivalent form: ζ = Kd / (2·I·ωn)
    assert res["damping_ratio"] == pytest.approx(kd / (2.0 * inertia * omega_n), rel=1e-9, abs=1e-12)
