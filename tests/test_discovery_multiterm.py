"""Additive multi-term discovery — the frontier beyond a single dimensional power law.

Pins the two honesty guarantees of ``discovery.multiterm``: (1) every additive term is
dimensionally consistent (only same-dimension quantities may be summed), and (2) parsimony —
a pure power law stays ONE term, a spurious greedy term is pruned, and the improvement
threshold is a real gate, so the extra freedom of a sum never accretes terms that only chase
the data.
"""

import math

import numpy as np
import pytest

from gen.discovery import (
    Constant, DiscoveryProblem, Variable,
    MultiTermLaw, MultiTermValidation, Term, candidate_term_exponents, discover_multiterm,
    evaluate_multiterm_law, multiterm_out_of_sample_validate,
)
from gen.discovery.engine import dimensional_system

MU_SUN = 1.32712440018e20


def _kinematics() -> DiscoveryProblem:
    """s = v0·t + ½·a·t²  — two additive terms of dimension [m] from three inputs."""
    v0 = np.array([1.0, 5.0, 2.0, 8.0, 3.0, 6.0, 10.0, 4.0])
    t = np.array([1.0, 2.0, 4.0, 1.5, 3.0, 5.0, 2.0, 6.0])
    a = np.array([2.0, 10.0, 1.0, 6.0, 4.0, 8.0, 3.0, 9.0])
    s = v0 * t + 0.5 * a * t**2
    return DiscoveryProblem(
        idea="Kinematik", target=Variable("s", "m", tuple(s)),
        inputs=(Variable("v0", "m/s", tuple(v0)), Variable("t", "s", tuple(t)),
                Variable("a", "m/s^2", tuple(a))))


def _free_fall() -> DiscoveryProblem:
    """v = 40 + g·t  — one power-law term (g·t) plus a fitted intercept of dimension [m/s]."""
    t = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    g = 9.81
    v = 40.0 + g * t
    return DiscoveryProblem(
        idea="Freier Fall mit Anfangsgeschwindigkeit", target=Variable("v", "m/s", tuple(v)),
        inputs=(Variable("t", "s", tuple(t)),),
        constants=(Constant("g", g, "m/s^2"),))


def _kepler() -> DiscoveryProblem:
    """T = 2π·a^(3/2)·μ^(−1/2)  — a pure single power law (fully-determined dimensional system)."""
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11, 1.434e12])
    T = 2.0 * math.pi * a**1.5 / math.sqrt(MU_SUN)
    return DiscoveryProblem(idea="Kepler", target=Variable("T", "s", tuple(T)),
                            inputs=(Variable("a", "m", tuple(a)),),
                            constants=(Constant("mu", MU_SUN, "m^3/s^2"),))


def _nonzero(exps: dict[str, float]) -> dict[str, float]:
    return {k: v for k, v in exps.items() if abs(v) > 1e-9}


def _find_term(law: MultiTermLaw, want: dict[str, float]) -> Term | None:
    for term in law.terms:
        if not term.is_intercept and _nonzero(term.exponents) == want:
            return term
    return None


def test_kinematics_recovers_exactly_the_two_physical_terms():
    """s = v0·t + ½·a·t² is recovered as EXACTLY two terms with coefficients 1.0 and 0.5,
    R²≈1 — the greedy's transient dimensionally-valid 'blend' term is pruned away."""
    law = discover_multiterm(_kinematics())
    assert law.n_terms == 2
    assert law.r_squared > 0.999
    vt = _find_term(law, {"v0": 1.0, "t": 1.0})
    at = _find_term(law, {"a": 1.0, "t": 2.0})
    assert vt is not None and abs(vt.coefficient - 1.0) < 1e-6
    assert at is not None and abs(at.coefficient - 0.5) < 1e-6


