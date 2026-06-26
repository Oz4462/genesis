"""Simulation Layer – hardened, automatic coupling of CAD + Physics into falsifiable predictions.

This completes "Punkt 4" of the hardening assessment:
- Automatic selection of relevant simulations from design intent.
- Execution of simulations on generated geometry / loads.
- Structured, provenance-rich results that feed directly into HORIZON δ⁺ (reality.py + gate_delta_plus).
- Deterministic, offline, gate-aware, 4-Linsen compliant.

Core entry point: run_simulations_for_design(...)
"""

from .runner import (
    SimulationRunner,
    SimulationCase,
    SimulationResult,
    SimulationReport,
    run_simulations_for_design,
    run_simulations_for_hammer,
    build_simulation_report,
    optimize_params,
    optimize_simulation_params,
    OptimizationResult,
    ReferenceCase,
    get_reference_cases,
    mesh_convergence_gate,
)

# quantum_opt re-exports its public API via runner for simulation users;
# direct: from gen.simulation.quantum_opt import optimize_params, OptimizationResult
from . import quantum_opt

__all__ = [
    "SimulationRunner",
    "SimulationCase",
    "SimulationResult",
    "SimulationReport",
    "run_simulations_for_design",
    "run_simulations_for_hammer",
    "build_simulation_report",
    "optimize_params",
    "optimize_simulation_params",
    "OptimizationResult",
    "quantum_opt",
    "ReferenceCase",
    "get_reference_cases",
    "mesh_convergence_gate",
]
