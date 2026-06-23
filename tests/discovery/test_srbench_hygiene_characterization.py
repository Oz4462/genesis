"""Characterization test for srbench_hygiene.py — proves the module is not a facade.

Headline contract exercised:
- leakage prevention (explicit check + split_overlap metric == 0 for internal OOS)
- out-of-sample truly held-out (recomputed test_r2 from train-derived law matches reported)
- dummy excluded + generalises for real law; rejects noise
- deterministic + error paths (negative tests)

One new authoritative test file; leaves legacy test_discovery_srbench_hygiene.py untouched.
Uses only pre-existing modules + stdlib + declared deps (numpy, hypothesis).
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given, strategies as st

from gen.discovery import DiscoveryProblem, Variable
from gen.discovery.benchmark import kepler_case
from gen.discovery.srbench_hygiene import (
    HygieneReport,
    check_train_test_overlap,
    assert_no_split_leakage,
    dummy_variable_test,
    hygiene_gate,
)


# --- helpers for proving "real held-out" (replicate split + recompute) --------------------

def _replicate_split(n: int, train_fraction: float = 0.6, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Exact mirror of validation._split so characterization can prove held-out application."""
    k = max(2, min(n - 1, int(round(n * train_fraction))))
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n)
    return np.sort(perm[:k]), np.sort(perm[k:])


def _subproblem(problem: DiscoveryProblem, idx: np.ndarray) -> DiscoveryProblem:
    """Exact mirror of validation._subproblem (allowed in test; proves the numbers)."""
    y = np.asarray(problem.target.values, float)
    return DiscoveryProblem(
        idea=problem.idea,
        target=Variable(problem.target.name, problem.target.unit, tuple(y[idx])),
        inputs=tuple(
            Variable(v.name, v.unit, tuple(np.asarray(v.values, float)[idx])) for v in problem.inputs
        ),
        constants=problem.constants,
        run_id=problem.run_id,
    )


def _r2(y: np.ndarray, y_hat: np.ndarray) -> float:
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
    if ss_tot <= 0.0:
        return 1.0 if np.allclose(y, y_hat) else 0.0
    return 1.0 - ss_res / ss_tot


# --- facade-killer tests -------------------------------------------------------------------

def test_clean_kepler_is_accepted_with_real_oos_and_zero_overlap():
    """Clean real law: hygiene accepts, dummy excluded, oos high, split_overlap==0 (no leakage)."""
    prob = kepler_case().problem
    report = hygiene_gate(prob)
    assert isinstance(report, HygieneReport)
    assert report.passed is True
    assert report.dummy_excluded is True
    assert report.dummy_exponent < 1e-3
    assert report.generalises is True
    assert report.oos_test_r2 > 0.99
    assert report.split_overlap == 0, "OOS must be computed on truly held-out rows"


def test_deliberate_leakage_is_detected_by_checker_and_rejected():
    """Deliberate leakage scenario: overlapping rows -> checker detects (non-zero), assert fails loud.
    A 'clean' claim contradicted by actual overlap must fail the gate (here: the explicit guard).
    """
    leaky_train = (0, 1, 2, 3)
    leaky_test = (2, 3, 4, 5)  # overlap on 2,3
    overlap = check_train_test_overlap(leaky_train, leaky_test)
    assert overlap == 2, "leakage metric must be real and count shared rows"

    with pytest.raises(ValueError, match="train/test leakage detected: 2 overlapping rows"):
        assert_no_split_leakage(leaky_train, leaky_test)

    # clean indices accepted
    clean_train = (0, 1, 2)
    clean_test = (3, 4, 5)
    assert check_train_test_overlap(clean_train, clean_test) == 0
    assert_no_split_leakage(clean_train, clean_test)  # does not raise


def test_hygiene_rejects_pure_noise_and_split_is_still_clean():
    """Noise target: hygiene rejects (generalises=False) even if a full-data 'leaky' fit
    might appear plausible; the internal split remains leak-free (split_overlap==0).
    """
    p = kepler_case().problem
    n = len(p.target.values)
    rng = np.random.default_rng(42)
    # pure noise target with same structure
    noise_y = tuple(rng.uniform(1e6, 1e7, size=n))
    noise_prob = DiscoveryProblem(
        idea="pure noise target for leakage hygiene",
        target=Variable(p.target.name, p.target.unit, noise_y),
        inputs=p.inputs,
        constants=p.constants,
        run_id="noise-leak-test",
    )
    report = hygiene_gate(noise_prob)
    assert report.passed is False
    assert report.generalises is False
    assert report.split_overlap == 0


