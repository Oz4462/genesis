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
from .fem3d_quadratic import _t10_from_gmsh, solve_elasticity_t10, t10_nodal_stresses


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


def _build_quarter_plate(gmsh, length, width, thickness, radius, refine_size, coarse_size):
    """Build the quarter plate-with-hole geometry and the hole-refinement size field
    into the active gmsh model (shared by the linear and quadratic meshers). The
    caller generates the mesh and extracts it at the order it wants."""
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


def _mesh_quarter_plate(length, width, thickness, radius, refine_size, coarse_size):
    """Mesh a quarter plate-with-hole into linear tets. Returns ``(nodes, tets)``
    with nodes (N×3) and tets (M×4) of 0-based indices. Deterministic (seeded)."""
    gmsh = _require_gmsh()
    gmsh.initialize()
    try:
        _build_quarter_plate(gmsh, length, width, thickness, radius, refine_size, coarse_size)
        gmsh.model.mesh.generate(3)
        ntags, ncoords, _ = gmsh.model.mesh.getNodes()
        nodes = np.array(ncoords).reshape(-1, 3)
        index = {int(tag): i for i, tag in enumerate(ntags)}
        _, _, conn = gmsh.model.mesh.getElements(dim=3)
        tets = np.array([index[int(t)] for t in conn[0]]).reshape(-1, 4)
        return nodes, tets
    finally:
        gmsh.finalize()


def _mesh_quarter_plate_t10(length, width, thickness, radius, refine_size, coarse_size):
    """Mesh a quarter plate-with-hole into quadratic (T10) tets via gmsh order 2.
    Returns ``(nodes (N×3), tets (M×10))`` in the local T10 ordering. Deterministic."""
    gmsh = _require_gmsh()
    gmsh.initialize()
    try:
        _build_quarter_plate(gmsh, length, width, thickness, radius, refine_size, coarse_size)
        gmsh.model.mesh.generate(3)
        gmsh.model.mesh.setOrder(2)
        return _t10_from_gmsh(gmsh)
    finally:
        gmsh.finalize()


def _tension_bcs(nodes: np.ndarray, length: float) -> dict[int, float]:
    """Quarter-symmetry BCs for the tension test: x=0/y=0 symmetry planes, z=0
    restraint, and an imposed x-displacement on the x=length face (1e-3·length)."""
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
    return fixed


def _read_kt(nodes, tets, stresses, length, peak=None) -> dict:
    """Gross Kt = peak σ_xx / far-field σ_xx (far = the x>0.8·length region). The
    far field is read from element-centroid stress (a smooth region); `peak` may be
    passed in for surface-node recovery (T10), else the centroid peak is used. The
    element centroid uses the 4 CORNERS only (correct for both T4 and T10, whose
    centroid stress is sampled at the natural centroid = mean of the corners)."""
    centroids = np.array([nodes[te[:4]].mean(axis=0) for te in tets])
    far = float(stresses[centroids[:, 0] > 0.8 * length, 0].mean())
    if peak is None:
        peak = float(stresses[:, 0].max())
    return {"kt": peak / far, "far_field_sxx": far, "peak_sxx": peak, "n_tets": len(tets)}


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
    concentration factor at the hole (LINEAR T4 tets).

    Returns ``{"kt", "far_field_sxx", "peak_sxx", "n_tets"}``: kt = peak σ_xx at the
    hole edge / the far-field σ_xx away from the hole (the gross Kt). Deterministic.
    """
    nodes, tets = _mesh_quarter_plate(
        length, width, thickness, hole_radius, refine_size, coarse_size
    )
    fixed = _tension_bcs(nodes, length)
    _, stresses = solve_elasticity(nodes, tets, e_modulus, nu, fixed, {})
    return _read_kt(nodes, tets, stresses, length)


def stress_concentration_plate_hole_t10(
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
    """Same as ``stress_concentration_plate_hole`` but with QUADRATIC (T10) tets,
    which capture the concentration field with far fewer elements (linear strain per
    element) — so the converged finite-width Kt is reached on a much coarser mesh.
    The peak σ_xx is recovered at the element NODES (where the hole-edge surface is),
    not the interior centroid, since the linear-strain T10 field resolves it there.

    Returns ``{"kt", "far_field_sxx", "peak_sxx", "n_tets"}``. Deterministic.
    """
    nodes, tets = _mesh_quarter_plate_t10(
        length, width, thickness, hole_radius, refine_size, coarse_size
    )
    fixed = _tension_bcs(nodes, length)
    u3, stresses = solve_elasticity_t10(nodes, tets, e_modulus, nu, fixed, {})
    nodal = t10_nodal_stresses(nodes, tets, u3, e_modulus, nu)
    peak = float(nodal[:, :, 0].max())
    return _read_kt(nodes, tets, stresses, length, peak=peak)
