"""composition — minimal-correction discovery when sourced laws are composed.

The second complementary capability beyond a single discovered law (the first being
``active_resolution``). Engineers compose independently-verified laws — thermal + structural, two
drag regimes, superposed deflections — and ask: *does the naive composition actually hold, and if
not, what is the smallest correction?* This module answers that honestly.

Given the data for a target ``y`` and a BASELINE prediction ``y_base`` (the composition of known /
sourced laws, e.g. naive superposition), it forms the residual ``r = y − y_base`` and runs the SAME
dimensional symbolic regression as the rest of GENESIS — but scoped to the residual. The key point:
the residual is SIGNED (a difference), while a power-law term is a positive monomial, so the fit is
``r ≈ Σ Cᵢ·termᵢ`` with the SIGN carried by the (linear-least-squares) coefficients and every term
still dimensionally consistent with ``r``'s dimension (= ``y``'s dimension). Parsimony — greedy
selection + a significance gate — keeps the answer minimal.

The verdict is honest, under the δ-asymmetry (a correction is a CLAIM, so it needs evidence):
  * ``vollstaendig`` — WITHIN the additive dimensional monomial basis and the gate, no significant
    correction is found (the residual is noise, or any term is insignificant / does not cross-
    validate). This is NOT "the composition is physically complete": a correction outside the basis
    (multiplicative, transcendental, or a monomial off the lattice) would also read ``vollstaendig``.
  * ``korrektur_noetig`` — a dimensionally-valid term explains a real fraction of the residual,
    meaningfully improves the composed fit, AND survives leave-one-out. Reported as "superposition
    holds to ~X %, correction = …".

Offline, deterministic, numpy-only. Honest boundary: this finds an ADDITIVE dimensional correction
(power-law monomials of the inputs, optional intercept); a multiplicative or transcendental coupling
is out of scope here (compose with ``transcendental`` for the latter).

The significance gate (residual_explained >= 0.9 AND delta-R2 > 1e-3) is computed in-sample on the
provided points. With very few points a flexible term can fit structured noise to high residual_explained
by chance; the gate is reliable when n is comfortably larger than the degrees of freedom of the correction
terms (cf. multiterm's separate out-of-sample validator). Parsimony + the high 0.9 bar make spurious
"laws" from noise rare in the intended regime (n>=6..8 as in the acceptance cases).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .engine import DiscoveryProblem
from .multiterm import (
    DEFAULT_IMPROVEMENT_THRESHOLD, DEFAULT_PRUNE_REL_TOL, Term,
    _arrays, _fit, _format_term, _r2, _term_vector, candidate_term_exponents,
)

#: A correction is asserted only if it explains at least this fraction of the residual's variance
#: (so a power-law term that merely grazes noise is not promoted to a "coupling law").
DEFAULT_RESIDUAL_BAR = 0.9

#: ...and only if adding it improves the composed R²(y, y_base + correction) by at least this much.
DEFAULT_SIGNIFICANCE = 1e-3

#: ...AND the correction must survive leave-one-out cross-validation on the residual at/above this
#: R² — a real correction generalises out-of-fold; a term that merely fits structured noise on few
#: points collapses (often negative). This is the actual defence behind the in-sample bar above.
DEFAULT_LOO_BAR = 0.5


@dataclass(frozen=True)
class CompositionResult:
    """How well a composition of sourced laws explains the data, and the minimal correction it
    misses. ``baseline_r2`` is the naive composition alone; ``corrected_r2`` adds the correction;
    ``residual_explained`` is how much of the residual structure the correction captures;
    ``relative_correction`` is RMS(correction)/RMS(y) — "superposition holds to ~(1 − this)"."""

    baseline_r2: float
    corrected_r2: float
    residual_explained: float
    loo_r2: float                       # leave-one-out cross-validated R² of the correction on the residual
    relative_correction: float
    correction_terms: tuple[Term, ...]
    correction_expression: str
    verdict: str
    n_terms: int


def _greedy_correction(
    residual: np.ndarray,
    names: list[str],
    arrs: list[np.ndarray],
    candidates: list[dict[str, float]],
    *,
    with_intercept: bool,
    max_terms: int,
    improvement_threshold: float,
    prune_rel_tol: float,
) -> tuple[list[tuple[dict[str, float], bool]], np.ndarray]:
    """Greedy forward selection of dimensionally-valid terms fitting the SIGNED residual (sign in
    the coefficients), with zero-contribution pruning. Returns (selected (exps, is_intercept), pred)."""
    pool: list[tuple[dict[str, float], bool, np.ndarray]] = [
        (exps, False, _term_vector(exps, names, arrs)) for exps in candidates]
    if with_intercept:
        pool.append(({}, True, np.ones_like(residual)))
    if not pool:
        return [], np.zeros_like(residual)

    selected: list[tuple[dict[str, float], bool, np.ndarray]] = []
    best_r2 = -np.inf
    while len(selected) < max_terms:
        best_gain: tuple[float, int] | None = None
        for i, cand in enumerate(pool):
            if any(cand[2] is s[2] for s in selected):
                continue
            cols = [s[2] for s in selected] + [cand[2]]
            try:
                _coef, pred = _fit(cols, residual)
            except np.linalg.LinAlgError:
                continue
            r2 = _r2(residual, pred)
            if r2 > best_r2 + improvement_threshold and (best_gain is None or r2 > best_gain[0]):
                best_gain = (r2, i)
        if best_gain is None:
            break
        best_r2 = best_gain[0]
        selected.append(pool[best_gain[1]])

    if not selected:
        return [], np.zeros_like(residual)

    coefs, pred = _fit([s[2] for s in selected], residual)
    contributions = [abs(float(c)) * float(np.mean(np.abs(s[2]))) for c, s in zip(coefs, selected)]
    cutoff = prune_rel_tol * max(contributions) if contributions else 0.0
    kept = [s for s, contrib in zip(selected, contributions) if contrib >= cutoff]
    if kept and len(kept) < len(selected):
        selected = kept
        coefs, pred = _fit([s[2] for s in selected], residual)
    return [(exps, is_int) for exps, is_int, _v in selected], pred


def _leave_one_out_r2(residual: np.ndarray, term_vectors: list[np.ndarray]) -> float:
    """Leave-one-out cross-validated R² of the selected correction structure on the residual: refit
    the coefficients on n−1 points, predict the held-out point, accumulate. A real correction
    generalises (LOO R² near the in-sample R²); a structure fitting noise on few points collapses
    out-of-fold (often negative). Returns 0.0 when there are too few points to cross-validate."""
    n = residual.shape[0]
    if n < 3 or not term_vectors:
        return 0.0
    x = np.column_stack(term_vectors)
    idx = np.arange(n)
    loo = np.empty(n)
    for j in range(n):
        mask = idx != j
        try:
            coef, *_ = np.linalg.lstsq(x[mask], residual[mask], rcond=None)
        except np.linalg.LinAlgError:
            return 0.0
        loo[j] = float(x[j] @ coef)
    return _r2(residual, loo)


def discover_correction(
    problem: DiscoveryProblem,
    baseline_prediction,
    *,
    max_terms: int = 2,
    with_intercept: bool = True,
    improvement_threshold: float = DEFAULT_IMPROVEMENT_THRESHOLD,
    prune_rel_tol: float = DEFAULT_PRUNE_REL_TOL,
    residual_bar: float = DEFAULT_RESIDUAL_BAR,
    significance: float = DEFAULT_SIGNIFICANCE,
    loo_bar: float = DEFAULT_LOO_BAR,
    max_abs_exp: float = 2.0,
    step: float = 0.5,
) -> CompositionResult:
    """Discover the minimal dimensional correction a composed/baseline prediction misses.

    ``baseline_prediction`` is the naive composition of sourced laws (same length as the target).
    Fits an additive dimensional correction ``Σ Cᵢ·termᵢ`` to the SIGNED residual ``y − y_base`` and
    returns an honest verdict: ``korrektur_noetig`` only if the correction explains ≥ `residual_bar`
    of the residual variance, improves the composed R² by > `significance`, AND survives leave-one-out
    at ≥ `loo_bar` (so structured noise grazing the in-sample bar on few points is rejected out-of-
    fold); otherwise ``vollstaendig`` (no correction asserted — within the additive monomial basis).
    Raises ValueError on a length mismatch or non-positive input magnitudes (the power-law domain is
    positive)."""
    y = np.asarray(problem.target.values, dtype=float)
    y_base = np.asarray(baseline_prediction, dtype=float)
    if y_base.shape != y.shape:
        raise ValueError(f"baseline_prediction length {y_base.shape} != target length {y.shape}")

    residual = y - y_base
    baseline_r2 = _r2(y, y_base)
    names, arrs = _arrays(problem)
    candidates = candidate_term_exponents(problem, max_abs_exp=max_abs_exp, step=step)

    selected, correction_pred = _greedy_correction(
        residual, names, arrs, candidates, with_intercept=with_intercept, max_terms=max_terms,
        improvement_threshold=improvement_threshold, prune_rel_tol=prune_rel_tol)

    term_vectors = [_term_vector(exps, names, arrs) if not is_int else np.ones_like(residual)
                    for exps, is_int in selected]
    residual_explained = _r2(residual, correction_pred) if selected else 0.0
    loo_r2 = _leave_one_out_r2(residual, term_vectors) if selected else 0.0
    corrected_pred = y_base + correction_pred
    corrected_r2 = _r2(y, corrected_pred)
    rms_y = float(np.sqrt(np.mean(y**2)))
    relative_correction = float(np.sqrt(np.mean(correction_pred**2)) / rms_y) if rms_y > 0 else 0.0

    # δ-asymmetry: a correction is a CLAIM. It must (1) explain almost all the residual in-sample,
    # (2) meaningfully improve the composed fit, AND (3) survive leave-one-out — so structured noise
    # that grazes the in-sample bar on few points is rejected out-of-fold, not promoted to a law.
    significant = ((residual_explained >= residual_bar)
                   and (corrected_r2 - baseline_r2 > significance)
                   and (loo_r2 >= loo_bar))

    if significant and selected:
        coefs, _ = _fit(term_vectors, residual)
        terms = tuple(Term(coefficient=float(c), exponents=dict(exps), is_intercept=is_int)
                      for c, (exps, is_int) in zip(coefs, selected))
        expr = "Korrektur = " + " + ".join(
            _format_term(t.coefficient, t.exponents, t.is_intercept) for t in terms)
        verdict = "korrektur_noetig"
    else:
        terms = ()
        expr = "Korrektur = (keine signifikante)"
        verdict = "vollstaendig"

    return CompositionResult(
        baseline_r2=baseline_r2, corrected_r2=corrected_r2, residual_explained=residual_explained,
        loo_r2=loo_r2, relative_correction=relative_correction, correction_terms=terms,
        correction_expression=expr, verdict=verdict, n_terms=len(terms))
