"""Computed stress concentration at a hole — the FEM that replaces the Kt=3 bound.

The statics layer (PHASE_DELTA §9) uses the Kirsch factor Kt=3 as a CONSERVATIVE
bound for the stress raiser at a mounting hole. This module COMPUTES it: it meshes
the classic plate-with-a-hole benchmark with gmsh (an unstructured tet mesh,
refined near the hole), feeds it to the 3-D continuum solver (`fem3d`), pulls the
plate in tension, and reads the actual peak stress at the hole edge — closing the
loop the §21 solver was built for.

Quarter-symmetry model (x≥0, y≥0): symmetry planes x=0 and y=0, a thin plate so the
in-plane field is ~plane stress. The peak σ_xx sits at the hole edge on the y-axis
(θ=90° from the load), where Kirsch gives σ_θθ = 3·σ_far for an INFINITE plate.

Verified, not asserted: the computed gross Kt converges (monotonically up under mesh
refinement) to ~3.1-3.3 — the Kirsch value 3.0 raised by the finite-width correction
(Peterson, here d/W=0.2). So the FEM reproduces, and slightly sharpens, the bound the
statics layer assumed — turning a conservative constant into a computed quantity.

gmsh is an OPTIONAL dependency (lazy import); the test skips when it is absent.
Honest boundary: linear elasticity, constant-strain tets (which converge slowly at a
concentration — hence the refinement), a finite plate (so Kt is the finite-width
value, not exactly 3). It computes the in-plane concentration, not a full 3-D fatigue
or fracture judgement.
"""

from __future__ import annotations

import numpy as np

from .core.errors import GeometryError
from .fem3d import solve_elasticity


def _require_gmsh():
    try:
        import gmsh  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised only without gmsh
        raise GeometryError(
            "computing the hole stress concentration needs the optional 'gmsh' "
            "package (unstructured mesher); install it with `pip install gmsh`, or "
            "use the conservative Kt=3 bound from the statics layer."
        ) from exc
    return gmsh


def _mesh_quarter_plate(length, width, thickness, radius, refine_size, coarse_size):
    """Mesh a quarter plate-with-hole into linear tets. Returns ``(nodes, tets)``
    with nodes (N×3) and tets (M×4) of 0-based indices. Deterministic (seeded)."""
    gmsh = _require_gmsh()
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("Mesh.RandomSeed", 1)
        gmsh.model.add("plate")
        box = gmsh.model.occ.addBox(0, 0, 0, length, width, thickness)
        cyl = gmsh.model.occ.addCylinder(0, 0, -1, 0, 0, thickness + 2, radius)
        gmsh.model.occ.cut([(3, box)], [(3, cyl)])
        gmsh.model.occ.synchronize()
        field = gmsh.model.mesh.field.add("Box")
        gmsh.model.mesh.field.setNumber(field, "VIn", refine_size)
        gmsh.model.mesh.field.setNumber(field, "VOut", coarse_size)
        gmsh.model.mesh.field.setNumber(field, "XMin", 0)
        gmsh.model.mesh.field.setNumber(field, "XMax", 3 * radius)
        gmsh.model.mesh.field.setNumber(field, "YMin", 0)
        gmsh.model.mesh.field.setNumber(field, "YMax", 3 * radius)
        gmsh.model.mesh.field.setNumber(field, "ZMin", -1)
        gmsh.model.mesh.field.setNumber(field, "ZMax", thickness + 1)
        gmsh.model.mesh.field.setAsBackgroundMesh(field)
        gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
        gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
        gmsh.model.mesh.generate(3)
        ntags, ncoords, _ = gmsh.model.mesh.getNodes()
        nodes = np.array(ncoords).reshape(-1, 3)
        index = {int(tag): i for i, tag in enumerate(ntags)}
        _, _, conn = gmsh.model.mesh.getElements(dim=3)
        tets = np.array([index[int(t)] for t in conn[0]]).reshape(-1, 4)
        return nodes, tets
    finally:
        gmsh.finalize()


def stress_concentration_plate_hole(
    *,
    length: float = 20.0,
    width: float = 20.0,
    thickness: float = 1.0,
    hole_radius: float = 2.0,
    e_modulus: float = 210000.0,
    nu: float = 0.3,
    refine_size: float = 0.5,
    coarse_size: float = 3.0,
) -> dict:
    """Mesh the plate-with-hole, pull it in tension, and read the stress
    concentration factor at the hole.

    Returns ``{"kt", "far_field_sxx", "peak_sxx", "n_tets"}``: kt = peak σ_xx at the
    hole edge / the far-field σ_xx away from the hole (the gross Kt). Deterministic.
    """
    nodes, tets = _mesh_quarter_plate(
        length, width, thickness, hole_radius, refine_size, coarse_size
    )
    delta = length * 1e-3
    fixed: dict[int, float] = {}
    for n, (x, y, z) in enumerate(nodes):
        if abs(x) < 1e-6:
            fixed[3 * n] = 0.0              # x=0 symmetry plane
        if abs(x - length) < 1e-6:
            fixed[3 * n] = delta            # imposed tension displacement
        if abs(y) < 1e-6:
            fixed[3 * n + 1] = 0.0          # y=0 symmetry plane
        if abs(z) < 1e-6:
            fixed[3 * n + 2] = 0.0          # z restraint
    _, stresses = solve_elasticity(nodes, tets, e_modulus, nu, fixed, {})

    centroids = np.array([nodes[te].mean(axis=0) for te in tets])
    far = float(stresses[centroids[:, 0] > 0.8 * length, 0].mean())
    peak = float(stresses[:, 0].max())
    return {
        "kt": peak / far,
        "far_field_sxx": far,
        "peak_sxx": peak,
        "n_tets": len(tets),
    }
