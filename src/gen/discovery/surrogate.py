"""surrogate — the Physics Foundation Layer: cheap PREFILTER + general surrogate approximator.

Two related but distinct capabilities (both obey "approximates only, never confirms"):

1. Discovery prefilter (original): surrogate_score / prefilter / discover_prefiltered use
   sub-sample R² to cheaply rank symbolic candidates before the expensive symbolic gate.
   A dimensionally-wrong candidate can score high; only the gate decides bestaetigt/widerlegt.

2. General function surrogate (added for the approximation claim): build_surrogate trains on
   samples (X, y) of a (possibly expensive) physics/objective function. predict_surrogate
   returns mean + uncertainty for new points. The model is a cheap stand-in that must be
   quantifiably accurate on held-out data and must be *honest* on extrapolation (high unc).

Common contract (Risk 2 / no-silent-defaults):
- Never emits a gate verdict or "confirmed" claim.
- Deterministic for fixed seed/hyperparams/data.
- numpy only. Fails loud on bad inputs (non-finite, insufficient data, dim mismatch).
- Uncertainty (when provided) grows with distance from training support.

See also: engine.py for the symbolic discovery that may use the prefilter.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .engine import (
    Candidate,
    DiscoveryProblem,
    DiscoveryResult,
    Variable,
    candidate_from_exponents,
    judge_candidate,
    symbolic_regress,
)

#: Default fraction of the data the surrogate fits on (cheaper than the full gate).
DEFAULT_SAMPLE_FRACTION = 0.5


@dataclass(frozen=True)
class SurrogateRanking:
    """A candidate plus its cheap surrogate score (sub-sample R²) — NOT a verdict."""

    candidate: Candidate
    surrogate_score: float


def _subsample_problem(problem: DiscoveryProblem, sample_fraction: float, seed: int) -> DiscoveryProblem:
    """A deterministic random SUB-SAMPLE of the problem's data points (constants unchanged)."""
    y = np.asarray(problem.target.values, dtype=float)
    n = y.shape[0]
    k = max(2, min(n, int(round(n * sample_fraction))))
    rng = np.random.default_rng(seed)
    idx = np.sort(rng.choice(n, size=k, replace=False))
    return DiscoveryProblem(
        idea=problem.idea,
        target=Variable(problem.target.name, problem.target.unit, tuple(y[idx])),
        inputs=tuple(Variable(v.name, v.unit, tuple(np.asarray(v.values, float)[idx]))
                     for v in problem.inputs),
        constants=problem.constants,
        run_id=problem.run_id,
    )


def surrogate_score(
    problem: DiscoveryProblem,
    candidate: Candidate,
    *,
    sample_fraction: float = DEFAULT_SAMPLE_FRACTION,
    seed: int = 0,
) -> float:
    """A CHEAP promise score for a candidate: refit its coefficient on a random sub-sample and
    return the sub-sample R². Fast (half the data) and dimension-blind — a high score is a hint
    to spend gate budget here, NOT a confirmation. Deterministic for a fixed seed."""
    if sample_fraction <= 0.0 or sample_fraction > 1.0:
        raise ValueError("sample_fraction must be in (0, 1]")
    y = np.asarray(problem.target.values, dtype=float)
    if y.shape[0] < 2:
        raise ValueError("surrogate_score requires a DiscoveryProblem with at least 2 data points")
    sub = _subsample_problem(problem, sample_fraction, seed)
    return candidate_from_exponents(sub, candidate.exponents).r_squared


def prefilter(
    problem: DiscoveryProblem,
    candidates: list[Candidate],
    *,
    top_k: int | None = None,
    min_score: float = 0.0,
    sample_fraction: float = DEFAULT_SAMPLE_FRACTION,
    seed: int = 0,
) -> list[SurrogateRanking]:
    """Score every candidate cheaply and return the most promising ones (those scoring at least
    `min_score`, then the best `top_k`), ranked best first. A RANKED SUBSET for the expensive
    gate — never a verdict, never a confirmation."""
    if sample_fraction <= 0.0 or sample_fraction > 1.0:
        raise ValueError("sample_fraction must be in (0, 1]")
    y = np.asarray(problem.target.values, dtype=float)
    if y.shape[0] < 2:
        raise ValueError("prefilter requires a DiscoveryProblem with at least 2 data points")
    ranked = [SurrogateRanking(c, surrogate_score(problem, c, sample_fraction=sample_fraction, seed=seed))
              for c in candidates]
    ranked = [r for r in ranked if r.surrogate_score >= min_score]
    ranked.sort(key=lambda r: -r.surrogate_score)
    return ranked if top_k is None else ranked[:top_k]


def discover_prefiltered(
    problem: DiscoveryProblem,
    *,
    top_k: int | None = None,
    min_score: float = 0.0,
    sample_fraction: float = DEFAULT_SAMPLE_FRACTION,
    seed: int = 0,
    known_laws: dict[str, dict[str, float]] | None = None,
) -> DiscoveryResult:
    """symbolic_regress → surrogate PREFILTER → gate ONLY the survivors. The validated set
    contains only gate-passed candidates (the surrogate merely saved compute on the losers);
    every gated candidate is still recorded. The gate, not the surrogate, decides."""
    candidates = symbolic_regress(problem)
    survivors = prefilter(problem, candidates, top_k=top_k, min_score=min_score,
                          sample_fraction=sample_fraction, seed=seed)
    records = tuple(judge_candidate(problem, r.candidate, known_laws=known_laws) for r in survivors)
    validated = tuple(sorted((r for r in records if r.passed),
                             key=lambda r: (-r.candidate.r_squared, r.candidate.complexity)))
    return DiscoveryResult(problem_idea=problem.idea, validated=validated,
                           all_records=records, run_id=problem.run_id)


