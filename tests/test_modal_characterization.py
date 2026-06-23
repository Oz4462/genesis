"""Depth-audit characterization tests for ``gen.modal`` (natural-frequency eigenproblem).

These tests are facade-detectors: each one would FAIL if the module were a hollow
stub returning canned numbers. They prove — mostly on a single hand-built,
non-degenerate tetrahedron (4 nodes, 1 tet) — that the headline outputs are
genuinely computed FROM the inputs:

  • the consistent mass matrix sums to the body mass ρ·V exactly and SCALES with
    density (doubling ρ doubles the mass) — a constant stub could not track that;
  • the free-free single tet returns exactly SIX ~zero rigid-body-mode frequencies,
    the structural signature only a real eigensolve produces;
  • ``resonance_check`` reports a ratio, ok-flag and margin that move with their
    inputs;
  • the documented guards fire loud (ValueError on non-positive excitation,
    GeometryError when every DOF is fixed).

Plus a property-based invariant (mass linear in density, mass-block == total_mass)
and a gmsh-guarded closed-form bar→c/(4L) cross-check.

Verdict: REAL — no source defect found; no edit to src/gen/modal.py.

Run:  pytest tests/test_modal_characterization.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from gen.core.errors import GeometryError  # noqa: E402
from gen.modal import (  # noqa: E402
    assemble_stiffness_mass,
    natural_frequencies,
    resonance_check,
    total_mass,
)

# steel, consistent SI units (m, kg, s, Pa -> Hz)
_E, _NU, _RHO = 210e9, 0.3, 7850.0


def _unit_tet():
    """The reference tetrahedron (0,0,0),(1,0,0),(0,1,0),(0,0,1): exact volume 1/6 m³,
    non-degenerate (unit determinant), so every expected number has a closed form."""
    nodes = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    )
    tets = np.array([[0, 1, 2, 3]])
    return nodes, tets


# --- (1) consistent mass: equals ρ·V, equals the assembled block, scales with ρ ----

def test_total_mass_equals_density_times_tet_volume_exactly():
    nodes, tets = _unit_tet()
    # reference tet volume is exactly 1/6, so the body mass is ρ/6 in closed form
    assert np.isclose(total_mass(nodes, tets, _RHO), _RHO / 6.0, rtol=1e-12)


def test_consistent_mass_block_sums_to_body_mass():
    nodes, tets = _unit_tet()
    _, m = assemble_stiffness_mass(nodes, tets, _E, _NU, _RHO)
    body = _RHO / 6.0
    # one translational block (every 3rd DOF) of the consistent mass matrix sums to ρV
    assert np.isclose(m[0::3, 0::3].sum(), body, rtol=1e-12)
    assert np.isclose(m[1::3, 1::3].sum(), body, rtol=1e-12)
    assert np.isclose(total_mass(nodes, tets, _RHO), m[0::3, 0::3].sum(), rtol=1e-12)


def test_mass_doubles_when_density_doubles():
    # a canned stub independent of its input could not track this linear scaling
    nodes, tets = _unit_tet()
    single = total_mass(nodes, tets, _RHO)
    doubled = total_mass(nodes, tets, 2.0 * _RHO)
    assert np.isclose(doubled, 2.0 * single, rtol=1e-12)

    _, m1 = assemble_stiffness_mass(nodes, tets, _E, _NU, _RHO)
    _, m2 = assemble_stiffness_mass(nodes, tets, _E, _NU, 2.0 * _RHO)
    assert np.isclose(m2[0::3, 0::3].sum(), 2.0 * m1[0::3, 0::3].sum(), rtol=1e-12)


# --- (2) free-free single tet: exactly six ~zero rigid-body modes ------------------

def test_free_free_single_tet_has_six_rigid_body_modes():
    nodes, tets = _unit_tet()
    # 12 DOFs -> 12 modes; the first six must be the rigid-body zeros (3 translations
    # + 3 rotations), then the first genuine deformation mode is clearly positive.
    f = natural_frequencies(nodes, tets, _E, _NU, _RHO, n_modes=12)
    assert f.size == 12
    first_deformation = f[6]
    assert first_deformation > 1.0  # a real, large deformation frequency (kHz range)
    # each rigid-body frequency is negligible RELATIVE to the first deformation mode;
    # a hollow facade returning a constant array could not separate them this cleanly.
    assert np.all(f[:6] < 1e-6 * first_deformation)
    assert np.sum(f < 1e-6 * first_deformation) == 6


# --- (3) resonance_check: ratio / ok-flag / margin all move with the inputs --------

def test_resonance_check_ratio_and_margin_track_inputs():
    clear = resonance_check(300.0, 100.0)  # 3x above forcing -> safely separated
    assert clear["ok"] is True
    assert np.isclose(clear["ratio"], 3.0)
    # margin_hz == first_natural_hz - factor * excitation_hz == 300 - 2*100 == 100
    assert np.isclose(clear["margin_hz"], 300.0 - 2.0 * 100.0)
    assert clear["margin_hz"] > 0.0


def test_resonance_check_ok_flips_near_resonance():
    near = resonance_check(120.0, 100.0)  # only 1.2x above forcing -> too close
    assert near["ok"] is False
    assert np.isclose(near["ratio"], 1.2)
    assert near["margin_hz"] < 0.0  # 120 - 2*100 == -80


def test_resonance_check_ok_flips_with_separation_factor():
    # the SAME frequencies flip ok purely by changing the required separation factor,
    # proving min_separation_factor is genuinely consumed.
    lenient = resonance_check(250.0, 100.0, min_separation_factor=2.0)  # 2.5 >= 2.0
    strict = resonance_check(250.0, 100.0, min_separation_factor=3.0)  # 2.5 < 3.0
    assert lenient["ok"] is True
    assert strict["ok"] is False
    assert np.isclose(strict["margin_hz"], 250.0 - 3.0 * 100.0)


# --- (4) documented guards fail loud ----------------------------------------------

def test_resonance_check_rejects_nonpositive_excitation():
    with pytest.raises(ValueError):
        resonance_check(100.0, 0.0)
    with pytest.raises(ValueError):
        resonance_check(100.0, -5.0)


def test_natural_frequencies_raises_when_every_dof_fixed():
    nodes, tets = _unit_tet()
    all_dofs = set(range(3 * len(nodes)))  # 12 DOFs, all clamped -> nothing free
    with pytest.raises(GeometryError):
        natural_frequencies(nodes, tets, _E, _NU, _RHO, fixed_dofs=all_dofs)


# --- property-based invariant: mass is linear in density and equals the block ------

@given(
    density=st.floats(min_value=1.0, max_value=1e5),
    scale=st.floats(min_value=0.1, max_value=10.0),
)
@settings(max_examples=50)
def test_mass_invariant_linear_and_block_consistent(density: float, scale: float):
    # uniformly scaling the reference tet by `scale` scales its volume by scale**3,
    # so total_mass must equal density * (scale**3 / 6); and the assembled mass block
    # must agree with total_mass for every (density, geometry) — a real computation,
    # not a stored constant.
    nodes, tets = _unit_tet()
    nodes = nodes * scale
    expected = density * (scale ** 3) / 6.0
    tm = total_mass(nodes, tets, density)
    assert np.isclose(tm, expected, rtol=1e-9)
    _, m = assemble_stiffness_mass(nodes, tets, _E, _NU, density)
    assert np.isclose(m[0::3, 0::3].sum(), tm, rtol=1e-9)


# --- gmsh-guarded closed-form bar cross-check (skips cleanly without gmsh) ---------

def test_longitudinal_bar_frequency_matches_closed_form_quadratic():
    """A clamped-free bar's first longitudinal mode converges to f₁ = c/(4L),
    c = √(E/ρ). The T10 mesher needs gmsh, so skip cleanly when it is absent — the
    gate stays green without the optional dependency."""
    pytest.importorskip("gmsh", reason="the T10 mesher needs the optional gmsh package")
    from gen.fem3d_quadratic import box_mesh_t10

    length, b, h = 0.1, 0.01, 0.01
    c = np.sqrt(_E / _RHO)
    f_analytic = c / (4.0 * length)
    nodes, tets = box_mesh_t10(length, b, h, h)
    # clamp x=0 fully, lock y,z everywhere else -> a pure 1-D longitudinal bar
    fixed: set[int] = set()
    for i, (x, _y, _z) in enumerate(nodes):
        if abs(x) < 1e-12:
            fixed.update({3 * i, 3 * i + 1, 3 * i + 2})
        else:
            fixed.update({3 * i + 1, 3 * i + 2})
    f1 = natural_frequencies(
        nodes, tets, _E, 0.0, _RHO, fixed_dofs=fixed, n_modes=1
    )[0]
    assert abs(f1 - f_analytic) / f_analytic < 0.05