def test_free_fall_recovers_an_intercept_plus_the_g_t_term():
    """v = 40 + g·t is recovered as a fitted intercept (≈40) plus the g·t term (coef ≈1)."""
    law = discover_multiterm(_free_fall())
    assert law.n_terms == 2
    assert law.r_squared > 0.999
    intercept = next((t for t in law.terms if t.is_intercept), None)
    gt = _find_term(law, {"g": 1.0, "t": 1.0})
    assert intercept is not None and abs(intercept.coefficient - 40.0) < 1e-6
    assert gt is not None and abs(gt.coefficient - 1.0) < 1e-6


def test_a_pure_power_law_stays_a_single_term():
    """Kepler is a pure power law: the fully-determined dimensional system admits exactly one
    valid term, and parsimony correctly REJECTS the available intercept — one term, not two."""
    law = discover_multiterm(_kepler())
    assert law.n_terms == 1
    term = law.terms[0]
    assert not term.is_intercept
    assert abs(term.exponents["a"] - 1.5) < 1e-9
    assert abs(term.exponents["mu"] + 0.5) < 1e-9
    assert abs(term.coefficient - 2.0 * math.pi) / (2.0 * math.pi) < 1e-6


def test_improvement_threshold_is_a_real_parsimony_gate():
    """A near-1 improvement threshold admits only the single best term; a tiny one admits the
    intercept too. The knob genuinely controls how readily a term enters (anti-overfit)."""
    strict = discover_multiterm(_free_fall(), improvement_threshold=0.99)
    loose = discover_multiterm(_free_fall(), improvement_threshold=1e-6)
    assert strict.n_terms == 1
    assert loose.n_terms == 2
    assert strict.n_terms < loose.n_terms


def test_max_terms_caps_the_model_complexity():
    """No matter the data, the model never exceeds max_terms terms."""
    law = discover_multiterm(_kinematics(), max_terms=1)
    assert law.n_terms == 1


def test_every_candidate_term_is_dimensionally_valid():
    """The core invariant: every enumerated term's exponent vector p satisfies A·p = b (it
    carries the target's dimension), and the two physical kinematics terms are in the set."""
    problem = _kinematics()
    a_matrix, b_vec, names = dimensional_system(problem)
    terms = candidate_term_exponents(problem)
    assert terms
    for exps in terms:
        p = np.array([exps[n] for n in names], dtype=float)
        assert np.linalg.norm(a_matrix @ p - b_vec) < 1e-9
    nonzero = [_nonzero(e) for e in terms]
    assert {"v0": 1.0, "t": 1.0} in nonzero
    assert {"a": 1.0, "t": 2.0} in nonzero


def test_rejects_non_positive_target_magnitudes():
    """Power-law terms need positive magnitudes; a non-positive target is a hard ValueError,
    never a silently-wrong fit."""
    bad = DiscoveryProblem(idea="kaputt", target=Variable("s", "m", (1.0, -2.0, 3.0, 4.0)),
                           inputs=(Variable("t", "s", (1.0, 2.0, 3.0, 4.0)),),
                           constants=(Constant("g", 9.81, "m/s^2"),))
    with pytest.raises(ValueError):
        discover_multiterm(bad)


def test_rejects_non_positive_input_magnitudes():
    """A non-positive INPUT magnitude is likewise rejected (the power-law domain is positive)."""
    bad = DiscoveryProblem(idea="kaputt", target=Variable("s", "m", (10.0, 20.0, 30.0, 40.0)),
                           inputs=(Variable("t", "s", (1.0, -2.0, 3.0, 4.0)),),
                           constants=(Constant("g", 9.81, "m/s^2"),))
    with pytest.raises(ValueError):
        discover_multiterm(bad)


def test_law_renders_a_readable_expression():
    """The discovered law exposes the dataclass types and a human-readable expression."""
    law = discover_multiterm(_free_fall())
    assert isinstance(law, MultiTermLaw)
    assert all(isinstance(t, Term) for t in law.terms)
    assert law.expression.startswith("v = ")


