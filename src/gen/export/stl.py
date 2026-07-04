"""Export γ CSG primitives to an ASCII STL triangle mesh — honest about booleans.

STL is the universal 3D-print mesh format (a flat list of outward-facing
triangles). This exporter tessellates the *meshable* part of a GeometryNode tree:
a box exactly (12 triangles), a cylinder and a sphere by deterministic
tessellation (a faceted APPROXIMATION of the curved surface — stated honestly),
and translate by shifting vertices.

It deliberately does NOT evaluate CSG booleans (difference / union /
intersection). A correct boolean mesh needs a real mesh-boolean kernel; emitting
the operands of a difference as if they were the result would be a geometric
hallucination (a box with a cylinder beside it, not a box with a hole). So a
boolean node raises ``ExportError`` pointing to the OpenSCAD / build123d
exporters, which evaluate CSG on a real kernel (CGAL / OCCT).

ASCII STL grammar (from the STL format spec): ``solid <name>`` / per triangle
``facet normal ni nj nk`` + ``outer loop`` + three ``vertex x y z`` + ``endloop``
+ ``endfacet`` / ``endsolid <name>``. Vertices are counter-clockwise from
outside; the normal points outward (right-hand rule).
"""

from __future__ import annotations

import math

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

Vec = tuple[float, float, float]
Tri = tuple[Vec, Vec, Vec]

DEFAULT_SEGMENTS = 32   # longitude divisions for cylinder/sphere
DEFAULT_RINGS = 16      # latitude divisions for sphere


class CsgBooleanRefusal(ExportError):
    """The DELIBERATE refusal to mesh a CSG boolean without a real kernel.

    Distinct from a malformed spec (unknown kind / missing param / absent
    quantity), which stays a plain ``ExportError``: a caller may treat THIS
    class as an expected, reportable skip, while a plain ExportError must
    always propagate loudly — conflating the two hid real defects (Schritt-8
    Review F6).
    """


def _f(v: float) -> str:
    return f"{v:.9g}"


def _value(node: GeometryNode, param: str, quantities: dict[str, Quantity]) -> float:
    qid = node.params.get(param)
    if qid is None:
        raise ExportError(f"geometry {node.kind!r} is missing parameter {param!r}")
    q = quantities.get(qid)
    if q is None:
        raise ExportError(
            f"geometry {node.kind!r} param {param!r} references unknown quantity {qid!r}"
        )
    return float(q.value)


def _sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _normal(t: Tri) -> Vec:
    n = _cross(_sub(t[1], t[0]), _sub(t[2], t[0]))
    mag = math.sqrt(_dot(n, n))
    if mag == 0.0:
        return (0.0, 0.0, 0.0)
    return (n[0] / mag, n[1] / mag, n[2] / mag)


def _oriented(v1: Vec, v2: Vec, v3: Vec) -> Tri:
    """Order vertices so the right-hand-rule normal points OUTWARD for a centered
    convex primitive — the outward direction is the triangle centroid's direction
    from the origin (valid because primitives are centered at the origin)."""
    centroid = ((v1[0] + v2[0] + v3[0]) / 3, (v1[1] + v2[1] + v3[1]) / 3, (v1[2] + v2[2] + v3[2]) / 3)
    n = _normal((v1, v2, v3))
    if _dot(n, centroid) < 0:
        return (v1, v3, v2)
    return (v1, v2, v3)


