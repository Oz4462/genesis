"""experiment_designer — vierter Grenzverschiebungs-Modul (nächster aktiver Stein).

Gemäß GENESIS_PLATFORM_PLAN.md §3.3:
- Aufgabe: entwirft Experimente, die eine Annahme wirklich prüfen.
- Output: `ExperimentPlan`.

Dieses Modul nimmt eine MilestoneLadder (oder FrontMap + Gaps) und
produziert konkrete, falsifizierbare Experiment-Pläne (mit Hypothese,
Messgrößen, Erfolgskriterien, Risiken, Dauer/Aufwand).

Erster Stein: Datamodel + deterministischer Designer für das Jetpack-Beispiel
( baut direkt auf den Meilensteinen der Ladder auf).
Später: Volle Integration mit Wissensbasis + teststand_architect.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .milestone_builder import MilestoneLadder


@dataclass(frozen=True)
class Experiment:
    """Ein einzelnes, falsifizierbares Experiment."""

    name: str
    hypothesen: list[str]
    messgroessen: list[str]
    erfolgskriterien: list[str]
    risiken: list[str]
    dauer_aufwand: str
    quelle: str | None = None


@dataclass(frozen=True)
class ExperimentPlan:
    """Der vollständige Experiment-Plan (Output des Moduls)."""

    source_traum: str
    experiments: list[Experiment]
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


def design_experiment_plan(
    ladder: "MilestoneLadder",
    *,
    run_id: str | None = None,
) -> ExperimentPlan:
    """
    Erste Version des experiment_designer.

    Für das Jetpack-Beispiel (PLAN) erzeugt sie zu jedem relevanten Meilenstein
    ein konkretes, falsifizierbares Experiment, das die zentrale Annahme des
    Meilensteins wirklich prüft (nicht nur "bauen und hoffen").
    """
    traum = ladder.source_traum

    experiments: list[Experiment] = []

    if "jetpack" in traum.lower() or ("mensch" in traum.lower() and "fliegen" in traum.lower()):
        experiments = [
            Experiment(
                name="E0 — Tethered Scale Hover + Abort (M0)",
                hypothesen=[
                    "Ein 1:5 getetherter Demonstrator mit redundanter Abschaltung kann >3 min stabile Hover mit >20kg Payload erreichen.",
                    "Bei Single-Failure (z.B. Motor) erfolgt kontrollierte Landung in <0.5s ohne unkontrollierten Absturz.",
                ],
                messgroessen=[
                    "Hover-Dauer bei definierter Payload",
                    "Abweichung von Soll-Höhe (cm)",
                    "Zeit bis kontrollierte Landung nach Failure-Trigger (ms)",
                    "Anzahl unkontrollierter Landungen in 20 Versuchen",
                ],
                erfolgskriterien=[
                    "Mind. 3 min stabile Hover in 8 von 10 Versuchen",
                    "Failure-Response <500ms in allen Versuchen",
                    "0 unkontrollierte Landungen in 20 Versuchen",
                ],
                risiken=["Tether-Reißversagen bei Windböen", "Sensor-Ausfall"],
                dauer_aufwand="2–3 Wochen (Skalierter Prototyp + 20 Versuche)",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + milestone_builder M0",
            ),
            Experiment(
                name="E1 — Portable Energy + Redundant Control Bench (M1)",
                hypothesen=[
                    "Mit aktueller oder nächst-besten Zellchemie ist eine Energie-Dichte erreichbar, die 5+ min bemannten Hover bei >80kg total erlaubt.",
                    "Ein redundantes Steuerungssystem (z.B. dualer ESC + Notfall-Rotor) kann Single-Failure in <100ms kompensieren.",
                ],
                messgroessen=[
                    "Energieverbrauch pro Minute bei 80kg+ Payload",
                    "Zeit bis kritischer Spannungsabfall",
                    "Reaktionszeit bei injiziertem Motor-Ausfall",
                    "Gewicht des Redundanz-Overheads",
                ],
                erfolgskriterien=[
                    "≥5 min Flugzeit bei 80kg+ mit ≥20% Restenergie",
                    "Single-Failure kompensiert in <100ms (gemessen)",
                    "Redundanz-Overhead <15% des Gesamtgewichts",
                ],
                risiken=["Neue Chemie nicht skalierbar in der verfügbaren Zeit", "Gewichtsexplosion durch Redundanz"],
                dauer_aufwand="3–4 Wochen (Bench + Zellen-Vergleich + 50 Failure-Injektionen)",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 (needs_breakthrough + missing_model)",
            ),
            Experiment(
                name="E2 — Tethered Public-Style Demo mit SafetyStagePlan (M2)",
                hypothesen=[
                    "Mit einem bemannten SafetyStagePlan (inkl. tethered + Wasser-Landung + redundanter Abort) kann ein bemannter Demonstrator sicher über einer kleinen Menschenmenge (simuliert) operieren.",
                ],
                messgroessen=[
                    "Abort-Erfolgsrate bei 10 injizierten Fehlern",
                    "Zeit von Failure-Detektion bis sichere Landung",
                    "Publikums-Distanz bei allen Manövern (Sicherheitsabstand eingehalten?)",
                ],
                erfolgskriterien=[
                    "100% sichere Aborts bei 10/10 Fehlern",
                    "Abort <3s von Detektion bis Landung",
                    "Immer >10m Sicherheitsabstand zu simulierten Zuschauern",
                ],
                risiken=["Publikums-Panik trotz SafetyStagePlan", "Wetterbedingte Tether-Probleme"],
                dauer_aufwand="4–6 Wochen (bemannter Dummy + SafetyStagePlan-Review + 10 öffentliche-style Versuche)",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + safety_ladder",
            ),
        ]
        zusammenfassung = (
            "3 konkrete, falsifizierbare Experimente, die die zentralen Annahmen der ersten drei Meilensteine wirklich prüfen. "
            "Jedes Experiment hat klare Hypothesen, Messgrößen, Erfolgskriterien und eine realistische Aufwands-Schätzung."
        )
    else:
        experiments = [
            Experiment(
                name="E0 — Frontier Mapping Validation",
                hypothesen=["Die aktuelle DevelopmentFrontMap + Gap-Analyse deckt die wesentlichen Grenzen und Lücken der Idee ab."],
                messgroessen=["Anzahl identifizierter Grenzen/Gaps", "Abdeckung der in PLAN §3.3 genannten Kategorien"],
                erfolgskriterien=["Mindestens 80% der in der Tabelle genannten Gap-Typen adressiert"],
                risiken=["Unvollständige Wissensbasis"],
                dauer_aufwand="1–2 Wochen (Review + Gap-Completion)",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3",
            ),
        ]
        zusammenfassung = "Minimal-Experiment für noch nicht detailliert analysierte Idee."

    return ExperimentPlan(
        source_traum=traum,
        experiments=experiments,
        zusammenfassung=zusammenfassung,
        run_id=run_id,
        quelle="experiment_designer (erster Stein) + milestone_ladder + GENESIS_PLATFORM_PLAN.md §3.3",
    )
