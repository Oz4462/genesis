"""Realization package artifacts — structured BOM, harness section, drawings honesty (Phase C).

Used by ``integrator.build_full_mini_realization_package`` so the package on disk is
machine-readable (JSON) and honest about gaps (no silent empty drawings/BOM).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


BOM_SCHEMA = "genesis-bom-v1"
HARNESS_SCHEMA = "genesis-harness-v1"
DRAWINGS_SCHEMA = "genesis-drawings-v1"


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
_DRAWING_VIEWS: dict[str, tuple[str, float]] = {"top": ("XY", 0.0), "front": ("XZ", 0.0)}


def _generate_part_views(cad: Any) -> tuple[dict[str, str], list[str]]:
    """Real DXF section views from the artifact's CSG tree (G4).

    Returns ({view_name: dxf_text}, notes). Empty dict when the artifact has no
    geometry or the drawing worker (build123d venv) is unavailable — the caller
    keeps drawing_gap=True then. Never a fabricated drawing.
    """
    geometry = getattr(cad, "geometry", None)
    quantities = getattr(cad, "geometry_quantities", None) or {}
    if geometry is None or not quantities:
        return {}, []
    try:
        from gen.export.drawing import drawing_available, section_dxf
    except Exception:  # pragma: no cover — export layer absent
        return {}, []
    if not drawing_available():
        return {}, ["drawing worker (build123d venv) unavailable — no DXF generated"]
    views: dict[str, str] = {}
    notes: list[str] = []
    for view_name, (plane, offset) in _DRAWING_VIEWS.items():
        try:
            dxf = section_dxf(geometry, quantities, plane=plane, offset=offset)
        except Exception as exc:  # ExportError (plane misses solid) et al. — honest skip
            notes.append(f"view {view_name!r} ({plane}) not generated: {exc}")
            continue
        if dxf and len(dxf) > 0:
            views[view_name] = dxf
    return views, notes


def build_drawings_section(
    fragments: list[Any],
    asm: Any,
    *,
    run_id: str | None = None,
    pkg_name: str = "",
) -> dict[str, Any]:
    """C7+G4: structured drawings index + REAL DXF section views where the part
    carries CSG geometry; explicit drawing_gap otherwise (no silent empty PDF).

    DXF texts travel under the reserved ``_view_texts`` key ({(index, view): text})
    and are written to files (and stripped) by ``write_drawings_section``.
    """
    parts: list[dict[str, Any]] = []
    view_texts: dict[tuple[int, str], str] = {}
    any_real_drawing = False
    for i, frag in enumerate(fragments):
        cad = getattr(frag, "cad_artifact", None)
        if cad is None:
            continue
        spec = cad.spec
        views, view_notes = _generate_part_views(cad)
        for view_name, dxf in views.items():
            view_texts[(i, view_name)] = dxf
        if views:
            any_real_drawing = True
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
                "view_notes": view_notes,
            }
        )
    gaps = [
        "tolerance frames and surface finish symbols not applied (GD&T gap)",
    ]
    if any_real_drawing:
        gaps.insert(
            0,
            "isometric/right views + dimension annotations not generated "
            "(only real top/front DXF sections)",
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
        "gaps": gaps,
        "quelle": "gen.pipelines.realization_package.build_drawings_section",
        "_view_texts": view_texts,
    }


def write_drawings_section(pkg_root: Path, section: dict[str, Any]) -> Path:
    # G4: materialise real DXF section views as files; never write empty files
    view_texts = section.pop("_view_texts", {}) or {}
    for (idx, view_name), dxf in view_texts.items():
        if dxf:
            (pkg_root / f"part_{idx}_{view_name}.dxf").write_text(
                dxf, encoding="utf-8"
            )
    path = pkg_root / "drawings.json"
    path.write_text(json.dumps(section, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# Drawings / Zeichnungen (Realisierungspaket)",
        "",
        f"Package: {section.get('package')} | Run: {section.get('run_id')}",
        f"**drawing_gap:** {section.get('drawing_gap')} (honest — no fabricated PDF)",
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
                "- Views generated (real DXF sections): "
                + ", ".join(f"{v} → `{files.get(v)}`" for v in generated)
            )
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
        "**Scope:** machine-generated package drawing *index* from CAD fragments. "
        "Full 2D GD&T / DXF / PDF still requires a CAD drafting step."
    )
    (pkg_root / "DRAWINGS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
