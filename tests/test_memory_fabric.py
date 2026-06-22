"""Unit tests for GATE ζ — the shared-memory fabric (``gen.memory_fabric``).

The module is deterministic and LLM-free: it builds a run-level audit receipt
(``build_memory_fabric_certificate``) from current run claims plus structural
recall results, and validates that receipt (``gate_zeta``). These tests exercise
both functions in isolation — the builder's VERIFIED-only deposit filter and its
recall mapping, and every distinct gate failure code plus the pass-on-empty path.

``recall_results`` is duck-typed by the module (it reads ``query``/``tau``/
``accepted`` and per-fact ``claim_id``/``score``/``sources``), so we feed it
lightweight ``SimpleNamespace`` stand-ins rather than importing ``gen.memory``.
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

RUN_ID = "run-zeta-001"


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
    """A structural stand-in for ``gen.memory.RecallResult`` (duck-typed)."""
    return SimpleNamespace(query=query, tau=tau, accepted=list(facts))


def _fact(claim_id: str, score: float, sources: tuple[str, ...] = ("https://example.org/a",)):
    return SimpleNamespace(claim_id=claim_id, score=score, sources=sources)


def _codes(result: GateResult) -> set[str]:
    return {failure.code for failure in result.failures}


# --- build_memory_fabric_certificate: deposit filter ------------------------

def test_build_deposits_only_verified_claims():
    state = _state(
        _claim("c-verified", status=ClaimStatus.VERIFIED),
        _claim("c-unverified", status=ClaimStatus.UNVERIFIED),
        _claim("c-refuted", status=ClaimStatus.REFUTED),
        _claim("c-unsupported", status=ClaimStatus.UNSUPPORTED),
    )

    cert = build_memory_fabric_certificate(state)

    assert [d.claim_id for d in cert.deposits] == ["c-verified"]
    assert cert.run_id == RUN_ID
    assert cert.produced_by == "memory_fabric"


def test_build_with_no_verified_claims_yields_empty_deposits():
    state = _state(_claim("c1", status=ClaimStatus.UNSUPPORTED))
    cert = build_memory_fabric_certificate(state)
    assert cert.deposits == []


def test_build_deposit_preserves_only_nonblank_source_ids():
    # A blank url_or_id carries no provenance and must not be deposited as a source.
    claim = _claim(
        "c1",
        sources=[_source("https://example.org/keep"), _source("   ", retrieved=True)],
    )
    cert = build_memory_fabric_certificate(_state(claim))
    assert cert.deposits[0].sources == ("https://example.org/keep",)


def test_build_passes_through_calibration_and_health():
    cert = build_memory_fabric_certificate(
        _state(),
        calibration_ready=True,
        health=MemoryHealthStatus.OK,
    )
    assert cert.calibration_ready is True
    assert cert.health is MemoryHealthStatus.OK


def test_build_defaults_to_not_enough_baseline_and_no_calibration():
    cert = build_memory_fabric_certificate(_state())
    assert cert.calibration_ready is False
    assert cert.health is MemoryHealthStatus.NOT_ENOUGH_BASELINE


# --- build_memory_fabric_certificate: recall mapping ------------------------

def test_build_maps_recall_results_to_links():
    results = [
        _recall_result(
            "  how to cool a motor  ",  # gets stripped
            0.4,
            _fact("prior-1", 0.1, ("src-1",)),
            _fact("prior-2", 0.3, ("src-2", "src-3")),
        ),
    ]
    cert = build_memory_fabric_certificate(_state(), recall_results=results)

    assert len(cert.recalls) == 2
    first, second = cert.recalls
    assert first.query == "how to cool a motor"  # stripped
    assert first.claim_id == "prior-1"
    assert first.score == pytest.approx(0.1)
    assert first.tau == pytest.approx(0.4)
    assert first.sources == ("src-1",)
    assert second.claim_id == "prior-2"
    assert second.sources == ("src-2", "src-3")


def test_build_recalls_carry_per_result_tau_including_none():
    results = [
        _recall_result("q1", None, _fact("p1", 0.2)),
        _recall_result("q2", 0.5, _fact("p2", 0.2)),
    ]
    cert = build_memory_fabric_certificate(_state(), recall_results=results)
    assert cert.recalls[0].tau is None
    assert cert.recalls[1].tau == pytest.approx(0.5)


def test_build_empty_recall_results_yields_no_recalls():
    cert = build_memory_fabric_certificate(_state(), recall_results=())
    assert cert.recalls == []


def test_build_skips_result_with_no_accepted_facts():
    results = [_recall_result("q-nothing", 0.5)]  # accepted is empty
    cert = build_memory_fabric_certificate(_state(), recall_results=results)
    assert cert.recalls == []


# --- gate_zeta: pass-on-empty ----------------------------------------------

def test_gate_passes_on_empty_certificate():
    state = _state()
    cert = build_memory_fabric_certificate(state)  # empty, NOT_ENOUGH_BASELINE
    result = gate_zeta(state, cert)
    assert isinstance(result, GateResult)
    assert result.gate == "zeta"
    assert result.passed is True
    assert result.failures == []


def test_gate_passes_full_healthy_certificate():
    claim = _claim("c1")
    state = _state(claim)
    cert = MemoryFabricCertificate(
        run_id=RUN_ID,
        deposits=[MemoryDeposit(claim_id="c1", sources=("https://example.org/a",))],
        recalls=[
            MemoryRecallLink(
                query="q",
                claim_id="prior-1",
                score=0.2,
                tau=0.5,
                sources=("src-1",),
            )
        ],
        calibration_ready=True,
        health=MemoryHealthStatus.OK,
    )
    result = gate_zeta(state, cert)
    assert result.passed is True


# --- gate_zeta: failure codes ----------------------------------------------

def test_gate_run_mismatch():
    state = _state(run_id=RUN_ID)
    cert = MemoryFabricCertificate(run_id="other-run")
    result = gate_zeta(state, cert)
    assert result.passed is False
    assert "MEMORY_RUN_MISMATCH" in _codes(result)


def test_gate_drift_alert_blocks_even_empty():
    state = _state()
    cert = MemoryFabricCertificate(run_id=RUN_ID, health=MemoryHealthStatus.DRIFT_ALERT)
    result = gate_zeta(state, cert)
    assert result.passed is False
    assert "MEMORY_DRIFT_ALERT" in _codes(result)


def test_gate_duplicate_deposit():
    claim = _claim("c1")
    state = _state(claim)
    dep = MemoryDeposit(claim_id="c1", sources=("https://example.org/a",))
    cert = MemoryFabricCertificate(run_id=RUN_ID, deposits=[dep, dep])
    result = gate_zeta(state, cert)
    failure = next(f for f in result.failures if f.code == "DUPLICATE_MEMORY_DEPOSIT")
    assert failure.claim_id == "c1"


def test_gate_deposit_unknown_claim():
    state = _state(_claim("c1"))
    cert = MemoryFabricCertificate(
        run_id=RUN_ID,
        deposits=[MemoryDeposit(claim_id="ghost", sources=("https://example.org/a",))],
    )
    result = gate_zeta(state, cert)
    failure = next(f for f in result.failures if f.code == "MEMORY_DEPOSIT_UNKNOWN_CLAIM")
    assert failure.claim_id == "ghost"


def test_gate_deposit_not_verified():
    # A deposit may only point at a VERIFIED claim; an UNVERIFIED target must fail.
    claim = _claim("c1", status=ClaimStatus.UNVERIFIED)
    state = _state(claim)
    cert = MemoryFabricCertificate(
        run_id=RUN_ID,
        deposits=[MemoryDeposit(claim_id="c1", sources=("https://example.org/a",))],
    )
    result = gate_zeta(state, cert)
    assert "MEMORY_DEPOSIT_NOT_VERIFIED" in _codes(result)


def test_gate_deposit_unsourced_when_no_retrieved_source():
    # The claim has a source string but it was never actually retrieved.
    claim = _claim("c1", sources=[_source("https://example.org/a", retrieved=False)])
    state = _state(claim)
    cert = MemoryFabricCertificate(
        run_id=RUN_ID,
        deposits=[MemoryDeposit(claim_id="c1", sources=("https://example.org/a",))],
    )
    result = gate_zeta(state, cert)
    assert "MEMORY_DEPOSIT_UNSOURCED" in _codes(result)


def test_gate_deposit_source_mismatch():
    # Deposit cites a source id that the claim does not actually carry.
    claim = _claim("c1", sources=[_source("https://example.org/a")])
    state = _state(claim)
    cert = MemoryFabricCertificate(
        run_id=RUN_ID,
        deposits=[MemoryDeposit(claim_id="c1", sources=("https://example.org/fabricated",))],
    )
    result = gate_zeta(state, cert)
    assert "MEMORY_DEPOSIT_SOURCE_MISMATCH" in _codes(result)


def test_gate_duplicate_recall():
    state = _state()
    link = MemoryRecallLink(
        query="q", claim_id="p1", score=0.1, tau=0.5, sources=("src-1",)
    )
    cert = MemoryFabricCertificate(
        run_id=RUN_ID,
        recalls=[link, link],
        calibration_ready=True,
        health=MemoryHealthStatus.OK,
    )
    result = gate_zeta(state, cert)
    failure = next(f for f in result.failures if f.code == "DUPLICATE_MEMORY_RECALL")
    assert failure.claim_id == "p1"


def test_gate_recall_without_calibration():
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
    assert "MEMORY_RECALL_WITHOUT_CALIBRATION" in _codes(result)


def test_gate_recall_without_health_clearance():
    state = _state()
    cert = MemoryFabricCertificate(
        run_id=RUN_ID,
        recalls=[
            MemoryRecallLink(query="q", claim_id="p1", score=0.1, tau=0.5, sources=("s",))
        ],
        calibration_ready=True,
        health=MemoryHealthStatus.NOT_ENOUGH_BASELINE,  # not OK
    )
    result = gate_zeta(state, cert)
    assert "MEMORY_RECALL_WITHOUT_HEALTH_CLEARANCE" in _codes(result)


def test_gate_recall_without_tau():
    state = _state()
    cert = MemoryFabricCertificate(
        run_id=RUN_ID,
        recalls=[
            MemoryRecallLink(query="q", claim_id="p1", score=0.1, tau=None, sources=("s",))
        ],
        calibration_ready=True,
        health=MemoryHealthStatus.OK,
    )
    result = gate_zeta(state, cert)
    failure = next(f for f in result.failures if f.code == "MEMORY_RECALL_WITHOUT_TAU")
    assert failure.claim_id == "p1"


def test_gate_recall_outside_band():
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
    failure = next(f for f in result.failures if f.code == "MEMORY_RECALL_OUTSIDE_BAND")
    assert failure.claim_id == "p1"


def test_gate_recall_score_equal_to_tau_is_in_band():
    # Boundary: score == tau is accepted (only score > tau is out of band).
    state = _state()
    cert = MemoryFabricCertificate(
        run_id=RUN_ID,
        recalls=[
            MemoryRecallLink(query="q", claim_id="p1", score=0.5, tau=0.5, sources=("s",))
        ],
        calibration_ready=True,
        health=MemoryHealthStatus.OK,
    )
    result = gate_zeta(state, cert)
    assert "MEMORY_RECALL_OUTSIDE_BAND" not in _codes(result)
    assert result.passed is True


def test_gate_recall_unsourced_when_blank_source_id():
    # A blank source id within the tuple means provenance was not preserved.
    state = _state()
    cert = MemoryFabricCertificate(
        run_id=RUN_ID,
        recalls=[
            MemoryRecallLink(query="q", claim_id="p1", score=0.1, tau=0.5, sources=("  ",))
        ],
        calibration_ready=True,
        health=MemoryHealthStatus.OK,
    )
    result = gate_zeta(state, cert)
    failure = next(f for f in result.failures if f.code == "MEMORY_RECALL_UNSOURCED")
    assert failure.claim_id == "p1"


# --- determinism + property-based -------------------------------------------

def test_build_is_deterministic():
    # A5 reproducibility: identical run state -> byte-identical certificate.
    state = _state(
        _claim("c1"),
        _claim("c2", status=ClaimStatus.UNSUPPORTED),
    )
    results = [_recall_result("q", 0.5, _fact("p1", 0.2))]
    a = build_memory_fabric_certificate(state, recall_results=results)
    b = build_memory_fabric_certificate(state, recall_results=results)
    assert a.deposits == b.deposits
    assert a.recalls == b.recalls
    assert a.run_id == b.run_id


def test_certificate_run_id_tracks_question_run_id():
    state = _state(run_id="run-xyz")
    cert = build_memory_fabric_certificate(state)
    assert cert.run_id == "run-xyz" == state.question.run_id


_STATUSES = list(ClaimStatus)


@settings(max_examples=75)
@given(statuses=st.lists(st.sampled_from(_STATUSES), max_size=12))
def test_deposit_count_equals_verified_count(statuses):
    # INVARIANT: the deposit set is exactly the VERIFIED claims, for any status mix.
    claims = [_claim(f"c{i}", status=status) for i, status in enumerate(statuses)]
    state = _state(*claims)
    cert = build_memory_fabric_certificate(state)

    verified_ids = [c.id for c in claims if c.status is ClaimStatus.VERIFIED]
    assert [d.claim_id for d in cert.deposits] == verified_ids


@settings(max_examples=75)
@given(statuses=st.lists(st.sampled_from(_STATUSES), max_size=12))
def test_built_certificate_always_passes_gate(statuses):
    # INVARIANT: a certificate built from well-sourced claims (no recalls, default
    # health) is internally consistent and must satisfy its own gate.
    claims = [_claim(f"c{i}", status=status) for i, status in enumerate(statuses)]
    state = _state(*claims)
    cert = build_memory_fabric_certificate(state)
    assert gate_zeta(state, cert).passed is True
