"""Characterization + Facade-Killer-Tests für teststand_architect.

Diese Tests beweisen, dass `build_test_stand` seine Eingabe (die realen
`Milestone`-Objekte der `MilestoneLadder`) im GENERISCHEN Pfad WIRKLICH
konsumiert — nicht nur das hartcodierte Jetpack-Beispiel. Vor dem Fix lieferte
der else-Zweig EINEN fixen TestStandSpec, unabhängig von `ladder.milestones`
(reine Facade): zwei verschiedene Leitern ergaben identische Pläne, und eine
leere Leiter erzeugte trotzdem einen erfundenen Stand.

Siehe GENESIS_PLATFORM_PLAN.md §3.3 und
docs/audit/DEPTH_AUDIT_teststand_architect.md.
"""

import pytest
from hypothesis import given, strategies as st

from gen.grenzverschiebung.milestone_builder import Milestone, MilestoneLadder
from gen.grenzverschiebung.teststand_architect import (
    TestStandPlan,
    TestStandSpec,
    build_test_stand,
)


def _milestone(
    name: str,
    *,
    dod: list[str] | None = None,
    risiken: list[str] | None = None,
    naechstes: str = "nächstes Experiment",
    quelle: str | None = "test-quelle",
) -> Milestone:
    """Kleiner Konstruktor-Helper über die ECHTEN Felder von Milestone."""
    return Milestone(
        name=name,
        beschreibung=f"Beschreibung von {name}",
        definition_of_done=dod if dod is not None else [f"{name} erreicht messbar X"],
        risiken=risiken if risiken is not None else [f"{name}-Risiko"],
        naechstes_experiment=naechstes,
        quelle=quelle,
    )


def _ladder(milestones: list[Milestone], *, traum: str = "Eine generische Idee") -> MilestoneLadder:
    return MilestoneLadder(
        source_traum=traum,
        milestones=milestones,
        zusammenfassung="Test-Leiter",
        run_id="run-x",
        quelle="test",
    )


# --- Facade-Killer 1: ein Prüfstand pro realem Meilenstein, aus dem Inhalt abgeleitet ---

def test_generic_derives_one_stand_per_milestone_from_its_content():
    """Jeder Meilenstein erzeugt genau einen Prüfstand; dessen messungen folgen
    aus der definition_of_done und die sicherheitsmassnahmen aus den risiken.
    Eine Facade (ein fixer Stand) würde das nicht leisten."""
    ladder = _ladder(
        [
            _milestone("Akku-Bench", dod=["5 min Hover bei 80kg"], risiken=["Zellbrand"]),
            _milestone("Sensor-Rig", dod=["Tilt < 1° gemessen"], risiken=["Sensor-Drift"]),
        ]
    )
    plan = build_test_stand(ladder, run_id="run-x")

    assert len(plan.stands) == 2
    # DoD → Messung; Risiko → Sicherheitsmassnahme (wortwörtlich konsumiert).
    assert any("5 min Hover bei 80kg" in mess for mess in plan.stands[0].messungen)
    assert any("Zellbrand" in s for s in plan.stands[0].sicherheitsmassnahmen)
    assert any("Tilt < 1° gemessen" in mess for mess in plan.stands[1].messungen)
    assert any("Sensor-Drift" in s for s in plan.stands[1].sicherheitsmassnahmen)
    # Provenance verweist auf den treibenden Meilenstein.
    assert "Akku-Bench" in (plan.stands[0].quelle or "")
    assert "Sensor-Rig" in (plan.stands[1].quelle or "")


# --- Facade-Killer 2: zwei verschiedene Leitern ⇒ verschieden Pläne ---

def test_two_different_ladders_yield_meaningfully_different_plans():
    """Zwei verschiedene Leitern müssen verschiedene Pläne ergeben — sonst wird
    `ladder.milestones` ignoriert (reine Facade)."""
    plan_a = build_test_stand(_ladder([_milestone("Akku-Bench")]))
    plan_b = build_test_stand(_ladder([_milestone("Lager-Rig")]))

    names_a = [s.name for s in plan_a.stands]
    names_b = [s.name for s in plan_b.stands]
    assert names_a != names_b
    assert any("Akku-Bench" in n for n in names_a)
    assert any("Lager-Rig" in n for n in names_b)
    # Auch die Messungen unterscheiden sich (aus der jeweiligen DoD abgeleitet).
    assert plan_a.stands[0].messungen != plan_b.stands[0].messungen


