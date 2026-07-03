"""assumption_annihilator — Assumption Annihilator + Law Rebuilder (build doc 4.3, Phase 4).

Every discovered law rests on assumptions. The biggest is "this quantity is a CONSTANT". The
Assumption Annihilator lifts exactly that: it promotes a held-constant quantity to a free
VARIABLE and RE-DERIVES the law (the Law Rebuilder — the dimensional solve runs again with the
promoted quantity as an input). If the rebuilt law fits the data SUBSTANTIALLY better, the
"constant" was secretly a variable — a hidden dependency the constant assumption was masking.
If it does not, the assumption held and the rebuild is honestly rejected.

THE δ-ASYMMETRY IS NOT OPTIONAL HERE. Claiming that a fundamental "constant" actually varies is
an extraordinary claim — among the highest-δ moves the engine makes. So the evidence bar is RAISED: a
marginal fit improvement is NOT enough; the rebuilt law must clear a large, δ-scaled margin
over the constant-held baseline (and be dimensionally sound and `bestaetigt`) before the
assumption is annihilated. A small improvement returns ``insufficient_evidence`` — the honest
"interesting, but not enough" — never a false discovery. This is exactly where a system is most
tempted to hallucinate; the δ-bar is the guardrail.

Offline, deterministic, numpy-only — it reuses the engine's gates, so a rebuilt law is judged
by the same machinery as everything else.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .engine import (
    DiscoveryProblem,
    DiscoveryVerdict,
    Variable,
    discover_new_formulas,
)

#: Base fit-improvement (ΔR²) a rebuild must show — before the δ-asymmetry raises it.
BASE_IMPROVEMENT_MARGIN = 0.01

#: δ of "a constant is actually a variable" — extraordinary, so near the top of [0, 1].
PROMOTION_DELTA = 0.8

#: How strongly δ scales the required improvement (so the effective bar is large).
DELTA_MARGIN_SCALE = 0.05


@dataclass(frozen=True)
class AnnihilationResult:
    """The verdict on lifting a constant assumption: the constant-held baseline law, the rebuilt
    law (constant promoted to variable), the fit improvement, the δ-raised evidence bar, and the
    honest outcome — ``promoted`` (assumption annihilated, hidden dependency found),
    ``assumption_held`` (no improvement) or ``insufficient_evidence`` (some, but below the δ-bar)."""

    promoted: str
    base_r2: float
    rebuilt_r2: float
    improvement: float
    delta: float
    required_improvement: float
    rebuilt_law: str
    verdict: str


def _best_r2(result) -> tuple[float, DiscoveryVerdict | None]:
    if not result.all_records:
        return 0.0, None
    best = max(result.all_records, key=lambda r: r.candidate.r_squared)
    return best.candidate.r_squared, best


def annihilate_constant(
    problem: DiscoveryProblem,
    constant_name: str,
    per_sample_values: list[float],
    *,
    improvement_margin: float = BASE_IMPROVEMENT_MARGIN,
    known_laws: dict[str, dict[str, float]] | None = None,
) -> AnnihilationResult:
    """Promote `constant_name` from a held constant to a free VARIABLE taking `per_sample_values`
    across the samples, re-derive the law, and judge under the δ-asymmetry.

    The assumption is **annihilated** (``promoted``) only if the rebuilt law beats the
    constant-held baseline by the δ-RAISED margin AND is itself dimensionally sound — an
    extraordinary claim needs extraordinary evidence. Otherwise the constant assumption is
    upheld (``assumption_held``) or the evidence is judged insufficient for the high δ
    (``insufficient_evidence``). Raises ValueError if `constant_name` is not a constant of
    `problem` or the sample count mismatches.
    """
    const = next((c for c in problem.constants if c.name == constant_name), None)
    if const is None:
        raise ValueError(f"{constant_name!r} is not a constant of the problem")
    values = np.asarray(per_sample_values, dtype=float)
    if values.shape[0] != len(problem.target.values):
        raise ValueError("per_sample_values must have one entry per data point")

    base = discover_new_formulas(problem, known_laws=known_laws)
    base_r2, _ = _best_r2(base)

    rebuilt_inputs = (*problem.inputs, Variable(constant_name, const.unit, tuple(values)))
    rebuilt_consts = tuple(c for c in problem.constants if c.name != constant_name)
    rebuilt_problem = DiscoveryProblem(
        idea=f"{problem.idea} [Annahme '{constant_name}=const' aufgehoben]",
        target=problem.target, inputs=rebuilt_inputs, constants=rebuilt_consts,
        run_id=problem.run_id)
    rebuilt = discover_new_formulas(rebuilt_problem, known_laws=known_laws)
    rebuilt_r2, rebuilt_best = _best_r2(rebuilt)

    improvement = rebuilt_r2 - base_r2
    delta = PROMOTION_DELTA
    required = improvement_margin + delta * DELTA_MARGIN_SCALE   # δ raises the bar

    rebuilt_ok = bool(rebuilt_best and rebuilt_best.candidate.dimension_ok)
    if improvement >= required and rebuilt_ok:
        verdict = "promoted"                      # assumption annihilated — hidden dependency
    elif improvement <= improvement_margin:
        verdict = "assumption_held"               # the constant assumption was justified
    else:
        verdict = "insufficient_evidence"         # some gain, but below the high-δ bar

    return AnnihilationResult(
        promoted=constant_name, base_r2=base_r2, rebuilt_r2=rebuilt_r2, improvement=improvement,
        delta=delta, required_improvement=required,
        rebuilt_law=rebuilt_best.candidate.expression if rebuilt_best else "(keiner)",
        verdict=verdict)
