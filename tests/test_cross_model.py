"""Tests for cross-model verification — no real LLM calls (judgments are mocked).

Covers Aufgabe 2 of CLAUDE_CODE_AUFTRAG_001:
  * model-family identification (basis for the cross-model audit, A6)
  * the hard rule: verifier family must differ from generator (ModelConflictError)
  * disagreement lowers confidence and forces a conservative, honest status
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.errors import ModelConflictError  # noqa: E402
from gen.core.state import ClaimStatus  # noqa: E402
from gen.verification.cross_model import (  # noqa: E402
    Judgment,
    assert_different_families,
    combine_judgments,
    corroborated_confidence,
    model_family,
    status_disagreement,
    verify_confidence,
)


# --- model_family -------------------------------------------------------------

@pytest.mark.parametrize(
    "model,family",
    [
        ("claude-opus-4-8", "claude"),
        ("claude-3-5-sonnet", "claude"),
        ("gpt-4o", "openai"),
        ("gpt-4o-mini", "openai"),
        ("gemini-1.5-pro", "google"),
        ("llama3.1:8b", "llama"),
        ("mixtral-8x7b", "mistral"),
        ("qwen2.5:14b", "qwen"),
        ("deepseek-r1", "deepseek"),
        ("codex", "codex"),
        ("gpt-5.5-codex", "codex"),
    ],
)
def test_model_family_known(model, family):
    assert model_family(model) == family


def test_model_family_unknown_falls_back_to_leading_token():
    assert model_family("acme-supermodel-v2") == "acme"
    # Two different unknowns must not collide on a shared default.
    assert model_family("foo-1") != model_family("bar-1")


def test_model_family_empty_raises():
    with pytest.raises(ValueError):
        model_family("   ")


# --- the hard cross-model rule -----------------------------------------------

def test_same_family_raises_model_conflict():
    with pytest.raises(ModelConflictError):
        assert_different_families("claude-opus-4-8", "claude-3-5-haiku")
    with pytest.raises(ModelConflictError):
        assert_different_families("codex-pro", "codex-fast")


def test_different_families_pass():
    assert_different_families("claude-opus-4-8", "gpt-4o")  # no raise


def test_verify_confidence_rejects_same_family_verifier():
    """KEY negative test: a verifier on the generator's family is a config error."""
    j = Judgment(status=ClaimStatus.VERIFIED, confidence=0.9, model="claude-3-5-haiku")
    with pytest.raises(ModelConflictError):
        verify_confidence(generator_model="claude-opus-4-8", verifier=j)


def test_verify_confidence_rejects_same_family_second_judge():
    verifier = Judgment(ClaimStatus.VERIFIED, 0.8, "gpt-4o")
    bad_second = Judgment(ClaimStatus.VERIFIED, 0.8, "claude-3-5-haiku")
    with pytest.raises(ModelConflictError):
        verify_confidence(
            generator_model="claude-opus-4-8",
            verifier=verifier,
            second_judge=bad_second,
        )


def test_verify_confidence_passes_three_distinct_families():
    verifier = Judgment(ClaimStatus.VERIFIED, 0.8, "gpt-4o")
    second = Judgment(ClaimStatus.VERIFIED, 0.7, "llama3.1:70b")
    out = verify_confidence(
        generator_model="claude-opus-4-8",
        verifier=verifier,
        second_judge=second,
    )
    assert out.status is ClaimStatus.VERIFIED


# --- disagreement & confidence folding ---------------------------------------

def test_status_disagreement_distances():
    assert status_disagreement(ClaimStatus.VERIFIED, ClaimStatus.VERIFIED) == 0.0
    assert status_disagreement(ClaimStatus.VERIFIED, ClaimStatus.UNSUPPORTED) == 0.5
    assert status_disagreement(ClaimStatus.UNSUPPORTED, ClaimStatus.REFUTED) == 0.5
    assert status_disagreement(ClaimStatus.VERIFIED, ClaimStatus.REFUTED) == 1.0


def test_corroborated_confidence_boosts_and_clamps():
    assert corroborated_confidence(0.7, 0.7) == pytest.approx(0.91)
    assert corroborated_confidence(1.0, 0.0) == pytest.approx(1.0)
    assert 0.0 <= corroborated_confidence(2.0, -1.0) <= 1.0  # clamped inputs


def test_combine_no_second_returns_primary():
    p = Judgment(ClaimStatus.VERIFIED, 0.8, "gpt-4o")
    assert combine_judgments(p) is p


def test_combine_agreement_verified_boosts():
    p = Judgment(ClaimStatus.VERIFIED, 0.7, "gpt-4o")
    s = Judgment(ClaimStatus.VERIFIED, 0.7, "llama3.1:70b")
    out = combine_judgments(p, s)
    assert out.status is ClaimStatus.VERIFIED
    assert out.confidence == pytest.approx(0.91)


def test_combine_agreement_unsupported_averages():
    p = Judgment(ClaimStatus.UNSUPPORTED, 0.4, "gpt-4o")
    s = Judgment(ClaimStatus.UNSUPPORTED, 0.2, "llama3.1:70b")
    out = combine_judgments(p, s)
    assert out.status is ClaimStatus.UNSUPPORTED
    assert out.confidence == pytest.approx(0.3)


def test_combine_verified_vs_unsupported_goes_conservative():
    p = Judgment(ClaimStatus.VERIFIED, 0.9, "gpt-4o")
    s = Judgment(ClaimStatus.UNSUPPORTED, 0.6, "llama3.1:70b")
    out = combine_judgments(p, s)
    assert out.status is ClaimStatus.UNSUPPORTED          # never VERIFIED under doubt
    assert out.confidence == pytest.approx(0.6 * 0.5)     # min(0.9,0.6)*(1-0.5)


def test_combine_verified_vs_refuted_collapses_to_unsupported_zero():
    p = Judgment(ClaimStatus.VERIFIED, 0.9, "gpt-4o")
    s = Judgment(ClaimStatus.REFUTED, 0.9, "llama3.1:70b")
    out = combine_judgments(p, s)
    assert out.status is ClaimStatus.UNSUPPORTED          # pure conflict -> assert neither
    assert out.confidence == pytest.approx(0.0)           # min*(1-1.0)


def test_combine_unsupported_vs_refuted_prefers_refuted():
    p = Judgment(ClaimStatus.UNSUPPORTED, 0.5, "gpt-4o")
    s = Judgment(ClaimStatus.REFUTED, 0.8, "llama3.1:70b")
    out = combine_judgments(p, s)
    assert out.status is ClaimStatus.REFUTED
    assert out.confidence == pytest.approx(0.5 * 0.5)     # min(0.5,0.8)*(1-0.5)
