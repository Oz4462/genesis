"""Tests für capability_gap_analyzer (zweiter Stein der Grenzverschiebungs-Module).

Siehe GENESIS_PLATFORM_PLAN.md §3.3.
"""

from gen.grenzverschiebung.development_front import map_development_front
from gen.grenzverschiebung.capability_gap_analyzer import (
    GapCategory,
    analyze_capability_gaps,
)


def test_jetpack_front_map_produces_classified_gaps():
    """Für das kanonische Jetpack-Beispiel liefert der Analyzer klassifizierte Gaps."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    front = map_development_front(idee, run_id="gap-test-001")
    report = analyze_capability_gaps(front, run_id="gap-test-001")

    assert report.source_traum == idee
    assert len(report.gaps) >= 3
    categories = {g.category for g in report.gaps}
    assert GapCategory.MISSING_TECHNOLOGY in categories
    assert GapCategory.MISSING_MODEL in categories
    assert GapCategory.MISSING_TOOLING in categories or GapCategory.MISSING_MEASUREMENT in categories

    # Alle Gaps haben sinnvolle nächste Aktion
    assert all(g.suggested_next for g in report.gaps)

    # Summary ist ehrlich (kein Optimismus)
    assert "Gaps identifiziert" in report.summary or "kein Optimismus" in report.summary.lower()


def test_generic_idea_falls_back_to_knowledge_gap():
    """Generische Idee → ehrlicher Fallback auf MISSING_KNOWLEDGE."""
    idee = "Ein tragbares Gerät, das Schwerkraft lokal aufhebt."
    report = analyze_capability_gaps(idee=idee)

    assert len(report.gaps) >= 1
    assert any(g.category == GapCategory.MISSING_KNOWLEDGE for g in report.gaps)
    assert report.quelle is not None and "capability_gap_analyzer" in report.quelle
