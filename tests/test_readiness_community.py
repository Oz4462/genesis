"""Readiness ladder + agent-sourced community evidence (OpenAlex / cache — no user ledger)."""

from __future__ import annotations

import json

from gen.grenzverschiebung.readiness_ladder import (
    assess_readiness,
    community_evidence,
    discover_community_literature,
)


def _fake_hits(query: str, *, max_hits: int = 8) -> list[dict]:
    return [
        {
            "openalex_id": "https://openalex.org/W1",
            "title": f"Validation study related to {query[:40]}",
            "year": 2022,
            "cited_by": 12,
            "doi": "https://doi.org/10.0/test",
        },
        {
            "openalex_id": "https://openalex.org/W2",
            "title": "Community replication of mechatronic mounts",
            "year": 2021,
            "cited_by": 5,
            "doi": None,
        },
    ][:max_hits]


def test_community_evidence_agent_sourced_no_user_data(monkeypatch):
    """User supplies nothing — agent fetch_fn provides public literature."""
    monkeypatch.setenv("GENESIS_COMMUNITY_LIVE", "1")
    monkeypatch.delenv("GENESIS_COMMUNITY_LEDGER", raising=False)
    ev = community_evidence(
        {"idea": "compliant gripper mount FDM"},
        fetch_fn=_fake_hits,
    )
    assert ev["user_data_required"] is False
    assert ev["agent_sourced"] is True
    assert ev["literature_count"] == 2
    assert ev["community_score"] > 0.0
    assert ev["community_score"] <= 0.55  # literature-only cap
    assert "openalex" in ev["quelle"]
    assert not any("create JSON" in g or "hand-write" in g for g in ev["gaps"])
    assert not any("user" in g.lower() and "must" in g.lower() for g in ev["gaps"])


def test_community_evidence_offline_does_not_blame_user(monkeypatch, tmp_path):
    monkeypatch.setenv("GENESIS_COMMUNITY_LIVE", "0")
    monkeypatch.setenv("GENESIS_COMMUNITY_LEDGER", str(tmp_path / "missing.json"))
    ev = community_evidence({}, live=False)
    assert ev["user_data_required"] is False
    assert ev["community_score"] == 0.0
    assert any("offline" in g or "not a user" in g or "user need not" in g or "user supplies" in g for g in ev["gaps"])
    assert not any("create JSON" in g for g in ev["gaps"])


def test_community_evidence_optional_agent_cache(tmp_path, monkeypatch):
    """Agent cache may enrich — still not a user form."""
    cache = tmp_path / "community_ledger.json"
    cache.write_text(
        json.dumps(
            {
                "replications": 2,
                "field_failures": ["bolt_creep"],
                "literature_hits": [
                    {"openalex_id": "https://openalex.org/W9", "title": "cached hit"}
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GENESIS_COMMUNITY_LEDGER", str(cache))
    monkeypatch.setenv("GENESIS_COMMUNITY_LIVE", "0")
    ev = community_evidence({}, live=False)
    assert ev["replications"] == 2
    assert ev["literature_count"] >= 1
    assert ev["community_score"] > 0.4
    assert "bolt_creep" in ev["field_failures"]
    assert "agent_cache" in ev["quelle"]
    assert ev["user_data_required"] is False


def test_discover_community_literature_injectable():
    hits = discover_community_literature("sindy", fetch_fn=_fake_hits)
    assert len(hits) == 2
    assert hits[0]["openalex_id"].startswith("https://openalex.org/")


def test_assess_readiness_next_gaps_not_perpetual_deferred():
    lvl = assess_readiness({"claims": [1], "cad_artifacts": True}, gates=["sim_ok"])
    assert lvl.achieved
    assert lvl.level in ("TRL3", "TRL4")
    assert lvl.gaps
    assert not any(g == "real operational data deferred" for g in lvl.gaps)


def test_assess_readiness_literature_hits_can_support_trl7():
    lvl = assess_readiness({"claims": [1], "literature_hits": [{"id": "W1"}], "bundle": True})
    assert lvl.level == "TRL7"
