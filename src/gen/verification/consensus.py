"""Multi-critic verification consensus (Phase 3).

GENESIS's `cross_model.combine_judgments` folds at most TWO judges. PoV-3 showed that
a panel of N independent verifiers, aggregated, catches far more unsound items than a
single skeptic (leak-rate 0.593 -> 0.173) without losing sound-recall — the same
"weighted mean + veto" property buch-llm's debate orchestrator uses.

This module implements that property NATIVELY on GENESIS's own `Judgment` model.
buch-llm itself is NOT imported or vendored: it is proprietary (All-Rights-Reserved)
while GENESIS is MIT, so its code cannot enter this tree. PoV-3 used buch-llm's real
aggregator to PROVE the property; here the generic statistics are re-implemented.

Honesty principles preserved (CLAUDE.md / cross_model.py):
  * every judge must run on a different model family than the generator (cross-model);
  * a fact is never VERIFIED under disagreement — any credible REFUTED vetoes, and an
    aggregate below the accept threshold collapses to the conservative UNSUPPORTED;
  * pure, deterministic (reproducibility A5): same judgments -> same verdict.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ..core.state import ClaimStatus
from .cross_model import (
    Judgment,
    assert_different_families,
    corroborated_confidence,
)


@dataclass(frozen=True)
class ConsensusVerdict:
    """Outcome of aggregating a panel of independent judgments.

    `status`      the conservative consensus status (VERIFIED only on agreement).
    `confidence`  0..1: corroborated noisy-OR for an accepted VERIFIED; the strongest
                  refuter's confidence for REFUTED; the weighted aggregate for UNSUPPORTED.
    `aggregate`   weighted mean of per-judge support scores (the accept signal).
    `accept`      True iff status is VERIFIED.
    `per_judge`   (model, support_score) for audit, in input order.
    `n_refuted`   how many judges actively refuted (any > 0 vetoes VERIFIED).
    """

    status: ClaimStatus
    confidence: float
    aggregate: float
    accept: bool
    per_judge: tuple[tuple[str, float], ...]
    n_refuted: int


def _support_score(j: Judgment) -> float:
    """Per-judge support for the claim being true, in [0,1].

    VERIFIED contributes its confidence; UNSUPPORTED/REFUTED contribute 0 (no
    positive support). A panel of mostly-supporting judges clears the threshold;
    each dissenter pulls the weighted mean down — the PoV-3 leak-reduction effect.
    """
    return _clamp01(j.confidence) if j.status is ClaimStatus.VERIFIED else 0.0


def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def consensus_verdict(
    *,
    generator_model: str,
    judgments: Sequence[Judgment],
    weights: Mapping[str, float] | None = None,
    accept_threshold: float = 0.7,
) -> ConsensusVerdict:
    """Aggregate an N-judge panel into one conservative, cross-model verdict.

    Args:
        generator_model: the model that produced the claim; every judge must be a
            different family (enforced — ``ModelConflictError`` otherwise).
        judgments: independent verdicts (>= 1). Each is the mockable boundary.
        weights: optional per-model weight (default uniform). Negative weights or a
            zero total are rejected (a silent zero would erase the panel).
        accept_threshold: minimum weighted aggregate to assert VERIFIED.

    Returns:
        ConsensusVerdict. VERIFIED only when no judge refuted AND the weighted
        aggregate of VERIFIED-support meets the threshold; any refutation yields
        REFUTED; everything else is the non-committal UNSUPPORTED.

    Raises:
        ValueError: empty panel, or weights invalid.
        ModelConflictError: a judge shares the generator's model family.
    """
    if not judgments:
        raise ValueError("consensus needs at least one judgment")
    for j in judgments:
        assert_different_families(generator_model, j.model)

    w = [float((weights or {}).get(j.model, 1.0)) for j in judgments]
    if any(x < 0 for x in w):
        raise ValueError("weights must be non-negative")
    total = sum(w)
    if total <= 0:
        raise ValueError("total weight must be positive")

    supports = [_support_score(j) for j in judgments]
    aggregate = sum(wi * si for wi, si in zip(w, supports, strict=True)) / total
    per_judge = tuple((j.model, s) for j, s in zip(judgments, supports, strict=True))
    n_refuted = sum(1 for j in judgments if j.status is ClaimStatus.REFUTED)

    if n_refuted > 0:
        # A credible refutation stands; report the strongest refuter's confidence.
        ref_conf = max(
            (_clamp01(j.confidence) for j in judgments if j.status is ClaimStatus.REFUTED),
            default=0.0,
        )
        return ConsensusVerdict(
            status=ClaimStatus.REFUTED,
            confidence=ref_conf,
            aggregate=aggregate,
            accept=False,
            per_judge=per_judge,
            n_refuted=n_refuted,
        )

    if aggregate >= accept_threshold:
        # Independent corroboration across the agreeing VERIFIED judges (noisy-OR).
        conf = 0.0
        for j in judgments:
            if j.status is ClaimStatus.VERIFIED:
                conf = corroborated_confidence(conf, j.confidence)
        return ConsensusVerdict(
            status=ClaimStatus.VERIFIED,
            confidence=conf,
            aggregate=aggregate,
            accept=True,
            per_judge=per_judge,
            n_refuted=0,
        )

    return ConsensusVerdict(
        status=ClaimStatus.UNSUPPORTED,
        confidence=aggregate,
        aggregate=aggregate,
        accept=False,
        per_judge=per_judge,
        n_refuted=0,
    )


__all__ = ["ConsensusVerdict", "consensus_verdict"]
