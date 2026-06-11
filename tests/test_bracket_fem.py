"""3-D FEM of the actual capstone bracket in bending vs the conservative hand-calc.

bracket_fem.py meshes the real bracket (a box with a through-hole), loads it as a
cantilever, and reads the real peak stress with the 3-D continuum solver. It checks
that the conservative statics bound (Kt=3, sigma_peak = 22 MPa) really was
conservative: the full field's peak (~6-7 MPa) is far below the bound and below
strength, and the hole - sitting at mid-span where the moment is halved - is not
even the critical location. gmsh is optional, so this test skips when absent.

The FEM is computed ONCE (coarse mesh, fast) and reused across the assertions.

Offline, no LLM. Engines: gmsh (mesh) + numpy (solve).

Run:  pytest tests/test_bracket_fem.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

pytest.importorskip("gmsh", reason="the bracket FEM needs the optional gmsh package")

from gen.bracket_fem import bracket_bending_fem  # noqa: E402

_RESULT = bracket_bending_fem(refine_size=2.0)   # one coarse run, reused below


def test_fem_confirms_the_conservative_bound_with_margin():
    # the conservative statics bound was Kt * sigma_nom = 22.07 MPa; strength = 50 MPa
    assert _RESULT["peak_vm"] < 22.07    # the Kt=3 bound was conservative
    assert _RESULT["peak_vm"] < 50.0     # and the part is safe
    assert _RESULT["peak_vm"] > 3.0      # a sane non-trivial stress


def test_root_stress_brackets_the_analytic_nominal():
    # constant-strain tets under-predict, so the root surface stress sits below the
    # analytic sigma_nom = 6FL/(b h^2) = 7.355 MPa (and converges up with refinement)
    assert 4.5 < _RESULT["root_vm"] < 8.5


def test_mid_span_hole_is_not_the_critical_location():
    # the hole is at mid-span (half the root moment), so even with its concentration
    # it stays below the root stress - the conservative full-nominal Kt=3 assumption
    # was therefore conservative
    assert _RESULT["hole_vm"] < _RESULT["root_vm"]


def test_is_deterministic():
    again = bracket_bending_fem(refine_size=2.0)
    assert again == _RESULT
