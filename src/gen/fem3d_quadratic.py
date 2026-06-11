"""Quadratic (10-node) tetrahedron FEM — linear-strain elements, faster convergence.

The 4-node tetrahedron (fem3d.py) has CONSTANT strain, so it under-predicts a stress
gradient and converges slowly. The 10-node tetrahedron (T10: 4 corners + 6 edge
midpoints) has quadratic shape functions and therefore LINEAR strain — it captures a
bending or concentration field with far fewer elements. This module adds it in pure
numpy with numerical (4-point Gauss) integration.

The element is meshed from a gmsh 2nd-order mesh: the structured 6-tet hex split is
degenerate for quadratic elements (its crossing internal diagonals put two distinct
nodes at the same edge midpoint, so the mesh does not conform), so the T10 mesh comes
from gmsh `setOrder(2)` with the 6 edge nodes re-sorted to this module's local order
by matching each to the corner pair whose geometric midpoint it is — making the
ordering independent of gmsh's own edge numbering.

Verified, not asserted: the element passes the linear patch test (a linear
displacement field gives exactly the imposed constant strain) and reproduces uniform
tension to machine precision on a gmsh order-2 box; and on the plate-with-hole the
T10 element reaches the converged Kirsch/finite-width Kt on a far coarser mesh than
the linear T4 element — the "faster convergence" this refinement is about.

Honest boundary: linear isotropic elasticity, static; numerical integration (4-point
Gauss, exact for these elements). The mesher needs the optional `gmsh` package.
"""

from __future__ import annotations

import numpy as np

from .core.errors import GeometryError
from .fem3d import _elasticity_matrix

# T10 local node order: 4 corners (0-3), then 6 edge midpoints for edges
# (0,1),(1,2),(2,0),(0,3),(1,3),(2,3).
_EDGES = ((0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3))

# natural coords (xi,eta,zeta) of the 10 nodes in local order — corners then the
# six edge midpoints — used for nodal stress recovery at the element surface.
_NODE_NAT = np.array([
    (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0, 0.0),
    (0.5, 0.5, 0.0), (0.0, 0.5, 0.5), (0.5, 0.0, 0.5),
    (0.5, 0.0, 0.0), (0.0, 0.5, 0.0), (0.0, 0.0, 0.5),
])

# 4-point Gauss rule for a tetrahedron (degree-2 exact); barycentric a,b.
_GA, _GB = 0.585410196624969, 0.138196601125011
_GAUSS = np.array([
    (_GA, _GB, _GB), (_GB, _GA, _GB), (_GB, _GB, _GA), (_GB, _GB, _GB),
])
_GW = 0.25  # weight per point (sum = 1; multiplied by 6·V below)


def _shape_grads(xi: float, eta: float, zeta: float) -> np.ndarray:
    """(10×3) derivatives dN_i/d(xi,eta,zeta) for the T10 element. L4 = 1-xi-eta-zeta."""
    l4 = 1.0 - xi - eta - zeta
    g = np.zeros((10, 3))
    # corners: N = L(2L-1) -> dN/dL = 4L-1
    g[0] = (4 * xi - 1, 0.0, 0.0)
    g[1] = (0.0, 4 * eta - 1, 0.0)
    g[2] = (0.0, 0.0, 4 * zeta - 1)
    g[3] = (-(4 * l4 - 1), -(4 * l4 - 1), -(4 * l4 - 1))
    # edges: N = 4 La Lb
    g[4] = (4 * eta, 4 * xi, 0.0)                       # (0,1): 4 xi eta
    g[5] = (0.0, 4 * zeta, 4 * eta)                     # (1,2): 4 eta zeta
    g[6] = (4 * zeta, 0.0, 4 * xi)                      # (2,0): 4 zeta xi
    g[7] = (4 * (l4 - xi), -4 * xi, -4 * xi)            # (0,3): 4 xi L4
    g[8] = (-4 * eta, 4 * (l4 - eta), -4 * eta)         # (1,3): 4 eta L4
    g[9] = (-4 * zeta, -4 * zeta, 4 * (l4 - zeta))      # (2,3): 4 zeta L4
    return g


def _b_matrix(coords: np.ndarray, gp: np.ndarray) -> tuple[np.ndarray, float]:
    """Strain-displacement matrix B (6×30) and |detJ| at a Gauss point `gp`."""
    grads_nat = _shape_grads(*gp)                      # (10×3) d N/d natural
    jac = grads_nat.T @ coords                         # (3×3); jac[j,k] = dx_k/dxi_j
    detj = np.linalg.det(jac)
    grads = grads_nat @ np.linalg.inv(jac).T           # (10×3) d N/d global
    b = np.zeros((6, 30))
    for i in range(10):
        bx, cy, dz = grads[i]
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
    return b, abs(detj)


def t10_stiffness(coords: np.ndarray, e_modulus: float, nu: float) -> np.ndarray:
    """30×30 stiffness of one T10 element by 4-point Gauss integration."""
    d = _elasticity_matrix(e_modulus, nu)
    ke = np.zeros((30, 30))
    for gp in _GAUSS:
        b, detj = _b_matrix(coords, gp)                # detj already |·| (see _b_matrix)
        ke += _GW * (detj / 6.0) * b.T @ d @ b         # weight·V_ref·|J|, V_ref=1/6
    return ke


