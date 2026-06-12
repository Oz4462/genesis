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

Two further orientation-dependent layers live here (research write-up in
docs/research/PRINT_DESIGN_FAILURES.md):

  * ``first_layer_report`` — the failures born in the FIRST layer: a part with no
    flat plate contact cannot adhere (a sphere printed as-is), and a sharp wall
    meeting the plate at 90° gets the elephant-foot bulge (first layers squashed
    outward), which jams any fit near the base — relieved by a ~0.3 mm base
    chamfer. Warping has no defensible universal threshold, so the report carries
    the EVIDENCE (footprint, contact area, height) and no warping verdict.
  * ``bridge_spans`` — the refinement of the support rule for BRIDGES: a flat
    ceiling anchored on opposite sides prints support-free up to ~10 mm of span
    (printability.FDM_MAX_BRIDGE_MM). Clusters of flat down-facing triangles are
    classified by which of their boundary edges are anchored (the neighbouring
    surface descends); anchored-opposite-sides regions get their axis-aligned
    span checked, unanchored ceilings honestly need support. Exact for the
    axis-aligned CSG world GENESIS builds; arbitrarily rotated bridge geometry
    degrades to the conservative verdict (needs support), never to a false pass.
"""

from __future__ import annotations

import math

from .brep import _require_cadquery, csg_to_solid
from .core.state import GeometryNode, Quantity
from .printability import FDM_BASE_CHAMFER_MM, FDM_MAX_BRIDGE_MM


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
    support_density: float = 0.2,
) -> dict:
    """Inspect a solid for self-supporting printability under one build direction.

    Returns ``{"needs_support", "overhang_area", "worst_overhang_deg",
    "support_volume"}``: needs_support is True if any down-facing surface (off the
    build plate) is within `max_overhang_deg` of straight-down; overhang_area is the
    flagged triangle area; worst_overhang_deg is how far the steepest flagged surface
    tilts past the limit toward horizontal; support_volume is an UPPER-BOUND estimate
    of the support material — the column volume from each overhang triangle down to
    the plate (projected area × height-above-plate) times `support_density` (a
    sparse-infill fraction). Deterministic for fixed `tolerance`.

    Build direction is only required to be normalised internally; build_dir=(0,0,1)
    means +Z is up. The support estimate is an upper bound because it counts the full
    column to the plate even where material sits below the overhang.
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
    column_volume = 0.0
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
            area = 0.5 * length
            overhang_area += area
            worst = max(worst, max_overhang_deg - phi)
            # projected (horizontal) area = |n·down| × area; column height to plate
            column_volume += abs(normal[2]) * area * (centroid_z - zmin)

    return {
        "needs_support": overhang_area > 0.0,
        "overhang_area": overhang_area,
        "worst_overhang_deg": worst,
        "support_volume": column_volume * support_density,
    }


