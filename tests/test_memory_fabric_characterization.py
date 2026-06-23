"""Characterization (facade-killer) tests for GATE ζ — ``gen.memory_fabric``.

The legacy ``test_memory_fabric.py`` exercises every individual code path. This file
takes the complementary, adversarial angle required by the depth-audit: it proves the
module is NOT a hollow facade — i.e. its headline outputs are genuinely *derived from*
the run's claims and the certificate's contents, not canned constants. Each test would
FAIL if ``build_memory_fabric_certificate`` ignored its inputs or ``gate_zeta`` were a
rubber stamp that always returned ``passed=True``.

Concretely, the facade-killer assertions check:
* the deposit set tracks the *VERIFIED* subset of claims and changes when that subset
  changes (input is consumed, not constant);
* ``run_id`` is copied from the live question, not hardcoded;
* the gate flips ``passed`` from True to False the moment a documented violation is
  introduced, emitting the exact ``GateFailure.code`` — i.e. the gate has teeth.

``recall_results`` is duck-typed by the module (it reads ``query``/``tau``/``accepted``
and per-fact ``claim_id``/``score``/``sources``), so structural ``SimpleNamespace``
stand-ins are fed in rather than importing ``gen.memory`` — exactly as the module's
docstring intends.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gen.core.interfaces import GateResult
from gen.core.state import (
    Claim,
    ClaimStatus,
    MemoryDeposit,
    MemoryFabricCertificate,
    MemoryHealthStatus,
    MemoryRecallLink,
    Question,
    RunState,
    SourceRef,
    SourceSupport,
)
from gen.memory_fabric import build_memory_fabric_certificate, gate_zeta

RUN_ID = "run-zeta-char-001"


# --- builders ---------------------------------------------------------------

def _source(url_or_id: str = "https://example.org/a", *, retrieved: bool = True) -> SourceRef:
    return SourceRef(
        url_or_id=url_or_id,
        retrieved=retrieved,
        content_hash="h",
        support=SourceSupport.SUPPORTS,
    )


def _claim(
    claim_id: str,
    *,
    status: ClaimStatus = ClaimStatus.VERIFIED,
    sources: list[SourceRef] | None = None,
) -> Claim:
    return Claim(
        id=claim_id,
        text=f"claim {claim_id}",
        sources=sources if sources is not None else [_source()],
        status=status,
    )


def _state(*claims: Claim, run_id: str = RUN_ID) -> RunState:
    return RunState(question=Question(raw="q", run_id=run_id), claims=list(claims))


def _recall_result(query: str, tau: float | None, *facts: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(query=query, tau=tau, accepted=list(facts))


def _fact(claim_id: str, score: float, sources: tuple[str, ...] = ("https://example.org/a",)):
    return SimpleNamespace(claim_id=claim_id, score=score, sources=sources)


def _codes(result: GateResult) -> set[str]:
    return {failure.code for failure in result.failures}


# --- spec (1): builder genuinely filters/derives from run claims ------------

def test_build_filters_verified_and_drops_refuted_preserving_sources():
    """A VERIFIED claim (with a retrieved source) and a REFUTED claim go in;
    exactly ONE deposit — for the VERIFIED id — comes out, with its source ids
    preserved, and the certificate's run_id is copied from the live question.

    Facade-killer: a constant/canned builder could not selectively keep the
    VERIFIED id, carry its specific source url, AND echo the question's run_id.
    """
    verified = _claim(
        "c-verified",
        status=ClaimStatus.VERIFIED,
        sources=[_source("https://example.org/keep")],
    )
    refuted = _claim("c-refuted", status=ClaimStatus.REFUTED)
    state = _state(verified, refuted, run_id="run-derived-xyz")

    cert = build_memory_fabric_certificate(state)

    assert [d.claim_id for d in cert.deposits] == ["c-verified"]
    assert cert.deposits[0].sources == ("https://example.org/keep",)
    assert cert.deposits[0].sources != ()  # non-empty provenance preserved
    # run_id is DERIVED from the question, not a constant baked into the module.
    assert cert.run_id == state.question.run_id == "run-derived-xyz"


def test_deposit_set_changes_when_verified_subset_changes():
    """The deposit list is a genuine function of which claims are VERIFIED.

    Facade-killer: flipping one claim's status from VERIFIED to REFUTED must
    remove its deposit. A canned output would not react to the input change.
    """
    both_verified = _state(
        _claim("a", status=ClaimStatus.VERIFIED),
        _claim("b", status=ClaimStatus.VERIFIED),
    )
    one_refuted = _state(
        _claim("a", status=ClaimStatus.VERIFIED),
        _claim("b", status=ClaimStatus.REFUTED),
    )

    cert_both = build_memory_fabric_certificate(both_verified)
    cert_one = build_memory_fabric_certificate(one_refuted)

    assert [d.claim_id for d in cert_both.deposits] == ["a", "b"]
    assert [d.claim_id for d in cert_one.deposits] == ["a"]
    assert cert_both.deposits != cert_one.deposits


def test_recall_links_are_derived_from_recall_results():
    """Recall links mirror the per-result query/tau and per-fact id/score/sources,
    proving the recall mapping consumes its structural input rather than canning it.
    """
    results = [_recall_result("  cool a motor  ", 0.42, _fact("prior-7", 0.13, ("s-9",)))]
    cert = build_memory_fabric_certificate(state := _state(), recall_results=results)
    assert state.question.run_id == RUN_ID  # state used; silence linters
    (link,) = cert.recalls
    assert link.query == "cool a motor"  # stripped, not constant
    assert link.claim_id == "prior-7"
    assert link.score == pytest.approx(0.13)
    assert link.tau == pytest.approx(0.42)
    assert link.sources == ("s-9",)


# --- spec (2): honest abstention on empty certificate -----------------------

def test_gate_passes_empty_certificate_with_honest_abstention():
    """No deposits + no recalls + NOT_ENOUGH_BASELINE is valid abstention.

    This is the one case where ``passed=True`` is correct; the rest of this file
    proves the gate is NOT a blanket rubber stamp.
    """
    state = _state()
    cert = build_memory_fabric_certificate(state)
    assert cert.deposits == []
    assert cert.recalls == []
    assert cert.health is MemoryHealthStatus.NOT_ENOUGH_BASELINE
    result = gate_zeta(state, cert)
    assert result.gate == "zeta"
    assert result.passed is True
    assert result.failures == []


# --- spec (3): documented fail-loud deposit/health/run paths ----------------

def test_gate_deposit_not_verified_fails_loud():
    claim = _claim("c1", status=ClaimStatus.UNVERIFIED)
    state = _state(claim)
    cert = MemoryFabricCertificate(
        run_id=RUN_ID,
        deposits=[MemoryDeposit(claim_id="c1", sources=("https://example.org/a",))],
    )
    result = gate_zeta(state, cert)
    assert result.passed is False
    failure = next(f for f in result.failures if f.code == "MEMORY_DEPOSIT_NOT_VERIFIED")
    assert failure.claim_id == "c1"


def test_gate_run_mismatch_fails_loud():
    state = _state(run_id=RUN_ID)
    cert = MemoryFabricCertificate(run_id="a-different-run")
    result = gate_zeta(state, cert)
    assert result.passed is False
    assert "MEMORY_RUN_MISMATCH" in _codes(result)


def test_gate_drift_alert_fails_loud():
    state = _state()
    cert = MemoryFabricCertificate(run_id=RUN_ID, health=MemoryHealthStatus.DRIFT_ALERT)
    result = gate_zeta(state, cert)
    assert result.passed is False
    assert "MEMORY_DRIFT_ALERT" in _codes(result)


# --- spec (4): recall-band fail-loud paths ----------------------------------

def test_gate_recall_without_calibration_fails_loud():
    state = _state()
    cert = MemoryFabricCertificate(
        run_id=RUN_ID,
        recalls=[
            MemoryRecallLink(query="q", claim_id="p1", score=0.1, tau=0.5, sources=("s",))
        ],
        calibration_ready=False,  # the defect under test
        health=MemoryHealthStatus.OK,
    )
    result = gate_zeta(state, cert)
    assert result.passed is False
    assert "MEMORY_RECALL_WITHOUT_CALIBRATION" in _codes(result)


def test_gate_recall_outside_band_fails_loud():
    state = _state()
    cert = MemoryFabricCertificate(
        run_id=RUN_ID,
        recalls=[
            # score 0.9 exceeds tau 0.5 -> reuse is outside the calibrated band.
            MemoryRecallLink(query="q", claim_id="p1", score=0.9, tau=0.5, sources=("s",))
        ],
        calibration_ready=True,
        health=MemoryHealthStatus.OK,
    )
    result = gate_zeta(state, cert)
    assert result.passed is False
    failure = next(f for f in result.failures if f.code == "MEMORY_RECALL_OUTSIDE_BAND")
    assert failure.claim_id == "p1"


# --- the gate has teeth: a single violation flips passed True -> False -------

def test_gate_is_not_a_rubber_stamp_single_defect_flips_verdict():
    """Take a fully-healthy certificate (passes), then introduce exactly ONE
    documented violation; the gate must flip to ``passed=False``.

    Facade-killer: an always-True gate would keep passing. The transition proves
    the verdict is computed from certificate contents, per 'a gate without a test
    does not exist'.
    """
    claim = _claim("c1")
    state = _state(claim)
    healthy = MemoryFabricCertificate(
        run_id=RUN_ID,
        deposits=[MemoryDeposit(claim_id="c1", sources=("https://example.org/a",))],
        recalls=[
            MemoryRecallLink(query="q", claim_id="p1", score=0.2, tau=0.5, sources=("src-1",))
        ],
        calibration_ready=True,
        health=MemoryHealthStatus.OK,
    )
    assert gate_zeta(state, healthy).passed is True

    # Same certificate, but the recall now exceeds its band — one defect only.
    tampered = MemoryFabricCertificate(
        run_id=RUN_ID,
        deposits=healthy.deposits,
        recalls=[
            MemoryRecallLink(query="q", claim_id="p1", score=0.99, tau=0.5, sources=("src-1",))
        ],
        calibration_ready=True,
        health=MemoryHealthStatus.OK,
    )
    tampered_result = gate_zeta(state, tampered)
    assert tampered_result.passed is False
    assert "MEMORY_RECALL_OUTSIDE_BAND" in _codes(tampered_result)


# --- property: the gate is monotone-honest about VERIFIED-only deposits ------

_STATUSES = list(ClaimStatus)


@settings(max_examples=80)
@given(statuses=st.lists(st.sampled_from(_STATUSES), min_size=1, max_size=10))
def test_property_built_certificate_passes_iff_built_from_claims(statuses):
    """INVARIANT (facade-killer at scale): a certificate the builder produced from
    well-sourced claims always passes its own gate, AND its deposits are exactly the
    VERIFIED ids — for ANY status mix. If the builder silently deposited a non-VERIFIED
    claim, the gate would catch it and this property would fail.
    """
    claims = [_claim(f"c{i}", status=status) for i, status in enumerate(statuses)]
    state = _state(*claims)
    cert = build_memory_fabric_certificate(state)

    verified_ids = [c.id for c in claims if c.status is ClaimStatus.VERIFIED]
    assert [d.claim_id for d in cert.deposits] == verified_ids
    assert gate_zeta(state, cert).passed is True
