"""Depth-audit test for omega.py (cross-phase completion gate cert-chain) — T03.

Proves gate_omega / build_omega_certificate is a REAL gate (not rubber stamp / facade)
per the task spec:
- Build RunState via real core.state ctors with >=1 output artifact.
- Build OmegaCertificate via build_omega_certificate from *real* GateResults.
- Happy: gate_omega(...).passed is True on coherent packet.
- Drive every documented failure loud with exact GateFailure.code:
  - OM-1: cert run_id != state.question.run_id → OMEGA_RUN_MISMATCH
  - OM-4: FAILED GateReceipt present → FAILED_GATE_RECEIPT
  - OM-3: required gate absent from receipts → MISSING_REQUIRED_GATE_RECEIPT
  - reviewed=True path: no upstream certs → MISSING_COVERAGE_CERTIFICATE etc;
    mismatched attached cert run_id → matching *_CERT_RUN_MISMATCH
- Input consumed: driving field change (e.g. report gap) mutates learning_notes
  and the required-note set.
- Uses only real constructors (read from core/state.py) + pre-existing modules.
- Property-based test(s) with Hypothesis for key invariants (run_id, mismatch etc).
- Negative tests required ("a gate without a test does not exist").
- No edits to src/gen/omega.py (module reads REAL after review).

New authoritative _depth test (leaves legacy test_omega_* untouched per team decisions).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402
from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from gen.core.interfaces import GateFailure, GateResult  # noqa: E402
from gen.core.state import (  # noqa: E402
    CoverageCertificate,
    DesignObjective,
    EmpiricalStatus,
    EmpiricalVerdict,
    InverseDesignGoal,
    MemoryFabricCertificate,
    ObjectiveDirection,
    ParetoFront,
    Question,
    Report,
    RunState,
    SeamCertificate,
    Specification,
)
from gen.omega import (  # noqa: E402
    OmegaCertificate,
    build_omega_certificate,
    gate_omega,
)


# --- real-ctor helpers (no invented fields, minimal but valid) ----------------

def _q(run_id: str = "omega-depth-001") -> Question:
    return Question(raw="depth audit omega gate", run_id=run_id)


def _spec(run_id: str = "omega-depth-001") -> Specification:
    return Specification(
        run_id=run_id,
        idea="minimal spec for omega depth audit",
        quantities=[],
        components=[],
        bom=[],
        steps=[],
        constraints=[],
        decisions=[],
        gaps=[],
    )


def _goal() -> InverseDesignGoal:
    return InverseDesignGoal(
        id="g-depth",
        description="depth-audit goal",
        objectives=[
            DesignObjective(
                id="o-mass",
                quantity_id="q-mass",
                direction=ObjectiveDirection.MINIMIZE,
                unit="kg",
            )
        ],
    )


def _minimal_state_with_artifact(run_id: str = "omega-depth-001", *, with_gap: bool = False) -> RunState:
    """Real RunState via real ctors, carrying at least one output artifact (report)."""
    q = _q(run_id)
    state = RunState(question=q)
    gaps = ["depth-audit identified gap in report"] if with_gap else []
    state.report = Report(
        run_id=run_id,
        question="depth question",
        body="Report body with provenance.",
        statement_to_claim={},
        gaps=gaps,
        sources_used=[],
    )
    # Attach a minimal spec so ratification/artifact notes paths are exercised when relevant
    state.specification = _spec(run_id)
    return state


def _attach_minimal_upstream_certs(state: RunState) -> None:
    """Attach minimal but *real-constructed* upstream cert objects so reviewed=True happy path works."""
    run_id = state.question.run_id
    # δ+ coverage (empty honest case is valid)
    state.coverage_certificate = CoverageCertificate(
        spec_run_id=run_id,
        failure_modes=[],
        coverage=[],
        complete=True,
        produced_by="depth-audit",
    )
    # δ+ reality (CORROBORATED is a valid verdict)
    state.reality_verdict = EmpiricalVerdict(
        status=EmpiricalStatus.CORROBORATED,
        residual=0.0,
        within_tolerance=True,
        detail="depth-audit match",
    )
    # γ+ pareto (empty front + gaps is allowed honest abstention)
    state.pareto_front = ParetoFront(
        goal=_goal(),
        candidates=[],
        evaluated_candidates=[],
        gaps=["no candidates evaluated in depth-audit"],
        produced_by="depth-audit",
    )
    # ε seam (empty is valid)
    state.seam_certificate = SeamCertificate(
        spec_run_id=run_id,
        seams=[],
        complete=True,
        produced_by="depth-audit",
    )
    # ζ memory (empty deposits/recalls = honest abstention)
    state.memory_fabric = MemoryFabricCertificate(
        run_id=run_id,
        deposits=[],
        recalls=[],
        calibration_ready=False,
        health="NOT_ENOUGH_BASELINE",  # enum value name ok (str enum)
        produced_by="depth-audit",
    )


def _real_passing_gate_results() -> dict[str, GateResult]:
    """Real GateResult objects (not fabricated) to feed build_omega_certificate."""
    return {
        "alpha": GateResult(gate="alpha", passed=True, failures=[]),
        "beta": GateResult(gate="beta", passed=True, failures=[]),
    }


# --- tests -------------------------------------------------------------------

def test_omega_happy_path_passes_with_real_gateresults_and_artifact():
    """Coherent packet from real GateResults on state with output artifact → .passed True."""
    state = _minimal_state_with_artifact()
    gr = _real_passing_gate_results()
    cert = build_omega_certificate(state, gr)
    assert cert.run_id == state.question.run_id
    assert len(cert.gate_receipts) == 2

    res = gate_omega(
        state,
        cert,
        required_gates=("alpha", "beta"),
        gate_results=gr,
        require_ratification=False,
        reviewed=False,
    )
    assert res.passed, f"expected pass; got failures={[f.code for f in res.failures]}"
    # artifact present in notes (learning notes derived from state)
    note_refs = {n.ref for n in cert.learning_notes}
    assert "artifact:report" in note_refs


def test_omega_input_consumed_report_gap_changes_notes_and_required_set():
    """Driving field (report gaps) changes learning_notes + _required_note_refs set — proves consumption."""
    s1 = _minimal_state_with_artifact(with_gap=False)
    s2 = _minimal_state_with_artifact(with_gap=True)

    gr: dict[str, GateResult] = {}
    c1 = build_omega_certificate(s1, gr)
    c2 = build_omega_certificate(s2, gr)

    refs1 = {n.ref for n in c1.learning_notes}
    refs2 = {n.ref for n in c2.learning_notes}
    # Gap note appears only when gap present
    assert "report:gap:0" not in refs1
    assert "report:gap:0" in refs2
    assert refs1 != refs2

    # required note set (internal but observable via note surface + behavior)
    # changing gap must affect what would be required notes
    req1 = {ref for ref in refs1 if ref.startswith("report:gap")}
    req2 = {ref for ref in refs2 if ref.startswith("report:gap")}
    assert req1 != req2


def test_omega_om1_run_mismatch_fails_loud():
    """(OM-1) cert run_id != state run_id → exact OMEGA_RUN_MISMATCH."""
    state = _minimal_state_with_artifact(run_id="run-good")
    gr = _real_passing_gate_results()
    cert = build_omega_certificate(state, gr)

    # Construct mismatched cert (use same receipts/notes, wrong run_id)
    bad_cert = OmegaCertificate(
        run_id="run-wrong",
        gate_receipts=cert.gate_receipts,
        learning_notes=cert.learning_notes,
        ratification_refs=cert.ratification_refs,
        signoff=cert.signoff,
    )

    res = gate_omega(state, bad_cert, require_ratification=False)
    assert not res.passed
    assert any(f.code == "OMEGA_RUN_MISMATCH" for f in res.failures), (
        f"got codes={[f.code for f in res.failures]}"
    )


def test_omega_om4_failed_gate_receipt_fails_loud():
    """(OM-4) a FAILED receipt in packet → exact FAILED_GATE_RECEIPT (completion cannot hide)."""
    state = _minimal_state_with_artifact()
    gr: dict[str, GateResult] = {
        "alpha": GateResult(gate="alpha", passed=True, failures=[]),
        "beta": GateResult(
            gate="beta",
            passed=False,
            failures=[GateFailure(code="BETA_FAIL", detail="synthetic failure for test")],
        ),
    }
    cert = build_omega_certificate(state, gr)

    res = gate_omega(state, cert, require_ratification=False)
    assert not res.passed
    assert any(f.code == "FAILED_GATE_RECEIPT" for f in res.failures), (
        f"got {[f.code for f in res.failures]}"
    )
    # exact string surface (regression guard)
    failed = [f for f in res.failures if f.code == "FAILED_GATE_RECEIPT"][0]
    assert "beta" in failed.detail
    assert "completion cannot hide" in failed.detail.lower()


def test_omega_om3_missing_required_gate_receipt_fails_loud():
    """(OM-3) required gate absent from receipts → exact MISSING_REQUIRED_GATE_RECEIPT."""
    state = _minimal_state_with_artifact()
    gr = {"alpha": GateResult(gate="alpha", passed=True, failures=[])}
    cert = build_omega_certificate(state, gr)

    res = gate_omega(state, cert, required_gates=("alpha", "gamma"), require_ratification=False)
    assert not res.passed
    assert any(
        f.code == "MISSING_REQUIRED_GATE_RECEIPT" and f.claim_id == "gamma" for f in res.failures
    ), f"got {[ (f.code, f.claim_id) for f in res.failures ]}"


def test_omega_reviewed_true_fails_on_each_missing_upstream_cert():
    """reviewed=True path: absence of any required upstream on state → documented MISSING_* code."""
    base = _minimal_state_with_artifact()
    _attach_minimal_upstream_certs(base)
    gr = _real_passing_gate_results()
    cert = build_omega_certificate(base, gr)

    for missing in (
        "coverage_certificate",
        "reality_verdict",
        "pareto_front",
        "seam_certificate",
        "memory_fabric",
    ):
        hollow = RunState(question=base.question)
        hollow.report = base.report
        hollow.specification = base.specification
        for fld in ("coverage_certificate", "reality_verdict", "pareto_front",
                    "seam_certificate", "memory_fabric"):
            if fld != missing:
                setattr(hollow, fld, getattr(base, fld))

        res = gate_omega(hollow, cert, reviewed=True, require_ratification=False)
        assert not res.passed
        expected = {
            "coverage_certificate": "MISSING_COVERAGE_CERTIFICATE",
            "reality_verdict": "MISSING_REALITY_VERDICT",
            "pareto_front": "MISSING_PARETO_FRONT",
            "seam_certificate": "MISSING_SEAM_CERTIFICATE",
            "memory_fabric": "MISSING_MEMORY_FABRIC",
        }[missing]
        assert any(f.code == expected for f in res.failures), (
            f"expected {expected} for {missing}; got {[f.code for f in res.failures]}"
        )


def test_omega_reviewed_mismatched_upstream_cert_run_id_fails_loud():
    """Attached upstream cert with run_id mismatch (under or outside reviewed) → exact *_CERT_RUN_MISMATCH."""
    state = _minimal_state_with_artifact(run_id="good-run-depth")
    _attach_minimal_upstream_certs(state)
    # Poison the coverage cert with wrong run_id (real ctor)
    bad_cov = CoverageCertificate(
        spec_run_id="bad-run-depth",
        failure_modes=[],
        coverage=[],
        complete=True,
    )
    state.coverage_certificate = bad_cov

    cert = build_omega_certificate(state, {})
    res = gate_omega(state, cert, reviewed=False, require_ratification=False)
    assert not res.passed
    assert any(f.code == "COVERAGE_CERT_RUN_MISMATCH" for f in res.failures)

    # Also memory fabric mismatch
    state2 = _minimal_state_with_artifact(run_id="good-run-depth-2")
    _attach_minimal_upstream_certs(state2)
    state2.memory_fabric = MemoryFabricCertificate(run_id="bad-mf-depth")
    cert2 = build_omega_certificate(state2, {})
    res2 = gate_omega(state2, cert2, reviewed=True, require_ratification=False)
    assert any(f.code == "MEMORY_FABRIC_RUN_MISMATCH" for f in res2.failures)


def test_omega_happy_reviewed_path_passes_with_all_real_certs():
    """reviewed=True happy: all upstream attached via real ctors + coherent receipts → passed."""
    state = _minimal_state_with_artifact()
    _attach_minimal_upstream_certs(state)
    gr = _real_passing_gate_results()
    cert = build_omega_certificate(state, gr)

    res = gate_omega(
        state,
        cert,
        required_gates=tuple(gr.keys()),
        gate_results=gr,
        reviewed=True,
        require_ratification=False,
    )
    assert res.passed, f"reviewed happy failed: {[f.code for f in res.failures]}"
    # notes reflect attached certs (consumption)
    refs = {n.ref for n in cert.learning_notes}
    assert "artifact:coverage_certificate" in refs
    assert "artifact:reality_verdict" in refs
    assert "artifact:pareto_front" in refs


# --- property-based invariants (Hypothesis) ----------------------------------

@given(
    run_id=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "P"), min_codepoint=45, max_codepoint=122),
        min_size=5,
        max_size=20,
    ).filter(lambda s: bool(s.strip()))
)
@settings(max_examples=15, deadline=1500)
def test_property_omega_cert_run_id_always_derives_from_state(run_id: str):
    """Invariant: build_omega_certificate always emits cert.run_id == state.question.run_id (A5 determinism)."""
    q = Question(raw="hyp-depth", run_id=run_id)
    stt = RunState(question=q)
    stt.report = Report(run_id=run_id, question="h", body="hb", gaps=[])
    cert = build_omega_certificate(stt, {})
    assert cert.run_id == run_id


@given(
    mismatch=st.booleans(),
)
@settings(max_examples=8, deadline=1200)
def test_property_omega_run_mismatch_always_detected(mismatch: bool):
    """OMEGA_RUN_MISMATCH fires exactly when run_ids differ (property over construction)."""
    good_id = "prop-run-42"
    state = _minimal_state_with_artifact(run_id=good_id)
    gr: dict[str, GateResult] = {}
    cert = build_omega_certificate(state, gr)
    if mismatch:
        bad = OmegaCertificate(
            run_id="prop-run-999",
            gate_receipts=cert.gate_receipts,
            learning_notes=cert.learning_notes,
        )
        res = gate_omega(state, bad, require_ratification=False)
        assert not res.passed
        assert any(f.code == "OMEGA_RUN_MISMATCH" for f in res.failures)
    else:
        res = gate_omega(state, cert, require_ratification=False)
        # may have other notes but must not have run mismatch
        assert not any(f.code == "OMEGA_RUN_MISMATCH" for f in res.failures)


if __name__ == "__main__":
    pytest.main([__file__, "-q"])