def test_small_problem_raises_documented_error_negative_test():
    """Negative: missing split (n<4) produces documented ValueError, not silent wrong value."""
    small = DiscoveryProblem(
        idea="too few points",
        target=Variable("y", "1", (1.0, 2.0, 3.0)),
        inputs=(Variable("x", "1", (1.0, 2.0, 3.0)),),
        run_id="tiny",
    )
    with pytest.raises(ValueError, match="need at least 4 data points to split train/held-out"):
        hygiene_gate(small)


def test_oos_metric_is_real_held_out_not_leaked():
    """Prove the leakage metric + oos score are computed on truly held-out data.

    Replicate the exact split, fit ONLY on train sub, apply the exact train-derived
    (coeff + exponents) to test rows, recompute R² — must match the hygiene-reported oos_test_r2.
    If the implementation had peeked at test during fit, this would diverge.
    """
    prob = kepler_case().problem
    n = len(prob.target.values)
    seed = 0
    report = hygiene_gate(prob, seed=seed)
    assert report.split_overlap == 0

    # replicate what hygiene/OOS used
    train_idx, test_idx = _replicate_split(n, seed=seed)
    train_sub = _subproblem(prob, train_idx)
    from gen.discovery.engine import symbolic_regress  # pre-existing, allowed

    train_cand = symbolic_regress(train_sub)[0]

    # apply TRAIN law (no refit) to held-out
    y_test = np.asarray(prob.target.values, float)[test_idx]
    pred = np.full(len(test_idx), train_cand.coefficient, dtype=float)
    for v in prob.inputs:
        arr = np.asarray(v.values, float)[test_idx]
        pred = pred * np.power(arr, train_cand.exponents.get(v.name, 0.0))
    for c in prob.constants:
        pred = pred * np.power(float(c.value), train_cand.exponents.get(c.name, 0.0))

    recomputed = _r2(y_test, pred)
    # must match (within float noise); proves truly held-out application
    assert math.isclose(recomputed, report.oos_test_r2, rel_tol=1e-9, abs_tol=1e-12)


# --- property-based invariants (Hypothesis) -----------------------------------------------

@given(
    n=st.integers(min_value=5, max_value=30),
    seed=st.integers(min_value=0, max_value=1000),
)
def test_internal_oos_split_always_has_zero_overlap(n: int, seed: int):
    """Property: the split hygiene inside hygiene_gate is always leak-free (0 overlap)
    for any valid n>=5 and any seed (invariant of the deterministic split).
    """
    # build minimal positive problem with n samples (use simple 1-var power law)
    x = np.linspace(1.0, 5.0, n)
    y = 3.0 * x ** 2.0
    prob = DiscoveryProblem(
        idea="prop test power law",
        target=Variable("y", "1", tuple(y)),
        inputs=(Variable("x", "1", tuple(x)),),
        run_id=f"prop-{n}-{seed}",
    )
    report = hygiene_gate(prob, seed=seed)
    assert report.split_overlap == 0


@given(
    train_idx=st.lists(st.integers(0, 50), min_size=0, max_size=20, unique=True).map(tuple),
    test_idx=st.lists(st.integers(0, 50), min_size=0, max_size=20, unique=True).map(tuple),
)
def test_check_overlap_is_exact_set_intersection(train_idx: tuple[int, ...], test_idx: tuple[int, ...]):
    """Property: check_train_test_overlap returns exactly the set intersection size
    (idempotent, symmetric, >=0).
    """
    overlap = check_train_test_overlap(train_idx, test_idx)
    expected = len(set(train_idx) & set(test_idx))
    assert overlap == expected
    assert overlap >= 0
    # symmetry
    assert check_train_test_overlap(test_idx, train_idx) == overlap


def test_hygiene_gate_is_deterministic_across_calls():
    """A5 reproducibility: same problem + same seed -> identical report (incl. overlap)."""
    prob = kepler_case().problem
    a = hygiene_gate(prob, seed=123)
    b = hygiene_gate(prob, seed=123)
    assert (a.passed, a.dummy_excluded, a.generalises, a.split_overlap) == (
        b.passed,
        b.dummy_excluded,
        b.generalises,
        b.split_overlap,
    )
    assert a.oos_test_r2 == b.oos_test_r2
