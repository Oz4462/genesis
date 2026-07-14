"""loop — the invention orchestrator: safety -> generate -> ground -> (novelty) -> score -> artifacts.

Composes the built pieces into one deterministic run (INVENTOR §3). The control flow is fixed and non-LLM;
only generation and grounding call the (injectable) models, and a deterministic gate decides at every step:

  1. SAFETY first (TS slot): an optional structural screen runs BEFORE any concept is generated — a refused
     brief never reaches the proposer.
  2. GENERATE: the council widens to grounded concepts (``generate_concepts``).
  3. GROUND: the domain grounds each concept through the architect -> δ-physics gate (``domain.ground``).
  4. NOVELTY (TN slot): an optional per-invention novelty check annotates each result.
  5. SCORE: keep the non-dominated grounded inventions (``pareto_inventions``).
  6. ARTIFACTS: emit a buildable bundle for each front member when ``out_dir`` is given.

Everything is injectable; with a ScriptedLLM council + architect and a fixed seed the whole run is byte-for-byte
reproducible (the M1 Definition of Done). The safety/novelty hooks default to no-ops so this loop is the stable
spine that TN and TS wire into without a rewrite.
"""

from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from ..core.state import Possibility
from ..llm.base import LLMClient
from .brief import Invention, InventionBrief
from .domains.base import InventionDomain
from .generate import generate_concepts
from .novelty import NICHT_NEU, NoveltyVerdict
from .refinement import ArchitectForRound, refine_invention
from .score import inventions_to_pareto_front, pareto_inventions

#: Optional hooks the later phases wire in. SafetyScreen runs on the brief BEFORE generation; NoveltyGate runs
#: on each CONCEPT before grounding (a nicht_neu concept is never grounded); NoveltyCheck annotates a grounded
#: invention; Checkpoint is called after each concept is processed (resume/audit).
#: architect_for_round + max_refine_rounds: on δ-fail, bounded refine_invention (TE2) — never fakes pass.
SafetyScreen = Callable[[InventionBrief], bool]
NoveltyGate = Callable[[Possibility], Awaitable[NoveltyVerdict]]
NoveltyCheck = Callable[[Invention], Invention]
Checkpoint = Callable[[Invention], None]


@dataclass(frozen=True)
class InventionRun:
    """The result of one invention run: the ``brief``, every proposed ``concept``, every ``invention``
    (grounded or an honest gap), the non-dominated grounded ``front``, the emitted ``artifact_dirs``, and
    whether the run was ``refused`` by the safety screen before generation.

    ``pareto_front`` is the HORIZON γ+ bridge (self-improve 2026-07-14): a
    :class:`~gen.core.state.ParetoFront` built from inventor 5-axis score proxies
    (``produced_by=inventor.score_proxy``). None only on refused runs.
    """

    brief: InventionBrief
    concepts: tuple[Possibility, ...]
    inventions: tuple[Invention, ...]
    front: tuple[Invention, ...]
    artifact_dirs: tuple[str, ...]
    refused: bool = False
    pareto_front: object = None  # ParetoFront | None — object avoids circular import weight

    @property
    def grounded_count(self) -> int:
        return sum(1 for i in self.inventions if i.grounded)


async def run_invention(
    brief: InventionBrief,
    *,
    domain: InventionDomain,
    council: LLMClient,
    architect: LLMClient,
    out_dir: Optional[str] = None,
    safety_screen: Optional[SafetyScreen] = None,
    novelty_gate: Optional[NoveltyGate] = None,
    novelty_check: Optional[NoveltyCheck] = None,
    checkpoint: Optional[Checkpoint] = None,
    architect_for_round: Optional[ArchitectForRound] = None,
    max_refine_rounds: int = 0,
) -> InventionRun:
    """Run the loop end to end. Returns an :class:`InventionRun`. If ``safety_screen`` rejects the brief, the
    run is ``refused`` and the proposer is NEVER called (safety-first). If ``novelty_gate`` judges a concept
    ``nicht_neu``, it is recorded but NEVER grounded — known prior art does not become an invention (M2 DoD).
    If first ground fails δ and ``architect_for_round`` + ``max_refine_rounds>=1`` are set, runs bounded
    :func:`refine_invention` (self-improve 2026-07-14 — TE2 was tested but not wired into the loop).
    Deterministic given deterministic inputs — re-running yields an identical front. ``out_dir`` emits a bundle
    per front member under ``out_dir/<concept-id>/``."""
    if safety_screen is not None and not safety_screen(brief):
        return InventionRun(brief, (), (), (), (), refused=True, pareto_front=None)

    concepts = await generate_concepts(brief, council)
    inventions: list[Invention] = []
    for concept in concepts:
        verdict: Optional[NoveltyVerdict] = None
        if novelty_gate is not None:
            verdict = await novelty_gate(concept)
            if verdict.verdict == NICHT_NEU:
                # known prior art: record the honest non-novel verdict + evidence, but do NOT ground it.
                evidence = (verdict.nearest_prior_art,) if verdict.nearest_prior_art else ()
                rejected = Invention(concept=concept, novelty_verdict=verdict.verdict, prior_art=evidence,
                                     gaps=("nicht neu — bekannte Prior-Art, nicht geerdet",))
                inventions.append(rejected)
                if checkpoint is not None:
                    checkpoint(rejected)
                continue

        invention = await domain.ground(concept, brief, architect)
        # Bounded TE2 refine on δ-fail (only when a regenerator schedule is injected).
        if (
            not invention.physics_verified
            and architect_for_round is not None
            and max_refine_rounds >= 1
        ):
            ref = await refine_invention(
                concept,
                brief,
                domain,
                architect_for_round,
                max_rounds=max_refine_rounds,
            )
            invention = ref.invention
            if ref.converged:
                extra = (f"refine converged in {ref.rounds} round(s)",)
            elif ref.stuck:
                extra = (f"refine stuck after {ref.rounds} round(s) — identical δ failures",)
            else:
                extra = (f"refine exhausted budget ({ref.rounds} rounds) without δ pass",)
            invention = dataclasses.replace(invention, gaps=tuple(dict.fromkeys((*invention.gaps, *extra))))
        if verdict is not None:
            merged = tuple(dict.fromkeys((*invention.prior_art,
                                          *( (verdict.nearest_prior_art,) if verdict.nearest_prior_art else () ))))
            invention = dataclasses.replace(invention, novelty_verdict=verdict.verdict, prior_art=merged)
        if novelty_check is not None:
            invention = novelty_check(invention)
        inventions.append(invention)
        if checkpoint is not None:
            checkpoint(invention)

    front = pareto_inventions(inventions)
    # γ+ bridge: attach HORIZON ParetoFront from 5-axis score proxies (CLI was printing empty).
    pf = inventions_to_pareto_front(inventions, front)

    artifact_dirs: list[str] = []
    if out_dir is not None:
        for invention in front:
            if invention.specification is None:
                continue
            part_dir = os.path.join(out_dir, invention.concept.id)
            domain.emit_artifact(invention.specification, part_dir)
            artifact_dirs.append(part_dir)

    return InventionRun(
        brief,
        tuple(concepts),
        tuple(inventions),
        tuple(front),
        tuple(artifact_dirs),
        refused=False,
        pareto_front=pf,
    )


__all__ = ["InventionRun", "run_invention", "SafetyScreen", "NoveltyGate", "NoveltyCheck", "Checkpoint"]
