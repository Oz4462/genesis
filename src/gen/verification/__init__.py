"""GENESIS verification: the deterministic core of the anti-hallucination guarantee.

  gate_alpha           — pure, LLM-free completion predicate (GATE α).
  gate_beta            — pure, LLM-free completion predicate (GATE β, builds on α).
  gate_gamma           — pure, LLM-free completion predicate (GATE γ, builds on α+β).
  claim_soundness_failures — shared per-claim α-soundness check (used by all gates).
  evaluate_formula / topological_values / within_tolerance — safe arithmetic for
                         DERIVED values (the LLM never does math; code computes,
                         the gate recomputes).
  Judgment             — one model's mockable verdict on a claim.
  verify_confidence    — enforce cross-model + fold judgments (skeptic entry point).
  assert_different_families / model_family — the cross-model audit primitives.
"""

from __future__ import annotations

# Audit F1: do NOT eagerly import coverage/seams/memory_fabric/omega here —
# those packages form import cycles with verification. Lazy via __getattr__.
from .consensus import ConsensusVerdict, consensus_verdict
from .cross_model import (
    Judgment,
    assert_different_families,
    assert_pairwise_different_families,
    combine_judgments,
    corroborated_confidence,
    model_family,
    status_disagreement,
    verify_confidence,
)
from .derivation import (
    DEFAULT_TOLERANCE,
    evaluate_formula,
    topological_values,
    within_tolerance,
)
from .gates import (
    claim_soundness_failures,
    gate_alpha,
    gate_beta,
    gate_chi,
    gate_delta,
    gate_gamma,
    gate_phi,
    geometry_envelope,
    value_in_text,
)
from .geometry import (
    Aabb,
    Mass,
    Volume,
    aabb_of,
    geometry_length_unit,
    mass_of,
    overlaps,
    volume_of,
)
from .units import DIMENSIONLESS, Dimension, formula_dimension, parse_unit

__all__ = [
    "gate_alpha",
    "gate_beta",
    "gate_gamma",
    "gate_delta",
    "gate_delta_plus_coverage",
    "gate_epsilon",
    "gate_zeta",
    "gate_omega",
    "gate_phi",
    "gate_chi",
    "geometry_envelope",
    "Aabb",
    "aabb_of",
    "overlaps",
    "Volume",
    "volume_of",
    "Mass",
    "mass_of",
    "geometry_length_unit",
    "claim_soundness_failures",
    "value_in_text",
    "evaluate_formula",
    "topological_values",
    "within_tolerance",
    "DEFAULT_TOLERANCE",
    "parse_unit",
    "formula_dimension",
    "Dimension",
    "DIMENSIONLESS",
    "Judgment",
    "verify_confidence",
    "combine_judgments",
    "corroborated_confidence",
    "status_disagreement",
    "assert_different_families",
    "assert_pairwise_different_families",
    "model_family",
    "consensus_verdict",
    "ConsensusVerdict",
]


def __getattr__(name: str):
    """Lazy re-exports for horizon gates (break verification↔coverage/seams cycles)."""
    if name == "gate_delta_plus_coverage":
        from ..coverage import gate_delta_plus_coverage as g

        return g
    if name == "gate_epsilon":
        from ..seams import gate_epsilon as g

        return g
    if name == "gate_zeta":
        from ..memory_fabric import gate_zeta as g

        return g
    if name == "gate_omega":
        from ..omega import gate_omega as g

        return g
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
