"""active_resolution — the active next move after an ``unentschieden`` verdict.

The discovery arm ends at a verdict: ``bestaetigt`` / ``widerlegt`` / ``unentschieden``. When it
says ``unentschieden`` it has found TWO dimensionally-valid rivals that fit the observed data
equally well (a transcendental ``C·f(α·π)+D`` and the power-of-a-group ``C·π^β+D``) and cannot tell
them apart. A passive verifier stops there. This module makes GENESIS an ACTIVE instrument: it asks
"what measurement would break the tie?".

Given the two rivals and the observed data, :func:`propose_resolution` computes — deterministically,
LLM-free, with NO new dependencies and NO hardware — the bounded region where the rivals' predictions
diverge, and emits a :class:`DecisionSpec`: which input to extend, to what (bounded) range, a SPREAD
of points to measure across that region (a spread, NOT the single divergence peak — a lone new value
a three-parameter rival can still bend to fit; a spread constrains the functional SHAPE), each
rival's expected signature there, and the exact verdict criterion to re-run. Feed real data at that
spec and re-judge: the ``unentschieden`` flips to ``bestaetigt`` / ``widerlegt``.

This is optimal-experimental-design in spirit — a maximum-disagreement, shape-constraining sampler
inside a hard extrapolation bound, not a formal Fisher-information (D/A/E-optimal) design — applied to
SYMBOLIC dimensional laws and gated like the rest of GENESIS. The honest failure mode is
extrapolation: a divergence found far outside the regime where
either form is a valid approximation is an artefact, not a discriminating experiment. The gate is
explicit — search only within the observed range scaled by a hard factor ``max_extrapolation`` (≤ a
few), and require the divergence to exceed ``min_discrimination`` times the fit-noise floor. If it
does not, the honest output is ``discriminating = False`` ("collect more in the observed regime"),
never an invented experiment.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .engine import DiscoveryProblem, Variable
from .multiplicative import ProductRival, evaluate_product_rival, refit_product_rival
from .transcendental import RivalForm, evaluate_rival, refit_rival

#: Any rival the resolver can evaluate/refit: the 6.3 transcendental-vs-power pair or the 6.6
#: multiplicative product-vs-power pair — same tie, same active move.
AnyRival = RivalForm | ProductRival


def _evaluate_any(rival: AnyRival, problem: DiscoveryProblem) -> np.ndarray:
    """Evaluate a fitted rival WITHOUT refit — dispatching on the rival family (6.3 or 6.6)."""
    if isinstance(rival, ProductRival):
        return evaluate_product_rival(rival, problem)
    return evaluate_rival(rival, problem)


def _refit_any(rival: AnyRival, problem: DiscoveryProblem) -> AnyRival | None:
    """Re-fit a rival on (possibly augmented) data — dispatching on the rival family."""
    if isinstance(rival, ProductRival):
        return refit_product_rival(rival, problem)
    return refit_rival(rival, problem)

#: Hard cap on how far past the observed range the divergence search may look (×). A transcendental
#: and a power law ALWAYS diverge eventually; only divergence near the data is a real experiment.
DEFAULT_MAX_EXTRAPOLATION = 3.0

#: The peak divergence must exceed this many fit-noise floors to count as discriminating.
DEFAULT_MIN_DISCRIMINATION = 5.0

#: Floor on the noise scale as a fraction of the observed signal span (so clean synthetic data with
#: ~0 residual still demands a divergence that is a real fraction of the signal, not float dust).
_REL_NOISE_FLOOR = 1e-3


@dataclass(frozen=True)
class DecisionSpec:
    """A discriminating-measurement specification: the deterministic answer to "what would break
    the tie between two rivals?". When ``discriminating`` is False there is no useful experiment in
    the allowed (bounded) region and ``reason`` says so — an honest gap, not an invented test."""

    variable: str                       # which input to extend
    observed_range: tuple[float, float]
    extended_range: tuple[float, float]
    measure_at: tuple[float, ...]       # suggested new input values (in the unobserved region)
    expected_a: tuple[float, ...]       # rival A's predicted target at measure_at (its signature)
    expected_b: tuple[float, ...]       # rival B's predicted target at measure_at
    max_divergence: float               # peak |f_a − f_b| in the bounded region
    discrimination_ratio: float         # max_divergence / noise floor
    discriminating: bool
    verdict_criterion: str
    reason: str


def _with_input_values(problem: DiscoveryProblem, var_name: str, values: np.ndarray) -> DiscoveryProblem:
    """A copy of `problem` with one input replaced by `values` (target zeroed — unused for
    evaluating an already-fitted rival, but it sets the row count for constant broadcasting)."""
    n = len(values)
    inputs = tuple(
        Variable(v.name, v.unit, tuple(float(x) for x in values)) if v.name == var_name else v
        for v in problem.inputs)
    return DiscoveryProblem(
        idea=problem.idea,
        target=Variable(problem.target.name, problem.target.unit, tuple(0.0 for _ in range(n))),
        inputs=inputs, constants=problem.constants, run_id=problem.run_id)


def propose_resolution(
    rival_a: AnyRival | None,
    rival_b: AnyRival | None,
    problem: DiscoveryProblem,
    *,
    max_extrapolation: float = DEFAULT_MAX_EXTRAPOLATION,
    min_discrimination: float = DEFAULT_MIN_DISCRIMINATION,
    n_grid: int = 400,
    n_suggest: int = 5,
) -> DecisionSpec:
    """Propose the measurement that would break the tie between two rivals that fit `problem`'s data
    equally well. Searches the single varying input's range scaled by `max_extrapolation` for the
    point of maximal predicted divergence; emits a :class:`DecisionSpec`. ``discriminating`` is True
    only if the peak divergence exceeds `min_discrimination` noise floors WITHIN the bounded region —
    otherwise the honest verdict is "no discriminating power in the allowed regime".

    MVP scope: exactly one varying input (plus any constants). Raises ValueError otherwise, on a
    non-positive / degenerate input range, or if either rival is None (``discover_rivals`` found no
    dimensionless argument — there is nothing to resolve)."""
    if rival_a is None or rival_b is None:
        raise ValueError("propose_resolution needs two fitted rivals; got None "
                         "(discover_rivals found no dimensionless argument or no fit)")
    if len(problem.inputs) != 1:
        raise ValueError(f"MVP supports a single varying input; got {len(problem.inputs)}")
    if max_extrapolation < 1.0:
        raise ValueError("max_extrapolation must be >= 1.0")
    var = problem.inputs[0]
    obs = np.asarray(var.values, dtype=float)
    lo, hi = float(obs.min()), float(obs.max())
    if not (lo > 0.0 and hi > lo):
        raise ValueError("input range must be positive and non-degenerate")

    y = np.asarray(problem.target.values, dtype=float)
    # noise floor: the demonstrated fit residual, floored to a fraction of the signal span so that
    # clean synthetic data (≈0 residual) still demands a real, not infinitesimal, divergence.
    resid = max(float(np.std(y - _evaluate_any(rival_a, problem))),
                float(np.std(y - _evaluate_any(rival_b, problem))))
    span_y = float(np.max(y) - np.min(y))
    noise = max(resid, _REL_NOISE_FLOOR * span_y, 1e-12)

    ext_lo, ext_hi = lo / max_extrapolation, hi * max_extrapolation
    grid = np.linspace(ext_lo, ext_hi, n_grid)
    grid_problem = _with_input_values(problem, var.name, grid)
    fa = _evaluate_any(rival_a, grid_problem)
    fb = _evaluate_any(rival_b, grid_problem)
    divergence = np.abs(fa - fb)
    # Conservative: a rival whose prediction is non-finite on the extended grid (numerical
    # overflow of a degenerate fit) is NOT counted as discriminating power — masked to zero
    # rather than promoted to an "infinite divergence" experiment.
    divergence = np.where(np.isfinite(divergence), divergence, 0.0)

    max_div = float(np.max(divergence))
    ratio = max_div / noise
    discriminating = ratio >= min_discrimination

    # Suggest points SPREAD across the unobserved, discriminating band — not clustered at the single
    # peak. Clustered points pin one value, which a 3-parameter rival can still bend to fit; a spread
    # constrains the SHAPE over the region, which the wrong form cannot follow. The band is the
    # unobserved grid where the divergence already exceeds the discrimination floor.
    unobserved = (grid < lo) | (grid > hi)
    informative = [i for i in range(grid.size) if unobserved[i] and divergence[i] >= min_discrimination * noise]
    if informative:
        sel = np.linspace(0, len(informative) - 1, min(n_suggest, len(informative)))
        picked = sorted({informative[int(round(s))] for s in sel})
    else:
        # nothing clears the floor in the unobserved region (not discriminating) — still report the
        # divergence peak so the spec is inspectable, but discriminating stays False.
        picked = sorted(int(i) for i in np.argsort(divergence)[::-1][:n_suggest])
    measure_at = tuple(float(grid[i]) for i in picked)
    expected_a = tuple(float(fa[i]) for i in picked)
    expected_b = tuple(float(fb[i]) for i in picked)

    crit = (f"Miss {problem.target.name} bei {var.name} in {measure_at}; dann discover_transcendental "
            f"erneut: erwartet Form '{rival_a.form_name}' bestaetigt, Rivale '{rival_b.form_name}' "
            f"faellt unter die Schwelle (oder umgekehrt).")
    if discriminating:
        reason = (f"Rivalen divergieren um {max_div:.3g} ({ratio:.1f}x Rausch-Boden) bei "
                  f"{var.name}~{grid[int(np.argmax(divergence))]:.3g} — entscheidbar.")
    else:
        reason = (f"Max. Divergenz {max_div:.3g} nur {ratio:.1f}x Rausch-Boden (< {min_discrimination}) "
                  f"im erlaubten Bereich [{ext_lo:.3g}, {ext_hi:.3g}] — keine Unterscheidungskraft; "
                  f"mehr Daten im beobachteten Regime sammeln.")

    return DecisionSpec(
        variable=var.name, observed_range=(lo, hi), extended_range=(ext_lo, ext_hi),
        measure_at=measure_at, expected_a=expected_a, expected_b=expected_b,
        max_divergence=max_div, discrimination_ratio=ratio, discriminating=discriminating,
        verdict_criterion=crit, reason=reason)


@dataclass(frozen=True)
class RobustDecisionSpec:
    """A discriminating spec that also SURVIVES the losing rival re-fitting (maximin T-optimality).

    ``propose_resolution`` finds where the two FITTED rivals diverge; this asks the harder question — if
    the loser is allowed to re-fit optimally to the proposed data, can it then follow the winner's shape?
    ``survives_refit`` is True only when, EVEN AFTER the re-fit, the loser still misses the winner's
    signature over the SPREAD by more than the discrimination floor; ``discriminating`` is the robust
    verdict (base discriminating AND survives the re-fit)."""

    base: DecisionSpec
    refit_rival_r2: float
    residual_after_refit: float
    survives_refit: bool
    discriminating: bool
    detail: str


def propose_resolution_robust(
    rival_a: AnyRival | None,
    rival_b: AnyRival | None,
    problem: DiscoveryProblem,
    *,
    min_discrimination: float = DEFAULT_MIN_DISCRIMINATION,
    **kwargs,
) -> RobustDecisionSpec:
    """Maximin-robust resolution (FORSCHUNG §A4 T-optimality): propose the discriminating spread, build the
    world where ``rival_a`` is true (observed data + ``rival_a``'s prediction at the spread), RE-FIT the
    loser ``rival_b`` on it, and require that it STILL cannot follow ``rival_a``'s shape over the spread.

    A lone proposed point a three-parameter rival absorbs by re-fitting; a SPREAD it cannot — that is what
    makes the experiment robust rather than a single absorbable value. ``discriminating`` is True only if the
    base spec discriminates AND the re-fit loser's residual to the winner-truth over the spread stays above
    ``min_discrimination`` noise floors. Same single-input MVP scope as ``propose_resolution``."""
    spec = propose_resolution(rival_a, rival_b, problem, min_discrimination=min_discrimination, **kwargs)
    var = problem.inputs[0]
    obs_x = np.asarray(var.values, dtype=float)
    obs_y = np.asarray(problem.target.values, dtype=float)
    new_x = np.asarray(spec.measure_at, dtype=float)
    truth_y = np.asarray(spec.expected_a, dtype=float)          # the world in which rival_a is true
    noise = spec.max_divergence / spec.discrimination_ratio if spec.discrimination_ratio > 0 else 1e-12

    if new_x.size == 0:
        return RobustDecisionSpec(spec, float("nan"), float("nan"), False, False,
                                  "keine Messpunkte vorgeschlagen")

    augmented = DiscoveryProblem(
        idea=problem.idea,
        target=Variable(problem.target.name, problem.target.unit,
                        tuple(np.concatenate([obs_y, truth_y]))),
        inputs=(Variable(var.name, var.unit, tuple(np.concatenate([obs_x, new_x]))),),
        constants=problem.constants, run_id=problem.run_id)
    refit_b = _refit_any(rival_b, augmented)  # type: ignore[arg-type]  (None handled below)
    if refit_b is None:
        return RobustDecisionSpec(spec, float("nan"), float("inf"), True, spec.discriminating,
                                  "der unterlegene Rivale konnte die erweiterten Daten nicht nachfitten")

    refit_pred = _evaluate_any(refit_b, _with_input_values(problem, var.name, new_x))
    residual = float(np.max(np.abs(refit_pred - truth_y)))
    survives = residual >= min_discrimination * noise
    discriminating = spec.discriminating and survives
    detail = (f"Verlierer-Rivale '{rival_b.form_name if rival_b else '?'}' nach Refit R²={refit_b.r_squared:.4f}; "
              f"Rest-Residuum {residual:.3g} = {residual / noise:.1f}x Rausch-Boden — "
              + ("ueberlebt den Refit (robust entscheidbar)" if survives else "absorbiert die Punkte (nicht robust)"))
    return RobustDecisionSpec(spec, refit_b.r_squared, residual, survives, discriminating, detail)
