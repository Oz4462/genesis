"""Creep and creep-rupture — closed forms pinned to exact limits and a known anchor.

The Larson-Miller parameter and its inverse must round-trip EXACTLY (t_r -> LMP -> t_r),
the Norton creep rate must scale as (s2/s1)^n with stress and follow the exact Arrhenius
ratio in temperature, and a concrete anchor (T=811 K ~1000 F, t_r=1e5 h, C=20 -> LMP
20275) must hold. These pin the slow high-temperature failure mode the room-temperature
stress check cannot see.

Offline, no LLM, pure python (math only).

Run:  pytest tests/test_creep.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from gen.creep import (  # noqa: E402
    creep_life_check,
    larson_miller_parameter,
    norton_creep_rate,
    rupture_time_from_lmp,
)


# --- Larson-Miller: the known anchor and the exact inverse -----------------------

def test_larson_miller_anchor():
    # T=811 K (~1000 F), t_r=1e5 h, C=20  ->  LMP = 811*(20 + 5) = 811*25 = 20275
    lmp = larson_miller_parameter(811.0, 1e5, constant_C=20.0)
    assert np.isclose(lmp, 20275.0)
    assert np.isclose(lmp, 811.0 * 25.0)


def test_lmp_inverse_round_trips_exactly():
    # t_r -> LMP -> t_r must reproduce the original rupture time exactly
    for T, tr, C in [(811.0, 1e5, 20.0), (900.0, 5e4, 20.0),
                     (1000.0, 1e3, 25.0), (700.0, 2.5e5, 18.0)]:
        lmp = larson_miller_parameter(T, tr, constant_C=C)
        back = rupture_time_from_lmp(lmp, T, constant_C=C)
        assert math.isclose(back, tr, rel_tol=1e-9)


def test_lmp_inverse_is_the_analytic_inverse():
    # rupture_time_from_lmp is 10^(LMP/T - C); feeding LMP=T*(C+log10(t)) returns t
    T, C = 850.0, 20.0
    lmp = larson_miller_parameter(T, 12345.0, constant_C=C)
    assert math.isclose(rupture_time_from_lmp(lmp, T, constant_C=C), 12345.0, rel_tol=1e-9)


def test_lmp_increases_with_temperature_and_time():
    base = larson_miller_parameter(800.0, 1e4)
    assert larson_miller_parameter(900.0, 1e4) > base   # hotter -> larger LMP
    assert larson_miller_parameter(800.0, 1e5) > base   # longer life -> larger LMP


# --- Norton creep: power law in stress, Arrhenius in temperature -----------------

_A, _n, _Q = 1e-10, 5.0, 300000.0     # arbitrary self-consistent Norton fit, Q in J/mol


def test_norton_rate_scales_as_stress_power():
    # doubling stress multiplies the rate by exactly (s2/s1)^n
    T = 873.0
    r1 = norton_creep_rate(100.0, _A, _n, _Q, T)
    r2 = norton_creep_rate(200.0, _A, _n, _Q, T)
    assert math.isclose(r2 / r1, (200.0 / 100.0) ** _n, rel_tol=1e-9)
    assert math.isclose(r2 / r1, 32.0, rel_tol=1e-9)    # 2^5


def test_norton_rate_follows_arrhenius_in_temperature():
    r_lo = norton_creep_rate(100.0, _A, _n, _Q, 800.0)
    r_hi = norton_creep_rate(100.0, _A, _n, _Q, 900.0)
    assert r_hi > r_lo                                   # hotter creeps faster
    expected = math.exp(-_Q / 8.314 * (1.0 / 900.0 - 1.0 / 800.0))
    assert math.isclose(r_hi / r_lo, expected, rel_tol=1e-9)


def test_norton_rate_is_linear_in_A():
    T = 873.0
    assert math.isclose(
        norton_creep_rate(100.0, 2.0 * _A, _n, _Q, T),
        2.0 * norton_creep_rate(100.0, _A, _n, _Q, T),
        rel_tol=1e-12,
    )


# --- the design check: rupture time vs design life -------------------------------

def test_creep_life_check_safe_part_outlasts_design():
    # LMP=20275 at 811 K -> rupture 1e5 h; design 1e4 h -> safety_factor 10, ok
    r = creep_life_check(120.0, 811.0, 1e4, 20275.0, constant_C=20.0)
    assert math.isclose(r["rupture_time"], 1e5, rel_tol=1e-9)
    assert math.isclose(r["safety_factor"], 10.0, rel_tol=1e-9)
    assert r["ok"]


def test_creep_life_check_flags_too_short_a_life():
    # same hot part, but a design life longer than the rupture time -> not ok
    r = creep_life_check(120.0, 811.0, 5e5, 20275.0, constant_C=20.0)
    assert math.isclose(r["rupture_time"], 1e5, rel_tol=1e-9)
    assert r["safety_factor"] < 1.0
    assert not r["ok"]


def test_creep_life_check_safety_factor_is_rupture_over_design():
    r = creep_life_check(80.0, 900.0, 2000.0, 22229.073, constant_C=20.0)
    assert math.isclose(r["safety_factor"], r["rupture_time"] / r["design_life"],
                        rel_tol=1e-12)


# --- guards: loud failure, never a guessed value ---------------------------------

def test_guards_reject_nonphysical_inputs():
    with pytest.raises(ValueError):
        larson_miller_parameter(-1.0, 1e4)            # negative absolute temperature
    with pytest.raises(ValueError):
        larson_miller_parameter(800.0, 0.0)           # log10(0) undefined
    with pytest.raises(ValueError):
        rupture_time_from_lmp(20000.0, 0.0)           # division by zero T
    with pytest.raises(ValueError):
        norton_creep_rate(0.0, _A, _n, _Q, 800.0)     # non-positive stress
    with pytest.raises(ValueError):
        norton_creep_rate(100.0, _A, _n, _Q, -5.0)    # non-positive temperature
    with pytest.raises(ValueError):
        creep_life_check(100.0, 800.0, 0.0, 20000.0)  # non-positive design life


def test_is_deterministic():
    a = creep_life_check(120.0, 811.0, 1e4, 20275.0)
    b = creep_life_check(120.0, 811.0, 1e4, 20275.0)
    assert a == b
