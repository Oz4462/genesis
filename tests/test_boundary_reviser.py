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


def test_generic_idea_produces_minimal_revision():
    """Generische Idee → minimale Revision (generic item)."""
    idee = "Ein tragbares Gerät, das Schwerkraft lokal aufhebt."
    front = map_development_front(idee)
    frontier = watch_frontier(front)
    revised = revise_boundary(front, frontier)

    assert len(revised.revisions) >= 1
    assert "generische" in revised.revisions[0].changed_boundary.lower() or "Machbarkeit" in revised.revisions[0].changed_boundary