def _kinematics_n(n: int, seed: int) -> DiscoveryProblem:
    """A larger kinematics dataset (s = v0·t + ½·a·t²) for train/held-out splits."""
    rng = np.random.default_rng(seed)
    v0 = rng.uniform(1.0, 10.0, n)
    t = rng.uniform(1.0, 6.0, n)
    a = rng.uniform(1.0, 10.0, n)
    s = v0 * t + 0.5 * a * t**2
    return DiscoveryProblem(
        idea="Kinematik", target=Variable("s", "m", tuple(s)),
        inputs=(Variable("v0", "m/s", tuple(v0)), Variable("t", "s", tuple(t)),
                Variable("a", "m/s^2", tuple(a))))


def test_evaluate_law_reproduces_the_in_sample_fit():
    """`evaluate_multiterm_law` applied to the data the law was fitted on reproduces the target
    (R²=1 case → exact) — the prediction primitive behind out-of-sample scoring is correct."""
    problem = _kinematics()
    law = discover_multiterm(problem)
    pred = evaluate_multiterm_law(law, problem)
    assert np.allclose(pred, np.asarray(problem.target.values, float), rtol=1e-9)


def test_a_real_multiterm_law_generalises_out_of_sample():
    """Kinematics fitted on a TRAIN split predicts the HELD-OUT points — the additive law (its
    terms, coefficients AND pruning) transfers, with a near-zero train-test gap."""
    res = multiterm_out_of_sample_validate(_kinematics_n(10, seed=1), train_fraction=0.6, seed=2)
    assert isinstance(res, MultiTermValidation)
    assert res.generalises
    assert res.test_r2 > 0.99
    assert abs(res.overfit_gap) < 1e-3
    assert res.n_train >= 2 and res.n_test >= 1
    assert res.n_terms == 2          # the two physical terms, not a noise-padded sum


def test_noise_does_not_generalise_multiterm():
    """A target that is pure noise does NOT generalise out-of-sample: even though the multi-term
    model CAN fit the train split (more free coefficients), the held-out R² collapses — the
    honest guard against an overfit (or over-pruned) additive model."""
    rng = np.random.default_rng(11)
    v0 = rng.uniform(1.0, 10.0, 12)
    t = rng.uniform(1.0, 6.0, 12)
    a = rng.uniform(1.0, 10.0, 12)
    y = rng.uniform(1.0, 50.0, 12)                       # noise, unrelated to the inputs
    problem = DiscoveryProblem(
        idea="Rauschen", target=Variable("s", "m", tuple(y)),
        inputs=(Variable("v0", "m/s", tuple(v0)), Variable("t", "s", tuple(t)),
                Variable("a", "m/s^2", tuple(a))))
    res = multiterm_out_of_sample_validate(problem, train_fraction=0.6, seed=3)
    assert not res.generalises
    assert res.test_r2 < 0.9


def test_oos_validation_needs_enough_points():
    """Splitting train/held-out needs at least 4 points — fewer is a hard ValueError."""
    tiny = DiscoveryProblem(
        idea="zu klein", target=Variable("s", "m", (10.0, 20.0, 30.0)),
        inputs=(Variable("v0", "m/s", (1.0, 2.0, 3.0)), Variable("t", "s", (1.0, 2.0, 3.0)),
                Variable("a", "m/s^2", (2.0, 3.0, 4.0))))
    with pytest.raises(ValueError):
        multiterm_out_of_sample_validate(tiny)


def test_oos_validation_detects_over_pruning():
    """The other failure mode the held-out R² must catch: OVER-pruning. Forced aggressive pruning
    (prune_rel_tol high enough to drop a genuine term of the real 2-term law) yields a smaller law
    whose held-out R² is measurably worse than the honest 2-term fit — so a wrongly-dropped real
    term is not hidden, it shows up out-of-sample."""
    problem = _kinematics_n(10, seed=1)                 # the data/seed proven to give a clean 2-term fit
    honest = multiterm_out_of_sample_validate(problem, seed=2)
    over_pruned = multiterm_out_of_sample_validate(problem, seed=2, prune_rel_tol=0.9)
    assert honest.generalises and honest.n_terms == 2
    assert over_pruned.n_terms < honest.n_terms        # a real term was pruned away
    assert over_pruned.test_r2 < honest.test_r2        # and the held-out fit suffered for it
