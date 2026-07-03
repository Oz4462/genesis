"""Tests for GATE β — proving the Phase β guarantee WITHOUT any LLM.

These tests are the executable form of PHASE_BETA.md §5 acceptance criteria. They
run with plain pytest, no models, no network. If these are green, the β gate logic
is provably correct; the synthesizer then only has to feed it honest data.

The β guarantee in one line: an Approach asserted as real must be grounded in a
VERIFIED claim, and every claim it leans on must be α-sound. A fabricated approach
is the β-equivalent of a sourceless fact — and is caught here.

Run:  pytest tests/test_gate_beta.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make src importable without packaging during early dev.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.errors import UngroundedApproachError  # noqa: E402
from gen.core.state import (  # noqa: E402
    Approach,
    Claim,
    ClaimStatus,
    Question,
    RunState,
    SolutionReport,
    SourceRef,
    SourceSupport,
)
from gen.verification.gates import gate_beta  # noqa: E402


# --- builders ----------------------------------------------------------------

def _src(url: str, retrieved: bool = True) -> SourceRef:
    return SourceRef(url_or_id=url, retrieved=retrieved, support=SourceSupport.SUPPORTS)


def _claim(
    cid: str,
    text: str,
    *,
    status: ClaimStatus = ClaimStatus.VERIFIED,
    confidence: float = 0.9,
    retrieved: bool = True,
) -> Claim:
    return Claim(
        id=cid,
        text=text,
        sources=[_src(f"https://example.org/{cid}", retrieved=retrieved)],
        status=status,
        confidence=confidence,
        verification=[_src(f"https://independent.org/{cid}")]
        if status is ClaimStatus.VERIFIED
        else [],
    )


def _state(claims, approaches, gaps=None) -> RunState:
    st = RunState(question=Question(raw="p", run_id="r1"))
    st.claims = claims
    st.approaches = approaches
    st.solution_report = SolutionReport(
        run_id="r1",
        problem="p",
        approaches=approaches,
        gaps=gaps or [],
        claim_ids_used=[cid for a in approaches for cid in (*a.grounding, *a.tradeoffs)],
    )
    return st


# --- B1/B2: the happy path (real solution space with alternatives) -----------

def test_passes_with_multiple_grounded_approaches():
    """B1/B2: ≥2 approaches, each grounded in a VERIFIED claim, trade-offs sound."""
    c1 = _claim("c1", "Token bucket is used to rate-limit production APIs.")
    c2 = _claim("c2", "Token bucket allows short bursts up to the bucket size.")
    c3 = _claim("c3", "Leaky bucket is used to smooth API request rates.")
    a1 = Approach(id="a1", name="Token bucket", grounding=["c1"], tradeoffs=["c2"])
    a2 = Approach(id="a2", name="Leaky bucket", grounding=["c3"])
    result = gate_beta(_state([c1, c2, c3], [a1, a2]))
    assert result.passed, result.failures
    assert len([a for a in [a1, a2]]) >= 2  # the report carries real alternatives


def test_fails_when_no_solution_report():
    """B-0: a run without an assembled solution report cannot pass."""
    st = RunState(question=Question(raw="p", run_id="r1"))
    result = gate_beta(st)
    assert not result.passed
    assert any(f.code == "NO_SOLUTION_REPORT" for f in result.failures)


# --- B1: grounding is structurally mandatory ---------------------------------

def test_ungrounded_approach_cannot_be_constructed():
    """The core β guard: constructing an Approach with no grounding raises."""
    with pytest.raises(UngroundedApproachError):
        Approach(id="x", name="ghost approach", grounding=[])


def test_gate_backstops_ungrounded_approach():
    """Independent backstop: an asserted approach with no grounding fails the gate,
    even though the constructor would normally prevent it from existing."""
    c1 = _claim("c1", "A real approach exists.")
    a = Approach(id="a1", name="Real", grounding=["c1"])
    a.grounding = []  # simulate a buggy/adversarial synthesizer bypassing the guard
    result = gate_beta(_state([c1], [a]))
    assert not result.passed
    assert any(f.code == "UNGROUNDED_APPROACH" for f in result.failures)


def test_fails_on_grounding_unknown_claim():
    """B-2: grounding that points to a non-existent claim must fail."""
    a = Approach(id="a1", name="Phantom", grounding=["ghost"])
    result = gate_beta(_state([], [a]))
    assert not result.passed
    assert any(f.code == "GROUNDING_UNKNOWN_CLAIM" for f in result.failures)


# --- B3: the heart of β — grounding must be VERIFIED -------------------------

def test_fails_when_grounding_not_verified():
    """B-3: an approach grounded only in an UNSUPPORTED claim is a fabricated
    approach and must be rejected."""
    c = _claim(
        "c1",
        "This speculative approach supposedly works.",
        status=ClaimStatus.UNSUPPORTED,
        confidence=0.1,
    )
    a = Approach(id="a1", name="Speculative", grounding=["c1"])
    result = gate_beta(_state([c], [a]))
    assert not result.passed
    assert any(f.code == "GROUNDING_NOT_VERIFIED" for f in result.failures)


def test_fails_when_grounding_under_confident():
    """B-3: VERIFIED grounding below τ is rejected."""
    c = _claim("c1", "Borderline grounding.", status=ClaimStatus.VERIFIED, confidence=0.5)
    a = Approach(id="a1", name="Borderline", grounding=["c1"])
    result = gate_beta(_state([c], [a]), confidence_threshold=0.7)
    assert not result.passed
    assert any(f.code == "GROUNDING_NOT_VERIFIED" for f in result.failures)


def test_fails_on_unverified_status_grounding():
    """B-3: grounding still in UNVERIFIED (skeptic never ran) is rejected."""
    c = _claim("c1", "Not yet checked.", status=ClaimStatus.UNVERIFIED, confidence=0.0)
    a = Approach(id="a1", name="Unchecked", grounding=["c1"])
    result = gate_beta(_state([c], [a]))
    assert not result.passed
    assert any(f.code == "GROUNDING_NOT_VERIFIED" for f in result.failures)


# --- B4: the false-uniqueness trap (REFUTED grounding) ----------------------

def test_false_uniqueness_trap_caught():
    """B4: a refuted 'only way' claim cannot ground an approach asserted as fact.

    The trap question ('why is X the ONLY way to do Y?') yields a uniqueness claim
    that the skeptic REFUTES. Trying to present it as a grounded approach is caught
    by the shared α-soundness check (REFUTED_AS_FACT) — exactly as α caught it."""
    c = _claim(
        "c1",
        "Token bucket is the only way to rate-limit an API.",
        status=ClaimStatus.REFUTED,
        confidence=0.2,
    )
    a = Approach(id="a1", name="Token bucket (sole)", grounding=["c1"])
    result = gate_beta(_state([c], [a]))
    assert not result.passed
    assert any(f.code == "REFUTED_AS_FACT" for f in result.failures)


# --- B5/B6: trade-offs must be honest ---------------------------------------

def test_fails_on_unknown_tradeoff_claim():
    """B-5: a trade-off pointing to a non-existent claim must fail."""
    c1 = _claim("c1", "Real approach grounding.")
    a = Approach(id="a1", name="Real", grounding=["c1"], tradeoffs=["ghost"])
    result = gate_beta(_state([c1], [a]))
    assert not result.passed
    assert any(f.code == "TRADEOFF_UNKNOWN_CLAIM" for f in result.failures)


def test_unsupported_tradeoff_must_be_flagged():
    """B-6: an UNSUPPORTED trade-off may appear only if flagged as a gap."""
    c1 = _claim("c1", "Real approach grounding.")
    c2 = _claim(
        "c2",
        "Alleged downside with no independent support.",
        status=ClaimStatus.UNSUPPORTED,
        confidence=0.1,
    )
    a = Approach(id="a1", name="Real", grounding=["c1"], tradeoffs=["c2"])

    # Asserted as a real trade-off, NOT flagged -> must fail.
    assert not gate_beta(_state([c1, c2], [a])).passed

    # Same trade-off, but flagged as a gap -> passes.
    good = _state([c1, c2], [a], gaps=["Alleged downside with no independent support."])
    assert gate_beta(good).passed, gate_beta(good).failures


def test_fails_on_dead_citation_in_grounding():
    """B6/α-soundness preserved: a grounding claim citing an unretrieved source fails."""
    c = _claim("c1", "Grounded but dead source.", retrieved=False)
    a = Approach(id="a1", name="Dead", grounding=["c1"])
    result = gate_beta(_state([c], [a]))
    assert not result.passed
    assert any(f.code == "DEAD_CITATION" for f in result.failures)


# --- B5/β: abstention --------------------------------------------------------

def test_abstention_passes():
    """B5: no groundable approach -> zero approaches asserted + honest gap -> passes."""
    st = _state(
        [],
        [],
        gaps=["No approach could be independently grounded for this problem."],
    )
    result = gate_beta(st)
    assert result.passed, result.failures
    assert st.solution_report.approaches == []


def test_unverified_tradeoff_must_be_flagged():
    """W1 fix: an UNVERIFIED trade-off (not only UNSUPPORTED) may appear only if
    flagged. The gate is the independent backstop — it must not trust the synthesizer
    to have filtered it out (PHASE_BETA.md §4 B-6)."""
    c1 = _claim("c1", "Real verified grounding.")
    c2 = Claim(
        id="c2",
        text="An unchecked alleged property.",
        sources=[_src("https://example.org/c2")],
        status=ClaimStatus.UNVERIFIED,
        confidence=0.2,
    )
    a = Approach(id="a1", name="Real", grounding=["c1"], tradeoffs=["c2"])

    # Asserted as a real trade-off, NOT flagged -> must fail.
    assert not gate_beta(_state([c1, c2], [a])).passed

    # Same trade-off, flagged as a gap -> passes.
    good = _state([c1, c2], [a], gaps=["An unchecked alleged property."])
    assert gate_beta(good).passed, gate_beta(good).failures
