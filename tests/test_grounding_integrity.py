"""Grounding integrity — independent corroboration and full report grounding.

A VERIFIED claim must be corroborated by sources independent of its own (no circular self-
citation); every report sentence must map to a real, non-refuted claim (dangling or refuted-
backed sentences are flagged). Offline, no LLM, pure functions.

Run:  pytest tests/test_grounding_integrity.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.state import (  # noqa: E402
    Claim,
    ClaimStatus,
    Report,
    SourceRef,
    SourceSupport,
)
from gen.demo import capstone_claims  # noqa: E402
from gen.grounding_integrity import corroboration_independence, report_grounding  # noqa: E402


def _src(url):
    return SourceRef(url, True, support=SourceSupport.SUPPORTS)


# --- corroboration independence ------------------------------------------------

def test_capstone_claims_are_independently_corroborated():
    rep = corroboration_independence(capstone_claims())
    assert rep.n_verified == 18 and rep.circular == [] and rep.ok
    assert rep.independent_rate == 1.0


def test_circular_corroboration_is_flagged():
    circular = Claim(id="x", text="t", sources=[_src("https://s")],
                     status=ClaimStatus.VERIFIED, verification=[_src("https://s")])  # same source
    rep = corroboration_independence([circular])
    assert rep.circular == ["x"] and not rep.ok


# --- report grounding coverage -------------------------------------------------

def _report(mapping):
    return Report(run_id="r", question="?", body="...", statement_to_claim=mapping)


def test_a_fully_grounded_report_passes():
    claims = capstone_claims()
    report = _report({"An M4 screw is 4 mm.": "c_screw", "The LED runs at 12 V.": "c_led"})
    cov = report_grounding(report, claims)
    assert cov.ok and cov.n_grounded == 2 and cov.coverage == 1.0


def test_a_dangling_claim_id_is_flagged():
    report = _report({"Invented fact.": "c_does_not_exist"})
    cov = report_grounding(report, capstone_claims())
    assert not cov.ok and cov.dangling == [("Invented fact.", "c_does_not_exist")]


def test_a_refuted_backed_sentence_is_flagged():
    refuted = Claim(id="c_bad", text="false", sources=[_src("https://s")],
                    status=ClaimStatus.REFUTED)
    report = _report({"A refuted thing.": "c_bad"})
    cov = report_grounding(report, [refuted])
    assert not cov.ok and cov.refuted_backed == [("A refuted thing.", "c_bad")]
    assert cov.coverage == 0.0


def test_is_deterministic():
    claims = capstone_claims()
    report = _report({"An M4 screw is 4 mm.": "c_screw"})
    a, b = report_grounding(report, claims), report_grounding(report, claims)
    assert (a.n_grounded, a.dangling, a.refuted_backed) == (b.n_grounded, b.dangling, b.refuted_backed)
