"""Tests for the dimensional-consistency training reward (discovery/reward.py).

Pins the unoccupied lever: a dimensionally-exact law scores 1.0 consistency; a dimensionally-wrong one
decays; and the reward gates fit by consistency, so a perfect-fit-but-dimensionally-impossible proposal
scores BELOW a dimensionally-sound moderate fit -- the anti-hallucination signal shaped into training.
Offline, deterministic.
"""

import math

from gen.discovery.reward import dimensional_consistency, discovery_reward

# Kepler: T [s] = a^1.5 * mu^-0.5, a [m], mu [m^3/s^2].
_KEPLER_UNITS = {"a": "m", "mu": "m^3/s^2"}


def test_dimensionally_exact_law_is_fully_consistent():
    assert dimensional_consistency("s", _KEPLER_UNITS, {"a": 1.5, "mu": -0.5}) == 1.0


def test_dimensionally_wrong_law_decays():
    c = dimensional_consistency("s", _KEPLER_UNITS, {"a": 1.0, "mu": -0.5})   # leaves a stray length^-0.5
    assert 0.0 < c < 1.0
    assert math.isclose(c, math.exp(-0.5), rel_tol=1e-9)                      # residual is exactly 0.5


def test_reward_gates_fit_by_dimensional_consistency():
    exact = discovery_reward(r_squared=1.0, target_unit="s", source_units=_KEPLER_UNITS,
                             exponents={"a": 1.5, "mu": -0.5})
    wrong = discovery_reward(r_squared=1.0, target_unit="s", source_units=_KEPLER_UNITS,
                             exponents={"a": 1.0, "mu": -0.5})
    assert exact == 1.0 and wrong < 1.0


def test_perfect_fit_but_impossible_scores_below_sound_moderate_fit():
    # the publishable point: numeric fit alone must NOT win over dimensional soundness.
    impossible_perfect = discovery_reward(r_squared=1.0, target_unit="s", source_units=_KEPLER_UNITS,
                                          exponents={"a": 3.0, "mu": -0.5})   # badly off-dimension
    sound_moderate = discovery_reward(r_squared=0.7, target_unit="s", source_units=_KEPLER_UNITS,
                                      exponents={"a": 1.5, "mu": -0.5})
    assert sound_moderate > impossible_perfect


def test_reward_is_bounded_and_clips_negative_r2():
    assert discovery_reward(r_squared=-5.0, target_unit="s", source_units=_KEPLER_UNITS,
                            exponents={"a": 1.5, "mu": -0.5}) == 0.0
    assert 0.0 <= discovery_reward(r_squared=2.0, target_unit="s", source_units=_KEPLER_UNITS,
                                   exponents={"a": 1.5, "mu": -0.5}) <= 1.0


def test_non_finite_r_squared_scores_zero_not_green():
    """IEEE NaN/Inf must never produce a high reward (REWORK integrity)."""
    for bad in (float("nan"), float("inf"), float("-inf")):
        r = discovery_reward(
            r_squared=bad,
            target_unit="s",
            source_units=_KEPLER_UNITS,
            exponents={"a": 1.5, "mu": -0.5},
        )
        assert r == 0.0 and math.isfinite(r)


def test_non_finite_exponents_yield_zero_consistency():
    c = dimensional_consistency("s", _KEPLER_UNITS, {"a": float("nan"), "mu": -0.5})
    assert c == 0.0
