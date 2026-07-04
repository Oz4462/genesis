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
  rotate(axis,angle) child:  the 8 corners of the child's AABB rotated
                (Rodrigues), then re-boxed — CONSERVATIVE (bounds the rotated
                child because the child lies inside its AABB and rotation is
                rigid); exact for 90°-multiples of axis-aligned children
  union:        envelope (min of mins, max of maxs) of children
  difference(A,…): subtracting can only shrink -> sound bound = AABB(A)
  intersection: overlap region (max of mins, min of maxs); inverted -> EMPTY

AABB math sources: standard minimum-bounding-box algebra (union envelope, overlap
region, the per-axis overlap test). See PHASE_DELTA.md §8.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from ..core.errors import GeometryError
from ..core.state import (
    GEOMETRY_OPERATIONS,
    GEOMETRY_PRIMITIVES,
    GEOMETRY_TRANSFORMS,
    Component,
    GeometryNode,
    Quantity,
)
from .units import Dimension, parse_unit, unit_scale


@dataclass(frozen=True)
class Aabb:
    """An axis-aligned bounding box. ``empty`` marks a provably-empty region (an
    intersection whose operands do not overlap), distinct from a zero-extent
    degenerate box (which is non-empty but has no volume).

    ``exact`` is True only when the box is provably TIGHT (it equals the solid's
    true bounding box); False marks a sound conservative SUPERSET — e.g. after a
    non-quarter-turn rotation, a difference (the tool may shave the extremes), or
    an intersection (the solids need not reach the overlap-box corners). A
    consumer must treat a non-exact box's extents as bounds, never as the solid's
    measured extents (comparing them with isclose produces false negatives)."""

    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float
    empty: bool = False
    exact: bool = True

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


def rotate_point(
    p: tuple[float, float, float],
    axis: tuple[float, float, float],
    angle_deg: float,
) -> tuple[float, float, float]:
    """Rotate a point about an axis through the origin (Rodrigues' formula).

    ``v' = v·cosθ + (k×v)·sinθ + k·(k·v)·(1−cosθ)`` with k the normalized axis
    — the standard closed form for rotation about an arbitrary axis. Angle in
    DEGREES (the shared geometry convention). Raises GeometryError on a
    zero-length axis: a rotation without a direction is undefined, never
    guessed. Shared by the AABB layer and the primitive STL mesher so both
    rotate identically."""
    ax, ay, az = axis
    n = math.sqrt(ax * ax + ay * ay + az * az)
    if n < 1e-12:
        raise GeometryError("rotate axis must be non-zero")
    kx, ky, kz = ax / n, ay / n, az / n
    th = math.radians(angle_deg)
    c, s = math.cos(th), math.sin(th)
    x, y, z = p
    dot = kx * x + ky * y + kz * z
    cx, cy, cz = ky * z - kz * y, kz * x - kx * z, kx * y - ky * x
    return (
        x * c + cx * s + kx * dot * (1.0 - c),
        y * c + cy * s + ky * dot * (1.0 - c),
        z * c + cz * s + kz * dot * (1.0 - c),
    )


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
                exact=c.exact,   # a pure shift preserves tightness
            )
        if kind == "rotate":
            if not node.children:
                raise GeometryError("rotate has no child")
            axis = (
                _value(node, "axis_x", quantities),
                _value(node, "axis_y", quantities),
                _value(node, "axis_z", quantities),
            )
            angle = _value(node, "angle_deg", quantities)
            c = aabb_of(node.children[0], quantities)
            if c.empty:
                return _EMPTY
            # rotate the 8 corners of the child's AABB and re-box: conservative
            # (the child lies inside its AABB; a rigid rotation keeps it inside
            # the rotated box, which lies inside the new AABB) — never too small.
            corners = [
                rotate_point((x, y, z), axis, angle)
                for x in (c.min_x, c.max_x)
                for y in (c.min_y, c.max_y)
                for z in (c.min_z, c.max_z)
            ]
            return Aabb(
                min(p[0] for p in corners), min(p[1] for p in corners),
                min(p[2] for p in corners),
                max(p[0] for p in corners), max(p[1] for p in corners),
                max(p[2] for p in corners),
                # exact only for a quarter-turn about a coordinate axis: such a
                # rotation is a signed coordinate permutation, so it maps the
                # child's TIGHT box to the rotated solid's TIGHT box. Any other
                # rotation makes the corner re-box a (sound) superset only.
                exact=c.exact and _is_quarter_turn_about_coordinate_axis(axis, angle),
            )

    if kind in GEOMETRY_OPERATIONS:
        if not node.children:
            raise GeometryError(f"{kind} has no children")
        child_boxes = [aabb_of(c, quantities) for c in node.children]
        if kind == "union":
            return _union(child_boxes)
        if kind == "difference":
            # subtracting can only shrink -> the sound bound is the minuend's box.
            # NOT exact: the tool may shave the minuend's extremes, so even a tight
            # minuend box is only a provable SUPERSET of the result's tight box.
            base = child_boxes[0]
            return base if base.empty else replace(base, exact=False)
        if kind == "intersection":
            return _intersection(child_boxes)

    raise GeometryError(f"unknown geometry kind {kind!r}")


