# GENESIS Simulation Contract (per GENESIS_PLATFORM_BUILD_TODO §A3)

## ModelContract

Defines the contract for any simulation model used in Genesis.

Required fields:
- intended_use: str (e.g. "preliminary structural sizing for prototype")
- decision_criticality: "low" | "medium" | "high" | "certification"
- conceptual_model: str (description of physics/idealization)
- governing_equations: list[str] (e.g. ["Euler-Bernoulli beam", "Hooke's law"])
- assumptions: list[str] (explicit, with sources)
- verification_evidence: list[dict] (mesh convergence, code verification, etc.)
- validation_evidence: list[dict] (comparison to experiment or analytical)
- uncertainty_budget: dict (sources, values, combined)
- sensitivity_report: dict (key parameters, influence)
- applicability_domain: str (e.g. "linear elastic, small deflections, isotropic")
- known_invalid_cases: list[str]
- acceptance_criteria: dict (e.g. {"max_error": 5%, "mesh_independence": "<2% change"})

## SimulationSpec

- model: ModelContract
- inputs: dict (geometry, loads, materials, BCs)
- mesh_spec: optional
- solver: str
- output_quantities: list[str]

## SimulationReceipt

- run_id
- status: "success" | "failed" | "inconclusive"
- results: dict
- provenance: list[SourceRef]
- warnings: list[str]
- gaps: list[str]
- validation_status: "verified" | "validated" | "neither"

## Gates (deterministic)

- Mesh Gate: quality metrics, convergence check
- Convergence Gate: residual, mesh independence
- Unit Gate + Dimensional consistency
- Applicability Gate (domain check)
- Acceptance Gate vs criteria

No simulation result accepted without Receipt and passed gates.

Implementation in simulation/runner.py + physics_validation + mesh_integrity.

(Initial fill 2026-06-24 autonomous per PLAN + existing code in simulation/, fem*, mesh_integrity.)