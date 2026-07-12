"""Tests for LUMENCRUCIBLE Ω v1 (rekursive HORIZON-Extension + Self-Ascent).

2 Tests (Jetpack-Kanon + Generic) nach Projekt-Muster.
Prüft:
- realen Frontier via map_development_front
- LumenHammer mit konkreter next_step + gate
- echtes OmegaCertificate + GateReceipt + LearningNotes
- Claim mit Provenance
- verifizierbaren Self-Improvement (WORK_QUEUE.md Append mit Quelle)
- 4 Linsen / Provenance überall
"""

from gen.core.state import ClaimStatus
from gen.grenzverschiebung.lumencrucible import LumenCrucible, process_dream, LumenHammer, forge_research


def test_lumencrucible_jetpack_produces_hammer_omega_certificate_and_self_improvement(tmp_path):
    """Kanonischer Jetpack-Traum → erster Hammer + Omega + realer Append (in isolierter Queue)."""
    wq = tmp_path / "WORK_QUEUE.md"
    crucible = LumenCrucible()
    result = crucible.process_dream(
        "jetpack hover energy impossible with current battery for sustained manned flight over people",
        run_id="lumen-test-jet-001",
        work_queue_path=str(wq),
    )

    # Hammer
    hammer = result["hammer"]
    assert isinstance(hammer, LumenHammer)
    assert "EmberNest" in hammer.experiment_name or "Thrust" in hammer.experiment_name
    assert "tethered" in hammer.description.lower() or "teststand" in hammer.description.lower()
    assert hammer.gate_to_pass in ("gate_delta_plus", "gate_delta_plus_coverage")
    assert "quelle" in hammer.quelle.lower() or "HORIZON" in hammer.quelle

    # OmegaCertificate (real)
    cert = result["omega_certificate"]
    assert cert.run_id == "lumen-test-jet-001"
    assert len(cert.gate_receipts) >= 1
    assert len(cert.learning_notes) >= 2
    assert any("self_ascent" in n.kind for n in cert.learning_notes)

    # Claim
    claim = result["claim"]
    assert "lumen" in claim.id
    assert len(claim.sources) >= 2
    assert claim.status in ("VERIFIED", "verified")

    # Self-Improvement (realer Append)
    improvement = result["self_improvement"]
    assert "LUMENCRUCIBLE" in improvement
    assert "WORK_QUEUE" in improvement or "Append" in improvement or "self_ascent" in improvement.lower()

    # WORK_QUEUE.md wurde tatsächlich erweitert (isolierte Datei, nicht die echte Queue)
    wq_text = wq.read_text(encoding="utf-8")
    assert "LUMENCRUCIBLE" in wq_text and "lumen-test-jet-001" in wq_text


def test_lumencrucible_generic_fallback_produces_valid_output_and_improvement(tmp_path):
    """Generischer Traum → funktioniert trotzdem (ehrlicher Fallback) + Self-Improve."""
    wq = tmp_path / "WORK_QUEUE.md"
    result = process_dream("sustained personal flight with portable energy beyond current limits", run_id="lumen-test-gen-002", work_queue_path=str(wq))

    hammer = result["hammer"]
    assert isinstance(hammer, LumenHammer)
    assert hammer.experiment_name
    assert hammer.next_step
    q = hammer.quelle.lower()
    assert "horizon" in q or "development_front" in q or "lumencrucible" in q

    cert = result["omega_certificate"]
    assert cert.run_id == "lumen-test-gen-002"
    assert len(cert.learning_notes) > 0

    # Auch hier muss ein realer Append passiert sein (isolierte Datei)
    wq_text = wq.read_text(encoding="utf-8")
    assert "LUMENCRUCIBLE" in wq_text and "lumen-test-gen-002" in wq_text


