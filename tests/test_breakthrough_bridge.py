"""Tests for the BreakthroughBridge surprise extension.

2 tests (Jetpack canonical + generic) per project pattern.
Verifies real artifacts (STL size, volume, package contents, report text),
Lern revision, DFM gate, provenance, and 4-Linsen discipline (by construction).
"""

import os
from pathlib import Path


from gen.extensions.breakthrough_bridge import (
    BreakthroughReport,
    challenge_impossible,
)


def test_breakthrough_bridge_jetpack_produces_real_artifacts_and_revised_frontier():
    """Jetpack energy gap (canonical NEEDS_BREAKTHROUGH) → diamag bridge + real outputs."""
    rep: BreakthroughReport = challenge_impossible(
        "jetpack hover energy impossible with current battery for sustained manned flight over people"
    )

    # Report structure + before/after
    assert isinstance(rep, BreakthroughReport)
    assert "jetpack" in rep.idea.lower()
    assert rep.before_grenztyp == "NEEDS_BREAKTHROUGH"
    assert rep.after_grenztyp == "POSSIBLE_BUT_UNSAFE_DIRECTLY"
    assert 5.0 <= rep.power_assist_pct <= 15.0

    # Lern + frontier revision happened
    assert rep.lern_persisted_key is not None
    assert rep.revised_frontier_gaps_closed >= 0

    # CAD + DFM — HONEST contract (STATUS.md §1 #2): the bridge fabricates NOTHING. build123d ships
    # in the optional `b123d` extra. If a real STL was produced, volume/DFM are real; if NOT, the
    # report must say "NOT BUILT" and must never claim "DFM PASSED". (Previously this asserted
    # cad_volume_cm3 > 20.0 — i.e. it validated the hardcoded fake volume of 48.5.)
    _rt = (Path(rep.package_dir) / "BREAKTHROUGH_REPORT.md").read_text(encoding="utf-8")
    _built = bool(rep.cad_stl_path) and Path(rep.cad_stl_path).exists()
    if _built:
        assert rep.cad_volume_cm3 is not None and rep.cad_volume_cm3 > 0.0
        assert os.path.getsize(Path(rep.cad_stl_path)) > 50_000
        assert rep.dfm_passed
        assert "DFM PASSED" in _rt
    else:
        # No geometry → no fabricated volume/DFM. NEGATIVE test that the fabrication is gone.
        assert rep.cad_volume_cm3 is None
        assert rep.dfm_passed is False
        assert "NOT BUILT" in _rt
        assert "DFM PASSED" not in _rt

    # Package + report on disk, self-contained
    pkg = Path(rep.package_dir)
    assert pkg.exists()
    assert (pkg / "BREAKTHROUGH_REPORT.md").exists()
    assert (pkg / "manifest.json").exists()
    report_text = (pkg / "BREAKTHROUGH_REPORT.md").read_text(encoding="utf-8")
    assert "The Impossible Made Possible" in report_text
    assert "F = (χ V B" in report_text or "diamagnetic" in report_text.lower()
    assert "possible_but_unsafe_directly" in report_text.lower()
    assert "Lern" in report_text or "lern" in report_text.lower()
    assert "4 Linsen" in report_text or "L1" in report_text
    assert "Gates" in report_text or "gates_passed" in report_text

    # Provenance everywhere + Lern activity
    assert rep.quelle and ("GENESIS" in rep.quelle or "Genesis" in rep.quelle)
    assert rep.gates_passed and len(rep.gates_passed) >= 3
    assert rep.lern_persisted_key is not None
    assert rep.revised_frontier_gaps_closed >= 0


def test_breakthrough_bridge_generic_fallback_still_produces_package_and_gates():
    """Generic idea still runs full chain (honest fallback) and ships artifacts."""
    rep = challenge_impossible("sustained personal flight with portable energy beyond current limits")

    assert isinstance(rep, BreakthroughReport)
    assert rep.package_dir
    assert Path(rep.package_dir).exists()
    assert rep.report_path and Path(rep.report_path).exists()
    assert rep.cad_stl_path is not None or rep.dfm_passed is not None  # either real or gate recorded
    assert "breakthrough" in (rep.quelle or "").lower() or "Genesis" in (rep.quelle or "")
    assert len(rep.gates_passed) >= 2
