"""Schritt-7-Batch-2-Härtungen (Review 2026-07-04): modal / orientation / manufacturing_check.

Vier Anti-Halluzinations-Härtungen — jede war ein Pfad, auf dem degenerierte oder
non-finite Eingaben zu einem stillen Pass statt einem lauten Fehler wurden:
  F1 leeres Mesh in overhang_check  → „kein Support nötig" ohne Geometrie
  F2 NaN-Wanddicke im DFM-Konsumenten → Min-Wall-Regel passt still (NaN < x == False)
  F3 build_dir=(0,0,0)              → alle Winkel 90° → nie Support
  F4 excitation_hz=NaN              → entkommt dem ≤0-Guard (zufällig fail-safe)

Stub-basiert: läuft OHNE cadquery/build123d (die optionalen Kernel-Pfade werden
gemonkeypatcht, exakt wie in test_geometry_verification_hardening.py).

Run:  pytest tests/test_step7_hardening.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402


# --- F1 + F3: orientation.overhang_check ----------------------------------------

class _StubVec:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class _StubSolid:
    """Minimal duck-typed solid: empty tessellation, unit bounding box."""

    def tessellate(self, tol):
        return [], []

    def BoundingBox(self):
        return SimpleNamespace(xmin=0.0, xmax=1.0, ymin=0.0, ymax=1.0,
                               zmin=0.0, zmax=1.0)


def _patch_orientation(monkeypatch):
    import gen.orientation as orientation
    monkeypatch.setattr(orientation, "_require_cadquery", lambda: None)
    monkeypatch.setattr(orientation, "csg_to_solid", lambda node, q: _StubSolid())
    return orientation


def test_overhang_check_empty_mesh_raises_not_silent_pass(monkeypatch):
    """F1: 0 Dreiecke dürfen nie 'needs_support=False' ergeben — wie die
    Schwestern first_layer_report/bridge_spans muss ein leeres Mesh werfen."""
    orientation = _patch_orientation(monkeypatch)
    with pytest.raises(ValueError, match="no triangles"):
        orientation.overhang_check(node=None, quantities={})


def test_overhang_check_zero_build_dir_raises(monkeypatch):
    """F3: build_dir=(0,0,0) machte jeden Winkel zu 90° (nie Support) — muss werfen."""
    orientation = _patch_orientation(monkeypatch)
    with pytest.raises(ValueError, match="build_dir"):
        orientation.overhang_check(node=None, quantities={}, build_dir=(0.0, 0.0, 0.0))


# --- F2: manufacturing_check NaN wall/volume -------------------------------------

def _fake_artifact(wall_mm: float, vol_cm3: float):
    spec = SimpleNamespace(name="nan-probe", min_wall_thickness_mm=wall_mm,
                           bounding_box_hint_mm=(50.0, 50.0, 10.0),
                           material_hint="PLA")
    return SimpleNamespace(spec=spec, exports={}, volume_estimate_cm3=vol_cm3)


def test_advanced_dfm_nan_wall_is_flagged_not_silently_conform():
    """F2: NaN-Wanddicke passiert jeden <-Guard als False — sie muss als
    Issue/Gap auftauchen und FDM darf nicht printable sein."""
    from gen.cad.manufacturing_check import check_advanced_dfm
    report = check_advanced_dfm(_fake_artifact(wall_mm=float("nan"), vol_cm3=10.0))
    fdm = next(p for p in report.processes if p.process == "FDM")
    joined = " ".join(list(fdm.issues) + list(fdm.gaps)).lower()
    assert "finite" in joined or "nan" in joined
    assert fdm.printable is False


def test_advanced_dfm_nan_volume_is_flagged():
    """F2b: NaN-Volumen darf weder Kosten noch Regeln still passieren."""
    from gen.cad.manufacturing_check import check_advanced_dfm
    report = check_advanced_dfm(_fake_artifact(wall_mm=2.0, vol_cm3=float("nan")))
    fdm = next(p for p in report.processes if p.process == "FDM")
    joined = " ".join(list(fdm.issues) + list(fdm.gaps)).lower()
    assert "finite" in joined or "nan" in joined


# --- F4: modal.resonance_check NaN excitation ------------------------------------

def test_resonance_check_nan_excitation_raises():
    """F4: der ≤0-Guard behauptet alle unzulässigen Anregungen zu fangen —
    NaN muss denselben ValueError treffen (nicht auf Vergleichs-Zufall bauen)."""
    from gen.modal import resonance_check
    with pytest.raises(ValueError):
        resonance_check(first_natural_hz=100.0, excitation_hz=float("nan"))
    assert math.isfinite(
        resonance_check(first_natural_hz=100.0, excitation_hz=10.0)["ratio"]
    )


# --- D1 (2026-07-04): subsystem types moved out of the framework-free core -------

def test_d1_subsystem_types_moved_with_compat_shim():
    """ModuleSpec/ColonyModule/NanoRecipe live in gen.subsystem_types; the old
    core.state import path keeps working via lazy PEP-562 re-export, and the
    shim raises AttributeError for genuinely unknown names."""
    import pytest as _pytest
    from gen import subsystem_types
    from gen.core import state
    for name in ("ModuleSpec", "ColonyModule", "NanoRecipe"):
        assert getattr(state, name) is getattr(subsystem_types, name)
    with _pytest.raises(AttributeError):
        state.DefinitelyNotAType  # noqa: B018
