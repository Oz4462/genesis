"""Characterization tests for lumencrucible.process_dream (T01 depth-audit).

These tests fail loudly if process_dream is a hollow facade. They assert that the
HEADLINE claim of the module is REAL:

* a real LumenHammer is produced (and is input-sensitive);
* a real OmegaCertificate with >=1 GateReceipt and >=2 LearningNotes that INCLUDE a
  ``self_ascent`` note and a ``delta_plus_reality`` note (the canonical post-cert
  override used to silently drop both — see DEPTH_AUDIT_lumencrucible.md);
* a VERIFIED Claim carrying >=2 real ``SourceRef`` provenance entries (not bare strings);
* the δ⁺ reality chain is genuinely wired (evaluate_reality surfaced via
  reality_verdict / delta_plus_result / coverage_certificate / run_state, with the
  post-cert seam/memory_fabric/pareto/coverage attach on the RunState);
* the self-ascent append is verifiable AND idempotent on an isolated WORK_QUEUE path
  (the same concrete suggestion appears exactly once across repeated runs, no APPEND_FAILED).

No mocking of the unit under test: process_dream runs against the real upstream wiring
(map_development_front, omega.build_omega_certificate, reality.evaluate_reality, ...).
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from gen.core.state import ClaimStatus, SourceRef
from gen.grenzverschiebung.lumencrucible import (
    LumenHammer,
    _SELF_ASCENT_SUGGESTION,
    process_dream,
)
from gen.memory_fabric import gate_zeta
from gen.omega import GateReceipt, LearningNote, OmegaCertificate

# A concrete, evaluable dream that clears the internal gate (>= 8 non-space chars).
_DREAM = "a jetpack that lets a human fly safely"


@pytest.fixture()
def work_queue(tmp_path):
    """An isolated WORK_QUEUE path so tests never touch the real WORK_QUEUE.md."""
    return str(tmp_path / "WORK_QUEUE.md")


def _run(dream: str, work_queue: str) -> dict:
    return process_dream(dream, work_queue_path=work_queue)


# --- OmegaCertificate: not a hollow facade -----------------------------------

def test_omega_certificate_has_receipt_and_required_notes(work_queue):
    result = _run(_DREAM, work_queue)
    cert = result["omega_certificate"]

    assert isinstance(cert, OmegaCertificate)
    # >= 1 GateReceipt
    assert len(cert.gate_receipts) >= 1
    assert all(isinstance(r, GateReceipt) for r in cert.gate_receipts)
    # >= 2 LearningNotes
    assert len(cert.learning_notes) >= 2
    assert all(isinstance(n, LearningNote) for n in cert.learning_notes)

    kinds = {n.kind for n in cert.learning_notes}
    # The two spec-mandated notes that the post-cert override used to drop.
    assert "self_ascent" in kinds, f"missing self_ascent note; kinds={kinds}"
    assert "delta_plus_reality" in kinds, f"missing delta_plus_reality note; kinds={kinds}"


def test_delta_plus_abstains_honestly_without_a_measurement(work_queue):
    """δ⁺ must NOT fabricate corroboration. With no independent measurement it ABSTAINS:
    reality_verdict is None and delta_plus_result.status is 'inconclusive'.

    (This test previously asserted status=='corroborated' on the 9.81 m/s² demo — but that was
    the δ⁺ tautology: the caller lied retrieved=True on a measurement equal to the prediction,
    so it could only ever 'corroborate'. STATUS.md §1 #1. This is now the NEGATIVE test that the
    lie is gone — the Ω note must not claim corroboration.)"""
    result = _run(_DREAM, work_queue)
    assert result["reality_verdict"] is None
    dpr = result["delta_plus_result"] or {}
    assert dpr.get("status") == "inconclusive"
    assert "no independent measurement" in dpr.get("note", "").lower()
    cert = result["omega_certificate"]
    note = next(n for n in cert.learning_notes if n.kind == "delta_plus_reality")
    # The Ω note declares honest abstention, not a (fabricated) corroboration.
    assert "abstention" in note.summary.lower()
    assert "no independent measurement" in note.summary.lower()


# --- Claim: VERIFIED with real provenance ------------------------------------

def test_claim_is_verified_with_multiple_sourcerefs(work_queue):
    result = _run(_DREAM, work_queue)
    claim = result["claim"]

    # Enum status, not a bare string (the old facade used "VERIFIED").
    assert claim.status is ClaimStatus.VERIFIED
    # >= 2 real provenance sources, each a SourceRef (typed as list[SourceRef]).
    assert len(claim.sources) >= 2
    assert all(isinstance(s, SourceRef) for s in claim.sources)
    assert all(s.url_or_id.strip() for s in claim.sources)


# --- δ⁺ reality chain genuinely wired ----------------------------------------

def test_delta_plus_chain_surfaced_via_result_keys(work_queue):
    result = _run(_DREAM, work_queue)

    # The δ⁺ chain keys are populated; δ⁺ is an HONEST abstention (no measurement), not a fake pass.
    assert "reality_verdict" in result and result["reality_verdict"] is None
    assert result["delta_plus_result"] is not None
    assert result["delta_plus_result"]["status"] == "inconclusive"
    assert result["coverage_certificate"] is not None
    assert result["run_state"] is not None


def test_memory_fabric_actually_deposits_the_verified_claim(work_queue):
    """Regression for a real hollow seam: memory_fabric.build deposits only claims with
    ``status is ClaimStatus.VERIFIED`` (identity). The old facade stored a bare string
    "VERIFIED", so NOTHING was ever deposited. A real VERIFIED claim must be deposited
    and pass gate_zeta."""
    result = _run(_DREAM, work_queue)
    mf = result["memory_fabric"]
    rs = result["run_state"]
    assert mf is not None
    assert len(mf.deposits) >= 1, "memory fabric deposited no claim — claim status not a real enum"
    assert gate_zeta(rs, mf).passed


def test_run_state_carries_post_cert_attachments(work_queue):
    result = _run(_DREAM, work_queue)
    rs = result["run_state"]

    # The post-cert seam/memory_fabric/pareto/coverage attach on the RunState.
    assert rs.seam_certificate is not None
    assert rs.memory_fabric is not None
    assert rs.pareto_front is not None
    assert rs.coverage_certificate is not None
    # The δ+ result is persisted on the state; reality_verdict is honestly None (no measurement → abstain).
    assert rs.reality_verdict is None
    assert rs.delta_plus_result is not None
    assert rs.delta_plus_result["status"] == "inconclusive"
    # build_omega + gate_omega ran over the populated state.
    assert result["omega_gate"] is not None
    assert result["omega_gate"].passed is True


# --- Ω enforcement opt-in (STATUS.md §1 #4) ----------------------------------

def test_omega_enforcement_opt_in_passes_on_normal_flow(work_queue):
    """Ω can be ENFORCED (enforce_omega=True raises OmegaGateNotPassed on a failed/absent Ω
    instead of only logging). On the normal flow Ω passes, so enforcing must NOT raise and must
    still return the result — the mechanism is wired without breaking the happy path."""
    result = process_dream(_DREAM, work_queue_path=work_queue, enforce_omega=True)
    assert result["omega_gate"] is not None and result["omega_gate"].passed is True


# --- Self-improvement: real, verifiable, idempotent --------------------------

def test_self_improvement_appends_once_no_failure(work_queue):
    result = _run(_DREAM, work_queue)

    note = result["self_improvement"]
    assert "APPEND_FAILED" not in note
    contents = open(work_queue, encoding="utf-8").read()
    # The concrete suggestion is genuinely written to the isolated queue.
    assert _SELF_ASCENT_SUGGESTION in contents
    assert contents.count(_SELF_ASCENT_SUGGESTION) == 1


def test_self_ascent_is_idempotent_across_runs(work_queue):
    """Repeated runs must not flood the queue: suggestion stays exactly once."""
    first = _run(_DREAM, work_queue)
    second = _run(_DREAM, work_queue)
    third = _run(_DREAM, work_queue)

    contents = open(work_queue, encoding="utf-8").read()
    assert contents.count(_SELF_ASCENT_SUGGESTION) == 1
    # First run actually appended; later runs detect the existing record.
    assert "[already recorded" not in first["self_improvement"]
    assert "[already recorded" in second["self_improvement"]
    assert "[already recorded" in third["self_improvement"]
    for note in (first, second, third):
        assert "APPEND_FAILED" not in note["self_improvement"]


# --- Input-sensitivity: output genuinely depends on the dream ----------------

def test_hammer_is_input_sensitive(work_queue):
    """A facade would emit a constant hammer; real code keys off the dream."""
    jetpack = _run(_DREAM, work_queue)["hammer"]
    other = _run("a quiet rooftop rainwater harvesting system", work_queue)["hammer"]

    assert isinstance(jetpack, LumenHammer)
    assert isinstance(other, LumenHammer)
    # The jetpack canon produces a distinct, named thrust rig.
    assert jetpack.experiment_name != other.experiment_name
    assert "Thrust_Rig" in jetpack.experiment_name


def test_claim_text_tracks_the_hammer(work_queue):
    result = _run(_DREAM, work_queue)
    # The claim text references the concrete produced hammer — proves data flow.
    assert result["hammer"].experiment_name in result["claim"].text


# --- Fail-loud guard ---------------------------------------------------------

@pytest.mark.parametrize("bad", ["", "   ", "short"])
def test_too_vague_dream_raises(bad, work_queue):
    """The internal gate must fail loud (no silent default) on an unusable dream."""
    with pytest.raises(ValueError) as exc:
        _run(bad, work_queue)
    assert "gate failed" in str(exc.value).lower()


# --- Property-based: idempotency invariant -----------------------------------

@settings(deadline=None, max_examples=15)
@given(runs=st.integers(min_value=1, max_value=6))
def test_property_suggestion_count_invariant(tmp_path_factory, runs):
    """For ANY number of repeated runs (>=1), the concrete self-ascent suggestion
    appears in the isolated queue exactly once. Idempotence is the invariant."""
    wq = str(tmp_path_factory.mktemp("wq") / "WORK_QUEUE.md")
    for _ in range(runs):
        out = _run(_DREAM, wq)
        assert "APPEND_FAILED" not in out["self_improvement"]
    contents = open(wq, encoding="utf-8").read()
    assert contents.count(_SELF_ASCENT_SUGGESTION) == 1


@settings(deadline=None, max_examples=10)
@given(
    suffix=st.text(
        alphabet=st.characters(min_codepoint=97, max_codepoint=122),
        min_size=8,
        max_size=40,
    )
)
def test_property_any_valid_dream_yields_required_notes(tmp_path_factory, suffix):
    """Any sufficiently-concrete dream yields a cert with BOTH mandated notes."""
    wq = str(tmp_path_factory.mktemp("wq") / "WORK_QUEUE.md")
    cert = _run(suffix, wq)["omega_certificate"]
    kinds = {n.kind for n in cert.learning_notes}
    assert {"self_ascent", "delta_plus_reality"} <= kinds
    assert len(cert.gate_receipts) >= 1
