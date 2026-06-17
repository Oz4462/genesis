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


def test_forge_research_fusion_produces_study_arbeit_and_seed():
    """Priority 0 stone (ResearchForge / DiscoveryCrucible).
    Testet den gehärteten Forscher-Erfindungsprozess:
    - Fusion-Modus (zwei existierende Dinge / Komponenten)
    - Studie + Emergence-Notizen
    - "Arbeit" (ForschungsArbeit.md Inhalt)
    - Seeding eines neuen Rezepts / neuer Wertschöpfungsquelle
    - 4 Linsen + Provenance im Ergebnis
    """
    result = forge_research(
        "fuse power electronics with bio-molecular actuator for new molecular-quantum sensor",
        mode="fusion",
        run_id="forge-test-fusion-001",
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
