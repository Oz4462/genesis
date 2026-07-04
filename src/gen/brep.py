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

import math

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


def _param(node: GeometryNode, key: str) -> str:
    """The quantity id behind a node parameter — GeometryError (the documented
    error contract), never a raw KeyError, when the key is absent."""
    try:
        return node.params[key]
    except KeyError as exc:
        raise GeometryError(
            f"{node.kind!r} node is missing required parameter {key!r}"
        ) from exc


def _positive(value: float, what: str, kind: str) -> float:
    """A primitive dimension must be a positive finite number — `not (v > 0)` also
    catches NaN. GATE γ C-9 checks this on the pipeline path; direct callers of
    this module get the same GeometryError instead of a raw OCCT failure."""
    if not (value > 0.0) or math.isinf(value):
        raise GeometryError(
            f"{kind} {what} must be positive and finite, got {value!r}"
        )
    return value


def csg_to_solid(node: GeometryNode, quantities: dict[str, Quantity]):
    """Translate a GENESIS CSG tree into an OpenCASCADE solid (centered primitives).
    Raises GeometryError on an unknown kind, a missing parameter key or quantity,
    a non-positive/non-finite primitive dimension, a transform without a child,
    or a zero/non-finite rotation axis — never a raw KeyError/IndexError/OCCT
    failure."""
    Solid, Vector = _require_cadquery()

    if node.kind in GEOMETRY_PRIMITIVES:
        if node.kind == "box":
            sx = _positive(_val(_param(node, "size_x"), quantities), "size_x", "box")
            sy = _positive(_val(_param(node, "size_y"), quantities), "size_y", "box")
            sz = _positive(_val(_param(node, "size_z"), quantities), "size_z", "box")
            return Solid.makeBox(sx, sy, sz, Vector(-sx / 2, -sy / 2, -sz / 2))
        if node.kind == "cylinder":
            r = _positive(_val(_param(node, "radius"), quantities), "radius", "cylinder")
            h = _positive(_val(_param(node, "height"), quantities), "height", "cylinder")
            return Solid.makeCylinder(r, h, Vector(0, 0, -h / 2), Vector(0, 0, 1))
        if node.kind == "sphere":
            r = _positive(_val(_param(node, "radius"), quantities), "radius", "sphere")
            # full sphere centered at the origin: makeSphere's defaults make only a
            # hemisphere (latitude 0..90), so the angles must be given explicitly.
            return Solid.makeSphere(r, Vector(0, 0, 0), Vector(0, 0, 1), -90, 90, 360)

    if node.kind in GEOMETRY_TRANSFORMS:
        if not node.children:
            raise GeometryError(f"{node.kind!r} transform has no child")
        child = csg_to_solid(node.children[0], quantities)
        if node.kind == "translate":
            x = _val(_param(node, "x"), quantities)
            y = _val(_param(node, "y"), quantities)
            z = _val(_param(node, "z"), quantities)
            return child.translate(Vector(x, y, z))
        if node.kind == "rotate":
            ax = _val(_param(node, "axis_x"), quantities)
            ay = _val(_param(node, "axis_y"), quantities)
            az = _val(_param(node, "axis_z"), quantities)
            if not all(math.isfinite(v) for v in (ax, ay, az)):
                raise GeometryError(
                    f"rotate axis components must be finite, got ({ax!r}, {ay!r}, {az!r})"
                )
            if (ax * ax + ay * ay + az * az) ** 0.5 < 1e-12:
                raise GeometryError("rotate axis must be non-zero")
            angle = _val(_param(node, "angle_deg"), quantities)
            # cadquery Shape.rotate(axisStart, axisEnd, angleDegrees) — axis
            # through the origin, the shared geometry convention.
            return child.rotate(Vector(0, 0, 0), Vector(ax, ay, az), angle)

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
    non-interfering.

    Error contract (the SAFE direction): only a provably empty intersection — a
    null result shape — is "no overlap". An unexpected kernel failure (boolean
    op or volume measurement) raises GeometryError; it is NEVER swallowed into
    False, because "collision check crashed" must not read as "no collision"."""
    solid_a = csg_to_solid(node_a, quantities)
    solid_b = csg_to_solid(node_b, quantities)
    try:
        inter = solid_a.intersect(solid_b)
    except Exception as exc:  # noqa: BLE001 - raw OCCT error, translated
        raise GeometryError(f"OCCT boolean intersection failed: {exc}") from exc
    wrapped = getattr(inter, "wrapped", None)
    if inter is None or wrapped is None or (hasattr(wrapped, "IsNull") and wrapped.IsNull()):
        return False  # empty intersection IS the proof of no overlap
    try:
        vol = float(inter.Volume())
    except Exception as exc:  # noqa: BLE001 - raw OCCT error, translated
        raise GeometryError(
            f"OCCT could not measure the intersection volume: {exc}"
        ) from exc
    return vol > tolerance
