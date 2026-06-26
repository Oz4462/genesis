"""ProofPackageGenerator - full realization proof package (PLAN G6, PLATFORM).

Collects claims, CAD, sim receipts, wb seeds, gates, falsification, costs, assembly into auditable package.

Honest: marks gaps, no overclaim on E2E real measurements (deferred).

Integrates with integrator, lumencrucible, reality, wissensbasis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..core.state import RunState, Claim
# LearningCycleResult may be in lumencrucible return style; use dict for compatibility
LearningCycleResult = dict  # fallback for type hint compatibility in autonomy build


@dataclass
class ProofPackage:
    run_id: str
    idea: str
    claims: list[dict] = field(default_factory=list)
    cad_artifacts: list[str] = field(default_factory=list)
    simulation_receipts: list[dict] = field(default_factory=list)
    wissensbasis_seeds: list[dict] = field(default_factory=list)
    gates_passed: list[str] = field(default_factory=list)
    falsification_experiments: list[dict] = field(default_factory=list)
    costs: dict = field(default_factory=dict)
    assembly: dict = field(default_factory=dict)
    readiness_level: str = "TRL3"  # default
    gaps: list[str] = field(default_factory=list)
    package_dir: str | None = None
    quelle: str = "proof_package + integrator + grenz"


def generate_proof_package(
    run_id: str,
    idea: str,
    state: Optional[RunState] = None,
    learning: Optional[LearningCycleResult] = None,
    cad_files: list[str] | None = None,
    sim_receipts: list[dict] | None = None,
    wb_seeds: list[dict] | None = None,
    package_root: str = "out/proof_packages",
) -> ProofPackage:
    """Generate full ProofPackage.

    Collects from passed data + state if present.
    Writes manifest + summary.md.
    """
    pkg = ProofPackage(run_id=run_id, idea=idea)

    if state:
        pkg.claims = [{"id": c.id, "text": c.text, "status": str(c.status)} for c in (state.claims or [])]
        if hasattr(state, "reality_verdict") and state.reality_verdict:
            pkg.gates_passed.append("delta_plus_reality")
        if hasattr(state, "coverage_certificate") and state.coverage_certificate:
            pkg.gates_passed.append("delta_plus_coverage")

    if learning:
        pkg.wissensbasis_seeds.extend(learning.seeded or [])
        pkg.gates_passed.append("learning_8step")

    if cad_files:
        pkg.cad_artifacts.extend(cad_files)

    if sim_receipts:
        pkg.simulation_receipts.extend(sim_receipts)

    if wb_seeds:
        pkg.wissensbasis_seeds.extend(wb_seeds)

    pkg.gaps = ["full real measurement E2E deferred (no live lab data)", "rich BOM/costs for non-FDM deferred"]

    # readiness basic
    pkg.readiness_level = "TRL4" if len(pkg.gates_passed) > 2 else "TRL3"

    # write package
    pkg_dir = Path(package_root) / f"{run_id}_proof"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": run_id,
        "idea": idea,
        "claims": pkg.claims,
        "artifacts": pkg.cad_artifacts,
        "receipts": pkg.simulation_receipts,
        "seeds": pkg.wissensbasis_seeds,
        "gates": pkg.gates_passed,
        "readiness": pkg.readiness_level,
        "gaps": pkg.gaps,
        "quelle": pkg.quelle,
    }
    (pkg_dir / "proof_manifest.json").write_text(str(manifest))
    (pkg_dir / "SUMMARY.md").write_text(f"# Proof Package for {idea}\n\nGates: {pkg.gates_passed}\nReadiness: {pkg.readiness_level}\nGaps: {pkg.gaps}")

    pkg.package_dir = str(pkg_dir)
    return pkg
