"""Realization package artifacts — structured BOM, harness section, drawings honesty (Phase C).

Used by ``integrator.build_full_mini_realization_package`` so the package on disk is
machine-readable (JSON) and honest about gaps (no silent empty drawings/BOM).
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


BOM_SCHEMA = "genesis-bom-v1"
HARNESS_SCHEMA = "genesis-harness-v1"
DRAWINGS_SCHEMA = "genesis-drawings-v1"
CAM_SCHEMA = "genesis-cam-v1"
READY_TO_BUILD_SCHEMA = "genesis-ready-to-build-v1"

#: Suffixes included in the Ready-to-Build manufacturer archive (H3).
_RTB_INCLUDE_SUFFIXES = frozenset({
    ".json", ".md", ".stl", ".dxf", ".nc", ".txt", ".html", ".csv", ".svg",
    ".kicad_pcb", ".kicad_sch", ".net",
})


@dataclass
class BomLine:
    """One structured BOM line (mechanical or electronic)."""

    id: str
    name: str
    domain: str  # "mechanical" | "electronic"
    quantity: float = 1.0
    unit: str = "ea"
    material_hint: str | None = None
    source_idea: str | None = None
    part_ref: str | None = None
    notes: list[str] = field(default_factory=list)
    provenance: str = "realization_package"


def build_mechanical_bom_lines(fragments: list[Any]) -> list[BomLine]:
    """C5: one mechanical line per CAD fragment with geometry provenance."""
    lines: list[BomLine] = []
    for i, frag in enumerate(fragments):
        cad = getattr(frag, "cad_artifact", None)
        if cad is None:
            continue
        spec = cad.spec
        safe = (
            str(spec.name)
            .replace(" ", "_")
            .replace("/", "_")
            .replace("\\", "_")
        )
        vol = getattr(cad, "volume_estimate_cm3", None)
        notes = []
        if vol is not None:
            notes.append(f"volume_est_cm3={vol}")
        notes.append(f"bbox_mm={spec.bounding_box_hint_mm}")
        notes.append(f"min_wall_mm={spec.min_wall_thickness_mm}")
        lines.append(
            BomLine(
                id=f"mech-{i}-{safe[:40]}",
                name=spec.name,
                domain="mechanical",
                quantity=1.0,
                unit="ea",
                material_hint=getattr(spec, "material_hint", None),
                source_idea=getattr(frag, "source_idea", None),
                part_ref=f"part_{i}_{safe}.stl",
                notes=notes,
                provenance="integrator.fragment.cad_artifact",
            )
        )
    return lines


def build_electronic_bom_lines(elec_bom_raw: Any, *, run_id: str | None = None) -> list[BomLine]:
    """C5: normalize electronics BOM pieces into BomLine list."""
    lines: list[BomLine] = []
    if not elec_bom_raw:
        return lines
    items = elec_bom_raw if isinstance(elec_bom_raw, list) else [elec_bom_raw]
    for i, item in enumerate(items):
        if hasattr(item, "id") and hasattr(item, "name"):
            lines.append(
                BomLine(
                    id=str(item.id),
                    name=str(item.name),
                    domain="electronic",
                    quantity=float(getattr(item, "count", 1) or 1),
                    unit="ea",
                    material_hint=None,
                    source_idea=None,
                    part_ref=getattr(item, "component_id", None),
                    notes=[f"role={getattr(getattr(item, 'role', None), 'value', getattr(item, 'role', ''))}"],
                    provenance="electronics.electronic_bom",
                )
            )
        elif isinstance(item, dict):
            lines.append(
                BomLine(
                    id=str(item.get("id") or f"elec-{i}"),
                    name=str(item.get("name") or item.get("refdes") or f"component-{i}"),
                    domain="electronic",
                    quantity=float(item.get("quantity") or item.get("count") or 1),
                    unit=str(item.get("unit") or "ea"),
                    material_hint=item.get("material"),
                    source_idea=item.get("source_idea"),
                    part_ref=item.get("part_number") or item.get("refdes"),
                    notes=[str(n) for n in (item.get("notes") or [])],
                    provenance="electronics.electronic_bom.dict",
                )
            )
        else:
            lines.append(
                BomLine(
                    id=f"elec-{i}",
                    name=str(item)[:120],
                    domain="electronic",
                    provenance="electronics.electronic_bom.str",
                )
            )
    if run_id:
        for ln in lines:
            ln.notes = list(ln.notes) + [f"run_id={run_id}"]
    return lines


def assemble_package_bom(
    fragments: list[Any],
    elec_bom_raw: Any = None,
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    """C5: unified structured BOM for the realization package."""
    mech = build_mechanical_bom_lines(fragments)
    elec = build_electronic_bom_lines(elec_bom_raw, run_id=run_id)
    gaps: list[str] = []
    if not mech:
        gaps.append("no mechanical fragments — mechanical BOM empty")
    if not elec:
        gaps.append(
            "no electronic BOM lines — electronics layer missing or empty "
            "(see electronics_bom.json / Elektriker path)"
        )
    lines = [*mech, *elec]
    return {
        "schema": BOM_SCHEMA,
        "run_id": run_id,
        "mechanical": [asdict(x) for x in mech],
        "electronic": [asdict(x) for x in elec],
        "lines": [asdict(x) for x in lines],
        "counts": {
            "mechanical": len(mech),
            "electronic": len(elec),
            "total": len(lines),
        },
        "gaps": gaps,
        "quelle": "gen.pipelines.realization_package.assemble_package_bom",
    }


def write_package_bom(pkg_root: Path, bom: dict[str, Any]) -> Path:
    path = pkg_root / "bom.json"
    path.write_text(json.dumps(bom, indent=2, ensure_ascii=False), encoding="utf-8")
    # Human-readable companion
    md_lines = [
        "# Bill of Materials (structured)",
        "",
        f"Schema: `{bom.get('schema')}` | total lines: {bom.get('counts', {}).get('total', 0)}",
        "",
        "## Mechanical",
    ]
    for ln in bom.get("mechanical") or []:
        md_lines.append(
            f"- **{ln['id']}**: {ln['name']} × {ln['quantity']} {ln['unit']} "
            f"(mat: {ln.get('material_hint')}; ref: {ln.get('part_ref')})"
        )
    md_lines += ["", "## Electronic"]
    for ln in bom.get("electronic") or []:
        md_lines.append(
            f"- **{ln['id']}**: {ln['name']} × {ln['quantity']} {ln['unit']} "
            f"(ref: {ln.get('part_ref')})"
        )
    if bom.get("gaps"):
        md_lines += ["", "## Gaps"]
        for g in bom["gaps"]:
            md_lines.append(f"- {g}")
    (pkg_root / "BOM.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return path


def build_harness_section(
    elec_pieces: dict[str, Any] | None,
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    """C6: structured harness + netlist + placement package section."""
    ep = elec_pieces or {}
    harness = ep.get("harness")
    netlist = ep.get("netlist")
    placement = ep.get("placement_hints") or ep.get("auto_placement") or []
    routed = ep.get("routed_harness") or {}

    def _to_data(obj: Any) -> Any:
        if obj is None:
            return None
        if hasattr(obj, "__dict__"):
            return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
        return obj

    gaps: list[str] = []
    if harness is None and not routed:
        gaps.append("no harness object — route_harness / Elektriker harness not produced")
    if netlist is None:
        gaps.append("no netlist — ERC/DRC needs electronics netlist")
    if not placement:
        gaps.append("no placement hints — board placement not computed")

    return {
        "schema": HARNESS_SCHEMA,
        "run_id": run_id,
        "harness": _to_data(harness),
        "routed_harness": _to_data(routed) if routed else None,
        "netlist": _to_data(netlist),
        "placement": [
            _to_data(p) if not isinstance(p, dict) else p for p in placement
        ],
        "gaps": gaps,
        "quelle": "gen.pipelines.realization_package.build_harness_section",
    }


def write_harness_section(pkg_root: Path, section: dict[str, Any]) -> Path:
    path = pkg_root / "harness_package.json"
    path.write_text(json.dumps(section, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    md = [
        "# Harness / Netlist / Placement",
        "",
        f"Schema: `{section.get('schema')}`",
        "",
        f"- harness present: {section.get('harness') is not None}",
        f"- netlist present: {section.get('netlist') is not None}",
        f"- placement entries: {len(section.get('placement') or [])}",
        "",
    ]
    if section.get("gaps"):
        md.append("## Gaps")
        for g in section["gaps"]:
            md.append(f"- {g}")
    (pkg_root / "HARNESS.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return path


#: Section views generated for parts with real CSG geometry: name -> (plane, offset)
#: H1: top + front + right (YZ). Isometric is a true 3-D projection, not a section — gap.
_DRAWING_VIEWS: dict[str, tuple[str, float]] = {
    "top": ("XY", 0.0),
    "front": ("XZ", 0.0),
    "right": ("YZ", 0.0),
}


def _generate_part_views(
    cad: Any,
) -> tuple[dict[str, str], dict[str, str], list[str], bool]:
    """Real dimensioned DXF section views from the artifact's CSG tree (G4+H1).

    Returns
    -------
    views : dict[str, str]
        view_name → DXF text (overall linear dimensions annotated when possible)
    sidecars : dict[str, str]
        view_name → human-readable ``.dims.txt`` content
    notes : list[str]
        per-view skip reasons / annotation notes
    dims_ok : bool
        True if at least one view carries overall dimension annotations
    """
    geometry = getattr(cad, "geometry", None)
    quantities = getattr(cad, "geometry_quantities", None) or {}
    if geometry is None or not quantities:
        return {}, {}, [], False
    try:
        from gen.export.drawing import (
            drawing_available,
            format_dimension_sidecar,
            section_dxf_dimensioned,
        )
    except Exception:  # pragma: no cover — export layer absent
        return {}, {}, [], False
    if not drawing_available():
        return {}, {}, [
            "drawing worker (build123d venv) unavailable — no DXF generated"
        ], False
    views: dict[str, str] = {}
    sidecars: dict[str, str] = {}
    notes: list[str] = []
    dims_ok = False
    for view_name, (plane, offset) in _DRAWING_VIEWS.items():
        try:
            dxf, info = section_dxf_dimensioned(
                geometry, quantities, plane=plane, offset=offset
            )
        except Exception as exc:  # ExportError (plane misses solid) et al. — honest skip
            notes.append(f"view {view_name!r} ({plane}) not generated: {exc}")
            continue
        if dxf and len(dxf) > 0:
            views[view_name] = dxf
            sidecars[view_name] = format_dimension_sidecar(
                info, plane=plane, offset=offset, label=f"view {view_name!r}"
            )
            dims_ok = True
            notes.append(
                f"view {view_name!r}: overall linear dimensions "
                f"{info.dimensions[0]:.3f} x {info.dimensions[1]:.3f} mm (envelope)"
            )
    return views, sidecars, notes, dims_ok


def build_drawings_section(
    fragments: list[Any],
    asm: Any,
    *,
    run_id: str | None = None,
    pkg_name: str = "",
) -> dict[str, Any]:
    """C7+G4+H1: drawings index + REAL dimensioned DXF section views (top/front/right)
    where the part carries CSG geometry; explicit drawing_gap otherwise.

    DXF texts travel under ``_view_texts`` ({(index, view): text}); dimension sidecars
    under ``_dim_sidecars`` ({(index, view): text}). Both are materialised and stripped
    by ``write_drawings_section``. Never a silent empty PDF/DXF.
    """
    parts: list[dict[str, Any]] = []
    view_texts: dict[tuple[int, str], str] = {}
    dim_sidecars: dict[tuple[int, str], str] = {}
    any_real_drawing = False
    any_dimensioned = False
    for i, frag in enumerate(fragments):
        cad = getattr(frag, "cad_artifact", None)
        if cad is None:
            continue
        spec = cad.spec
        views, sidecars, view_notes, dims_ok = _generate_part_views(cad)
        for view_name, dxf in views.items():
            view_texts[(i, view_name)] = dxf
        for view_name, text in sidecars.items():
            dim_sidecars[(i, view_name)] = text
        if views:
            any_real_drawing = True
        if dims_ok:
            any_dimensioned = True
        parts.append(
            {
                "index": i,
                "name": spec.name,
                "description": spec.description,
                "bbox_mm": list(spec.bounding_box_hint_mm),
                "min_wall_mm": spec.min_wall_thickness_mm,
                "volume_cm3": getattr(cad, "volume_estimate_cm3", None),
                "stl_ref": f"part_{i}_*.stl",
                "views_requested": ["isometric", "front", "top", "right"],
                "views_generated": sorted(views.keys()),
                "view_files": {
                    v: f"part_{i}_{v}.dxf" for v in sorted(views.keys())
                },
                "dimension_sidecars": {
                    v: f"part_{i}_{v}.dxf.dims.txt" for v in sorted(sidecars.keys())
                },
                "dimensions_annotated": dims_ok,
                "view_notes": view_notes,
            }
        )
    gaps = [
        "tolerance frames, surface finish symbols, hole callouts, title block "
        "not applied (full GD&T / production drawing gap)",
        "isometric view not generated (true 3-D projection, not a planar section)",
    ]
    if any_real_drawing:
        if any_dimensioned:
            gaps.insert(
                0,
                "overall envelope linear dimensions present on DXF sections; "
                "feature-level GD&T / multi-sheet PDF still required for shop sign-off",
            )
        else:
            gaps.insert(
                0,
                "DXF sections present but overall dimension annotation failed "
                "(ezdxf or bbox envelope issue) — geometry only",
            )
    else:
        gaps.insert(
            0,
            "full 2D GD&T / DXF / PDF drawings not generated — need CAD drafting "
            "(build123d/export drawing views)",
        )
    if not parts:
        gaps.insert(0, "no CAD fragments — drawing index empty")
    return {
        "schema": DRAWINGS_SCHEMA,
        "run_id": run_id,
        "package": pkg_name,
        "parts": parts,
        "assembly": {
            "combined_stl": bool(getattr(asm, "combined_stl", None)),
            "part_files": len(getattr(asm, "part_files", None) or []),
        },
        # honest: gap closes only when at least one REAL section drawing exists
        "drawing_gap": not any_real_drawing,
        "dimensions_annotated": any_dimensioned,
        "gaps": gaps,
        "quelle": "gen.pipelines.realization_package.build_drawings_section",
        "_view_texts": view_texts,
        "_dim_sidecars": dim_sidecars,
    }


def write_drawings_section(pkg_root: Path, section: dict[str, Any]) -> Path:
    # G4+H1: materialise real dimensioned DXF section views + dim sidecars; never empty files
    view_texts = section.pop("_view_texts", {}) or {}
    dim_sidecars = section.pop("_dim_sidecars", {}) or {}
    for (idx, view_name), dxf in view_texts.items():
        if dxf:
            (pkg_root / f"part_{idx}_{view_name}.dxf").write_text(
                dxf, encoding="utf-8"
            )
    for (idx, view_name), text in dim_sidecars.items():
        if text:
            (pkg_root / f"part_{idx}_{view_name}.dxf.dims.txt").write_text(
                text, encoding="utf-8"
            )
    path = pkg_root / "drawings.json"
    path.write_text(json.dumps(section, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# Drawings / Zeichnungen (Realisierungspaket)",
        "",
        f"Package: {section.get('package')} | Run: {section.get('run_id')}",
        f"**drawing_gap:** {section.get('drawing_gap')} (honest — no fabricated PDF)",
        f"**dimensions_annotated:** {section.get('dimensions_annotated')} "
        "(overall envelope linear dims on DXF when True)",
        "",
        "## Parts",
    ]
    for p in section.get("parts") or []:
        lines.append(f"### Part {p['index']}: {p['name']}")
        lines.append(f"- Description: {p.get('description')}")
        lines.append(f"- Bounding box hint (mm): {p.get('bbox_mm')}")
        lines.append(f"- Min wall: {p.get('min_wall_mm')} mm")
        lines.append(f"- Volume est: {p.get('volume_cm3')} cm³")
        lines.append(f"- STL: {p.get('stl_ref')}")
        lines.append(f"- Views requested: {', '.join(p.get('views_requested') or [])}")
        generated = p.get("views_generated") or []
        if generated:
            files = p.get("view_files") or {}
            lines.append(
                "- Views generated (real dimensioned DXF sections): "
                + ", ".join(f"{v} → `{files.get(v)}`" for v in generated)
            )
        sc = p.get("dimension_sidecars") or {}
        if sc:
            lines.append(
                "- Dimension sidecars: "
                + ", ".join(f"{v} → `{fn}`" for v, fn in sorted(sc.items()))
            )
        lines.append(f"- Dimensions annotated: {p.get('dimensions_annotated')}")
        for note in p.get("view_notes") or []:
            lines.append(f"- Note: {note}")
        lines.append("")
    lines.append("## Assembly")
    lines.append(f"- combined STL claimed: {section.get('assembly', {}).get('combined_stl')}")
    lines.append("")
    lines.append("## Gaps")
    for g in section.get("gaps") or []:
        lines.append(f"- {g}")
    lines.append("")
    lines.append(
        "**Scope (H1):** machine-generated top/front/right DXF *sections* with overall "
        "envelope linear dimensions from the CAD kernel. Full production GD&T (feature "
        "control frames, surface finish, multi-sheet PDF) still requires a drafting step."
    )
    (pkg_root / "DRAWINGS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _part_bbox_mm(cad: Any) -> tuple[float, float, float] | None:
    """Extract positive bbox (x,y,z) mm from a CAD artifact, or None."""
    spec = getattr(cad, "spec", None)
    if spec is None:
        return None
    bbox = getattr(spec, "bounding_box_hint_mm", None)
    if not bbox or len(bbox) < 3:
        return None
    try:
        bx, by, bz = float(bbox[0]), float(bbox[1]), float(bbox[2])
    except (TypeError, ValueError):
        return None
    if not (bx > 0 and by > 0 and bz > 0):
        return None
    return bx, by, bz


def _center_hole_diameter_mm(cad: Any) -> float | None:
    """Best-effort centre-hole diameter from geometry quantities (plate builder uses hr).

    Returns None when no positive hole radius quantity is present — helical bore is
    then skipped (not fabricated).
    """
    quantities = getattr(cad, "geometry_quantities", None) or {}
    for key in ("hr", "hole_r", "hole_radius", "bore_r"):
        q = quantities.get(key)
        if q is None:
            continue
        try:
            r = float(getattr(q, "value", q))
        except (TypeError, ValueError):
            continue
        if r > 0:
            return 2.0 * r
    return None


def build_cam_section(
    fragments: list[Any],
    *,
    run_id: str | None = None,
    pkg_name: str = "",
) -> dict[str, Any]:
    """H2: verified 2.5D G-code programs for each part bbox + multi-axis honesty.

    Emits profile + face_mill from bbox; helical_bore when a centre-hole diameter is
    known from geometry quantities. Every program must pass ``verify_gcode`` before
    inclusion — never a rubber-stamp .nc file. Multi-axis freeform is documented as
    unsupported via ``multi_axis_cam_capability``.
    """
    from gen.cad.gcode import (
        generate_face_mill_gcode,
        generate_helical_bore_gcode,
        generate_profile_gcode,
        multi_axis_cam_capability,
        verify_gcode,
    )

    parts: list[dict[str, Any]] = []
    program_texts: dict[tuple[int, str], str] = {}
    any_verified = False
    notes: list[str] = []

    for i, frag in enumerate(fragments):
        cad = getattr(frag, "cad_artifact", None)
        if cad is None:
            continue
        spec = cad.spec
        bbox = _part_bbox_mm(cad)
        if bbox is None:
            notes.append(f"part {i}: no positive bbox — CAM skipped")
            continue
        bx, by, bz = bbox
        ops_meta: list[dict[str, Any]] = []

        candidates: list[tuple[str, Any]] = [
            ("outside_profile", lambda: generate_profile_gcode(bx, by, bz)),
            ("face_mill", lambda: generate_face_mill_gcode(bx, by, face_depth_mm=min(0.5, bz))),
        ]
        hole_d = _center_hole_diameter_mm(cad)
        if hole_d is not None:
            # bore depth = full thickness; centre at plate origin (builder convention)
            depth = bz
            candidates.append(
                (
                    "helical_bore",
                    lambda d=hole_d, dep=depth: generate_helical_bore_gcode(
                        d, dep, center_x_mm=0.0, center_y_mm=0.0
                    ),
                )
            )
        else:
            notes.append(f"part {i}: no centre-hole quantity — helical_bore skipped")

        for op_name, factory in candidates:
            try:
                prog = factory()
            except (ValueError, TypeError) as exc:
                notes.append(f"part {i} op {op_name}: generate refused: {exc}")
                continue
            chk = verify_gcode(prog)
            if not chk.ok:
                notes.append(
                    f"part {i} op {op_name}: verify failed: {chk.issues[:3]}"
                )
                continue
            fname = f"part_{i}_{op_name}.nc"
            program_texts[(i, op_name)] = prog.text()
            any_verified = True
            ops_meta.append(
                {
                    "operation": op_name,
                    "file": fname,
                    "verified": True,
                    "n_lines": len(prog.lines),
                    "n_moves": chk.n_moves,
                    "bounds_mm": prog.bounds_mm,
                    "assumptions": list(prog.assumptions),
                    "gaps": list(prog.gaps),
                }
            )

        parts.append(
            {
                "index": i,
                "name": getattr(spec, "name", f"part_{i}"),
                "bbox_mm": [bx, by, bz],
                "operations": ops_meta,
                "n_programs": len(ops_meta),
            }
        )

    multi = multi_axis_cam_capability()
    gaps = list(multi.get("gaps") or [])
    if not any_verified:
        gaps.insert(0, "no verified G-code programs generated for package parts")
    else:
        gaps.insert(
            0,
            "verified 2.5D programs only (profile / face_mill / helical_bore when hole known); "
            "not a full multi-setup CNC job package",
        )

    return {
        "schema": CAM_SCHEMA,
        "run_id": run_id,
        "package": pkg_name,
        "parts": parts,
        "multi_axis": multi,
        "cam_gap": not any_verified,
        "gaps": gaps,
        "notes": notes,
        "quelle": "gen.pipelines.realization_package.build_cam_section",
        "_program_texts": program_texts,
    }


def write_cam_section(pkg_root: Path, section: dict[str, Any]) -> Path:
    """Write verified ``.nc`` programs + cam.json / CAM.md. Never empty .nc files."""
    program_texts = section.pop("_program_texts", {}) or {}
    for (idx, op_name), text in program_texts.items():
        if text and text.strip():
            (pkg_root / f"part_{idx}_{op_name}.nc").write_text(text, encoding="utf-8")
    path = pkg_root / "cam.json"
    path.write_text(json.dumps(section, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# CAM / CNC programs (Realisierungspaket)",
        "",
        f"Package: {section.get('package')} | Run: {section.get('run_id')}",
        f"**cam_gap:** {section.get('cam_gap')} (True only when no verified program)",
        "",
        "## Multi-axis capability",
    ]
    multi = section.get("multi_axis") or {}
    lines.append(f"- supported: {multi.get('supported')}")
    lines.append(f"- level: {multi.get('level')}")
    lines.append(f"- axes: {multi.get('axes')}")
    lines.append(f"- ops available: {', '.join(multi.get('ops_available') or [])}")
    lines.append("")
    lines.append("## Parts")
    for p in section.get("parts") or []:
        lines.append(f"### Part {p['index']}: {p.get('name')}")
        lines.append(f"- BBox (mm): {p.get('bbox_mm')}")
        for op in p.get("operations") or []:
            lines.append(
                f"- `{op['operation']}` → `{op['file']}` "
                f"(verified={op.get('verified')}, lines={op.get('n_lines')}, "
                f"moves={op.get('n_moves')})"
            )
        if not p.get("operations"):
            lines.append("- (no verified programs)")
        lines.append("")
    if section.get("notes"):
        lines.append("## Notes")
        for n in section["notes"]:
            lines.append(f"- {n}")
        lines.append("")
    lines.append("## Gaps")
    for g in section.get("gaps") or []:
        lines.append(f"- {g}")
    lines.append("")
    lines.append(
        "**Scope (H2):** verified RS-274 2.5D programs from part bbox (+ helical bore "
        "when hole radius is known). Multi-axis freeform CAM is explicitly unsupported."
    )
    (pkg_root / "CAM.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _rtb_category(path: Path) -> str:
    """Bucket a package file into a manufacturer-facing inventory category."""
    name = path.name.lower()
    suf = path.suffix.lower()
    if name in ("manifest.json", "ready_to_build.json"):
        return "manifest"
    if name.startswith("bom") or name == "bom.json":
        return "bom"
    if "harness" in name or "netlist" in name or "placement" in name:
        return "harness"
    if suf == ".dxf" or name.startswith("drawing") or name.endswith(".dims.txt"):
        return "drawings"
    if suf == ".nc" or name.startswith("cam"):
        return "cam"
    if suf == ".stl":
        return "geometry"
    if "montage" in name or "schaltplan" in name or "regulatorik" in name:
        return "docs"
    if suf in (".md", ".html", ".txt"):
        return "docs"
    if "electronics" in name or suf in (".kicad_pcb", ".kicad_sch", ".net"):
        return "electronics"
    return "other"


def collect_ready_to_build_files(pkg_root: Path) -> list[Path]:
    """List files that belong in the manufacturer ZIP (no nested zips, no dotfiles)."""
    root = Path(pkg_root)
    if not root.is_dir():
        raise ValueError(f"collect_ready_to_build_files: not a directory: {root}")
    out: list[Path] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.name.startswith("."):
            continue
        if p.suffix.lower() == ".zip":
            continue
        if p.suffix.lower() and p.suffix.lower() not in _RTB_INCLUDE_SUFFIXES:
            # allow extensionless only if named known artifacts — skip binaries we don't claim
            continue
        out.append(p)
    return out


def build_ready_to_build_zip(
    pkg_root: Path,
    *,
    zip_name: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """H3: pack the realization package into one manufacturer-facing ZIP.

    Includes BOM, harness, dimensioned DXFs, verified G-code, STLs, and docs when
    present. Never fabricates missing artifacts — inventory + gaps list what is
    and is not in the archive. The ZIP itself is written *inside* ``pkg_root``
    and is excluded from nested re-packing.

    Returns a serialisable meta dict (also written as ``ready_to_build.json``).
    """
    root = Path(pkg_root)
    if not root.is_dir():
        raise ValueError(f"build_ready_to_build_zip: package root missing: {root}")

    zip_fname = zip_name or f"{root.name}_ready_to_build.zip"
    zip_path = root / zip_fname

    def _inventory_for(paths: list[Path]) -> dict[str, list[str]]:
        inv: dict[str, list[str]] = {
            "manifest": [],
            "bom": [],
            "harness": [],
            "drawings": [],
            "cam": [],
            "geometry": [],
            "electronics": [],
            "docs": [],
            "other": [],
        }
        for p in paths:
            inv[_rtb_category(p)].append(p.relative_to(root).as_posix())
        return inv

    # Draft meta + docs first so they are included in the archive
    files_pre = collect_ready_to_build_files(root)
    inventory_pre = _inventory_for(files_pre)
    has_manifest = bool(inventory_pre["manifest"]) or (root / "manifest.json").is_file()
    has_payload = bool(
        inventory_pre["bom"]
        or inventory_pre["geometry"]
        or inventory_pre["cam"]
        or inventory_pre["drawings"]
    )
    gaps: list[str] = []
    if not has_manifest:
        gaps.append("manifest.json missing from package root")
    if not inventory_pre["bom"]:
        gaps.append("structured BOM not in archive")
    if not inventory_pre["geometry"]:
        gaps.append("no STL geometry in archive")
    if not inventory_pre["drawings"]:
        gaps.append("no DXF/drawing files in archive")
    if not inventory_pre["cam"]:
        gaps.append("no CAM/G-code files in archive")
    if not inventory_pre["harness"]:
        gaps.append("no harness/netlist section in archive")
    gaps.append(
        "full factory sign-off (GD&T PDF, multi-axis CAM, copper PCB) not claimed — "
        "see package gap lists"
    )

    meta: dict[str, Any] = {
        "schema": READY_TO_BUILD_SCHEMA,
        "run_id": run_id,
        "package_dir": root.name,
        "zip_file": zip_fname,
        "zip_path": str(zip_path),
        "n_files_archived": 0,
        "size_bytes": 0,
        "inventory": {k: v for k, v in inventory_pre.items() if v},
        "inventory_counts": {k: len(v) for k, v in inventory_pre.items() if v},
        # ready = minimum usable manufacturer handoff, NOT factory-complete
        "ready": has_manifest and has_payload,
        "gaps": gaps,
        "quelle": "gen.pipelines.realization_package.build_ready_to_build_zip",
    }
    (root / "ready_to_build.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (root / "READY_TO_BUILD.md").write_text(
        "\n".join(
            [
                "# Ready-to-Build package",
                "",
                f"**ZIP:** `{zip_fname}`",
                f"**ready (min handoff):** {meta['ready']}",
                f"**run_id:** {run_id}",
                "",
                "## Gaps",
                *[f"- {g}" for g in gaps],
                "",
                "**Scope (H3):** one ZIP of artifacts this run actually produced. "
                "Not a claim of complete factory documentation.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    files = collect_ready_to_build_files(root)
    inventory = _inventory_for(files)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            zf.write(p, arcname=p.relative_to(root).as_posix())
        zf.writestr(
            "READY_TO_BUILD_README.txt",
            (
                "GENESIS Ready-to-Build package\n"
                f"run_id: {run_id or 'n/a'}\n"
                f"source_dir: {root.name}\n"
                "Contents are only what this run actually produced.\n"
                "See ready_to_build.json inventory + gaps for honesty.\n"
                "Full GD&T sign-off, multi-axis CAM, and PCB copper remain product gaps\n"
                "when listed there — they are never fabricated into this ZIP.\n"
            ),
        )

    size = zip_path.stat().st_size
    if size <= 0:
        raise ValueError("build_ready_to_build_zip: produced empty archive (refusing)")

    meta["n_files_archived"] = len(files)
    meta["size_bytes"] = size
    meta["inventory"] = {k: v for k, v in inventory.items() if v}
    meta["inventory_counts"] = {k: len(v) for k, v in inventory.items() if v}
    meta["ready"] = bool(
        (inventory.get("manifest") or has_manifest)
        and (
            inventory.get("bom")
            or inventory.get("geometry")
            or inventory.get("cam")
            or inventory.get("drawings")
        )
    )
    (root / "ready_to_build.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    # Refresh MD with final counts (outside ZIP is fine; JSON inside has draft counts OK)
    inv_block: list[str] = []
    for cat, paths in sorted((meta.get("inventory") or {}).items()):
        inv_block.append(f"### {cat} ({len(paths)})")
        for rel in paths[:40]:
            inv_block.append(f"- `{rel}`")
        if len(paths) > 40:
            inv_block.append(f"- … +{len(paths) - 40} more")
        inv_block.append("")
    (root / "READY_TO_BUILD.md").write_text(
        "\n".join(
            [
                "# Ready-to-Build package",
                "",
                f"**ZIP:** `{zip_fname}` ({size} bytes, {len(files)} files)",
                f"**ready (min handoff):** {meta['ready']}",
                f"**run_id:** {run_id}",
                "",
                "## Inventory",
                *inv_block,
                "## Gaps",
                *[f"- {g}" for g in gaps],
                "",
                "**Scope (H3):** one ZIP of artifacts this run actually produced. "
                "Not a claim of complete factory documentation.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return meta
