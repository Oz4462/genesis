"""cad assembly support (CAD-Vertiefung, GENESIS_TODO Item 4).

Erzeugt Baugruppen (Assemblies) aus SystemConcept + realen CAD-Exports (z.B. aus
prototype_cad_builder oder Integrator-Fragmenten).

P0-1 (2026-07-15) — Integritäts-Fix: Diese Datei erzeugte früher stille 0-Byte-
STL-Platzhalter (leere Tempfiles) und deklarierte `combined_stl` als Kopie des
ersten Teils. Beides ist entfernt. Jetzt gilt:

  * ``part_files`` enthält NUR real existierende, nicht-leere STL-Dateien.
  * Fehlt einem Teil die Geometrie, entsteht KEINE Datei — stattdessen ein
    expliziter Eintrag in ``gaps`` (und im Manifest).
  * ``combined_stl`` ist eine ECHTE Kernel-Union der Teil-Geometrien
    (CSG-Bäume der Artefakte, je Teil verschoben, via cadquery_bridge) — oder
    ``None`` mit Gap-Eintrag. Nie eine umbenannte Einzelteil-Kopie.

Später: volle Constraints, Exploded Views, BOM-Integration.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Optional, Union

from ..core.errors import GeometryError
from ..core.state import GeometryNode, Quantity, ValueOrigin
from .prototype_cad_builder import BuildArtifact, PrototypeSpec, build_prototype_cad

# For compatibility with fragments
try:
    from gen.pipelines.integrator import RealizationFragment
except ImportError:
    RealizationFragment = None  # type: ignore


@dataclass(frozen=True)
class AssemblyPart:
    """Ein Teil in der Baugruppe mit Position/Label."""
    spec: PrototypeSpec
    label: str
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)  # simple offset for demo
    artifact: Optional[BuildArtifact] = None


#: Supported constraint kinds (H5 first stone — explicit, not freeform FreeCAD mates).
CONSTRAINT_KINDS = frozenset({"offset", "stack_z", "align_xy"})


@dataclass(frozen=True)
class AssemblyConstraint:
    """H5: one assembly placement constraint between two parts (or part vs world).

    Kinds
    -----
    offset
        place ``moving`` at ``fixed`` position + ``offset_mm``
    stack_z
        place ``moving`` on top of ``fixed``: same XY, Z = fixed.Z + fixed_height + gap
    align_xy
        share XY with ``fixed``; keep ``moving`` Z (or use offset Z)

    FreeCAD seam / full mate solver remain explicit gaps.
    """

    kind: str
    fixed: str  # part label (or "WORLD")
    moving: str  # part label that receives the solved position
    offset_mm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    gap_mm: float = 0.0
    note: str = ""

    def __post_init__(self) -> None:
        if self.kind not in CONSTRAINT_KINDS:
            raise ValueError(
                f"AssemblyConstraint: kind must be one of {sorted(CONSTRAINT_KINDS)}, "
                f"got {self.kind!r}"
            )
        if not self.moving:
            raise ValueError("AssemblyConstraint: moving label must be non-empty")
        if not self.fixed:
            raise ValueError("AssemblyConstraint: fixed label must be non-empty")


def resolve_constraint_positions(
    labels: list[str],
    constraints: list[AssemblyConstraint],
    *,
    part_heights_mm: dict[str, float] | None = None,
    world_origin: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> tuple[dict[str, tuple[float, float, float]], list[str]]:
    """Solve part positions from a list of AssemblyConstraint (H5).

    Deterministic single-pass: constraints applied in order. Unknown labels or
    cyclic/unresolved moves produce gap notes rather than invented positions.
    Returns (positions_by_label, gaps).
    """
    heights = part_heights_mm or {}
    pos: dict[str, tuple[float, float, float]] = {}
    gaps: list[str] = []
    label_set = set(labels)

    # First label anchors at world unless constrained as moving later
    if labels:
        pos[labels[0]] = world_origin

    for c in constraints:
        if c.moving not in label_set:
            gaps.append(f"constraint ignored: moving {c.moving!r} not in assembly")
            continue
        if c.fixed != "WORLD" and c.fixed not in label_set:
            gaps.append(f"constraint ignored: fixed {c.fixed!r} not in assembly")
            continue
        if c.fixed == "WORLD":
            base = world_origin
        elif c.fixed in pos:
            base = pos[c.fixed]
        else:
            gaps.append(
                f"constraint deferred/unresolved: fixed {c.fixed!r} has no position yet "
                f"(order constraints so fixed is placed first)"
            )
            continue

        ox, oy, oz = c.offset_mm
        if c.kind == "offset":
            pos[c.moving] = (base[0] + ox, base[1] + oy, base[2] + oz)
        elif c.kind == "stack_z":
            h = float(heights.get(c.fixed, 0.0))
            pos[c.moving] = (
                base[0] + ox,
                base[1] + oy,
                base[2] + h + float(c.gap_mm) + oz,
            )
        elif c.kind == "align_xy":
            prev_z = pos.get(c.moving, (0.0, 0.0, base[2]))[2]
            pos[c.moving] = (base[0] + ox, base[1] + oy, prev_z + oz)
        else:  # pragma: no cover — guarded by __post_init__
            gaps.append(f"unknown constraint kind {c.kind!r}")

    for lab in labels:
        if lab not in pos:
            gaps.append(f"part {lab!r}: no constraint placed it — left unpositioned")
    return pos, gaps


def default_spacing_constraints(labels: list[str]) -> list[AssemblyConstraint]:
    """Legacy demo spacing as explicit constraints (H5 honesty vs free offsets)."""
    if not labels:
        return []
    out: list[AssemblyConstraint] = [
        AssemblyConstraint(kind="offset", fixed="WORLD", moving=labels[0], offset_mm=(0, 0, 0))
    ]
    # same spacing pattern as the old hardcoded offsets
    spacings = [(150.0, 0.0, 0.0), (0.0, 110.0, 0.0), (150.0, 110.0, 0.0)]
    for i, lab in enumerate(labels[1:4]):
        dx, dy, dz = spacings[i % len(spacings)]
        out.append(
            AssemblyConstraint(
                kind="offset",
                fixed=labels[0],
                moving=lab,
                offset_mm=(dx, dy, dz),
                note="default demo spacing (not a FreeCAD mate)",
            )
        )
    return out


@dataclass(frozen=True)
class AssemblySpec:
    """Die Baugruppen-Spez."""
    name: str
    parts: list[AssemblyPart]
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None
    constraints: list[AssemblyConstraint] = field(default_factory=list)


@dataclass(frozen=True)
class AssemblyArtifact:
    """Output der Assembly: reale part_files + echte Kernel-Union (oder ehrliche Gaps)."""
    spec: AssemblySpec
    combined_stl: Optional[str] = None  # real kernel union, or None (see gaps)
    part_files: list[str] = field(default_factory=list)
    manifest: dict[str, Any] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)
    run_id: str | None = None
    quelle: str | None = None


def _is_real_file(path: str | None) -> bool:
    """True iff path names an existing, NON-EMPTY file (the anti-0-byte gate)."""
    return bool(path) and os.path.isfile(str(path)) and os.path.getsize(str(path)) > 0


def _prefix_tree(node: GeometryNode, prefix: str) -> GeometryNode:
    """Copy a CSG tree with all quantity_ids prefixed (collision-free merging)."""
    return GeometryNode(
        kind=node.kind,
        params={k: prefix + v for k, v in node.params.items()},
        children=[_prefix_tree(c, prefix) for c in node.children],
    )


def _prefix_quantities(
    quantities: dict[str, Quantity], prefix: str
) -> dict[str, Quantity] | None:
    """Prefix quantity ids. Returns None when any quantity carries a derivation
    (its formula references the old ids — prefixing would silently break it)."""
    out: dict[str, Quantity] = {}
    for qid, q in quantities.items():
        if q.derivation is not None:
            return None
        out[prefix + qid] = replace(q, id=prefix + qid)
    return out


def _offset_quantity(qid: str, value: float) -> Quantity:
    return Quantity(
        id=qid,
        name=qid.replace("_", " "),
        value=float(value),
        unit="mm",
        origin=ValueOrigin.DECISION,
        rationale="assembly placement offset (demo spacing, cad/assembly)",
    )


def _combine_real(
    parts_with_geometry: list[tuple[AssemblyPart, GeometryNode, dict[str, Quantity]]],
    name: str,
    run_id: str | None,
    gaps: list[str],
) -> str | None:
    """REAL kernel union of the parts' CSG trees (each translated to its
    position). Returns the written STL path, or None with a gap entry."""
    from .cadquery_bridge import cad_available, to_stl

    if len(parts_with_geometry) < 2:
        return None
    if not cad_available():
        gaps.append("combined STL not built: CAD kernel (cad-venv) unavailable")
        return None

    merged_q: dict[str, Quantity] = {}
    children: list[GeometryNode] = []
    for i, (part, node, quantities) in enumerate(parts_with_geometry):
        prefix = f"p{i}_"
        pq = _prefix_quantities(quantities, prefix)
        if pq is None:
            gaps.append(
                f"combined STL not built: part {part.label!r} carries DERIVED "
                f"quantities (prefixing would break derivations)"
            )
            return None
        merged_q.update(pq)
        ox, oy, oz = part.position
        for axis, val in (("x", ox), ("y", oy), ("z", oz)):
            oq = _offset_quantity(f"{prefix}asm_off_{axis}", val)
            merged_q[oq.id] = oq
        children.append(
            GeometryNode(
                kind="translate",
                params={
                    "x": f"{prefix}asm_off_x",
                    "y": f"{prefix}asm_off_y",
                    "z": f"{prefix}asm_off_z",
                },
                children=[_prefix_tree(node, prefix)],
            )
        )

    union = GeometryNode(kind="union", params={}, children=children)
    try:
        stl_text = to_stl(union, merged_q, name=f"{name}_combined")
    except GeometryError as exc:
        gaps.append(f"combined STL not built: kernel union failed ({exc})")
        return None
    if not stl_text or "facet" not in stl_text:
        gaps.append("combined STL not built: kernel returned no tessellation")
        return None

    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") or "assembly"
    out_dir = Path("out") / "cad"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{safe}_{run_id or 'asm'}_combined.stl"
    path.write_text(stl_text)
    if path.stat().st_size == 0:  # never ship an empty artifact
        path.unlink()
        gaps.append("combined STL not built: kernel produced an empty file")
        return None
    return str(path)


def build_assembly(
    parts: list[Union[PrototypeSpec, BuildArtifact, "RealizationFragment"]],
    name: str = "Jetpack Assembly",
    *,
    run_id: str | None = None,
    constraints: list[AssemblyConstraint] | None = None,
) -> AssemblyArtifact:
    """
    Baut eine Assembly aus Specs/Artifacts/Fragments (z.B. aus dem Integrator).

    Teile mit realer Geometrie liefern reale STL-Dateien (Kernel-Export über den
    prototype_cad_builder bzw. dessen exports); Teile ohne Geometrie erzeugen
    KEINE Datei, sondern einen ehrlichen ``gaps``-Eintrag. ``combined_stl`` ist
    eine echte Kernel-Union der CSG-Bäume oder ``None``.

    H5: optional ``constraints`` place parts via ``resolve_constraint_positions``;
    when omitted, default spacing constraints replace the old free offsets
    (same numeric result, but constraints are recorded in the manifest).
    """
    # First pass: materialise specs/artifacts (positions filled after constraints)
    pending: list[tuple[str, PrototypeSpec, BuildArtifact | None]] = []
    gaps: list[str] = []

    for i, p in enumerate(parts[:3]):  # limit for first stone
        art: BuildArtifact | None = None
        spec: PrototypeSpec | None = None
        if isinstance(p, PrototypeSpec):
            art = build_prototype_cad(p, run_id=f"{run_id or 'asm'}-part{i}")
            spec = p
        elif isinstance(p, BuildArtifact):
            art = p
            spec = getattr(p, "spec", None) or PrototypeSpec(
                name=f"part{i}", description="from artifact", bounding_box_hint_mm=(10, 10, 10)
            )
        elif hasattr(p, "cad_artifact") and getattr(p, "cad_artifact", None) is not None:
            art = p.cad_artifact
            spec = getattr(art, "spec", None) or PrototypeSpec(
                name=f"part{i}", description="from frag", bounding_box_hint_mm=(10, 10, 10)
            )
        else:
            continue

        if art is None or spec is None:
            continue
        pending.append((spec.name, spec, art))

    labels = [lab for lab, _, _ in pending]
    heights = {
        lab: float(spec.bounding_box_hint_mm[2])
        for lab, spec, _ in pending
    }
    used_constraints = (
        list(constraints) if constraints is not None else default_spacing_constraints(labels)
    )
    positions, c_gaps = resolve_constraint_positions(
        labels, used_constraints, part_heights_mm=heights
    )
    gaps.extend(c_gaps)
    constraint_limitations = [
        "FreeCAD / full mate solver not integrated — only offset/stack_z/align_xy constraints"
    ]

    assembly_parts: list[AssemblyPart] = []
    part_files: list[str] = []
    part_file_by_label: dict[str, str | None] = {}
    parts_with_geometry: list[tuple[AssemblyPart, GeometryNode, dict[str, Quantity]]] = []

    for lab, spec, art in pending:
        pos = positions.get(lab, (0.0, 0.0, 0.0))
        part = AssemblyPart(spec=spec, label=lab, position=pos, artifact=art)
        assembly_parts.append(part)

        geometry = getattr(art, "geometry", None) if art is not None else None
        quantities = (getattr(art, "geometry_quantities", None) or {}) if art else {}
        if geometry is not None:
            parts_with_geometry.append((part, geometry, quantities))

        # ONLY real, non-empty files enter part_files — no placeholder, ever.
        stl = art.exports.get("stl") if art and isinstance(getattr(art, "exports", {}), dict) else None
        if _is_real_file(stl):
            part_files.append(str(stl))
            part_file_by_label[lab] = str(stl)
        else:
            part_file_by_label[lab] = None
            gaps.append(
                f"part {lab!r}: no real STL on disk "
                f"(export absent or kernel unavailable) — honest gap, no placeholder file"
            )

    combined_stl = _combine_real(parts_with_geometry, name, run_id, gaps)
    if combined_stl is None and len(assembly_parts) > 1 and not any(
        g.startswith("combined STL not built") for g in gaps
    ):
        gaps.append(
            "combined STL not built: fewer than 2 parts carry CSG geometry"
        )

    manifest = {
        "name": name,
        "num_parts": len(assembly_parts),
        "parts": [
            {"label": ap.label, "pos": ap.position, "stl": part_file_by_label.get(ap.label)}
            for ap in assembly_parts
        ],
        "constraints": [
            {
                "kind": c.kind,
                "fixed": c.fixed,
                "moving": c.moving,
                "offset_mm": list(c.offset_mm),
                "gap_mm": c.gap_mm,
                "note": c.note,
            }
            for c in used_constraints
        ],
        "constraint_limitations": constraint_limitations,
        "combined": combined_stl,
        "gaps": list(gaps),
    }

    quelle = (
        "cad/assembly (P0-1 real-geometry + H5 constraints) + cadquery_bridge kernel union "
        "+ GENESIS_TODO + Integrator/CAD real + PLAN §3.6"
    )

    return AssemblyArtifact(
        spec=AssemblySpec(
            name=name,
            parts=assembly_parts,
            zusammenfassung=f"Assembly of {len(assembly_parts)} parts from specs/fragments (real files: {len(part_files)}, gaps: {len(gaps)}).",
            run_id=run_id,
            quelle=quelle,
            constraints=list(used_constraints),
        ),
        combined_stl=combined_stl,
        part_files=part_files,
        manifest=manifest,
        gaps=gaps,
        run_id=run_id,
        quelle=quelle,
    )
