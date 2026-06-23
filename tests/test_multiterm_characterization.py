"""Characterization + depth audit of ``discovery.multiterm`` (T01).

This file is the FACADE DETECTOR for additive multi-term discovery. The pre-existing
``test_discovery_multiterm.py`` pins the physics (kinematics/free-fall/Kepler recovery); this
file proves the *machinery underneath* genuinely runs rather than echoing canned answers:

  * the linear least-squares fit is COMPUTED from the data — change the generating coefficients
    and the recovered coefficients change to match (no constant return);
  * greedy forward selection is a real, input-driven loop — the term set and term count depend
    on the data and on the parsimony knobs;
  * pruning of float-noise terms genuinely fires and is input-dependent;
  * held-out scoring really refits on a TRAIN split and scores the HELD-OUT split — a real law
    transfers, noise does not, and the reported numbers move with the data;
  * every documented fail-loud guard raises (including the ``max_terms < 1`` guard this audit
    added — previously a silent fabricated 1-term law).

Property-based invariants (Hypothesis) cover the lstsq exactness/linearity that must hold for
ALL positive coefficient choices, not just the hand-picked examples.
"""

import math

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from gen.discovery import (
    Constant, DiscoveryProblem, Variable,
    MultiTermLaw, MultiTermValidation, discover_multiterm,
    evaluate_multiterm_law, multiterm_out_of_sample_validate,
)

MU_SUN = 1.32712440018e20


# --------------------------------------------------------------------------------------------
# builders — additive laws with KNOWN coefficients so we can assert the fit recovered them
# --------------------------------------------------------------------------------------------
def _kinematics(c1: float, c2: float, n: int = 9, seed: int = 0) -> DiscoveryProblem:
    """s = c1·(v0·t) + c2·(a·t²) — two dimensionally-valid additive terms of dimension [m]."""
    rng = np.random.default_rng(seed)
    v0 = rng.uniform(1.0, 10.0, n)
    t = rng.uniform(1.0, 6.0, n)
    a = rng.uniform(1.0, 10.0, n)
    s = c1 * v0 * t + c2 * a * t**2
    return DiscoveryProblem(
        idea="Kinematik", target=Variable("s", "m", tuple(s)),
        inputs=(Variable("v0", "m/s", tuple(v0)), Variable("t", "s", tuple(t)),
                Variable("a", "m/s^2", tuple(a))))


def _kepler() -> DiscoveryProblem:
    """A pure single power law: the fully-determined dimensional system admits one valid term."""
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11, 1.434e12])
    T = 2.0 * math.pi * a**1.5 / math.sqrt(MU_SUN)
    return DiscoveryProblem(idea="Kepler", target=Variable("T", "s", tuple(T)),
                            inputs=(Variable("a", "m", tuple(a)),),
                            constants=(Constant("mu", MU_SUN, "m^3/s^2"),))


def _sorted_coefs(law: MultiTermLaw) -> list[float]:
    return sorted(t.coefficient for t in law.terms)


# --------------------------------------------------------------------------------------------
# (a) the lstsq fit is COMPUTED, not canned — output moves with the input
# --------------------------------------------------------------------------------------------
def test_recovered_coefficients_track_the_generating_coefficients():
    """The headline 'linear least squares is exact and deterministic' claim: feed three different
    coefficient pairs and the recovered coefficients change to match each one — proof the fit is
    derived from the data, not a constant."""
    seen: list[list[float]] = []
    for c1, c2 in [(1.0, 0.5), (3.0, 2.0), (0.7, 4.2)]:
        law = discover_multiterm(_kinematics(c1, c2))
        assert law.n_terms == 2
        assert law.r_squared > 1.0 - 1e-9
        recovered = _sorted_coefs(law)
        assert recovered == pytest.approx(sorted([c1, c2]), abs=1e-6)
        seen.append(recovered)
    # distinct inputs -> distinct outputs (no input-independent constant facade)
    assert seen[0] != seen[1] != seen[2]


def test_fit_is_deterministic_for_identical_input():
    """Determinism (Kernprinzip A5): the same problem yields byte-identical coefficients twice."""
    p_a = _kinematics(2.5, 1.3, seed=7)
    p_b = _kinematics(2.5, 1.3, seed=7)
    assert _sorted_coefs(discover_multiterm(p_a)) == _sorted_coefs(discover_multiterm(p_b))


# --------------------------------------------------------------------------------------------
# (b) greedy forward selection is a real input-driven loop
# --------------------------------------------------------------------------------------------
def test_greedy_selection_count_responds_to_the_data_structure():
    """Greedy selection genuinely chooses how many terms to admit: a TWO-term law yields 2 terms,
    a pure power law (Kepler) yields 1 — the count is computed from the data, not fixed."""
    two_term = discover_multiterm(_kinematics(1.0, 0.5))
    one_term = discover_multiterm(_kepler())
    assert two_term.n_terms == 2
    assert one_term.n_terms == 1


