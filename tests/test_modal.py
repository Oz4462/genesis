"""Modal analysis — natural frequencies: exact structural checks + a closed-form mode.

Three levels of evidence:
  • EXACT: the consistent mass matrix sums to the body mass ρ·V.
  • EXACT: a free-free body shows exactly six zero-frequency rigid-body modes.
  • QUANTITATIVE: a bar's longitudinal natural frequency converges to f₁ = c/(4L),
    c = √(E/ρ), to ~1%; the cantilever bending frequency converges toward the
    Euler-Bernoulli value from above (the linear tet is over-stiff in bending).

Plus the resonance-avoidance design check. Offline, no LLM, pure numpy (no mesher).

Run:  pytest tests/test_modal.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from gen.core.errors import GeometryError  # noqa: E402
from gen.fem3d import structured_box_mesh  # noqa: E402
from gen.modal import (  # noqa: E402
    assemble_stiffness_mass,
    natural_frequencies,
    resonance_check,
    total_mass,
)

# steel, consistent SI units (m, kg, s, Pa -> Hz)
_E, _NU, _RHO = 210e9, 0.3, 7850.0
_L, _B, _H = 0.1, 0.005, 0.005


# --- exact structural checks ---------------------------------------------------

def test_consistent_mass_sums_to_body_mass():
    nodes, tets = structured_box_mesh(_L, _B, _H, 6, 2, 2)
    _, m = assemble_stiffness_mass(nodes, tets, _E, _NU, _RHO)
    body = _RHO * _L * _B * _H
    assert np.isclose(m[0::3, 0::3].sum(), body, rtol=1e-12)     # one translational block
    assert np.isclose(total_mass(nodes, tets, _RHO), body, rtol=1e-12)


def test_free_free_body_has_six_rigid_body_modes():
    nodes, tets = structured_box_mesh(_L, _B, _H, 6, 2, 2)
    f = natural_frequencies(nodes, tets, _E, _NU, _RHO, n_modes=8)   # no constraints
    # 3 translations + 3 rotations at zero frequency, then a clearly positive mode
    assert np.sum(f[:8] < 1.0) == 6
    assert f[6] > 100.0


# --- closed-form longitudinal frequency ----------------------------------------

def _axial_fixed(nodes):
    """Clamp x=0 fully and lock y,z everywhere -> a pure 1-D longitudinal bar."""
    fixed: set[int] = set()
    for i, (x, y, z) in enumerate(nodes):
        if abs(x) < 1e-12:
            fixed.update({3 * i, 3 * i + 1, 3 * i + 2})
        else:
            fixed.update({3 * i + 1, 3 * i + 2})
    return fixed


def test_longitudinal_frequency_matches_closed_form_and_converges():
    c = np.sqrt(_E / _RHO)                       # wave speed (nu=0 -> modulus = E)
    f_analytic = c / (4.0 * _L)                  # fixed-free bar, first longitudinal mode
    errs = []
    for nx in (8, 16):
        nodes, tets = structured_box_mesh(_L, _B, _H, nx, 1, 1)
        f1 = natural_frequencies(nodes, tets, _E, 0.0, _RHO,
                                 fixed_dofs=_axial_fixed(nodes), n_modes=1)[0]
        errs.append(abs(f1 - f_analytic) / f_analytic)
    assert errs[-1] < 0.02                        # ~1% at nx=16
    assert errs[-1] < errs[0]                      # refining reduces the error


def test_cantilever_bending_converges_toward_euler_bernoulli_from_above():
    inertia = _B * _H ** 3 / 12.0
    area = _B * _H
    f_eb = (1.875104 ** 2 / (2 * np.pi)) * np.sqrt(_E * inertia / (_RHO * area * _L ** 4))
    f1s = []
    for nx in (6, 10, 16):
        nodes, tets = structured_box_mesh(_L, _B, _H, nx, 2, 2)
        fixed = set()
        for i, (x, y, z) in enumerate(nodes):
            if abs(x) < 1e-12:
                fixed.update({3 * i, 3 * i + 1, 3 * i + 2})
        f1s.append(natural_frequencies(nodes, tets, _E, _NU, _RHO,
                                       fixed_dofs=fixed, n_modes=1)[0])
    # the constant-strain tet is over-stiff in bending: frequency biased HIGH,
    # decreasing monotonically toward the Euler-Bernoulli value as the mesh refines.
    assert f1s[0] > f1s[1] > f1s[2] > f_eb
    assert (f1s[2] - f_eb) < (f1s[0] - f_eb)       # genuinely converging toward it


# --- the resonance design check ------------------------------------------------

def test_resonance_check_flags_proximity():
    near = resonance_check(120.0, 100.0)           # only 1.2x above forcing
    clear = resonance_check(300.0, 100.0)          # 3x above forcing
    assert not near["ok"] and near["margin_hz"] < 0.0
    assert clear["ok"] and clear["margin_hz"] > 0.0
    assert np.isclose(clear["ratio"], 3.0)


def test_resonance_check_rejects_nonpositive_excitation():
    with pytest.raises(ValueError):
        resonance_check(100.0, 0.0)


# --- guards & determinism ------------------------------------------------------

def test_fully_fixed_is_an_error():
    nodes, tets = structured_box_mesh(_L, _B, _H, 2, 1, 1)
    all_dofs = set(range(3 * len(nodes)))
    with pytest.raises(GeometryError):
        natural_frequencies(nodes, tets, _E, _NU, _RHO, fixed_dofs=all_dofs)


def test_is_deterministic():
    nodes, tets = structured_box_mesh(_L, _B, _H, 4, 2, 2)
    fixed = {3 * i + c for i, (x, y, z) in enumerate(nodes) if abs(x) < 1e-12 for c in range(3)}
    a = natural_frequencies(nodes, tets, _E, _NU, _RHO, fixed_dofs=fixed, n_modes=3)
    b = natural_frequencies(nodes, tets, _E, _NU, _RHO, fixed_dofs=fixed, n_modes=3)
    assert np.array_equal(a, b)