def test_more_milestones_means_more_stands():
    """Mehr Meilensteine ⇒ mehr Prüfstände (1:1) — Beleg, dass die Liste
    tatsächlich durchlaufen wird."""
    one = build_test_stand(_ladder([_milestone("A")]))
    three = build_test_stand(_ladder([_milestone("A"), _milestone("B"), _milestone("C")]))
    assert len(one.stands) == 1
    assert len(three.stands) == 3


# --- Facade-Killer 3: ehrliche Abstinenz bei leerer Leiter (kein erfundener Stand) ---

def test_empty_ladder_yields_no_fabricated_stand():
    """Ohne Meilensteine darf KEIN Prüfstand erfunden werden — leere stands-Liste,
    und die zusammenfassung sagt das explizit (keine stillen Defaults)."""
    plan = build_test_stand(_ladder([]))
    assert plan.stands == []
    assert "keine meilensteine" in plan.zusammenfassung.lower()
    assert plan.source_traum == "Eine generische Idee"


def test_milestone_without_dod_marks_gap_honestly():
    """Ein Meilenstein ohne messbare DoD darf keine Messung fabrizieren —
    die Lücke wird ehrlich markiert."""
    plan = build_test_stand(_ladder([_milestone("Vage", dod=["   ", ""])]))
    assert len(plan.stands) == 1
    assert any("LÜCKE" in mess for mess in plan.stands[0].messungen)


def test_milestone_without_risiken_still_has_baseline_safety():
    """Ohne benanntes Risiko bleibt nur die ehrliche Boden-Baseline — keine
    erfundene risiko-spezifische Massnahme."""
    plan = build_test_stand(_ladder([_milestone("X", risiken=["  ", ""])]))
    massnahmen = plan.stands[0].sicherheitsmassnahmen
    assert len(massnahmen) == 1
    assert "Abbruch" in massnahmen[0]


# --- Negativpfad: Whitespace-Einträge in DoD/Risiken werden verworfen ---

def test_whitespace_dod_and_risiken_entries_are_dropped():
    plan = build_test_stand(
        _ladder([_milestone("M", dod=["echte DoD", "   "], risiken=["echtes Risiko", ""])])
    )
    stand = plan.stands[0]
    assert any("echte DoD" in mess for mess in stand.messungen)
    # Eine echte DoD-Messung (Whitespace verworfen).
    assert sum(1 for mess in stand.messungen if "Messe:" in mess) == 1
    # Ein echtes Risiko + eine Baseline (Whitespace verworfen).
    assert len(stand.sicherheitsmassnahmen) == 2


# --- Regression: der reiche Jetpack-Pfad bleibt unverändert erhalten ---

def test_jetpack_rich_path_still_intact():
    """Der hartcodierte Jetpack-Pfad bleibt als geschützte Regression bestehen."""
    ladder = _ladder([], traum="Ich will ein Jetpack bauen, das Menschen frei fliegen lässt.")
    plan = build_test_stand(ladder, run_id="jet")
    assert isinstance(plan, TestStandPlan)
    # 3 reiche, kuratierte Stands (T0–T2) — unabhängig von milestones.
    assert len(plan.stands) == 3
    assert plan.stands[0].name.startswith("T0 — Tethered")
    for stand in plan.stands:
        assert stand.sicherheitsmassnahmen and stand.messungen


# --- Property: jede DoD/jedes Risiko jedes Meilensteins wird konsumiert ---

# Buchstaben-Alphabet vermeidet schweres Filtern (keine Whitespace-/Jetpack-Treffer)
# und hält die Namen eindeutig — Hypothesis muss keine Eingaben verwerfen.
_NAME = st.text(alphabet=st.characters(min_codepoint=ord("a"), max_codepoint=ord("z")), min_size=1)


@given(names=st.lists(_NAME, min_size=1, max_size=5, unique=True))
def test_property_every_milestone_becomes_a_stand(names):
    """Invariante: im generischen Pfad gibt es genau einen Prüfstand pro
    Meilenstein, und jeder Stand zitiert seinen Meilenstein in der Provenance."""
    traum = "Eine generische Idee ohne Flug-Bezug"
    milestones = [_milestone(n) for n in names]
    plan = build_test_stand(_ladder(milestones, traum=traum))

    assert len(plan.stands) == len(milestones)
    for milestone, stand in zip(milestones, plan.stands):
        assert milestone.name in (stand.quelle or "")
        assert isinstance(stand, TestStandSpec)
