"""Self-contained beam FEM (δ structural engine) verified against the closed form.

The direct-stiffness Euler-Bernoulli beam solver (fem.py, pure numpy, no external
solver) must reproduce the analytical cantilever to machine precision — the beam
element is exact for this model. The decisive test cross-checks the FEM against
BOTH the closed form AND the independent δ-2 analytical stress used in the
capstone: two different methods agreeing is defense in depth.

Offline, no LLM, no external engine.

Run:  pytest tests/test_fem.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.fem import (  # noqa: E402
    beam_element_stiffness,
    max_bending_stress,
    rectangular_section_inertia,
    solve_cantilever_tip_load,
)
from gen.structural import cantilever_bending_stress_formula  # noqa: E402
from gen.verification.derivation import evaluate_formula  # noqa: E402

# capstone bracket parameters (N-mm-MPa), E for PLA ~ 3.5 GPa
E, B, H, L, F = 3500.0, 80.0, 12.0, 60.0, 235.3596


def test_section_inertia():
    assert rectangular_section_inertia(80.0, 12.0) == 11520.0     # b*h^3/12


def test_element_stiffness_is_symmetric():
    k = beam_element_stiffness(E, rectangular_section_inertia(B, H), L)
    assert k.shape == (4, 4)
    assert (k == k.T).all()


def test_fem_matches_closed_form_cantilever():
    I = rectangular_section_inertia(B, H)
    r = solve_cantilever_tip_load(E, I, L, F, n_elements=8)
    # tip deflection delta = F L^3 / (3 E I)
    assert math.isclose(r["tip_deflection"], F * L ** 3 / (3 * E * I), rel_tol=1e-9)
    # root bending moment M = F L
    assert math.isclose(r["root_moment"], F * L, rel_tol=1e-9)


def test_fem_is_mesh_independent():
    I = rectangular_section_inertia(B, H)
    coarse = solve_cantilever_tip_load(E, I, L, F, n_elements=1)
    fine = solve_cantilever_tip_load(E, I, L, F, n_elements=64)
    assert math.isclose(coarse["tip_deflection"], fine["tip_deflection"], rel_tol=1e-9)
    assert math.isclose(coarse["root_moment"], fine["root_moment"], rel_tol=1e-9)


def test_fem_stress_agrees_with_delta2_analytical():
    # the FEM root stress must equal the closed-form 6FL/(b h^2) AND the exact
    # value the delta-2 statics layer computes from structural.py's formula.
    I = rectangular_section_inertia(B, H)
    r = solve_cantilever_tip_load(E, I, L, F, n_elements=8)
    fem_sigma = max_bending_stress(r["root_moment"], B, H)

    closed_form = 6 * F * L / (B * H ** 2)
    analytical = evaluate_formula(
        cantilever_bending_stress_formula("q_force", "q_w", "q_h", "q_t"),
        {"q_force": F, "q_w": L, "q_h": B, "q_t": H},
    )
    assert math.isclose(fem_sigma, closed_form, rel_tol=1e-9)
    assert math.isclose(fem_sigma, analytical, rel_tol=1e-9)


def test_fem_confirms_capstone_nominal_stress():
    from gen.demo import capstone_state
    q = {x.id: x for x in capstone_state().specification.quantities}
    I = rectangular_section_inertia(q["q_h"].value, q["q_t"].value)
    r = solve_cantilever_tip_load(E, I, q["q_w"].value, q["q_force"].value, n_elements=8)
    fem_sigma = max_bending_stress(r["root_moment"], q["q_h"].value, q["q_t"].value)
    assert math.isclose(fem_sigma, q["q_sigma_nom"].value, rel_tol=1e-9)
