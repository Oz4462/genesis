"""Exact BREP geometry via the OpenCASCADE kernel (the δ-1 geometry upgrade).

The δ-1 layer (verification/geometry.py) reasons over axis-aligned bounding boxes:
sound but CONSERVATIVE — it proves non-overlap (disjoint AABBs) and computes exact
volume only for simple cases, never a false positive but often "no claim". This
module upgrades that to EXACT geometry by translating the GENESIS CSG tree into
real OpenCASCADE B-Rep solids (via cadquery / OCP) and asking the kernel directly:
exact volume, solid validity, and exact interference (the volume of the actual
intersection, not of the bounding boxes).

cadquery/OCP is an OPTIONAL dependency: the module imports it lazily and raises a
clear error if it is absent, so the core GENESIS install (and CI) needs no CAD
kernel. The test skips when cadquery is not installed; where it IS installed the
results are cross-checked against the analytic `geometry.volume_of` (two
independent methods agreeing) and against the conservative AABB (exact ≤ bound).

Geometry convention matches the rest of GENESIS: primitives are CENTERED at the
origin (see PHASE_DELTA.md §1 / export/openscad.py / export/build123d.py).

Honest boundary: this is exact for the modelled CSG of rigid solids. It still makes
no physical judgement (strength, manufacturability) — that is the job of the
statics / DFM / FEM layers. A passed geometry check stays necessary, not sufficient.
"""

from __future__ import annotations

from .core.errors import GeometryError
from .core.state import (
    GEOMETRY_OPERATIONS,
    GEOMETRY_PRIMITIVES,
    GEOMETRY_TRANSFORMS,
    GeometryNode,
    Quantity,
)


def _require_cadquery():
    try:
        from cadquery import Solid, Vector  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised only without cadquery
        raise GeometryError(
            "exact BREP needs the optional 'cadquery' package (OpenCASCADE kernel); "
            "install it with `pip install cadquery`, or use the AABB layer "
            "(verification/geometry.py), which needs no CAD kernel."
        ) from exc
    return Solid, Vector


def _val(qid: str, quantities: dict[str, Quantity]) -> float:
    q = quantities.get(qid)
    if q is None:
        raise GeometryError(f"geometry references unknown quantity {qid!r}")
    return float(q.value)


def csg_to_solid(node: GeometryNode, quantities: dict[str, Quantity]):
    """Translate a GENESIS CSG tree into an OpenCASCADE solid (centered primitives).
    Raises GeometryError on an unknown kind or a missing parameter quantity."""
    Solid, Vector = _require_cadquery()

    if node.kind in GEOMETRY_PRIMITIVES:
        if node.kind == "box":
            sx = _val(node.params["size_x"], quantities)
            sy = _val(node.params["size_y"], quantities)
            sz = _val(node.params["size_z"], quantities)
            return Solid.makeBox(sx, sy, sz, Vector(-sx / 2, -sy / 2, -sz / 2))
        if node.kind == "cylinder":
            r = _val(node.params["radius"], quantities)
            h = _val(node.params["height"], quantities)
            return Solid.makeCylinder(r, h, Vector(0, 0, -h / 2), Vector(0, 0, 1))
        if node.kind == "sphere":
            r = _val(node.params["radius"], quantities)
            # full sphere centered at the origin: makeSphere's defaults make only a
            # hemisphere (latitude 0..90), so the angles must be given explicitly.
            return Solid.makeSphere(r, Vector(0, 0, 0), Vector(0, 0, 1), -90, 90, 360)

    if node.kind in GEOMETRY_TRANSFORMS:  # translate
        child = csg_to_solid(node.children[0], quantities)
        x = _val(node.params["x"], quantities)
        y = _val(node.params["y"], quantities)
        z = _val(node.params["z"], quantities)
        return child.translate(Vector(x, y, z))

    if node.kind in GEOMETRY_OPERATIONS:
        solids = [csg_to_solid(c, quantities) for c in node.children]
        if not solids:
            raise GeometryError(f"{node.kind!r} operation has no children")
        result = solids[0]
        for other in solids[1:]:
            if node.kind == "union":
                result = result.fuse(other)
            elif node.kind == "difference":
                result = result.cut(other)
            else:  # intersection
                result = result.intersect(other)
        return result

    raise GeometryError(f"unknown geometry kind {node.kind!r}")


def exact_volume(node: GeometryNode, quantities: dict[str, Quantity]) -> float:
    """Exact solid volume from the OCCT kernel (vs the analytic bound of
    geometry.volume_of). Same length unit cubed as the quantities."""
    return float(csg_to_solid(node, quantities).Volume())


def is_valid(node: GeometryNode, quantities: dict[str, Quantity]) -> bool:
    """True if the kernel reports a topologically valid solid (BRepCheck)."""
    return bool(csg_to_solid(node, quantities).isValid())


def interferes(
    node_a: GeometryNode,
    node_b: GeometryNode,
    quantities: dict[str, Quantity],
    *,
    tolerance: float = 1e-9,
) -> bool:
    """Exact interference: True iff the two solids actually overlap (intersection
    volume > tolerance). Unlike the AABB test this is EXACT — two parts whose
    bounding boxes overlap but whose solids do not are correctly reported as
    non-interfering."""
    solid_a = csg_to_solid(node_a, quantities)
    solid_b = csg_to_solid(node_b, quantities)
    inter = solid_a.intersect(solid_b)
    try:
        vol = float(inter.Volume())
    except Exception:  # noqa: BLE001 - an empty intersection can be a null shape
        return False
    return vol > tolerance
