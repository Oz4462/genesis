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
from .completeness import completeness_warnings
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
    completeness_warnings: list[str]
    overall: str
    # Phase ε: None only when the spec has no seam obligations (honest vacuous).
    seam_gate: GateResult | None = None
    # BREP-vs-analytic: verified | failed | unavailable | no_geometry
    geometry_status: str = "no_geometry"
    geometry_checks: list[dict] | None = None
    # E2E HORIZON cert pop (ε/ζ; δ+/γ+/Ω for consumers). Typed as object|None so
    # ruff F821 does not require importing every optional cert type into pipeline.
    # Concrete types live on RunState; assess path may leave these None.
    seam_certificate: object | None = None
    memory_fabric: object | None = None
    pareto_front: object | None = None
    omega_certificate: object | None = None
    coverage_certificate: object | None = None
    reality_verdict: object | None = None
    delta_plus_result: dict | None = None
    # Platform Caps (no-stop autonomy)
    proof_package: str | None = None
    readiness_level: str | None = None
    teacher_notes: dict | None = None
    community_evidence: dict | None = None

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
        """True only if seam obligations existed AND gate_epsilon passed."""
        if self.seam_gate is None:
            return False
        return self.seam_gate.passed

    @property
    def geometry_ok(self) -> bool:
        """True only when every geometry-carrying component's BREP agreed with analytic."""
        return self.geometry_status == "verified"


def _geometry_cross_check(spec: Specification) -> tuple[str, list[dict]]:
    """Cross-check geometry-carrying components' BREP vs analytic layer.

    Returns (status, results): no_geometry | unavailable | failed | verified.
    """
    parts = [c for c in spec.components if c.geometry is not None]
    if not parts:
        return "no_geometry", []
    # Cross-check in assess_specification uses *in-process* cadquery only.
    # Bridge-based OCCT (subprocess cold-start) is too slow for multi-part product
    # demos (humanoid/aethon). Print/printability still use the cad-venv bridge via
    # orientation/brep_stl (see docs/CADQUERY_VENV.md). Opt-in bridge here:
    # GENESIS_BREP_CROSSCHECK=1.
    try:
        import cadquery  # noqa: F401  (optional CAD kernel — probe only)
        in_process = True
    except ImportError:
        in_process = False
    if not in_process:
        import os

        if os.environ.get("GENESIS_BREP_CROSSCHECK", "").strip() not in ("1", "true", "yes"):
            return "unavailable", []
        try:
            from .cad.cadquery_bridge import cad_available
        except Exception:  # noqa: BLE001
            return "unavailable", []
        if not cad_available():
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
            results.append({"component": comp.id, "ok": False, "error": str(exc)})
    status = "verified" if all(r.get("ok") for r in results) else "failed"
    return status, results


def _overall_status(
    questions,
    gaps,
    gate: GateResult,
    contradictions,
    n_checks: int,
    corroboration,
    seam_gate: GateResult | None = None,
    geometry_status: str = "no_geometry",
) -> str:
    """The single honest status, in priority order (what must be resolved first)."""
    if questions:
        return "needs_clarification"
    if contradictions:
        return "inconsistent_constraints"
    if corroboration is not None and not corroboration.ok:
        return "grounding_failed"            # claims not independently corroborated (circular)
    if geometry_status == "failed":
        return "geometry_failed"
    if seam_gate is not None and not seam_gate.passed:
        return "seams_failed"
    if gaps:
        return "physics_incomplete"          # indicated but unrunnable — not a pass
    if not gate.passed:
        return "physics_failed"
    # D14 G4 note (deferred low, per WQ): "physics_failed vor physics_incomplete reorder" not applied.
    # Analysis: gaps/questions 1:1 coupled in clarify+select; needs_clarification fires first.
    # Reachable cases use current priority (clarify > ... > incomplete > failed). No change.
    if n_checks == 0:
        return "no_physics_indicated"        # nothing ran — a vacuous pass, surfaced
    return "physics_verified"