# --- General physics / objective surrogate (quantifiable approximation of expensive f) ---
# Added to make the module's headline claim hold: a surrogate that can be *trained* on
# samples of a known (possibly expensive-to-evaluate) function and then cheaply predict
# held-out points with a bounded error and a monotone uncertainty signal.
# This is orthogonal to (and composable with) the discovery prefilter above.
# The surrogate approximates only; it is a prefilter/accelerator, never a replacement
# for exact evaluation or the symbolic gate. Deterministic given data + hyperparameters.
# Uses only numpy (declared dep).

@dataclass(frozen=True)
class Surrogate:
    """A trained, deterministic surrogate model for a scalar expensive function.

    Approximates y ≈ f(X) from finite samples. Provides predictions + uncertainty
    estimate that grows with distance from training support (L4 edge honesty).
    Never returns a confirmation or gate verdict.
    """

    X: np.ndarray  # (n, d) copy of the training inputs provided to build_surrogate
    y: np.ndarray  # (n,) training targets
    centers: np.ndarray
    weights: np.ndarray
    length_scale: float
    reg: float


def build_surrogate(
    X: np.ndarray | list[list[float]] | list[float],
    y: np.ndarray | list[float],
    *,
    length_scale: float = 1.0,
    reg: float = 1e-8,
) -> Surrogate:
    """Build (train) a surrogate approximator from samples of a known function.

    Args:
        X: training inputs, shape (n_samples, n_features) or (n_samples,) for 1D.
        y: training targets, shape (n_samples,).
        length_scale: RBF kernel length scale (controls smoothness/support).
        reg: small ridge regularizer for numerical stability.

    Returns:
        A Surrogate that supports predict_surrogate.

    Raises:
        ValueError: if fewer than 2 samples, shape mismatch, or non-finite data.
    """
    X_arr = np.asarray(X, dtype=float)
    y_arr = np.asarray(y, dtype=float).ravel()
    if X_arr.ndim == 1:
        X_arr = X_arr.reshape(-1, 1)
    n = X_arr.shape[0]
    if n < 2:
        raise ValueError("build_surrogate requires at least 2 training points to fit a surrogate")
    if y_arr.shape[0] != n:
        raise ValueError("X and y must have the same number of samples")
    if not np.all(np.isfinite(X_arr)) or not np.all(np.isfinite(y_arr)):
        raise ValueError("training inputs and targets must be finite (no NaN/inf)")
    if length_scale <= 0:
        raise ValueError("length_scale must be > 0")
    if reg < 0:
        raise ValueError("reg must be >= 0")

    # Store owned copies so the dataclass holds a stable snapshot (not a view that could be mutated by caller).
    X_stored = X_arr.copy()
    centers = X_arr.copy()
    # Pairwise squared distances, Gaussian (RBF) kernel
    # K_ij = exp( - ||x_i - c_j||^2 / (2 * ls^2) )
    deltas = X_arr[:, None, :] - centers[None, :, :]
    sq_dists = np.sum(deltas * deltas, axis=-1)
    K = np.exp(-sq_dists / (2.0 * length_scale * length_scale))
    K_reg = K + reg * np.eye(n)
    # Solve for weights; lstsq as stable fallback
    try:
        weights = np.linalg.solve(K_reg, y_arr)
    except np.linalg.LinAlgError:
        weights = np.linalg.lstsq(K_reg, y_arr, rcond=None)[0]
    return Surrogate(
        X=X_stored,
        y=y_arr.copy(),
        centers=centers,
        weights=weights,
        length_scale=float(length_scale),
        reg=float(reg),
    )


def predict_surrogate(
    model: Surrogate,
    X: np.ndarray | list[list[float]] | list[float],
) -> tuple[np.ndarray, np.ndarray]:
    """Predict mean and uncertainty at new points using the trained surrogate.

    Uncertainty heuristic is monotone increasing with distance to nearest training
    center. Far extrapolation therefore yields high uncertainty rather than
    spuriously confident predictions (negative-test contract).

    Returns:
        (y_mean, uncertainty) with shapes (m,), (m,). uncertainty >=0 and grows outside support.
    """
    if not isinstance(model, Surrogate):
        raise ValueError("predict_surrogate expects a Surrogate from build_surrogate")
    X_arr = np.asarray(X, dtype=float)
    if X_arr.ndim == 1:
        X_arr = X_arr.reshape(-1, 1)
    if X_arr.shape[1] != model.X.shape[1]:
        raise ValueError(f"feature dimension mismatch: got {X_arr.shape[1]}, expected {model.X.shape[1]}")
    if X_arr.shape[0] == 0:
        return np.array([], dtype=float), np.array([], dtype=float)

    deltas = X_arr[:, None, :] - model.centers[None, :, :]
    sq_dists = np.sum(deltas * deltas, axis=-1)
    Knew = np.exp(-sq_dists / (2.0 * model.length_scale * model.length_scale))
    y_mean = Knew @ model.weights

    # Distance-based uncertainty: base floor + term proportional to min-distance / ls
    # This guarantees: far points have *higher* unc than near points.
    min_dists = np.min(np.sqrt(sq_dists), axis=1)
    unc = 0.05 + (min_dists / max(model.length_scale, 1e-12))
    return y_mean, unc
