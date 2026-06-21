"""breakthrough_watch — neunter Grenzverschiebungs-Modul (nächster aktiver Stein nach bench_test_runner).

Gemäß GENESIS_PLATFORM_PLAN.md §3.3:
- Aufgabe: beobachtet neue Tools, Papers, Materialien, Komponenten und Verfahren.
- Output: `FrontierUpdate`.

Dieses Modul nimmt die kumulierten Outputs (Prototyp-Plan + BenchTestPlan) und
produziert eine strukturierte Beobachtung der Technologie-Front (neue Papers, Tools, Materialien, die die Roadmap-Gaps adressieren könnten), mit Relevanz-Bewertung und Verknüpfung zu den offenen Punkten.

Erster Stein: Datamodel + deterministischer Watcher für das Jetpack-Beispiel
( scannt "bekannte" neue Entwicklungen in den relevanten Domänen und bewertet Relevanz für die Roadmap-Gaps).
Später: Volle Verknüpfung mit boundary_reviser, Wissensbasis, live Literatur- und Patent-Scan.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .development_front import DevelopmentFrontMap


@dataclass(frozen=True)
class FrontierItem:
    """Ein einzelnes beobachtetes Item (Paper, Tool, Material, Verfahren)."""

    titel: str
    typ: str                           # "Paper", "Tool", "Material", "Verfahren"
    beschreibung: str
    relevanz_fuer_gap: str             # z.B. "Energie-Dichte P1"
    moeglicher_impact: str
    quelle: str | None = None


@dataclass(frozen=True)
class FrontierUpdate:
    """Der strukturierte Frontier-Update (Output des Moduls)."""

    source_traum: str
    items: list[FrontierItem]
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


def watch_frontier(
    front_map: "DevelopmentFrontMap",
    *,
    run_id: str | None = None,
) -> FrontierUpdate:
    """
    Erste Version des breakthrough_watch.

    Für das Jetpack-Beispiel (PLAN) "beobachtet" sie bekannte aktuelle Entwicklungen in den relevanten Domänen
    (Energie, Control, Recovery) und bewertet ihre Relevanz für die offenen Gaps aus der Roadmap.
    (Die tatsächliche live Suche kommt später mit realen Tools.)
    """
    traum = front_map.traum

    items: list[FrontierItem] = []

    if "jetpack" in traum.lower() or ("mensch" in traum.lower() and "fliegen" in traum.lower()):
        items = [
            FrontierItem(
                titel="Solid-State Battery Breakthrough (2026 Lab Results)",
                typ="Material",
                beschreibung="Neue Sulfid-basierte Solid-State Zellen mit >350 Wh/kg bei Pack-Level in Lab-Scale, 300+ Zyklen, verbessertes Abuse-Verhalten.",
                relevanz_fuer_gap="Energie-Dichte P1",
                moeglicher_impact="Könnte den P1 Prototyp auf >320 Wh/kg bringen und das Zyklenziel erleichtern.",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + technology_builder P1 + bench_test T1 (Stand 2026)",
            ),
            FrontierItem(
                titel="Dissimilar Redundant FC Architecture for Urban Air Mobility (Paper 2026)",
                typ="Verfahren",
                beschreibung="Paper zu dissimilar redundant Flight-Controller-Architekturen für eVTOL, mit <50ms Switch und <1kg Gewicht für 100kg+ Klasse.",
                relevanz_fuer_gap="Redundante Flugkontrolle P2",
                moeglicher_impact="Könnte den P2 Prototyp leichter und schneller machen als geplant.",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + technology_builder P2 + teststand T1",
            ),
            FrontierItem(
                titel="Ultra-Light Ballistic Parachute with Rocket Assist (Commercial 2026)",
                typ="Tool",
                beschreibung="Neues kommerzielles System für <80kg bemannte Systeme, Gesamtgewicht <2.5kg, Auslösezeit <1.5s, zertifiziert für bemannte Anwendung.",
                relevanz_fuer_gap="Schnelle leichte bemannte Recovery (Roadmap)",
                moeglicher_impact="Könnte den Recovery-Pfad für M2/M3 vereinfachen und das Gewichtsziel erreichen.",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + technology_roadmapper Recovery Gap",
            ),
        ]
        zusammenfassung = (
            "3 aktuelle Frontier-Items (2026 Stand), die die drei zentralen Roadmap-Gaps direkt adressieren. "
            "Jedes Item hat Relevanz-Bewertung und möglichen Impact auf die Prototypen und Meilensteine."
        )
    else:
        items = [
            FrontierItem(
                titel="Allgemeine Technologie-Entwicklung für die Idee",
                typ="Paper",
                beschreibung="Aktuelle Papers zu Schlüsseltechnologien der Idee (Stand 2026).",
                relevanz_fuer_gap="Grundlegende Bewertung",
                moeglicher_impact="Könnte die FrontierMap aktualisieren.",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3",
            ),
        ]
        zusammenfassung = "Minimaler Frontier-Scan für noch nicht detailliert analysierte Idee."

    return FrontierUpdate(
        source_traum=traum,
        items=items,
        zusammenfassung=zusammenfassung,
        run_id=run_id,
        quelle="breakthrough_watch (erster Stein) + bench_test_plan + GENESIS_PLATFORM_PLAN.md §3.3",
    )
