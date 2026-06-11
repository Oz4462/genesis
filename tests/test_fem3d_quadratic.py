"""Quadratic (10-node) tetrahedron FEM — element correctness and faster Kt convergence.

Two layers of evidence:

1. ELEMENT (pure numpy, no mesher): the T10 element passes the linear patch test —
   a linear displacement field returns EXACTLY the imposed constant strain at every
   Gauss point — and the stiffness has the rigid-body null space (a rigid translation
   carries no force). These pin the element maths without any external dependency.

2. MESH (needs the optional gmsh): on a gmsh order-2 box the element reproduces
   uniform tension to machine precision; and on the plate-with-hole the T10 element
   reaches the analytic Howland/Heywood finite-width gross Kt (~3.14 for d/W=0.2) on a
   COARSE mesh where the linear T4 element still under-predicts — the "faster
   convergence" this refinement is about.

Offline, no LLM. Engine: numpy + gmsh (optional, order-2 mesher).

Run:  pytest tests/test_fem3d_quadratic.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from gen.fem3d_quadratic import (  # noqa: E402
    _EDGES,
    _GAUSS,
    _b_matrix,
    box_mesh_t10,
    solve_elasticity_t10,
    t10_stiffness,
)


def _unit_tet_t10() -> np.ndarray:
    """A non-degenerate T10 element: 4 corners + the 6 edge midpoints (local order)."""
    corners = np.array([(2.0, 0.0, 0.0), (0.0, 3.0, 0.0), (0.0, 0.0, 4.0), (0.0, 0.0, 0.0)])
    mids = [(corners[a] + corners[b]) / 2.0 for a, b in _EDGES]
    return np.vstack([corners, np.array(mids)])


# --- element maths (no mesher needed) ------------------------------------------

def test_linear_patch_test_recovers_constant_strain():
    # impose u_i = G @ x_i with a constant gradient G; the strain must be the
    # symmetric part of G, exactly, at every Gauss point.
    coords = _unit_tet_t10()
    g = np.array([[0.010, 0.002, -0.001],
                  [0.000, -0.003, 0.004],
                  [0.005, 0.000, 0.006]])
    u = (coords @ g.T).reshape(-1)                     # nodal displacements (30,)
    exx, eyy, ezz = g[0, 0], g[1, 1], g[2, 2]
    expected = np.array([exx, eyy, ezz,
                         g[0, 1] + g[1, 0], g[1, 2] + g[2, 1], g[2, 0] + g[0, 2]])
    for gp in _GAUSS:
        b, _ = _b_matrix(coords, gp)
        assert np.allclose(b @ u, expected, atol=1e-12)


def test_stiffness_has_rigid_translation_null_space():
    coords = _unit_tet_t10()
    ke = t10_stiffness(coords, 210000.0, 0.3)
    trans = np.tile([1.0, 0.0, 0.0], 10)               # rigid +x translation
    assert np.allclose(ke @ trans, 0.0, atol=1e-6)


def test_stiffness_is_symmetric():
    ke = t10_stiffness(_unit_tet_t10(), 70000.0, 0.33)
    assert np.allclose(ke, ke.T, atol=1e-9)


# --- meshed solves (need gmsh) -------------------------------------------------

def test_uniform_tension_is_exact_on_a_box():
    pytest.importorskip("gmsh", reason="the T10 mesher needs the optional gmsh package")
    nodes, tets = box_mesh_t10(10.0, 4.0, 2.0, 3.0)
    e_mod, nu, length = 210000.0, 0.3, 10.0
    delta = length * 1e-3
    fixed: dict[int, float] = {}
    for n, (x, y, z) in enumerate(nodes):
        if abs(x) < 1e-6:
            fixed[3 * n] = 0.0
        if abs(x - length) < 1e-6:
            fixed[3 * n] = delta
        if abs(y) < 1e-6:
            fixed[3 * n + 1] = 0.0
        if abs(z) < 1e-6:
            fixed[3 * n + 2] = 0.0
    _, stresses = solve_elasticity_t10(nodes, tets, e_mod, nu, fixed, {})
    sxx = stresses[:, 0]
    assert np.isclose(sxx.mean(), e_mod * delta / length, rtol=1e-9)   # = 210
    assert sxx.std() < 1e-6                                            # uniform, exact


def test_quadratic_tets_converge_faster_at_the_hole():
    pytest.importorskip("gmsh", reason="the T10 mesher needs the optional gmsh package")
    from gen.plate_hole import (
        stress_concentration_plate_hole,
        stress_concentration_plate_hole_t10,
    )
    t4 = stress_concentration_plate_hole(refine_size=1.0, coarse_size=4.0)
    t10 = stress_concentration_plate_hole_t10(refine_size=1.0, coarse_size=4.0)
    # same mesh size, so a like-for-like comparison
    assert t10["n_tets"] == t4["n_tets"]
    # T10 reaches the analytic Howland/Heywood finite-width gross Kt (~3.14 for
    # d/W=0.2) on this coarse mesh; T4 still under-predicts it.
    assert 3.0 < t10["kt"] < 3.35
    assert abs(t10["kt"] - 3.14) < 0.2
    assert t10["kt"] > t4["kt"]


def test_plate_hole_t10_is_deterministic():
    pytest.importorskip("gmsh", reason="the T10 mesher needs the optional gmsh package")
    from gen.plate_hole import stress_concentration_plate_hole_t10
    a = stress_concentration_plate_hole_t10(refine_size=1.0, coarse_size=4.0)
    b = stress_concentration_plate_hole_t10(refine_size=1.0, coarse_size=4.0)
    assert a == b
