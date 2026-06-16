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

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .milestone_builder import MilestoneLadder


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
    else:
        stands = [
            TestStandSpec(
                name="T0 — Frontier Mapping Validation Rig",
                beschreibung="Einfacher Bench + Scale-Setup zur Validierung der aktuellen FrontierMap und Gap-Analyse.",
                sicherheitsmassnahmen=["Keine bemannte oder riskante Phase"],
                messungen=["Anzahl identifizierter Grenzen/Gaps", "Abdeckung der PLAN-Kategorien"],
                dauer_aufwand="1–2 Wochen",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3",
            ),
        ]
        zusammenfassung = "Minimaler Prüfstand für noch nicht detailliert analysierte Idee."

    return TestStandPlan(
        source_traum=traum,
        stands=stands,
        zusammenfassung=zusammenfassung,
        run_id=run_id,
        quelle="teststand_architect (erster Stein) + milestone_ladder + GENESIS_PLATFORM_PLAN.md §3.3",
    )
