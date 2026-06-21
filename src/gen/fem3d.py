"""3-D continuum FEM — linear elasticity on 4-node tetrahedra (numpy, no solver dep).

The δ-2 statics layer and the 1-D beam FEM (fem.py) model a beam. The real
continuum stress field — the thing that, at a hole, rises to the Kirsch
concentration the statics layer only bounds conservatively (Kt=3) — needs a 3-D
continuum FEM. This module is one: the constant-strain 4-node tetrahedron of
linear isotropic elasticity, assembled and solved in pure numpy, with a built-in
structured box mesher (each hex cell split into 6 tets). No external solver
(CalculiX/FreeCAD) and no mesher (gmsh) are required.

Verified, not asserted: the constant-strain tetrahedron reproduces a UNIFORM stress
state exactly, so a prismatic bar in axial tension must return σ = F/A to machine
precision on any mesh, with the correct Poisson contraction — the test pins exactly
that. (A conforming mesh of a holed part — to compute the Kt field itself rather
than bound it — needs an unstructured mesher such as gmsh; that is the next layer,
this provides the solver it would feed.)

Consistent SI-ish units: pass E and tractions in MPa/N-mm or Pa/N-m consistently;
lengths set the scale. Honest boundary: linear (small-strain, small-displacement)
isotropic elasticity, static — no plasticity, contact, or large deformation.

Wiring (physics validators campaign): core 4-node tet solver + structured_box_mesh for
3D continuum linear elasticity. Used directly by modal.py:41 (internals for stiffness),
plate_hole.py:156 (Kt), bracket_fem.py:102 (capstone). Resonance path to
physics_validation.VALIDATORS["resonance"], physics_selection recipe, pipeline.assess_specification
+ gate_delta_physics. Cross fem3d_quadratic (shared _elasticity_matrix). L3 seam to δ-gate,
structural (Kt bound), HORIZON δ, sim/inventor via modal quantities.
"""

from __future__ import annotations

import numpy as np

# the 6-tetrahedron (Freudenthal) split of a hex with local corner order
# 0:(0,0,0) 1:(1,0,0) 2:(1,1,0) 3:(0,1,0) 4:(0,0,1) 5:(1,0,1) 6:(1,1,1) 7:(0,1,1)
_HEX_TETS = (
    (0, 1, 3, 7), (0, 1, 7, 5), (0, 5, 7, 4),
    (0, 3, 2, 7), (0, 2, 6, 7), (0, 6, 4, 7),
)
_HEX_CORNERS = (
    (0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
    (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1),
)


def structured_box_mesh(
    lx: float, ly: float, lz: float, nx: int, ny: int, nz: int
) -> tuple[np.ndarray, np.ndarray]:
    """A structured tetrahedral mesh of an ``lx×ly×lz`` box (nx·ny·nz hex cells,
    6 tets each). Returns ``(nodes (Nx3), tets (Mx4))``."""
    xs = np.linspace(0.0, lx, nx + 1)
    ys = np.linspace(0.0, ly, ny + 1)
    zs = np.linspace(0.0, lz, nz + 1)
    nodes = np.array([(x, y, z) for z in zs for y in ys for x in xs], dtype=float)

    def nid(i: int, j: int, k: int) -> int:
        return k * (ny + 1) * (nx + 1) + j * (nx + 1) + i

    tets: list[tuple[int, int, int, int]] = []
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                corner = [nid(i + dx, j + dy, k + dz) for (dx, dy, dz) in _HEX_CORNERS]
                for t in _HEX_TETS:
                    tets.append((corner[t[0]], corner[t[1]], corner[t[2]], corner[t[3]]))
    return nodes, np.array(tets, dtype=int)


def _elasticity_matrix(e_modulus: float, nu: float) -> np.ndarray:
    """6×6 isotropic elasticity matrix D (Voigt: xx,yy,zz,xy,yz,zx)."""
    lam = e_modulus * nu / ((1.0 + nu) * (1.0 - 2.0 * nu))
    mu = e_modulus / (2.0 * (1.0 + nu))
    d = np.zeros((6, 6))
    d[:3, :3] = lam
    d[0, 0] = d[1, 1] = d[2, 2] = lam + 2.0 * mu
    d[3, 3] = d[4, 4] = d[5, 5] = mu
    return d


def _tet_b_and_volume(coords: np.ndarray) -> tuple[np.ndarray, float]:
    """Strain-displacement matrix B (6×12) and volume of a 4-node tetrahedron.
    Constant over the element (constant-strain tetrahedron)."""
    m = np.ones((4, 4))
    m[:, 1:] = coords                       # rows [1, x, y, z]
    vol6 = np.linalg.det(m)                 # = 6·V (signed)
    minv = np.linalg.inv(m)
    grads = minv[1:4, :]                    # (3×4): rows dN/dx, dN/dy, dN/dz
    b = np.zeros((6, 12))
    for i in range(4):
        bx, cy, dz = grads[0, i], grads[1, i], grads[2, i]
        col = 3 * i
        b[0, col] = bx
        b[1, col + 1] = cy
        b[2, col + 2] = dz
        b[3, col] = cy
        b[3, col + 1] = bx
        b[4, col + 1] = dz
        b[4, col + 2] = cy
        b[5, col] = dz
        b[5, col + 2] = bx
    return b, abs(vol6) / 6.0


def solve_elasticity(
    nodes: np.ndarray,
    tets: np.ndarray,
    e_modulus: float,
    nu: float,
    fixed_dofs: dict[int, float],
    loads: dict[int, float],
) -> tuple[np.ndarray, np.ndarray]:
    """Solve K·u = F for a linear-elastic tet mesh.

    `fixed_dofs` and `loads` are keyed by global DOF index (3·node + component,
    component 0/1/2 = x/y/z). Returns ``(displacements (Nx3), element_stresses
    (Mx6))`` in Voigt order. Deterministic.
    """
    n_dof = 3 * len(nodes)
    d = _elasticity_matrix(e_modulus, nu)
    k = np.zeros((n_dof, n_dof))
    b_cache = []
    for tet in tets:
        coords = nodes[tet]
        b, vol = _tet_b_and_volume(coords)
        ke = vol * b.T @ d @ b
        dofs = np.array([3 * n + c for n in tet for c in range(3)])
        k[np.ix_(dofs, dofs)] += ke
        b_cache.append((b, dofs))

    f = np.zeros(n_dof)
    for dof, val in loads.items():
        f[dof] += val
    # Dirichlet BCs by row/col elimination (penalty-free, exact).
    free = np.array([i for i in range(n_dof) if i not in fixed_dofs])
    u = np.zeros(n_dof)
    for dof, val in fixed_dofs.items():
        u[dof] = val
    f_red = f[free] - k[np.ix_(free, np.array(list(fixed_dofs)))] @ np.array(
        list(fixed_dofs.values())
    ) if fixed_dofs else f[free]
    u[free] = np.linalg.solve(k[np.ix_(free, free)], f_red)

    stresses = np.zeros((len(tets), 6))
    for e, (b, dofs) in enumerate(b_cache):
        stresses[e] = d @ b @ u[dofs]
    return u.reshape(-1, 3), stresses


def von_mises(stress6: np.ndarray) -> float:
    """Von-Mises equivalent stress from a Voigt stress vector (xx,yy,zz,xy,yz,zx)."""
    sx, sy, sz, txy, tyz, tzx = stress6
    return float(
        np.sqrt(
            0.5 * ((sx - sy) ** 2 + (sy - sz) ** 2 + (sz - sx) ** 2)
            + 3.0 * (txy ** 2 + tyz ** 2 + tzx ** 2)
        )
    )
