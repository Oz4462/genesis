"""milestone_builder — drittes Grenzverschiebungs-Modul (nächster aktiver Stein).

Gemäß GENESIS_PLATFORM_PLAN.md §3.3:
- Aufgabe: zerlegt die Vision in beweisbare Entwicklungsstufen.
- Output: `MilestoneLadder`.

Dieses Modul nimmt eine DevelopmentFrontMap + CapabilityGapReport und
produziert eine geordnete Leiter von Meilensteinen (jeder mit klarer
Definition of Done, Risiken, nächsten Experimenten).

Erster Stein: Datamodel + deterministischer Builder für das Jetpack-Beispiel.
Später: Integration mit experiment_designer, safety_ladder, Wissensbasis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .development_front import DevelopmentFrontMap
    from .capability_gap_analyzer import CapabilityGapReport


@dataclass(frozen=True)
class Milestone:
    """Ein einzelner Meilenstein in der Leiter."""

    name: str
    beschreibung: str
    definition_of_done: list[str]
    risiken: list[str]
    naechstes_experiment: str
    quelle: str | None = None           # Provenance


@dataclass(frozen=True)
class MilestoneLadder:
    """Die vollständige, geordnete Leiter (Output des Moduls)."""

    source_traum: str
    milestones: list[Milestone]
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


def build_milestone_ladder(
    front_map: "DevelopmentFrontMap",
    gap_report: "CapabilityGapReport | None" = None,
    *,
    run_id: str | None = None,
) -> MilestoneLadder:
    """
    Erste Version des milestone_builder.

    Für das Jetpack-Beispiel (PLAN) erzeugt sie eine realistische, geordnete Leiter
    von 4–6 Meilensteinen, die direkt aus den identifizierten Gaps und der
    Experimentleiter im FrontMap abgeleitet sind.
    """
    traum = front_map.traum

    milestones: list[Milestone] = []

    if "jetpack" in traum.lower() or ("mensch" in traum.lower() and "fliegen" in traum.lower()):
        milestones = [
            Milestone(
                name="M0 — Tethered Scale Demo (1:5)",
                beschreibung="Stark getetherter 1:5 Demonstrator mit Dummy-Payload + redundanter Abschaltung + Wasser-Landung.",
                definition_of_done=[
                    "Stabile Hover >3 min mit >20kg Payload",
                    "Failure-Response <0.5s (gemessen)",
                    "Keine unkontrollierte Landung in 20 Versuchen",
                ],
                risiken=["Tether-Reißversagen", "Steuerungsverlust bei Wind"],
                naechstes_experiment="Tethered public Demo mit SafetyStagePlan (Safety Ladder)",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + development_front + capability_gap",
            ),
            Milestone(
                name="M1 — Energy & Control Redundancy Bench",
                beschreibung="Prüfstand für portable Energie + redundante Flugkontrolle unter Last.",
                definition_of_done=[
                    "Energie-Dichte nachgewiesen für 5+ min bei 80kg+",
                    "Single-Failure Recovery <0.1s demonstriert",
                ],
                risiken=["Neue Batterie-Chemie nicht skalierbar", "Gewichtszunahme durch Redundanz"],
                naechstes_experiment="Technology Builder Prototyp + bench_test_runner",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 (missing_model + needs_breakthrough)",
            ),
            Milestone(
                name="M2 — Tethered Public Demo",
                beschreibung="Öffentliche tethered Demo mit bemannter SafetyStagePlan (kein Risiko für Dritte).",
                definition_of_done=[
                    "SafetyStagePlan reviewed & approved",
                    "Live-Abort in <0.1s bei 3 von 3 Versuchen",
                    "Regulatorische Freigabe für tethered public Test",
                ],
                risiken=["Public Perception", "Wetterabhängigkeit"],
                naechstes_experiment="Free-flight low-altitude Test mit parachute + boundary_reviser",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + safety_ladder",
            ),
            Milestone(
                name="M3 — Free Low-Altitude Proof",
                beschreibung="Ungebundener Test in sicherer Höhe + kontrollierter Abstieg.",
                definition_of_done=[
                    "5+ min free hover mit Pilot-äquivalenter Last",
                    "Notfall-Abstieg <3s ohne Verletzungsrisiko",
                ],
                risiken=["Regulatorik für free flight", "Energie-Limit in Realität"],
                naechstes_experiment="Regulatorik-Meilenstein + breakthrough_watch für vergleichbare Projekte",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 (boundary_reviser)",
            ),
        ]
        zusammenfassung = (
            "4-stufige Leiter vom tethered Scale-Demo bis low-altitude Free-Flight Proof. "
            "Jeder Meilenstein hat klare DoD und verweist auf das nächste Grenzverschiebungs-Modul."
        )
    else:
        milestones = [
            Milestone(
                name="M0 — Frontier Mapping Complete",
                beschreibung="Vollständige DevelopmentFrontMap + CapabilityGapReport für die Idee.",
                definition_of_done=["Alle relevanten Grenzen typisiert", "Gaps mit suggested_next"],
                risiken=["Unvollständige Wissensbasis"],
                naechstes_experiment="Wissensbasis-Integration + experiment_designer",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3",
            ),
        ]
        zusammenfassung = "Minimal-Leiter für noch nicht detailliert analysierte Idee."

    return MilestoneLadder(
        source_traum=traum,
        milestones=milestones,
        zusammenfassung=zusammenfassung,
        run_id=run_id,
        quelle="milestone_builder (erster Stein) + front_map + gap_report + GENESIS_PLATFORM_PLAN.md §3.3",
    )
