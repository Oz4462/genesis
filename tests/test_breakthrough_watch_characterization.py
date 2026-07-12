"""Charakterisierungs-Test für breakthrough_watch (Depth-Audit T03).

Beweist, dass `watch_frontier` die emittierten FrontierItems WIRKLICH aus den realen
offenen Gaps der Eingabe-`DevelopmentFrontMap` ableitet (statt eine Konserven-Liste
auszugeben, die `fehlende_faehigkeiten`/`grenzen` ignoriert). Diese Tests fallen gegen
die alte Facade-Implementierung durch und bestehen gegen die gefixte, gap-gebundene.

4-Linsen-Bezug:
- L1 (Wahrheit): jedes Item referenziert einen realen Gap der Map.
- L2 (Drift): andere Map → anderes Ergebnis (Input wird konsumiert).
- L3 (Naht/Vollständigkeit): Jetpack-Reichtum bleibt als Regression erhalten.
- L4 (Realisierbarkeit/Abstention): keine Gaps → ehrlich leerer FrontierUpdate; None → fail-loud.
"""

from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from gen.grenzverschiebung.development_front import (
    DevelopmentFrontMap,
    Grenztyp,
    map_development_front,
)
from gen.grenzverschiebung.breakthrough_watch import watch_frontier


# --- Helfer: eine Map mit exakt den vorgegebenen Gaps konstruieren ---

def _map_with(
    *,
    traum: str = "Generische Idee ohne bekannte Domäne",
    fehlende: list[str] | None = None,
    grenzen: dict[str, Grenztyp] | None = None,
    run_id: str | None = None,
) -> DevelopmentFrontMap:
    return DevelopmentFrontMap(
        traum=traum,
        heutige_grenze="(Test)",
        fehlende_faehigkeiten=fehlende or [],
        grenzen=grenzen or {},
        run_id=run_id,
    )


def _gap_set(front_map: DevelopmentFrontMap) -> set[str]:
    """Alle realen, offenen Gap-Texte der Map (fehlend + offene grenzen-Keys)."""
    gaps = set(front_map.fehlende_faehigkeiten)
    gaps |= {k for k, v in front_map.grenzen.items() if v is not Grenztyp.KNOWN_POSSIBLE}
    return gaps


# --- Kern-Facade-Killer ---

def test_every_item_references_a_real_gap_of_this_map():
    """L1: jede relevanz_fuer_gap ist ein echter offener Gap DIESER Map — keine Konserve."""
    front = _map_with(
        traum="Bau einer leiseren Windturbine",
        fehlende=["Bessere Lager-Lebensdauer unter Wechsellast", "Leiseres Blattprofil"],
        grenzen={"Erprobte Feldhaltbarkeit": Grenztyp.MISSING_MEASUREMENT},
    )
    update = watch_frontier(front)
    real_gaps = _gap_set(front)

    assert update.items, "Bei offenen Gaps müssen Items entstehen."
    for item in update.items:
        assert item.relevanz_fuer_gap in real_gaps, (
            f"Item-relevanz {item.relevanz_fuer_gap!r} ist kein realer Gap der Map "
            f"{real_gaps!r} — Facade-Konserve."
        )


def test_canned_jetpack_strings_do_not_leak_into_unrelated_map():
    """L2: die alte hardcodierte Liste ('Energie-Dichte P1' etc.) darf bei fremder Map nicht erscheinen."""
    front = _map_with(
        traum="Optimierung einer Brückenkonstruktion",
        fehlende=["Korrosionsschutz für 100 Jahre"],
    )
    update = watch_frontier(front)

    joined = " ".join(
        f"{it.titel} {it.relevanz_fuer_gap} {it.beschreibung}" for it in update.items
    )
    # Genau diese Strings waren die Facade-Konserve der alten Implementierung.
    assert "Energie-Dichte P1" not in joined
    assert "Redundante Flugkontrolle P2" not in joined
    assert "Solid-State" not in joined  # Jetpack-Katalog gilt nur für Flug-Domäne
    # Stattdessen: das reale Gap der Map ist adressiert.
    assert any("Korrosionsschutz" in it.relevanz_fuer_gap for it in update.items)


def test_input_sensitivity_different_gaps_give_different_update():
    """L2: zwei Maps mit unterschiedlichen Gaps → unterschiedliche FrontierUpdates."""
    a = _map_with(fehlende=["Gap A"])
    b = _map_with(fehlende=["Gap B"])
    rel_a = {it.relevanz_fuer_gap for it in watch_frontier(a).items}
    rel_b = {it.relevanz_fuer_gap for it in watch_frontier(b).items}
    assert rel_a == {"Gap A"}
    assert rel_b == {"Gap B"}
    assert rel_a != rel_b


