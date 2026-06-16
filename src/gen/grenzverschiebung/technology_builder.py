"""technology_builder — siebter Grenzverschiebungs-Modul (nächster aktiver Stein nach technology_roadmapper).

Gemäß GENESIS_PLATFORM_PLAN.md §3.3:
- Aufgabe: übersetzt eine fehlende Technologie in einen ersten baubaren Prototyp.
- Output: `TechnologyPrototypeSpec`.

Dieses Modul nimmt eine TechnologyRoadmap (oder die kumulierten Outputs der vorherigen) und
produziert die erste konkrete Prototyp-Spezifikation für eine der priorisierten fehlenden Technologien (mit Anforderungen, Test-Stand-Tie-in, Risiken, grobem Zeitplan).

Erster Stein: Datamodel + deterministischer Builder für das Jetpack-Beispiel
( wählt z.B. den Energie- oder Control-Pfad aus der Roadmap und liefert eine sichere erste Prototyp-Spec).
Später: Volle Verknüpfung mit bench_test_runner, safety_ladder, Wissensbasis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .technology_roadmapper import TechnologyRoadmap


@dataclass(frozen=True)
class TechnologyPrototypeSpec:
    """Ein einzelner erster Prototyp (Output des Moduls)."""

    name: str
    beschreibung: str
    ziel_technologie: str
    anforderungen: list[str]
    test_stand_tie_in: str
    risiken: list[str]
    grober_zeitplan: str
    quelle: str | None = None


@dataclass(frozen=True)
class TechnologyPrototypePlan:
    """Der vollständige Prototyp-Plan (Output des Moduls)."""

    source_traum: str
    prototypes: list[TechnologyPrototypeSpec]
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


def build_technology_prototype(
    roadmap: "TechnologyRoadmap",
    *,
    run_id: str | None = None,
) -> TechnologyPrototypePlan:
    """
    Erste Version des technology_builder.

    Für das Jetpack-Beispiel (PLAN) wählt sie die höchst-priorisierten Gaps aus der Roadmap
    und liefert die erste sichere Prototyp-Spec (z.B. für die Energie-Dichte oder die redundante Control).
    """
    traum = roadmap.source_traum

    prototypes: list[TechnologyPrototypeSpec] = []

    if "jetpack" in traum.lower() or ("mensch" in traum.lower() and "fliegen" in traum.lower()):
        prototypes = [
            TechnologyPrototypeSpec(
                name="P1 — Portable Hochdichte-Energie-Einheit (erste Zelle + Pack)",
                beschreibung="Erster funktionsfähiger Prototyp einer leichten, hochdichten Energieeinheit (z.B. Li-Metal oder Solid-State Stack), der in einem getetherten oder Bench-Setup die 5-minütige Hover-Leistung bei 80kg+ demonstriert.",
                ziel_technologie="Hochdichte portable Energie (Li-Metal / Solid-State)",
                anforderungen=[
                    "Energiedichte ≥ 300 Wh/kg bei Pack-Level",
                    "Zyklenleben ≥ 200 bei 80% DoD",
                    "Sicherheitsverhalten bei Überladung/Kurzschluss (kein Thermal Runaway)",
                    "Gewicht < 8 kg für 80kg+ Payload 5-min Flight",
                ],
                test_stand_tie_in="T1 — Portable Energy + Redundant Control Prüfstand (Bench mit Last-Simulation)",
                risiken=["Neue Chemie zeigt in Realität niedrigere Dichte als Labordaten", "Sicherheitszertifizierung dauert länger"],
                grober_zeitplan="3–4 Monate bis erster Bench-fähiger Pack (inkl. 50 Zyklen + Abuse-Tests)",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + technology_roadmapper Energy Gap + teststand T1",
            ),
            TechnologyPrototypeSpec(
                name="P2 — Dissimilar Redundant Flight Controller + ESC Set",
                beschreibung="Erster Prototyp eines leichten, dissimilar-redundanten Steuerungssatzes (zwei unterschiedliche Flight-Controller + ESC-Paare), der Single-Failure in <100ms kompensiert und in den existierenden Test-Ständen validiert werden kann.",
                ziel_technologie="Leichte redundante Flugkontrolle für bemannte VTOL",
                anforderungen=[
                    "Single-Failure Detection + Switch <80ms",
                    "Gesamtgewicht < 1,2 kg für das volle redundante Set",
                    "Kompatibel mit bestehenden Motoren und Sensoren der vorherigen Stände",
                    "HIL/SIL-Validierung + 100 Failure-Injektionen ohne Absturz",
                ],
                test_stand_tie_in="T1 — Portable Energy + Redundant Control Prüfstand + T0 Scale Hover Rig",
                risiken=["Cross-Talk zwischen dissimilar Kanälen", "Gewichtsziel wird nicht erreicht"],
                grober_zeitplan="2–3 Monate bis erster HIL-fähiger Satz + 100 Injektionen",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + technology_roadmapper Control Gap + teststand T1",
            ),
        ]
        zusammenfassung = (
            "2 erste Prototyp-Specs (Energie + Redundante Control), die die höchst-priorisierten Gaps der Roadmap direkt umsetzen. "
            "Jede Spec ist an einen existierenden sicheren Test-Stand gekoppelt und hat klare Anforderungen + Risiken."
        )
    else:
        prototypes = [
            TechnologyPrototypeSpec(
                name="P0 — Grundlegender Technologie-Validierungs-Prototyp",
                beschreibung="Minimaler Bench-Prototyp zur Validierung der in der Roadmap identifizierten Schlüsseltechnologie.",
                ziel_technologie="Bewertete Schlüsseltechnologie der Idee",
                anforderungen=["Reproduzierbare Messung der kritischen Parameter"],
                test_stand_tie_in="T0 — Frontier Mapping Validation Rig",
                risiken=["Unvollständige Anforderungen"],
                grober_zeitplan="2–4 Wochen",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3",
            ),
        ]
        zusammenfassung = "Minimaler Prototyp für noch nicht detailliert analysierte Idee."

    return TechnologyPrototypePlan(
        source_traum=traum,
        prototypes=prototypes,
        zusammenfassung=zusammenfassung,
        run_id=run_id,
        quelle="technology_builder (erster Stein) + technology_roadmap + GENESIS_PLATFORM_PLAN.md §3.3",
    )
