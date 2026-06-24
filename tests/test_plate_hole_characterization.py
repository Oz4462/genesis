"""Depth-audit (characterization) for ``plate_hole.py`` — FEM-computed Kt vs Kirsch.

This file is the *facade-detector* for the stress-concentration solver. The legacy
``test_plate_hole.py`` checks that the computed gross Kt lands in a band around 3 and
converges up under refinement. That alone does not rule out a hollow facade: a module
that simply *returned the Kirsch constant 3.0* would also "land in a band around 3".

So here we prove the field is genuinely SOLVED, not echoed:

  * the result dict carries the documented FEM observables
    ``{"kt", "far_field_sxx", "peak_sxx", "n_tets"}`` and ``kt == peak/far`` exactly
    (the reduction is arithmetic on solved stresses, not a literal);
  * ``kt`` is the finite-width value (~3.0–3.5), strictly ABOVE the canned Kirsch 3.0
    — the finite-width correction is present, which a constant could never produce;
  * ``kt`` CHANGES MEASURABLY with geometry: a larger hole (bigger d/W) yields a
    different, higher finite-width Kt — impossible for a canned constant;
  * the quadratic (T10) solver reaches a comparable converged Kt on a COARSER mesh
    (strictly fewer tets), proving the higher-order element does real work;
  * a Hypothesis property test pins the Kt *definition* (kt = peak σ_xx / far σ_xx)
    on a hand-built field with no gmsh — fast, exhaustive over the input space.

ALWAYS-RUN negative test: ``_require_gmsh`` must fail loud with the documented
``GeometryError`` when gmsh cannot be imported. We poison ``sys.modules['gmsh']`` so
the guard is exercised whether or not gmsh is actually installed — a gate without a
test does not exist.

Offline, no LLM, deterministic. Engines: gmsh (mesh) + numpy (solve).
Run:  pytest tests/test_plate_hole_characterization.py
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
from gen.plate_hole import (  # noqa: E402
    _read_kt,
    _require_gmsh,
    stress_concentration_plate_hole,
    stress_concentration_plate_hole_t10,
)

# The documented FEM observables every result dict must carry. If the module were a
# facade returning the bare Kirsch constant, these keys would not all be present and
# self-consistent.
RESULT_KEYS = {"kt", "far_field_sxx", "peak_sxx", "n_tets"}
KIRSCH_INFINITE = 3.0  # the conservative constant the FEM is meant to REPLACE


# --------------------------------------------------------------------------- #
# Deep numeric checks — require gmsh (the unstructured mesher).
# importorskip is at the TEST level (not the module top) so the always-run
# negative guard test below still executes when gmsh is absent.
# --------------------------------------------------------------------------- #


def test_result_carries_fem_observables_and_kt_is_computed():
    """The headline path returns the documented dict, kt == peak/far exactly, and
    kt is the finite-width value strictly ABOVE the canned Kirsch 3.0 — proving a
    solved field, not an echoed constant."""
    pytest.importorskip("gmsh", reason="computing the hole Kt needs the optional gmsh")
    r = stress_concentration_plate_hole(refine_size=0.5)

    assert set(r) == RESULT_KEYS, r
    assert r["n_tets"] > 0
    assert r["far_field_sxx"] > 0.0
    assert r["peak_sxx"] > r["far_field_sxx"]  # there IS a raiser at the hole

    # kt is arithmetic on the solved stresses, not a literal: it must equal the ratio.
    assert r["kt"] == pytest.approx(r["peak_sxx"] / r["far_field_sxx"], rel=1e-12)

    # Finite-width Kt sits in the documented band and STRICTLY exceeds Kirsch 3.0.
    assert 3.0 < r["kt"] < 3.5, r["kt"]
    assert r["kt"] != KIRSCH_INFINITE  # not the canned constant

    # The far field is the imposed gross stress E·(delta/L) = 210000·1e-3 = 210 MPa.
    assert 195.0 < r["far_field_sxx"] < 215.0, r["far_field_sxx"]


def test_kt_changes_with_geometry():
    """A facade returning a constant would give the SAME Kt for every geometry. The
    real FEM raises the finite-width Kt as the hole grows (d/W 0.2 -> 0.3), so the two
    solves must differ measurably — proving the hole_radius/width ratio drives the
    solved field, not a canned value."""
    pytest.importorskip("gmsh", reason="computing the hole Kt needs the optional gmsh")
    small_hole = stress_concentration_plate_hole(hole_radius=2.0, refine_size=0.5)
    large_hole = stress_concentration_plate_hole(hole_radius=3.0, refine_size=0.5)

    # Both are valid finite-width Kt values.
    assert 3.0 < small_hole["kt"] < 3.6
    assert 3.0 < large_hole["kt"] < 3.6
    # The larger hole (higher d/W) carries the higher finite-width correction.
    assert large_hole["kt"] > small_hole["kt"]
    # The change is real and well outside mesh noise (a constant would give 0).
    assert large_hole["kt"] - small_hole["kt"] > 0.01
    # Different geometry => a genuinely different mesh, not a reused canned result.
    assert large_hole["n_tets"] != small_hole["n_tets"]


def test_t10_reaches_comparable_kt_on_coarser_mesh():
    """The quadratic (T10) element captures the linear-strain concentration field, so
    it reaches a comparable converged Kt with FAR fewer tets than the linear element.
    If T10 were a facade aliasing the linear path it could not do this."""
    pytest.importorskip("gmsh", reason="computing the hole Kt needs the optional gmsh")
    linear = stress_concentration_plate_hole(refine_size=0.5)
    quadratic = stress_concentration_plate_hole_t10(refine_size=1.0)

    assert set(quadratic) == RESULT_KEYS, quadratic
    # Coarser mesh: strictly fewer elements than the fine linear solve.
    assert quadratic["n_tets"] < linear["n_tets"]
    # Yet the converged finite-width Kt is comparable (same physics, both ~3.0–3.5).
    assert 3.0 < quadratic["kt"] < 3.5, quadratic["kt"]
    assert abs(quadratic["kt"] - linear["kt"]) < 0.2


def test_is_deterministic_full_pipeline():
    """Reproducibility (core principle A5): the seeded mesh + numpy solve must give a
    byte-identical result dict across two runs."""
    pytest.importorskip("gmsh", reason="computing the hole Kt needs the optional gmsh")
    a = stress_concentration_plate_hole(refine_size=1.0)
    b = stress_concentration_plate_hole(refine_size=1.0)
    assert a == b


# --------------------------------------------------------------------------- #
# Property test — the Kt DEFINITION, no gmsh needed (pure reduction on a field).
# --------------------------------------------------------------------------- #


@settings(max_examples=60, deadline=None)
@given(
    far_val=st.floats(min_value=1.0, max_value=1.0e4),
    ratio=st.floats(min_value=1.05, max_value=10.0),
)
def test_read_kt_definition_property(far_val: float, ratio: float):
    """Invariant: ``_read_kt`` reduces a solved field to kt = peak σ_xx / far σ_xx.

    We hand-build a 2-element field (no gmsh): one element sits in the far region
    (centroid x > 0.8·L) carrying ``far_val``; one near-hole element carries the peak
    ``far_val·ratio`` (the global max). The reduction must recover exactly that ratio.
    A facade that ignored the field and returned 3.0 would fail this for every input.
    """
    length = 10.0
    peak_val = far_val * ratio

    # Element 0: far region — all four corner nodes at x = length (centroid x = length).
    # Element 1: near the hole — corner nodes near x = 0 (centroid well below 0.8·L).
    nodes = np.array(
        [
            [length, 0.0, 0.0],
            [length, 1.0, 0.0],
            [length, 0.0, 1.0],
            [length, 1.0, 1.0],
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    tets = np.array([[0, 1, 2, 3], [4, 5, 6, 7]])
    # Per-element stress rows (σ_xx in column 0). Element 0 = far, element 1 = peak.
    stresses = np.zeros((2, 6))
    stresses[0, 0] = far_val
    stresses[1, 0] = peak_val

    out = _read_kt(nodes, tets, stresses, length)

    assert out["far_field_sxx"] == pytest.approx(far_val, rel=1e-12)
    assert out["peak_sxx"] == pytest.approx(peak_val, rel=1e-12)
    assert out["kt"] == pytest.approx(ratio, rel=1e-9)
    assert out["n_tets"] == 2


# --------------------------------------------------------------------------- #
# ALWAYS-RUN negative test — the fail-loud guard. Runs whether or not gmsh is
# installed, by poisoning sys.modules so the lazy `import gmsh` raises ImportError.
# --------------------------------------------------------------------------- #


def test_require_gmsh_raises_geometry_error_when_absent(monkeypatch):
    """When gmsh cannot be imported, ``_require_gmsh`` must fail loud with the
    documented ``GeometryError`` (keine stillen Defaults) rather than silently
    falling back. Setting sys.modules['gmsh'] = None makes `import gmsh` raise
    ImportError, exercising the guard even on a machine where gmsh IS installed."""
    monkeypatch.setitem(sys.modules, "gmsh", None)

    with pytest.raises(GeometryError) as excinfo:
        _require_gmsh()

    msg = str(excinfo.value)
    # The documented, actionable message — names the missing package and the fallback.
    assert "gmsh" in msg
    assert "Kt=3" in msg  # points the caller at the conservative statics-layer bound


def test_require_gmsh_returns_module_when_present():
    """The positive half of the guard contract: when gmsh imports cleanly it returns
    the module object (so the meshers can use it)."""
    gmsh = pytest.importorskip("gmsh", reason="needs gmsh installed for the success path")
    assert _require_gmsh() is gmsh
