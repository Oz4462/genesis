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

from .cross_model import (
    Judgment,
    assert_different_families,
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
    gate_delta,
    gate_gamma,
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
    "model_family",
]
