"""bundle — the honest realization bundle: one Specification, every deliverable, no silent gap.

``pipelines/integrator.py``'s ``build_full_mini_realization_package`` writes a package dir but
swallows failures (``except Exception: pass`` / "skipped (graceful)") and ships stubs, so its output
is silently incomplete — the very dishonesty GENESIS exists to prevent. This module is the honest
counterpart on the GATED ``Specification`` world: ``emit_bundle(spec, out_dir)`` writes every
deliverable that CAN be produced — the Markdown build manual, the OpenSCAD print source, the
print-ready STL (when the OCCT kernel is present) — and a MANIFEST that records, BY CONSTRUCTION,
exactly what was produced AND what was not, each missing item with its reason. Nothing is swallowed:
an absent CAD kernel, a spec with no geometry, an ungrounded price, an indicated-but-unrunnable
physics check all surface as explicit entries, never as silence.

It also classifies the BOM into printed vs bought parts and reports the printed share — owner
directive (2026-06-18): the 3D printer is our friend, so maximise what is fabricated in-house and
buy only what genuinely cannot be printed (motors, bearings, electronics, standard fasteners). The
split is exactly the one the data model already declares: a PART with a geometry-backed
``component_id`` is fabricated; without one it is purchased (core/state.py BomItem docstring).

Deterministic, offline. The honest verdict comes from ``pipeline.assess_specification``; this module
turns it into files plus a manifest a human can audit. No model calls.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .core.state import BomRole, Specification
from .costing import bom_cost, format_cost
from .export.markdown import specification_to_markdown
from .export.openscad import specification_to_openscad
from .pipeline import assess_specification
from .seams import build_seam_certificate, DomainSeam, SeamDomain, SeamRelation


@dataclass(frozen=True)
class PrintSplit:
    """The 3D-print-maximisation view of the BOM: which build parts are fabricated in-house
    (printed) vs which must be purchased. Tools are excluded (neither printed nor bought as a
    build part).

    This is a DESIGN classification — the intended fabrication route a part's BOM line + geometry
    declare — NOT a claim that a printable asset was emitted this run. Whether the watertight STL was
    actually produced is reported separately in the bundle manifest's ``written`` / ``missing``."""

    printed: list[str] = field(default_factory=list)
    bought: list[str] = field(default_factory=list)

    @property
    def printed_share(self) -> float:
        n = len(self.printed) + len(self.bought)
        return len(self.printed) / n if n else 0.0


def classify_printability(spec: Specification) -> PrintSplit:
    """Split the BOM's build parts into printed (geometry-backed, fabricated in-house) vs bought.

    A PART/MATERIAL whose ``component_id`` resolves to a component carrying geometry is 3D-printed;
    every other build part (a motor, a bearing, electronics, a standard metal fastener) is bought.
    This is the data model's own ``fabricated vs purchased`` distinction, surfaced for the
    print-maximisation directive. Deterministic."""
    comps = {c.id: c for c in spec.components}
    printed: list[str] = []
    bought: list[str] = []
    for item in spec.bom:
        if item.role not in (BomRole.PART, BomRole.MATERIAL):
            continue  # tools are not build parts
        comp = comps.get(item.component_id) if item.component_id else None
        if comp is not None and comp.geometry is not None:
            printed.append(item.id)
        else:
            bought.append(item.id)
    return PrintSplit(printed=printed, bought=bought)


