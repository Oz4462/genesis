"""Export a γ Specification's parametric CSG geometry to OpenSCAD source.

OpenSCAD is the canonical script-based CSG modeller ("The Programmers Solid 3D
CAD Modeller", openscad.org); its syntax is the natural target for GENESIS'
GeometryNode tree (PHASE_GAMMA.md §3.3/§10). This exporter is deterministic and
LLM-free: it resolves each parameter quantity_id to its concrete value and emits
the documented OpenSCAD primitives, annotating every dimension with the
originating quantity id so the export stays traceable to the ledger.

OpenSCAD syntax used (from the OpenSCAD language manual):
  cube([x, y, z]);        cylinder(h=H, r=R);     sphere(r=R);
  union() { ... }         difference() { ... }    intersection() { ... }
  translate([x, y, z]) { ... }

A node the exporter cannot faithfully render (unknown kind, missing param, a
param referencing an absent quantity) raises ``ExportError`` — never a guessed
number. The exporter assumes a GATE-γ-validated spec (which already enforces the
geometry shape, C-9), but fails loudly rather than fabricating output.
"""

from __future__ import annotations

from ..core.errors import ExportError, GeometryError
from ..core.state import (
    GEOMETRY_OPERATIONS,
    GEOMETRY_PRIMITIVES,
    GEOMETRY_TRANSFORMS,
    Component,
    GeometryNode,
    Quantity,
    Specification,
)
from ..verification.geometry import aabb_of
from ._text import single_line as _single_line
from .numfmt import fmt_number as _fmt

_INDENT = "  "


def _resolve(node: GeometryNode, param: str, quantities: dict[str, Quantity]) -> tuple[str, str]:
    """Return (rendered_value, quantity_id) for one geometry param, or raise."""
    qid = node.params.get(param)
    if qid is None:
        raise ExportError(f"geometry {node.kind!r} is missing parameter {param!r}")
    quantity = quantities.get(qid)
    if quantity is None:
        raise ExportError(
            f"geometry {node.kind!r} param {param!r} references unknown quantity {qid!r}"
        )
    return _fmt(quantity.value), qid


def _emit(node: GeometryNode, quantities: dict[str, Quantity], depth: int) -> list[str]:
    pad = _INDENT * depth
    kind = node.kind

    if kind in GEOMETRY_PRIMITIVES:
        if kind == "box":
            sx, qx = _resolve(node, "size_x", quantities)
            sy, qy = _resolve(node, "size_y", quantities)
            sz, qz = _resolve(node, "size_z", quantities)
            # center=true so OpenSCAD matches the centered-primitive convention
            # shared by build123d and Phase δ's AABB math (PHASE_DELTA.md §1).
            return [f"{pad}cube([{sx}, {sy}, {sz}], center=true); // size_x={qx}, size_y={qy}, size_z={qz}"]
        if kind == "cylinder":
            r, qr = _resolve(node, "radius", quantities)
            h, qh = _resolve(node, "height", quantities)
            return [f"{pad}cylinder(h={h}, r={r}, center=true); // height={qh}, radius={qr}"]
        if kind == "sphere":
            r, qr = _resolve(node, "radius", quantities)
            return [f"{pad}sphere(r={r}); // radius={qr}"]

    if kind in GEOMETRY_OPERATIONS:
        lines = [f"{pad}{kind}() {{"]
        for child in node.children:
            lines.extend(_emit(child, quantities, depth + 1))
        lines.append(f"{pad}}}")
        return lines

    if kind in GEOMETRY_TRANSFORMS:
        if kind == "translate":
            x, qx = _resolve(node, "x", quantities)
            y, qy = _resolve(node, "y", quantities)
            z, qz = _resolve(node, "z", quantities)
            lines = [f"{pad}translate([{x}, {y}, {z}]) {{ // x={qx}, y={qy}, z={qz}"]
            for child in node.children:
                lines.extend(_emit(child, quantities, depth + 1))
            lines.append(f"{pad}}}")
            return lines
        if kind == "rotate":
            ax, qax = _resolve(node, "axis_x", quantities)
            ay, qay = _resolve(node, "axis_y", quantities)
            az, qaz = _resolve(node, "axis_z", quantities)
            a, qa = _resolve(node, "angle_deg", quantities)
            # OpenSCAD rotate(a, v): angle in degrees about axis v through the
            # origin — exactly the shared geometry convention.
            lines = [f"{pad}rotate(a={a}, v=[{ax}, {ay}, {az}]) {{ // angle_deg={qa}, axis=({qax}, {qay}, {qaz})"]
            for child in node.children:
                lines.extend(_emit(child, quantities, depth + 1))
            lines.append(f"{pad}}}")
            return lines

    raise ExportError(f"unknown geometry kind {kind!r}")


