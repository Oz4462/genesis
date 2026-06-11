"""Export a γ Specification's parametric CSG geometry to build123d Python code.

build123d is a parametric Python CAD library built on the Open Cascade (OCCT)
kernel (a GENESIS-internal VERIFIED claim); its *algebra mode* maps directly onto
GENESIS' GeometryNode tree, so it is the natural second CAD back-end next to
OpenSCAD (PHASE_GAMMA.md §3.3/§10).

build123d algebra-mode syntax (from the build123d documentation, key_concepts_algebra
and objects):
  Box(length, width, height)    Cylinder(radius, height)    Sphere(radius)
  union  A + B      difference  A - B      intersection  A & B
  translate         Pos(x, y, z) * obj

This exporter is deterministic and LLM-free: it resolves each parameter
quantity_id to its concrete value, emits the documented primitives, and lists the
contributing quantity ids as a per-component comment for traceability. A node it
cannot faithfully render (unknown kind, missing param, absent quantity) raises
``ExportError`` — never a guessed number.
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

# operator per boolean operation (build123d algebra mode)
_OP = {"union": " + ", "difference": " - ", "intersection": " & "}


def _value(node: GeometryNode, param: str, quantities: dict[str, Quantity],
           refs: dict[str, float]) -> str:
    qid = node.params.get(param)
    if qid is None:
        raise ExportError(f"geometry {node.kind!r} is missing parameter {param!r}")
    quantity = quantities.get(qid)
    if quantity is None:
        raise ExportError(
            f"geometry {node.kind!r} param {param!r} references unknown quantity {qid!r}"
        )
    refs[qid] = float(quantity.value)
    return _fmt(quantity.value)


def _expr(node: GeometryNode, quantities: dict[str, Quantity], refs: dict[str, float]) -> str:
    kind = node.kind

    if kind in GEOMETRY_PRIMITIVES:
        if kind == "box":
            sx = _value(node, "size_x", quantities, refs)
            sy = _value(node, "size_y", quantities, refs)
            sz = _value(node, "size_z", quantities, refs)
            return f"Box({sx}, {sy}, {sz})"
        if kind == "cylinder":
            r = _value(node, "radius", quantities, refs)
            h = _value(node, "height", quantities, refs)
            return f"Cylinder({r}, {h})"
        if kind == "sphere":
            r = _value(node, "radius", quantities, refs)
            return f"Sphere({r})"

    if kind in GEOMETRY_OPERATIONS:
        parts = [_child_expr(child, quantities, refs) for child in node.children]
        return "(" + _OP[kind].join(parts) + ")"

    if kind in GEOMETRY_TRANSFORMS:
        if kind == "translate":
            x = _value(node, "x", quantities, refs)
            y = _value(node, "y", quantities, refs)
            z = _value(node, "z", quantities, refs)
            child = _child_expr(node.children[0], quantities, refs) if node.children else "None"
            return f"Pos({x}, {y}, {z}) * {child}"

    raise ExportError(f"unknown geometry kind {kind!r}")


def _child_expr(node: GeometryNode, quantities: dict[str, Quantity], refs: dict[str, float]) -> str:
    """A child expression, parenthesized when compound so operator structure is
    preserved (a primitive needs no extra parentheses)."""
    expr = _expr(node, quantities, refs)
    if node.kind in GEOMETRY_PRIMITIVES:
        return expr
    return expr if expr.startswith("(") else f"({expr})"


def component_to_build123d(component: Component, quantities: dict[str, Quantity]) -> str:
    """Render one component's geometry as a build123d algebra-mode assignment.

    Raises ``ExportError`` if the component has no geometry or contains an
    unrenderable node. The variable name is derived from the component id.
    """
    if component.geometry is None:
        raise ExportError(f"component {component.id!r} has no geometry to export")
    refs: dict[str, float] = {}
    expr = _expr(component.geometry, quantities, refs)
    var = _safe_name(component.id)
    dims = ", ".join(f"{qid}={_fmt(val)}" for qid, val in refs.items())
    return f"# {var}  dims: {dims}\n{var} = {expr}"


def specification_to_build123d(spec: Specification) -> str:
    """Render every fabricated component of a spec as build123d Python source."""
    quantities = {q.id: q for q in spec.quantities}
    header = [
        "# GENESIS — Phase γ CSG export (build123d, algebra mode)",
        f"# idea: {spec.idea}",
        f"# run_id: {spec.run_id}",
        "# Each component lists its contributing quantity ids for traceability.",
        "from build123d import *",
        "",
    ]
    blocks: list[str] = []
    for comp in spec.components:
        if comp.geometry is None:
            blocks.append(f"# component {comp.id!r} ({comp.name}) has no geometry — skipped")
            continue
        blocks.append(component_to_build123d(comp, quantities))
    if not blocks:
        blocks.append("# no fabricated geometry in this specification")
    return "\n".join(header) + "\n\n".join(blocks) + "\n"


def _safe_name(component_id: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in component_id)
    if not safe or not (safe[0].isalpha() or safe[0] == "_"):
        safe = f"comp_{safe}"
    return safe
