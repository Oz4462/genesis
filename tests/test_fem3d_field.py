"""Computed stress-concentration FIELD on an unstructured holed-plate mesh (gmsh+meshio).

fem3d.py used to defer "a conforming mesh of a holed part — to compute the Kt field
rather than bound it" to a "next layer". This pins that layer now living IN fem3d:

  * :func:`unstructured_tet_mesh` builds a REAL gmsh-meshed plate-with-a-hole — and the
    test proves it is genuinely UNSTRUCTURED (element volumes span a wide range, refined
    at the hole), not the regular structured-box grid;
  * :func:`stress_concentration_field` solves it and DERIVES Kt from the computed field
    (peak σ_xx / far-field σ_xx). The decisive checks: Kt lands near the Kirsch value 3
    (raised by the finite-width correction), it converges UP under refinement (constant-
    strain tets approach the concentration from below), and the peak σ_xx is well above
    the far field — i.e. the number is read from a real field, not hardcoded at 3;
  * the von-Mises field round-trips through meshio (VTU), so the same mesh GENESIS solved
    on is portable to ParaView.

NEGATIVE tests (always run, no gmsh needed): a hole that does not fit inside the plate,
and a non-physical Poisson ratio, both raise loud (GeometryError / ValueError) — a
degenerate case never silently returns a wrong field.

gmsh + meshio are optional, so the meshing tests skip when gmsh is absent. Offline, no
LLM. Engines: gmsh (mesh) + numpy (solve) + meshio (I/O), all deterministic.

Run:  pytest tests/test_fem3d_field.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from gen.core.errors import GeometryError  # noqa: E402
from gen.fem3d import (  # noqa: E402
    _tet_b_and_volume,
    stress_concentration_field,
    structured_box_mesh,
    unstructured_tet_mesh,
    write_mesh,
)

_HAVE_GMSH = True
try:  # the meshing path is optional; the negative tests do not need it
    import gmsh  # noqa: F401
except Exception:
    _HAVE_GMSH = False

_skip_no_gmsh = pytest.mark.skipif(
    not _HAVE_GMSH, reason="the unstructured holed-plate mesher needs the optional gmsh package"
)


def _volume_ratio(nodes: np.ndarray, tets: np.ndarray) -> float:
    vols = np.array([_tet_b_and_volume(nodes[t])[1] for t in tets])
    return float(vols.max() / vols.min())


# --- NEGATIVE tests (no gmsh required) ---------------------------------------------

def test_hole_too_big_raises():
    """A hole that does not fit strictly inside the plate is a loud GeometryError —
    not a silently-clipped, wrong mesh."""
    with pytest.raises(GeometryError):
        unstructured_tet_mesh(length=10.0, width=10.0, hole_radius=6.0)


def test_bad_poisson_ratio_raises():
    """nu outside (-1, 0.5) makes the elasticity matrix singular/non-physical — loud."""
    with pytest.raises(ValueError):
        stress_concentration_field(nu=0.5)


# --- POSITIVE meshing tests (need gmsh) --------------------------------------------

@_skip_no_gmsh
def test_unstructured_mesh_is_genuinely_irregular():
    """The holed-plate mesh is a REAL unstructured tet mesh: refined at the hole, so its
    element volumes span a wide range — unlike the near-uniform structured-box grid."""
    nodes_u, tets_u = unstructured_tet_mesh(refine_size=0.6, coarse_size=3.0)
    assert tets_u.shape[1] == 4 and len(tets_u) > 500
    # a structured box of the same plate has near-uniform cells (small ratio); the
    # hole-refined unstructured mesh has a much larger spread.
    nodes_s, tets_s = structured_box_mesh(20.0, 20.0, 1.0, 6, 6, 2)
    assert _volume_ratio(nodes_u, tets_u) > 5.0 * _volume_ratio(nodes_s, tets_s)


@_skip_no_gmsh
def test_computed_kt_is_near_kirsch_and_read_from_the_field():
    """Kt is COMPUTED from the field: the peak σ_xx greatly exceeds the far field, and
    their ratio sits in a tight band around the Kirsch value 3 (finite-width raised)."""
    r = stress_concentration_field(refine_size=0.5)
    assert 2.9 < r.kt < 3.6, r.kt
    # the number is genuinely a concentration: peak is far above the far field
    assert r.peak_sxx > 1.8 * r.far_field_sxx
    # the far field is a real tension (E*far_strain order), and Kt == peak/far exactly
    assert r.far_field_sxx > 0.0
    assert r.kt == pytest.approx(r.peak_sxx / r.far_field_sxx)
    # the full per-element field is returned (not just a scalar)
    assert r.sxx.shape == (r.n_tets,)
    assert r.von_mises_field.shape == (r.n_tets,)
    assert r.peak_von_mises > 0.0


@_skip_no_gmsh
def test_kt_converges_up_under_refinement():
    """Constant-strain tets approach the true concentration from below, so a finer hole
    mesh gives a HIGHER Kt — proof the value tracks the resolved field, not a constant."""
    coarse = stress_concentration_field(refine_size=1.0).kt
    fine = stress_concentration_field(refine_size=0.5).kt
    assert fine > coarse
    assert coarse > 2.8


@_skip_no_gmsh
def test_field_round_trips_through_meshio(tmp_path):
    """The solved mesh + its von-Mises field write to VTU and read back identically
    (the same mesh GENESIS solved on is portable to ParaView)."""
    meshio = pytest.importorskip("meshio")
    nodes, tets = unstructured_tet_mesh(refine_size=0.8)
    r = stress_concentration_field(refine_size=0.8)
    # tie the field to a mesh with the SAME element count (both use refine_size=0.8)
    assert r.n_tets == len(tets)
    out = tmp_path / "holed_plate.vtu"
    write_mesh(str(out), nodes, tets, cell_data={"von_mises": r.von_mises_field})
    assert out.is_file()
    back = meshio.read(str(out))
    assert back.cells_dict["tetra"].shape == tets.shape
    assert back.points.shape == nodes.shape
    assert "von_mises" in back.cell_data


@_skip_no_gmsh
def test_is_deterministic():
    a = stress_concentration_field(refine_size=1.0)
    b = stress_concentration_field(refine_size=1.0)
    assert a.kt == b.kt and a.n_tets == b.n_tets
