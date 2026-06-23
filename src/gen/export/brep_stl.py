"""Print-ready STL via the OCCT kernel — CSG booleans evaluated, then tessellated.

The plain mesh export (export/stl.py) honestly refuses CSG booleans: meshing a
``difference`` correctly needs a real geometry kernel. This module is that kernel path:
it builds the exact OpenCASCADE solid (brep.py — the same one the geometry verification
cross-checks), tessellates it, and writes an ASCII STL whose triangles carry the
kernel's consistent outward winding. The result is a directly sliceable, print-ready
mesh — hole and all.

Verified, not asserted: the mesh volume (divergence theorem over the triangles) matches
the kernel's exact solid volume to the tessellation tolerance (the capstone bracket:
0.0001 %), and is strictly below the unbored box volume — the hole is provably in the
mesh. cadquery/OCP is an OPTIONAL dependency (lazy via brep.py); the CLI falls back to
the boolean-refusing primitive export when the kernel is absent, so honesty is preserved
either way.

Honest boundary: `tolerance` is the chordal sag of the tessellation (mm) — smaller is
smoother and heavier; curvature is approximated by flat triangles as in every STL. The
geometry is exact up to that tessellation; printability (walls, supports, fit) is judged
by the δ-DFM layers, not by this exporter.
"""

from __future__ import annotations

import importlib.util

from ..core.errors import GeometryError
from ..core.state import Quantity, Specification
from ..brep import csg_to_solid


def _in_process_cadquery() -> bool:
    """True iff cadquery imports in THIS interpreter. When False (the GENESIS box,
    where cadquery lives only in the isolated cad venv) the STL is produced via the
    subprocess bridge instead of the in-process tessellation below."""
    return importlib.util.find_spec("cadquery") is not None


def _facet(a, b, c) -> str | None:
    """One STL facet from three tessellation vertices (kernel winding kept); None for
    a degenerate sliver."""
    ux, uy, uz = b.x - a.x, b.y - a.y, b.z - a.z
    vx, vy, vz = c.x - a.x, c.y - a.y, c.z - a.z
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    length = (nx * nx + ny * ny + nz * nz) ** 0.5
    if length < 1e-15:
        return None
    nx, ny, nz = nx / length, ny / length, nz / length
    return (
        f"  facet normal {nx:.6e} {ny:.6e} {nz:.6e}\n"
        "    outer loop\n"
        f"      vertex {a.x:.6e} {a.y:.6e} {a.z:.6e}\n"
        f"      vertex {b.x:.6e} {b.y:.6e} {b.z:.6e}\n"
        f"      vertex {c.x:.6e} {c.y:.6e} {c.z:.6e}\n"
        "    endloop\n"
        "  endfacet\n"
    )


def specification_to_brep_stl(spec: Specification, *, tolerance: float = 0.1) -> str:
    """Print-ready ASCII STL of every fabricated component, booleans evaluated on the
    OCCT kernel.

    All components' triangles are written into ONE ``solid`` block (slicers expect a
    single body per file by default; the capstone has one component). Deterministic for
    a fixed tolerance. Raises GeometryError if no component carries geometry, or (via
    brep.py) when cadquery is absent or the CSG is malformed.
    """
    quantities: dict[str, Quantity] = {q.id: q for q in spec.quantities}
    parts = [c for c in spec.components if c.geometry is not None]
    if not parts:
        raise GeometryError("no component with geometry to export")

    # Off-box / isolated-venv path: tessellate every part in the cad venv and fuse
    # the resulting facet blocks into one body (strip each part's solid wrapper).
    if not _in_process_cadquery():
        from ..cad import cadquery_bridge  # noqa: PLC0415
        body = [f"solid genesis_{spec.run_id}\n"]
        n_facets = 0
        for comp in parts:
            part_stl = cadquery_bridge.to_stl(
                comp.geometry, quantities, name="part", tolerance=tolerance
            )
            for line in part_stl.splitlines(keepends=True):
                if line.startswith("solid ") or line.startswith("endsolid "):
                    continue
                body.append(line)
                if line.lstrip().startswith("facet normal"):
                    n_facets += 1
        if n_facets == 0:
            raise GeometryError("tessellation produced no facets (degenerate geometry?)")
        body.append(f"endsolid genesis_{spec.run_id}\n")
        return "".join(body)

    chunks: list[str] = [f"solid genesis_{spec.run_id}\n"]
    n_facets = 0
    for comp in parts:
        solid = csg_to_solid(comp.geometry, quantities)
        verts, tris = solid.tessellate(tolerance)
        for i, j, k in tris:
            facet = _facet(verts[i], verts[j], verts[k])
            if facet is not None:
                chunks.append(facet)
                n_facets += 1
    if n_facets == 0:
        raise GeometryError("tessellation produced no facets (degenerate geometry?)")
    chunks.append(f"endsolid genesis_{spec.run_id}\n")
    return "".join(chunks)


def component_to_brep_stl(geometry, quantities: dict[str, Quantity], *,
                          name: str = "part", tolerance: float = 0.1) -> str:
    """Print-ready ASCII STL of ONE component's CSG, booleans evaluated on the OCCT kernel, as its own
    ``solid`` block — for multi-part ASSEMBLIES where each part is printed separately (one file per
    part), unlike ``specification_to_brep_stl`` which fuses every component into a single body. Same
    tessellation and outward winding. Raises GeometryError if cadquery is absent, the CSG is malformed,
    or the mesh is degenerate (no facets)."""
    if not _in_process_cadquery():
        from ..cad import cadquery_bridge  # noqa: PLC0415
        return cadquery_bridge.to_stl(geometry, quantities, name=name, tolerance=tolerance)
    solid = csg_to_solid(geometry, quantities)
    verts, tris = solid.tessellate(tolerance)
    chunks: list[str] = [f"solid genesis_{name}\n"]
    n_facets = 0
    for i, j, k in tris:
        facet = _facet(verts[i], verts[j], verts[k])
        if facet is not None:
            chunks.append(facet)
            n_facets += 1
    if n_facets == 0:
        raise GeometryError(f"tessellation produced no facets for {name!r} (degenerate geometry?)")
    chunks.append(f"endsolid genesis_{name}\n")
    return "".join(chunks)
