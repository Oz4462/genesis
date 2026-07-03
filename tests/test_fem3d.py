"""3-D continuum FEM (tetrahedral linear elasticity) verified against exact solutions.

fem3d.py is a real 3-D continuum solver - the constant-strain 4-node tetrahedron of
linear isotropic elasticity, in pure numpy, with a built-in structured box mesher
(no external solver/mesher). The constant-strain tetrahedron reproduces a UNIFORM
stress state EXACTLY, so:
  * a displacement-controlled bar returns sigma = E*delta/L to machine precision,
    perfectly uniform, with sigma_yy = sigma_zz = 0 and the exact Poisson contraction;
  * a force-controlled bar returns mean sigma_xx = F/A exactly (equilibrium).

Offline, no LLM, no external engine (numpy only).

Run:  pytest tests/test_fem3d.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402

from gen.fem3d import solve_elasticity, structured_box_mesh, von_mises  # noqa: E402

LX, LY, LZ, E, NU = 10.0, 2.0, 2.0, 210000.0, 0.3


def _symmetry_bcs(nodes):
    fixed = {}
    for n, (x, y, z) in enumerate(nodes):
        if abs(x) < 1e-9:
            fixed[3 * n] = 0.0          # x=0 face: ux = 0
        if abs(y) < 1e-9:
            fixed[3 * n + 1] = 0.0      # y=0 face: uy = 0
        if abs(z) < 1e-9:
            fixed[3 * n + 2] = 0.0      # z=0 face: uz = 0
    return fixed


def test_mesh_shape():
    nodes, tets = structured_box_mesh(LX, LY, LZ, 4, 2, 2)
    assert nodes.shape == (5 * 3 * 3, 3)
    assert tets.shape == (4 * 2 * 2 * 6, 4)        # 6 tets per hex cell


def test_uniform_tension_is_exact_under_displacement_control():
    nodes, tets = structured_box_mesh(LX, LY, LZ, 4, 2, 2)
    delta = 0.01
    fixed = _symmetry_bcs(nodes)
    for n, (x, y, z) in enumerate(nodes):
        if abs(x - LX) < 1e-9:
            fixed[3 * n] = delta                   # imposed end displacement
    _, sig = solve_elasticity(nodes, tets, E, NU, fixed, {})

    expected = E * delta / LX                       # uniaxial: sigma = E*eps
    assert np.allclose(sig[:, 0], expected, atol=1e-6)   # uniform to machine precision
    assert np.allclose(sig[:, 1], 0.0, atol=1e-6)        # sigma_yy = 0
    assert np.allclose(sig[:, 2], 0.0, atol=1e-6)        # sigma_zz = 0


def test_poisson_contraction_is_correct():
    nodes, tets = structured_box_mesh(LX, LY, LZ, 4, 2, 2)
    delta = 0.01
    fixed = _symmetry_bcs(nodes)
    for n, (x, y, z) in enumerate(nodes):
        if abs(x - LX) < 1e-9:
            fixed[3 * n] = delta
    u, _ = solve_elasticity(nodes, tets, E, NU, fixed, {})
    eps = delta / LX
    yface = [n for n, (x, y, z) in enumerate(nodes) if abs(y - LY) < 1e-9]
    assert np.isclose(u[yface, 1].mean(), -NU * eps * LY, atol=1e-9)


def test_von_mises_equals_axial_stress_in_uniaxial():
    nodes, tets = structured_box_mesh(LX, LY, LZ, 4, 2, 2)
    delta = 0.01
    fixed = _symmetry_bcs(nodes)
    for n, (x, y, z) in enumerate(nodes):
        if abs(x - LX) < 1e-9:
            fixed[3 * n] = delta
    _, sig = solve_elasticity(nodes, tets, E, NU, fixed, {})
    vm = [von_mises(s) for s in sig]
    assert np.allclose(vm, E * delta / LX, atol=1e-6)


def test_force_controlled_mean_stress_equals_F_over_A():
    nodes, tets = structured_box_mesh(LX, LY, LZ, 5, 2, 2)
    fixed = _symmetry_bcs(nodes)
    end = [n for n, (x, y, z) in enumerate(nodes) if abs(x - LX) < 1e-9]
    force = 1000.0
    loads = {3 * n: force / len(end) for n in end}
    _, sig = solve_elasticity(nodes, tets, E, NU, fixed, loads)
    # the volume-average axial stress equals F/A exactly by equilibrium
    assert np.isclose(sig[:, 0].mean(), force / (LY * LZ), rtol=1e-9)
