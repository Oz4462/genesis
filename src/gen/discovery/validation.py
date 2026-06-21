"""validation — out-of-sample validation against p-hacking (build doc Phase 4, Risk 4).

A law that only fits the data it was fitted on proves nothing — that is the classic
p-hacking / overfitting trap. The honest guard is OUT-OF-SAMPLE validation: fit the law on a
TRAIN split and score it on a HELD-OUT split it never saw. A real law (Kepler from half the
planets) predicts the other half; a spurious fit does not.

GENESIS's dimensional constraint already makes the engine hard to overfit — a power-law
candidate has exactly ONE free parameter (the coefficient), the exponents being fixed by the
units — so this validation mostly CONFIRMS that dimensionally-constrained laws generalise, and
flags the cases where the power-law assumption simply does not hold (the target is not a power
law of the inputs). It applies the TRAIN-fitted coefficient to the held-out data — no peeking,
no refit — and reports the out-of-sample R². Offline, deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .engine import DiscoveryProblem, Variable, symbolic_regress

#: Held-out R² at/above which a law is judged to generalise.
DEFAULT_GENERALISES_R2 = 0.99


@dataclass(frozen=True)
class OutOfSampleResult:
    """Train vs held-out fit of the discovered law: `test_r2` is the law's R² on data it was
    NOT fitted on (the honest number); `generalises` is the verdict; `overfit_gap` is
    train−test (large means the fit did not transfer)."""

    law: str
    train_r2: float
    test_r2: float
    overfit_gap: float
    generalises: bool
    n_train: int
    n_test: int


def _r2(y: np.ndarray, y_hat: np.ndarray) -> float:
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
    if ss_tot <= 0.0:
        return 1.0 if np.allclose(y, y_hat) else 0.0
    return 1.0 - ss_res / ss_tot


def _split(problem: DiscoveryProblem, train_fraction: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    n = len(problem.target.values)
    k = max(2, min(n - 1, int(round(n * train_fraction))))
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n)
    return np.sort(perm[:k]), np.sort(perm[k:])


def _subproblem(problem: DiscoveryProblem, idx: np.ndarray) -> DiscoveryProblem:
    y = np.asarray(problem.target.values, float)
    return DiscoveryProblem(
        idea=problem.idea,
        target=Variable(problem.target.name, problem.target.unit, tuple(y[idx])),
        inputs=tuple(Variable(v.name, v.unit, tuple(np.asarray(v.values, float)[idx]))
                     for v in problem.inputs),
        constants=problem.constants, run_id=problem.run_id)


def out_of_sample_validate(
    problem: DiscoveryProblem,
    *,
    train_fraction: float = 0.6,
    r2_threshold: float = DEFAULT_GENERALISES_R2,
    seed: int = 0,
) -> OutOfSampleResult:
    """Fit the law on a TRAIN split and score it, unchanged, on the HELD-OUT split.

    Discovers the best candidate on the train data (its exponents AND its train-fitted
    coefficient), then applies that exact law to the held-out inputs and reports the
    out-of-sample R². `generalises` is True iff the held-out R² clears `r2_threshold` — a real
    law transfers, a spurious one does not. Raises ValueError on too few points to split or on
    non-positive magnitudes (via the engine)."""
    n = len(problem.target.values)
    if n < 4:
        raise ValueError("need at least 4 data points to split train/held-out")
    train_idx, test_idx = _split(problem, train_fraction, seed)

    train_cand = symbolic_regress(_subproblem(problem, train_idx))[0]   # exponents + train coefficient

    # apply the TRAIN law to the held-out data — no refit
    y = np.asarray(problem.target.values, float)
    y_test = y[test_idx]
    pred = np.full(test_idx.shape[0], train_cand.coefficient, dtype=float)
    for v in problem.inputs:
        arr = np.asarray(v.values, float)[test_idx]
        pred = pred * np.power(arr, train_cand.exponents.get(v.name, 0.0))
    for c in problem.constants:
        pred = pred * np.power(float(c.value), train_cand.exponents.get(c.name, 0.0))

    test_r2 = _r2(y_test, pred)
    return OutOfSampleResult(
        law=train_cand.expression, train_r2=train_cand.r_squared, test_r2=test_r2,
        overfit_gap=train_cand.r_squared - test_r2,
        generalises=test_r2 >= r2_threshold,
        n_train=train_idx.shape[0], n_test=test_idx.shape[0])
