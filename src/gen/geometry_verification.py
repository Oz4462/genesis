"""Geometry verification — does the generated CAD match what the spec implies (TIER 3).

Text-to-CAD SOTA (CAD-Judge; CodeGen-3D; visual-feedback loops) checks a generated model
against its intent — execute it, measure it, compare. GENESIS exports CAD and bounds geometry
with AABBs, but nothing cross-checks the BUILT solid against the spec's own declared geometry.
This module does: it builds the exact OpenCASCADE solid (brep.py) and verifies its measured
properties against the INDEPENDENT analytic layer (verification.geometry) — the GENESIS analogue
of "two methods agreeing", applied to the generated geometry.

Three checks, each a cross-comparison of two independent computations of the same property:
  • VALID & NON-DEGENERATE — the kernel reports a topologically valid solid AND its volume is
    > 0 (a difference that removed everything, or an empty intersection, is caught).
  • VOLUME agrees — the exact BREP volume equals the analytic ``volume_of`` where that is exact,
    and never exceeds it where it is only a sound upper bound (a BREP volume above the bound is
    a bug).
  • EXTENTS agree — the BREP bounding box matches the analytic ``aabb_of`` per axis.

This catches a CSG whose built geometry diverges from its declared dimensions — exactly the bug
class that once made a sphere render as a hemisphere (half the volume): that mismatch fails the
volume cross-check here. cadquery/OCP is an OPTIONAL dependency (lazy via brep.py); the test
skips when it is absent. A passed geometry check is necessary, not sufficient — physical
judgement stays with the statics/DFM/FEM layers. Offline, deterministic, no model calls.
"""

from __future__ import annotations

import math

from .brep import csg_to_solid
from .core.state import GeometryNode, Quantity
from .verification.geometry import aabb_of, volume_of


def verify_geometry(
    node: GeometryNode,
    quantities: dict[str, Quantity],
    *,
    rel_tol: float = 1e-6,
    abs_tol: float = 1e-9,
) -> dict:
    """Cross-check the built BREP solid of `node` against the analytic geometry layer.

    Returns ``{"valid", "nonzero_volume", "brep_volume", "analytic_volume",
    "analytic_exact", "volume_ok", "brep_extent", "analytic_extent", "extent_ok", "ok"}``:
    ok is True only if the solid is valid, has a non-zero volume, its volume agrees with the
    analytic value (equal when that is exact, within the sound upper bound otherwise), and its
    bounding box matches the analytic AABB on every axis. Deterministic. Raises GeometryError
    (via brep.py) if cadquery is absent or the CSG is malformed.
    """
    solid = csg_to_solid(node, quantities)
    valid = bool(solid.isValid())
    brep_volume = float(solid.Volume())
    nonzero = brep_volume > abs_tol
    analytic = volume_of(node, quantities)
    analytic_extent = aabb_of(node, quantities).extent

    if not nonzero:
        # a degenerate / empty solid (a difference that removed everything, an empty
        # intersection) has no meaningful bounding box — the kernel cannot measure it.
        # Report it honestly as a failed geometry rather than computing on a null shape.
        return {
            "valid": valid, "nonzero_volume": False, "brep_volume": brep_volume,
            "analytic_volume": analytic.value, "analytic_exact": analytic.exact,
            "volume_ok": False, "brep_extent": (0.0, 0.0, 0.0),
            "analytic_extent": analytic_extent, "extent_ok": False, "ok": False,
        }

    if analytic.exact:
        volume_ok = math.isclose(brep_volume, analytic.value, rel_tol=rel_tol, abs_tol=abs_tol)
    else:  # analytic is a sound UPPER bound: the exact BREP volume must not exceed it
        volume_ok = brep_volume <= analytic.value + abs_tol + rel_tol * abs(analytic.value)

    bb = solid.BoundingBox()
    brep_extent = (bb.xmax - bb.xmin, bb.ymax - bb.ymin, bb.zmax - bb.zmin)
    extent_ok = all(
        math.isclose(b, a, rel_tol=rel_tol, abs_tol=abs_tol)
        for b, a in zip(brep_extent, analytic_extent)
    )

    return {
        "valid": valid,
        "nonzero_volume": nonzero,
        "brep_volume": brep_volume,
        "analytic_volume": analytic.value,
        "analytic_exact": analytic.exact,
        "volume_ok": volume_ok,
        "brep_extent": brep_extent,
        "analytic_extent": analytic_extent,
        "extent_ok": extent_ok,
        "ok": valid and nonzero and volume_ok and extent_ok,
    }
