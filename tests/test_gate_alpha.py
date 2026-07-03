"""Tests for GATE α — proving the anti-hallucination guarantee WITHOUT any LLM.

These tests are the executable form of PHASE_ALPHA.md §5 acceptance criteria.
They run with plain pytest, no models, no network. If these are green, the gate
logic is provably correct; the agents then only have to feed it honest data.

Run:  pytest tests/test_gate_alpha.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make src importable without packaging during early dev.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.state import (  # noqa: E402
    Claim,
    ClaimStatus,
    Question,
    Report,
    RunState,
    SourceRef,
    SourceSupport,
)
from gen.verification.gates import gate_alpha  # noqa: E402


def _src(url: str, retrieved: bool = True) -> SourceRef:
    return SourceRef(
        url_or_id=url, retrieved=retrieved, support=SourceSupport.SUPPORTS
    )


def _state_with(claims, report) -> RunState:
    st = RunState(question=Question(raw="q", run_id="r1"))
    st.claims = claims
    st.report = report
    return st


def test_passes_when_all_facts_verified_and_sourced():
    """A1/A2: a clean report with a verified, sourced claim passes."""
    c = Claim(
        id="c1",
        text="build123d is built on the Open Cascade kernel.",
        sources=[_src("https://build123d.readthedocs.io")],
        status=ClaimStatus.VERIFIED,
        confidence=0.9,
        verification=[_src("https://dev-iz.com/build123d")],
    )
    report = Report(
        run_id="r1",
        question="q",
        body="build123d is built on the Open Cascade kernel.",
        statement_to_claim={"build123d is built on the Open Cascade kernel.": "c1"},
    )
    result = gate_alpha(_state_with([c], report))
    assert result.passed, result.failures


def test_fails_on_unsourced_statement():
    """A1: a report sentence mapping to a non-existent claim must fail."""
    report = Report(
        run_id="r1",
        question="q",
        body="The sky is definitely green.",
        statement_to_claim={"The sky is definitely green.": "ghost"},
    )
    result = gate_alpha(_state_with([], report))
    assert not result.passed
    assert any(f.code == "UNSOURCED_STATEMENT" for f in result.failures)


def test_fails_when_refuted_claim_used_as_fact():
    """A3: a refuted claim asserted as fact must be caught."""
    c = Claim(
        id="c1",
        text="X is the only method for Y.",
        sources=[_src("https://example.org/x")],
        status=ClaimStatus.REFUTED,
        confidence=0.2,
    )
    report = Report(
        run_id="r1",
        question="q",
        body="X is the only method for Y.",
        statement_to_claim={"X is the only method for Y.": "c1"},
    )
    result = gate_alpha(_state_with([c], report))
    assert not result.passed
    assert any(f.code == "REFUTED_AS_FACT" for f in result.failures)


def test_unsupported_must_be_flagged():
    """A4: an unsupported claim is allowed only if flagged as a gap."""
    c = Claim(
        id="c1",
        text="This speculative thing is true.",
        sources=[_src("https://example.org/s")],
        status=ClaimStatus.UNSUPPORTED,
        confidence=0.1,
    )
    # Asserted as fact, NOT flagged -> must fail.
    bad = Report(
        run_id="r1",
        question="q",
        body="This speculative thing is true.",
        statement_to_claim={"This speculative thing is true.": "c1"},
    )
    assert not gate_alpha(_state_with([c], bad)).passed

    # Same claim, but flagged as a gap -> passes.
    good = Report(
        run_id="r1",
        question="q",
        body="(see gaps)",
        statement_to_claim={"This speculative thing is true.": "c1"},
        gaps=["This speculative thing is true."],
    )
    assert gate_alpha(_state_with([c], good)).passed


def test_fails_on_low_confidence_verified():
    """Condition 4: VERIFIED below threshold is rejected."""
    c = Claim(
        id="c1",
        text="Borderline claim.",
        sources=[_src("https://example.org/a")],
        status=ClaimStatus.VERIFIED,
        confidence=0.5,
    )
    report = Report(
        run_id="r1",
        question="q",
        body="Borderline claim.",
        statement_to_claim={"Borderline claim.": "c1"},
    )
    result = gate_alpha(_state_with([c], report), confidence_threshold=0.7)
    assert not result.passed
    assert any(f.code == "LOW_CONFIDENCE" for f in result.failures)


def test_fails_on_dead_citation():
    """Condition 5: a cited-but-unretrieved source is rejected."""
    c = Claim(
        id="c1",
        text="Claim with a dead citation.",
        sources=[_src("https://example.org/missing", retrieved=False)],
        status=ClaimStatus.VERIFIED,
        confidence=0.9,
    )
    report = Report(
        run_id="r1",
        question="q",
        body="Claim with a dead citation.",
        statement_to_claim={"Claim with a dead citation.": "c1"},
    )
    result = gate_alpha(_state_with([c], report))
    assert not result.passed
    assert any(f.code == "DEAD_CITATION" for f in result.failures)


def test_unsourced_claim_cannot_be_constructed():
    """The core guard: constructing a Claim with no sources raises."""
    import pytest
    from gen.core.errors import UnsourcedClaimError

    with pytest.raises(UnsourcedClaimError):
        Claim(id="x", text="a sourceless fact", sources=[])


def test_gate_backstops_unsourced_asserted_claim():
    """Independent backstop: an asserted claim with no source fails the gate,
    even though the ledger would normally prevent such a claim from existing."""
    c = Claim(
        id="c1",
        text="A claim that lost its sources.",
        sources=[_src("https://example.org/a")],
        status=ClaimStatus.VERIFIED,
        confidence=0.9,
    )
    c.sources = []  # simulate a buggy/adversarial assembler bypassing the ledger
    report = Report(
        run_id="r1",
        question="q",
        body="A claim that lost its sources.",
        statement_to_claim={"A claim that lost its sources.": "c1"},
    )
    result = gate_alpha(_state_with([c], report))
    assert not result.passed
    assert any(f.code == "UNSOURCED_CLAIM" for f in result.failures)


def test_gate_backstops_sentence_claim_mismatch():
    """Independent backstop: the asserted sentence must match the cited claim."""
    c = Claim(
        id="c1",
        text="build123d uses the Open Cascade kernel.",
        sources=[_src("https://example.org/a")],
        status=ClaimStatus.VERIFIED,
        confidence=0.9,
    )
    report = Report(
        run_id="r1",
        question="q",
        body="The moon is made of cheese.",
        statement_to_claim={"The moon is made of cheese.": "c1"},  # misattributed!
    )
    result = gate_alpha(_state_with([c], report))
    assert not result.passed
    assert any(f.code == "SENTENCE_CLAIM_MISMATCH" for f in result.failures)


def test_unverified_claim_as_fact_must_be_flagged():
    """Independent backstop: an UNVERIFIED claim asserted as fact must fail unless
    flagged. The gate no longer passes a not-verified claim presented as truth (it
    previously only caught UNSUPPORTED) — closes the shared UNVERIFIED gap."""
    c = Claim(
        id="c1",
        text="An unverified statement.",
        sources=[_src("https://example.org/u")],
        status=ClaimStatus.UNVERIFIED,
        confidence=0.2,
    )
    bad = Report(
        run_id="r1",
        question="q",
        body="An unverified statement.",
        statement_to_claim={"An unverified statement.": "c1"},
    )
    result = gate_alpha(_state_with([c], bad))
    assert not result.passed
    assert any(f.code == "UNSUPPORTED_NOT_FLAGGED" for f in result.failures)

    # Flagged as a gap -> allowed.
    good = Report(
        run_id="r1",
        question="q",
        body="(see gaps)",
        statement_to_claim={"An unverified statement.": "c1"},
        gaps=["An unverified statement."],
    )
    assert gate_alpha(_state_with([c], good)).passed