def _require_gmsh():
    try:
        import gmsh  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised only without gmsh
        raise GeometryError(
            "the quadratic-tet mesher needs the optional 'gmsh' package; install it "
            "with `pip install gmsh`, or use the linear-tet solver (fem3d)."
        ) from exc
    return gmsh


def _reorder_t10(raw_tets: np.ndarray, nodes: np.ndarray) -> np.ndarray:
    """Reorder each gmsh T10 element's 6 edge nodes to the local convention above by
    matching each edge node to the corner pair whose geometric midpoint it is — so
    the ordering is independent of the mesher's own edge numbering."""
    out = []
    for el in raw_tets:
        corners = list(el[:4])
        edge_nodes = list(el[4:])
        row = list(corners)
        for a, b in _EDGES:
            target = (nodes[corners[a]] + nodes[corners[b]]) / 2.0
            best = min(edge_nodes, key=lambda m: float(np.linalg.norm(nodes[m] - target)))
            row.append(best)
        out.append(row)
    return np.array(out, dtype=int)


def _t10_from_gmsh(gmsh) -> tuple[np.ndarray, np.ndarray]:
    """Extract a conforming T10 mesh (reordered) from the current gmsh model after a
    2nd-order mesh has been generated."""
    ntags, ncoords, _ = gmsh.model.mesh.getNodes()
    nodes = np.array(ncoords).reshape(-1, 3)
    index = {int(tag): i for i, tag in enumerate(ntags)}
    etypes, _, conn = gmsh.model.mesh.getElements(dim=3)
    raw = None
    for et, e in zip(etypes, conn):
        if et == 11:                                   # 10-node tetrahedron
            raw = np.array([index[int(x)] for x in e]).reshape(-1, 10)
    if raw is None:
        raise GeometryError("no 10-node tetrahedra in the mesh (was setOrder(2) called?)")
    return nodes, _reorder_t10(raw, nodes)


def box_mesh_t10(lx: float, ly: float, lz: float, size: float) -> tuple[np.ndarray, np.ndarray]:
    """A conforming quadratic (T10) mesh of an ``lx×ly×lz`` box via gmsh. Returns
    ``(nodes (N×3), tets (M×10))`` in the local ordering above. Deterministic."""
    gmsh = _require_gmsh()
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("Mesh.RandomSeed", 1)
        gmsh.model.add("box")
        gmsh.model.occ.addBox(0, 0, 0, lx, ly, lz)
        gmsh.model.occ.synchronize()
        gmsh.option.setNumber("Mesh.MeshSizeMax", size)
        gmsh.model.mesh.generate(3)
        gmsh.model.mesh.setOrder(2)
        return _t10_from_gmsh(gmsh)
    finally:
        gmsh.finalize()


def solve_elasticity_t10(nodes, tets, e_modulus, nu, fixed_dofs, loads):
    """Solve K·u = F for a T10 mesh. Same interface as fem3d.solve_elasticity but
    with 10-node elements. Returns ``(displacements (N×3), element_stresses (M×6))``
    (stress evaluated at the element centroid)."""
    n_dof = 3 * len(nodes)
    d = _elasticity_matrix(e_modulus, nu)
    k = np.zeros((n_dof, n_dof))
    for tet in tets:
        coords = nodes[tet]
        ke = t10_stiffness(coords, e_modulus, nu)
        dofs = np.array([3 * n + c for n in tet for c in range(3)])
        k[np.ix_(dofs, dofs)] += ke

    f = np.zeros(n_dof)
    for dof, val in loads.items():
        f[dof] += val
    free = np.array([i for i in range(n_dof) if i not in fixed_dofs])
    u = np.zeros(n_dof)
    for dof, val in fixed_dofs.items():
        u[dof] = val
    f_red = f[free] - k[np.ix_(free, np.array(list(fixed_dofs)))] @ np.array(
        list(fixed_dofs.values())
    ) if fixed_dofs else f[free]
    u[free] = np.linalg.solve(k[np.ix_(free, free)], f_red)

    centre = np.array([0.25, 0.25, 0.25])
    stresses = np.zeros((len(tets), 6))
    for e, tet in enumerate(tets):
        b, _ = _b_matrix(nodes[tet], centre)
        dofs = np.array([3 * n + c for n in tet for c in range(3)])
        stresses[e] = d @ b @ u[dofs]
    return u.reshape(-1, 3), stresses


def t10_nodal_stresses(nodes, tets, displacements, e_modulus, nu) -> np.ndarray:
    """Per-element stress (Voigt) at each of the 10 element nodes, shape ``(M,10,6)``.

    The centroid stress from ``solve_elasticity_t10`` under-reads a surface peak (a
    stress concentration sits at a boundary node, not the interior centroid). Because
    the T10 strain is LINEAR over the element, sampling at the corner/edge nodes
    recovers the surface peak — this is the recovery the plate-hole Kt uses.
    """
    d = _elasticity_matrix(e_modulus, nu)
    u = np.asarray(displacements).reshape(-1)
    out = np.zeros((len(tets), 10, 6))
    for e, tet in enumerate(tets):
        dofs = np.array([3 * n + c for n in tet for c in range(3)])
        ue = u[dofs]
        for a, nat in enumerate(_NODE_NAT):
            b, _ = _b_matrix(nodes[tet], nat)
            out[e, a] = d @ b @ ue
    return out
