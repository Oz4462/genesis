"""GENESIS verification: the deterministic core of the anti-hallucination guarantee.

  gate_alpha           — pure, LLM-free completion predicate (GATE α).
  gate_beta            — pure, LLM-free completion predicate (GATE β, builds on α).
  claim_soundness_failures — shared per-claim α-soundness check (used by both gates).
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
from .gates import claim_soundness_failures, gate_alpha, gate_beta

__all__ = [
    "gate_alpha",
    "gate_beta",
    "claim_soundness_failures",
    "Judgment",
    "verify_confidence",
    "combine_judgments",
    "corroborated_confidence",
    "status_disagreement",
    "assert_different_families",
    "model_family",
]
