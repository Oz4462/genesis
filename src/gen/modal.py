"""Modal analysis — natural frequencies of an elastic part (numpy, no solver dep).

The static FEM (fem3d.py) answers "does it hold the load?"; it cannot answer "does it
RESONATE?" — a structure forced near a natural frequency amplifies wildly and fails by
fatigue at a load far below its static strength. That failure mode is invisible to a
stress check. This module adds it: the consistent-mass eigenproblem K·φ = ω²·M·φ,
whose lowest roots are the natural frequencies. It reuses the exact stiffness of the
4-node tetrahedron (fem3d) and adds the only missing ingredient — the element MASS
matrix — then solves the generalized eigenproblem in pure numpy (Cholesky transform).

Verified, not asserted, on three levels:
  • EXACT: the consistent mass matrix sums to the body mass ρ·V to machine precision.
  • EXACT: a free-free body returns exactly SIX zero-frequency rigid-body modes (3
    translations + 3 rotations) — the structural signature the eigenproblem must show.
  • QUANTITATIVE: a bar's longitudinal natural frequency converges to the closed form
    f₁ = c/(4L), c = √(E/ρ), to well under a percent (the axial mode the linear tet
    captures accurately). The cantilever BENDING frequency converges toward the
    Euler-Bernoulli value from ABOVE — the linear tet is over-stiff in bending (the
    same constant-strain limitation §23 documents for stress), so it needs many
    elements there. The QUADRATIC tet (pass a `box_mesh_t10` order-2 mesh) fixes this:
    the same solver, dispatching on the 10-node element, hits the bending frequency to
    ~0.2 % on a coarse mesh where the linear tet is off by tens of percent.

Units must be a consistent SI set: E in Pa, density in kg/m³, lengths in m → natural
frequencies in Hz. Honest boundary: linear, undamped, small-displacement modal
analysis; the linear tet is over-stiff in bending (frequencies biased HIGH there, a
non-conservative bias — stated, not hidden — so refine or use quadratic elements
before trusting a bending mode).

Wiring (physics validators campaign): "resonance" validator in physics_validation; auto-selected via
physics_selection recipe "resonance" (trigger="vibration.excitation_frequency"). Invoked via
gate_delta_physics in pipeline.assess_specification. Used via gate/quantities in inventor/eval;
simulation/runner uses analytical placeholder (dispatch note to full modal/fem3d at runner:239).
Cross-check with fem3d/fem3d_quadratic.
"""

from __future__ import annotations

import numpy as np

from .core.errors import GeometryError
from .fem3d import _elasticity_matrix, _tet_b_and_volume
from .fem3d_quadratic import t10_mass, t10_stiffness


def _tet4_mass(coords: np.ndarray, density: float) -> np.ndarray:
    """12×12 consistent mass matrix of a 4-node tetrahedron.

    For a tetrahedron the consistent mass per coordinate direction is
    (ρV/20)·(1 + δ_ij) — a closed form (no quadrature) — replicated on each of the
    three translational DOFs. It sums to the element mass ρV exactly.
    """
    m = np.ones((4, 4))
    m[:, 1:] = coords
    vol = abs(np.linalg.det(m)) / 6.0
    scalar = (density * vol / 20.0) * (np.ones((4, 4)) + np.eye(4))
    mass = np.zeros((12, 12))
    for a in range(4):
        for b in range(4):
            for d in range(3):
                mass[3 * a + d, 3 * b + d] = scalar[a, b]
    return mass


def total_mass(nodes: np.ndarray, tets: np.ndarray, density: float) -> float:
    """Body mass ρ·ΣV (kg) — the sum of every tetrahedron volume times density. Equals
    the sum of one translational block of the assembled mass matrix exactly."""
    total = 0.0
    for tet in tets:
        m = np.ones((4, 4))
        m[:, 1:] = nodes[tet]
        total += abs(np.linalg.det(m)) / 6.0
    return density * total


