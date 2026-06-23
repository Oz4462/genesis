"""Characterization + facade-killer tests für development_front_mapper.

Diese Tests beweisen, dass `map_development_front` seine Eingabe
(`idee` + `bekannte_grenzen`) im GENERISCHEN Pfad WIRKLICH konsumiert —
nicht nur das hartcodierte Jetpack-Beispiel. Vor dem Fix scheiterten sie,
weil der else-Zweig eine fast-fixe Skelett-Map lieferte, die `bekannte_grenzen`
nur zu einem flachen MISSING_MEASUREMENT-Dict verarbeitete und `idee` ignorierte.

Siehe GENESIS_PLATFORM_PLAN.md §3.3 und docs/audit/DEPTH_AUDIT_development_front.md.
"""

import pytest
from hypothesis import assume, given, strategies as st

from gen.grenzverschiebung.development_front import (
    DevelopmentFrontMap,
    ExperimentleiterSchritt,
    Grenztyp,
    map_development_front,
)


# --- Facade-Killer 1: bekannte_grenzen werden überall referenziert + typisiert ---

def test_generic_bekannte_grenzen_appear_in_grenzen_faehigkeiten_and_steps():
    """Jede bekannte Grenze muss (a) typisiert in `grenzen`, (b) in
    `fehlende_faehigkeiten` und (c) in mindestens einem Experimentleiter-Schritt
    auftauchen. Ein Facade-Skelett würde sie nur flach in `grenzen` ablegen."""
    grenzen_in = [
        "Es fehlt eine reale Messung der Schubkraft am Prüfstand",
        "Akku-Energiedichte reicht nicht für den Durchbruch",
        "Modell der nichtlinearen Regelung fehlt",
    ]
    m = map_development_front(
        "Eine schwebende Plattform für Lasten", bekannte_grenzen=grenzen_in
    )

    for g in grenzen_in:
        # (a) typisierter Eintrag in grenzen
        assert g in m.grenzen, f"{g!r} fehlt in grenzen"
        assert isinstance(m.grenzen[g], Grenztyp)
        # (b) in fehlende_faehigkeiten referenziert
        assert any(g in f for f in m.fehlende_faehigkeiten), f"{g!r} nicht in fehlende_faehigkeiten"
        # (c) in mindestens einem Experimentleiter-Schritt referenziert
        assert any(g in s.beschreibung for s in m.experimentleiter), f"{g!r} in keinem Schritt"


def test_generic_grenztyp_is_derived_from_text_not_constant():
    """Der Grenztyp muss AUS dem Text folgen — eine Messlücke ≠ ein Durchbruch.
    Ein konstanter MISSING_MEASUREMENT-Default (alte Facade) würde hier scheitern."""
    m = map_development_front(
        "Teststand",
        bekannte_grenzen=[
            "reale Messung der Temperatur fehlt",          # → MISSING_MEASUREMENT
            "braucht einen Durchbruch bei Supraleitern",   # → NEEDS_BREAKTHROUGH
            "widerspricht der Thermodynamik",              # → CONTRADICTS_CURRENT_MODEL
            "es fehlt ein Bauteil / Material",             # → MISSING_COMPONENT
        ],
    )
    assert m.grenzen["reale Messung der Temperatur fehlt"] == Grenztyp.MISSING_MEASUREMENT
    assert m.grenzen["braucht einen Durchbruch bei Supraleitern"] == Grenztyp.NEEDS_BREAKTHROUGH
    assert m.grenzen["widerspricht der Thermodynamik"] == Grenztyp.CONTRADICTS_CURRENT_MODEL
    assert m.grenzen["es fehlt ein Bauteil / Material"] == Grenztyp.MISSING_COMPONENT
    # Mindestens zwei verschiedene Typen → der Typ ist nicht konstant.
    assert len({m.grenzen[g] for g in m.grenzen}) >= 3


# --- Facade-Killer 2: idee fließt in die Map ein → zwei Ideen ≠ gleiche Map ---