def component_to_openscad(component: Component, quantities: dict[str, Quantity]) -> str:
    """Render one component's geometry as an OpenSCAD module + a call.

    Raises ``ExportError`` if the component has no geometry (nothing to export)
    or contains an unrenderable node. The module name is derived from the
    component id so the output is stable and re-importable.
    """
    if component.geometry is None:
        raise ExportError(f"component {component.id!r} has no geometry to export")
    module = _module_name(component.id)
    body = _emit(component.geometry, quantities, depth=1)
    lines = [f"module {module}() {{", *body, "}", f"{module}();"]
    return "\n".join(lines)


def _footprint(node: GeometryNode | None,
               quantities: dict[str, Quantity]) -> tuple[float, float, float, float]:
    """(width_x, depth_y, center_x, center_y) of a component's outer envelope, from the SOUND
    analytic AABB (``verification.geometry.aabb_of``) — internal translate/rotate included, so
    the parts-tray placement can compensate the AABB center and guarantee disjoint envelopes
    (the old root-primitive walk ignored offsets and could overlap). Unknown or provably-empty
    geometry falls back to a safe default envelope centered at the origin."""
    if node is not None:
        try:
            bb = aabb_of(node, quantities)
        except GeometryError:
            bb = None
        if bb is not None and not bb.empty:
            return (bb.max_x - bb.min_x, bb.max_y - bb.min_y,
                    (bb.min_x + bb.max_x) / 2.0, (bb.min_y + bb.max_y) / 2.0)
    return (120.0, 120.0, 0.0, 0.0)


def specification_to_openscad(spec: Specification) -> str:
    """Render every fabricated component of a spec as OpenSCAD source — AS A LAID-OUT PARTS TRAY.

    Each fabricated component (one carrying geometry) becomes an OpenSCAD ``module`` DEFINITION, then
    a single assembly section calls every module inside a ``translate`` onto a non-overlapping grid, so
    opening the .scad shows EVERY printed part side by side (not all stacked at the origin) — each
    labelled with its name and how many to print. Purchased parts (no geometry) are listed as comments
    with their BOM count, so the script also reads as a complete parts inventory. Returns one
    deterministic OpenSCAD document tied back to the idea and the run.
    """
    quantities = {q.id: q for q in spec.quantities}
    counts = {b.component_id: b.count for b in spec.bom if b.component_id is not None}
    header = [
        "// GENESIS — Phase γ CSG export (OpenSCAD) — full parts tray",
        f"// idea: {_single_line(spec.idea)}",
        f"// run_id: {spec.run_id}",
        "// Every printed part is laid out on a grid so ALL parts are visible at once;",
        "// every dimension is annotated with its originating quantity id.",
        "",
    ]

    geom_comps = [c for c in spec.components if c.geometry is not None]
    modules: list[str] = []
    for comp in geom_comps:
        geom = comp.geometry
        assert geom is not None  # guaranteed by the geom_comps filter
        module = _module_name(comp.id)
        body = _emit(geom, quantities, depth=1)
        modules.append("\n".join([f"module {module}() {{", *body, "}"]))

    # purchased / abstract parts (no geometry) — surfaced as an inventory comment, never silently dropped
    purchased = [c for c in spec.components if c.geometry is None]
    for comp in purchased:
        modules.append(
            f"// component {comp.id!r} ({_single_line(comp.name)}) has no geometry — purchased/abstract"
        )

    if not geom_comps:
        return "\n".join(header) + "\n".join(modules or ["// no fabricated geometry in this specification"]) + "\n"

    # assembly layout: a square-ish grid. Pitch = the largest AABB extent + margin, and each
    # part is shifted by MINUS its own AABB center, so every placed envelope occupies
    # [grid ± extent/2] — pairwise disjoint by construction (internal offsets included).
    footprints = [_footprint(c.geometry, quantities) for c in geom_comps]
    pitch = max(max(w, d) for w, d, _, _ in footprints) + 60.0
    cols = max(1, int((len(geom_comps) - 1) ** 0.5) + 1)
    layout = ["", "// ---- PARTS TRAY: every printed part laid out so all are visible at once ----"]
    for i, comp in enumerate(geom_comps):
        _, _, cx, cy = footprints[i]
        x = _fmt((i % cols) * pitch - cx)
        y = _fmt(-(i // cols) * pitch - cy)
        n = counts.get(comp.id, 1)
        layout.append(
            f"translate([{x}, {y}, 0]) {_module_name(comp.id)}();  "
            f"// {_single_line(comp.name)} — {n}x drucken"
        )

    return "\n".join(header) + "\n\n".join(modules) + "\n" + "\n".join(layout) + "\n"


def _module_name(component_id: str) -> str:
    """A safe OpenSCAD identifier from a component id (alnum/underscore only)."""
    safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in component_id)
    if not safe or not (safe[0].isalpha() or safe[0] == "_"):
        safe = f"comp_{safe}"
    return safe