def assemble_stiffness_mass(
    nodes: np.ndarray, tets: np.ndarray, e_modulus: float, nu: float, density: float
) -> tuple[np.ndarray, np.ndarray]:
    """Assemble the global stiffness K and consistent mass M (each 3N×3N) for a
    tetrahedral mesh. Dispatches on the element node count: 4-node (linear, constant
    strain — over-stiff in bending) or 10-node (quadratic, captures bending; pass a
    gmsh order-2 mesh from ``fem3d_quadratic.box_mesh_t10``). Deterministic."""
    ndof = 3 * len(nodes)
    d = _elasticity_matrix(e_modulus, nu)
    k = np.zeros((ndof, ndof))
    m = np.zeros((ndof, ndof))
    for tet in tets:
        coords = nodes[tet]
        if len(tet) == 4:
            b, vol = _tet_b_and_volume(coords)
            ke = vol * b.T @ d @ b
            me = _tet4_mass(coords, density)
        elif len(tet) == 10:
            ke = t10_stiffness(coords, e_modulus, nu)
            me = t10_mass(coords, density)
        else:
            raise GeometryError(
                f"unsupported element with {len(tet)} nodes (need 4 or 10)"
            )
        dofs = np.array([3 * n + c for n in tet for c in range(3)])
        k[np.ix_(dofs, dofs)] += ke
        m[np.ix_(dofs, dofs)] += me
    return k, m


def natural_frequencies(
    nodes: np.ndarray,
    tets: np.ndarray,
    e_modulus: float,
    nu: float,
    density: float,
    *,
    fixed_dofs: frozenset[int] | set[int] = frozenset(),
    n_modes: int = 6,
) -> np.ndarray:
    """The lowest `n_modes` natural frequencies (Hz, ascending) of the mesh.

    `fixed_dofs` are clamped global DOF indices (3·node + component); leave empty for a
    free-free body (whose first six frequencies are then the rigid-body zeros). Solves
    the generalized symmetric eigenproblem K·φ = ω²·M·φ on the free DOFs via a Cholesky
    transform (M is positive-definite), returning √(ω²)/2π. Deterministic.

    Raises GeometryError if there are no free DOFs.
    """
    k, m = assemble_stiffness_mass(nodes, tets, e_modulus, nu, density)
    ndof = k.shape[0]
    free = np.array([i for i in range(ndof) if i not in fixed_dofs])
    if free.size == 0:
        raise GeometryError("every DOF is fixed — there is nothing to vibrate")
    k_ff = k[np.ix_(free, free)]
    m_ff = m[np.ix_(free, free)]
    chol = np.linalg.cholesky(m_ff)
    # A = L^-1 K L^-T, symmetric; eig(A) = ω² of the generalized problem
    a = np.linalg.solve(chol, np.linalg.solve(chol, k_ff).T).T
    omega_sq = np.clip(np.sort(np.linalg.eigvalsh(a)), 0.0, None)
    freqs = np.sqrt(omega_sq) / (2.0 * np.pi)
    return freqs[: min(n_modes, freqs.size)]


def resonance_check(
    first_natural_hz: float,
    excitation_hz: float,
    *,
    min_separation_factor: float = 2.0,
) -> dict:
    """Resonance-avoidance check: is the first natural frequency clear of the forcing
    frequency by a safe margin?

    A mount/bracket is normally designed "stiff" — its first natural frequency kept at
    least `min_separation_factor`× above the highest forcing frequency, so the forcing
    sits on the flat, low-amplification part of the response. Returns
    ``{"ratio", "min_separation_factor", "ok", "margin_hz"}`` with ok = ratio ≥ factor.
    Deterministic. (Soft mounting — deliberately f₁ ≪ f_exc for isolation — is the
    other valid regime and is not what this check enforces.)
    """
    if excitation_hz <= 0.0:
        raise ValueError("excitation frequency must be positive")
    ratio = first_natural_hz / excitation_hz
    return {
        "ratio": ratio,
        "min_separation_factor": min_separation_factor,
        "ok": ratio >= min_separation_factor,
        "margin_hz": first_natural_hz - min_separation_factor * excitation_hz,
    }
