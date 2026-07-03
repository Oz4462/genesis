"""Flight validators — momentum theory, energy/current budgets, PD damping.

Exact anchors, not vibes: the two momentum-theory power forms T·v_i and
T^(3/2)/sqrt(2·ρ·A) are an algebraic identity (pinned to machine precision);
v_i for T=10 N on A=0.05 m² at ISA density is sqrt(10/(2·1.225·0.05)) m/s by
hand; a 1-kg craft with 20 N max thrust clears the 2:1 rule and 15 N fails it;
50 Wh at 80 % usable over 100 W is exactly 24 min; 500 W at 14.8 V draws
33.78 A (clears a 40-A ESC, browns out a 20C·1.3Ah pack); Kd = 2·ζ·sqrt(Kp·I)
reproduces ζ = 0.7 exactly. Every nonsense input raises; an undamped (Kd=0)
loop honestly FAILS instead of raising — it is an evaluable bad design.

Offline, no LLM, no numpy.

Run:  pytest tests/test_flight.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.flight import (  # noqa: E402
    AIR_DENSITY_SEA_LEVEL,
    attitude_pd_check,
    battery_endurance_check,
    current_budget_check,
    ideal_induced_power,
    induced_velocity,
    rotor_hover_check,
)


# ---------------------------------------------------------- momentum theory
def test_induced_velocity_hand_anchor():
    v = induced_velocity(10.0, 0.05)                       # ISA density default
    assert v == pytest.approx(math.sqrt(10.0 / (2.0 * 1.225 * 0.05)))
    assert v == pytest.approx(9.0351, abs=1e-3)            # by hand


def test_power_forms_are_an_algebraic_identity():
    for thrust, area in ((1.0, 0.01), (10.0, 0.05), (37.5, 0.2)):
        p1 = ideal_induced_power(thrust, area)
        p2 = thrust ** 1.5 / math.sqrt(2.0 * AIR_DENSITY_SEA_LEVEL * area)
        assert p1 == pytest.approx(p2, rel=1e-12)          # identity, not approximation


def test_hover_check_two_to_one_rule():
    ok = rotor_hover_check(mass=1.0, rotor_disk_area=0.05, n_rotors=4.0,
                           max_total_thrust=20.0)
    assert ok["ok"] and ok["thrust_weight_ratio"] == pytest.approx(20.0 / 9.80665)
    weak = rotor_hover_check(mass=1.0, rotor_disk_area=0.05, n_rotors=4.0,
                             max_total_thrust=15.0)
    assert not weak["ok"]                                  # 1.53 < 2: no margin


def test_hover_power_scales_with_figure_of_merit():
    a = rotor_hover_check(1.0, 0.05, 4.0, 20.0, figure_of_merit=0.6)
    b = rotor_hover_check(1.0, 0.05, 4.0, 20.0, figure_of_merit=0.5)
    assert b["hover_power_w"] == pytest.approx(a["hover_power_w"] * 0.6 / 0.5)
    # and the ideal total is n * T_r * v_i for the hover share of the weight
    t_r = 9.80665 / 4.0
    p_ideal = 4.0 * t_r * induced_velocity(t_r, 0.05)
    assert a["hover_power_w"] == pytest.approx(p_ideal / 0.6)


def test_hover_check_rejects_nonsense():
    with pytest.raises(ValueError):
        rotor_hover_check(0.0, 0.05, 4.0, 20.0)
    with pytest.raises(ValueError):
        rotor_hover_check(1.0, -0.05, 4.0, 20.0)
    with pytest.raises(ValueError):
        rotor_hover_check(1.0, 0.05, 0.0, 20.0)
    with pytest.raises(ValueError):
        rotor_hover_check(1.0, 0.05, 4.0, 20.0, figure_of_merit=1.3)


# ------------------------------------------------------------ energy budget
def test_battery_endurance_exact_arithmetic():
    r = battery_endurance_check(50.0, 100.0, 20.0)         # 50 Wh, 100 W, need 20 min
    assert r["usable_wh"] == pytest.approx(40.0)           # the 80 % LiPo rule
    assert r["endurance_min"] == pytest.approx(24.0)
    assert r["ok"] and r["safety_factor"] == pytest.approx(1.2)
    assert not battery_endurance_check(50.0, 100.0, 30.0)["ok"]


def test_battery_rejects_nonsense():
    for bad in ((0.0, 100.0, 20.0), (50.0, 0.0, 20.0), (50.0, 100.0, 0.0)):
        with pytest.raises(ValueError):
            battery_endurance_check(*bad)
    with pytest.raises(ValueError):
        battery_endurance_check(50.0, 100.0, 20.0, usable_fraction=1.2)


# ----------------------------------------------------------- current budget
def test_current_budget_esc_and_battery():
    r = current_budget_check(power_w=500.0, voltage_v=14.8, esc_limit_a=40.0,
                             battery_capacity_ah=1.3, battery_c_rating=50.0)
    assert r["current_a"] == pytest.approx(500.0 / 14.8)   # 33.78 A
    assert r["battery_max_a"] == pytest.approx(65.0)
    assert r["ok"]
    weak_pack = current_budget_check(500.0, 14.8, 40.0, 1.3, 20.0)
    assert not weak_pack["ok"]                             # 26 A < 33.78 A: brownout
    assert weak_pack["safety_factor"] == pytest.approx(26.0 / (500.0 / 14.8))


def test_current_budget_rejects_nonsense():
    with pytest.raises(ValueError):
        current_budget_check(0.0, 14.8, 40.0, 1.3, 50.0)
    with pytest.raises(ValueError):
        current_budget_check(500.0, 0.0, 40.0, 1.3, 50.0)
    with pytest.raises(ValueError):
        current_budget_check(500.0, 14.8, 40.0, 1.3, 0.0)


# --------------------------------------------------------------- PD damping
def test_pd_damping_exact_design_point():
    inertia, kp = 0.02, 2.0
    kd = 2.0 * 0.7 * math.sqrt(kp * inertia)               # design for zeta = 0.7
    r = attitude_pd_check(inertia, kp, kd)
    assert r["natural_frequency_rad_s"] == pytest.approx(10.0)   # sqrt(2/0.02)
    assert r["damping_ratio"] == pytest.approx(0.7)
    assert r["ok"]


def test_pd_underdamped_overdamped_and_undamped_fail_honestly():
    assert not attitude_pd_check(0.02, 2.0, 0.06)["ok"]    # zeta = 0.15: wobble
    assert not attitude_pd_check(0.02, 2.0, 1.0)["ok"]     # zeta = 2.5: sluggish
    undamped = attitude_pd_check(0.02, 2.0, 0.0)           # P-only: evaluable
    assert undamped["damping_ratio"] == 0.0 and not undamped["ok"]
    negative = attitude_pd_check(0.02, 2.0, -0.1)          # negative damping
    assert negative["damping_ratio"] < 0.0 and not negative["ok"]


def test_pd_rejects_nonsense():
    with pytest.raises(ValueError):
        attitude_pd_check(0.0, 2.0, 0.28)
    with pytest.raises(ValueError):
        attitude_pd_check(0.02, 0.0, 0.28)
    with pytest.raises(ValueError):
        attitude_pd_check(0.02, 2.0, 0.28, zeta_min=0.8, zeta_max=0.4)
