"""surrogate — the Physics Foundation Layer as a cheap PREFILTER (build doc §3.1 item 2 / §4.2).

A fast, deterministic surrogate that RANKS and PRUNES candidates before the expensive gate
runs — so a wide candidate space (later: the assumption annihilator, a GP search) does not
pay full gate cost on the obvious losers.

THE HARD RULE (the doc, Risk 2): **the surrogate only prefilters, it NEVER confirms.** It looks
at a cheap signal — the R² of the candidate refit on a random SUB-SAMPLE of the data — and
deliberately does NOT look at dimensional consistency or run the full gate. So it can rank a
dimensionally-impossible candidate highly; that is fine and expected, because the gate
(`engine.judge_candidate`) remains the sole decider of ``bestaetigt`` / ``widerlegt`` /
``unentschieden``. If we ever let the surrogate confirm, we would import exactly the black-box
weakness we criticise in other systems.

Structurally enforced: `surrogate_score` returns a float, `prefilter` returns a ranked subset
of *candidates* — neither returns a verdict. Confirmation lives only in the gate. Offline,
deterministic (seeded sub-sampling), numpy-only.
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
