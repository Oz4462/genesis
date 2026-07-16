"""materials_oracle — an import-gated materials-energy ExternalOracle (ORB / MatterSim class) + offline twin.

INVENTOR §10¾ B/D + M4. A universal interatomic potential (ORB, MatterSim, CHGNet) predicts the energy and
stability of a candidate structure — a GPU foundation model GENESIS *calls*, never reimplements. This module
supplies the WIRING under the :class:`gen.external.oracle.ExternalOracle` contract, with the real model
import-gated to the owner's GPU machine and a deterministic OFFLINE TWIN that proves the gated-claim path.

Honesty (the whole point of the twin): :class:`OfflineMaterialsTwin` is a TRANSPARENT PLACEHOLDER — a plain
harmonic estimate E ≈ ½·k·Σδ², explicitly NOT the real potential. Its :class:`OracleClaim` says so in the
statement, and it flows into the ledger as an UNVERIFIED, licensed, provenance-carrying claim (never raw
truth). :class:`RealMaterialsOracle` raises :class:`MaterialsOracleUnavailable` when ``orb-models`` is absent
— an honest skip, never a fabricated energy. ORB is Apache-2.0 (permissive → core-linkable, commercial_ok).
Deterministic, offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .oracle import OracleClaim
from .registry import ExternalBinding, IntegrationMode, external_binding

#: The validated, license-disciplined binding for the ORB universal potential (Apache-2.0, permissive).
#: Constructing this already enforces the license gate (a non-commercial model could not be bound here).
ORB_BINDING: ExternalBinding = external_binding(
    "orb-models", "0.5", "apache-2.0",
    provenance=("pip:orb-models (Orbital Materials, Apache-2.0); "
                "https://github.com/orbital-materials/orb-models"),
    integration_mode=IntegrationMode.LIBRARY,
)


class MaterialsOracleUnavailable(RuntimeError):
    """Raised when the real GPU potential is not installed — an honest abstention (like
    ``SimulatorUnavailable``), never a fabricated energy. Use :class:`OfflineMaterialsTwin` for the
    deterministic wiring proof."""


@dataclass(frozen=True)
class StructureSpec:
    """A minimal structure descriptor the offline twin can score deterministically: a formula label, the atom
    count, the mean per-atom displacement from equilibrium (Å; 0 = relaxed) and an effective harmonic
    stiffness. A real ORB adapter would take ASE ``Atoms`` / positions; this is the twin's transparent input."""

    formula: str
    n_atoms: int
    mean_displacement: float = 0.0
    stiffness_ev_per_a2: float = 1.0

    def __post_init__(self) -> None:
        if self.n_atoms <= 0:
            raise ValueError("n_atoms must be positive")
        if self.mean_displacement < 0.0 or self.stiffness_ev_per_a2 < 0.0:
            raise ValueError("displacement and stiffness must be non-negative")


class RealMaterialsOracle:
    """The real ORB adapter — import-gated. Without ``orb-models`` (the owner's GPU machine) ``query`` raises
    :class:`MaterialsOracleUnavailable`. The live GPU inference is configured on the owner machine; this class
    deliberately never returns an invented energy."""

    name = "orb-materials"
    binding = ORB_BINDING

    async def query(self, spec: Any) -> OracleClaim:
        try:
            import orb_models
        except Exception as exc:
            raise MaterialsOracleUnavailable(
                "orb-models not installed — the real universal potential runs on the owner's GPU machine; "
                "use OfflineMaterialsTwin for the deterministic wiring proof") from exc
        raise MaterialsOracleUnavailable(
            "orb-models is importable, but live GPU inference must be configured on the owner machine "
            "(model weights + device); GENESIS never fabricates an energy here")


class OfflineMaterialsTwin:
    """A deterministic OFFLINE TWIN of the energy oracle — NOT the real potential. It scores a structure with a
    transparent harmonic estimate E ≈ ½·k·Σδ² (over the atoms) so the gated-claim path is testable offline.
    Every claim names itself an offline twin and carries low confidence, so it can never pass as an ORB run."""

    name = "orb-materials-offline-twin"
    binding = ORB_BINDING

    async def query(self, spec: StructureSpec) -> OracleClaim:
        energy = 0.5 * spec.stiffness_ev_per_a2 * (spec.mean_displacement ** 2) * spec.n_atoms
        return OracleClaim(
            subject=f"relative energy of {spec.formula} ({spec.n_atoms} atoms)",
            statement=("OFFLINE TWIN harmonic estimate (NOT the ORB potential): "
                       f"E≈½·k·Σδ² = {energy:.4g} eV; a real value needs orb-models on a GPU"),
            binding=self.binding,
            oracle_provenance=(f"offline-twin:harmonic;formula={spec.formula};"
                               f"displacement={spec.mean_displacement};k={spec.stiffness_ev_per_a2}"),
            value=energy, uncertainty=None, confidence=0.3)


__all__ = ["ORB_BINDING", "MaterialsOracleUnavailable", "StructureSpec",
           "RealMaterialsOracle", "OfflineMaterialsTwin"]
