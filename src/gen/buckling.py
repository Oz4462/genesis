"""Euler column buckling — the elastic-stability failure mode (numpy, no solver dep).

The statics layers check whether a member's stress stays below its strength; modal.py
checks resonance. Neither sees the third classic failure: a slender member under
COMPRESSION buckles — bows out sideways and collapses — at a load far below the one
that would yield it. A bracket strut, a long bolt in compression, a thin leg: each can
be perfectly safe on stress yet fail by elastic instability. This module adds it.

Two methods, cross-checked:
  • CLOSED FORM — Euler's critical load P_cr = π²·E·I / (K·L)², with K the
    effective-length factor of the end condition (pinned-pinned 1, fixed-free 2,
    fixed-fixed 0.5, fixed-pinned ≈0.699).
  • COMPUTED — a beam-element buckling eigenproblem (K_e·φ = P·K_g·φ) assembled from
    the Euler-Bernoulli elastic stiffness (fem.py) and the consistent geometric
    stiffness; its lowest eigenvalue is P_cr. It reuses the SAME beam element the
    deflection solver is verified on.

Verified, not asserted: the computed P_cr converges to the Euler closed form for ALL
four end conditions to well under a percent with a handful of elements (the Hermitian
beam element captures the buckling mode) — two independent methods agreeing is the
defense against an error in either.

The design check is honest about WHEN Euler applies: a stocky column (low slenderness
KL/r) crushes/yields before it can buckle, so the governing failure is the smaller of
the Euler load and the squash load σ_y·A — the check reports which mode governs rather
than blindly trusting Euler (which over-predicts for short columns).

Consistent N-mm-MPa units (as fem.py): E, σ_y in MPa, I in mm⁴, L in mm, A in mm² → P
in N. Honest boundary: linear elastic Euler buckling of a prismatic member, ideal
(no initial crookedness or load eccentricity, which lower the real capacity — so this
is an UPPER bound; a real design applies a safety factor / the Perry-Robertson or
Johnson reduction for imperfections and inelasticity).
"""

from __future__ import annotations

import numpy as np

from .core.errors import GeometryError
from .fem import beam_element_stiffness

# effective-length (K) factors for the four classic ideal end conditions
END_CONDITION_FACTORS: dict[str, float] = {
    "pinned-pinned": 1.0,
    "fixed-free": 2.0,
    "fixed-fixed": 0.5,
    "fixed-pinned": 0.699,
}


def beam_geometric_stiffness(length: float) -> np.ndarray:
    """4×4 consistent geometric stiffness of a 2-node Euler-Bernoulli beam element,
    per unit axial COMPRESSIVE load. DOF order [w1, θ1, w2, θ2] (matching
    `fem.beam_element_stiffness`). Standard form (e.g. Cook, *Concepts and
    Applications of Finite Element Analysis*; Przemieniecki)."""
    L = float(length)
    return (1.0 / (30.0 * L)) * np.array([
        [36.0, 3.0 * L, -36.0, 3.0 * L],
        [3.0 * L, 4.0 * L ** 2, -3.0 * L, -L ** 2],
        [-36.0, -3.0 * L, 36.0, -3.0 * L],
        [3.0 * L, -L ** 2, -3.0 * L, 4.0 * L ** 2],
    ])


def euler_critical_load(
    e_modulus: float, inertia: float, length: float, *, k_factor: float
) -> float:
    """Euler critical buckling load P_cr = π²·E·I / (K·L)² [N for MPa·mm⁴/mm²]."""
    return float(np.pi ** 2 * e_modulus * inertia / (k_factor * length) ** 2)


def _fixed_dofs(end_condition: str, n_nodes: int) -> set[int]:
    """Clamped global DOF (2·node + {0:w, 1:θ}) for the named end condition."""
    top_w, top_th = 2 * (n_nodes - 1), 2 * (n_nodes - 1) + 1
    if end_condition == "pinned-pinned":
        return {0, top_w}                       # transverse held at both ends
    if end_condition == "fixed-free":
        return {0, 1}                           # base clamped, top free
    if end_condition == "fixed-fixed":
        return {0, 1, top_w, top_th}
    if end_condition == "fixed-pinned":
        return {0, 1, top_w}
    raise GeometryError(
        f"unknown end condition {end_condition!r}; one of {sorted(END_CONDITION_FACTORS)}"
    )


