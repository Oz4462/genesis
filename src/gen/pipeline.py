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


@dataclass(frozen=True)
class PrintabilityAssessment:
    """The honest geometric/mesh printability verdict over a Specification.

    `status` is one of:
      • "print_ready"      — mesh proven sliceable, plate contact, nothing unsupported.
      • "needs_attention"  — printable, but with advisories (elephant-foot risk, …).
      • "not_printable"    — at least one hard blocker (broken mesh, no plate
                             contact, an unsupported/unbridgeable ceiling).
      • "no_geometry"      — no component carries geometry; nothing was judged.
      • "unavailable"      — the CAD kernel (cadquery/OCP) is absent; nothing was
                             judged — surfaced, never a silent pass.
    """

    status: str
    components: list[dict]
    mesh: dict | None
    blockers: list[str]
    advisories: list[str]

    @property
    def ok(self) -> bool:
        """True only when the geometry was actually judged and nothing blocks a
        print (advisories allowed) — "unavailable"/"no_geometry" are NOT ok."""
        return self.status in ("print_ready", "needs_attention")


def assess_printability(spec: Specification) -> PrintabilityAssessment:
    """Compose the printability layers into one honest verdict (the geometric
    counterpart of ``assess_specification``; research write-up:
    docs/research/PRINT_DESIGN_FAILURES.md, PHASE_DELTA §52).

    Per geometry-carrying component it runs the 45°-overhang rule, the bridge
    refinement (an anchored flat ceiling ≤ 10 mm prints support-free — its area is
    SUBTRACTED from the overhang area, both measured on the SAME tessellation, so
    a fully-bridgeable ceiling composes to "no support needed"), and the
    first-layer report (plate contact, elephant foot). The exported kernel STL is
    then proven sliceable by ``stl_integrity_check``. cadquery/OCP absent or no
    geometry present yields an explicit non-ok status, never a silent pass.
    Deterministic; offline; no model calls."""
    from .core.errors import GeometryError
    from .core.state import Quantity

    parts = [c for c in spec.components if c.geometry is not None]
    if not parts:
        return PrintabilityAssessment(
            status="no_geometry", components=[], mesh=None, blockers=[], advisories=[],
        )

    from .mesh_integrity import stl_integrity_check
    from .orientation import bridge_spans, first_layer_report, overhang_check

    quantities: dict[str, Quantity] = {q.id: q for q in spec.quantities}
    components: list[dict] = []
    blockers: list[str] = []
    advisories: list[str] = []
    try:
        for comp in parts:
            overhang = overhang_check(comp.geometry, quantities)
            bridges = bridge_spans(comp.geometry, quantities)
            first_layer = first_layer_report(comp.geometry, quantities)

            bridged_area = sum(
                r["area"] for r in bridges["regions"] if not r["needs_support"]
            )
            unsupported_area = max(0.0, overhang["overhang_area"] - bridged_area)
            components.append({
                "component": comp.id,
                "overhang": overhang,
                "bridges": bridges,
                "first_layer": first_layer,
                "unsupported_overhang_area": unsupported_area,
            })

            if not first_layer["plate_contact"]:
                blockers.append(
                    f"{comp.id}: keine ebene Druckbett-Kontaktfläche — das Teil haftet nicht"
                )
            if bridges["needs_support"]:
                blockers.append(
                    f"{comp.id}: ebene Decke nicht überbrückbar "
                    f"(größte Spannweite {bridges['worst_span']:.1f} mm > Limit, oder "
                    "kein gegenüberliegendes verankertes Paar) — braucht Stützmaterial"
                )
            elif unsupported_area > 1e-9:
                advisories.append(
                    f"{comp.id}: {unsupported_area:.1f} mm² Überhang jenseits der "
                    "45°-Regel druckt nur mit Stützmaterial"
                )
            if first_layer["elephant_foot_risk"]:
                advisories.append(
                    f"{comp.id}: scharfe Bodenkante — der Elephant-Foot-Wulst untermaßt "
                    f"Features nahe der Druckplatte; eine "
                    f"{first_layer['recommended_base_chamfer']} mm Fase am Boden vorsehen "
                    "(oder Erste-Schicht-Kompensation im Slicer)"
                )

        from .export.brep_stl import specification_to_brep_stl

        mesh = stl_integrity_check(specification_to_brep_stl(spec))
    except GeometryError as exc:
        return PrintabilityAssessment(
            status="unavailable", components=components, mesh=None,
            blockers=[], advisories=[f"nicht beurteilt: {exc}"],
        )
    if not mesh["ok"]:
        blockers.append(
            "exportiertes STL hat die Mesh-Integritätsprüfung nicht bestanden: "
            + "; ".join(mesh["issues"])
        )

    if blockers:
        status = "not_printable"
    elif advisories:
        status = "needs_attention"
    else:
        status = "print_ready"
    return PrintabilityAssessment(
        status=status, components=components, mesh=mesh,
        blockers=blockers, advisories=advisories,
    )
