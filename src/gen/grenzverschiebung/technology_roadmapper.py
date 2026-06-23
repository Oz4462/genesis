"""technology_roadmapper — sechster Grenzverschiebungs-Modul (nächster aktiver Stein nach teststand_architect).

Gemäß GENESIS_PLATFORM_PLAN.md §3.3:
- Aufgabe: beschreibt fehlende Technologien und mögliche Entwicklungspfade.
- Output: `TechnologyRoadmap`.

Dieses Modul nimmt die kumulierten Outputs der vorherigen Module (FrontMap, Gaps, Ladder, ExperimentPlan, TestStandPlan) und
produziert eine klare Roadmap der fehlenden Technologien (mit Gap-Referenz, möglichen Pfaden, grober Aufwands-Schätzung, Abhängigkeiten).

Erster Stein: Datamodel + deterministischer Builder für das Jetpack-Beispiel
( leitet die fehlenden Techs direkt aus den identifizierten Gaps und Meilensteinen ab).
Später: Volle Verknüpfung mit technology_builder, breakthrough_watch, Wissensbasis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .teststand_architect import TestStandPlan


@dataclass(frozen=True)
class TechnologyGap:
    """Ein einzelnes fehlendes Technologie-Element in der Roadmap."""

    name: str
    beschreibung: str
    gap_referenz: str                  # z.B. "Energie-Dichte aus capability_gap M1"
    moegliche_pfade: list[str]
    geschaetzter_aufwand: str
    abhaengigkeiten: list[str]
    quelle: str | None = None


@dataclass(frozen=True)
class TechnologyRoadmap:
    """Die vollständige Technologie-Roadmap (Output des Moduls)."""

    source_traum: str
    gaps: list[TechnologyGap]
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


def build_technology_roadmap(
    stand_plan: "TestStandPlan",
    *,
    run_id: str | None = None,
) -> TechnologyRoadmap:
    """
    Erste Version des technology_roadmapper.

    Für das Jetpack-Beispiel (PLAN) erzeugt sie eine Roadmap der zentralen fehlenden
    Technologien, die aus den vorherigen Gaps, Meilensteinen und Prüfständen abgeleitet sind.

    Für beliebige (non-jetpack) Eingaben leitet der generische Pfad die Gaps direkt aus
    den TestStandSpec-Einträgen ab: pro Stand ein TechnologyGap, gap_referenz = stand.name,
    beschreibung und abhaengigkeiten spiegeln die messungen/sicherheitsmassnahmen des Standes.
    Bei leerer stands-Liste wird eine ehrliche leere gaps-Liste mit expliziter
    Zusammenfassung "no stands were provided" (keine fabrizierte Lücke) zurückgegeben.
    Der reiche Jetpack-Zweig wird verbatim als Regression erhalten.
    """
    traum = stand_plan.source_traum

    gaps: list[TechnologyGap] = []

    if "jetpack" in traum.lower() or ("mensch" in traum.lower() and "fliegen" in traum.lower()):
        # Jetpack branch preserved VERBATIM per spec / team decisions (protected regression).
        gaps = [
            TechnologyGap(
                name="Hochdichte portable Energie (Li-Metal / Solid-State / Wasserstoff)",
                beschreibung="Aktuelle Li-Ion/LiPo reichen nicht für 5+ min bemannten Hover bei >80kg mit akzeptablem Gewicht. Neue Zellchemie oder alternative Speicher nötig.",
                gap_referenz="capability_gap MISSING_TECHNOLOGY + milestone M1 + teststand T1",
                moegliche_pfade=[
                    "Li-Metal / Solid-State Batterien (hohe Energiedichte, aber Zyklenleben & Sicherheit noch kritisch)",
                    "Wasserstoff-Brennstoffzelle + leichter Tank (hohe Energiedichte, aber Infrastruktur & Sicherheit)",
                    "Hybrid: Hochleistungs-Superkaps + optimierte Li-Ion für kurze Spitzen",
                ],
                geschaetzter_aufwand="12–24 Monate bis brauchbarer Prototyp (je nach Pfad)",
                abhaengigkeiten=["technology_builder", "bench_test_runner", "safety_ladder"],
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 (needs_breakthrough) + vorherige Module",
            ),
            TechnologyGap(
                name="Leichte, zuverlässige Redundante Flugkontrolle für bemannte VTOL",
                beschreibung="Single-Failure-tolerant Steuerung (Motor, ESC, Sensor, Flight-Controller) bei minimalem Gewicht und hoher Reaktionsgeschwindigkeit (<100ms).",
                gap_referenz="milestone M1 + experiment E1 + teststand T1",
                moegliche_pfade=[
                    "Dual/Triple modular redundant Flight-Controller + dissimilar hardware",
                    "Distributed electric propulsion mit per-motor autonomy + central supervisor",
                    "Mechanik-inspiriertes Fail-Safe (z.B. autorotierende Rotoren + Notfall-Parachute-Integration)",
                ],
                geschaetzter_aufwand="9–18 Monate (inkl. HIL/SIL-Validierung)",
                abhaengigkeiten=["technology_builder", "teststand_architect", "safety_ladder"],
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + vorherige Module",
            ),
            TechnologyGap(
                name="Schnelle, leichte, zuverlässige bemannte Notfall-Recovery-Systeme",
                beschreibung="Systeme, die bei Total-Failure eine sichere Landung/Abstieg in <3s garantieren (Parachute, Rocket-Abort, Ducted-Fan, etc.) bei akzeptablem Gewicht.",
                gap_referenz="milestone M2/M3 + experiment E2 + teststand T0/T2",
                moegliche_pfade=[
                    "Ballistic Parachute + Rocket-Assist (bewährte Technik, aber Gewicht & Auslösezeit)",
                    "Leichte Ducted-Fan / Coaxial Notfall-Rotoren mit eigenem Akku",
                    "Morphing / Autorotierende Strukturen (zukunftsweisend, noch unreif)",
                ],
                geschaetzter_aufwand="6–15 Monate (je nach Pfad, inkl. Drop-Tests)",
                abhaengigkeiten=["bench_test_runner", "safety_ladder", "experiment_designer"],
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + vorherige Module",
            ),
        ]
        zusammenfassung = (
            "3 zentrale Technologie-Gaps für bemannten Jetpack, jeweils mit mehreren realistischen Entwicklungspfaden, "
            "Aufwands-Schätzung und Abhängigkeiten zu den nachfolgenden Modulen (technology_builder, safety_ladder etc.). "
            "Die Roadmap ist direkt aus den identifizierten Gaps und Meilensteinen abgeleitet."
        )
    else:
        # Generic (non-jetpack) path: derive TechnologyGaps from the ACTUAL stands.
        # This kills the facade (previously a single fixed gap regardless of stand_plan.stands).
        # One gap per stand; gap_referenz points at stand.name; beschreibung/abhaengigkeiten
        # reflect that stand's measurements and safety measures (L2 drift fix + L1 grounding).
        # Empty stands -> honest empty list + explicit summary (no fabricated canned gap).
        if not stand_plan.stands:
            gaps = []
            zusammenfassung = (
                "Keine Prüfstände wurden bereitgestellt. "
                "Es können keine Technologie-Gaps abgeleitet werden. "
                "(keine fabrizierte Lücke)"
            )
        else:
            for s in stand_plan.stands:
                # WHY (non-obvious correctness): we deliberately 1:1 map stands -> gaps
                # so that any change to a stand's name/messungen/sicherheitsmassnahmen
                # produces an observably different roadmap (facade detector requirement).
                # Abhaengigkeiten pull from the safety list (reflects input) with safe fallback.
                ref = s.name
                beschreibung = (
                    f"Prüfstand '{s.name}' erfordert Technologie-Fortschritt für Messungen "
                    f"{s.messungen} unter Sicherheitsmassnahmen {s.sicherheitsmassnahmen}. "
                    f"Stand-Beschreibung: {s.beschreibung}"
                )
                abhaengigkeiten = (
                    list(s.sicherheitsmassnahmen)[:3] if s.sicherheitsmassnahmen else ["safety_ladder", "bench_test_runner"]
                )
                gaps.append(
                    TechnologyGap(
                        name=f"Technologie-Lücke für {s.name}",
                        beschreibung=beschreibung,
                        gap_referenz=ref,
                        moegliche_pfade=[
                            "Entwicklung passend zu den Stand-Messungen und Sicherheitsanforderungen",
                            "Kopplung an technology_builder + bench_test_runner",
                        ],
                        geschaetzter_aufwand=s.dauer_aufwand,
                        abhaengigkeiten=abhaengigkeiten,
                        quelle=s.quelle or "technology_roadmapper (generic) + TestStandSpec",
                    )
                )
            zusammenfassung = (
                f"{len(gaps)} Technologie-Gaps direkt aus den {len(stand_plan.stands)} "
                "realen Prüfstand-Einträgen abgeleitet (gap_referenz = Stand-Name; "
                "Beschreibung/Abhängigkeiten spiegeln Messungen + Sicherheit)."
            )

    return TechnologyRoadmap(
        source_traum=traum,
        gaps=gaps,
        zusammenfassung=zusammenfassung,
        run_id=run_id,
        quelle="technology_roadmapper (erster Stein) + teststand_plan + GENESIS_PLATFORM_PLAN.md §3.3",
    )
