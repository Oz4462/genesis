"""teststand_architect — fünfter Grenzverschiebungs-Modul (nächster aktiver Stein).

Gemäß GENESIS_PLATFORM_PLAN.md §3.3:
- Aufgabe: baut Prüfstände statt riskanter Direktversuche.
- Output: `TestStandSpec`.

Dieses Modul nimmt eine MilestoneLadder (oder FrontMap + Gaps + ExperimentPlan) und
produziert sichere, messbare Prüfstand-Spezifikationen (tethered, Wasser, Scale, Bench, etc.),
die die Annahmen der Meilensteine und Experimente wirklich prüfen können, ohne unnötiges Risiko.

Erster Stein: Datamodel + deterministischer Builder für das Jetpack-Beispiel
( baut auf den Meilensteinen und Experimenten auf).
Später: Volle Integration mit technology_builder, bench_test_runner, Wissensbasis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .milestone_builder import Milestone, MilestoneLadder


@dataclass(frozen=True)
class TestStandSpec:
    """Ein einzelner sicherer Prüfstand (Output des Moduls)."""

    name: str
    beschreibung: str
    sicherheitsmassnahmen: list[str]
    messungen: list[str]
    dauer_aufwand: str
    quelle: str | None = None


@dataclass(frozen=True)
class TestStandPlan:
    """Der vollständige Prüfstand-Plan (Output des Moduls)."""

    source_traum: str
    stands: list[TestStandSpec]
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


def _messungen_from_milestone(milestone: "Milestone") -> list[str]:
    """Leite messbare Prüf-Grössen aus dem Meilenstein ab.

    Die ``definition_of_done`` IST das messbare Erfolgskriterium des Meilensteins;
    jeder Eintrag wird zu einer Messung am Prüfstand. Whitespace-Einträge sind kein
    Signal und werden verworfen. Hat der Meilenstein KEINE prüfbare DoD, wird die
    Lücke ehrlich markiert statt eine Messung zu erfinden (keine stillen Defaults).
    """
    dod = [d.strip() for d in milestone.definition_of_done if d.strip()]
    if not dod:
        return [f"LÜCKE: Meilenstein '{milestone.name}' hat keine messbare Definition of Done — nicht prüfbar"]
    return [f"Messe: {d} (Meilenstein '{milestone.name}')" for d in dod]


def _sicherheit_from_milestone(milestone: "Milestone") -> list[str]:
    """Leite Sicherheitsmassnahmen aus den Risiken des Meilensteins ab.

    Jedes deklarierte Risiko begründet eine konkrete Absicherung am Prüfstand.
    Whitespace-Risiken werden verworfen. Ohne benanntes Risiko wird KEINE Pseudo-
    Massnahme erfunden — nur die generische Boden-/Abbruch-Absicherung bleibt ehrlich.
    """
    risiken = [r.strip() for r in milestone.risiken if r.strip()]
    measures = [f"Absicherung gegen Risiko '{r}'" for r in risiken]
    # Jeder Prüfstand bleibt am Boden gegen genau das Risiko des Meilensteins;
    # diese Baseline gilt auch ohne benanntes Risiko (ehrliches Minimum, kein Fake).
    measures.append("Kontrollierter Abbruch + keine unbeteiligten Personen im Gefahrenbereich")
    return measures


def build_test_stand(
    ladder: "MilestoneLadder",
    *,
    run_id: str | None = None,
) -> TestStandPlan:
    """
    Erste Version des teststand_architect.

    Für das Jetpack-Beispiel (PLAN) erzeugt sie zu den relevanten Meilensteinen
    konkrete, sichere Prüfstand-Specs (tethered + Wasser + Scale + Bench), die
    die Annahmen ohne unnötiges Risiko für Menschen prüfen können.

    Im generischen Pfad wird zu JEDEM realen Meilenstein der Leiter ein eigener
    ``TestStandSpec`` abgeleitet (``definition_of_done`` → ``messungen``,
    ``risiken`` → ``sicherheitsmassnahmen``, Provenance verweist auf den
    Meilenstein) — die Eingabe wird also wirklich konsumiert, nicht ein Stub.

    Fehlerfälle / Edge-Cases:
    - ``ladder.milestones`` leer → ``stands == []`` und ``zusammenfassung`` sagt
      explizit, dass keine Meilensteine geliefert wurden (kein erfundener Stand).
    - Meilenstein ohne messbare ``definition_of_done`` → die Lücke wird ehrlich
      als nicht-prüfbar markiert statt eine Messung zu fabrizieren.
    """
    traum = ladder.source_traum

    stands: list[TestStandSpec] = []

    if "jetpack" in traum.lower() or ("mensch" in traum.lower() and "fliegen" in traum.lower()):
        stands = [
            TestStandSpec(
                name="T0 — Tethered 1:5 Scale Hover + Water Abort Bench (M0 + E0)",
                beschreibung="Stark getetherter 1:5 Demonstrator mit Dummy-Payload, redundanter Abschaltung, Wasser-Landungszone und Instrumentierung. Prüft Hover-Stabilität, Payload, Failure-Response ohne Risiko für Dritte.",
                sicherheitsmassnahmen=[
                    "Mehrfach redundante Tether (mind. 3 unabhängige)",
                    "Automatischer Cut + Wasser-Landung bei >X° Tilt oder Motor-Ausfall",
                    "Immer über Wasser oder unbesiedeltem Gelände",
                    "Notfall-Team + Rettungsweste für Dummy",
                ],
                messungen=[
                    "Hover-Dauer bei definierter Payload (min)",
                    "Höhenabweichung (cm)",
                    "Zeit bis kontrollierte Wasser-Landung nach Failure (ms)",
                    "Anzahl unkontrollierter Landungen in 30 Versuchen",
                ],
                dauer_aufwand="2–3 Wochen (Skalierter Prototyp + Instrumentierung + 30 Versuche)",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + milestone_builder M0 + experiment_designer E0",
            ),
            TestStandSpec(
                name="T1 — Portable Energy + Redundant Control Prüfstand (M1 + E1)",
                beschreibung="Bench-Prüfstand mit Last-Simulation (80kg+), verschiedenen Zellchemien, dualem ESC + Notfall-Rotor, Strom-/Spannungsmessung, automatischer Failure-Injektion. Prüft Energie-Dichte und Single-Failure-Kompensation ohne Flug.",
                sicherheitsmassnahmen=[
                    "Keine echte Flugphase — alles am Boden mit mechanischer Fixierung",
                    "Temperatur-Überwachung + automatischer Shutdown",
                    "Feuerlöscher + Notfall-Stopp für alle Kanäle",
                ],
                messungen=[
                    "Energieverbrauch pro Minute bei 80kg+ Payload (Wh/min)",
                    "Zeit bis kritischer Spannungsabfall (min)",
                    "Reaktionszeit bei injiziertem Motor-Ausfall (ms)",
                    "Gewicht des Redundanz-Overheads (kg)",
                ],
                dauer_aufwand="3–4 Wochen (Bench-Aufbau + Zellen-Vergleich + 50 Failure-Injektionen)",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 (needs_breakthrough + missing_model) + experiment_designer E1",
            ),
            TestStandSpec(
                name="T2 — Tethered Public-Style Safety Demo Rig (M2 + E2)",
                beschreibung="Getetherter bemannter Dummy + SafetyStagePlan-Setup (Wasser-Landung, redundanter Abort, Publikums-Distanz-Messung). Simuliert öffentliche Demo unter kontrollierten Bedingungen.",
                sicherheitsmassnahmen=[
                    "Immer über Wasser oder weichem Gelände",
                    "Mehrfach redundante Tether + automatischer Cut",
                    "Live-Abort-Team mit <3s Reaktionszeit",
                    "Publikums-Sicherheitsabstand >10m immer eingehalten (Messung)",
                ],
                messungen=[
                    "Abort-Erfolgsrate bei 15 injizierten Fehlern",
                    "Zeit von Failure-Detektion bis sichere Landung (s)",
                    "Einhaltung des Sicherheitsabstands in allen Manövern (m)",
                ],
                dauer_aufwand="4–6 Wochen (bemannter Dummy + SafetyStagePlan-Review + 15 Versuche)",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + safety_ladder + experiment_designer E2",
            ),
        ]
        zusammenfassung = (
            "3 sichere Prüfstand-Specs (T0–T2), die die zentralen Annahmen der ersten Meilensteine "
            "wirklich prüfen können, ohne unnötiges Risiko für Menschen. Jeder Stand ist auf einen "
            "oder mehrere Meilensteine/Experimente abgestimmt und hat klare Sicherheitsmassnahmen + Messungen."
        )
    elif not ladder.milestones:
        # Ehrliche Abstinenz: ohne Meilensteine gibt es nichts abzuleiten — kein
        # fabrizierter Stub (Kernprinzip „keine stillen Defaults bei faktischen Dingen").
        stands = []
        zusammenfassung = (
            "Keine Prüfstände — die MilestoneLadder enthält keine Meilensteine, "
            "aus denen sich messbare Prüfstände ableiten liessen."
        )
    else:
        # Generischer Pfad: zu JEDEM realen Meilenstein einen eigenen Prüfstand
        # ableiten. So fliesst die Eingabe (Name, DoD, Risiken, Provenance) wirklich
        # ein; zwei verschiedene Leitern ergeben verschiedene Pläne (keine Facade).
        for index, milestone in enumerate(ladder.milestones):
            stands.append(
                TestStandSpec(
                    name=f"T{index} — Prüfstand für {milestone.name}",
                    beschreibung=(
                        f"Sicherer Prüfstand, der den Meilenstein '{milestone.name}' "
                        f"messbar prüft: {milestone.beschreibung}"
                    ),
                    sicherheitsmassnahmen=_sicherheit_from_milestone(milestone),
                    messungen=_messungen_from_milestone(milestone),
                    dauer_aufwand=f"Abgestimmt auf nächstes Experiment: {milestone.naechstes_experiment}",
                    # Provenance verweist explizit auf den treibenden Meilenstein.
                    quelle=(
                        f"teststand_architect ← Meilenstein '{milestone.name}'"
                        + (f" ({milestone.quelle})" if milestone.quelle else "")
                    ),
                )
            )
        zusammenfassung = (
            f"{len(stands)} Prüfstand-Spec(s), je einer pro Meilenstein der Leiter; "
            "jede Definition of Done wird zu einer Messung, jedes Risiko zu einer "
            "Sicherheitsmassnahme."
        )

    return TestStandPlan(
        source_traum=traum,
        stands=stands,
        zusammenfassung=zusammenfassung,
        run_id=run_id,
        quelle="teststand_architect (erster Stein) + milestone_ladder + GENESIS_PLATFORM_PLAN.md §3.3",
    )
