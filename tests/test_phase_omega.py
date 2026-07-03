"""Phase omega acceptance - no hidden completion, no hidden learning debt."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.interfaces import GateFailure, GateResult  # noqa: E402
from gen.core.state import Decision, Question, Report, RunState, Specification  # noqa: E402
from gen.omega import (  # noqa: E402
    OmegaCertificate,
    build_omega_certificate,
    gate_omega,
)
from gen.ratification import SignOff, ratification_packet  # noqa: E402
from gen.verification import gate_omega as exported_gate_omega  # noqa: E402


def _spec() -> Specification:
    return Specification(
        run_id="r-omega",
        idea="omega completion packet",
        decisions=[
            Decision(
                id="d_material",
                title="Material",
                choice="aluminum",
                rationale="light enough for the intended build envelope",
            )
        ],
        gaps=["No field measurement has been imported yet."],
    )


def _state_with_spec() -> RunState:
    state = RunState(question=Question(raw="omega", run_id="r-omega"))
    state.specification = _spec()
    state.report = Report(
        run_id="r-omega",
        question="omega",
        body="Claim-backed report.",
        statement_to_claim={"Claim-backed report.": "c1"},
        gaps=["The evidence base is still narrow."],
    )
    return state


def _passing_gates() -> dict[str, GateResult]:
    return {
        "gamma": GateResult(gate="gamma", passed=True),
        "zeta": GateResult(gate="zeta", passed=True),
    }


def _full_signoff(spec: Specification, gates: dict[str, GateResult]) -> SignOff:
    packet = ratification_packet(spec, gates)
    refs = frozenset(item.ref for item in packet if item.blocking)
    return SignOff(approved=refs, approver="ozan")


def test_builder_produces_valid_cross_phase_packet():
    state = _state_with_spec()
    gates = _passing_gates()
    cert = build_omega_certificate(
        state,
        gates,
        signoff=_full_signoff(state.specification, gates),  # type: ignore[arg-type]
    )

    res = gate_omega(
        state,
        cert,
        required_gates=("gamma", "zeta"),
        gate_results=gates,
    )

    assert res.passed
    assert exported_gate_omega is gate_omega
    assert {note.ref for note in cert.learning_notes} >= {
        "artifact:report",
        "artifact:specification",
        "report:gap:0",
        "spec:decision:d_material",
        "spec:gap:0",
        "gate:gamma",
        "gate:zeta",
    }


def test_missing_required_gate_receipt_fails():
    state = _state_with_spec()
    gates = {"gamma": GateResult(gate="gamma", passed=True)}
    cert = build_omega_certificate(
        state,
        gates,
        signoff=_full_signoff(state.specification, gates),  # type: ignore[arg-type]
    )

    res = gate_omega(state, cert, required_gates=("gamma", "zeta"), gate_results=gates)

    assert not res.passed
    assert any(f.code == "MISSING_REQUIRED_GATE_RECEIPT" for f in res.failures)


def test_failed_gate_receipt_blocks_done():
    state = RunState(question=Question(raw="omega", run_id="r-omega"))
    state.report = Report(run_id="r-omega", question="q", body="body")
    gates = {
        "delta": GateResult(
            gate="delta",
            passed=False,
            failures=[GateFailure("PHYSICS_CHECK_FAILED", "torsion failed")],
        )
    }
    cert = build_omega_certificate(state, gates)

    res = gate_omega(state, cert, required_gates=("delta",), gate_results=gates)

    assert not res.passed
    assert any(f.code == "FAILED_GATE_RECEIPT" for f in res.failures)


def test_gate_receipt_mismatch_fails():
    state = RunState(question=Question(raw="omega", run_id="r-omega"))
    state.report = Report(run_id="r-omega", question="q", body="body")
    cert = build_omega_certificate(state, {"gamma": GateResult("gamma", True)})
    actual = {
        "gamma": GateResult(
            "gamma",
            False,
            [GateFailure("FAKE_PASS", "receipt was altered")],
        )
    }

    res = gate_omega(state, cert, required_gates=("gamma",), gate_results=actual)

    assert not res.passed
    assert any(f.code == "GATE_RECEIPT_MISMATCH" for f in res.failures)


def test_hidden_gap_note_fails():
    state = _state_with_spec()
    gates = _passing_gates()
    cert = build_omega_certificate(
        state,
        gates,
        signoff=_full_signoff(state.specification, gates),  # type: ignore[arg-type]
    )
    hidden = OmegaCertificate(
        run_id=cert.run_id,
        gate_receipts=cert.gate_receipts,
        learning_notes=tuple(note for note in cert.learning_notes if note.ref != "spec:gap:0"),
        ratification_refs=cert.ratification_refs,
        signoff=cert.signoff,
    )

    res = gate_omega(state, hidden, required_gates=("gamma", "zeta"), gate_results=gates)

    assert not res.passed
    assert any(f.code == "MISSING_GAP_NOTE" and f.claim_id == "spec:gap:0" for f in res.failures)


def test_hidden_decision_note_fails():
    state = _state_with_spec()
    gates = _passing_gates()
    cert = build_omega_certificate(
        state,
        gates,
        signoff=_full_signoff(state.specification, gates),  # type: ignore[arg-type]
    )
    hidden = OmegaCertificate(
        run_id=cert.run_id,
        gate_receipts=cert.gate_receipts,
        learning_notes=tuple(
            note for note in cert.learning_notes if note.ref != "spec:decision:d_material"
        ),
        ratification_refs=cert.ratification_refs,
        signoff=cert.signoff,
    )

    res = gate_omega(state, hidden, required_gates=("gamma", "zeta"), gate_results=gates)

    assert not res.passed
    assert any(
        f.code == "MISSING_DECISION_NOTE" and f.claim_id == "spec:decision:d_material"
        for f in res.failures
    )


def test_missing_ratification_ref_fails():
    state = _state_with_spec()
    gates = _passing_gates()
    cert = build_omega_certificate(
        state,
        gates,
        signoff=_full_signoff(state.specification, gates),  # type: ignore[arg-type]
    )
    hidden = OmegaCertificate(
        run_id=cert.run_id,
        gate_receipts=cert.gate_receipts,
        learning_notes=cert.learning_notes,
        ratification_refs=tuple(ref for ref in cert.ratification_refs if ref != "decision:d_material"),
        signoff=cert.signoff,
    )

    res = gate_omega(state, hidden, required_gates=("gamma", "zeta"), gate_results=gates)

    assert not res.passed
    assert any(f.code == "MISSING_RATIFICATION_REF" for f in res.failures)


def test_missing_signoff_keeps_blocking_items_unratified():
    state = _state_with_spec()
    gates = _passing_gates()
    cert = build_omega_certificate(state, gates)

    res = gate_omega(state, cert, required_gates=("gamma", "zeta"), gate_results=gates)

    assert not res.passed
    assert any(f.code == "UNRATIFIED_BLOCKING_ITEM" for f in res.failures)


def test_blank_signoff_approver_fails():
    state = _state_with_spec()
    gates = _passing_gates()
    cert = build_omega_certificate(
        state,
        gates,
        signoff=SignOff(
            approved=_full_signoff(state.specification, gates).approved,  # type: ignore[arg-type]
            approver="",
        ),
    )

    res = gate_omega(state, cert, required_gates=("gamma", "zeta"), gate_results=gates)

    assert not res.passed
    assert any(f.code == "SIGNOFF_WITHOUT_APPROVER" for f in res.failures)


def test_output_without_learning_notes_fails():
    state = RunState(question=Question(raw="omega", run_id="r-omega"))
    state.report = Report(run_id="r-omega", question="q", body="body")
    cert = OmegaCertificate(run_id="r-omega")

    res = gate_omega(state, cert)

    assert not res.passed
    assert any(f.code == "NO_LEARNING_NOTES" for f in res.failures)
    assert any(f.code == "MISSING_ARTIFACT_NOTE" for f in res.failures)