def critical_buckling_load(
    e_modulus: float,
    inertia: float,
    length: float,
    *,
    end_condition: str = "pinned-pinned",
    n_elements: int = 8,
) -> float:
    """Lowest buckling load (N) of a prismatic column by the beam-element eigenproblem
    K_e·φ = P·K_g·φ.

    Solves the symmetric-definite pencil via a Cholesky transform of K_e (positive-
    definite once the end condition is applied) and returns the smallest positive
    eigenvalue P. Deterministic; converges to `euler_critical_load` as n_elements
    grows. Raises GeometryError for an unknown end condition.
    """
    n_nodes = n_elements + 1
    n_dof = 2 * n_nodes
    le = float(length) / n_elements
    ke = beam_element_stiffness(e_modulus, inertia, le)
    kge = beam_geometric_stiffness(le)
    k_e = np.zeros((n_dof, n_dof))
    k_g = np.zeros((n_dof, n_dof))
    for e in range(n_elements):
        dofs = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        for i in range(4):
            for j in range(4):
                k_e[dofs[i], dofs[j]] += ke[i, j]
                k_g[dofs[i], dofs[j]] += kge[i, j]

    fixed = _fixed_dofs(end_condition, n_nodes)
    free = np.array([i for i in range(n_dof) if i not in fixed])
    k_ef = k_e[np.ix_(free, free)]
    k_gf = k_g[np.ix_(free, free)]
    chol = np.linalg.cholesky(k_ef)
    # eigenvalues μ of (L⁻¹ K_g L⁻ᵀ) are 1/P; the largest positive μ → smallest P
    a = np.linalg.solve(chol, np.linalg.solve(chol, k_gf).T).T
    mu = np.linalg.eigvalsh(a)
    mu = mu[mu > 1e-12]
    if mu.size == 0:
        raise GeometryError("no positive buckling mode found (check the load/geometry)")
    return float(1.0 / mu.max())


def radius_of_gyration(inertia: float, area: float) -> float:
    """r = √(I/A) — the section property the slenderness ratio uses."""
    if area <= 0.0:
        raise ValueError("area must be positive")
    return float(np.sqrt(inertia / area))


def buckling_check(
    applied_load: float,
    e_modulus: float,
    inertia: float,
    length: float,
    area: float,
    *,
    end_condition: str = "pinned-pinned",
    yield_strength: float | None = None,
) -> dict:
    """Compression-member stability check.

    Computes the Euler critical load and, if `yield_strength` is given, the squash
    load σ_y·A; the GOVERNING failure is the smaller (a stocky column yields before it
    buckles — Euler over-predicts there). Returns ``{"p_euler", "squash_load",
    "governing_load", "governs", "slenderness", "transition_slenderness",
    "safety_factor", "ok"}``: governs is "buckling" or "yield"; safety_factor =
    governing_load / applied_load; ok = safety_factor ≥ 1. Deterministic.

    `applied_load` is the compressive load (N, positive). Raises ValueError on a
    non-positive load.
    """
    if applied_load <= 0.0:
        raise ValueError("applied compressive load must be positive")
    k = END_CONDITION_FACTORS.get(end_condition)
    if k is None:
        raise GeometryError(
            f"unknown end condition {end_condition!r}; one of {sorted(END_CONDITION_FACTORS)}"
        )
    p_euler = euler_critical_load(e_modulus, inertia, length, k_factor=k)
    r = radius_of_gyration(inertia, area)
    slenderness = k * length / r

    if yield_strength is not None:
        squash = yield_strength * area
        transition = float(np.pi * np.sqrt(e_modulus / yield_strength))  # λ where σ_cr=σ_y
        if p_euler <= squash:
            governing, governs = p_euler, "buckling"
        else:
            governing, governs = squash, "yield"
    else:
        squash = None
        transition = None
        governing, governs = p_euler, "buckling"

    return {
        "p_euler": p_euler,
        "squash_load": squash,
        "governing_load": governing,
        "governs": governs,
        "slenderness": slenderness,
        "transition_slenderness": transition,
        "safety_factor": governing / applied_load,
        "ok": governing >= applied_load,
    }
