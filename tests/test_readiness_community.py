"""Readiness ladder + community evidence (honest, ledger-backed)."""

from __future__ import annotations

import json

from gen.grenzverschiebung.readiness_ladder import (
    assess_readiness,
    community_evidence,
)


def test_community_evidence_zero_without_ledger(tmp_path, monkeypatch):
    ledger = tmp_path / "community_ledger.json"
    monkeypatch.setenv("GENESIS_COMMUNITY_LEDGER", str(ledger))
    ev = community_evidence({})
    assert ev["replications"] == 0
    assert ev["community_score"] == 0.0
    assert any("ledger" in g for g in ev["gaps"])


def test_community_evidence_reads_ledger(tmp_path, monkeypatch):
    ledger = tmp_path / "community_ledger.json"
    ledger.write_text(
        json.dumps({"replications": 3, "field_failures": ["bolt_creep"]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("GENESIS_COMMUNITY_LEDGER", str(ledger))
    ev = community_evidence({})
    assert ev["replications"] == 3
    assert ev["community_score"] > 0.4
    assert "bolt_creep" in ev["field_failures"]


def test_assess_readiness_next_gaps_not_perpetual_deferred():
    lvl = assess_readiness({"claims": [1], "cad_artifacts": True}, gates=["sim_ok"])
    assert lvl.achieved
    assert lvl.level in ("TRL3", "TRL4")
    assert lvl.gaps
    assert not any(g == "real operational data deferred" for g in lvl.gaps)
