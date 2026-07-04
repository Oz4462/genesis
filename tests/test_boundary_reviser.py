"""Tests für boundary_reviser (zehnter Stein der Grenzverschiebungs-Module).

Siehe GENESIS_PLATFORM_PLAN.md §3.3.
"""

from gen.grenzverschiebung.development_front import map_development_front
from gen.grenzverschiebung.breakthrough_watch import watch_frontier
from gen.grenzverschiebung.boundary_reviser import revise_boundary


def test_jetpack_produces_revised_front_map():
    """Für das Jetpack-Beispiel notiert der Reviser die Frontier-Items als Revisions-
    Kandidaten. Da die Items aus breakthrough_watch synthetisch sind (Plan-Beispiele,
    unverifiziert), werden Grenztypen NICHT aufgewertet (Review F6)."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    front = map_development_front(idee, run_id="rev-test-001")
    frontier = watch_frontier(front, run_id="rev-test-001")  # reuse the watch from previous
    revised = revise_boundary(front, frontier, run_id="rev-test-001")

    assert revised.source_traum == idee
    assert len(revised.revisions) >= 2
    # Check that some boundary was noted (e.g. Energie / Recovery Kandidaten)
    assert any("Energie" in r.changed_boundary or "Recovery" in r.changed_boundary for r in revised.revisions)
    # The revised_map has typed grenzen
    assert "possible_but_unsafe_directly" in str(revised.revised_map.grenzen.values()) or "known_possible" in str(revised.revised_map.grenzen.values())


def test_synthetic_frontier_items_do_not_upgrade_boundaries():
    """Review F6: fabrizierte '2026 Lab Results'-Items (evidence_level='synthetic')
    dürfen keinen Grenztyp aufwerten. NEEDS_BREAKTHROUGH bleibt bestehen, die
    Revision wird nur als unverifizierter Kandidat notiert."""
    from gen.grenzverschiebung.development_front import Grenztyp
    from gen.grenzverschiebung.breakthrough_watch import FrontierItem

    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    front = map_development_front(idee, run_id="rev-test-syn-001")
    frontier = watch_frontier(front, run_id="rev-test-syn-001")

    # Alle deterministisch fabrizierten Items sind als synthetisch gekennzeichnet
    assert all(item.evidence_level == "synthetic" for item in frontier.items)

    revised = revise_boundary(front, frontier, run_id="rev-test-syn-001")

    # Grenztypen bleiben unverändert (kein Upgrade aus synthetischer Evidenz)
    key = "portable Energie für 5+ min bemannten Hover >80kg"
    assert revised.revised_map.grenzen[key] == Grenztyp.NEEDS_BREAKTHROUGH
    assert (
        revised.revised_map.grenzen["validierte Manned Single-Failure Recovery <0.1s"]
        == Grenztyp.MISSING_MODEL
    )
    # fehlende Fähigkeit Energie-Dichte bleibt erhalten (nicht "adressiert")
    assert any("energy" in f.lower() or "energie" in f.lower() for f in revised.revised_map.fehlende_faehigkeiten)
    # Revisions sind Notizen, keine Aufwertungen
    for r in revised.revisions:
        assert r.new_typ == r.old_typ
        assert "unverifiziert" in r.reason.lower() or "synthetisch" in r.reason.lower()

    # Gegenprobe: ein wirklich verifiziertes Item DARF aufwerten
    verified_update = type(frontier)(
        source_traum=frontier.source_traum,
        items=[
            FrontierItem(
                titel="Solid-State Battery Breakthrough (verifizierte Messung)",
                typ="Material",
                beschreibung="Extern verifizierte Pack-Level-Messung >350 Wh/kg.",
                relevanz_fuer_gap="Energie-Dichte P1",
                moeglicher_impact="Energie-Grenze real verschoben.",
                quelle="externe verifizierte Quelle (Test)",
                evidence_level="verified",
            )
        ],
        zusammenfassung="1 verifiziertes Item",
        run_id="rev-test-syn-001",
        quelle="test",
    )
    revised2 = revise_boundary(front, verified_update, run_id="rev-test-syn-001")
    assert revised2.revised_map.grenzen[key] == Grenztyp.POSSIBLE_BUT_UNSAFE_DIRECTLY
    assert any(r.new_typ != r.old_typ for r in revised2.revisions)


def test_generic_idea_produces_minimal_revision():
    """Generische Idee → minimale Revision (generic item)."""
    idee = "Ein tragbares Gerät, das Schwerkraft lokal aufhebt."
    front = map_development_front(idee)
    frontier = watch_frontier(front)
    revised = revise_boundary(front, frontier)

    assert len(revised.revisions) >= 1
    assert "generische" in revised.revisions[0].changed_boundary.lower() or "Machbarkeit" in revised.revisions[0].changed_boundary