def test_two_different_ideen_yield_meaningfully_different_maps():
    """Zwei verschiedene Ideen müssen meaningfully verschiedene Maps ergeben —
    sonst wird `idee` ignoriert (reine Facade)."""
    a = map_development_front("Ein selbstheilender Beton für Brücken")
    b = map_development_front("Eine leise Drohne für Stadtlieferungen")

    assert a.traum != b.traum
    assert a.heutige_grenze != b.heutige_grenze
    # Die Idee taucht wortwörtlich in heutiger Grenze und im ersten Schritt auf.
    assert "Beton" in a.heutige_grenze and "Drohne" in b.heutige_grenze
    assert any("Beton" in s.beschreibung for s in a.experimentleiter)
    assert any("Drohne" in s.beschreibung for s in b.experimentleiter)


def test_breakthrough_grenze_adds_honest_abort_criterion():
    """Eine Grenze, die einen Durchbruch/Widerspruch verlangt, muss ein hartes
    Abbruchkriterium nach sich ziehen (aus dem Typ abgeleitet, nicht erfunden)."""
    m = map_development_front(
        "Reaktionsloser Antrieb",
        bekannte_grenzen=["widerspricht der Impulserhaltung"],
    )
    assert any("widerspricht der Impulserhaltung" in k for k in m.abbruchkriterien)


# --- Facade-Killer 3: ehrliche Abstinenz statt erfundener Pseudo-Grenze ---

def test_no_bekannte_grenzen_is_honestly_abstaining_not_canned():
    """Ohne bekannte Grenzen darf KEINE kanonische Pseudo-Grenze
    ('generische Machbarkeit der Idee') erfunden werden — `grenzen` bleibt leer."""
    m = map_development_front("Irgendeine Idee ohne benannte Grenzen")
    assert m.grenzen == {}
    # Trotzdem ehrlich: eine Meta-Lücke + ein Hypothese-Schritt bleiben.
    assert len(m.fehlende_faehigkeiten) >= 1
    assert any(s.hypothese for s in m.experimentleiter)


def test_whitespace_grenzen_are_dropped():
    """Leere/Whitespace-Grenzen sind kein Signal und dürfen nicht in die Map."""
    m = map_development_front("Idee", bekannte_grenzen=["   ", "", "echte Grenze: Messung fehlt"])
    assert "echte Grenze: Messung fehlt" in m.grenzen
    assert len(m.grenzen) == 1


# --- Negativpfad: leere idee schlägt laut fehl (keine stille leere Map) ---

@pytest.mark.parametrize("bad", ["", "   ", "\t\n  "])
def test_empty_or_whitespace_idee_raises(bad):
    with pytest.raises(ValueError, match="idee darf nicht leer"):
        map_development_front(bad)


# --- Regression: der reiche Jetpack-Pfad bleibt erhalten (geschützter Spezialfall) ---

def test_jetpack_rich_path_still_intact():
    """Der hartcodierte Jetpack-Pfad bleibt als geschützte Regression bestehen."""
    m = map_development_front("Ich will ein Jetpack bauen, das Menschen frei fliegen lässt.")
    assert isinstance(m, DevelopmentFrontMap)
    assert len(m.experimentleiter) >= 4
    assert any(t == Grenztyp.POSSIBLE_BUT_UNSAFE_DIRECTLY for t in m.grenzen.values())
    assert "safety_ladder" in (m.naechste_stufe or "")


# --- Property: jede bekannte Grenze ist immer in grenzen + faehigkeiten + schritt ---

@given(
    idee=st.text(min_size=1).filter(lambda s: s.strip() != ""),
    grenzen=st.lists(
        st.text(min_size=1).filter(lambda s: s.strip() != "" and "jetpack" not in s.lower()),
        min_size=1,
        max_size=6,
        unique_by=lambda s: s.strip(),
    ),
)
def test_property_every_grenze_consumed(idee, grenzen):
    """Invariante: jede (nicht-leere) bekannte Grenze wird im generischen Pfad
    typisiert, referenziert und in einen Schritt überführt — für ALLE Eingaben."""
    # Generischen Pfad erzwingen: idee darf den Jetpack-Spezialfall nicht treffen.
    low = idee.lower()
    assume("jetpack" not in low and not ("mensch" in low and "fliegen" in low))
    m = map_development_front(idee, bekannte_grenzen=grenzen)
    cleaned = [g.strip() for g in grenzen if g.strip()]
    for g in cleaned:
        assert g in m.grenzen
        assert any(g in f for f in m.fehlende_faehigkeiten)
        assert any(g in s.beschreibung for s in m.experimentleiter)
    assert isinstance(m.experimentleiter[0], ExperimentleiterSchritt)