def test_no_gaps_yields_honest_empty_update():
    """L4: Map ohne offene Gaps → leerer, abstinenter FrontierUpdate (kein fabrizierter Treffer)."""
    front = _map_with(
        traum="Etwas bereits Gelöstes",
        fehlende=[],
        grenzen={"bereits machbar": Grenztyp.KNOWN_POSSIBLE},  # known_possible zählt NICHT als offen
    )
    update = watch_frontier(front, run_id="empty-001")
    assert update.items == []
    assert update.run_id == "empty-001"
    assert "Abstention" in update.zusammenfassung or "Keine offenen" in update.zusammenfassung


def test_known_possible_boundary_is_not_treated_as_open_gap():
    """L1: ein known_possible-Schlüssel ist heute machbar und darf kein Watch-Item erzeugen."""
    front = _map_with(
        fehlende=[],
        grenzen={
            "schon machbar": Grenztyp.KNOWN_POSSIBLE,
            "echte offene Grenze": Grenztyp.MISSING_MODEL,
        },
    )
    update = watch_frontier(front)
    rels = {it.relevanz_fuer_gap for it in update.items}
    assert rels == {"echte offene Grenze"}


# --- Determinismus & Provenance ---

def test_determinism_same_map_identical_update():
    """Gleiche Map → identischer FrontierUpdate (A5 Reproduzierbarkeit)."""
    front = map_development_front(
        "Jetpack für sicheren bemannten Flug", run_id="det-001"
    )
    u1 = watch_frontier(front, run_id="det-001")
    u2 = watch_frontier(front, run_id="det-001")
    assert u1 == u2


def test_run_id_is_propagated():
    front = _map_with(fehlende=["irgendein Gap"], run_id="ignored")
    assert watch_frontier(front, run_id="rid-42").run_id == "rid-42"


# --- Regression: der reiche Jetpack-Pfad bleibt erhalten und ist input-gebunden ---

def test_jetpack_regression_rich_catalog_still_surfaces():
    """L3: die volle Jetpack-Map liefert weiterhin die drei kuratierten Durchbrüche."""
    front = map_development_front(
        "Ich will ein Jetpack bauen, das Menschen sicher fliegen lässt.",
        run_id="jp-001",
    )
    update = watch_frontier(front, run_id="jp-001")
    titel = " ".join(it.titel for it in update.items)
    assert "Solid-State Battery" in titel
    assert "Dissimilar Redundant FC" in titel
    assert "Ballistic Parachute" in titel
    # ... und jedes davon ist an einen realen Gap gebunden (input-derived, keine Konserve).
    real_gaps = _gap_set(front)
    for it in update.items:
        assert it.relevanz_fuer_gap in real_gaps


def test_jetpack_catalog_item_disappears_when_its_gap_is_absent():
    """L2: nimmt man der Flug-Domänen-Map den Energie-Gap, verschwindet das Batterie-Item.

    Beweist, dass selbst der Jetpack-Pfad input-derived ist und nicht konserviert.
    """
    front = _map_with(
        traum="jetpack ohne Energie-Sorgen",
        fehlende=["Redundant flight control for single failure"],  # nur Control-Gap, kein energy-Gap
    )
    update = watch_frontier(front)
    titel = " ".join(it.titel for it in update.items)
    assert "Solid-State Battery" not in titel  # kein Energie-Gap → kein Batterie-Item
    assert "Dissimilar Redundant FC" in titel   # Control-Gap → FC-Item bleibt


# --- Fail-loud ---

def test_none_map_raises_typeerror():
    """L4: None statt Map → fail-loud (keine stillen Defaults)."""
    with pytest.raises(TypeError):
        watch_frontier(None)  # type: ignore[arg-type]


# --- Property-based: relevanz IMMER ein realer Gap; keine Gaps → leer ---

@given(
    gaps=st.lists(
        st.text(min_size=1, max_size=40).filter(lambda s: s.strip()),
        max_size=6,
        unique=True,
    )
)
def test_property_every_relevanz_is_an_input_gap(gaps: list[str]):
    """Invariante: über beliebige Gap-Listen ist jede relevanz_fuer_gap ein Eingabe-Gap;
    leere Gap-Liste → leerer Update."""
    front = _map_with(fehlende=gaps)
    update = watch_frontier(front)
    if not gaps:
        assert update.items == []
    else:
        valid = set(gaps)
        for it in update.items:
            assert it.relevanz_fuer_gap in valid
        # Jeder Gap wird adressiert (Vollständigkeit / L3-Naht).
        addressed = {it.relevanz_fuer_gap for it in update.items}
        assert addressed == valid
