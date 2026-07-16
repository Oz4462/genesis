"""engine — dimensional symbolic regression + the discover_new_formulas loop.

The Phase-1 core of the build doc (Anhang B). Given an idea and observational data, the
engine proposes candidate formulas, but NOT by free-form LLM guessing: it uses the
DIMENSIONAL constraint to nail the functional form first (Buckingham-π / the AI-Feynman
insight), then fits the remaining dimensionless coefficient to the data, then runs the
candidate through the existing GENESIS gates.

The dimensional move, concretely (the Kepler example the Rediscovery benchmark pins):
seek the orbital period ``T`` [s] from the semi-major axis ``a`` [m] and the gravitational
parameter ``mu = G·M`` [m³·s⁻²]. A power-law product ``a^p · mu^q`` has dimension
``L^(p+3q)·T^(-2q)``; matching ``T`` = ``L^0·T^1`` forces ``p+3q = 0`` and ``-2q = 1`` →
``q = -1/2``, ``p = 3/2``. The dimensional analysis ALONE fixes the exponents; the fit only
finds the constant ``C ≈ 2π``. That is an honest, reproducible discovery, not a guess.

Every candidate (kept AND rejected) is scored and judged:
  * DIMENSIONAL gate (C-15 analogue) — does the power law actually match the target
    dimension? (residual of the exponent linear system ≈ 0). A target whose dimension
    cannot be formed from the inputs is ``widerlegt`` — the red-team case.
  * gate_c6 RECOMPUTE — independently re-evaluate the fitted formula on the data and
    confirm it reproduces the target within tolerance (the project's ``within_tolerance``).
  * FIT gate — the R² of the fit must clear a threshold (the formula must explain the
    data), and the δ-asymmetry RAISES that threshold with the candidate's complexity.
  * UNCERTAINTY — the residual scatter, so the verdict is honest about precision.

Verdict (the doc's three honest outcomes): ``widerlegt`` (dimensionally impossible),
``bestaetigt`` (dimension ok AND fit clears the δ-raised threshold), else ``unentschieden``.

Honest boundary: this MVP discovers POWER-LAW / Π-group relations of POSITIVE physical
magnitudes — the family that covers Kepler, the ideal gas law, Coulomb/Newton inverse
squares, etc. Sums of several terms, transcendental forms and sub-variable selection are a
declared extension (the Tournament loop widens the candidate space; full symbolic/GP search
is a Phase-1+ gap). Offline, deterministic, numpy + the existing units algebra only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

import numpy as np

from typing import TYPE_CHECKING, Callable

from ..verification.derivation import within_tolerance
from ..verification.symbolic import cross_check_power_law
from ..verification.units import Dimension, parse_unit

if TYPE_CHECKING:
    from .concept_utility import ConceptUtility
    from .separability import SeparabilityResult

#: Default fit-quality bar for a ``bestaetigt`` verdict (R² ≥ this, δ-raised per candidate).
DEFAULT_R2_THRESHOLD = 0.999

#: Residual of the dimensional exponent system below which the power law is dimensionally
#: consistent (the lstsq solve is on integer matrices, so a true solution is ~0).
DIMENSION_TOLERANCE = 1e-9

#: Largest denominator when rationalising fitted exponents for display/canonicalisation
#: (1.4999999998 -> 3/2). The dimensional solve is exact linear algebra, so exponents are
#: rationals; this only cleans float artefacts.
EXPONENT_MAX_DENOMINATOR = 24


@dataclass(frozen=True)
class Variable:
    """An observed quantity: a name, a unit (parsed by the units algebra) and its samples.

    `values` are the observations (one per data point); for the target and every input the
    arrays must be the same length. Magnitudes must be POSITIVE (a power law of a negative
    base is not real) — the engine rejects non-positive data loudly rather than return nan.
    """

    name: str
    unit: str
    values: tuple[float, ...]


@dataclass(frozen=True)
class Constant:
    """A known physical constant used as a search source (e.g. ``mu = G·M``). Broadcast to
    every data point; carries a unit so it participates in the dimensional solve."""

    name: str
    value: float
    unit: str


@dataclass(frozen=True)
class DiscoveryProblem:
    """A discovery task: an idea, the target to explain, the input variables, optional
    known constants, and a run id for provenance."""

    idea: str
    target: Variable
    inputs: tuple[Variable, ...]
    constants: tuple[Constant, ...] = ()
    run_id: str | None = None


@dataclass(frozen=True)
class Candidate:
    """A proposed power-law formula ``target = C · ∏ source_i^p_i`` and its quality.

    `exponents` maps each source name to its fitted exponent; `coefficient` is the fitted
    dimensionless ``C``; `r_squared`/`rmse` measure the fit; `complexity` is the number of
    sources with a non-zero exponent (parsimony); `dimension_ok` + `dimension_residual` are
    the dimensional-consistency verdict. `expression` is the human-readable rendering.
    """

    expression: str
    exponents: dict[str, float]
    coefficient: float
    r_squared: float
    rmse: float
    complexity: int
    dimension_ok: bool
    dimension_residual: float
    #: Independent SymPy cross-engine verdict: True = both engines agree the dimensions are consistent,
    #: False = they disagree (fail-closed -> dimension_ok is forced False), None = SymPy could not
    #: corroborate (opaque unit) so only the lstsq solve spoke. Provenance for the anti-hallucination gate.
    dimension_corroborated: bool | None = None


@dataclass(frozen=True)
class DiscoveryVerdict:
    """The honest judgement of one candidate: the candidate, whether it passed every gate,
    the three-way verdict, the per-gate detail, and the δ to consensus."""

    candidate: Candidate
    passed: bool
    verdict: str  # "bestaetigt" | "widerlegt" | "unentschieden"
    gates: dict[str, dict]
    delta_to_consensus: float


@dataclass(frozen=True)
class DiscoveryResult:
    """The result of a discovery run: the validated verdicts (best first) and the full
    record of every candidate (kept and rejected) for the Discovery Graph / Ledger."""

    problem_idea: str
    validated: tuple[DiscoveryVerdict, ...]
    all_records: tuple[DiscoveryVerdict, ...]
    run_id: str | None = None
    #: Optional AI-Feynman separability annotation: when ``discover_new_formulas`` is given a queryable
    #: ``target_fn``, the additive/multiplicative decomposition of the target into independent variable
    #: groups — structural provenance toward the declared multi-term/composition extension. ``None`` when
    #: no ``target_fn`` was supplied. Purely informational; NEVER a discovery verdict.
    separability: "SeparabilityResult | None" = None


def _exponent_vector(dim: Dimension, bases: list[str]) -> np.ndarray:
    """The exponent of `dim` over each base symbol in `bases` (0 where absent)."""
    d = dim.as_dict()
    return np.array([float(d.get(b, 0)) for b in bases], dtype=float)


def dimensional_power_law(
    target_dim: Dimension,
    source_names: list[str],
    source_dims: list[Dimension],
) -> tuple[dict[str, float], float]:
    """Solve for the power-law exponents ``p`` such that ``∏ source_i^p_i`` has the target
    dimension — the Buckingham-π / AI-Feynman step.

    Builds the base-exponent matrix ``A`` (rows = base symbols, cols = sources) and solves
    ``A·p = b`` (``b`` = target exponents) by least squares. Returns ``(exponents, residual)``
    where residual = ‖A·p − b‖; a residual ≈ 0 means the target dimension is exactly
    reachable. For an exactly-determined system (sources == bases) the solution is unique;
    for an under-determined one numpy returns the minimum-norm exponents (a documented,
    deterministic choice). Raises ValueError with no sources.
    """
    if not source_dims:
        raise ValueError("dimensional_power_law needs at least one source dimension")
    bases = sorted({b for dim in [target_dim, *source_dims] for b, _ in dim.exponents})
    if not bases:  # everything dimensionless
        return {name: 0.0 for name in source_names}, 0.0
    a_matrix = np.column_stack([_exponent_vector(d, bases) for d in source_dims])
    b_vec = _exponent_vector(target_dim, bases)
    p, *_ = np.linalg.lstsq(a_matrix, b_vec, rcond=None)
    residual = float(np.linalg.norm(a_matrix @ p - b_vec))
    return {name: float(pi) for name, pi in zip(source_names, p, strict=True)}, residual


def _rationalise(x: float, max_denominator: int = EXPONENT_MAX_DENOMINATOR) -> float:
    """Snap a float exponent to the nearest simple rational (1.4999999 -> 1.5)."""
    return float(Fraction(x).limit_denominator(max_denominator))


def _format_exponent(x: float) -> str:
    frac = Fraction(x).limit_denominator(EXPONENT_MAX_DENOMINATOR)
    if frac.denominator == 1:
        return str(frac.numerator)
    return f"{frac.numerator}/{frac.denominator}"


def _render_expression(target_name: str, coefficient: float, exponents: dict[str, float]) -> str:
    factors = [f"{coefficient:.6g}"]
    for name, p in exponents.items():
        if abs(p) < 1e-9:
            continue
        factors.append(name if abs(p - 1.0) < 1e-9 else f"{name}^{_format_exponent(p)}")
    return f"{target_name} = " + " * ".join(factors)


def _source_arrays(problem: DiscoveryProblem, n: int) -> tuple[list[str], list[Dimension], list[np.ndarray]]:
    names: list[str] = []
    dims: list[Dimension] = []
    arrays: list[np.ndarray] = []
    for v in problem.inputs:
        arr = np.asarray(v.values, dtype=float)
        if arr.shape[0] != n:
            raise ValueError(f"input {v.name!r} has {arr.shape[0]} samples, target has {n}")
        if np.any(arr <= 0.0):
            raise ValueError(f"input {v.name!r} has non-positive values; power-law discovery needs positive magnitudes")
        names.append(v.name)
        dims.append(parse_unit(v.unit))
        arrays.append(arr)
    for c in problem.constants:
        if c.value <= 0.0:
            raise ValueError(f"constant {c.name!r} must be positive for power-law discovery")
        names.append(c.name)
        dims.append(parse_unit(c.unit))
        arrays.append(np.full(n, float(c.value)))
    return names, dims, arrays


def _fit_coefficient(arrays: list[np.ndarray], exponents: dict[str, float],
                     names: list[str], y: np.ndarray) -> tuple[float, np.ndarray]:
    """Least-squares scalar ``C`` for ``y = C · ∏ source^exp`` (the only free parameter once
    the exponents are dimensionally fixed). Returns ``(C, y_hat)``."""
    pred = np.ones_like(y)
    for name, arr in zip(names, arrays, strict=True):
        pred = pred * np.power(arr, exponents[name])
    denom = float(np.dot(pred, pred))
    coefficient = float(np.dot(pred, y) / denom) if denom > 0 else 0.0
    return coefficient, coefficient * pred


def _r_squared(y: np.ndarray, y_hat: np.ndarray) -> float:
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
    if ss_tot <= 0.0:  # constant target — fall back to relative-error agreement
        return 1.0 if np.allclose(y, y_hat) else 0.0
    return 1.0 - ss_res / ss_tot


def _build_candidate(problem: DiscoveryProblem, names: list[str], arrays: list[np.ndarray],
                     exponents: dict[str, float], dim_residual: float, y: np.ndarray) -> Candidate:
    coefficient, y_hat = _fit_coefficient(arrays, exponents, names, y)
    r2 = _r_squared(y, y_hat)
    rmse = float(np.sqrt(np.mean((y - y_hat) ** 2)))
    complexity = sum(1 for p in exponents.values() if abs(p) >= 1e-9)
    # Independent SymPy cross-check ONLY on candidates the lstsq solve calls consistent (where a false
    # positive would be dangerous): two disjoint dimensional engines must AGREE to claim consistency.
    # SymPy opaque on a unit -> None (cannot corroborate; fall back to the lstsq verdict honestly);
    # SymPy disagreeing -> fail-closed (dimension_ok forced False). See verification/symbolic.py.
    lstsq_ok = dim_residual < DIMENSION_TOLERANCE
    corroborated: bool | None = None
    if lstsq_ok:
        source_units = {v.name: v.unit for v in problem.inputs}
        source_units.update({c.name: c.unit for c in problem.constants})
        xcheck = cross_check_power_law(problem.target.unit, source_units, exponents)
        corroborated = xcheck.agrees if xcheck.available else None
    return Candidate(
        expression=_render_expression(problem.target.name, coefficient, exponents),
        exponents=exponents,
        coefficient=coefficient,
        r_squared=r2,
        rmse=rmse,
        complexity=complexity,
        dimension_ok=lstsq_ok and corroborated is not False,
        dimension_residual=dim_residual,
        dimension_corroborated=corroborated,
    )


def dimensional_system(problem: DiscoveryProblem) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """The dimensional constraint of `problem` as ``(A, b, source_names)``: ``A·p = b``
    means the power law ``∏ source^p`` has the target dimension (rows = base symbols, cols =
    sources). The Tournament searches the NULL SPACE of ``A`` so every evolved candidate
    stays dimensionally valid by construction."""
    n = len(problem.target.values)
    names, dims, _ = _source_arrays(problem, n)
    target_dim = parse_unit(problem.target.unit)
    bases = sorted({b for dim in [target_dim, *dims] for b, _ in dim.exponents})
    if not bases:
        return np.zeros((1, len(names))), np.zeros(1), names
    a_matrix = np.column_stack([_exponent_vector(d, bases) for d in dims])
    b_vec = _exponent_vector(target_dim, bases)
    return a_matrix, b_vec, names


def candidate_from_exponents(problem: DiscoveryProblem, exponents: dict[str, float]) -> Candidate:
    """Build (fit + score) a Candidate for a GIVEN exponent vector — the reusable evaluator
    shared by symbolic_regress and the Tournament. Computes the fitted coefficient, R², the
    dimensional residual and complexity for these exponents."""
    y = np.asarray(problem.target.values, dtype=float)
    n = y.shape[0]
    names, _, arrays = _source_arrays(problem, n)
    a_matrix, b_vec, _ = dimensional_system(problem)
    p = np.array([exponents[name] for name in names], dtype=float)
    residual = float(np.linalg.norm(a_matrix @ p - b_vec))
    return _build_candidate(problem, names, arrays, dict(exponents), residual, y)


def symbolic_regress(problem: DiscoveryProblem) -> list[Candidate]:
    """Propose candidate power-law formulas for `problem`, dimensionally constrained.

    Returns the dimensional Π-solution and, when rationalising the exponents changes them,
    a cleaned variant — ranked best (highest R², then lowest complexity) first. Raises
    ValueError on empty/mismatched/non-positive data (no fabricated candidate)."""
    y = np.asarray(problem.target.values, dtype=float)
    n = y.shape[0]
    if n == 0:
        raise ValueError("target has no samples")
    if np.any(y <= 0.0):
        raise ValueError("target has non-positive values; power-law discovery needs positive magnitudes")
    names, dims, arrays = _source_arrays(problem, n)
    target_dim = parse_unit(problem.target.unit)

    raw_exps, residual = dimensional_power_law(target_dim, names, dims)
    candidates = [_build_candidate(problem, names, arrays, raw_exps, residual, y)]

    nice_exps = {k: _rationalise(v) for k, v in raw_exps.items()}
    if nice_exps != raw_exps:
        # re-measure the dimensional residual with the cleaned exponents
        bases = sorted({b for dim in [target_dim, *dims] for b, _ in dim.exponents})
        a_matrix = np.column_stack([_exponent_vector(d, bases) for d in dims]) if bases else np.zeros((1, len(dims)))
        b_vec = _exponent_vector(target_dim, bases) if bases else np.zeros(1)
        p_nice = np.array([nice_exps[name] for name in names], dtype=float)
        nice_residual = float(np.linalg.norm(a_matrix @ p_nice - b_vec))
        candidates.append(_build_candidate(problem, names, arrays, nice_exps, nice_residual, y))

    candidates.sort(key=lambda c: (-c.r_squared, c.complexity))
    return candidates


def _delta_to_consensus(candidate: Candidate, known_laws: dict[str, dict[str, float]]) -> float:
    """A first, honest δ heuristic: 0 if the candidate's exponents match a supplied known
    law (an expected result), else rising with complexity (a more novel claim). Bounded to
    [0, 1]. Documented as a heuristic, not a calibrated probability — the δ-asymmetry then
    RAISES the evidence bar with δ."""
    for exps in known_laws.values():
        if all(abs(candidate.exponents.get(k, 0.0) - v) < 1e-6 for k, v in exps.items()) and \
           all(abs(candidate.exponents.get(k, 0.0) - exps.get(k, 0.0)) < 1e-6 for k in candidate.exponents):
            return 0.0
    return min(1.0, candidate.complexity / 5.0)


def _judge(candidate: Candidate, y: np.ndarray, y_hat: np.ndarray, *, r2_threshold: float,
           delta: float) -> DiscoveryVerdict:
    # δ-asymmetry: a more novel (higher-δ) claim must clear a stricter fit bar.
    effective_threshold = r2_threshold + (1.0 - r2_threshold) * delta
    rel_err = np.abs(y - y_hat) / np.abs(y)
    max_rel_err = float(np.max(rel_err)) if rel_err.size else math.inf
    recompute_ok = bool(np.all([within_tolerance(float(o), float(p), tolerance=max(1e-6, 1.0 - r2_threshold))
                                for o, p in zip(y, y_hat, strict=True)]))
    fit_ok = candidate.r_squared >= effective_threshold
    gates = {
        "dimensional_check": {"passed": candidate.dimension_ok, "residual": candidate.dimension_residual},
        "gate_c6_recompute": {"passed": recompute_ok, "max_rel_err": max_rel_err},
        "fit": {"passed": fit_ok, "r_squared": candidate.r_squared, "threshold": effective_threshold,
                "rmse": candidate.rmse},
        "uncertainty": {"residual_std": float(np.std(y - y_hat)), "coefficient": candidate.coefficient},
    }
    passed = candidate.dimension_ok and recompute_ok and fit_ok
    if not candidate.dimension_ok:
        verdict = "widerlegt"  # dimensionally impossible — a definite negative
    elif passed:
        verdict = "bestaetigt"
    else:
        verdict = "unentschieden"
    return DiscoveryVerdict(candidate=candidate, passed=passed, verdict=verdict,
                            gates=gates, delta_to_consensus=delta)


def _target_separability(problem: DiscoveryProblem, target_fn: "Callable[..., float] | None"):
    """Annotate the AI-Feynman separability of a queryable target, or ``None`` — best-effort, never fatal.

    Multiplicative separability is the power-law-native question (does the law factor into independent
    variable groups the engine could represent?); it is used when the target is positive on the data,
    else additive. The input variables are the axes; the caller bakes any constants into ``target_fn``.
    Any failure (signature mismatch, non-positive log, overflow) yields ``None`` — a missing structure,
    never a fabricated one or a crashed discovery. Deterministic (separability uses a fixed seed).
    """
    if target_fn is None or len(problem.inputs) < 2:
        return None
    from .separability import analyze_separability

    names = [v.name for v in problem.inputs]
    ranges = {v.name: (float(min(v.values)), float(max(v.values))) for v in problem.inputs}
    mode = "multiplicative" if min(problem.target.values) > 0.0 else "additive"
    try:
        return analyze_separability(target_fn, names, ranges, mode=mode)
    except (ValueError, TypeError, ArithmeticError):
        return None


def discover_new_formulas(
    problem: DiscoveryProblem,
    *,
    known_laws: dict[str, dict[str, float]] | None = None,
    r2_threshold: float = DEFAULT_R2_THRESHOLD,
    prior: "ConceptUtility | None" = None,
    refine_with_search: bool = False,
    target_fn: "Callable[..., float] | None" = None,
) -> DiscoveryResult:
    """The Phase-1 core loop (Anhang B): idea+data → candidate formulas → gated validation.

    Generates candidates with ``symbolic_regress``, judges each through the dimensional,
    recompute, fit and uncertainty gates under the δ-asymmetry, and returns BOTH the
    validated verdicts (best first) and the full record of every candidate — kept and
    rejected — because a rejection is information, not garbage (it feeds the Discovery
    Graph). `known_laws` optionally maps a law name to its exponent signature so an expected
    rediscovery gets a low δ (a lower evidence bar) than a novel claim.

    `prior` is an optional ledger-learned ``ConceptUtility``: it ONLY breaks ties among validated
    candidates of EQUAL fit and parsimony (best-fit-first is never overridden by a heuristic), so a
    historically-passing concept structure is preferred only when the gate could not separate them.
    Default ``None`` reproduces the bare gate ordering exactly. Deterministic.

    `refine_with_search` opts into a best-first exponent search (AI-Scientist-v2 tree search, the
    deterministic gate as the node oracle) that runs ONLY when the single-shot SR confirmed nothing —
    e.g. an under-determined free π-group the SR cannot pin. It walks from the SR's best guess and can
    only ADD gate-passing laws; it never removes or overrides a verdict. Default ``False`` is
    byte-identical to the bare loop.

    `target_fn` is an OPTIONAL queryable form of the target — ``f(**input_vars) -> float`` with any
    constants baked in by the caller (synthetic/benchmark problems have it; raw-data problems do not).
    When supplied, the result is annotated with the target's AI-Feynman separability (does the law factor
    into independent variable groups?), structural provenance toward the declared multi-term extension.
    It is purely informational and NEVER changes a verdict; default ``None`` leaves the result unchanged.
    """
    known = known_laws or {}
    y = np.asarray(problem.target.values, dtype=float)
    n = y.shape[0]
    names, _, arrays = _source_arrays(problem, n)

    records: list[DiscoveryVerdict] = []
    for cand in symbolic_regress(problem):
        _, y_hat = _fit_coefficient(arrays, cand.exponents, names, y)
        delta = _delta_to_consensus(cand, known)
        records.append(_judge(cand, y, y_hat, r2_threshold=r2_threshold, delta=delta))

    def _key(r: DiscoveryVerdict):
        # primary: best fit; secondary: parsimony; tertiary (only if prior given): learned utility.
        utility = prior.score(r.candidate) if prior is not None else 0.0
        return (-r.candidate.r_squared, r.candidate.complexity, -utility)

    validated = tuple(sorted((r for r in records if r.passed), key=_key))

    # Opt-in rescue: when the cheap single-shot SR confirmed nothing (e.g. an under-determined free
    # π-group it could not pin), a best-first exponent search walks from the SR's best guess, scored by
    # the SAME gate. It can only ADD gate-passing laws — the gate stays the sole authority, and a
    # problem SR already solved is left untouched (default off → byte-identical to the bare loop).
    if refine_with_search and not validated and records:
        from .tree_search import directed_search

        best_sr = max(records, key=lambda r: r.candidate.r_squared)
        start = {name: float(best_sr.candidate.exponents.get(name, 0.0)) for name in names}
        for node in directed_search(problem, start).passing:
            rescued = candidate_from_exponents(problem, dict(zip(names, node.state, strict=True)))
            records.append(judge_candidate(problem, rescued, known_laws=known, r2_threshold=r2_threshold))
        validated = tuple(sorted((r for r in records if r.passed), key=_key))

    return DiscoveryResult(problem_idea=problem.idea, validated=validated,
                           all_records=tuple(records), run_id=problem.run_id,
                           separability=_target_separability(problem, target_fn))


def judge_candidate(
    problem: DiscoveryProblem,
    candidate: Candidate,
    *,
    known_laws: dict[str, dict[str, float]] | None = None,
    r2_threshold: float = DEFAULT_R2_THRESHOLD,
) -> DiscoveryVerdict:
    """Judge a single, already-built Candidate against `problem` — the public gate wrapper the
    controller/tournament use to record an externally-produced candidate (e.g. an evolved or a
    Grok-proposed one) with the SAME gates and δ-asymmetry as the engine's own candidates.
    Refits the coefficient from the candidate's exponents and runs the dimensional/recompute/
    fit/uncertainty gates. Deterministic."""
    y = np.asarray(problem.target.values, dtype=float)
    names, _, arrays = _source_arrays(problem, y.shape[0])
    _, y_hat = _fit_coefficient(arrays, candidate.exponents, names, y)
    delta = _delta_to_consensus(candidate, known_laws or {})
    return _judge(candidate, y, y_hat, r2_threshold=r2_threshold, delta=delta)