def _mesh_box(node: GeometryNode, quantities: dict[str, Quantity]) -> list[Tri]:
    hx = _value(node, "size_x", quantities) / 2.0
    hy = _value(node, "size_y", quantities) / 2.0
    hz = _value(node, "size_z", quantities) / 2.0
    # 8 corners
    c = [(sx * hx, sy * hy, sz * hz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    # index: bit2=x, bit1=y, bit0=z -> c[(x<<2)|(y<<1)|z] with x,y,z in {0,1}
    def idx(x, y, z):
        return c[(x << 2) | (y << 1) | z]

    quads = [
        (idx(1, 0, 0), idx(1, 1, 0), idx(1, 1, 1), idx(1, 0, 1)),  # +X
        (idx(0, 0, 0), idx(0, 1, 0), idx(0, 1, 1), idx(0, 0, 1)),  # -X
        (idx(0, 1, 0), idx(1, 1, 0), idx(1, 1, 1), idx(0, 1, 1)),  # +Y
        (idx(0, 0, 0), idx(1, 0, 0), idx(1, 0, 1), idx(0, 0, 1)),  # -Y
        (idx(0, 0, 1), idx(1, 0, 1), idx(1, 1, 1), idx(0, 1, 1)),  # +Z
        (idx(0, 0, 0), idx(1, 0, 0), idx(1, 1, 0), idx(0, 1, 0)),  # -Z
    ]
    tris: list[Tri] = []
    for a, b, d, e in quads:
        tris.append(_oriented(a, b, d))
        tris.append(_oriented(a, d, e))
    return tris


def _mesh_cylinder(node: GeometryNode, quantities: dict[str, Quantity], segments: int) -> list[Tri]:
    r = _value(node, "radius", quantities)
    hz = _value(node, "height", quantities) / 2.0
    ring = [(r * math.cos(2 * math.pi * i / segments), r * math.sin(2 * math.pi * i / segments))
            for i in range(segments)]
    tris: list[Tri] = []
    top_c = (0.0, 0.0, hz)
    bot_c = (0.0, 0.0, -hz)
    for i in range(segments):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % segments]
        tb0, tb1 = (x0, y0, hz), (x1, y1, hz)
        bb0, bb1 = (x0, y0, -hz), (x1, y1, -hz)
        tris.append(_oriented(bb0, bb1, tb1))   # side quad -> 2 tris
        tris.append(_oriented(bb0, tb1, tb0))
        tris.append(_oriented(top_c, tb0, tb1))  # top cap fan
        tris.append(_oriented(bot_c, bb0, bb1))  # bottom cap fan
    return tris


def _mesh_sphere(node: GeometryNode, quantities: dict[str, Quantity], segments: int, rings: int) -> list[Tri]:
    r = _value(node, "radius", quantities)

    def point(theta: float, phi: float) -> Vec:
        return (r * math.sin(theta) * math.cos(phi),
                r * math.sin(theta) * math.sin(phi),
                r * math.cos(theta))

    tris: list[Tri] = []
    for i in range(rings):
        t0 = math.pi * i / rings
        t1 = math.pi * (i + 1) / rings
        for j in range(segments):
            p0 = 2 * math.pi * j / segments
            p1 = 2 * math.pi * (j + 1) / segments
            a, b, cc, d = point(t0, p0), point(t1, p0), point(t1, p1), point(t0, p1)
            if i != 0:
                tris.append(_oriented(a, b, cc))
            if i != rings - 1:
                tris.append(_oriented(a, cc, d))
    return tris


def _mesh(node: GeometryNode, quantities: dict[str, Quantity], segments: int, rings: int) -> list[Tri]:
    kind = node.kind
    if kind in GEOMETRY_PRIMITIVES:
        if kind == "box":
            return _mesh_box(node, quantities)
        if kind == "cylinder":
            return _mesh_cylinder(node, quantities, segments)
        if kind == "sphere":
            return _mesh_sphere(node, quantities, segments, rings)
    if kind in GEOMETRY_TRANSFORMS and kind == "translate":
        if not node.children:
            raise ExportError("translate has no child")
        dx = _value(node, "x", quantities)
        dy = _value(node, "y", quantities)
        dz = _value(node, "z", quantities)
        child = _mesh(node.children[0], quantities, segments, rings)
        return [tuple((v[0] + dx, v[1] + dy, v[2] + dz) for v in tri) for tri in child]  # type: ignore[misc]
    if kind in GEOMETRY_TRANSFORMS and kind == "rotate":
        if not node.children:
            raise ExportError("rotate has no child")
        from ..verification.geometry import rotate_point  # single Rodrigues source

        axis = (_value(node, "axis_x", quantities),
                _value(node, "axis_y", quantities),
                _value(node, "axis_z", quantities))
        angle = _value(node, "angle_deg", quantities)
        child = _mesh(node.children[0], quantities, segments, rings)
        # rigid rotation of every vertex; winding is preserved, so the facet
        # normals (recomputed from the triangle) stay outward.
        return [tuple(rotate_point(v, axis, angle) for v in tri) for tri in child]  # type: ignore[misc]
    if kind in GEOMETRY_OPERATIONS:
        raise CsgBooleanRefusal(
            f"STL export does not evaluate the CSG boolean {kind!r} — a correct "
            "boolean mesh needs a mesh-boolean kernel. Use --format scad or b123d, "
            "which evaluate CSG on a real kernel (CGAL / OCCT)."
        )
    raise ExportError(f"unknown geometry kind {kind!r}")


def _triangles_to_stl(name: str, tris: list[Tri]) -> str:
    """ASCII STL text for a triangle list. Zero-area (degenerate) facets are DROPPED
    — cross-product magnitude < 1e-15, the same filter as ``brep_stl._facet`` — a
    slicer must never see them. Raises ``ExportError`` if nothing remains: a mesh
    of only degenerate facets is broken geometry, not an exportable solid."""
    lines = [f"solid {name}"]
    n_emitted = 0
    for tri in tris:
        n = _cross(_sub(tri[1], tri[0]), _sub(tri[2], tri[0]))
        mag = math.sqrt(_dot(n, n))
        if mag < 1e-15:
            continue    # degenerate sliver — same threshold as brep_stl
        nx, ny, nz = n[0] / mag, n[1] / mag, n[2] / mag
        lines.append(f"  facet normal {_f(nx)} {_f(ny)} {_f(nz)}")
        lines.append("    outer loop")
        for v in tri:
            lines.append(f"      vertex {_f(v[0])} {_f(v[1])} {_f(v[2])}")
        lines.append("    endloop")
        lines.append("  endfacet")
        n_emitted += 1
    if n_emitted == 0:
        raise ExportError(
            f"mesh for {name!r} contains only zero-area facets (degenerate geometry)"
        )
    lines.append(f"endsolid {name}")
    return "\n".join(lines)


def component_to_stl(component: Component, quantities: dict[str, Quantity],
                     *, segments: int = DEFAULT_SEGMENTS, rings: int = DEFAULT_RINGS) -> str:
    """ASCII STL for one component's geometry. Raises ``ExportError`` for a CSG
    boolean (not mesh-evaluated) or an unrenderable node — never a wrong mesh."""
    if component.geometry is None:
        raise ExportError(f"component {component.id!r} has no geometry to export")
    tris = _mesh(component.geometry, quantities, segments, rings)
    return _triangles_to_stl(_safe_name(component.id), tris)


def specification_to_stl_report(spec: Specification, *, segments: int = DEFAULT_SEGMENTS,
                                rings: int = DEFAULT_RINGS) -> tuple[str, dict[str, str]]:
    """ASCII STL for every mesh-exportable component PLUS an honest skip report.

    Returns ``(stl_text, skipped)``: ``skipped`` maps component id → reason for
    every component whose geometry contains a CSG boolean (``CsgBooleanRefusal``
    — the expected, kernel-less refusal). Any OTHER ``ExportError`` (unknown
    kind, missing param, absent quantity, all-degenerate mesh) is a MALFORMED
    spec and propagates — it must never be conflated with the boolean skip.
    Raises ``ExportError`` if no component is meshable at all.
    """
    quantities = {q.id: q for q in spec.quantities}
    blocks: list[str] = []
    skipped: dict[str, str] = {}
    for comp in spec.components:
        if comp.geometry is None:
            continue
        try:
            blocks.append(component_to_stl(comp, quantities, segments=segments, rings=rings))
        except CsgBooleanRefusal as exc:
            skipped[comp.id] = str(exc)
    if not blocks:
        raise ExportError(
            "no mesh-exportable geometry: "
            + (f"components {sorted(skipped)} contain CSG booleans — " if skipped else "")
            + "use --format scad or b123d, which evaluate CSG on a real kernel."
        )
    return "\n".join(blocks) + "\n", skipped


def specification_to_stl(spec: Specification, *, segments: int = DEFAULT_SEGMENTS,
                         rings: int = DEFAULT_RINGS) -> str:
    """ASCII STL for every mesh-exportable component of a spec (text only).

    Thin wrapper over ``specification_to_stl_report`` that DISCARDS the skip
    report — a caller that must not silently lose CSG-boolean parts (the CLI)
    uses the report variant and acts on ``skipped``. Error behaviour is the
    report's: real export errors propagate, only boolean refusals are skipped.
    """
    stl, _skipped = specification_to_stl_report(spec, segments=segments, rings=rings)
    return stl


def _safe_name(component_id: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in component_id)
    if not safe or not (safe[0].isalpha() or safe[0] == "_"):
        safe = f"comp_{safe}"
    return safe
