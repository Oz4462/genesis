"""STL mesh integrity — is the exported mesh actually sliceable? (δ-layer)

The classic way a CAD design fails in print without ever looking wrong on screen:
the MESH is broken. A slicer needs a closed, consistently-oriented 2-manifold —
every triangle edge shared by exactly two triangles, wound in opposite directions,
normals pointing outward. Holes in the mesh, non-manifold edges, flipped facets and
inverted solids make slicers guess (or refuse), and the print fails or prints
inside-out. This module checks the exported ASCII STL itself, independently of the
kernel that produced it — a second, mesh-level proof on top of brep_stl.py's
volume proof.

The mathematics is exact, not heuristic:

  * WATERTIGHT + CONSISTENT WINDING — for a closed orientable surface, every
    directed edge (a→b) appears exactly once and its reverse (b→a) exactly once.
    One condition covers both defects: a missing reverse is a hole (open edge), a
    duplicated directed edge is a flipped or non-manifold facet.
  * EULER CHARACTERISTIC — chi = V − E + F = 2 − 2g for a closed connected
    orientable surface of genus g (Euler–Poincaré). A box mesh must give chi = 2
    (genus 0); a part with one through-hole, chi = 0 (genus 1). An ODD chi is a
    topology defect no visual inspection finds and is flagged. There is NO
    per-shell decomposition: for multi-shell files chi is the SUM over shells,
    so an even chi > 2 is possible for valid meshes — it only suppresses the
    genus (None), it is reported, not flagged.
  * OUTWARD ORIENTATION — the divergence-theorem signed volume of a closed,
    consistently wound mesh is positive iff the normals point outward. An
    inside-out solid has exactly the negative volume.

Vertices are matched EXACTLY (same coordinates), which is correct for a mesh
produced by one tessellation pass (brep_stl.py, and any single-kernel export).
Honest boundary: meshes from other tools with jittered shared vertices can report
false open edges here — that is a refusal to guess a welding tolerance, not a bug;
genus is only derived when the surface is closed (chi = 2 − 2g needs closedness),
and for multi-shell files chi is the SUM over shells, which the report states
rather than hiding. Pure stdlib; offline; deterministic.

Sources: Euler–Poincaré formula for closed orientable surfaces (standard
topology / mesh-processing, e.g. Botsch et al., *Polygon Mesh Processing*, 2010);
divergence-theorem mesh volume (same); STL 2-manifold requirement for slicing
(any slicer documentation, e.g. the "non-manifold / not watertight" repair class
in PrusaSlicer/Cura).
"""

from __future__ import annotations

import math
import re

_VERTEX_RE = re.compile(r"vertex\s+([^\s]+)\s+([^\s]+)\s+([^\s]+)")

Vec = tuple[float, float, float]


def _triangles(stl_text: str) -> list[tuple[Vec, Vec, Vec]]:
    """Parse the facet vertices of an ASCII STL into triangles (groups of three).
    Raises ValueError when the vertex count is not a multiple of three, or when
    any vertex component is non-finite (nan/inf/1e999) — a malformed file must
    surface, not produce a half-parsed verdict: a +inf vertex can still yield
    volume_positive=True while chi/genus are garbage."""
    verts: list[Vec] = [
        (float(m.group(1)), float(m.group(2)), float(m.group(3)))
        for m in _VERTEX_RE.finditer(stl_text)
    ]
    if not verts:
        raise ValueError("no vertices found — not an ASCII STL?")
    if len(verts) % 3 != 0:
        raise ValueError(
            f"malformed STL: {len(verts)} vertices is not a multiple of three"
        )
    for v in verts:
        if not all(math.isfinite(c) for c in v):
            raise ValueError(
                f"malformed STL: non-finite vertex {v!r} — every coordinate must "
                "be finite for topology and volume to mean anything"
            )
    return [tuple(verts[i : i + 3]) for i in range(0, len(verts), 3)]  # type: ignore[misc]


