"""Computed hole stress concentration vs the Kirsch Kt=3 bound (gmsh + fem3d).

plate_hole.py closes the loop the 3-D solver was built for: it meshes the classic
plate-with-a-hole benchmark (gmsh), pulls it in tension, and reads the actual peak
stress at the hole edge - COMPUTING the stress concentration the statics layer only
bounds conservatively at Kt=3.

The decisive checks: the computed gross Kt sits in a tight band around 3 (the Kirsch
infinite-plate value, raised by the finite-width correction for d/W=0.2), and it
converges monotonically UP under mesh refinement (constant-strain tets approach the
true concentration from below). gmsh is optional, so this test skips when absent.

Offline, no LLM. Engines: gmsh (mesh) + numpy (solve), both deterministic.

Run:  pytest tests/test_plate_hole.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

pytest.importorskip("gmsh", reason="computing the hole Kt needs the optional gmsh package")

from gen.plate_hole import stress_concentration_plate_hole  # noqa: E402


def test_computed_kt_matches_kirsch_with_finite_width():
    r = stress_concentration_plate_hole(refine_size=0.5)
    # Kirsch infinite-plate Kt = 3.0; finite width (d/W = 0.2) raises it slightly.
    assert 2.9 < r["kt"] < 3.5, r["kt"]
    # the far-field stress is the imposed E*delta/L = 210 (gross), within a few %
    assert abs(r["far_field_sxx"] - 210.0) / 210.0 < 0.05


def test_kt_converges_up_under_refinement():
    coarse = stress_concentration_plate_hole(refine_size=1.0)["kt"]
    fine = stress_concentration_plate_hole(refine_size=0.5)["kt"]
    # constant-strain tets approach the true concentration from below
    assert fine > coarse
    assert coarse > 2.8                      # already near 3 even coarse


def test_is_deterministic():
    a = stress_concentration_plate_hole(refine_size=1.0)
    b = stress_concentration_plate_hole(refine_size=1.0)
    assert a == b
