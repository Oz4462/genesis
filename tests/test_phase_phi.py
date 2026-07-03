"""Phase φ acceptance — grounded divergence (HORIZON.md §5).

Gate-first, deterministic, LLM-free. The decisive teeth: an invented possibility
(no anchor) is structurally impossible (constructor raises), an anchor that is not a
VERIFIED claim is rejected by GATE φ, and a divergence that claims completeness
(grounded_sample=False) fails. Abstention (zero possibilities) is valid.
"""

from __future__ import annotations

import pytest

from gen.core.errors import UngroundedPossibilityError
from gen.core.state import (
    Claim,
    ClaimStatus,
    Divergence,
    Possibility,
    Spark,
    SourceRef,
)
from gen.verification import gate_phi


def _verified_claim(cid: str = "c_pcm", conf: float = 0.9) -> Claim:
    return Claim(
        id=cid,
        text="Phase-change materials store latent heat at constant temperature.",
        sources=[SourceRef(url_or_id="src://pcm", retrieved=True)],
        status=ClaimStatus.VERIFIED,
        confidence=conf,
    )


def _spark() -> Spark:
    return Spark(id="s1", raw="something that smooths out temperature swings")


def _poss(grounding: list[str], pid: str = "p1") -> Possibility:
    return Possibility(
        id=pid, statement="store heat in a phase-change material",
        mechanism="latent-heat storage", grounding=grounding,
    )


# --- data-model teeth ---------------------------------------------------------
def test_possibility_without_grounding_is_impossible():
    with pytest.raises(UngroundedPossibilityError):
        Possibility(id="p0", statement="invented direction", mechanism="?", grounding=[])


# --- GATE φ -------------------------------------------------------------------
def test_grounded_possibility_passes():
    claim = _verified_claim()
    div = Divergence(spark=_spark(), possibilities=[_poss([claim.id])], grounded_sample=True)
    res = gate_phi(div, [claim])
    assert res.passed and res.failures == []


def test_unknown_grounding_claim_fails():
    div = Divergence(spark=_spark(), possibilities=[_poss(["c_missing"])], grounded_sample=True)
    res = gate_phi(div, [_verified_claim()])
    assert not res.passed
    assert any(f.code == "GROUNDING_UNKNOWN_CLAIM" for f in res.failures)


def test_non_verified_anchor_fails():
    unver = Claim(id="c_u", text="maybe", sources=[SourceRef(url_or_id="s", retrieved=True)],
                  status=ClaimStatus.UNSUPPORTED, confidence=0.0)
    div = Divergence(spark=_spark(), possibilities=[_poss([unver.id])], grounded_sample=True)
    res = gate_phi(div, [unver])
    assert not res.passed
    assert any(f.code == "GROUNDING_NOT_VERIFIED" for f in res.failures)


def test_underconfident_anchor_fails():
    weak = _verified_claim(conf=0.3)
    div = Divergence(spark=_spark(), possibilities=[_poss([weak.id])], grounded_sample=True)
    res = gate_phi(div, [weak], confidence_threshold=0.7)
    assert not res.passed
    assert any(f.code == "GROUNDING_NOT_VERIFIED" for f in res.failures)


def test_claiming_completeness_fails():
    claim = _verified_claim()
    div = Divergence(spark=_spark(), possibilities=[_poss([claim.id])], grounded_sample=False)
    res = gate_phi(div, [claim])
    assert not res.passed
    assert any(f.code == "NOT_GROUNDED_SAMPLE" for f in res.failures)


def test_abstention_passes():
    div = Divergence(spark=_spark(), possibilities=[], grounded_sample=True)
    res = gate_phi(div, [])
    assert res.passed and res.failures == []