def _signed_volume(tris: list[tuple[Vec, Vec, Vec]]) -> float:
    """Divergence-theorem signed volume: positive iff consistently outward-wound."""
    vol = 0.0
    for a, b, c in tris:
        vol += (
            a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0])
            + a[2] * (b[0] * c[1] - b[1] * c[0])
        ) / 6.0
    return vol


def _is_degenerate(a: Vec, b: Vec, c: Vec) -> bool:
    """Zero-area triangle (repeated vertex or collinear points)."""
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    # Absolute threshold, justified for the GENESIS mm convention (PHASE_DELTA §1):
    # |u×v| is twice the triangle area, so 1e-15 means area < 5e-16 mm². True
    # degeneracies (repeated vertex, exactly collinear points) give exactly 0.0;
    # the smallest real tessellation facets of printable parts are many orders of
    # magnitude above this. Honest boundary: NOT unit-agnostic — a mesh authored
    # in metres with sub-µm features would need a relative threshold, which is
    # out of scope for the mm-based export pipeline this module checks.
    return (nx * nx + ny * ny + nz * nz) ** 0.5 < 1e-15


def stl_integrity_check(stl_text: str) -> dict:
    """Mesh-level printability proof of an ASCII STL.

    Returns ``{"ok", "n_facets", "n_vertices", "n_edges", "n_degenerate",
    "watertight", "consistent_winding", "euler_characteristic", "genus",
    "volume", "volume_positive", "issues"}``. ``ok`` is True only when the mesh
    is watertight, consistently wound, outward-oriented (positive volume), free
    of degenerate facets, and has a plausible closed-surface Euler characteristic
    (chi even); every defect appends a human-readable entry to ``issues`` —
    never a silent pass. ``genus`` is derived as (2 − chi) / 2 only for a closed
    single-shell-consistent chi (chi <= 2, even); otherwise None. Raises
    ValueError on a file that cannot be parsed as ASCII STL triangles at all
    (an unparseable mesh must not get a verdict). Deterministic, stdlib-only."""
    tris = _triangles(stl_text)
    issues: list[str] = []

    n_degenerate = sum(1 for a, b, c in tris if _is_degenerate(a, b, c))
    if n_degenerate:
        issues.append(f"{n_degenerate} degenerate (zero-area) facet(s)")

    directed: dict[tuple[Vec, Vec], int] = {}
    for a, b, c in tris:
        for e in ((a, b), (b, c), (c, a)):
            directed[e] = directed.get(e, 0) + 1

    duplicated = sum(1 for n in directed.values() if n > 1)
    open_edges = sum(1 for (u, v) in directed if (v, u) not in directed)
    consistent_winding = duplicated == 0
    watertight = open_edges == 0 and consistent_winding
    if duplicated:
        issues.append(
            f"{duplicated} directed edge(s) used more than once "
            "(flipped or non-manifold facet)"
        )
    if open_edges:
        issues.append(f"{open_edges} open (unmatched) edge(s) — the mesh has holes")

    vertices = {v for tri in tris for v in tri}
    undirected = {(u, v) if u <= v else (v, u) for (u, v) in directed}
    chi = len(vertices) - len(undirected) + len(tris)
    genus: int | None = None
    if watertight and chi % 2 == 0 and chi <= 2:
        genus = (2 - chi) // 2
    if chi % 2 != 0:
        issues.append(f"odd Euler characteristic {chi} — broken surface topology")

    volume = _signed_volume(tris)
    volume_positive = volume > 0.0
    if not volume_positive:
        issues.append(
            f"signed volume {volume:.6g} is not positive — normals point inward "
            "(inside-out solid) or the mesh is not closed"
        )

    return {
        "ok": not issues,
        "n_facets": len(tris),
        "n_vertices": len(vertices),
        "n_edges": len(undirected),
        "n_degenerate": n_degenerate,
        "watertight": watertight,
        "consistent_winding": consistent_winding,
        "euler_characteristic": chi,
        "genus": genus,
        "volume": volume,
        "volume_positive": volume_positive,
        "issues": issues,
    }
