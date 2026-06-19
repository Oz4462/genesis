"""refinement — the gate-feedback -> mutation -> re-grounding loop for a single concept (TE2).

The Self-Refine finding (verifiers beat generators): a δ-physics failure is not a dead end but TARGETED
feedback. This module is the bounded controller around the inventor's grounding, carrying GENESIS's honesty
discipline (it reuses ``gen.refinement.directives_from_gate`` for the gate-feedback table):

  * Each round grounds the concept with an injectable ``architect_for_round`` (the regeneration step — e.g.
    "strengthen the design" by raising the modal margin); the δ-physics gate verdict drives the next round.
  * The loop is BOUNDED (``max_rounds``) and detects NO-PROGRESS: if a round leaves the IDENTICAL gap set, it
    stops with ``stuck=True`` — an honest "this regenerator cannot fix it", never a faked convergence.
  * ``converged`` is True only when an invention is actually ``physics_verified``; an exhausted or stuck loop
    returns the last (still-failing) invention with ``converged=False``.

Deterministic given a deterministic ``architect_for_round``; offline-testable with a scripted schedule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from ..core.state import Possibility
from ..llm.base import LLMClient
from ..physics_selection import evaluate_spec_physics
from ..refinement import RefinementDirective, directives_from_gate
from .brief import Invention, InventionBrief
from .domains.base import InventionDomain
from .domains.mechatronics import scripted_mechatronics_architect

#: A regeneration step: (round_index, previous_invention_or_None) -> the architect for this round.
ArchitectForRound = Callable[[int, Optional[Invention]], LLMClient]


@dataclass
class InventionRefinement:
    """Outcome of the per-concept refinement loop. ``invention`` is the final one (possibly still failing);
    ``converged`` iff it became physics-verified; ``stuck`` iff a round made no progress (identical gaps
    recurred); ``directives`` are the gate-feedback instructions for the residual failure (empty if converged);
    ``history`` is per-round ``(round, physics_verified)`` for audit."""

    invention: Invention
    rounds: int
    converged: bool
    stuck: bool = False
    directives: list[RefinementDirective] = field(default_factory=list)
    history: list[tuple[int, bool]] = field(default_factory=list)


def _failure_signature(inv: Invention) -> tuple:
    """A no-progress fingerprint that reflects the ACTUAL failure, so a real design change is seen as progress.
    Uses the δ-physics GateResult's (code, target, detail) per failure — the detail carries the concrete
    margin/values, so a stronger design (different values) is a DIFFERENT signature, while an unchanged design
    repeats. Falls back to the gap strings when there is no spec to evaluate."""
    if inv.specification is None:
        return ("nospec", tuple(sorted(inv.gaps)))
    gate = evaluate_spec_physics(inv.specification)["gate"]
    return tuple(sorted((f.code, f.claim_id or "", f.detail) for f in gate.failures))


def _residual_directives(inv: Invention) -> list[RefinementDirective]:
    """The gate-feedback directives for a still-failing invention, via the δ-physics GateResult (reusing the
    declared ``directives_from_gate`` table). Empty when there is no spec to evaluate."""
    if inv.specification is None:
        return []
    gate = evaluate_spec_physics(inv.specification)["gate"]
    return directives_from_gate(gate)


async def refine_invention(
    concept: Possibility,
    brief: InventionBrief,
    domain: InventionDomain,
    architect_for_round: ArchitectForRound,
    *,
    max_rounds: int = 5,
) -> InventionRefinement:
    """Bounded gate-feedback refinement of one concept. Each round grounds the concept with
    ``architect_for_round(round, prev)``; on a δ-physics failure the next round regenerates. Returns an honest
    :class:`InventionRefinement`: ``converged`` only on a real physics-verified pass, ``stuck`` when a round
    leaves the identical gaps. Raises ValueError on a non-positive round budget."""
    if max_rounds < 1:
        raise ValueError("max_rounds must be >= 1")
    history: list[tuple[int, bool]] = []
    seen: set[tuple] = set()
    invention: Optional[Invention] = None
    for rnd in range(max_rounds + 1):
        architect = architect_for_round(rnd, invention)
        invention = await domain.ground(concept, brief, architect)
        history.append((rnd, invention.physics_verified))
        if invention.physics_verified:
            return InventionRefinement(invention, rnd, True, False, [], history)
        signature = _failure_signature(invention)
        if signature in seen:                       # identical gaps recurred -> no progress, stop honestly
            return InventionRefinement(invention, rnd, False, True, _residual_directives(invention), history)
        seen.add(signature)
        if rnd == max_rounds:                       # budget spent without convergence
            return InventionRefinement(invention, rnd, False, False, _residual_directives(invention), history)
    raise AssertionError("unreachable")             # pragma: no cover


def strengthening_schedule(*, start_hz: float = 30.0, step_hz: float = 40.0) -> ArchitectForRound:
    """An offline regeneration schedule for the mechatronics resonance gate: each round raises the mount's
    first natural frequency by ``step_hz`` ("strengthen the design until the modal margin clears"). Reaches a
    passing design from a failing start — the repairable case. A zero ``step_hz`` models an unrepairable
    regenerator (the same failing design every round -> stuck)."""
    def schedule(rnd: int, _prev: Optional[Invention]) -> LLMClient:
        return scripted_mechatronics_architect(first_natural_hz=start_hz + step_hz * rnd)
    return schedule


__all__ = ["InventionRefinement", "refine_invention", "strengthening_schedule", "ArchitectForRound"]