@dataclass(frozen=True)
class BundleManifest:
    """What ``emit_bundle`` actually produced — honest by construction.

    ``written`` lists the files on disk; ``missing`` lists deliverables that could NOT be produced,
    each with a reason (a spec with no geometry, an absent OCCT kernel, a mesh that failed
    integrity). ``files_complete`` is True only when nothing is missing. The physics / cost / gap
    fields carry the rest of the honest verdict — a partial bundle is reported as partial, never as
    done."""

    out_dir: str
    run_id: str
    idea: str
    written: list[str]
    missing: list[str]
    overall: str
    physics_ok: bool
    physics_checks: list[str]
    physics_gaps: list[str]
    cost_summary: str
    cost_complete: bool
    #: True only when every position carries a GROUNDED purchase price — no filament estimate.
    #: ``cost_complete`` alone means "every position accounted for, estimates explicitly labelled".
    cost_fully_grounded: bool
    #: BOM item ids whose cost is a filament ESTIMATE (bbox × infill × density × price/g),
    #: not a claim-backed price — the label travels with the manifest (C-1 honesty).
    cost_estimated_parts: list[str]
    #: Honest per-item cost diagnostics (ungrounded price origin, negative count).
    cost_notes: list[str]
    unpriced: list[str]
    printed_parts: list[str]
    bought_parts: list[str]
    printed_share: float
    spec_gaps: list[str]
    # S4: platform caps honesty (present/absent — never silent omit)
    proof_package: str | None = None
    readiness_level: str | None = None
    teacher_notes_present: bool = False
    community_score: float | None = None
    community_agent_sourced: bool | None = None
    user_data_required: bool | None = None
    caps_present: dict | None = None
    caps_gaps: list[str] | None = None

    @property
    def files_complete(self) -> bool:
        """True only when every producible deliverable was written (no missing files). Independent
        of the honesty signals (unpriced items, physics gaps) which are surfaced separately."""
        return not self.missing