def assess_specification(
    spec: Specification,
    *,
    claims: list[Claim] | None = None,
    trace: RunTrace | None = None,
    seam_certificate: object | None = None,
) -> Assessment:
    """Compose the quality engine into one honest Assessment of `spec`.

    Wires clarification (underspecification), physics selection + the δ-physics gate,
    constraint consistency, and — when `claims` are given — corroboration independence.
    Records each step to `trace` if provided. The returned ``overall`` distinguishes a
    genuine verification from an incomplete (gap), failed, or vacuous (no-check) one — so
    a consumer cannot read a clean pass where there is an honest gap. Deterministic.

    ``seam_certificate``: optional Phase-ε cert from the caller (e.g. bundle cost rollup).
    Wins over ``spec.seam_certificate``; when neither is set, auto-detect builds one.
    """
    questions = clarifying_questions(spec)
    checks, gaps = select_physics_checks(spec)
    gate = gate_delta_physics(checks)
    contradictions = find_contradictions(spec.constraints)
    corroboration = corroboration_independence(claims) if claims is not None else None
    comp_warns = completeness_warnings(spec)

    # E2E HORIZON cert pop (ε/ζ here; δ+/γ+/Ω honest-None in assess path).
    # Uses builders for provenance (VERIFIED claims for memory; spec for seam).
    # Guards for cases without full data (honest None). δ+ (reality etc), γ+ (pareto), Ω populated on RunState paths only.
    # Enables full consumers (bundle/web/cli Assessment). See CONSUMERS FULL CERTS 4L.
    # Explicit arg wins; then spec-carried cert; else auto-detect (bundle/capstone demos).
    if seam_certificate is None:
        seam_certificate = getattr(spec, "seam_certificate", None)
    seam_gate: GateResult | None = None
    memory_fabric = None
    pareto_front = None
    omega_certificate = None
    coverage_certificate = None
    reality_verdict = None
    delta_plus_result = None
    # Optional HORIZON/platform enrichments: never silent — surface skip reasons
    # in completeness_warnings so assess cannot hide failed optional wiring
    # (STATUS §5 bans bare ``except Exception: pass`` around verdict construction).
    optional_notes: list[str] = []
    try:
        from .costing import bom_cost
        from .seams import (
            build_seam_certificate,
            cost_rollup_required,
            detect_cross_domain_seams,
            gate_epsilon,
            required_seam_pairs,
        )
        from .memory_fabric import build_memory_fabric_certificate
        # richer auto (was skeleton []); real DomainSeams from spec/constraints/bom (architect post-γ or here after spec).
        # See detect_cross_domain_seams + gap report. Memory from passed claims (richer deposits).
        if seam_certificate is None:
            real_seams = detect_cross_domain_seams(spec)
            seam_certificate = build_seam_certificate(spec, real_seams, complete=bool(real_seams))
        # Phase ε: only when adjacent pairs exist OR a *complete* cost rollup is provable.
        # Incomplete BOM (missing prices) must not force MISSING_COST_ROLLUP.
        required_pairs = required_seam_pairs(spec)
        needs_seams = bool(required_pairs) or (
            cost_rollup_required(spec) and bom_cost(spec).complete
        )
        if needs_seams:
            cert = seam_certificate or build_seam_certificate(spec, [])
            seam_gate = gate_epsilon(spec, cert)
        if claims:
            # minimal state-like (builder only needs claims + question.run_id)
            class _MinQ:
                run_id = getattr(spec, "run_id", f"assess-{id(spec)}")
            class _MinState:
                claims = claims
                question = _MinQ()
            memory_fabric = build_memory_fabric_certificate(_MinState())
    except Exception as exc:  # noqa: BLE001 — optional path; recorded below
        optional_notes.append(
            f"optional_horizon_certs_skipped ({type(exc).__name__}: {exc})"
        )

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

    geometry_status, geometry_checks = _geometry_cross_check(spec)
    if trace is not None:
        trace.record(
            "geometry",
            "geometry",
            status="error" if geometry_status == "failed" else "ok",
            geometry_status=geometry_status,
            n_components=len(geometry_checks),
        )

    overall = _overall_status(
        questions,
        gaps,
        gate,
        contradictions,
        len(checks),
        corroboration,
        seam_gate,
        geometry_status,
    )

    # E2E caps (autonomy deepen): populate from grenz generators for consumers (honest minimal data here)
    proof_package = None
    readiness_level = "TRL3"
    teacher_notes = None
    community_evidence = None
    try:
        from .grenzverschiebung.proof_package import generate_proof_package
        from .grenzverschiebung.readiness_ladder import assess_readiness, TeacherMode, community_evidence as _ce
        p = generate_proof_package(run_id=getattr(spec, 'run_id', 'assess'), idea=getattr(spec, 'idea', str(spec)[:20]), cad_files=[], sim_receipts=[{'gate': 'delta'}], wb_seeds=[{'claims': bool(claims)}])
        proof_package = p.package_dir
        rl = assess_readiness({'claims': bool(claims), 'physics': gate.passed})
        readiness_level = rl.level
        tm = TeacherMode()
        teacher_notes = tm.record('assess', ['physics', 'seams'])
        teacher_notes = tm.apply({'overall': overall})
        community_evidence = _ce({
            'claims': len(claims or []),
            'idea': getattr(spec, 'idea', None) or str(spec)[:120],
            'gates': ['assess', 'delta'] if gate.passed else ['assess'],
        })
    except Exception as exc:  # noqa: BLE001 — optional platform caps; recorded below
        optional_notes.append(
            f"optional_platform_caps_skipped ({type(exc).__name__}: {exc})"
        )

    return Assessment(
        clarification_questions=questions,
        physics_checks=checks,
        physics_gaps=gaps,
        physics_gate=gate,
        constraint_contradictions=contradictions,
        corroboration=corroboration,
        completeness_warnings=[*comp_warns, *optional_notes],
        seam_gate=seam_gate,
        geometry_status=geometry_status,
        geometry_checks=geometry_checks,
        seam_certificate=seam_certificate,
        memory_fabric=memory_fabric,
        pareto_front=pareto_front,
        omega_certificate=omega_certificate,
        coverage_certificate=coverage_certificate,
        reality_verdict=reality_verdict,
        delta_plus_result=delta_plus_result,
        overall=overall,
        proof_package=proof_package,
        readiness_level=readiness_level,
        teacher_notes=teacher_notes,
        community_evidence=community_evidence,
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

            # D15 wiring: run Tier-3 geometry verification (built BREP vs analytic spec)
            # when possible. Includes "ok", volumes, extents. Necessary not sufficient.
            # Mismatch or degenerate surfaces as blocker (honest CAD/spec divergence).
            geo_verification = None
            try:
                from .geometry_verification import verify_geometry
                geo_verification = verify_geometry(comp.geometry, quantities)
            except Exception as exc:  # noqa: BLE001 — Tier-3 optional; never silent
                geo_verification = {
                    "ok": False,
                    "status": "unavailable",
                    "reason": f"{type(exc).__name__}: {exc}",
                }

            components.append({
                "component": comp.id,
                "overhang": overhang,
                "bridges": bridges,
                "first_layer": first_layer,
                "unsupported_overhang_area": unsupported_area,
                "geometry_verification": geo_verification,
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

            # D15 seam closure: surface geometry verification result (Tier-3 CAD match)
            if geo_verification and not geo_verification.get("ok", True):
                if geo_verification.get("nonzero_volume") is False:
                    blockers.append(
                        f"{comp.id}: geometry verification: degenerate or zero-volume CAD vs declared spec"
                    )
                else:
                    blockers.append(
                        f"{comp.id}: built CAD geometry does not match declared spec "
                        "(volume or extents cross-check failed — see verify_geometry)"
                    )

        from .export.brep_stl import specification_to_brep_stl

        try:
            mesh = stl_integrity_check(specification_to_brep_stl(spec))
        except GeometryError as mesh_exc:
            # Self-improve 2026-07-13: when OCCT/cadquery is absent, fall back to
            # the primitive STL exporter for integrity check only — CSG booleans
            # still refuse honestly (skipped → unavailable).
            from .core.errors import ExportError
            from .export.stl import specification_to_stl_report

            try:
                fallback, skipped = specification_to_stl_report(spec)
            except ExportError as exp_exc:
                raise GeometryError(
                    f"{mesh_exc}; primitive fallback failed: {exp_exc}"
                ) from mesh_exc
            if skipped:
                raise GeometryError(
                    f"{mesh_exc}; primitive fallback skipped CSG parts: {sorted(skipped)}"
                ) from mesh_exc
            mesh = stl_integrity_check(fallback)
            advisories.append(
                "mesh via primitive STL fallback (cadquery/OCCT unavailable) — "
                "curved surfaces faceted; CSG booleans not evaluated"
            )
    except GeometryError as exc:
        # Blockers already found are FACTS — do not discard them when mesh export dies.
        # With blockers → not_printable; blocker-free partial run → unavailable.
        advisories.append(f"nicht beurteilt: {exc}")
        return PrintabilityAssessment(
            status="not_printable" if blockers else "unavailable",
            components=components,
            mesh=None,
            blockers=blockers,
            advisories=advisories,
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
