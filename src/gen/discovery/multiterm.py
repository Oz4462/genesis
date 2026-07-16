"""multiterm — additive multi-term discovery, the frontier beyond a single power law.

The base engine finds ONE dimensionally-constrained power law. Real laws are often a SUM of
terms: free fall ``v = g·t + v0``, kinematics ``s = v0·t + ½·a·t²``, a series expansion. This
module extends discovery to additive models ``y = Σ Cᵢ·termᵢ (+ intercept)`` while keeping the
two things that make GENESIS honest:

  * EVERY term is dimensionally consistent — you can only add quantities of the SAME dimension.
    Each ENUMERATED candidate term is a power-law product whose exponents satisfy the SAME
    dimensional equation ``A·p = b`` as the target, over a bounded exponent lattice (so Kepler's
    ½-integer exponents and kinematics' integer exponents are both reachable). The optional
    INTERCEPT is the ONE exception to ``A·p = b``: a fitted constant that carries the target's
    dimension BY CONSTRUCTION (a real model parameter, labelled ``is_intercept``, never a sourced
    fact) — dimensionally consistent without being a lattice point.
  * PARSIMONY guards against overfitting. A multi-term model has more free coefficients and so
    CAN fit noise — the opposite of the single-power-law's built-in safety. Terms are added by
    greedy forward selection (orthogonal-matching-pursuit style) and a term is kept ONLY if it
    improves the fit by more than a threshold. So a pure power law (Kepler) comes back as ONE
    term, not a padded sum, and noise does not accrete spurious terms. The in-sample R² is NOT
    the final word: pair every discovered law with :func:`multiterm_out_of_sample_validate` (in
    this module), whose held-out R² catches both an overfit (spurious terms) and an over-pruned
    (a real term wrongly dropped) additive model.

The coefficients are fitted by LINEAR least squares (the model is linear in the Cᵢ), so the fit
is exact and deterministic. Offline, numpy-only. Two honest boundaries: (1) the final pruning is
a NUMERICAL threshold — it drops a term whose additive contribution is negligible *over the
sampled data* (below ``prune_rel_tol`` of the dominant term). That is the right call for a
greedy-picked term the exact fit then nulls to float-noise, but it is NOT a universal
physical-significance test: a term that is weak in-sample yet matters far outside it could be
dropped. (2) This covers SUMS of dimensionally-valid power-law terms (+ intercept) over a bounded
exponent lattice — it does not yet cover transcendental forms (sin/exp/log of a dimensionless
group), which need a dimensionless argument and are the next frontier.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np

from .engine import DiscoveryProblem, Variable, dimensional_system

#: Largest absolute exponent and lattice step for enumerating dimensionally-valid terms.
DEFAULT_MAX_ABS_EXP = 2.0
DEFAULT_STEP = 0.5

#: A term is kept only if it improves R² by at least this much (parsimony / anti-overfit).
DEFAULT_IMPROVEMENT_THRESHOLD = 1e-4

#: After the final fit, a term whose additive contribution is below this fraction of the dominant
#: term's magnitude *over the sampled data* is numerically negligible here (greedy can pick a term
#: the final lstsq then nulls to ~float-noise) and is pruned, so the law stays minimal (kinematics
#: -> exactly 2 terms, not 3). A sample-scale numerical threshold, NOT a universal significance test.
DEFAULT_PRUNE_REL_TOL = 1e-6

#: Residual of the dimensional system below which a term is dimensionally valid.
_DIM_TOL = 1e-9


@dataclass(frozen=True)
class Term:
    """One additive term: a fitted coefficient times a power-law product (or the intercept).
    `exponents` is empty for the intercept (`is_intercept=True`)."""

    coefficient: float
    exponents: dict[str, float]
    is_intercept: bool = False


@dataclass(frozen=True)
class MultiTermLaw:
    """A discovered additive law ``y = Σ Cᵢ·termᵢ`` with its fit quality and parsimony. Every
    term is dimensionally consistent; the expression renders the readable formula."""

    terms: tuple[Term, ...]
    r_squared: float
    rmse: float
    n_terms: int
    expression: str


def _arrays(problem: DiscoveryProblem) -> tuple[list[str], list[np.ndarray]]:
    n = len(problem.target.values)
    names: list[str] = []
    arrs: list[np.ndarray] = []
    for v in problem.inputs:
        a = np.asarray(v.values, dtype=float)
        if np.any(a <= 0.0):
            raise ValueError(f"input {v.name!r} has non-positive values; power-law terms need positive magnitudes")
        names.append(v.name)
        arrs.append(a)
    for c in problem.constants:
        if c.value <= 0.0:
            raise ValueError(f"constant {c.name!r} must be positive")
        names.append(c.name)
        arrs.append(np.full(n, float(c.value)))
    return names, arrs


def candidate_term_exponents(
    problem: DiscoveryProblem,
    *,
    max_abs_exp: float = DEFAULT_MAX_ABS_EXP,
    step: float = DEFAULT_STEP,
) -> list[dict[str, float]]:
    """Enumerate every dimensionally-VALID power-law term over a bounded exponent lattice: each
    returned exponent vector ``p`` satisfies ``A·p = b`` (the term has the target's dimension).
    Raises ValueError if the lattice would be too large (reduce the range/step)."""
    a_matrix, b_vec, names = dimensional_system(problem)
    grid = np.round(np.arange(-max_abs_exp, max_abs_exp + step / 2, step), 6)
    if len(grid) ** len(names) > 200_000:
        raise ValueError("exponent lattice too large; reduce max_abs_exp or raise step")
    valid: list[dict[str, float]] = []
    for combo in itertools.product(grid, repeat=len(names)):
        p = np.array(combo, dtype=float)
        if np.linalg.norm(a_matrix @ p - b_vec) < _DIM_TOL:
            valid.append({n: float(e) for n, e in zip(names, combo, strict=True)})
    return valid


def _term_vector(exps: dict[str, float], names: list[str], arrs: list[np.ndarray]) -> np.ndarray:
    pred = np.ones_like(arrs[0]) if arrs else np.ones(1)
    for name, arr in zip(names, arrs, strict=True):
        e = exps.get(name, 0.0)
        if e != 0.0:
            pred = pred * np.power(arr, e)
    return pred


def _format_term(coef: float, exps: dict[str, float], is_intercept: bool) -> str:
    if is_intercept:
        return f"{coef:.6g}"
    factors = [f"{coef:.6g}"]
    for name, e in exps.items():
        if abs(e) < 1e-9:
            continue
        factors.append(name if abs(e - 1.0) < 1e-9 else f"{name}^{e:g}")
    return " * ".join(factors)


def _r2(y: np.ndarray, y_hat: np.ndarray) -> float:
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
    if ss_tot <= 0.0:
        return 1.0 if np.allclose(y, y_hat) else 0.0
    return 1.0 - ss_res / ss_tot


def _fit(columns: list[np.ndarray], y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x = np.column_stack(columns)
    coef, *_ = np.linalg.lstsq(x, y, rcond=None)
    return coef, x @ coef


def discover_multiterm(
    problem: DiscoveryProblem,
    *,
    max_terms: int = 3,
    with_intercept: bool = True,
    improvement_threshold: float = DEFAULT_IMPROVEMENT_THRESHOLD,
    prune_rel_tol: float = DEFAULT_PRUNE_REL_TOL,
    max_abs_exp: float = DEFAULT_MAX_ABS_EXP,
    step: float = DEFAULT_STEP,
) -> MultiTermLaw:
    """Discover an additive law ``y = Σ Cᵢ·termᵢ (+ intercept)`` by greedy forward selection over
    the dimensionally-valid power-law terms. A term enters only if it improves R² by more than
    `improvement_threshold` (parsimony), so a pure power law stays a single term and noise does
    not accrete terms. Coefficients are fitted by linear least squares (exact, deterministic).
    Raises ValueError on non-positive magnitudes or an over-large lattice."""
    y = np.asarray(problem.target.values, dtype=float)
    if np.any(y <= 0.0):
        raise ValueError("target has non-positive values; additive power-law discovery needs positive magnitudes")
    names, arrs = _arrays(problem)

    pool: list[tuple[dict[str, float], bool, np.ndarray]] = [
        (exps, False, _term_vector(exps, names, arrs))
        for exps in candidate_term_exponents(problem, max_abs_exp=max_abs_exp, step=step)
    ]
    if with_intercept:
        pool.append(({}, True, np.ones_like(y)))

    selected: list[tuple[dict[str, float], bool, np.ndarray]] = []
    best_r2 = -np.inf
    best_pred = np.full_like(y, float(np.mean(y)))

    while len(selected) < max_terms:
        best_gain: tuple[float, int, np.ndarray, np.ndarray] | None = None
        for i, cand in enumerate(pool):
            if any(cand[2] is s[2] for s in selected):
                continue
            cols = [s[2] for s in selected] + [cand[2]]
            try:
                coef, pred = _fit(cols, y)
            except np.linalg.LinAlgError:
                continue
            r2 = _r2(y, pred)
            if r2 > best_r2 + improvement_threshold and (best_gain is None or r2 > best_gain[0]):
                best_gain = (r2, i, coef, pred)
        if best_gain is None:
            break
        best_r2 = best_gain[0]
        best_pred = best_gain[3]
        selected.append(pool[best_gain[1]])

    # final exact fit over the selected columns
    if not selected:
        # The greedy loop only fails to select a term when the pool is empty (no dimensionally-
        # valid term AND no intercept) or every fit was singular — never the normal case, since
        # the first iteration's -inf bar admits any finite-R² term. Empty pool is a hard error;
        # otherwise fall back to the FIRST enumerated term so we always return a usable law.
        if not pool:
            raise ValueError("no dimensionally-valid term exists for this target; check the units")
        selected = [pool[0]]
    coefs, best_pred = _fit([s[2] for s in selected], y)

    # prune terms the final lstsq nulled out (greedy can pick a locally-good term the exact fit
    # then zeroes): drop any term contributing < prune_rel_tol of the dominant term, then refit.
    contributions = [abs(float(c)) * float(np.mean(np.abs(s[2]))) for c, s in zip(coefs, selected, strict=True)]
    if contributions:
        cutoff = prune_rel_tol * max(contributions)
        kept = [s for s, contrib in zip(selected, contributions, strict=True) if contrib >= cutoff]
        if kept and len(kept) < len(selected):
            selected = kept
            coefs, best_pred = _fit([s[2] for s in selected], y)

    terms = tuple(Term(coefficient=float(c), exponents=dict(exps), is_intercept=is_int)
                  for c, (exps, is_int, _v) in zip(coefs, selected, strict=True))
    expr = f"{problem.target.name} = " + " + ".join(
        _format_term(t.coefficient, t.exponents, t.is_intercept) for t in terms)
    return MultiTermLaw(
        terms=terms, r_squared=_r2(y, best_pred),
        rmse=float(np.sqrt(np.mean((y - best_pred) ** 2))),
        n_terms=len(terms), expression=expr)


#: Held-out R² at/above which a multi-term law is judged to generalise (mirrors the single-law
#: validator's bar). Below it the additive model did not transfer — overfit OR over-pruned.
DEFAULT_GENERALISES_R2 = 0.99


@dataclass(frozen=True)
class MultiTermValidation:
    """Out-of-sample fit of an additive law: `test_r2` is the law's R² on data it was NOT fitted
    on (the honest number); `generalises` is the verdict; `overfit_gap` = train − test (large
    means the additive model — its terms AND its pruning — did not transfer)."""

    law: str
    train_r2: float
    test_r2: float
    overfit_gap: float
    generalises: bool
    n_train: int
    n_test: int
    n_terms: int


def evaluate_multiterm_law(law: MultiTermLaw, problem: DiscoveryProblem) -> np.ndarray:
    """Apply a discovered additive law to a problem's data — ``Σ Cᵢ·termᵢ`` evaluated on the
    inputs/constants, with the intercept (empty exponents → ones) carried uniformly. The primitive
    behind out-of-sample scoring: the law's coefficients are NOT refitted here. Raises ValueError
    on non-positive magnitudes (the power-law domain is positive)."""
    names, arrs = _arrays(problem)
    pred = np.zeros(len(problem.target.values), dtype=float)
    for term in law.terms:
        pred = pred + term.coefficient * _term_vector(term.exponents, names, arrs)
    return pred


def _split_indices(n: int, train_fraction: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
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


def multiterm_out_of_sample_validate(
    problem: DiscoveryProblem,
    *,
    train_fraction: float = 0.6,
    r2_threshold: float = DEFAULT_GENERALISES_R2,
    seed: int = 0,
    **discover_kwargs,
) -> MultiTermValidation:
    """Out-of-sample validation for an ADDITIVE law (the honest guard for the multi-term frontier).

    Discovers the multi-term law — its term structure, its pruning AND its train-fitted
    coefficients — on a TRAIN split, then scores it UNCHANGED on the HELD-OUT split (no refit, no
    peeking). The held-out R² catches BOTH failure modes the extra degrees of freedom open up:
    overfitting (spurious terms chasing the train data → test R² collapses) AND over-pruning (a
    real-but-weak term wrongly dropped → the pruned law under-fits the held-out data). A real
    additive law (kinematics from a subset of points) transfers; noise does not. ``discover_kwargs``
    are forwarded to :func:`discover_multiterm`. Raises ValueError on too few points to split."""
    n = len(problem.target.values)
    if n < 4:
        raise ValueError("need at least 4 data points to split train/held-out")
    train_idx, test_idx = _split_indices(n, train_fraction, seed)
    train_law = discover_multiterm(_subproblem(problem, train_idx), **discover_kwargs)
    test_problem = _subproblem(problem, test_idx)
    y_test = np.asarray(test_problem.target.values, float)
    pred = evaluate_multiterm_law(train_law, test_problem)
    test_r2 = _r2(y_test, pred)
    return MultiTermValidation(
        law=train_law.expression, train_r2=train_law.r_squared, test_r2=test_r2,
        overfit_gap=train_law.r_squared - test_r2,
        generalises=test_r2 >= r2_threshold,
        n_train=int(train_idx.shape[0]), n_test=int(test_idx.shape[0]), n_terms=train_law.n_terms)