def emit_bundle(spec: Specification, out_dir: str | Path, *, tolerance: float = 0.1) -> BundleManifest:
    """Write the full realization bundle for `spec` to `out_dir` and return its honest manifest.

    Always writes the Markdown build manual, a BOM file and the manifest. Writes the OpenSCAD print
    source and the print-ready STL when the spec carries geometry. The OPTIONAL deliverables (scad,
    stl) are emitted under a catch-all that turns ANY failure — an absent OCCT kernel (GeometryError),
    a malformed CSG, a disk error — into an explicit ``missing`` entry with its reason, so one bad
    deliverable never aborts the bundle and is never silently dropped. The MANDATORY manual + manifest
    are not swallowed either: if they cannot be written the call fails LOUDLY (an exception, never a
    silent pass) — which preserves the anti-hallucination property (an incomplete bundle is never
    presented as complete). A MISSING.md is written whenever anything is missing or unproven (unpriced
    parts, physics gaps, declared gaps) so the incompleteness cannot be overlooked. Deterministic;
    offline."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    missing: list[str] = []

    # Declare cost seam explicitly for demos with complete bom (per re-review Council-Auftrag for Befund 10)
    cost = bom_cost(spec)
    seam_cert = None
    if cost.complete:
      cost_seam = DomainSeam(
        id="cost_rollup",
        left_domain=SeamDomain.COST,
        right_domain=SeamDomain.ELECTRICAL,
        relation=SeamRelation.COST_ROLLUP,
        left_expr="bom_total_cost",
        right_expr="EUR",
        rationale="cost rollup declared for demo (from bom total)",
      )
      seam_cert = build_seam_certificate(spec, [cost_seam])
    assessment = assess_specification(spec, seam_certificate=seam_cert)
    base = spec.run_id or "part"

    # build manual — always producible from any spec
    (out / "BAUANLEITUNG.md").write_text(specification_to_markdown(spec), encoding="utf-8")
    written.append("BAUANLEITUNG.md")

    has_geometry = any(c.geometry is not None for c in spec.components)

    # OpenSCAD print source — needs no CAD kernel, but needs geometry
    if has_geometry:
        try:
            (out / f"{base}.scad").write_text(specification_to_openscad(spec), encoding="utf-8")
            written.append(f"{base}.scad")
        except Exception as exc:  # recorded, never swallowed
            missing.append(f"{base}.scad: OpenSCAD-Export fehlgeschlagen — {type(exc).__name__}: {exc}")
    else:
        missing.append(
            "SCAD/STL: keine Bauteil-Geometrie in der Spezifikation (zahlen-only Spec) — "
            "es gibt kein druckbares Teil zu erzeugen"
        )

    # ASSEMBLED-product view — the finished robot, parts in place (not the flat tray): an OpenSCAD
    # assembly script + a 3D image. Only when the spec declares assembly placements. The PNG needs
    # matplotlib; its absence is recorded honestly (never a fake image).
    if spec.assembly:
        from .export.assembly import assembly_scad, render_assembly_png

        try:
            asm = assembly_scad(spec)
            if asm is not None:
                (out / f"{base}_assembly.scad").write_text(asm, encoding="utf-8")
                written.append(f"{base}_assembly.scad")
        except Exception as exc:
            missing.append(f"{base}_assembly.scad: Montage-Export fehlgeschlagen — {type(exc).__name__}: {exc}")
        try:
            if render_assembly_png(spec, out / f"{base}_assembly.png"):
                written.append(f"{base}_assembly.png")
            else:
                missing.append(
                    f"{base}_assembly.png: 3D-Montagebild nicht erzeugt (matplotlib fehlt) — "
                    "die Montage-OpenSCAD-Ansicht ist die Bildquelle, bis matplotlib installiert ist")
        except Exception as exc:
            missing.append(f"{base}_assembly.png: Render fehlgeschlagen — {type(exc).__name__}: {exc}")

    # print-ready watertight STL — ONE file per printed component (an assembly prints part-by-part,
    # so each component gets its own mesh); needs the OCCT kernel, whose absence is reported honestly.
    if has_geometry:
        import os

        from .brep import _in_process_cadquery
        from .cad.cadquery_bridge import cad_available
        from .core.errors import GeometryError
        from .export.brep_stl import component_to_brep_stl
        from .mesh_integrity import stl_integrity_check

        geom_comps = [c for c in spec.components if c.geometry is not None]
        single = len(geom_comps) == 1
        quantities = {q.id: q for q in spec.quantities}
        # Multi-part assemblies via cad-venv bridge are slow (cold OCCT per part).
        # Default: only emit BREP STLs in-process OR for single-body specs via bridge.
        # Opt-in multi-part bridge: GENESIS_CAD_MULTIPART=1
        multipart_bridge = os.environ.get("GENESIS_CAD_MULTIPART", "").strip() in (
            "1",
            "true",
            "yes",
        )
        can_brep = _in_process_cadquery() or (
            cad_available() and (single or multipart_bridge)
        )
        if not can_brep:
            for comp in geom_comps:
                fname = f"{base}.stl" if single else f"{base}__{comp.id}.stl"
                missing.append(
                    f"{fname}: watertight STL nicht erzeugt — multi-part cad-venv "
                    "export skipped by default (set GENESIS_CAD_MULTIPART=1); "
                    "OpenSCAD bleibt die Druckquelle"
                )
        else:
            for comp in geom_comps:  # one watertight STL per printed part
                fname = f"{base}.stl" if single else f"{base}__{comp.id}.stl"
                try:
                    stl = component_to_brep_stl(
                        comp.geometry, quantities, name=comp.id, tolerance=tolerance
                    )
                    verdict = stl_integrity_check(stl)
                    if verdict["ok"]:
                        (out / fname).write_text(stl, encoding="utf-8")
                        written.append(fname)
                    else:
                        missing.append(
                            f"{fname}: Mesh-Integrität nicht bestanden — "
                            f"{'; '.join(verdict['issues'])}"
                        )
                except GeometryError as exc:
                    missing.append(
                        f"{fname}: watertight STL nicht erzeugt — {exc} "
                        "(der OpenSCAD-Quellcode ist die Druckquelle, bis der "
                        "OCCT-Kernel installiert ist)"
                    )
                except Exception as exc:
                    missing.append(
                        f"{fname}: unerwarteter Fehler — {type(exc).__name__}: {exc}"
                    )

    # BOM + honest cost
    cost = bom_cost(spec)
    split = classify_printability(spec)
    (out / "bom.json").write_text(json.dumps({
        "items": [{"id": b.id, "name": b.name, "role": b.role.value,
                   "count": b.count, "component_id": b.component_id} for b in spec.bom],
        "cost": format_cost(cost),
        "cost_complete": cost.complete,
        "cost_fully_grounded": cost.fully_grounded,
        "cost_estimated_parts": cost.fabricated,
        "cost_notes": cost.notes,
        "unpriced": cost.unpriced,
        "printed_parts": split.printed,
        "bought_parts": split.bought,
        "printed_share": round(split.printed_share, 4),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    written.append("bom.json")

    # S4: surface platform caps on MANIFEST (honest present/absent)
    try:
        from .platform_caps import extract_caps_snapshot

        caps_snap = extract_caps_snapshot(assessment=assessment)
        caps_dict = caps_snap.to_dict()
    except Exception:
        caps_dict = {
            "proof_package": getattr(assessment, "proof_package", None),
            "readiness_level": getattr(assessment, "readiness_level", None),
            "teacher_present": bool(getattr(assessment, "teacher_notes", None)),
            "community_score": None,
            "community_agent_sourced": None,
            "user_data_required": None,
            "present": {},
            "gaps": ["caps extract skipped"],
        }
        ce = getattr(assessment, "community_evidence", None) or {}
        if isinstance(ce, dict):
            caps_dict["community_score"] = ce.get("community_score")
            caps_dict["community_agent_sourced"] = ce.get("agent_sourced")
            caps_dict["user_data_required"] = ce.get("user_data_required")

    manifest = BundleManifest(
        out_dir=str(out),
        run_id=spec.run_id,
        idea=spec.idea,
        written=written,
        missing=missing,
        overall=assessment.overall,
        physics_ok=assessment.physics_ok,
        physics_checks=[c.validator for c in assessment.physics_checks],
        physics_gaps=list(assessment.physics_gaps),
        cost_summary=format_cost(cost),
        cost_complete=cost.complete,
        cost_fully_grounded=cost.fully_grounded,
        cost_estimated_parts=list(cost.fabricated),
        cost_notes=list(cost.notes),
        unpriced=list(cost.unpriced),
        printed_parts=split.printed,
        bought_parts=split.bought,
        printed_share=round(split.printed_share, 4),
        spec_gaps=list(spec.gaps),
        proof_package=caps_dict.get("proof_package"),
        readiness_level=caps_dict.get("readiness_level"),
        teacher_notes_present=bool(caps_dict.get("teacher_present")),
        community_score=caps_dict.get("community_score"),
        community_agent_sourced=caps_dict.get("community_agent_sourced"),
        user_data_required=caps_dict.get("user_data_required"),
        caps_present=caps_dict.get("present") or {},
        caps_gaps=list(caps_dict.get("gaps") or []),
    )
    (out / "MANIFEST.json").write_text(
        json.dumps(asdict(manifest), indent=2, ensure_ascii=False), encoding="utf-8")
    written.append("MANIFEST.json")

    # MISSING.md — written whenever anything is absent or unproven, so it cannot be overlooked
    # (a filament-ESTIMATED price and every cost note count as "unproven" — C-1/C-2 honesty)
    if missing or assessment.physics_gaps or not cost.complete or cost.fabricated or cost.notes or spec.gaps:
        lines = [f"# Was an diesem Bündel NICHT fertig/bewiesen ist: {spec.idea}", "",
                 "> Ehrliche Lückenliste — kein stilles Verschlucken. Jeder Punkt ist ein "
                 "nicht erzeugtes Lieferobjekt oder eine ausdrücklich nicht behauptete Eigenschaft.", ""]
        if missing:
            lines += ["## Nicht erzeugte Lieferobjekte", ""] + [f"- {m}" for m in missing] + [""]
        if not cost.complete and cost.unpriced:
            lines += ["## Ohne belegten Preis (Kosten sind eine partielle Untergrenze)", "",
                      *[f"- `{u}`" for u in cost.unpriced], ""]
        if cost.fabricated:
            lines += ["## Geschätzte Preise (gedruckte Teile — geschätzt aus Filament, "
                      "kein belegter Preis)", "",
                      *[f"- `{u}`" for u in cost.fabricated], ""]
        if cost.notes:
            lines += ["## Kosten-Hinweise (nicht belegte oder defekte Positionen)", "",
                      *[f"- {n}" for n in cost.notes], ""]
        if assessment.physics_gaps:
            lines += ["## Indizierte, aber nicht berechenbare Physik", "",
                      *[f"- {g}" for g in assessment.physics_gaps], ""]
        if spec.gaps:
            lines += ["## Ausdrücklich nicht behauptet (Lücken der Spezifikation)", "",
                      *[f"- {g}" for g in spec.gaps], ""]
        (out / "MISSING.md").write_text("\n".join(lines), encoding="utf-8")
        # rewrite manifest.written to include MISSING.md (kept honest: the file list is exact)
        written.append("MISSING.md")
        manifest = BundleManifest(**{**asdict(manifest), "written": written})
        (out / "MANIFEST.json").write_text(
            json.dumps(asdict(manifest), indent=2, ensure_ascii=False), encoding="utf-8")

    return manifest
