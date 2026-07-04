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
  • grounding_failed         — the claims are not independently corroborated (circular
                              self-corroboration) — the facts underneath cannot be trusted.
  • geometry_failed          — the built BREP solid diverges from the spec's own declared
                              geometry (cross-check via geometry_verification); an absent
                              CAD kernel is an explicit "unavailable" skip, never a pass.
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
from .core.state import Claim, SeamCertificate, Specification
from .grounding_integrity import CorroborationReport, corroboration_independence
from .physics_selection import select_physics_checks
from .physics_validation import PhysicsCheck, gate_delta_physics
from .seams import (build_seam_certificate, cost_rollup_required, gate_epsilon,
                    required_seam_pairs, DomainSeam, SeamDomain, SeamRelation)
from .costing import bom_cost
from .telemetry import RunTrace


@dataclass(frozen=True)
class Assessment:
    """The unified, honest verdict over a Specification's quality axes.

    Now includes Phase ε seam verification (gate_epsilon) when the spec has
    required cross-domain obligations (adjacent MECH/THERM/ELEC/FIRM or COST rollup).
    `seam_gate` is None only for specs with no seam obligations (vacuous case is
    honest and never turned into a clean pass via other properties).

    `geometry_status` is the BREP-vs-analytic cross-check (geometry_verification):
    "verified" (every geometry-carrying component's built solid agrees with its
    declared geometry), "failed" (a divergence — a blocker in `overall`),
    "unavailable" (the optional cadquery/OCP kernel is absent — an honest skip,
    surfaced here and in the CLI/web views, never a silent pass or fail), or
    "no_geometry" (nothing to judge — vacuous, honest). `geometry_checks` carries
    the per-component results.
    """

    clarification_questions: list[ClarifyingQuestion]
    physics_checks: list[PhysicsCheck]
    physics_gaps: list[str]
    physics_gate: GateResult
    constraint_contradictions: list[Contradiction]
    corroboration: CorroborationReport | None
    seam_gate: GateResult | None
    geometry_status: str
    geometry_checks: list[dict]
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
        """Physics is ok only if at least one indicated check actually RAN, the gate
        passed, AND every indicated check ran — a gap OR a vacuous no-check spec makes
        this False, never a silent pass (a gate that passes over zero checks is vacuous)."""
        return self.physics_checked and self.physics_gate.passed and self.physics_complete

    @property
    def constraints_consistent(self) -> bool:
        return not self.constraint_contradictions

    @property
    def seams_ok(self) -> bool:
        """True only if this spec had epsilon obligations (required adjacent domain pairs
        or COST rollup) AND the provided (or auto-built empty) certificate satisfied
        gate_epsilon with no failures. False for vacuous specs (no obligations) or
        when seams are required but not satisfied. Never masks a missing seam."""
        if self.seam_gate is None:
            return False  # no obligations or not yet computed (honest)
        return self.seam_gate.passed

    @property
    def geometry_ok(self) -> bool:
        """True only when every geometry-carrying component's BREP solid was actually
        cross-checked against the analytic layer and agreed. "unavailable" (no CAD
        kernel) and "no_geometry" (nothing to judge) are honest non-ok — never a
        silent pass; "failed" additionally blocks `overall` as "geometry_failed"."""
        return self.geometry_status == "verified"


def _geometry_cross_check(spec: Specification) -> tuple[str, list[dict]]:
    """Cross-check every geometry-carrying component's built BREP solid against the
    analytic layer (geometry_verification.verify_geometry) — the "two independent
    methods agree" guard over the generated CAD, wired into the one honest verdict.

    Returns ``(status, results)``: status is "no_geometry" (no component carries
    geometry — vacuous, honest), "unavailable" (the optional cadquery/OCP kernel is
    absent — an explicit skip with reason, the same honesty pattern as
    PrintabilityAssessment's "unavailable", NEVER a silent pass), "failed" (a
    component's built solid diverges from its declared geometry, or the kernel/CSG
    could not judge it — fail-loud), or "verified". Deterministic, offline.
    """
    parts = [c for c in spec.components if c.geometry is not None]
    if not parts:
        return "no_geometry", []
    try:
        import cadquery  # noqa: F401  (optional CAD kernel — probe only)
    except ImportError:
        return "unavailable", []

    from .core.errors import GeometryError
    from .geometry_verification import verify_geometry

    quantities = {q.id: q for q in spec.quantities}
    results: list[dict] = []
    for comp in parts:
        try:
            r = verify_geometry(comp.geometry, quantities)
            results.append({"component": comp.id, **r})
        except GeometryError as exc:
            # kernel present but the check itself failed loudly (malformed CSG,
            # OCCT crash): that is a finding about the geometry, not a skip.
            results.append({"component": comp.id, "ok": False, "error": str(exc)})
    status = "verified" if all(r["ok"] for r in results) else "failed"
    return status, results


