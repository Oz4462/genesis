"""mesh_convergence_gate + get_reference_cases — honest sim gate for humanoid/aethon CLI."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.simulation.runner import (  # noqa: E402
    SimulationCase,
    get_reference_cases,
    mesh_convergence_gate,
)


def test_get_reference_cases_nonempty_offline():
    refs = get_reference_cases()
    assert len(refs) >= 2
    assert all("name" in r and "quelle" in r for r in refs)


def test_mesh_gate_none_is_honest_fail():
    g = mesh_convergence_gate(None)
    assert g["ok"] is False
    assert g["converged"] is False
    assert g["gaps"]
    assert "quelle" in g


def test_mesh_gate_analytical_ok():
    case = SimulationCase(
        domain="structural_linear",
        description="tip deflection",
        predicted_value=1.0,
        predicted_unit="mm",
        tolerance=0.1,
        inputs_summary={},
        solver="analytical+euler_bernoulli",
        quelle="test",
    )
    g = mesh_convergence_gate(case)
    assert g["ok"] is True
    assert g["converged"] is True


def test_mesh_gate_series_converged():
    case = SimulationCase(
        domain="structural_linear",
        description="tip",
        predicted_value=1.01,
        predicted_unit="mm",
        tolerance=0.1,
        inputs_summary={"mesh_series": [1.2, 1.05, 1.02, 1.01]},
        solver="fem_hex",
        quelle="test",
    )
    g = mesh_convergence_gate(case, relative_tol=0.05)
    assert g["ok"] is True
    assert g["relative_change"] <= 0.05


def test_mesh_gate_series_not_converged():
    case = SimulationCase(
        domain="structural_linear",
        description="tip",
        predicted_value=2.0,
        predicted_unit="mm",
        tolerance=0.1,
        inputs_summary={"mesh_series": [1.0, 2.0]},
        solver="fem_hex",
        quelle="test",
    )
    g = mesh_convergence_gate(case, relative_tol=0.05)
    assert g["ok"] is False
    assert g["gaps"]


def test_mesh_gate_no_series_is_gap():
    case = SimulationCase(
        domain="structural_linear",
        description="tip",
        predicted_value=1.0,
        predicted_unit="mm",
        tolerance=0.1,
        inputs_summary={},
        solver="fem_hex",
        quelle="test",
    )
    g = mesh_convergence_gate(case)
    assert g["ok"] is False
    assert "mesh_series" in g["gaps"][0]