def test_self_ascent_is_idempotent_does_not_flood_queue(tmp_path):
    """Self-Ascent darf die Work-Queue nicht fluten: derselbe konkrete Vorschlag wird
    genau EINMAL eingetragen, egal wie oft process_dream läuft (Dedup-Fix gegen den
    historischen ~150-Zeilen-Bug)."""
    wq = tmp_path / "WORK_QUEUE.md"
    for i in range(5):
        process_dream(
            "jetpack hover energy impossible for sustained manned flight test",
            run_id=f"dedup-run-{i}",
            work_queue_path=str(wq),
        )
    text = wq.read_text(encoding="utf-8")
    # Der konkrete Vorschlag erscheint genau einmal, nicht fünfmal.
    assert text.count("dream_to_hammer_gate") == 1
    assert "APPEND_FAILED" not in text


def test_forge_research_fusion_produces_study_arbeit_and_seed(tmp_path):
    """Priority 0 stone (ResearchForge / DiscoveryCrucible).
    Testet den gehärteten Forscher-Erfindungsprozess:
    - Fusion-Modus (zwei existierende Dinge / Komponenten)
    - Studie + Emergence-Notizen
    - "Arbeit" (ForschungsArbeit.md Inhalt)
    - Seeding eines neuen Rezepts / neuer Wertschöpfungsquelle
    - 4 Linsen + Provenance im Ergebnis
    Hermetisch: schreibt via out_dir in tmp_path statt runs/ im CWD (Review F8).
    """
    result = forge_research(
        "fuse power electronics with bio-molecular actuator for new molecular-quantum sensor",
        mode="fusion",
        run_id="forge-test-fusion-001",
        out_dir=str(tmp_path / "forge_out"),
    )

    assert result.idea
    assert result.mode in ("fusion", "multisim")
    assert result.run_id == "forge-test-fusion-001"

    # Study (falsifizierbar, mit Hypothese/Methode/Metriken)
    study = result.study
    assert study.name
    assert "Fusion" in study.method or "fusion" in study.method.lower()
    assert len(study.metrics) >= 2
    assert len(study.success_criteria) >= 1

    # Emergence / Research output
    assert len(result.emergence_notes) > 0
    assert any("4 Linsen" in n or "4-Linsen" in n for n in result.emergence_notes) or result.four_linsen

    # Die eigentliche "Arbeit" (Paper / Work)
    assert result.arbeit_markdown
    assert "# ForschungsArbeit" in result.arbeit_markdown or "ForschungsArbeit" in result.arbeit_markdown
    assert "Hypothese" in result.arbeit_markdown
    assert result.quelle and "user requirement" in result.quelle.lower()

    # Neues Rezept / neue Wertschöpfungsquelle wurde (versucht) geseedet
    # (kann None sein im ersten Stein, wenn Store nicht voll verfügbar — aber Feld existiert)
    assert hasattr(result, "new_recipe_id")

    # 4 Linsen explizit vorhanden
    assert result.four_linsen
    assert "L1" in result.four_linsen or "L2" in result.four_linsen

    # Mehrwert-Indikatoren
    assert result.mehwert_indicators
    assert "new_value_source" in result.mehwert_indicators or "has_arbeit" in result.mehwert_indicators

    # Provenance durchgängig
    assert "lumencrucible.forge_research" in result.provenance or "forge_research" in result.provenance


def test_forge_lernzyklus_is_honestly_planned_not_executed(tmp_path):
    """Review F1: Der 8-Schritt-Lernzyklus wird von forge_research NICHT ausgeführt
    (die echte Engine lebt in lernmaschine/engine.py). Die frühere Version druckte
    via `or True` eine statische lern_summary als durchgeführt. Jetzt muss der
    Status ehrlich PLANNED_NOT_EXECUTED sein — im Struct UND in der Arbeit."""
    result = forge_research(
        "multi component emergence probe",
        mode="multisim",
        run_id="forge-test-lern-001",
        out_dir=str(tmp_path / "forge_out"),
    )
    assert result.lern_steps, "lern_steps darf nicht leer sein (Plan muss ausgewiesen werden)"
    assert result.lern_steps[0].get("status") == "PLANNED_NOT_EXECUTED"
    assert "PLANNED_NOT_EXECUTED" in result.arbeit_markdown
    assert "nicht ausgeführt" in result.arbeit_markdown
    # Kein fingierter Vollzug mehr:
    assert "applied=True" not in result.arbeit_markdown


