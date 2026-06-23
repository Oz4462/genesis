"""Tests für boundary_reviser (zehnter Stein der Grenzverschiebungs-Module).

Siehe GENESIS_PLATFORM_PLAN.md §3.3.
"""

from gen.grenzverschiebung.development_front import map_development_front
from gen.grenzverschiebung.breakthrough_watch import watch_frontier
from gen.grenzverschiebung.boundary_reviser import revise_boundary


def test_jetpack_produces_revised_front_map():
    """Für das Jetpack-Beispiel revised der Reviser die Map basierend auf neuen Frontier-Items (z.B. downgraded Grenzen)."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    front = map_development_front(idee, run_id="rev-test-001")
    frontier = watch_frontier(front, run_id="rev-test-001")  # reuse the watch from previous
    revised = revise_boundary(front, frontier, run_id="rev-test-001")

    assert revised.source_traum == idee
    assert len(revised.revisions) >= 2
    # Check that some boundary was revised (e.g. Energie downgraded)
    assert any("Energie" in r.changed_boundary or "Recovery" in r.changed_boundary for r in revised.revisions)
    # The revised_map has updated grenzen
    assert "possible_but_unsafe_directly" in str(revised.revised_map.grenzen.values()) or "known_possible" in str(revised.revised_map.grenzen.values())


def test_generic_idea_with_no_known_boundaries_yields_honest_noop():
    """Generische Idee ohne benannte Grenzen → ehrlicher No-op (keine fabrizierte Revision).

    Integriertes Verhalten: development_front bleibt für eine generische Idee ohne
    bekannte_grenzen ehrlich abstinent (``grenzen == {}``), und breakthrough_watch
    liefert nur ein abstinentes Watch-Target. Der evidenz-getriebene boundary_reviser
    erfindet daraufhin KEINE „generische Machbarkeit"-Revision mehr (das war die alte
    Fassade, die beide Features bewusst entfernt haben — „keine stillen Defaults"),
    sondern gibt die Map substanziell unverändert zurück. Das ist ein echter Negativtest:
    er schlägt fehl, sobald der Reviser eine Revision ohne reale Evidenz fabriziert.
    """
    idee = "Ein tragbares Gerät, das Schwerkraft lokal aufhebt."
    front = map_development_front(idee)
    frontier = watch_frontier(front)
    revised = revise_boundary(front, frontier)

    assert front.grenzen == {}  # T05: ehrlich abstinent statt erfundener Pseudo-Grenze
    assert len(revised.revisions) == 0
    assert "No boundary revision emitted" in revised.zusammenfassung
    assert revised.revised_map.grenzen == front.grenzen
    assert revised.revised_map.heutige_grenze == front.heutige_grenze
