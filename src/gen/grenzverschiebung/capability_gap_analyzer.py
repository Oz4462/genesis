"""capability_gap_analyzer — zweites Grenzverschiebungs-Modul.

Gemäß GENESIS_PLATFORM_PLAN.md §3.3:
- Aufgabe: trennt fehlendes Wissen, fehlende Technologie, fehlende Messung,
  fehlendes Geld/Tooling.
- Output: `CapabilityGap`.

Dieses Modul nimmt eine DevelopmentFrontMap (oder rohe Idee + Kontext) und
klassifiziert die Lücken präzise in die 7+ Gap-Kategorien. Kein Optimismus.
Jede Lücke wird typisiert und mit minimaler Provenance versehen (L1).

Später: Tiefe Integration mit Wissensbasis + frontier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from .development_front import is_jetpack_traum

if TYPE_CHECKING:
    from .development_front import DevelopmentFrontMap

# --- Gap-Typen (abgeleitet aus PLAN §3.3 Grenztypen + expliziter Aufgabe) ---

class GapCategory(str, Enum):
    MISSING_KNOWLEDGE = "missing_knowledge"          # fehlendes Wissen / Verständnis
    MISSING_TECHNOLOGY = "missing_technology"        # fehlende Technologie / Erfindung
    MISSING_MEASUREMENT = "missing_measurement"      # es fehlt eine reale Messung / Validierung
    MISSING_FUNDING = "missing_funding"              # fehlendes Geld / Ressourcen
    MISSING_TOOLING = "missing_tooling"              # fehlt Fertigung, Prüfstand, Messgerät, Regulatorik-Tool etc.
    MISSING_MODEL = "missing_model"                  # es fehlt ein tragfähiges Modell / Simulation
    MISSING_COMPONENT = "missing_component"          # fehlt ein Bauteil, Material oder Prozess
    NEEDS_BREAKTHROUGH = "needs_breakthrough"        # braucht neue Technologie oder starke Verbesserung
    CONTRADICTS_CURRENT_MODEL = "contradicts_current_model"  # widerspricht heutigem Stand des Wissens


@dataclass(frozen=True)
class CapabilityGap:
    """Ein präzise klassifizierter Gap (Output des Analyzers)."""

    category: GapCategory
    description: str
    affected_boundary: str | None = None      # z.B. "bemannter freier Flug über Menschenmenge"
    severity: str = "high"                    # low | medium | high | blocker (für spätere Priorisierung)
    evidence: list[str] = field(default_factory=list)   # Quellen / warum wir das wissen (L1)
    suggested_next: str | None = None         # z.B. "technology_roadmapper" oder "experiment_designer für tethered test"


@dataclass(frozen=True)
class CapabilityGapReport:
    """Gesamtergebnis des Analyzers."""

    source_traum: str
    gaps: list[CapabilityGap]
    summary: str
    run_id: str | None = None
    quelle: str | None = None                 # "capability_gap_analyzer + development_front_map + PLAN §3.3"


def analyze_capability_gaps(
    front_map: "DevelopmentFrontMap | None" = None,
    *,
    idee: str | None = None,
    run_id: str | None = None,
) -> CapabilityGapReport:
    """
    Erste funktionale Version des capability_gap_analyzer.

    Nimmt entweder eine bereits erzeugte DevelopmentFrontMap oder eine rohe Idee
    und produziert eine saubere Liste von CapabilityGap.

    Aktuell regelbasiert + deterministisch für das Jetpack-Beispiel (PLAN).
    Später: Ersetzbar durch Wissensbasis-Query + echte frontier-Daten.

    Hinweis (ehrlich, Review F4): aus ``front_map`` wird derzeit nur ``.traum``
    konsumiert; grenzen/experimentleiter sind reservierte API und werden noch
    nicht ausgewertet (Lücke — keine Schein-Auswertung).
    """
    if front_map is not None:
        traum = front_map.traum
        source = "development_front_map"
    elif idee:
        traum = idee.strip()
        source = "raw_idee"
        # Minimal-Map für Fallback (wird später durch echten Mapper ersetzt)
        front_map = None
    else:
        raise ValueError("Entweder front_map oder idee muss übergeben werden.")

    gaps: list[CapabilityGap] = []

    # Kanonische Analyse für bemannten Jetpack / freien Flug (PLAN §3.2/3.3)
    if is_jetpack_traum(traum):  # Wortgrenzen-Trigger (Review F5)
        gaps.append(
            CapabilityGap(
                category=GapCategory.MISSING_TECHNOLOGY,
                description="Keine portable Energie-Dichte für sustained hover mit >80kg Payload + Pilot bei vernünftiger Flugdauer.",
                affected_boundary="portable Energie für 5+ min bemannten Hover >80kg",
                severity="blocker",
                evidence=["GENESIS_PLATFORM_PLAN.md §3.3 (Grenztyp-Tabelle + Jetpack-Beispiel)"],
                suggested_next="technology_roadmapper + technology_builder für neue Batterie- oder Brennstoffzellen-Technologie",
            )
        )
        gaps.append(
            CapabilityGap(
                category=GapCategory.MISSING_MODEL,
                description="Kein valides Manned-Safety + Single-Failure-Recovery-Modell für public overflight.",
                affected_boundary="validierte Manned Single-Failure Recovery <0.1s",
                severity="high",
                evidence=["GENESIS_PLATFORM_PLAN.md §3.3", "bestehende δ+ Physik-Modelle nur für unbemannte Systeme"],
                suggested_next="safety_ladder + experiment_designer für tethered + wasserbasierte Falsifikations-Experimente",
            )
        )
        gaps.append(
            CapabilityGap(
                category=GapCategory.MISSING_TOOLING,
                description="Kein Regulatorik- und Human-Acceptance-Pfad für bemannten experimentellen VTOL in populated areas.",
                affected_boundary="regulatorischer Pfad für bemannten personal flight in populated area",
                severity="high",
                evidence=["GENESIS_PLATFORM_PLAN.md §3.3 (missing_tooling)"],
                suggested_next="milestone_builder mit regulatorischen Meilensteinen + breakthrough_watch für vergleichbare Genehmigungen",
            )
        )
        gaps.append(
            CapabilityGap(
                category=GapCategory.MISSING_MEASUREMENT,
                description="Keine realen Messdaten für bemannte tethered oder wasserbasierte Demonstratoren mit relevanter Payload.",
                affected_boundary="bemannter freier Flug über Menschenmenge ohne Failure-Risiko",
                severity="medium",
                evidence=["Aktueller Projekt-Stand: nur unbemannte δ+ Validierungen vorhanden"],
                suggested_next="bench_test_runner für 1:5 Scale tethered Demo",
            )
        )
    else:
        # Ehrlicher Fallback
        gaps.append(
            CapabilityGap(
                category=GapCategory.MISSING_KNOWLEDGE,
                description="Vollständige Grenz-Kartierung und Gap-Analyse für diese Idee noch nicht durchgeführt.",
                affected_boundary="generische Machbarkeit der Idee",
                severity="medium",
                evidence=["GENESIS_PLATFORM_PLAN.md §3.3 (Grenzverschiebungs-Module allgemein)"],
                suggested_next="development_front_mapper + full Wissensbasis-Integration",
            )
        )

    summary = (
        f"{len(gaps)} Capability Gaps identifiziert für Traum: {traum[:80]}... "
        "Alle Gaps sind explizit typisiert und mit nächster Aktion versehen (kein Optimismus)."
    )

    return CapabilityGapReport(
        source_traum=traum,
        gaps=gaps,
        summary=summary,
        run_id=run_id,
        quelle=f"capability_gap_analyzer (erster Stein) + {source} (nur traum konsumiert; übrige Map-Felder noch nicht ausgewertet — Lücke) + GENESIS_PLATFORM_PLAN.md §3.3",
    )