def test_forge_seed_failure_leaves_recipe_id_none_and_records_reason(tmp_path, monkeypatch):
    """Review F3: Wenn save_fragment fehlschlägt, darf new_recipe_id NICHT gesetzt
    werden (die Arbeit würde sonst ein geseedetes Rezept behaupten). Stattdessen:
    None + mehwert_indicators['seed_failed'] mit Grund."""
    import gen.wissensbasis.store as wb_store

    def _boom(*args, **kwargs):
        raise OSError("store not writable (test)")

    monkeypatch.setattr(wb_store, "save_fragment", _boom)
    result = forge_research(
        "fusion of two proven things",
        mode="fusion",
        run_id="forge-test-seedfail-001",
        out_dir=str(tmp_path / "forge_out"),
    )
    assert result.new_recipe_id is None
    assert result.mehwert_indicators.get("new_value_source") is False
    assert "seed_failed" in result.mehwert_indicators
    assert "store not writable" in result.mehwert_indicators["seed_failed"]
    # Die Arbeit weist das Rezept als pending aus, nicht als geseedet
    assert "pending" in result.arbeit_markdown


def test_forge_out_dir_is_hermetic_and_writes_artifacts(tmp_path):
    """Review F8: out_dir-Parameter lenkt alle Forge-Artefakte um (kein runs/ im CWD)."""
    out = tmp_path / "my_forge"
    result = forge_research(
        "independent components emergence",
        mode="multisim",
        run_id="forge-test-outdir-001",
        out_dir=str(out),
    )
    assert (out / "FORSCHUNGSARBEIT.md").exists()
    assert (out / "EMERGENCE_SUMMARY.txt").exists()
    assert result.mehwert_indicators["artifact_dir"] == str(out)


def test_process_dream_degrades_claim_when_multi_domain_stages_skipped(tmp_path):
    """Review F2 + F7: Ein komplexer Traum versucht den Multi-Domain-Block; scheitern
    Stufen (heute: .architekt-Import), werden sie strukturiert in
    multi_domain['skipped'] erfasst, der Claim wird degradiert (UNVERIFIED, <=0.7)
    und die quelle behauptet keine nicht-gelaufenen Stufen."""
    wq = tmp_path / "WORK_QUEUE.md"
    result = process_dream(
        "build a complex robot with power board and circuit control",
        run_id="lumen-test-complex-001",
        work_queue_path=str(wq),
    )
    md = result["multi_domain"]
    skipped = md.get("skipped") or []
    claim = result["claim"]
    quelle = result["quelle"]
    # Honest contract: if optional multi-domain stages fail, they are structured in
    # multi_domain["skipped"] and the claim is degraded. If every stage runs, claim stays VERIFIED.
    if skipped:
        assert all("stage" in s and "reason" in s for s in skipped)
        assert claim.status in (ClaimStatus.UNVERIFIED, "UNVERIFIED", "unverified")
        assert claim.confidence <= 0.7
        assert "übersprungen" in quelle or "skipped" in quelle
        # do not claim stages that only appear in skipped list
        for s in skipped:
            stage = s["stage"]
            if stage == "electronics":
                assert "electronics layer" not in quelle
            if stage == "wissensbasis_seeding":
                assert "Wissensbasis-Seeding" not in quelle
            if stage == "inverse_design":
                assert "inverse design" not in quelle
    else:
        assert claim.status in (ClaimStatus.VERIFIED, "VERIFIED", "verified")
        assert claim.confidence >= 0.9


def test_process_dream_simple_dream_keeps_verified_claim(tmp_path):
    """Gegenprobe zu F2: Ein Traum ohne Multi-Domain-Trigger, bei dem alle
    versuchten Stufen laufen, behält VERIFIED/0.92."""
    wq = tmp_path / "WORK_QUEUE.md"
    result = process_dream(
        "jetpack hover energy impossible with current battery for sustained manned flight over people",
        run_id="lumen-test-simple-001",
        work_queue_path=str(wq),
    )
    assert not result["multi_domain"].get("skipped")
    claim = result["claim"]
    assert claim.status in (ClaimStatus.VERIFIED, "VERIFIED", "verified")
    assert claim.confidence == 0.92
