"""Transcendental discovery — exp/log/sin/tanh of a DIMENSIONLESS π-group (the frontier past the
power-law family). Pins the honest method: a transcendental argument must be dimensionless (built
from the null space of the dimensional matrix), and a transcendental verdict must BEAT the simpler
power-law hypothesis — never an over-claim for what is really a power law.
"""

import math

import numpy as np
import pytest

from gen.discovery import (
    Constant, DiscoveryProblem, Variable,
    TranscendentalLaw, dimensionless_groups, discover_transcendental,
)

MU_SUN = 1.32712440018e20


def _exp_decay() -> DiscoveryProblem:
    """Exponential decay x = x0·exp(−t/τ), x0=10 m, τ=5 s — genuinely transcendental: x[m] is NOT
    a power law of the time-only sources, so the dimensional scale lives in the fitted C."""
    t = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    tau, x0 = 5.0, 10.0
    x = x0 * np.exp(-t / tau)
    return DiscoveryProblem(
        idea="Zerfall", target=Variable("x", "m", tuple(x)),
        inputs=(Variable("t", "s", tuple(t)),),
        constants=(Constant("tau", tau, "s"),))


def _sine() -> DiscoveryProblem:
    """An oscillation y = 3·sin(2·(t/τ)) + 5 over the dimensionless group t/τ."""
    t = np.linspace(0.1, 3.0, 16)
    tau = 1.0
    y = 3.0 * np.sin(2.0 * (t / tau)) + 5.0
    return DiscoveryProblem(
        idea="Schwingung", target=Variable("y", "m", tuple(y)),
        inputs=(Variable("t", "s", tuple(t)),),
        constants=(Constant("tau", tau, "s"),))


def _kepler() -> DiscoveryProblem:
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11, 1.434e12])
    T = 2.0 * math.pi * a**1.5 / math.sqrt(MU_SUN)
    return DiscoveryProblem(idea="Kepler", target=Variable("T", "s", tuple(T)),
                            inputs=(Variable("a", "m", tuple(a)),),
                            constants=(Constant("mu", MU_SUN, "m^3/s^2"),))


def test_dimensionless_group_is_the_time_ratio():
    """For two time scales t and τ the only dimensionless group is the ratio t/τ (both
    orientations are enumerated; the fit later picks the one a transcendental needs)."""
    groups = dimensionless_groups(_exp_decay())
    nonzero = [{k: v for k, v in g.items() if abs(v) > 1e-9} for g in groups]
    assert {"t": 1.0, "tau": -1.0} in nonzero      # t/τ
    assert {"t": -1.0, "tau": 1.0} in nonzero      # τ/t
    # every returned group is genuinely dimensionless
    assert all(g for g in nonzero)


def test_rediscovers_exponential_decay():
    """x = x0·exp(−t/τ) is recovered: form exp over t/τ, α≈−1, C≈x0, R²≈1, verdict bestätigt
    (a power law cannot match an exponential — the transcendental beats the baseline)."""
    law = discover_transcendental(_exp_decay())
    assert isinstance(law, TranscendentalLaw)
    assert law.form_name == "exp"
    assert law.verdict == "bestaetigt"
    assert law.r_squared > 0.999
    assert law.powerlaw_r2 < 0.999          # the power-of-a-group rival does NOT nail an exponential
    assert abs(law.params["alpha"] + 1.0) < 1e-2          # the decay rate −1
    assert abs(law.params["C"] - 10.0) < 1e-1             # the scale x0
    assert abs(law.group["t"] - 1.0) < 1e-9 and abs(law.group["tau"] + 1.0) < 1e-9


def test_rediscovers_a_sine_oscillation():
    """y = 3·sin(2·t/τ) + 5 is recovered as the sin form with R²≈1 and verdict bestätigt."""
    law = discover_transcendental(_sine())
    assert law.form_name == "sin"
    assert law.verdict == "bestaetigt"
    assert law.r_squared > 0.999
    assert law.powerlaw_r2 < 0.999          # a monotonic power law cannot fit an oscillation


def test_kepler_power_law_is_not_misclassified_as_transcendental():
    """Kepler is a pure power law: it has NO dimensionless group among (a, μ), so transcendental
    discovery honestly returns widerlegt — never a transcendental over-claim for a power law."""
    law = discover_transcendental(_kepler())
    assert law.verdict != "bestaetigt"
    assert law.verdict == "widerlegt"


def test_kepler_has_no_dimensionless_group():
    """The dimensional reason behind the previous test: (a, μ) admit no nontrivial null-space
    vector, so there is no dimensionless argument a transcendental could take."""
    assert dimensionless_groups(_kepler()) == []


def test_a_pure_power_law_over_a_group_is_not_called_transcendental():
    """The decisive red-team: a target that IS a power law of the group (y = C·(t/τ)²). A
    transcendental form can still fit it ABOVE the bar (exp with a tiny argument ≈ a polynomial),
    so the honest gate does NOT rely on the transcendental failing — it relies on the power-of-a-
    group rival ALSO clearing the bar (it fits the quadratic exactly). Both essentially exact →
    verdict ``unentschieden``, never a transcendental over-claim for what is really a power law."""
    t = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    tau = 2.0
    y = 7.0 * (t / tau) ** 2                                # a quadratic in the group, a power law
    problem = DiscoveryProblem(
        idea="Potenz", target=Variable("y", "m", tuple(y)),
        inputs=(Variable("t", "s", tuple(t)),), constants=(Constant("tau", tau, "s"),))
    law = discover_transcendental(problem)
    assert law.verdict == "unentschieden"
    assert law.r_squared >= 0.999                # the transcendental DOES clear the bar here ...
    assert law.powerlaw_r2 >= 0.999             # ... but so does the power-of-the-group rival
    assert abs(law.powerlaw_r2 - 1.0) < 1e-6    # which fits the quadratic essentially exactly


def test_rejects_non_positive_input_magnitudes():
    """A π-group needs positive magnitudes; a non-positive input is a hard ValueError."""
    bad = DiscoveryProblem(
        idea="kaputt", target=Variable("x", "m", (1.0, 2.0, 3.0, 4.0)),
        inputs=(Variable("t", "s", (1.0, -2.0, 3.0, 4.0)),),
        constants=(Constant("tau", 5.0, "s"),))
    with pytest.raises(ValueError):
        discover_transcendental(bad)
