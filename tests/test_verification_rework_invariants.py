"""Verification package invariants (REWORK campaign 2026-07-11).

Pins fail-loud / non-poisoning behaviour on cross-model confidence folding,
GATE α soundness, and derivation tolerance — the anti-hallucination core.
"""

from __future__ import annotations

import math

import pytest

from gen.core.state import (
    Claim,
    ClaimStatus,
    Question,
    Report,
    RunState,
    SourceRef,
)
from gen.verification.consensus import consensus_verdict
from gen.verification.cross_model import (
    Judgment,
    combine_judgments,
    corroborated_confidence,
    _clamp01,
)
from gen.verification.derivation import within_tolerance
from gen.verification.gates import claim_soundness_failures, gate_alpha


def _src() -> SourceRef:
    return SourceRef(url_or_id="https://example.test/s", retrieved=True)


# --- clamp / cross-model: NaN must never poison confidence -------------------


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_clamp01_maps_nonfinite_to_zero(bad: float):
    out = _clamp01(bad)
    assert out == 0.0
    assert math.isfinite(out)


def test_corroborated_confidence_nonfinite_inputs_are_safe():
    # NaN must not yield NaN confidence (would defeat gate thresholds).
    c = corroborated_confidence(float("nan"), 0.9)
    assert math.isfinite(c)
    assert 0.0 <= c <= 1.0


def test_combine_judgments_nonfinite_confidence_stays_finite():
    p = Judgment(ClaimStatus.VERIFIED, float("nan"), "gpt-4o")
    s = Judgment(ClaimStatus.VERIFIED, 0.8, "llama3.1:70b")
    out = combine_judgments(p, s)
    assert math.isfinite(out.confidence)
    assert 0.0 <= out.confidence <= 1.0


def test_consensus_nonfinite_judge_confidence_does_not_poison():
    judges = [
        Judgment(ClaimStatus.VERIFIED, float("nan"), "gpt-4o"),
        Judgment(ClaimStatus.VERIFIED, 0.9, "claude-3-5"),
    ]
    v = consensus_verdict(generator_model="llama3.1:8b", judgments=judges)
    assert math.isfinite(v.confidence)
    assert math.isfinite(v.aggregate)


# --- GATE α: VERIFIED + non-finite confidence must not pass ------------------


def test_claim_soundness_flags_nonfinite_verified_confidence():
    claim = Claim(
        id="c1",
        text="steel is dense",
        sources=[_src()],
        status=ClaimStatus.VERIFIED,
        confidence=0.9,
    )
    # Dataclass allows post-construction mutation (legacy tests); gate must still catch it.
    claim.confidence = float("nan")
    fails = claim_soundness_failures(claim, confidence_threshold=0.7, flagged=set())
    codes = {f.code for f in fails}
    assert "LOW_CONFIDENCE" in codes or "NONFINITE_CONFIDENCE" in codes


def test_gate_alpha_rejects_verified_with_nan_confidence():
    claim = Claim(
        id="c1",
        text="steel is dense",
        sources=[_src()],
        status=ClaimStatus.VERIFIED,
        confidence=0.95,
    )
    claim.confidence = float("nan")
    state = RunState(question=Question(raw="density?", run_id="r1"))
    state.claims = [claim]
    state.report = Report(
        run_id="r1",
        question="density?",
        body="steel is dense",
        statement_to_claim={"steel is dense": "c1"},
    )
    result = gate_alpha(state, confidence_threshold=0.7)
    assert result.passed is False
    assert any(
        f.code in ("LOW_CONFIDENCE", "NONFINITE_CONFIDENCE") for f in result.failures
    )


# --- derivation tolerance: non-finite never "matches" ------------------------


@pytest.mark.parametrize(
    "stated,computed,tol",
    [
        (float("nan"), 1.0, 1e-9),
        (1.0, float("nan"), 1e-9),
        (1.0, 1.0, float("nan")),
        (float("inf"), 1.0, 1e-9),
    ],
)
def test_within_tolerance_rejects_nonfinite(stated, computed, tol):
    assert within_tolerance(stated, computed, tolerance=tol) is False