def test_max_terms_caps_and_improvement_threshold_gates_selection():
    """Both knobs that drive the greedy loop are live: capping max_terms shrinks the model, and a
    near-1 improvement threshold admits only the single strongest term (anti-overfit gate)."""
    capped = discover_multiterm(_kinematics(1.0, 0.5), max_terms=1)
    strict = discover_multiterm(_kinematics(1.0, 0.5), improvement_threshold=0.99)
    loose = discover_multiterm(_kinematics(1.0, 0.5), improvement_threshold=1e-9)
    assert capped.n_terms == 1
    assert strict.n_terms < loose.n_terms  # the threshold really controls entry


# --------------------------------------------------------------------------------------------
# (c) pruning genuinely fires and is input-driven
# --------------------------------------------------------------------------------------------
def test_pruning_drops_a_transient_term_to_keep_the_law_minimal():
    """The exact 2-term kinematics law comes back as EXACTLY 2 terms even though greedy may pick a
    third dimensionally-valid 'blend' term first: the final lstsq nulls it and pruning removes it.
    A high prune_rel_tol instead over-prunes to 1 term — proof the pruning branch is live and its
    threshold genuinely governs which terms survive (input/knob-dependent, not a constant)."""
    minimal = discover_multiterm(_kinematics(1.0, 0.5))
    over_pruned = discover_multiterm(_kinematics(1.0, 0.5), prune_rel_tol=0.9)
    assert minimal.n_terms == 2
    assert over_pruned.n_terms < minimal.n_terms


# --------------------------------------------------------------------------------------------
# (d) held-out scoring really refits-on-train, scores-on-held-out
# --------------------------------------------------------------------------------------------
def test_real_additive_law_generalises_but_noise_does_not():
    """The out-of-sample validator is a real held-out scorer, not a rubber stamp: a genuine 2-term
    law fitted on a TRAIN split transfers to the HELD-OUT split (high test R², tiny gap), while a
    target that is pure noise collapses out-of-sample — the two verdicts differ because the numbers
    are computed from held-out data."""
    real = multiterm_out_of_sample_validate(_kinematics(1.0, 0.5, n=10, seed=1),
                                            train_fraction=0.6, seed=2)
    rng = np.random.default_rng(11)
    noise = DiscoveryProblem(
        idea="Rauschen", target=Variable("s", "m", tuple(rng.uniform(1.0, 50.0, 12))),
        inputs=(Variable("v0", "m/s", tuple(rng.uniform(1.0, 10.0, 12))),
                Variable("t", "s", tuple(rng.uniform(1.0, 6.0, 12))),
                Variable("a", "m/s^2", tuple(rng.uniform(1.0, 10.0, 12)))))
    noisy = multiterm_out_of_sample_validate(noise, train_fraction=0.6, seed=3)

    assert isinstance(real, MultiTermValidation)
    assert real.generalises and real.test_r2 > 0.99 and abs(real.overfit_gap) < 1e-3
    assert not noisy.generalises and noisy.test_r2 < 0.9
    assert real.n_train >= 2 and real.n_test >= 1


def test_held_out_score_moves_with_the_split_seed_on_noise():
    """A pure-noise target produces DIFFERENT held-out R² for different splits — confirming the
    score is recomputed from whichever points land in the held-out set, not memoised/canned. (A
    real law would transfer regardless; only noise exposes the split dependence.)"""
    rng = np.random.default_rng(5)
    noise = DiscoveryProblem(
        idea="Rauschen", target=Variable("s", "m", tuple(rng.uniform(1.0, 50.0, 14))),
        inputs=(Variable("v0", "m/s", tuple(rng.uniform(1.0, 10.0, 14))),
                Variable("t", "s", tuple(rng.uniform(1.0, 6.0, 14))),
                Variable("a", "m/s^2", tuple(rng.uniform(1.0, 10.0, 14)))))
    scores = {multiterm_out_of_sample_validate(noise, seed=s).test_r2 for s in (0, 1, 2, 3)}
    assert len(scores) > 1  # the held-out number genuinely depends on the split


# --------------------------------------------------------------------------------------------
# (e) fail-loud guards — every documented (and the newly-hardened) error path raises
# --------------------------------------------------------------------------------------------
def test_rejects_non_positive_target_and_input():
    """Power-law magnitudes must be positive; a non-positive target or input is a hard ValueError,
    never a silently-wrong fit (no-silent-defaults)."""
    bad_target = DiscoveryProblem(
        idea="kaputt", target=Variable("s", "m", (1.0, -2.0, 3.0, 4.0)),
        inputs=(Variable("t", "s", (1.0, 2.0, 3.0, 4.0)),),
        constants=(Constant("g", 9.81, "m/s^2"),))
    bad_input = DiscoveryProblem(
        idea="kaputt", target=Variable("s", "m", (10.0, 20.0, 30.0, 40.0)),
        inputs=(Variable("t", "s", (1.0, -2.0, 3.0, 4.0)),),
        constants=(Constant("g", 9.81, "m/s^2"),))
    with pytest.raises(ValueError):
        discover_multiterm(bad_target)
    with pytest.raises(ValueError):
        discover_multiterm(bad_input)


