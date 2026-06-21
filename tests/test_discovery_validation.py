"""Out-of-sample validation (anti-p-hacking) + the expanded rediscovery benchmark (Phase 4)."""

import math

import numpy as np

from gen.discovery import (
    Variable, Constant, DiscoveryProblem, discover_new_formulas,
    out_of_sample_validate, rediscovery_benchmark, pendulum_case,
)

MU_SUN = 1.32712440018e20


def _kepler():
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11, 1.434e12])
    T = 2.0 * math.pi * a ** 1.5 / math.sqrt(MU_SUN)
    return DiscoveryProblem(idea="Kepler", target=Variable("T", "s", tuple(T)),
                            inputs=(Variable("a", "m", tuple(a)),),
                            constants=(Constant("mu", MU_SUN, "m^3/s^2"),))


def test_a_real_law_generalises_out_of_sample():
    """Kepler fitted on a TRAIN split predicts the HELD-OUT planets — it generalises, with a
    near-zero train-test gap (the dimensional constraint makes overfitting impossible)."""
    res = out_of_sample_validate(_kepler(), train_fraction=0.6, seed=1)
    assert res.generalises
    assert res.test_r2 > 0.99
    assert abs(res.overfit_gap) < 1e-3
    assert res.n_train >= 2 and res.n_test >= 1


def test_noise_does_not_generalise():
    """A target that is pure noise (no real relation to the inputs) does NOT generalise: the
    held-out R² collapses — out-of-sample validation catches the spurious fit."""
    rng = np.random.default_rng(7)
    a = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    y = rng.uniform(1.0, 10.0, size=a.shape[0])              # noise, unrelated to a
    problem = DiscoveryProblem(idea="Rauschen", target=Variable("y", "s", tuple(y)),
                               inputs=(Variable("a", "m", tuple(a)),),
                               constants=(Constant("c", 2.0, "m/s"),))
    res = out_of_sample_validate(problem, train_fraction=0.6, seed=3)
    assert not res.generalises
    assert res.test_r2 < 0.99


def test_pendulum_added_to_benchmark_and_rediscovered():
    """The benchmark now covers the pendulum period T = 2π·L^(1/2)·g^(-1/2)."""
    result = discover_new_formulas(pendulum_case().problem).validated[0]
    assert result.verdict == "bestaetigt"
    assert abs(result.candidate.exponents["L"] - 0.5) < 1e-3
    assert abs(result.candidate.exponents["g"] + 0.5) < 1e-3
    assert abs(result.candidate.coefficient - 2.0 * math.pi) / (2.0 * math.pi) < 1e-3


def test_full_benchmark_still_100_percent_with_pendulum():
    report = rediscovery_benchmark()
    assert report.rediscovery_rate == 1.0
    assert report.redteam_catch_rate == 1.0
    assert any(r.name == "Pendulum period" and r.success for r in report.results)
