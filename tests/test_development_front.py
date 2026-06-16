"""Tests für development_front_mapper (erster Stein der Grenzverschiebungs-Module).

Siehe GENESIS_PLATFORM_PLAN.md §3.3.
"""


from gen.grenzverschiebung.development_front import (
    DevelopmentFrontMap,
    Grenztyp,
    map_development_front,
)


def test_jetpack_traum_produces_rich_typed_front_map():
    """Positiv (funktional): Für das kanonische Jetpack-Beispiel aus dem PLAN liefert der Mapper
    ein reichhaltiges, ehrliches DevelopmentFrontMap mit typisierten Grenzen und voller Experimentleiter."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    m = map_development_front(idee, run_id="ultra-slice-2-jetpack")

    assert isinstance(m, DevelopmentFrontMap)
    assert "Jetpack" in m.traum or "mensch" in m.traum.lower()
    assert m.run_id == "ultra-slice-2-jetpack"
    assert m.quelle is not None and "PLATFORM_PLAN" in m.quelle

    # Reichhaltige Experimentleiter (PLAN §3.3 verlangt die Kette)
    assert len(m.experimentleiter) >= 4
    assert any("Traum" in s.beschreibung or "Idee" in s.beschreibung for s in m.experimentleiter)
    assert any("sicherer test" in s.beschreibung.lower() for s in m.experimentleiter)

    # Typisierte Grenzen (kein flacher "unmöglich")
    assert len(m.grenzen) >= 3
    assert any(t == Grenztyp.POSSIBLE_BUT_UNSAFE_DIRECTLY for t in m.grenzen.values())
    assert any(t in (Grenztyp.NEEDS_BREAKTHROUGH, Grenztyp.MISSING_MODEL) for t in m.grenzen.values())

    # Fehlende Fähigkeiten + Abbruchkriterien ehrlich (kein Optimismus)
    assert len(m.fehlende_faehigkeiten) >= 2
    assert len(m.abbruchkriterien) >= 1
    assert any("safety" in " ".join(m.fehlende_faehigkeiten).lower() or "Failure" in " ".join(m.abbruchkriterien) for _ in [0])

    # Nächste Stufe verweist auf nachfolgende Module
    assert m.naechste_stufe is not None
    assert "safety_ladder" in m.naechste_stufe or "capability_gap" in m.naechste_stufe.lower()


def test_generic_idea_still_produces_honest_minimal_map():
    """Fallback für beliebige Ideen bleibt ehrlich (keine Halluzination von Details)."""
    idee = "Ein tragbares Gerät, das Schwerkraft lokal aufhebt."
    m = map_development_front(idee)

    assert isinstance(m, DevelopmentFrontMap)
    assert len(m.fehlende_faehigkeiten) > 0
    assert m.heutige_grenze is not None and len(m.heutige_grenze) > 20
    # Kein "das geht schon" – entweder hypothese oder missing_*
    assert any(step.hypothese for step in m.experimentleiter) or any(t == Grenztyp.MISSING_MEASUREMENT for t in m.grenzen.values())