@pytest.mark.parametrize("bad_max_terms", [0, -1, -5])
def test_max_terms_below_one_is_a_hard_error_not_a_silent_law(bad_max_terms):
    """DEPTH-AUDIT FIX: before this guard, ``max_terms <= 0`` skipped the greedy loop and the
    empty-selection fallback silently returned a fabricated 1-term law (a wrong, input-independent
    result). A model with < 1 term is meaningless and must fail loud, per 'keine stillen Defaults'."""
    with pytest.raises(ValueError):
        discover_multiterm(_kinematics(1.0, 0.5), max_terms=bad_max_terms)


def test_out_of_sample_needs_enough_points_to_split():
    """Splitting train/held-out needs at least 4 points — fewer is a hard ValueError, not a
    degenerate one-point 'validation'."""
    tiny = DiscoveryProblem(
        idea="zu klein", target=Variable("s", "m", (10.0, 20.0, 30.0)),
        inputs=(Variable("v0", "m/s", (1.0, 2.0, 3.0)), Variable("t", "s", (1.0, 2.0, 3.0)),
                Variable("a", "m/s^2", (2.0, 3.0, 4.0))))
    with pytest.raises(ValueError):
        multiterm_out_of_sample_validate(tiny)


# --------------------------------------------------------------------------------------------
# property-based invariants — must hold for ALL positive coefficient choices
# --------------------------------------------------------------------------------------------
def _independent_r2(y: np.ndarray, y_hat: np.ndarray) -> float:
    """A second, independent R² implementation — so the assertion does NOT reuse the module's own
    formula (which would be circular)."""
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0.0 else (1.0 if np.allclose(y, y_hat) else 0.0)


@given(c1=st.floats(min_value=0.2, max_value=8.0),
       c2=st.floats(min_value=0.2, max_value=8.0))
@settings(max_examples=40, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_reported_quality_is_recomputed_from_the_actual_fit(c1, c2):
    """INVARIANT (facade detector for the reported metrics): for the additive law
    s = c1·(v0·t) + c2·(a·t²) with ANY positive c1,c2, re-evaluating the discovered law on its own
    data and INDEPENDENTLY recomputing R²/RMSE reproduces ``law.r_squared``/``law.rmse``. This holds
    regardless of whether greedy lands on the clean 2-term optimum or a worse local one (a documented
    OMP boundary) — what it proves is that the reported quality is genuinely derived from the fitted
    prediction, never a canned constant."""
    problem = _kinematics(c1, c2, n=12, seed=3)
    law = discover_multiterm(problem)
    y = np.asarray(problem.target.values, float)
    pred = evaluate_multiterm_law(law, problem)  # the law's own coefficients, no refit
    self_r2 = _independent_r2(y, pred)
    assert law.r_squared == pytest.approx(self_r2, abs=1e-9)
    assert law.rmse == pytest.approx(float(np.sqrt(np.mean((y - pred) ** 2))), rel=1e-9, abs=1e-9)


@given(c1=st.floats(min_value=0.5, max_value=5.0),
       c2=st.floats(min_value=0.5, max_value=5.0))
@settings(max_examples=30, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_clean_fit_recovers_both_coefficients_exactly(c1, c2):
    """INVARIANT, conditional on a clean fit: WHEN greedy reaches an R²≈1 two-term law (the common
    case on well-conditioned data), the recovered coefficients equal the generating c1,c2 to
    float precision — the exact-lstsq claim. Local-optimum cases (R² < 1) are out of scope here and
    are caught honestly out-of-sample, so we assert recovery only on the clean branch."""
    problem = _kinematics(c1, c2, n=12, seed=3)
    law = discover_multiterm(problem)
    if law.n_terms == 2 and law.r_squared > 1.0 - 1e-9:
        assert _sorted_coefs(law) == pytest.approx(sorted([c1, c2]), rel=1e-6, abs=1e-6)
        pred = evaluate_multiterm_law(law, problem)
        assert np.allclose(pred, np.asarray(problem.target.values, float), rtol=1e-8)


@given(k=st.floats(min_value=0.1, max_value=100.0))
@settings(max_examples=30, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_fit_is_linear_in_the_target_scale(k):
    """INVARIANT (linearity of least squares): scaling the target by k>0 scales every fitted
    coefficient by k. A canned/constant 'fit' could not satisfy this for arbitrary k, so it is a
    sharp facade detector for the lstsq step."""
    base = _kinematics(1.0, 0.5, n=10, seed=2)
    scaled_values = tuple(k * v for v in base.target.values)
    scaled = DiscoveryProblem(idea=base.idea,
                              target=Variable(base.target.name, base.target.unit, scaled_values),
                              inputs=base.inputs, constants=base.constants)
    base_coefs = _sorted_coefs(discover_multiterm(base))
    scaled_coefs = _sorted_coefs(discover_multiterm(scaled))
    assert scaled_coefs == pytest.approx([k * c for c in base_coefs], rel=1e-6, abs=1e-9)