def _is_quarter_turn_about_coordinate_axis(
    axis: tuple[float, float, float], angle_deg: float, *, eps: float = 1e-9
) -> bool:
    """True iff the rotation provably maps axis-aligned boxes to axis-aligned boxes.

    Proof sketch: a rotation by k·90° about a coordinate axis is a signed
    permutation of the coordinates; it maps every axis-aligned box bijectively to
    an axis-aligned box and preserves face contact, so a TIGHT child box stays
    tight after corner re-boxing. For any other axis/angle no such claim is made
    (the re-box is then only a sound superset)."""
    ax, ay, az = (abs(c) for c in axis)
    n = math.sqrt(ax * ax + ay * ay + az * az)
    if n < 1e-12:
        return False           # degenerate axis — rotate_point raises loudly anyway
    axis_aligned = max(ax, ay, az) / n > 1.0 - eps
    remainder = angle_deg % 90.0
    quarter_turn = remainder < eps or (90.0 - remainder) < eps
    return axis_aligned and quarter_turn


def _union(boxes: list[Aabb]) -> Aabb:
    present = [b for b in boxes if not b.empty]
    if not present:
        return _EMPTY
    return Aabb(
        min(b.min_x for b in present), min(b.min_y for b in present), min(b.min_z for b in present),
        max(b.max_x for b in present), max(b.max_y for b in present), max(b.max_z for b in present),
        # the envelope of TIGHT boxes is tight for the union (every extreme of the
        # union is attained by some child, whose tight box records it exactly)
        exact=all(b.exact for b in present),
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
    # NOT exact: the solids need not reach the corners of the overlap box, so this
    # is only a provable superset of the intersection's tight box.
    return Aabb(min_x, min_y, min_z, max_x, max_y, max_z, exact=False)


# --- volume (deterministic, exact where provable) ----------------------------

@dataclass(frozen=True)
class Volume:
    """A CSG volume estimate. ``value`` is ALWAYS a sound UPPER BOUND on the true
    volume (in the geometry's length-unit cubed). ``exact`` is True only when the
    value is provably the exact volume — otherwise it is an honest upper bound and
    ``note`` says why it could not be computed exactly. GENESIS never presents an
    estimated volume as exact (PHASE_DELTA.md §0 honesty, applied to a property).

    ``lower`` is ALWAYS a sound LOWER BOUND on the true volume: for an exact value
    it equals ``value``; for a non-exact value it defaults to the honest (possibly
    vacuous) 0.0 unless the caller proves something better. The invariant
    ``0 ≤ lower ≤ value`` is enforced loudly — an inverted bracket is a bug, never
    a silently-returned estimate.
    """

    value: float
    exact: bool
    note: str = ""
    lower: float | None = None

    def __post_init__(self) -> None:
        if self.lower is None:
            object.__setattr__(self, "lower", self.value if self.exact else 0.0)
        if self.lower > self.value + 1e-9 * max(1.0, abs(self.value)):
            raise GeometryError(
                f"unsound volume bracket: lower bound {self.lower} exceeds upper bound {self.value}"
            )


def _contains(outer: Aabb, inner: Aabb) -> bool:
    """True iff `inner` is fully inside `outer` on every axis (closed)."""
    if outer.empty or inner.empty:
        return False
    return (
        outer.min_x <= inner.min_x and inner.max_x <= outer.max_x
        and outer.min_y <= inner.min_y and inner.max_y <= outer.max_y
        and outer.min_z <= inner.min_z and inner.max_z <= outer.max_z
    )


def _is_box_solid(node: GeometryNode) -> bool:
    """True if the node's solid region equals its AABB — i.e. a box, or a
    translate of a box. For such a region, AABB containment of a tool implies
    SOLID containment, which is what makes an exact difference provable."""
    if node.kind == "box":
        return True
    if node.kind == "translate" and node.children:
        return _is_box_solid(node.children[0])
    return False


def _disjoint_pairwise(boxes: list[Aabb]) -> bool:
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if overlaps(boxes[i], boxes[j]):
                return False
    return True


def volume_of(node: GeometryNode, quantities: dict[str, Quantity]) -> Volume:
    """Deterministic CSG volume — exact where provable, else a sound [lower, upper] bracket.

    Primitive volumes are exact (box = x·y·z, cylinder = π·r²·h, sphere =
    4/3·π·r³ — standard formulas; lower == value). For composites (upper bound as
    before, plus a provable LOWER bound on every non-exact path):
      * union: exact = Σ parts when the children are pairwise disjoint (provable
        via AABB); otherwise Σ parts is a sound upper bound (union ≤ Σ) and
        max(part lowers) a sound lower bound — every child is a subset of the
        union, so vol(union) ≥ vol(childᵢ) ≥ lowerᵢ for each i.
      * difference: exact = vol(A) − Σ vol(tool) only when A's solid equals its
        AABB (a box), every tool is contained in A, and tools are pairwise
        disjoint; otherwise vol(A) is a sound upper bound (removing only shrinks)
        and max(0, lower(A) − Σ upper(toolᵢ)) a sound lower bound — the removed
        material is vol(A ∩ ⋃toolᵢ) ≤ Σ vol(toolᵢ) ≤ Σ upperᵢ even when tools
        overlap each other or protrude outside A, so
        vol(A∖tools) ≥ vol(A) − Σ upperᵢ ≥ lower(A) − Σ upperᵢ (clamped at 0).
      * intersection: min(parts) is a sound upper bound (∩ ≤ each part); the lower
        bound is the honest vacuous 0 (disjoint interiors are not excludable here)
        — stated in ``note``, never dressed up as information.
    Raises ``GeometryError`` (via aabb_of / value lookup) on an unrenderable node.
    """
    kind = node.kind

    if kind in GEOMETRY_PRIMITIVES:
        if kind == "box":
            x = _value(node, "size_x", quantities)
            y = _value(node, "size_y", quantities)
            z = _value(node, "size_z", quantities)
            return Volume(x * y * z, exact=True)
        if kind == "cylinder":
            r = _value(node, "radius", quantities)
            h = _value(node, "height", quantities)
            return Volume(math.pi * r * r * h, exact=True)
        if kind == "sphere":
            r = _value(node, "radius", quantities)
            return Volume((4.0 / 3.0) * math.pi * r * r * r, exact=True)

    if kind in GEOMETRY_TRANSFORMS:
        if kind == "translate":
            if not node.children:
                raise GeometryError("translate has no child")
            return volume_of(node.children[0], quantities)  # translation preserves volume
        if kind == "rotate":
            if not node.children:
                raise GeometryError("rotate has no child")
            # validate the axis loudly even though volume is rotation-invariant
            rotate_point((1.0, 0.0, 0.0), (
                _value(node, "axis_x", quantities),
                _value(node, "axis_y", quantities),
                _value(node, "axis_z", quantities),
            ), _value(node, "angle_deg", quantities))
            return volume_of(node.children[0], quantities)  # rigid: volume preserved

    if kind in GEOMETRY_OPERATIONS:
        if not node.children:
            raise GeometryError(f"{kind} has no children")
        parts = [volume_of(c, quantities) for c in node.children]
        boxes = [aabb_of(c, quantities) for c in node.children]
        if kind == "union":
            upper = sum(p.value for p in parts)
            exact = all(p.exact for p in parts) and _disjoint_pairwise(boxes)
            note = "" if exact else "overlapping geometry — value is an upper bound (union ≤ Σ parts)"
            # sound lower bound: each child ⊆ union ⇒ vol(union) ≥ max(part lowers)
            return Volume(upper, exact=exact, note=note,
                          lower=None if exact else max(p.lower for p in parts))
        if kind == "difference":
            a = parts[0]
            tools = parts[1:]
            tool_boxes = boxes[1:]
            contained = all(_contains(boxes[0], tb) for tb in tool_boxes)
            tools_disjoint = _disjoint_pairwise(tool_boxes)
            if a.exact and _is_box_solid(node.children[0]) and contained and tools_disjoint and all(t.exact for t in tools):
                return Volume(a.value - sum(t.value for t in tools), exact=True)
            # sound lower bound: removed ≤ Σ vol(toolᵢ) ≤ Σ upperᵢ (tools may overlap
            # each other or lie outside A — both only make the removal smaller), so
            # vol(A∖tools) ≥ lower(A) − Σ upperᵢ, clamped at the trivial 0.
            return Volume(
                a.value, exact=False,
                note="tool not provably contained / minuend not a box — value is an upper bound (vol of minuend)",
                lower=max(0.0, a.lower - sum(t.value for t in tools)),
            )
        if kind == "intersection":
            upper = min(p.value for p in parts)
            return Volume(
                upper, exact=False,
                note="intersection volume not computed exactly — value is an upper bound "
                     "(∩ ≤ each part); lower bound is the vacuous 0",
                lower=0.0,
            )

    raise GeometryError(f"unknown geometry kind {kind!r}")


def geometry_length_unit(node: GeometryNode, quantities: dict[str, Quantity]) -> str | None:
    """The common length unit of every quantity a geometry references, or None if
    mixed/absent — so a volume/mass is only labelled (and converted) when the unit
    is unambiguous."""
    units: set[str] = set()

    def walk(n: GeometryNode) -> None:
        for qid in n.params.values():
            q = quantities.get(qid)
            if q is not None:
                units.add(q.unit.strip())
        for child in n.children:
            walk(child)

    walk(node)
    return next(iter(units)) if len(units) == 1 else None


# --- mass (volume × declared density, soundly unit-converted) ------------------

_DENSITY_DIM: Dimension = parse_unit("kg/m^3")   # M·L⁻³


@dataclass(frozen=True)
class Mass:
    """A component mass = volume × density, in grams. ``value`` is None when mass
    cannot be computed soundly (no/unknown density, unknown or mixed units, or a
    non-density dimension) — GENESIS reports the reason in ``note`` rather than a
    wrong number. ``exact`` follows the volume's exactness (the density value is a
    declared constant)."""

    value: float | None
    exact: bool
    unit: str = "g"
    note: str = ""


def mass_of(component: Component, quantities: dict[str, Quantity]) -> Mass:
    """Mass of a fabricated component, in grams, soundly unit-converted.

    Requires `component.material_density` to reference a quantity of dimension
    mass/length³, and the geometry to have a single length unit. Converts via
    unit_scale so mm³ × g/cm³ yields the correct magnitude. Returns ``value=None``
    with a reason when it cannot be computed soundly — never a guessed number.
    """
    if component.geometry is None:
        return Mass(None, exact=False, note="component has no geometry")
    if component.material_density is None:
        return Mass(None, exact=False, note="no material density declared")
    density = quantities.get(component.material_density)
    if density is None:
        return Mass(None, exact=False,
                    note=f"density quantity {component.material_density!r} not found")
    if parse_unit(density.unit) != _DENSITY_DIM:
        return Mass(None, exact=False,
                    note=f"density unit {density.unit!r} is not a mass/length³ dimension")
    geom_unit = geometry_length_unit(component.geometry, quantities)
    if geom_unit is None:
        return Mass(None, exact=False, note="geometry has mixed or absent length units")
    s_geom = unit_scale(geom_unit)
    s_dens = unit_scale(density.unit)
    s_gram = unit_scale("g")
    if s_geom is None or s_dens is None or s_gram is None:
        return Mass(None, exact=False, note="unknown unit — cannot convert mass soundly")

    vol = volume_of(component.geometry, quantities)
    # physical mass [kg] = (V · s_geom³) [m³] · (ρ · s_dens) [kg/m³]; report in grams.
    mass_kg = (vol.value * s_geom ** 3) * (density.value * s_dens)
    mass_g = mass_kg / s_gram
    return Mass(mass_g, exact=vol.exact, unit="g",
                note="" if vol.exact else "upper bound (volume is an upper bound)")
