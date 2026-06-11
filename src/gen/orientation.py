"""Orientation-dependent DFM — overhang detection over the BREP (the δ-DFM upgrade).

The deterministic DFM rules (dfm.py) check wall thickness and hole size from the
quantities. The orientation-dependent rule — "a surface steeper than 45° from the
vertical needs support" — needs the actual geometry AND a build direction, which
the CSG by itself does not carry. This module adds it using the OpenCASCADE kernel
(cadquery/OCP): build the solid, then inspect every face's OUTWARD normal; a
surface whose normal points within `max_overhang_deg` of straight-down (a shallow,
down-facing surface) requires support — except the build-plate contact at the
bottom.

Method: the solid is tessellated into triangles (the standard slicer approach);
each triangle's outward normal follows from its winding (consistent for a valid
solid), and a triangle is an overhang if its normal points within
`max_overhang_deg` of straight-down and it sits above the build plate. The plate
contact is excluded by skipping triangles at the global z-minimum. cadquery/OCP is
optional (lazy import); the test skips when it is absent.

Honest boundary: this is the standard 45° support rule for FDM, exact for the
modelled geometry. It assumes a single build direction (default +Z); it does not
optimise the orientation or model support volume/cost — those are a further layer.
A clean PASS (no support needed) is necessary, not a guarantee of a perfect print.
"""

from __future__ import annotations

import math

from .brep import _require_cadquery, csg_to_solid
from .core.state import GeometryNode, Quantity


def _unit(x: float, y: float, z: float) -> tuple[float, float, float]:
    n = math.sqrt(x * x + y * y + z * z)
    if n < 1e-12:
        return (0.0, 0.0, 0.0)
    return (x / n, y / n, z / n)


def _angle_deg(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    d = max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))
    return math.degrees(math.acos(d))


def overhang_check(
    node: GeometryNode,
    quantities: dict[str, Quantity],
    *,
    build_dir: tuple[float, float, float] = (0.0, 0.0, 1.0),
    max_overhang_deg: float = 45.0,
    tolerance: float | None = None,
) -> dict:
    """Inspect a solid for self-supporting printability under one build direction.

    Returns ``{"needs_support", "overhang_area", "worst_overhang_deg"}``:
    needs_support is True if any down-facing surface (off the build plate) is within
    `max_overhang_deg` of straight-down; overhang_area is the flagged triangle area;
    worst_overhang_deg is how far the steepest flagged surface tilts past the limit
    toward horizontal (0 = exactly at the limit). Deterministic for fixed
    `tolerance`.
    """
    _require_cadquery()  # clear error if OCP is missing
    solid = csg_to_solid(node, quantities)
    bb = solid.BoundingBox()
    zmin = bb.zmin
    extent = max(bb.xmax - bb.xmin, bb.ymax - bb.ymin, bb.zmax - bb.zmin)
    eps = extent * 1e-3 + 1e-9
    tol = tolerance if tolerance is not None else max(extent / 200.0, 1e-4)
    down = _unit(-build_dir[0], -build_dir[1], -build_dir[2])

    verts, tris = solid.tessellate(tol)
    overhang_area = 0.0
    worst = 0.0
    for i, j, k in tris:
        a, b, c = verts[i], verts[j], verts[k]
        cross = b.sub(a).cross(c.sub(a))
        length = cross.Length
        if length < 1e-15:
            continue                                  # degenerate sliver
        normal = (cross.x / length, cross.y / length, cross.z / length)
        centroid_z = (a.z + b.z + c.z) / 3.0
        phi = _angle_deg(normal, down)                # angle from straight-down
        if phi < max_overhang_deg and (centroid_z - zmin) > eps:
            overhang_area += 0.5 * length             # triangle area
            worst = max(worst, max_overhang_deg - phi)

    return {
        "needs_support": overhang_area > 0.0,
        "overhang_area": overhang_area,
        "worst_overhang_deg": worst,
    }
