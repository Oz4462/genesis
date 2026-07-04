"""Schritt-7-Batch-2-Härtungen (Review 2026-07-04): FEM-Schicht fem/fem3d/fem3d_quadratic/bracket_fem/plate_hole.

F1 (MED): Die FEM-Engines validierten Endlichkeit nicht — NaN/Inf in E, ν, inertia,
force propagierte still zu NaN-Ergebnissen (tip_deflection, peak_vm, kt, …). NaN
passiert jeden Vergleichs-Guard als False, ein späterer `if peak > limit: fail`
würde NaN als ok maskieren. Fix-Konvention (konsistent zu buckling.py/modal.py):
  * ungültige EINGABEN (non-finite / unphysikalisch) → ValueError, fail-loud;
  * non-finite LÖSUNG nach dem Solve (degeneriertes Mesh / singuläre Struktur)
    → GeometryError (die Klasse, die modal/buckling für degenerierte Struktur heben).
F3 (LOW): plate_hole._read_kt — leere Fernfeld-Maske → np.mean([]) = NaN → stiller
NaN-Kt; jetzt GeometryError.

Stub-basiert wo gmsh nötig wäre: die Guards feuern VOR jedem gmsh-Aufruf bzw. werden
per Monkeypatch auf np.linalg.solve getroffen — läuft komplett OHNE gmsh
(Muster: test_step7_hardening.py).

Run:  pytest tests/test_step7_fem_hardening.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from gen.core.errors import GeometryError  # noqa: E402
from gen.fem import solve_cantilever_tip_load  # noqa: E402
from gen.fem3d import solve_elasticity, structured_box_mesh, von_mises  # noqa: E402
from gen.fem3d_quadratic import solve_elasticity_t10  # noqa: E402

NAN, INF = float("nan"), float("inf")


# --- F1a: fem.solve_cantilever_tip_load — Eingangs-Guards -------------------------

def test_beam_nan_e_modulus_raises():
    """NaN-E propagierte still zu tip_deflection=NaN — muss laut werfen."""
    with pytest.raises(ValueError, match="finite"):
        solve_cantilever_tip_load(NAN, 11520.0, 60.0, 235.0)


def test_beam_inf_inertia_raises():
    with pytest.raises(ValueError, match="finite"):
        solve_cantilever_tip_load(3500.0, INF, 60.0, 235.0)


def test_beam_nan_force_raises():
    with pytest.raises(ValueError, match="finite"):
        solve_cantilever_tip_load(3500.0, 11520.0, 60.0, NAN)


def test_beam_nonpositive_length_raises():
    """L=0 gäbe eine 0/0-Elementsteifigkeit — unphysikalisch, fail-loud."""
    with pytest.raises(ValueError, match="positive"):
        solve_cantilever_tip_load(3500.0, 11520.0, 0.0, 235.0)


def test_beam_valid_inputs_still_exact():
    r = solve_cantilever_tip_load(3500.0, 11520.0, 60.0, 235.0)
    assert np.isclose(r["tip_deflection"], 235.0 * 60.0**3 / (3 * 3500.0 * 11520.0))


# --- F1b: fem3d.solve_elasticity — Eingangs- und Lösungs-Guards -------------------

def _tiny_mesh():
    return structured_box_mesh(1.0, 1.0, 1.0, 1, 1, 1)


def _tiny_bcs(nodes):
    fixed = {}
    for n, (x, _y, _z) in enumerate(nodes):
        if abs(x) < 1e-9:
            for c in range(3):
                fixed[3 * n + c] = 0.0
    return fixed


def test_fem3d_nan_e_modulus_raises():
    nodes, tets = _tiny_mesh()
    with pytest.raises(ValueError, match="finite"):
        solve_elasticity(nodes, tets, NAN, 0.3, _tiny_bcs(nodes), {})


def test_fem3d_invalid_poisson_raises():
    """ν=0.5 macht die Elastizitätsmatrix singulär (1−2ν=0) — vorher fangen."""
    nodes, tets = _tiny_mesh()
    with pytest.raises(ValueError, match="Poisson"):
        solve_elasticity(nodes, tets, 210000.0, 0.5, _tiny_bcs(nodes), {})


def test_fem3d_nan_load_raises():
    nodes, tets = _tiny_mesh()
    with pytest.raises(ValueError, match="finite"):
        solve_elasticity(nodes, tets, 210000.0, 0.3, _tiny_bcs(nodes), {3: NAN})


def test_fem3d_nan_fixed_value_raises():
    nodes, tets = _tiny_mesh()
    with pytest.raises(ValueError, match="finite"):
        solve_elasticity(nodes, tets, 210000.0, 0.3, {0: NAN}, {3: 1.0})


def test_fem3d_nonfinite_solution_raises_geometry_error(monkeypatch):
    """Ein Solve, das NaN liefert (degeneriertes System), darf NIE still als
    Verschiebungsfeld zurückkommen — GeometryError wie modal/buckling bei
    degenerierter Struktur."""
    nodes, tets = _tiny_mesh()
    fixed = _tiny_bcs(nodes)
    monkeypatch.setattr(
        np.linalg, "solve", lambda a, b: np.full(np.shape(b), NAN)
    )
    with pytest.raises(GeometryError, match="finite"):
        solve_elasticity(nodes, tets, 210000.0, 0.3, fixed, {3: 1.0})


def test_von_mises_nan_stress_raises():
    """von_mises(NaN) = NaN passierte jeden Limit-Vergleich als False."""
    with pytest.raises(ValueError, match="finite"):
        von_mises(np.array([NAN, 0.0, 0.0, 0.0, 0.0, 0.0]))


# --- F1c: fem3d_quadratic.solve_elasticity_t10 ------------------------------------

def _single_t10():
    """Ein gerader Referenz-T10-Tet (Ecken + geometrische Kantenmittelpunkte) in der
    lokalen Knotenordnung des Moduls — kein gmsh nötig."""
    corners = np.array([
        (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0, 0.0),
    ])
    edges = ((0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3))
    mids = np.array([(corners[a] + corners[b]) / 2.0 for a, b in edges])
    nodes = np.vstack([corners, mids])
    return nodes, np.array([list(range(10))])


def test_t10_nan_e_modulus_raises():
    nodes, tets = _single_t10()
    with pytest.raises(ValueError, match="finite"):
        solve_elasticity_t10(nodes, tets, NAN, 0.3, {9: 0.0}, {0: 1.0})


def test_t10_invalid_poisson_raises():
    nodes, tets = _single_t10()
    with pytest.raises(ValueError, match="Poisson"):
        solve_elasticity_t10(nodes, tets, 210000.0, 0.5, {9: 0.0}, {0: 1.0})


def test_t10_nonfinite_solution_raises_geometry_error(monkeypatch):
    nodes, tets = _single_t10()
    fixed = {3 * 3 + c: 0.0 for c in range(3)}
    monkeypatch.setattr(
        np.linalg, "solve", lambda a, b: np.full(np.shape(b), NAN)
    )
    with pytest.raises(GeometryError, match="finite"):
        solve_elasticity_t10(nodes, tets, 210000.0, 0.3, fixed, {0: 1.0})


# --- F1d: bracket_fem — Eingangs-Guard feuert VOR gmsh ----------------------------

def test_bracket_fem_nan_force_raises_before_gmsh():
    """NaN-Kraft lief bis vm.max()=NaN durch; der Guard muss VOR _require_gmsh
    liegen, sonst maskiert die fehlende gmsh-Installation den echten Fehler."""
    from gen.bracket_fem import bracket_bending_fem
    with pytest.raises(ValueError, match="finite"):
        bracket_bending_fem(force=NAN)


def test_bracket_fem_nan_e_modulus_raises_before_gmsh():
    from gen.bracket_fem import bracket_bending_fem
    with pytest.raises(ValueError, match="finite"):
        bracket_bending_fem(e_modulus=NAN)


def test_bracket_fem_nonpositive_thickness_raises_before_gmsh():
    from gen.bracket_fem import bracket_bending_fem
    with pytest.raises(ValueError, match="positive"):
        bracket_bending_fem(thickness=0.0)


# --- F3: plate_hole._read_kt — leere/entartete Fernfeld-Maske ----------------------

def _synthetic_field(x_centroids, sxx):
    """Ein synthetisches T4-'Mesh': je Element ein Punkt-Cluster am gewünschten
    Zentroid, mit vorgegebener Element-σxx."""
    nodes = []
    tets = []
    for i, x in enumerate(x_centroids):
        base = 4 * i
        nodes += [(x, 0.0, 0.0)] * 4
        tets.append((base, base + 1, base + 2, base + 3))
    stresses = np.zeros((len(x_centroids), 6))
    stresses[:, 0] = sxx
    return np.array(nodes), np.array(tets), stresses


def test_read_kt_empty_far_field_raises():
    """Kein Element mit x > 0.8·L → np.mean([]) = NaN → stiller NaN-Kt. Muss werfen."""
    from gen.plate_hole import _read_kt
    nodes, tets, stresses = _synthetic_field([0.1, 0.2], [100.0, 300.0])
    with pytest.raises(GeometryError, match="far-field"):
        _read_kt(nodes, tets, stresses, length=20.0)


def test_read_kt_zero_far_field_raises():
    """σ_far = 0 → Kt = peak/0 = inf — kein ehrlicher Konzentrationsfaktor."""
    from gen.plate_hole import _read_kt
    nodes, tets, stresses = _synthetic_field([0.1, 19.0], [300.0, 0.0])
    with pytest.raises(GeometryError, match="far-field"):
        _read_kt(nodes, tets, stresses, length=20.0)


def test_read_kt_valid_field_still_works():
    from gen.plate_hole import _read_kt
    nodes, tets, stresses = _synthetic_field([0.1, 19.0], [300.0, 100.0])
    r = _read_kt(nodes, tets, stresses, length=20.0)
    assert r["kt"] == pytest.approx(3.0)
