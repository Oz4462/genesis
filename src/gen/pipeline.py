"""Pipeline — the honest wiring of the GENESIS quality engine into one verdict.

The engine's parts are individually honest (the physics gate reports its checks; the
selector reports gaps; clarification reports underspecification; the constraint and
grounding checks report contradictions). But a consumer that reads a single part can be
MISLED at the seam: ``evaluate_spec_physics(...)["gate"].passed`` is True both when the
checks genuinely cleared AND when an indicated check could not run (a gap) or when no
checks ran at all (a spec with no physics measurands). A pass that masks a gap is exactly
the failure GENESIS exists to prevent — an honest gap presented as a clean result.

This module is the wiring that fixes that. ``assess_specification`` composes clarification,
physics selection + gate, constraint consistency, and (optionally) grounding into ONE
``Assessment`` whose ``overall`` status is honest by construction:

  • needs_clarification     — an indicated physics is missing an input (ask first).
  • inconsistent_constraints— the requirements structurally contradict each other.
  • physics_incomplete      — a physics check was indicated but could not be evaluated
                              (a gap) — NOT a pass.
  • physics_failed          — a check ran and did not clear its margin.
  • no_physics_indicated    — the spec declares no physics checks; nothing was verified
                              here (a vacuous "pass" is surfaced as this, not as verified).
  • physics_verified        — every indicated check ran and cleared.

So ``physics_ok`` is true only when the gate passed AND every indicated check actually ran;
``physics_checked`` flags whether anything ran at all. Each step is recorded to an optional
telemetry trace. Ratification (the human sign-off) stays an explicit separate step. Offline,
deterministic, pure composition over the existing modules.
"""

from __future__ import annotations

from dataclasses import dataclass

from .clarification import ClarifyingQuestion, clarifying_questions
from .constraint_consistency import Contradiction, find_contradictions
from .core.interfaces import GateResult
from .core.state import Claim, Specification
from .grounding_integrity import CorroborationReport, corroboration_independence
from .physics_selection import select_physics_checks
from .physics_validation import PhysicsCheck, gate_delta_physics
from .telemetry import RunTrace


@dataclass(frozen=True)
class Assessment:
    """The unified, honest verdict over a Specification's quality axes."""

    clarification_questions: list[ClarifyingQuestion]
    physics_checks: list[PhysicsCheck]
    physics_gaps: list[str]
    physics_gate: GateResult
    constraint_contradictions: list[Contradiction]
    corroboration: CorroborationReport | None
    overall: str

    @property
    def needs_clarification(self) -> bool:
        return bool(self.clarification_questions)

    @property
    def physics_checked(self) -> bool:
        """Whether any physics check actually ran (False = a vacuous spec-level pass)."""
        return bool(self.physics_checks)

    @property
    def physics_complete(self) -> bool:
        """Whether every INDICATED physics check could be evaluated (no gaps)."""
        return not self.physics_gaps

    @property
    def physics_ok(self) -> bool:
        """Physics is ok only if the gate passed AND every indicated check ran — a gap
        makes this False, never a silent pass."""
        return self.physics_gate.passed and self.physics_complete

    @property
    def constraints_consistent(self) -> bool:
        return not self.constraint_contradictions


def _overall_status(
    questions, gaps, gate: GateResult, contradictions, n_checks: int
) -> str:
    """The single honest status, in priority order (what must be resolved first)."""
    if questions:
        return "needs_clarification"
    if contradictions:
        return "inconsistent_constraints"
    if gaps:
        return "physics_incomplete"          # indicated but unrunnable — not a pass
    if not gate.passed:
        return "physics_failed"
    if n_checks == 0:
        return "no_physics_indicated"        # nothing ran — a vacuous pass, surfaced
    return "physics_verified"


def assess_specification(
    spec: Specification,
    *,
    claims: list[Claim] | None = None,
    trace: RunTrace | None = None,
) -> Assessment:
    """Compose the quality engine into one honest Assessment of `spec`.

    Wires clarification (underspecification), physics selection + the δ-physics gate,
    constraint consistency, and — when `claims` are given — corroboration independence.
    Records each step to `trace` if provided. The returned ``overall`` distinguishes a
    genuine verification from an incomplete (gap), failed, or vacuous (no-check) one — so
    a consumer cannot read a clean pass where there is an honest gap. Deterministic.
    """
    questions = clarifying_questions(spec)
    checks, gaps = select_physics_checks(spec)
    gate = gate_delta_physics(checks)
    contradictions = find_contradictions(spec.constraints)
    corroboration = corroboration_independence(claims) if claims is not None else None

    if trace is not None:
        trace.record("clarify", "clarify", n_questions=len(questions))
        trace.record("select", "select", n_checks=len(checks), n_gaps=len(gaps))
        trace.record_gate("delta-physics", gate)
        trace.record("constraints", "constraints", n_contradictions=len(contradictions))
        if corroboration is not None:
            trace.record("grounding", "grounding", status="ok" if corroboration.ok else "error",
                         circular=len(corroboration.circular))

    overall = _overall_status(questions, gaps, gate, contradictions, len(checks))
    return Assessment(
        clarification_questions=questions,
        physics_checks=checks,
        physics_gaps=gaps,
        physics_gate=gate,
        constraint_contradictions=contradictions,
        corroboration=corroboration,
        overall=overall,
    )
