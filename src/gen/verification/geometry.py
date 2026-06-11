"""Axis-aligned bounding boxes for Phase δ — deterministic geometric validation.

The δ guarantee leans on one exact, sound primitive: the axis-aligned bounding
box (AABB). An AABB is a *conservative* bound, which gives δ its honesty (see
PHASE_DELTA.md §0): if two AABBs are disjoint, the solids they bound *provably*
do not overlap, so a difference whose tool misses the body, or an intersection of
non-touching parts, can be flagged with NO false positives. If AABBs overlap, the
solids only *might* overlap — δ then claims nothing.

Conventions (PHASE_DELTA.md §1, consistent with build123d's centered primitives):
  box(size_x,size_y,size_z): centered at origin -> ±size/2 per axis
  cylinder(radius,height):   axis along Z      -> [±r, ±r, ±h/2]
  sphere(radius):            centered          -> ±r per axis
  translate(x,y,z) child:    child's AABB shifted by (x,y,z)
  union:        envelope (min of mins, max of maxs) of children
  difference(A,…): subtracting can only shrink -> sound bound = AABB(A)
  intersection: overlap region (max of mins, min of maxs); inverted -> EMPTY

AABB math sources: standard minimum-bounding-box algebra (union envelope, overlap
region, the per-axis overlap test). See PHASE_DELTA.md §8.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.errors import GeometryError
from ..core.state import (
    GEOMETRY_OPERATIONS,
    GEOMETRY_PRIMITIVES,
    GEOMETRY_TRANSFORMS,
    GeometryNode,
    Quantity,
)


@dataclass(frozen=True)
class Aabb:
    """An axis-aligned bounding box. ``empty`` marks a provably-empty region (an
    intersection whose operands do not overlap), distinct from a zero-extent
    degenerate box (which is non-empty but has no volume)."""

    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float
    empty: bool = False

    @property
    def extent(self) -> tuple[float, float, float]:
        return (self.max_x - self.min_x, self.max_y - self.min_y, self.max_z - self.min_z)

    def is_degenerate(self) -> bool:
        """True if any axis has non-positive extent (no volume)."""
        return any(e <= 0.0 for e in self.extent)


_EMPTY = Aabb(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, empty=True)


def overlaps(a: Aabb, b: Aabb) -> bool:
    """True iff the two boxes overlap on EVERY axis (the AABB overlap test).

    Empty boxes overlap nothing. Touching faces (shared boundary) count as
    overlap (closed intervals) — a tool flush against a face still removes a
    boundary, so it is not a *provably* dead operation.
    """
    if a.empty or b.empty:
        return False
    return (
        a.min_x <= b.max_x and b.min_x <= a.max_x
        and a.min_y <= b.max_y and b.min_y <= a.max_y
        and a.min_z <= b.max_z and b.min_z <= a.max_z
    )


def _value(node: GeometryNode, param: str, quantities: dict[str, Quantity]) -> float:
    qid = node.params.get(param)
    if qid is None:
        raise GeometryError(f"geometry {node.kind!r} is missing parameter {param!r}")
    quantity = quantities.get(qid)
    if quantity is None:
        raise GeometryError(
            f"geometry {node.kind!r} param {param!r} references unknown quantity {qid!r}"
        )
    return float(quantity.value)


def aabb_of(node: GeometryNode, quantities: dict[str, Quantity]) -> Aabb:
    """The axis-aligned bounding box of a CSG node (sound bound).

    Raises ``GeometryError`` for an unknown kind / missing param / absent
    quantity — never a guessed extent.
    """
    kind = node.kind

    if kind in GEOMETRY_PRIMITIVES:
        if kind == "box":
            hx = _value(node, "size_x", quantities) / 2.0
            hy = _value(node, "size_y", quantities) / 2.0
            hz = _value(node, "size_z", quantities) / 2.0
            return Aabb(-hx, -hy, -hz, hx, hy, hz)
        if kind == "cylinder":
            r = _value(node, "radius", quantities)
            hh = _value(node, "height", quantities) / 2.0
            return Aabb(-r, -r, -hh, r, r, hh)
        if kind == "sphere":
            r = _value(node, "radius", quantities)
            return Aabb(-r, -r, -r, r, r, r)

    if kind in GEOMETRY_TRANSFORMS:
        if kind == "translate":
            if not node.children:
                raise GeometryError("translate has no child")
            dx = _value(node, "x", quantities)
            dy = _value(node, "y", quantities)
            dz = _value(node, "z", quantities)
            c = aabb_of(node.children[0], quantities)
            if c.empty:
                return _EMPTY
            return Aabb(
                c.min_x + dx, c.min_y + dy, c.min_z + dz,
                c.max_x + dx, c.max_y + dy, c.max_z + dz,
            )

    if kind in GEOMETRY_OPERATIONS:
        if not node.children:
            raise GeometryError(f"{kind} has no children")
        child_boxes = [aabb_of(c, quantities) for c in node.children]
        if kind == "union":
            return _union(child_boxes)
        if kind == "difference":
            # subtracting can only shrink -> the sound bound is the minuend's box
            return child_boxes[0]
        if kind == "intersection":
            return _intersection(child_boxes)

    raise GeometryError(f"unknown geometry kind {kind!r}")


def _union(boxes: list[Aabb]) -> Aabb:
    present = [b for b in boxes if not b.empty]
    if not present:
        return _EMPTY
    return Aabb(
        min(b.min_x for b in present), min(b.min_y for b in present), min(b.min_z for b in present),
        max(b.max_x for b in present), max(b.max_y for b in present), max(b.max_z for b in present),
    )


def _intersection(boxes: list[Aabb]) -> Aabb:
    if any(b.empty for b in boxes):
        return _EMPTY
    min_x = max(b.min_x for b in boxes)
    min_y = max(b.min_y for b in boxes)
    min_z = max(b.min_z for b in boxes)
    max_x = min(b.max_x for b in boxes)
    max_y = min(b.max_y for b in boxes)
    max_z = min(b.max_z for b in boxes)
    # inverted on any axis -> the operands do not all overlap -> provably empty
    if min_x > max_x or min_y > max_y or min_z > max_z:
        return _EMPTY
    return Aabb(min_x, min_y, min_z, max_x, max_y, max_z)
