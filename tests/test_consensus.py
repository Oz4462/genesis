"""Tests for the multi-critic verification consensus (Phase 3).

Exercises the PoV-3 property natively on GENESIS Judgments: a panel agreeing
VERIFIED corroborates; enough dissent collapses to the conservative UNSUPPORTED
(more catches than a single optimistic judge); any refutation vetoes; cross-model
is enforced; verdicts are deterministic.
"""

from __future__ import annotations

import pytest

from gen.core.errors import ModelConflictError
from gen.core.state import ClaimStatus
from gen.verification import ConsensusVerdict, Judgment, consensus_verdict

GEN = "qwen3.5:9b"  # generator family = qwen


def _j(status: ClaimStatus, conf: float, model: str) -> Judgment:
    return Judgment(status=status, confidence=conf, model=model)


def _panel(*statuses_conf) -> list[Judgment]:
    # distinct non-qwen families so cross-model holds
    fams = ["claude-x", "gpt-x", "gemini-x", "llama-x", "mistral-x", "deepseek-x", "grok-x"]
    return [_j(s, c, fams[i]) for i, (s, c) in enumerate(statuses_conf)]


def test_unanimous_verified_corroborates():
    panel = _panel((ClaimStatus.VERIFIED, 0.8), (ClaimStatus.VERIFIED, 0.8),
                   (ClaimStatus.VERIFIED, 0.8))
    v = consensus_verdict(generator_model=GEN, judgments=panel, accept_threshold=0.7)
    assert v.status is ClaimStatus.VERIFIED and v.accept
    assert v.confidence > 0.8  # noisy-OR corroboration > any single judge


def test_dissent_collapses_to_unsupported():
    # 3 verified (0.9) + 4 unsupported -> aggregate = 3*0.9/7 = 0.386 < 0.7
    panel = _panel(
        (ClaimStatus.VERIFIED, 0.9), (ClaimStatus.VERIFIED, 0.9), (ClaimStatus.VERIFIED, 0.9),
        (ClaimStatus.UNSUPPORTED, 0.0), (ClaimStatus.UNSUPPORTED, 0.0),
        (ClaimStatus.UNSUPPORTED, 0.0), (ClaimStatus.UNSUPPORTED, 0.0),
    )
    v = consensus_verdict(generator_model=GEN, judgments=panel, accept_threshold=0.7)
    assert v.status is ClaimStatus.UNSUPPORTED and not v.accept


def test_any_refutation_vetoes():
    panel = _panel((ClaimStatus.VERIFIED, 0.95), (ClaimStatus.VERIFIED, 0.95),
                   (ClaimStatus.REFUTED, 0.8))
    v = consensus_verdict(generator_model=GEN, judgments=panel, accept_threshold=0.7)
    assert v.status is ClaimStatus.REFUTED and not v.accept and v.n_refuted == 1
    assert v.confidence == 0.8


def test_cross_model_enforced():
    panel = [_j(ClaimStatus.VERIFIED, 0.9, "qwen2.5:14b")]  # same family as generator
    with pytest.raises(ModelConflictError):
        consensus_verdict(generator_model=GEN, judgments=panel)


def test_weights_and_validation():
    panel = _panel((ClaimStatus.VERIFIED, 0.9), (ClaimStatus.UNSUPPORTED, 0.0))
    # upweight the verified judge -> clears threshold
    v = consensus_verdict(
        generator_model=GEN, judgments=panel,
        weights={"claude-x": 9.0, "gpt-x": 1.0}, accept_threshold=0.7,
    )
    assert v.status is ClaimStatus.VERIFIED
    with pytest.raises(ValueError):
        consensus_verdict(generator_model=GEN, judgments=[])
    with pytest.raises(ValueError):
        consensus_verdict(generator_model=GEN, judgments=panel,
                          weights={"claude-x": 0.0, "gpt-x": 0.0})


def test_deterministic():
    panel = _panel((ClaimStatus.VERIFIED, 0.8), (ClaimStatus.VERIFIED, 0.6),
                   (ClaimStatus.UNSUPPORTED, 0.0))
    a = consensus_verdict(generator_model=GEN, judgments=panel)
    b = consensus_verdict(generator_model=GEN, judgments=panel)
    assert a == b
    assert isinstance(a, ConsensusVerdict)
