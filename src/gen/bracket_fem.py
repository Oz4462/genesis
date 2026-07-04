"""3-D FEM of the ACTUAL capstone bracket in bending — the conservative bound, checked.

The statics layer bounds the bracket's mount-hole stress with the conservative
Kirsch Kt=3 (σ_peak = 22 MPa). plate_hole.py computed the canonical TENSION Kt; this
closes it for the real part: it meshes the actual bracket geometry (a box with a
through-hole) with gmsh — refined at both the fixed root (the maximum-bending
section) and the hole — feeds it to the 3-D continuum solver (fem3d), loads it as a
cantilever (fixed wall face, transverse tip load), and reads the real peak stress.

The honest finding it verifies: the full 3-D field confirms the hand-calc (the root
surface stress converges to the analytical σ_nom = 6FL/(bh²)) and shows the
conservative bound was conservative — the hole sits at mid-span (half the root
moment), so even with its concentration it is NOT the critical location, and the
real peak (~7 MPa) is well below the Kt=3 bound (22 MPa) and far below strength
(50 MPa). A conservative hand-calc, confirmed and quantified by FEM.

gmsh is OPTIONAL (lazy import); the test skips when it is absent. Honest boundary:
linear elasticity, constant-strain tets (which under-predict a peak on a coarse
mesh — hence the refinement and the "converges up" framing), static tip load. PLA
modulus E≈3500 MPa, ν≈0.35 are declared material constants.
"""

from __future__ import annotations

import numpy as np

from .core.errors import GeometryError
from .fem3d import solve_elasticity, von_mises


def _require_gmsh():
    try:
        import gmsh  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised only without gmsh
        raise GeometryError(
            "the bracket FEM needs the optional 'gmsh' package; install it with "
            "`pip install gmsh`, or use the conservative statics bound."
        ) from exc
    return gmsh


def bracket_bending_fem(
    *,
    length: float = 60.0,        # q_w — the cantilever arm (x)
    breadth: float = 80.0,       # q_h — the section breadth (y)
    thickness: float = 12.0,     # q_t — the section depth / load direction (z)
    hole_radius: float = 2.25,   # q_hole_r — through-hole, axis z, at the centre
    force: float = 235.3596,     # q_force — the design-load tip force
    e_modulus: float = 3500.0,   # PLA Young's modulus [MPa]
    nu: float = 0.35,
    refine_size: float = 1.2,
    coarse_size: float = 5.0,
) -> dict:
    """Mesh the capstone bracket, load it as a cantilever in bending, and read the
    peak stress. Returns ``{"peak_vm", "root_vm", "hole_vm", "n_tets"}`` (MPa).
    Deterministic (seeded gmsh).

    Raises ValueError on non-finite/unphysical inputs (a NaN force would ride
    through the solve to ``peak_vm=NaN``, which passes every ``< limit`` guard as
    False). The guard fires BEFORE gmsh is required, so a missing gmsh install
    never masks a bad-input error."""
    for name, val in (
        ("length", length), ("breadth", breadth), ("thickness", thickness),
        ("hole_radius", hole_radius), ("force", force),
        ("e_modulus", e_modulus), ("nu", nu),
        ("refine_size", refine_size), ("coarse_size", coarse_size),
    ):
        if not np.isfinite(val):
            raise ValueError(f"{name} must be finite, got {val!r}")
    for name, val in (
        ("length", length), ("breadth", breadth), ("thickness", thickness),
        ("hole_radius", hole_radius), ("e_modulus", e_modulus),
        ("refine_size", refine_size), ("coarse_size", coarse_size),
    ):
        if val <= 0.0:
            raise ValueError(f"{name} must be positive, got {val!r}")
    gmsh = _require_gmsh()
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("Mesh.RandomSeed", 1)
        gmsh.model.add("bracket")
        lx, ly, lz, r = length, breadth, thickness, hole_radius
        box = gmsh.model.occ.addBox(-lx / 2, -ly / 2, -lz / 2, lx, ly, lz)
        cyl = gmsh.model.occ.addCylinder(0, 0, -lz, 0, 0, 2 * lz, r)
        gmsh.model.occ.cut([(3, box)], [(3, cyl)])
        gmsh.model.occ.synchronize()

        def _box_field(vin, xmin, xmax, ymin, ymax):
            f = gmsh.model.mesh.field.add("Box")
            for key, val in (("VIn", vin), ("VOut", coarse_size),
                             ("XMin", xmin), ("XMax", xmax), ("YMin", ymin), ("YMax", ymax),
                             ("ZMin", -lz), ("ZMax", lz)):
                gmsh.model.mesh.field.setNumber(f, key, val)
            return f

        f_hole = _box_field(refine_size, -3 * r, 3 * r, -3 * r, 3 * r)
        f_root = _box_field(refine_size * 1.5, -lx / 2, -lx / 2 + 6, -ly / 2, ly / 2)
        fmin = gmsh.model.mesh.field.add("Min")
        gmsh.model.mesh.field.setNumbers(fmin, "FieldsList", [f_hole, f_root])
        gmsh.model.mesh.field.setAsBackgroundMesh(fmin)
        for opt in ("MeshSizeExtendFromBoundary", "MeshSizeFromPoints", "MeshSizeFromCurvature"):
            gmsh.option.setNumber("Mesh." + opt, 0)
        gmsh.model.mesh.generate(3)
        ntags, ncoords, _ = gmsh.model.mesh.getNodes()
        nodes = np.array(ncoords).reshape(-1, 3)
        index = {int(tag): i for i, tag in enumerate(ntags)}
        _, _, conn = gmsh.model.mesh.getElements(dim=3)
        tets = np.array([index[int(t)] for t in conn[0]]).reshape(-1, 4)
    finally:
        gmsh.finalize()

    fixed: dict[int, float] = {}
    tip: list[int] = []
    for n, (x, y, z) in enumerate(nodes):
        if abs(x + lx / 2) < 1e-5:                  # fixed wall face: all DOF
            for c in range(3):
                fixed[3 * n + c] = 0.0
        if abs(x - lx / 2) < 1e-5:
            tip.append(n)
    loads = {3 * n + 2: -force / len(tip) for n in tip}   # transverse tip load (-z)
    _, stresses = solve_elasticity(nodes, tets, e_modulus, nu, fixed, loads)

    vm = np.array([von_mises(s) for s in stresses])
    centroids = np.array([nodes[te].mean(axis=0) for te in tets])
    root_vm = float(vm[centroids[:, 0] < -lx / 2 + 5].max())
    near_hole = (np.abs(centroids[:, 0]) < 3 * r) & (np.abs(centroids[:, 1]) < 3 * r)
    hole_vm = float(vm[near_hole].max())
    return {
        "peak_vm": float(vm.max()),
        "root_vm": root_vm,
        "hole_vm": hole_vm,
        "n_tets": len(tets),
    }
