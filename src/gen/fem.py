"""Self-contained Euler-Bernoulli beam FEM (the δ structural engine, no binary).

The δ-2 statics layer answers the cantilever with a closed-form formula. The real
generalisation is the finite element method: assemble element stiffness matrices,
apply boundary conditions and loads, solve K·u = F. This module is a genuine FEM
solver — the direct stiffness method for 2-node Euler-Bernoulli beam elements —
implemented in pure numpy, so it needs NO external solver (CalculiX/FreeCAD) and
runs fully offline and deterministically.

It earns its place by being VERIFIABLE: for a tip-loaded cantilever the beam
element is exact, so the FEM result must equal the closed form to machine
precision — tip deflection δ = F·L³/(3·E·I) and root bending stress
σ = M·c/I = 6·F·L/(b·h²). The test cross-checks the FEM against BOTH the closed
form and the δ-2 analytical stress (`structural.py`): two independent methods
agreeing is defense in depth against a coding error in either.

Consistent N-mm-MPa unit system: E in MPa, I in mm⁴, L in mm, F in N → deflection
in mm, moment in N·mm, stress in MPa.

Honest boundary: this is 1-D Euler-Bernoulli beam theory (the same model class as
the closed form), now by the matrix method — it generalises to multi-segment /
multi-load beams the single formula cannot do, but it is NOT a 3-D continuum FEM
(no stress concentration field, no plates/shells). That remains an external-solver
layer under the same proof standard.
"""

from __future__ import annotations

import numpy as np


def rectangular_section_inertia(breadth: float, depth: float) -> float:
    """Second moment of area of a rectangle about its neutral axis: ``b·h³/12``."""
    return breadth * depth ** 3 / 12.0


def beam_element_stiffness(e_modulus: float, inertia: float, length: float) -> np.ndarray:
    """4×4 stiffness matrix of a 2-node Euler-Bernoulli beam element.

    DOF order per node is (transverse deflection w, rotation θ); the element has
    DOF [w1, θ1, w2, θ2]. Standard Hermitian-cubic beam element (e.g. Cook,
    *Concepts and Applications of Finite Element Analysis*)."""
    L = float(length)
    c = e_modulus * inertia / L ** 3
    return c * np.array([
        [12.0, 6.0 * L, -12.0, 6.0 * L],
        [6.0 * L, 4.0 * L ** 2, -6.0 * L, 2.0 * L ** 2],
        [-12.0, -6.0 * L, 12.0, -6.0 * L],
        [6.0 * L, 2.0 * L ** 2, -6.0 * L, 4.0 * L ** 2],
    ])


def solve_cantilever_tip_load(
    e_modulus: float,
    inertia: float,
    length: float,
    tip_force: float,
    n_elements: int = 8,
) -> dict[str, float]:
    """Solve a cantilever (fixed at x=0, free at x=L) under a transverse tip load
    by the direct stiffness method.

    Returns ``{"tip_deflection", "root_moment", "max_moment"}`` (deflection in mm,
    moments in N·mm). Deterministic; the beam element makes this exact for the
    Euler-Bernoulli model regardless of ``n_elements``.

    Raises ValueError on non-finite inputs (NaN/Inf would propagate silently to a
    NaN tip deflection, which passes every comparison guard as False) and on
    non-positive E, I or L (a zero/negative stiffness is unphysical).
    """
    for name, val in (
        ("e_modulus", e_modulus),
        ("inertia", inertia),
        ("length", length),
        ("tip_force", tip_force),
    ):
        if not np.isfinite(val):
            raise ValueError(f"{name} must be finite, got {val!r}")
    for name, val in (("e_modulus", e_modulus), ("inertia", inertia), ("length", length)):
        if val <= 0.0:
            raise ValueError(f"{name} must be positive, got {val!r}")
    n_nodes = n_elements + 1
    n_dof = 2 * n_nodes
    le = float(length) / n_elements
    k_glob = np.zeros((n_dof, n_dof))
    ke = beam_element_stiffness(e_modulus, inertia, le)
    for e in range(n_elements):
        dofs = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        for i in range(4):
            for j in range(4):
                k_glob[dofs[i], dofs[j]] += ke[i, j]

    f = np.zeros(n_dof)
    f[2 * (n_nodes - 1)] = float(tip_force)        # transverse load at the free tip

    # cantilever BC: node 0 fully fixed (w0 = θ0 = 0) -> drop DOF 0 and 1
    free = list(range(2, n_dof))
    k_ff = k_glob[np.ix_(free, free)]
    u_free = np.linalg.solve(k_ff, f[free])
    u = np.zeros(n_dof)
    u[free] = u_free

    tip_deflection = float(u[2 * (n_nodes - 1)])
    # element-1 end moments recover the bending moment; the root (element 0, node 0)
    # carries the maximum for a tip load. M = EI * (curvature); from the element
    # equation the nodal "forces" k_e · u_e give shear/moment — root moment is the
    # reaction moment at the fixed node.
    u_e0 = u[[0, 1, 2, 3]]
    root_forces = ke @ u_e0
    root_moment = float(root_forces[1])            # moment reaction at node 0
    return {
        "tip_deflection": tip_deflection,
        "root_moment": abs(root_moment),
        "max_moment": abs(root_moment),
    }


def max_bending_stress(moment: float, breadth: float, depth: float) -> float:
    """σ = M·c/I with c = h/2, I = b·h³/12 ⟹ σ = 6·M/(b·h²) for a rectangle [MPa
    when M is in N·mm and lengths in mm]."""
    return 6.0 * abs(moment) / (breadth * depth ** 2)
