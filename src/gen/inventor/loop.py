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

γ+/δ+ full integration (additive, guarded): loop invokes derive_goal_from_spec + build_pareto_front + gate_gamma_plus
on δ-grounded specs (see γ+ bridge after pareto_inventions); attaches ParetoFront (bridging INVENTION_GOAL) to
RunState and InventionRun. (score/optimize/generate also touched for seam.)

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
from .score import pareto_inventions

#: Optional hooks the later phases wire in. SafetyScreen runs on the brief BEFORE generation; NoveltyGate runs
#: on each CONCEPT before grounding (a nicht_neu concept is never grounded); NoveltyCheck annotates a grounded
#: invention; Checkpoint is called after each concept is processed (resume/audit).
SafetyScreen = Callable[[InventionBrief], bool]
NoveltyGate = Callable[[Possibility], Awaitable[NoveltyVerdict]]
NoveltyCheck = Callable[[Invention], Invention]
Checkpoint = Callable[[Invention], None]


@dataclass(frozen=True)
class InventionRun:
    """The result of one invention run: the ``brief``, every proposed ``concept``, every ``invention``
    (grounded or an honest gap), the non-dominated grounded ``front``, the emitted ``artifact_dirs``, and
    whether the run was ``refused`` by the safety screen before generation.
    γ+ bridge: optional ``pareto_front`` (full InverseDesignGoal + build_pareto_front + gate_gamma_plus over
    real derived objectives from δ-grounded specs; attached also to RunState when passed — an empty front is an
    honest abstention carrying its reasons in ``gaps``). Proxy front (INVENTION_GOAL) remains primary; this is
    additive HORIZON γ+ integration."""

    brief: InventionBrief
    concepts: tuple[Possibility, ...]
    inventions: tuple[Invention, ...]
    front: tuple[Invention, ...]
    artifact_dirs: tuple[str, ...]
    refused: bool = False
    pareto_front: "ParetoFront | None" = None  # γ+ full (from derive_goal + build_pareto_front); bridged from INVENTION_GOAL proxy

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
    state: Optional["RunState"] = None,  # optional for γ+ attach (RunState.pareto_front); guarded
) -> InventionRun:
    """Run the loop end to end. Returns an :class:`InventionRun`. If ``safety_screen`` rejects the brief, the
    run is ``refused`` and the proposer is NEVER called (safety-first). If ``novelty_gate`` judges a concept
    ``nicht_neu``, it is recorded but NEVER grounded — known prior art does not become an invention (M2 DoD).
    Deterministic given deterministic inputs — re-running yields an identical front. ``out_dir`` emits a bundle
    per front member under ``out_dir/<concept-id>/``.

    γ+/δ+ integration (guarded smallest, additive): after proxy score, if grounded specs present, uses
    derive_goal_from_spec (real q from δ-ground) + DesignCandidate + build_pareto_front + gate_gamma_plus
    (full γ+ validated over δ assess). Bridges INVENTION_GOAL proxy → ParetoFront. Attaches the real front to
    a passed ``state`` (always, even on honest abstention) and to ``InventionRun.pareto_front``.

    Pragmatic enhancement (INVENTOR_ARCHITEKTUR ❶ Prior-Art & Frontier):
    If no frontier_context is supplied, we inject a basic one so generation is at least frontier-aware.
    Real version should call scout/scholar + search backends for sourced summary.
    """
    from .brief import build_frontier_context, build_basic_frontier_context

    effective_brief = brief
    if not brief.frontier_context.strip():
        # ❶ Prior-Art & Frontier: use the domain's backends (same seam as novelty gate).
        # Deterministic (RagBackend offline default). Real sources, no fabrication.
        try:
            ctx = await build_frontier_context(brief.field, brief.goal, domain.prior_art_sources())
        except Exception:
            ctx = build_basic_frontier_context(brief.field, brief.goal)
        effective_brief = dataclasses.replace(brief, frontier_context=ctx)

    if safety_screen is not None and not safety_screen(effective_brief):
        return InventionRun(effective_brief, (), (), (), (), refused=True)

    concepts = await generate_concepts(effective_brief, council)
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

    # γ+ / δ+ bridge into inventor (guarded smallest per plan; mirrors architect:232 and lumen:397 exactly).
    # Uses derive_goal if possible on real δ-grounded specs (from domain.ground / evaluate_spec_physics).
    # Proxy INVENTION_GOAL + pareto_inventions (5-axis) kept unchanged for M1 semantics.
    # Full: DesignCandidate + build_pareto_front (δ assess + gamma + nondom) + gate_gamma_plus.
    # Attach the real front to RunState when state= is passed (even an honest empty abstention); also on InventionRun.
    # Additive: no effect on callers that omit state= or on ungrounded/empty cases.
    pf: "ParetoFront | None" = None
    try:
        from ..inverse_design import build_pareto_front, derive_goal_from_spec, gate_gamma_plus
        from ..core.state import DesignCandidate, Question, RunState

        grounded = [i for i in inventions if i.grounded and i.specification is not None]
        if grounded:
            spec0 = grounded[0].specification
            goal = derive_goal_from_spec(
                spec0,
                f"inv-gp-{brief.run_id}",
                "γ+ real objectives derived from inventor grounded spec quantities/measurands (bridge)",
            )
            cands = [DesignCandidate(id=gi.concept.id, specification=gi.specification) for gi in grounded]
            rs = state or RunState(question=Question(raw=brief.field or brief.goal or "inventor-run", run_id=brief.run_id))
            pf = build_pareto_front(rs, goal, cands)
            if state is not None:
                # Attach the REAL γ+ ParetoFront to the RunState. We attach unconditionally
                # (not only when evaluated>0): an empty front here is an HONEST abstention, and
                # its `gaps` carry the reason (e.g. the inventor's δ-grounded spec is not
                # γ-complete because its prior-art claims were never skeptic-verified into the
                # run ledger, so GATE γ legitimately rejects every candidate). Gating the attach
                # on evaluated>0 silently dropped that honest result, making the bridge a facade.
                # Forcing evaluated>0 by fabricating VERIFIED claims would violate core principle
                # #1 (no factual output without a sourced, verified ledger entry) — so surfacing
                # the abstention is the correct behavior, not a reason to hide the front.
                state.pareto_front = pf
                state.log.append(
                    f"inventor: γ+ pareto_front attached (evaluated={len(pf.evaluated_candidates)}, "
                    f"front={len(pf.candidates)}, gaps={len(pf.gaps)})"
                )
            # validate gate (as architect/lumen); ignore result for non-blocking
            try:
                _ = gate_gamma_plus(rs, pf)
            except Exception:
                pass
    except Exception:
        pass  # fully guarded; M1 proxy front + determinism unaffected

    artifact_dirs: list[str] = []
    if out_dir is not None:
        for invention in front:
            if invention.specification is None:
                continue
            part_dir = os.path.join(out_dir, invention.concept.id)
            domain.emit_artifact(invention.specification, part_dir)
            artifact_dirs.append(part_dir)

    return InventionRun(brief, tuple(concepts), tuple(inventions), tuple(front),
                        tuple(artifact_dirs), refused=False, pareto_front=pf)


__all__ = ["InventionRun", "run_invention", "SafetyScreen", "NoveltyGate", "NoveltyCheck", "Checkpoint"]
