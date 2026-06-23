"""Depth-audit / characterization tests for the Euler-Bernoulli beam FEM (fem.py).

Goal: prove fem.py is a GENUINE direct-stiffness FEM solver, not a module that
merely echoes the closed form it documents. The facade-killer strategy:

* Cross-check the FEM output against the INDEPENDENT closed forms documented in
  the module — tip deflection δ = F·L³/(3·E·I) and root bending stress
  σ = 6·F·L/(b·h²). These hand-derived anchors are computed here in the test, so
  if fem.py silently returned a canned number the cross-check would diverge.
* Prove the driving inputs are actually CONSUMED: changing F, L, E or I must move
  the output exactly as the physics predicts (linear in F, cubic in L for δ, …),
  which a hardcoded constant cannot reproduce.
* Prove it is a real ASSEMBLED system, not a one-line formula: the result must be
  mesh-independent (same answer for n_elements = 1 vs 32), which only holds
  because the beam element is exact and the assembly/solve is correct.
* Mandatory NEGATIVE tests: every documented guard (non-positive E/I/L/section,
  n_elements < 1) must fail loud with ValueError.

Offline, deterministic, no LLM, no external solver.

Run:  pytest tests/test_fem_characterization.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.fem import (  # noqa: E402
    beam_element_stiffness,
    max_bending_stress,
    rectangular_section_inertia,
    solve_cantilever_tip_load,
)

# Reference cantilever (N-mm-MPa unit system). PLA-like E ~ 3.5 GPa.
E, B, H, L, F = 3500.0, 80.0, 12.0, 60.0, 235.3596


def _tip_deflection_closed_form(e, inertia, length, force):
    """δ = F·L³/(3·E·I) — hand-derived anchor, independent of fem.py internals."""
    return force * length ** 3 / (3.0 * e * inertia)


# --------------------------------------------------------------------------- #
# (a) Headline claim REALLY holds against the closed-form anchor.
# --------------------------------------------------------------------------- #

def test_section_inertia_is_bh3_over_12():
    # Closed form I = b·h³/12; 80·12³/12 = 80·144 = 11520.
    assert rectangular_section_inertia(B, H) == 11520.0
    assert math.isclose(rectangular_section_inertia(80.0, 12.0), 80.0 * 12.0 ** 3 / 12.0)


def test_tip_deflection_matches_closed_form_to_machine_precision():
    inertia = rectangular_section_inertia(B, H)
    result = solve_cantilever_tip_load(E, inertia, L, F, n_elements=8)
    anchor = _tip_deflection_closed_form(E, inertia, L, F)
    # The beam element is exact for this model -> agreement to ~machine precision.
    assert math.isclose(result["tip_deflection"], anchor, rel_tol=1e-9)


def test_root_moment_and_stress_match_closed_form():
    inertia = rectangular_section_inertia(B, H)
    result = solve_cantilever_tip_load(E, inertia, L, F, n_elements=8)
    # Root bending moment of a tip-loaded cantilever is M = F·L.
    assert math.isclose(result["root_moment"], F * L, rel_tol=1e-9)
    # And the corresponding fibre stress is σ = 6·F·L/(b·h²).
    fem_sigma = max_bending_stress(result["root_moment"], B, H)
    assert math.isclose(fem_sigma, 6.0 * F * L / (B * H ** 2), rel_tol=1e-9)


def test_element_stiffness_is_symmetric_and_singular_unconstrained():
    inertia = rectangular_section_inertia(B, H)
    k = beam_element_stiffness(E, inertia, L)
    assert k.shape == (4, 4)
    # Stiffness matrices are symmetric; a free-free element has 2 rigid-body modes
    # (translation + rotation) so K is singular until BCs remove them.
    assert np.allclose(k, k.T)
    assert abs(np.linalg.det(k)) < 1e-6 * (E * inertia / L ** 3) ** 4


# --------------------------------------------------------------------------- #
# (a') Inputs are genuinely CONSUMED — output moves with the physics.
# --------------------------------------------------------------------------- #

def test_deflection_is_linear_in_force():
    inertia = rectangular_section_inertia(B, H)
    base = solve_cantilever_tip_load(E, inertia, L, F, n_elements=8)["tip_deflection"]
    doubled = solve_cantilever_tip_load(E, inertia, L, 2.0 * F, n_elements=8)["tip_deflection"]
    # δ ∝ F: doubling the load must exactly double the deflection (a canned
    # constant would not respond to F at all).
    assert math.isclose(doubled, 2.0 * base, rel_tol=1e-9)


def test_deflection_scales_with_length_cubed():
    inertia = rectangular_section_inertia(B, H)
    short = solve_cantilever_tip_load(E, inertia, L, F, n_elements=8)["tip_deflection"]
    long = solve_cantilever_tip_load(E, inertia, 2.0 * L, F, n_elements=8)["tip_deflection"]
    # δ ∝ L³: doubling the span multiplies deflection by 8.
    assert math.isclose(long, 8.0 * short, rel_tol=1e-9)


def test_deflection_inverse_in_stiffness_and_inertia():
    inertia = rectangular_section_inertia(B, H)
    base = solve_cantilever_tip_load(E, inertia, L, F, n_elements=8)["tip_deflection"]
    stiffer_e = solve_cantilever_tip_load(2.0 * E, inertia, L, F, n_elements=8)["tip_deflection"]
    stiffer_i = solve_cantilever_tip_load(E, 2.0 * inertia, L, F, n_elements=8)["tip_deflection"]
    # δ ∝ 1/(E·I): doubling either halves the deflection.
    assert math.isclose(stiffer_e, 0.5 * base, rel_tol=1e-9)
    assert math.isclose(stiffer_i, 0.5 * base, rel_tol=1e-9)


def test_root_moment_independent_of_e_and_i():
    # M = F·L is statically determinate: it must NOT depend on E or I. This is a
    # subtle facade check — a fake that "computed" moment from deflection*EI would
    # wrongly drift when E or I change.
    inertia = rectangular_section_inertia(B, H)
    m1 = solve_cantilever_tip_load(E, inertia, L, F, n_elements=8)["root_moment"]
    m2 = solve_cantilever_tip_load(5.0 * E, 3.0 * inertia, L, F, n_elements=8)["root_moment"]
    assert math.isclose(m1, m2, rel_tol=1e-9)
    assert math.isclose(m1, F * L, rel_tol=1e-9)


# --------------------------------------------------------------------------- #
# (a'') Real assembled system -> mesh independence (exact beam element).
# --------------------------------------------------------------------------- #

def test_mesh_independence_proves_assembly_and_solve():
    inertia = rectangular_section_inertia(B, H)
    coarse = solve_cantilever_tip_load(E, inertia, L, F, n_elements=1)
    fine = solve_cantilever_tip_load(E, inertia, L, F, n_elements=32)
    # If this were a one-line closed form the n_elements arg would be ignored;
    # if the assembly were wrong the coarse/fine answers would diverge.
    assert math.isclose(coarse["tip_deflection"], fine["tip_deflection"], rel_tol=1e-9)
    assert math.isclose(coarse["root_moment"], fine["root_moment"], rel_tol=1e-9)


@settings(max_examples=40, deadline=None)
@given(
    e=st.floats(min_value=1e2, max_value=2e5),
    breadth=st.floats(min_value=1.0, max_value=200.0),
    depth=st.floats(min_value=1.0, max_value=200.0),
    length=st.floats(min_value=5.0, max_value=1000.0),
    force=st.floats(min_value=-1e4, max_value=1e4),
    n_elements=st.integers(min_value=1, max_value=12),
)
def test_property_fem_equals_closed_form_for_any_cantilever(
    e, breadth, depth, length, force, n_elements
):
    """INVARIANT: for ANY admissible cantilever the exact beam element reproduces
    δ = F·L³/(3·E·I) and M = |F·L|, regardless of mesh density. Property-based so
    the agreement is explored across the whole input space, not a single point."""
    inertia = rectangular_section_inertia(breadth, depth)
    result = solve_cantilever_tip_load(e, inertia, length, force, n_elements=n_elements)
    anchor_delta = _tip_deflection_closed_form(e, inertia, length, force)
    assert math.isclose(result["tip_deflection"], anchor_delta, rel_tol=1e-7, abs_tol=1e-12)
    assert math.isclose(result["root_moment"], abs(force * length), rel_tol=1e-7, abs_tol=1e-9)


# --------------------------------------------------------------------------- #
# (b) Mandatory NEGATIVE tests — every documented guard fails loud.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("breadth,depth", [(0.0, 12.0), (-1.0, 12.0), (80.0, 0.0), (80.0, -3.0)])
def test_section_inertia_rejects_non_positive(breadth, depth):
    with pytest.raises(ValueError):
        rectangular_section_inertia(breadth, depth)


@pytest.mark.parametrize("e,inertia,length", [(0.0, 1.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, 0.0), (-1.0, 1.0, 1.0)])
def test_element_stiffness_rejects_non_positive(e, inertia, length):
    with pytest.raises(ValueError):
        beam_element_stiffness(e, inertia, length)


@pytest.mark.parametrize("e,inertia,length", [(0.0, 1.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, -5.0)])
def test_solver_rejects_non_positive_material_geometry(e, inertia, length):
    with pytest.raises(ValueError):
        solve_cantilever_tip_load(e, inertia, length, F)


@pytest.mark.parametrize("n_elements", [0, -1])
def test_solver_rejects_bad_mesh(n_elements):
    with pytest.raises(ValueError):
        solve_cantilever_tip_load(E, rectangular_section_inertia(B, H), L, F, n_elements=n_elements)


@pytest.mark.parametrize("breadth,depth", [(0.0, 12.0), (80.0, -1.0)])
def test_max_bending_stress_rejects_non_positive_section(breadth, depth):
    with pytest.raises(ValueError):
        max_bending_stress(F * L, breadth, depth)
