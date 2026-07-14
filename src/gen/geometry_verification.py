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
  • VOLUME agrees — the exact BREP volume equals the analytic ``volume_of`` where that is exact;
    where it is only a bracket, the BREP volume must lie INSIDE the provable
    ``[lower, upper]`` (a hemisphere-class bug — half the volume — fails the lower bound
    even on the non-exact path; a volume above the upper bound is equally a bug).
  • EXTENTS agree — where the analytic ``aabb_of`` is provably TIGHT (``Aabb.exact``) the BREP
    bounding box must match per axis (isclose); where it is only a sound SUPERSET (e.g. after a
    non-quarter-turn rotation) the BREP extent must be CONTAINED per axis — an isclose there
    would flag perfectly correct rotated parts as failures (false negatives).

This catches a CSG whose built geometry diverges from its declared dimensions — exactly the bug
class that once made a sphere render as a hemisphere (half the volume): that mismatch fails the
volume cross-check here. cadquery/OCP is an OPTIONAL dependency (lazy via brep.py); the test
skips when it is absent. Kernel calls (isValid/Volume/BoundingBox) are guarded: an OCCT-side
crash surfaces as GeometryError with context (fail-loud, consistent with brep.py), never as a
raw kernel exception. A passed geometry check is necessary, not sufficient — physical
judgement stays with the statics/DFM/FEM layers. Offline, deterministic, no model calls.
"""

from __future__ import annotations

import math

from .brep import _in_process_cadquery, csg_to_solid
from .core.errors import GeometryError
from .core.state import GeometryNode, Quantity
from .verification.geometry import aabb_of, volume_of


def _kernel_call(solid, method: str, node_kind: str):
    """Run one OCCT kernel measurement, translating any kernel-side crash into a
    GeometryError with context — the cross-check must fail loudly and attributably,
    never with a raw OCCT exception (consistent with brep.py's error contract)."""
    try:
        return getattr(solid, method)()
    except Exception as exc:  # noqa: BLE001 - OCCT raises various Standard_* errors
        raise GeometryError(
            f"OCCT kernel call {method}() failed for geometry {node_kind!r}: {exc}"
        ) from exc


def _brep_measures(
    node: GeometryNode, quantities: dict[str, Quantity]
) -> tuple[bool, float, tuple[float, float, float]]:
    """(valid, volume, extent_xyz) via in-process OCCT or cad-venv bridge."""
    if not _in_process_cadquery():
        from .cad import cadquery_bridge as br

        valid = br.is_valid(node, quantities)
        vol = br.exact_volume(node, quantities)
        xmin, xmax, ymin, ymax, zmin, zmax = br.bounding_box(node, quantities)
        return valid, float(vol), (xmax - xmin, ymax - ymin, zmax - zmin)
    solid = csg_to_solid(node, quantities)
    valid = bool(_kernel_call(solid, "isValid", node.kind))
    brep_volume = float(_kernel_call(solid, "Volume", node.kind))
    bb = _kernel_call(solid, "BoundingBox", node.kind)
    brep_extent = (bb.xmax - bb.xmin, bb.ymax - bb.ymin, bb.zmax - bb.zmin)
    return valid, brep_volume, brep_extent


def verify_geometry(
    node: GeometryNode,
    quantities: dict[str, Quantity],
    *,
    rel_tol: float = 1e-6,
    abs_tol: float = 1e-9,
) -> dict:
    """Cross-check the built BREP solid of `node` against the analytic geometry layer.

    Returns ``{"valid", "nonzero_volume", "brep_volume", "analytic_volume",
    "analytic_volume_lower", "analytic_exact", "volume_ok", "brep_extent",
    "analytic_extent", "analytic_extent_exact", "extent_ok", "ok"}``:
    ok is True only if the solid is valid, has a non-zero volume, its volume agrees with the
    analytic value (equal when that is exact, inside the provable ``[lower, upper]`` bracket
    otherwise), and its bounding box agrees with the analytic AABB on every axis (isclose when
    that box is provably tight, containment when it is only a sound superset — e.g. after a
    non-quarter-turn rotation). Deterministic. Raises GeometryError (via brep.py / bridge)
    if the CAD kernel path is unavailable or the CSG is malformed.
    """
    valid, brep_volume, brep_extent = _brep_measures(node, quantities)
    nonzero = brep_volume > abs_tol
    analytic = volume_of(node, quantities)
    analytic_box = aabb_of(node, quantities)
    analytic_extent = analytic_box.extent

    if not nonzero:
        # a degenerate / empty solid (a difference that removed everything, an empty
        # intersection) has no meaningful bounding box — the kernel cannot measure it.
        # Report it honestly as a failed geometry rather than computing on a null shape.
        return {
            "valid": valid, "nonzero_volume": False, "brep_volume": brep_volume,
            "analytic_volume": analytic.value, "analytic_volume_lower": analytic.lower,
            "analytic_exact": analytic.exact,
            "volume_ok": False, "brep_extent": (0.0, 0.0, 0.0),
            "analytic_extent": analytic_extent,
            "analytic_extent_exact": analytic_box.exact, "extent_ok": False, "ok": False,
        }

    if analytic.exact:
        volume_ok = math.isclose(brep_volume, analytic.value, rel_tol=rel_tol, abs_tol=abs_tol)
    else:
        # analytic is a sound [lower, upper] bracket: the exact BREP volume must lie
        # inside it — the lower bound catches a hemisphere-class bug (half the volume)
        # even where the analytic value is not exact, the upper bound the converse.
        upper_ok = brep_volume <= analytic.value + abs_tol + rel_tol * abs(analytic.value)
        lower_ok = brep_volume >= analytic.lower - abs_tol - rel_tol * abs(analytic.lower)
        volume_ok = upper_ok and lower_ok
    if analytic_box.exact:
        # the analytic box is provably tight -> the kernel must reproduce it
        extent_ok = all(
            math.isclose(b, a, rel_tol=rel_tol, abs_tol=abs_tol)
            for b, a in zip(brep_extent, analytic_extent)
        )
    else:
        # the analytic box is only a sound SUPERSET (e.g. a non-quarter-turn rotation):
        # requiring equality would fail correct parts (false negative) — the sound
        # check is per-axis CONTAINMENT of the measured extent in the bound.
        extent_ok = all(
            b <= a + abs_tol + rel_tol * abs(a)
            for b, a in zip(brep_extent, analytic_extent)
        )

    return {
        "valid": valid,
        "nonzero_volume": nonzero,
        "brep_volume": brep_volume,
        "analytic_volume": analytic.value,
        "analytic_volume_lower": analytic.lower,
        "analytic_exact": analytic.exact,
        "volume_ok": volume_ok,
        "brep_extent": brep_extent,
        "analytic_extent": analytic_extent,
        "analytic_extent_exact": analytic_box.exact,
        "extent_ok": extent_ok,
        "ok": valid and nonzero and volume_ok and extent_ok,
    }
