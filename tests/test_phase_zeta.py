"""Phase zeta acceptance — shared, conformal-gated memory fabric.

Zeta certifies the connective tissue above ANAMNESIS/trust-core: only VERIFIED facts
enter shared memory, recalled prior facts keep provenance, accepted recall needs a ready
conformal threshold, and drift alerts block reuse.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.state import (  # noqa: E402
    Claim,
    ClaimStatus,
    MemoryDeposit,
    MemoryFabricCertificate,
    MemoryHealthStatus,
    MemoryRecallLink,
    Question,
    RunState,
    SourceRef,
)
from gen.memory import VerifiedFactsLibrary  # noqa: E402
from gen.memory_fabric import build_memory_fabric_certificate, gate_zeta  # noqa: E402


_BASIS = {
    "standard gravity is 9.80665 m/s^2": 0,
    "speed of light is 299792458 m/s": 1,
    "unrelated query": 7,
}


def _embedder():
    def embed(text: str) -> np.ndarray:
        v = np.zeros(8, dtype=np.float64)
        v[_BASIS.get(text, 6)] = 1.0
        return v

    return embed


def _claim(
    cid: str,
    text: str,
    status: ClaimStatus,
    *,
    retrieved: bool = True,
) -> Claim:
    return Claim(
        id=cid,
        text=text,
        sources=[SourceRef(url_or_id=f"src://{cid}", retrieved=retrieved)],
        status=status,
    )


def _state(*claims: Claim) -> RunState:
    state = RunState(question=Question(raw="zeta", run_id="r-zeta"))
    state.claims = list(claims)
    return state


def _accepted_recall():
    lib = VerifiedFactsLibrary(_embedder(), alpha=0.1)
    claim = _claim("c0", "standard gravity is 9.80665 m/s^2", ClaimStatus.VERIFIED)
    assert lib.remember([claim]) == 1
    lib.add_calibration([1e-6] * 40)
    result = lib.recall("standard gravity is 9.80665 m/s^2")
    assert not result.abstained
    return result


def test_builder_deposits_only_verified_claims():
    state = _state(
        _claim("c_ok", "speed of light is 299792458 m/s", ClaimStatus.VERIFIED),
        _claim("c_no", "an unverified guess", ClaimStatus.UNVERIFIED),
    )
    cert = build_memory_fabric_certificate(state)
    assert [deposit.claim_id for deposit in cert.deposits] == ["c_ok"]
    assert cert.recalls == []
    assert gate_zeta(state, cert).passed


def test_accepted_conformal_recall_passes_when_memory_is_healthy():
    state = _state()
    cert = build_memory_fabric_certificate(
        state,
        recall_results=[_accepted_recall()],
        calibration_ready=True,
        health=MemoryHealthStatus.OK,
    )
    assert len(cert.recalls) == 1
    assert cert.recalls[0].score <= (cert.recalls[0].tau or 0.0)
    assert cert.recalls[0].sources == ("src://c0",)
    assert gate_zeta(state, cert).passed


def test_recall_without_calibration_fails():
    state = _state()
    cert = build_memory_fabric_certificate(
        state,
        recall_results=[_accepted_recall()],
        calibration_ready=False,
        health=MemoryHealthStatus.OK,
    )
    res = gate_zeta(state, cert)
    assert not res.passed
    assert any(f.code == "MEMORY_RECALL_WITHOUT_CALIBRATION" for f in res.failures)


def test_recall_outside_conformal_band_fails():
    state = _state()
    recall = MemoryRecallLink(
        query="q",
        claim_id="c0",
        score=0.5,
        tau=0.1,
        sources=("src://c0",),
    )
    cert = MemoryFabricCertificate(
        run_id=state.question.run_id,
        recalls=[recall],
        calibration_ready=True,
        health=MemoryHealthStatus.OK,
    )
    res = gate_zeta(state, cert)
    assert not res.passed
    assert any(f.code == "MEMORY_RECALL_OUTSIDE_BAND" for f in res.failures)


def test_drift_alert_blocks_memory_fabric():
    state = _state()
    cert = MemoryFabricCertificate(
        run_id=state.question.run_id,
        calibration_ready=True,
        health=MemoryHealthStatus.DRIFT_ALERT,
    )
    res = gate_zeta(state, cert)
    assert not res.passed
    assert any(f.code == "MEMORY_DRIFT_ALERT" for f in res.failures)


def test_manual_unverified_deposit_fails():
    state = _state(_claim("c_no", "not verified", ClaimStatus.UNSUPPORTED))
    cert = MemoryFabricCertificate(
        run_id=state.question.run_id,
        deposits=[MemoryDeposit(claim_id="c_no", sources=("src://c_no",))],
    )
    res = gate_zeta(state, cert)
    assert not res.passed
    assert any(f.code == "MEMORY_DEPOSIT_NOT_VERIFIED" for f in res.failures)


def test_deposit_source_mismatch_and_dead_source_fail():
    state = _state(_claim("c_dead", "dead source claim", ClaimStatus.VERIFIED, retrieved=False))
    cert = MemoryFabricCertificate(
        run_id=state.question.run_id,
        deposits=[MemoryDeposit(claim_id="c_dead", sources=("src://other",))],
    )
    res = gate_zeta(state, cert)
    codes = {f.code for f in res.failures}
    assert {"MEMORY_DEPOSIT_UNSOURCED", "MEMORY_DEPOSIT_SOURCE_MISMATCH"} <= codes


def test_uncalibrated_abstention_passes():
    state = _state()
    cert = MemoryFabricCertificate(
        run_id=state.question.run_id,
        calibration_ready=False,
        health=MemoryHealthStatus.NOT_ENOUGH_BASELINE,
    )
    assert gate_zeta(state, cert).passed
