"""Integrity watchlist re-proof (REWORK 2026-07-11) — §1 #3 + #4.

#3 lumen provenance claim is deterministic VERIFIED@1.0 (not fuzzy 0.92).
#4 enforce_omega (default True) raises OmegaGateNotPassed when Ω fails/absent.
   Opt-out enforce_omega=False remains for partial demos.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from gen.core.errors import OmegaGateNotPassed
from gen.core.state import ClaimStatus
from gen.grenzverschiebung.lumencrucible import LumenCrucible


def test_lumen_claim_is_deterministic_provenance_not_fuzzy_092(tmp_path):
    out = LumenCrucible().process_dream(
        "steel bracket for 100 N",
        run_id="int3-claim",
        work_queue_path=str(tmp_path / "wq.md"),
    )
    claim = out["claim"]
    assert claim.status is ClaimStatus.VERIFIED
    assert claim.confidence == 1.0
    assert any("lumencrucible" in s.url_or_id for s in claim.sources)
    # Explicit honesty: not a cross-model world-fact score
    assert claim.confidence != pytest.approx(0.92)


def test_enforce_omega_raises_when_omega_gate_fails(tmp_path, monkeypatch):
    lc = LumenCrucible()
    failed = SimpleNamespace(passed=False, failures=[SimpleNamespace(code="OMEGA_FAKE_FAIL")])

    # Patch build path: make gate_omega return failed under default enforcement
    import gen.omega as omega_mod

    monkeypatch.setattr(
        omega_mod,
        "gate_omega",
        lambda *a, **k: failed,
    )
    monkeypatch.setattr(
        omega_mod,
        "build_omega_certificate",
        lambda *a, **k: SimpleNamespace(
            learning_notes=(),
            phase_receipts=(),
            complete=False,
        ),
    )

    with pytest.raises(OmegaGateNotPassed) as ei:
        lc.process_dream(
            "steel bracket",
            run_id="int4-enforce",
            work_queue_path=str(tmp_path / "wq.md"),
            # default enforce_omega=True
        )
    assert "OMEGA" in str(ei.value) or "int4-enforce" in str(ei.value)


def test_enforce_omega_default_on_succeeds_when_omega_passes(tmp_path):
    """HORIZON-COMPLETION: default enforce_omega=True; normal dreams already pass Ω."""
    out = LumenCrucible().process_dream(
        "tiny idea",
        run_id="int4-default-on",
        work_queue_path=str(tmp_path / "wq.md"),
    )
    assert "hammer" in out
    assert out.get("omega_gate") is None or out["omega_gate"].passed
    assert out.get("teacher_notes") is not None
    assert out.get("community_evidence") is not None
    assert out["community_evidence"].get("user_data_required") is False


def test_enforce_omega_opt_out_does_not_raise(tmp_path):
    """Escape hatch for partial demos — explicit False must not block."""
    out = LumenCrucible().process_dream(
        "tiny idea",
        run_id="int4-opt-out",
        work_queue_path=str(tmp_path / "wq.md"),
        enforce_omega=False,
    )
    assert "hammer" in out


def test_h1_memory_fabric_attached_and_zeta_gate_bool(tmp_path):
    """H1: ζ memory_fabric certificate + gate_zeta must attach (not silent None)."""
    out = LumenCrucible().process_dream(
        "steel bracket for 100 N",
        run_id="h1-zeta",
        work_queue_path=str(tmp_path / "wq.md"),
    )
    mf = out.get("memory_fabric")
    assert mf is not None, "memory_fabric must be attached after H1 import split"
    assert getattr(mf, "run_id", None) == "h1-zeta"
    # VERIFIED lumen claim → at least one deposit
    assert len(getattr(mf, "deposits", ())) >= 1
    zeta = (out.get("horizon_subgates") or {}).get("zeta")
    assert zeta is True, f"expected zeta gate True, got {zeta!r}"
    rs = out.get("run_state")
    assert rs is not None
    assert getattr(rs, "memory_fabric", None) is not None


def test_h2_subgates_epsilon_coverage_gamma_not_none(tmp_path):
    """H2: ε / coverage / γ⁺ attach as real gate verdicts (not silent None)."""
    out = LumenCrucible().process_dream(
        "steel bracket for 100 N",
        run_id="h2-subgates",
        work_queue_path=str(tmp_path / "wq.md"),
    )
    sub = out.get("horizon_subgates") or {}
    for key in ("epsilon", "zeta", "gamma_plus", "coverage", "omega"):
        assert sub.get(key) is not None, f"subgate {key} must not be None after H2"
        assert sub.get(key) is True or sub.get(key) is False or isinstance(sub.get(key), str)
    assert out.get("seam_certificate") is not None
    assert out.get("coverage_certificate") is not None
    assert out.get("memory_fabric") is not None
    assert getattr(out.get("run_state"), "pareto_front", None) is not None
