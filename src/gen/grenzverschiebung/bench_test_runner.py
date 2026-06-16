"""bench_test_runner — achter Grenzverschiebungs-Modul (nächster aktiver Stein nach technology_builder).

Gemäß GENESIS_PLATFORM_PLAN.md §3.3:
- Aufgabe: plant und bewertet den Messlauf für diesen Prototyp.
- Output: `BenchTestResult`.

Dieses Modul nimmt die TechnologyPrototypePlan (oder die kumulierten Outputs) und
produziert die konkreten Messpläne und Ergebnis-Bewertungen für die Prototypen (mit definierten Testläufen, Messdaten-Anforderungen, Erfolgskriterien, Abbruchregeln und ehrlicher Bewertung).

Erster Stein: Datamodel + deterministischer Runner für das Jetpack-Beispiel
( plant die Messläufe für die Prototypen aus dem Builder, mit sicheren Bedingungen und Abbruchkriterien).
Später: Volle Verknüpfung mit breakthrough_watch, boundary_reviser, Wissensbasis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .technology_builder import TechnologyPrototypePlan


@dataclass(frozen=True)
class BenchTestResult:
    """Ein einzelnes Messergebnis für einen Prototyp (Output des Moduls)."""

    prototype_name: str
    test_name: str
    beschreibung: str
    messdaten_anforderungen: list[str]
    erfolgskriterien: list[str]
    abbruchkriterien: list[str]
    geplante_dauer: str
    ergebnis_bewertung: str | None = None   # Wird nach dem Lauf gesetzt (z.B. "bestanden", "teilweise", "abgebrochen", "nicht erreicht")
    quelle: str | None = None


@dataclass(frozen=True)
class BenchTestPlan:
    """Der vollständige Messplan und Ergebnis-Bewertung (Output des Moduls)."""

    source_traum: str
    results: list[BenchTestResult]
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


def run_bench_test(
    prototype_plan: "TechnologyPrototypePlan",
    *,
    run_id: str | None = None,
) -> BenchTestPlan:
    """
    Erste Version des bench_test_runner.

    Für das Jetpack-Beispiel (PLAN) plant sie die konkreten Messläufe für die Prototypen aus dem Builder
    und liefert die Struktur für die Bewertung (die tatsächliche Ausführung und Datenerfassung kommt später mit realen Ständen).
    """
    traum = prototype_plan.source_traum

    results: list[BenchTestResult] = []

    if "jetpack" in traum.lower() or ("mensch" in traum.lower() and "fliegen" in traum.lower()):
        results = [
            BenchTestResult(
                prototype_name="P1 — Portable High-Density Energy Module (erste Zelle + Pack)",
                test_name="Energie-Dichte & Zyklen unter Last (T1 Bench)",
                beschreibung="Messlauf auf dem T1 Bench mit simulierter 80kg+ Payload, 50 Zyklen bei 80% DoD, Abuse-Tests (Überladung, Kurzschluss, Temperatur).",
                messdaten_anforderungen=[
                    "Wh/kg bei Pack-Level (Ziel ≥300)",
                    "Zyklenleben bei 80% DoD (Ziel ≥200)",
                    "Temperaturprofil bei Dauerlast",
                    "Spannungsverlauf bei Abuse",
                ],
                erfolgskriterien=[
                    "Durchschnittliche Energiedichte ≥280 Wh/kg über 50 Zyklen",
                    "Keine Thermal Runaway in Abuse-Tests",
                    "Kapazitätsverlust <20% nach 200 Zyklen",
                ],
                abbruchkriterien=[
                    "Temperatur >60°C bei Dauerlast",
                    "Kapazitätsverlust >5% in einem Zyklus",
                    "Spannungsabfall >10% unter Last",
                ],
                geplante_dauer="4–6 Wochen (Bench-Aufbau + 50 Zyklen + Abuse + Auswertung)",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + technology_builder P1 + teststand T1",
            ),
            BenchTestResult(
                prototype_name="P2 — Dissimilar Redundant Flight Controller + ESC Set",
                test_name="Single-Failure Detection & Switch (T1 + T0)",
                beschreibung="HIL/SIL auf T1 Bench + Integration auf T0 Scale Rig, 100 injizierte Single-Failures (Motor, ESC, Sensor, FC), Messung der Reaktionszeit und Kompensation.",
                messdaten_anforderungen=[
                    "Zeit von Failure-Detektion bis Switch (Ziel <80ms)",
                    "Anzahl erfolgreicher Kompensationen in 100 Injektionen",
                    "Stabilität nach Switch (Höhenabweichung)",
                    "Gewicht des vollen Satzes",
                ],
                erfolgskriterien=[
                    "Durchschnittliche Switch-Zeit <80ms",
                    "≥98/100 Injektionen erfolgreich kompensiert ohne Absturz",
                    "Gesamtgewicht ≤1,2 kg",
                ],
                abbruchkriterien=[
                    "Switch-Zeit >150ms in >5% der Fälle",
                    "Unkompensierter Absturz in >3 Injektionen",
                    "Gewicht >1,5 kg",
                ],
                geplante_dauer="3–4 Wochen (HIL-Setup + 100 Injektionen + T0 Integration + Auswertung)",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + technology_builder P2 + teststand T1/T0",
            ),
        ]
        zusammenfassung = (
            "2 konkrete BenchTestResults (Messpläne + Erfolgskriterien + Abbruchregeln) für die ersten Prototypen. "
            "Die Pläne sind direkt an die existierenden sicheren Test-Stände gekoppelt und haben klare, messbare Kriterien."
        )
    else:
        results = [
            BenchTestResult(
                prototype_name="P0 — Grundlegender Technologie-Validierungs-Prototyp",
                test_name="Parameter-Validierung (T0)",
                beschreibung="Minimaler Bench-Lauf zur Messung der kritischen Parameter des P0-Prototyps.",
                messdaten_anforderungen=["Reproduzierbare Messung der kritischen Parameter"],
                erfolgskriterien=["Messung innerhalb der erwarteten Toleranz"],
                abbruchkriterien=["Messung nicht reproduzierbar"],
                geplante_dauer="1–2 Wochen",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3",
            ),
        ]
        zusammenfassung = "Minimaler Messplan für noch nicht detailliert analysierte Idee."

    return BenchTestPlan(
        source_traum=traum,
        results=results,
        zusammenfassung=zusammenfassung,
        run_id=run_id,
        quelle="bench_test_runner (erster Stein) + technology_prototype_plan + GENESIS_PLATFORM_PLAN.md §3.3",
    )
