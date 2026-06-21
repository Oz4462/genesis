"""Fatigue — high-cycle lifetime checks (Goodman / Soderberg / Gerber, Basquin, Miner).

The mean-stress lines must reduce to their exact endpoints (pure alternating fails at
S_e, pure mean at UTS / S_y), order correctly (Soderberg ≤ Goodman ≤ Gerber in
allowable load), Basquin must invert exactly (σ→N→σ), and Miner must sum to 1 at
failure. Offline, no LLM, pure python.

Run:  pytest tests/test_fatigue.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.fatigue import (  # noqa: E402
    basquin_life,
    basquin_stress,
    endurance_limit,
    gerber_safety_factor,
    goodman_check,
    goodman_safety_factor,
    miner_damage,
    soderberg_safety_factor,
)


# --- endurance limit -----------------------------------------------------------

def test_endurance_limit_is_half_uts_capped():
    assert math.isclose(endurance_limit(500.0), 250.0)            # 0.5 * UTS
    assert math.isclose(endurance_limit(2000.0), 700.0)          # capped plateau
    assert math.isclose(endurance_limit(500.0, marin_factor=0.8), 200.0)  # Marin reduction
    with pytest.raises(ValueError):
        endurance_limit(0.0)


# --- Goodman endpoints and a worked value --------------------------------------

def test_goodman_pure_alternating_fails_at_endurance():
    # sigma_m = 0: the safety factor is simply S_e / sigma_a
    assert math.isclose(goodman_safety_factor(100.0, 0.0, 500.0, 250.0), 2.5)


def test_goodman_pure_mean_fails_at_uts():
    # sigma_a = 0: failure when sigma_m = UTS (n = 1 there)
    assert math.isclose(goodman_safety_factor(0.0, 500.0, 500.0, 250.0), 1.0)
    assert math.isclose(goodman_safety_factor(0.0, 200.0, 500.0, 250.0), 2.5)


def test_goodman_worked_value_and_check():
    r = goodman_check(80.0, 60.0, uts=500.0, endurance=250.0)
    assert math.isclose(r["goodman_value"], 0.44)                # 80/250 + 60/500
    assert math.isclose(r["safety_factor"], 1.0 / 0.44)
    assert r["ok"] and r["infinite_life"]
    # an overloaded case fails
    assert not goodman_check(200.0, 200.0, uts=500.0, endurance=250.0)["ok"]


def test_compressive_mean_is_not_credited():
    # a compressive mean is conservatively treated as zero -> same as sigma_m = 0
    with_compr = goodman_safety_factor(100.0, -150.0, 500.0, 250.0)
    zero_mean = goodman_safety_factor(100.0, 0.0, 500.0, 250.0)
    assert math.isclose(with_compr, zero_mean)


# --- ordering of the three criteria --------------------------------------------

def test_soderberg_stricter_than_goodman_stricter_than_gerber():
    sa, sm, uts, sy, se = 80.0, 60.0, 500.0, 300.0, 250.0
    soderberg = soderberg_safety_factor(sa, sm, sy, se)
    goodman = goodman_safety_factor(sa, sm, uts, se)
    gerber = gerber_safety_factor(sa, sm, uts, se)
    assert soderberg < goodman < gerber          # allowable load: Soderberg <= ... <= Gerber


def test_gerber_reduces_to_alternating_when_mean_is_zero():
    assert math.isclose(gerber_safety_factor(100.0, 0.0, 500.0, 250.0), 2.5)


# --- Basquin S-N inverts exactly -----------------------------------------------

def test_basquin_round_trips():
    coeff, b = 900.0, -0.1
    n = basquin_life(300.0, coeff, b)
    assert math.isclose(basquin_stress(n, coeff, b), 300.0, rel_tol=1e-9)
    # at 2N = 1 (N = 0.5) the amplitude equals the strength coefficient
    assert math.isclose(basquin_stress(0.5, coeff, b), coeff, rel_tol=1e-12)


def test_basquin_higher_amplitude_means_fewer_cycles():
    coeff, b = 900.0, -0.1
    assert basquin_life(400.0, coeff, b) < basquin_life(200.0, coeff, b)
    with pytest.raises(ValueError):
        basquin_life(100.0, coeff, 0.1)          # exponent must be negative


# --- Miner's cumulative damage -------------------------------------------------

def test_miner_sums_to_one_at_failure():
    full = miner_damage([(5000.0, 10000.0), (2500.0, 5000.0)])   # 0.5 + 0.5
    assert math.isclose(full["damage"], 1.0)
    assert not full["ok"]                                        # D = 1 is failure
    partial = miner_damage([(1000.0, 10000.0)])
    assert math.isclose(partial["damage"], 0.1)
    assert partial["ok"] and math.isclose(partial["remaining_life_fraction"], 0.9)
    with pytest.raises(ValueError):
        miner_damage([(1.0, 0.0)])
