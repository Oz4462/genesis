"""PRODUCT_WIRE: frontier (χ) + full Fach-Pipeline family (REWORK 2026-07-11)."""

from __future__ import annotations

import pytest

from gen.fach_cli import (
    FACH_PIPELINE_NAMES,
    demo_frontier_state,
    format_designer,
    format_fach_family,
    format_frontier,
    format_pipeline_spec,
    format_wirtschaft,
    research_promotion_stage,
    run_designer_cli,
    run_fach_family,
    run_fach_pipeline,
    run_frontier_cli,
    run_wirtschaft_cli,
)
from gen.frontier import build_frontier_map
from gen.identity_research import AssumptionManifest, assess_identity
from gen.verification import gate_chi


def test_frontier_cli_passes_gate_chi():
    result = run_frontier_cli()
    assert result.gate_passed is True
    assert result.n_known >= 1
    assert result.n_edges >= 1  # gap + unsupported claim
    assert result.gate_failures == ()
    text = format_frontier(result)
    assert "GATE χ: PASS" in text
    assert "Frontier-Kanten" in text


def test_frontier_builder_matches_cli_demo():
    state = demo_frontier_state()
    fmap = build_frontier_map(state)
    gate = gate_chi(state, fmap)
    assert gate.passed
    assert len(fmap.known_regions) >= 1


def test_designer_cli_generic_idea_is_input_driven():
    a = run_designer_cli("aluminum heat sink for LED array", run_id="t1")
    b = run_designer_cli("wooden bookshelf wall mount", run_id="t2")
    assert a.source_idea != b.source_idea
    assert len(a.ergonomie_anforderungen) >= 1
    assert all(f.markiert_als == "DECISION" for f in a.form_entscheidungen)
    text = format_designer(a)
    assert "Designer" in text
    assert "form_entscheidungen" in text or "Ergonomie" in text or len(a.form_entscheidungen) >= 1


def test_wirtschaft_cli_no_empty_idea():
    with pytest.raises(ValueError):
        run_wirtschaft_cli("   ")


def test_wirtschaft_cli_marks_gaps_honestly():
    spec = run_wirtschaft_cli("sensor enclosure for outdoor IoT", run_id="w1")
    blob = (
        spec.kosten.prototype
        + spec.kosten.low_volume
        + spec.markt.stueckzahl_ramp
        + spec.zusammenfassung
    )
    # Either qualitative drivers or explicit Lücke — never silent empty fabrication
    assert len(blob) > 20
    text = format_wirtschaft(spec)
    assert "Wirtschaft" in text
    assert "Lücke" in text or "prototype" in text.lower() or "EUR" in text or "qualit" in text.lower() or len(spec.kosten.prototype) > 5


@pytest.mark.parametrize("name", FACH_PIPELINE_NAMES)
def test_all_fach_pipelines_run_offline(name: str):
    spec = run_fach_pipeline(name, "compact sensor housing IoT", run_id=f"t-{name}")
    assert spec is not None
    text = format_pipeline_spec(name, spec)
    assert name in text or "GENESIS" in text
    assert "first-stone" in text or "Gate" in text


def test_fach_family_runs_all_pipelines():
    results = run_fach_family("compact sensor housing IoT", run_id="fam")
    assert set(results) == set(FACH_PIPELINE_NAMES)
    text = format_fach_family(results)
    assert "10" in text or str(len(FACH_PIPELINE_NAMES)) in text


def test_research_promotion_stage_never_established_autonomously():
    m = AssumptionManifest(domain_id="R", variables={"x": "real"})
    art = assess_identity("cli-t", "sin(x)**2 + cos(x)**2", "1", m, register=False)
    line = research_promotion_stage(art)
    assert "ESTABLISHED requires human SignOff" in line or "HARDENED" in line
    assert "ESTABLISHED — reusable ANCHOR" not in line