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

from ..core.errors import ExportError
from ..core.state import (
    GEOMETRY_OPERATIONS,
    GEOMETRY_PRIMITIVES,
    GEOMETRY_TRANSFORMS,
    Component,
    GeometryNode,
    Quantity,
    Specification,
)
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
            return [f"{pad}cube([{sx}, {sy}, {sz}]); // size_x={qx}, size_y={qy}, size_z={qz}"]
        if kind == "cylinder":
            r, qr = _resolve(node, "radius", quantities)
            h, qh = _resolve(node, "height", quantities)
            return [f"{pad}cylinder(h={h}, r={r}); // height={qh}, radius={qr}"]
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


def specification_to_openscad(spec: Specification) -> str:
    """Render every fabricated component of a spec as OpenSCAD source.

    A fabricated component is one carrying geometry. Components without geometry
    (purchased/abstract parts) are skipped with a comment. Returns a single
    OpenSCAD document with a header tying it back to the idea and the run.
    """
    quantities = {q.id: q for q in spec.quantities}
    header = [
        "// GENESIS — Phase γ CSG export (OpenSCAD)",
        f"// idea: {spec.idea}",
        f"// run_id: {spec.run_id}",
        "// Every dimension is annotated with its originating quantity id.",
        "",
    ]
    blocks: list[str] = []
    for comp in spec.components:
        if comp.geometry is None:
            blocks.append(f"// component {comp.id!r} ({comp.name}) has no geometry — skipped")
            continue
        blocks.append(component_to_openscad(comp, quantities))
    if not blocks:
        blocks.append("// no fabricated geometry in this specification")
    return "\n".join(header) + "\n\n".join(blocks) + "\n"


def _module_name(component_id: str) -> str:
    """A safe OpenSCAD identifier from a component id (alnum/underscore only)."""
    safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in component_id)
    if not safe or not (safe[0].isalpha() or safe[0] == "_"):
        safe = f"comp_{safe}"
    return safe