def _overall_status(
    questions, gaps, gate: GateResult, contradictions, n_checks: int, corroboration,
    seam_gate: GateResult | None, geometry_status: str
) -> str:
    """The single honest status, in priority order (what must be resolved first).

    Seams (epsilon) are now part of the honest composition: if a spec has required
    cross-domain obligations (or cost rollup) and they are not satisfied, this surfaces
    as "seams_failed" (preventing masked passes on coupling).

    Geometry: a BREP-vs-analytic divergence surfaces as "geometry_failed" (a built
    artifact that does not match its own declared geometry blocks the verdict).
    "unavailable"/"no_geometry" do NOT alter the headline — the skip stays visible
    in Assessment.geometry_status (and geometry_ok stays False), never masked
    either way.
    """
    if questions:
        return "needs_clarification"
    if contradictions:
        return "inconsistent_constraints"
    if corroboration is not None and not corroboration.ok:
        return "grounding_failed"            # claims not independently corroborated (circular)
    if geometry_status == "failed":
        # built CAD diverges from the spec's own declared geometry: the artifact itself
        # is wrong, which outranks an uncertified seam over that artifact.
        return "geometry_failed"
    if seam_gate is not None and not seam_gate.passed:
        return "seams_failed"                # required cross-domain coupling not satisfied (honest)
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
    seam_certificate: SeamCertificate | None = None,
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

    # A spec may carry its own Phase-ε output (state.Specification.seam_certificate,
    # e.g. the capstone demo or the humanoid specs) — the explicit argument wins,
    # the spec's own certificate is the fallback. Without this, a caller that only
    # passes the spec would fail seams the spec has honestly certified.
    if seam_certificate is None:
        seam_certificate = getattr(spec, "seam_certificate", None)

    # Phase ε seam verification (wired mandatorily per rigorous multi-physics expansion)
    # If the spec has required adjacent domain pairs or COST rollup, run gate_epsilon.
    # Empty cert (when none provided) produces explicit honest failures (MISSING_* etc.).
    # T+E (THERMAL+ELECTRICAL) always triggers via improved domains_present (quantity measurands)
    # even without bom/netlist (prevents gate skip for power->heat specs).
    required_pairs = required_seam_pairs(spec)
    # NOTE C-1 (costing): Cost.complete means "every position accounted for — GROUNDED price OR
    # explicitly labelled filament ESTIMATE", not "all prices proven". The COST_ROLLUP seam proves
    # arithmetic coupling of that roll-up; price grounding is carried by Cost.fully_grounded and
    # labelled downstream (format_cost, bundle manifest, MISSING.md).
    needs_seams = bool(required_pairs) or (cost_rollup_required(spec) and bom_cost(spec).complete)
    seam_gate: GateResult | None = None
    if needs_seams:
        provided_seams = list(seam_certificate.seams) if seam_certificate else []
        if cost_rollup_required(spec) and bom_cost(spec).complete and not any(s.relation == SeamRelation.COST_ROLLUP for s in provided_seams):
            has_declared_total = any(
                "total" in (q.id or "").lower() and q.unit in ("EUR", "USD", "€", "$")
                for q in spec.quantities
            )
            if not has_declared_total:
                # virtual auto only for no declared total (per re-review Council-Auftrag)
                auto_cost = DomainSeam(
                    id="auto_cost_rollup",
                    left_domain=SeamDomain.COST,
                    right_domain=SeamDomain.ELECTRICAL,
                    relation=SeamRelation.COST_ROLLUP,
                    left_expr="bom_total_cost",
                    right_expr="EUR",
                    rationale="auto for complete bom without declared total (virtual case only)",
                )
                provided_seams = provided_seams + [auto_cost]
        if seam_certificate is not None and len(provided_seams) != len(seam_certificate.seams):
            # the virtual auto-cost seam was appended above — a provided certificate
            # must not silently drop it, or the gate would fail a coupling the code
            # just declared (latent since the certificate path existed)
            from dataclasses import replace as _replace
            cert = _replace(seam_certificate, seams=provided_seams)
        else:
            cert = seam_certificate or build_seam_certificate(spec, provided_seams)
        seam_gate = gate_epsilon(spec, cert)

    geometry_status, geometry_checks = _geometry_cross_check(spec)

    if trace is not None:
        trace.record("clarify", "clarify", n_questions=len(questions))
        trace.record("select", "select", n_checks=len(checks), n_gaps=len(gaps))
        trace.record_gate("delta-physics", gate)
        trace.record("constraints", "constraints", n_contradictions=len(contradictions))
        if corroboration is not None:
            trace.record("grounding", "grounding", status="ok" if corroboration.ok else "error",
                         circular=len(corroboration.circular))
        if seam_gate is not None:
            trace.record_gate("epsilon", seam_gate)
        trace.record("geometry", "geometry", status=geometry_status,
                     n_components=len(geometry_checks))

    overall = _overall_status(questions, gaps, gate, contradictions, len(checks), corroboration,
                              seam_gate, geometry_status)
    return Assessment(
        clarification_questions=questions,
        physics_checks=checks,
        physics_gaps=gaps,
        physics_gate=gate,
        constraint_contradictions=contradictions,
        corroboration=corroboration,
        seam_gate=seam_gate,
        geometry_status=geometry_status,
        geometry_checks=geometry_checks,
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
