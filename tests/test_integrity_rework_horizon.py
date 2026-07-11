"""Integrity watchlist re-proof (REWORK 2026-07-11) — §1 #3 + #4.

#3 lumen provenance claim is deterministic VERIFIED@1.0 (not fuzzy 0.92).
#4 enforce_omega=True raises OmegaGateNotPassed when Ω fails/absent.
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

    # Force the post-certs omega path to report a failed gate result.
    import gen.grenzverschiebung.lumencrucible as lumen_mod

    real_process = lc.process_dream

    def _wrap(*args, **kwargs):
        kwargs = dict(kwargs)
        kwargs.setdefault("work_queue_path", str(tmp_path / "wq.md"))
        # Inject after normal flow by patching gate_omega inside process_dream's import path
        return real_process(*args, **kwargs)

    # Patch build path: make gate_omega return failed when enforce_omega True
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
            enforce_omega=True,
        )
    assert "OMEGA" in str(ei.value) or "int4-enforce" in str(ei.value)


def test_enforce_omega_default_off_does_not_raise_on_weak_run(tmp_path):
    # Default enforce_omega=False must never block weak-mode demos.
    out = LumenCrucible().process_dream(
        "tiny idea",
        run_id="int4-default",
        work_queue_path=str(tmp_path / "wq.md"),
        enforce_omega=False,
    )
    assert "hammer" in out