def _basis(up: tuple[float, float, float]):
    """Two orthonormal axes perpendicular to `up` (deterministic construction)."""
    ax = min(((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
             key=lambda a: abs(a[0] * up[0] + a[1] * up[1] + a[2] * up[2]))
    u = _unit(up[1] * ax[2] - up[2] * ax[1],
              up[2] * ax[0] - up[0] * ax[2],
              up[0] * ax[1] - up[1] * ax[0])
    v = _unit(up[1] * u[2] - up[2] * u[1],
              up[2] * u[0] - up[0] * u[2],
              up[0] * u[1] - up[1] * u[0])
    return u, v


def _mesh(node: GeometryNode, quantities: dict[str, Quantity],
          build_dir: tuple[float, float, float], tolerance: float | None):
    """Tessellate and precompute per-triangle data in the build frame.

    Returns ``(tris, up, eps)`` where each tri is a dict with vertex-coordinate
    keys (exact tuples — adjacent OCCT face meshes share edge coordinates
    exactly, proven by the watertight STL topology test), outward normal, area,
    centroid height, min vertex height."""
    _require_cadquery()
    solid = csg_to_solid(node, quantities)
    bb = solid.BoundingBox()
    extent = max(bb.xmax - bb.xmin, bb.ymax - bb.ymin, bb.zmax - bb.zmin)
    eps = extent * 1e-3 + 1e-9
    tol = tolerance if tolerance is not None else max(extent / 200.0, 1e-4)
    up = _unit(*build_dir)

    verts, tris_idx = solid.tessellate(tol)
    pos = [(p.x, p.y, p.z) for p in verts]
    h = [p[0] * up[0] + p[1] * up[1] + p[2] * up[2] for p in pos]
    tris = []
    for i, j, k in tris_idx:
        a, b, c = pos[i], pos[j], pos[k]
        cx = ((b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1]),
              (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]),
              (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
        length = math.sqrt(cx[0] ** 2 + cx[1] ** 2 + cx[2] ** 2)
        if length < 1e-15:
            continue                                  # degenerate sliver
        tris.append({
            "keys": (a, b, c),
            "normal": (cx[0] / length, cx[1] / length, cx[2] / length),
            "area": 0.5 * length,
            "centroid_h": (h[i] + h[j] + h[k]) / 3.0,
            "min_h": min(h[i], h[j], h[k]),
            "max_h": max(h[i], h[j], h[k]),
        })
    return tris, up, eps


def first_layer_report(
    node: GeometryNode,
    quantities: dict[str, Quantity],
    *,
    build_dir: tuple[float, float, float] = (0.0, 0.0, 1.0),
    tolerance: float | None = None,
) -> dict:
    """The first-layer failures: plate adhesion and the elephant-foot bulge.

    Returns ``{"plate_contact", "contact_area", "footprint", "height",
    "sharp_base_edge", "elephant_foot_risk", "recommended_base_chamfer"}``:
    `plate_contact` is False when NO flat face rests on the build plate (a
    sphere/point contact — an adhesion failure before the print begins);
    `footprint` is the (u, v) extent of the plate-contact region; a
    `sharp_base_edge` (a vertical wall meeting the plate directly) plus contact
    means `elephant_foot_risk` — the squashed first layers bulge outward and any
    fit near the base jams — relieved by the recommended ~0.3 mm base chamfer.
    Warping carries no verdict here (material-dependent, no defensible universal
    threshold): footprint/contact/height are the evidence, the human judges.
    Deterministic for a fixed tolerance."""
    tris, up, eps = _mesh(node, quantities, build_dir, tolerance)
    if not tris:
        raise ValueError("tessellation produced no triangles")
    hmin = min(t["min_h"] for t in tris)
    hmax = max(t["max_h"] for t in tris)
    u_ax, v_ax = _basis(up)

    contact_area = 0.0
    contact_pts: list[tuple[float, float]] = []
    sharp_base_edge = False
    for t in tris:
        if t["max_h"] <= hmin + eps:                  # a flat face ON the plate
            contact_area += t["area"]
            for p in t["keys"]:
                contact_pts.append((
                    p[0] * u_ax[0] + p[1] * u_ax[1] + p[2] * u_ax[2],
                    p[0] * v_ax[0] + p[1] * v_ax[1] + p[2] * v_ax[2],
                ))
        else:
            n_up = t["normal"][0] * up[0] + t["normal"][1] * up[1] + t["normal"][2] * up[2]
            if abs(n_up) < math.sin(math.radians(5.0)) and t["min_h"] <= hmin + eps:
                sharp_base_edge = True                # a vertical wall reaches the plate

    footprint = (0.0, 0.0)
    if contact_pts:
        us = [p[0] for p in contact_pts]
        vs = [p[1] for p in contact_pts]
        footprint = (max(us) - min(us), max(vs) - min(vs))
    plate_contact = contact_area > 0.0
    elephant_foot_risk = plate_contact and sharp_base_edge
    return {
        "plate_contact": plate_contact,
        "contact_area": contact_area,
        "footprint": footprint,
        "height": hmax - hmin,
        "sharp_base_edge": sharp_base_edge,
        "elephant_foot_risk": elephant_foot_risk,
        "recommended_base_chamfer": FDM_BASE_CHAMFER_MM if elephant_foot_risk else 0.0,
    }


def bridge_spans(
    node: GeometryNode,
    quantities: dict[str, Quantity],
    *,
    build_dir: tuple[float, float, float] = (0.0, 0.0, 1.0),
    max_span: float = FDM_MAX_BRIDGE_MM,
    flat_tol_deg: float = 5.0,
    tolerance: float | None = None,
) -> dict:
    """Bridge detection — the honest refinement of the blanket support rule.

    ``overhang_check`` flags EVERY flat ceiling above the plate; but a ceiling
    anchored on opposite sides is a BRIDGE and prints support-free up to
    ``max_span`` (10 mm). This groups the flat down-facing triangles into
    connected regions, classifies each region's boundary edges as anchored (the
    neighbouring surface descends below the region) or free, and derives the
    span: the extent across an opposite anchored pair of sides — the direction
    the slicer would lay bridge lines — taking the SHORTER one when both axis
    pairs are anchored (a pocket ceiling). A region with no anchored opposite
    pair cannot be bridged and needs support regardless of size.

    Returns ``{"regions": [...], "worst_span", "needs_support", "ok"}``; each
    region carries ``{"area", "height", "extent", "anchored_sides", "span",
    "needs_support"}`` (span None = unbridgeable). `worst_span` is the largest
    span with None counted as infinity (None when there are no regions at all).
    Exact for axis-aligned geometry (the GENESIS CSG world); rotated bridge
    directions degrade to the conservative needs-support verdict, never to a
    false pass. Deterministic for a fixed tolerance."""
    tris, up, eps = _mesh(node, quantities, build_dir, tolerance)
    if not tris:
        raise ValueError("tessellation produced no triangles")
    hmin = min(t["min_h"] for t in tris)
    u_ax, v_ax = _basis(up)
    down = (-up[0], -up[1], -up[2])

    flat = [i for i, t in enumerate(tris)
            if _angle_deg(t["normal"], down) <= flat_tol_deg
            and t["centroid_h"] > hmin + eps]

    # undirected coordinate-keyed edge map over the WHOLE mesh (for anchoring)
    edge_tris: dict[tuple, list[int]] = {}
    for i, t in enumerate(tris):
        a, b, c = t["keys"]
        for e in ((a, b), (b, c), (c, a)):
            key = e if e[0] <= e[1] else (e[1], e[0])
            edge_tris.setdefault(key, []).append(i)

    # union-find: connect flat triangles sharing a vertex
    parent = {i: i for i in flat}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    by_vertex: dict[tuple, int] = {}
    for i in flat:
        for p in tris[i]["keys"]:
            if p in by_vertex:
                parent[find(i)] = find(by_vertex[p])
            else:
                by_vertex[p] = i

    clusters: dict[int, list[int]] = {}
    for i in flat:
        clusters.setdefault(find(i), []).append(i)

    regions = []
    for members in clusters.values():
        member_set = set(members)
        pts = {p for i in members for p in tris[i]["keys"]}
        h0 = min(tris[i]["min_h"] for i in members)
        us = [p[0] * u_ax[0] + p[1] * u_ax[1] + p[2] * u_ax[2] for p in pts]
        vs = [p[0] * v_ax[0] + p[1] * v_ax[1] + p[2] * v_ax[2] for p in pts]
        umin, umax, vmin, vmax = min(us), max(us), min(vs), max(vs)

        anchored = {"u_low": False, "u_high": False, "v_low": False, "v_high": False}
        for i in members:
            a, b, c = tris[i]["keys"]
            for e in ((a, b), (b, c), (c, a)):
                key = e if e[0] <= e[1] else (e[1], e[0])
                inside = sum(1 for j in edge_tris[key] if j in member_set)
                if inside != 1:
                    continue                          # interior (or defect) edge
                if not any(tris[j]["min_h"] < h0 - eps
                           for j in edge_tris[key] if j not in member_set):
                    continue                          # free edge — nothing below
                eu = [q[0] * u_ax[0] + q[1] * u_ax[1] + q[2] * u_ax[2] for q in key]
                ev = [q[0] * v_ax[0] + q[1] * v_ax[1] + q[2] * v_ax[2] for q in key]
                if all(abs(x - umin) <= eps for x in eu):
                    anchored["u_low"] = True
                if all(abs(x - umax) <= eps for x in eu):
                    anchored["u_high"] = True
                if all(abs(x - vmin) <= eps for x in ev):
                    anchored["v_low"] = True
                if all(abs(x - vmax) <= eps for x in ev):
                    anchored["v_high"] = True

        candidates = []
        if anchored["u_low"] and anchored["u_high"]:
            candidates.append(umax - umin)
        if anchored["v_low"] and anchored["v_high"]:
            candidates.append(vmax - vmin)
        span = min(candidates) if candidates else None
        regions.append({
            "area": sum(tris[i]["area"] for i in members),
            "height": h0,
            "extent": (umax - umin, vmax - vmin),
            "anchored_sides": anchored,
            "span": span,
            "needs_support": span is None or span > max_span,
        })

    regions.sort(key=lambda r: (r["height"], -r["area"]))
    spans = [math.inf if r["span"] is None else r["span"] for r in regions]
    return {
        "regions": regions,
        "worst_span": max(spans) if spans else None,
        "needs_support": any(r["needs_support"] for r in regions),
        "ok": not any(r["needs_support"] for r in regions),
    }
