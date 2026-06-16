"""physiker — dritter Stein der Fach-Pipelines (Physiker-Pipeline).

Gemäß GENESIS_PLATFORM_PLAN.md §4.3:
- Ziel: Die echte Physik hinter der Idee sauber modellieren.
- Aufgaben: relevante physikalische Domänen identifizieren, Modelle auswählen, Modellgrenzen beschreiben, Formeln prüfen, Dimensionsanalyse, Energie-/Kraft-/Wärme-/Schwingungsbilanzen, Unsicherheiten propagieren, Falsifikationsexperimente vorschlagen.
- Outputs: Modellkarte, Gleichungen, Grenzfälle, erwartete Messgrößen, Unsicherheitsbudget, Falsifikationsplan.
- Gate: Dimensionshomogenität, Grenzfallprüfung, keine Modellanwendung außerhalb ihres Gültigkeitsbereichs, Messbarkeit der zentralen Vorhersagen.

Erster Stein: deterministischer Mapper von SystemConcept + IngenieurSpec zu PhysikerSpec.
Jetpack-Beispiel baut direkt auf den vorherigen Stones auf (Energie aus Ingenieur, Recovery/Thrust aus Grenz/CAD, Tether-Lasten etc.).

Naht: Nimmt vorherige Outputs, erzeugt Physik-Modell + Unsicherheitsbudget + Falsifikationsplan, die in CAD-Anforderungen, Manufacturing-Checks und spätere Teststände fließen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .architekt import SystemConcept
from .ingenieur import IngenieurSpec


@dataclass(frozen=True)
class PhysikDomäne:
    """Eine relevante physikalische Domäne mit Beleg."""
    name: str
    beschreibung: str
    quelle: str | None = None


@dataclass(frozen=True)
class ModellGleichung:
    """Eine Formel mit Gültigkeitsbereich und Herkunft."""
    name: str
    formel: str
    einheiten: str
    gueltigkeitsbereich: str
    quelle: str | None = None


@dataclass(frozen=True)
class UnsicherheitsBudget:
    """Unsicherheitsbetrachtung (einfach aber ehrlich)."""
    quelle: str
    wert: str  # z.B. "±15% auf Schub"
    auswirkung: str
    quelle_ref: str | None = None


@dataclass(frozen=True)
class FalsifikationsPlan:
    """Vorschlag für Experimente, die das Modell widerlegen könnten."""
    name: str
    beschreibung: str
    erwartete_messgroesse: str
    abbruchkriterium: str
    quelle: str | None = None


@dataclass(frozen=True)
class PhysikerSpec:
    """Der Output der Physiker-Pipeline (erster Stein)."""
    source_idea: str
    relevante_domaenen: list[PhysikDomäne]
    modell_gleichungen: list[ModellGleichung]
    unsicherheits_budget: list[UnsicherheitsBudget]
    falsifikations_plan: list[FalsifikationsPlan]
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


def map_to_physiker_spec(
    concept: SystemConcept,
    ingenieur: IngenieurSpec,
    *,
    run_id: str | None = None,
) -> PhysikerSpec:
    """
    Erster Stein der Physiker-Pipeline.
    Für das Jetpack-Beispiel: Energie, Kräfte, Aerodynamik, Schwingungen, Wärme (aus vorherigen Stones).
    """
    if "jetpack" in concept.source_idea.lower() or any("jetpack" in a.name.lower() for a in concept.main_assemblies):
        domaenen = [
            PhysikDomäne("Energie & Leistung", "Batterie/Propulsion Bilanz für 5+ min Flight", "breakthrough + ingenieur lastfaelle"),
            PhysikDomäne("Kräfte & Dynamik", "Tether-Zug, Schub, Recovery-Impact, Aerodynamik", "ingenieur + gren safety"),
            PhysikDomäne("Schwingungen & Stabilität", "Vibrationen, Control-Response, Tether-Mode", "prior gren + breakthrough FC"),
            PhysikDomäne("Wärme & Thermik", "Motor/Batterie Wärme bei Last, Dissipation", "ingenieur material + energy"),
        ]
        gleichungen = [
            ModellGleichung(
                "Energie-Bilanz",
                "E_in - E_out - Verluste = E_verbleibend",
                "Wh",
                "5-10 min Flight, 20-80% SOC",
                "breakthrough Solid-State + ingenieur",
            ),
            ModellGleichung(
                "Tether-Dynamik (vereinfacht)",
                "F_tether = m * a + Drag + Gravity_comp",
                "N",
                "Low altitude, <50 km/h Wind",
                "safety_ladder + CAD anchor",
            ),
            ModellGleichung(
                "Recovery-Entfaltung",
                "t_open < 3s bei v_fall < v_max",
                "s, m/s",
                "Single-Failure Case",
                "learning_integrator + gren",
            ),
        ]
        budget = [
            UnsicherheitsBudget("Schub", "±12%", "Reichweite/Energie stark betroffen", "breakthrough lab data 2026"),
            UnsicherheitsBudget("Tether-Last", "±20% (Dynamik)", "Struktur/Recovery Dimensionierung", "ingenieur + real tether tests"),
            UnsicherheitsBudget("Recovery-Zeit", "±0.8s", "Sicherheitsabstand", "gren simulation + prior"),
        ]
        falsi = [
            FalsifikationsPlan(
                "Tether-Überlast Test",
                "Statische + dynamische Last bis Bruch oder 1.5x Max",
                "F_max, Dehnung",
                "Bruch vor 1.5x oder Dehnung > Grenze",
                "ingenieur toleranzen + CAD",
            ),
            FalsifikationsPlan(
                "Single-Failure Recovery Drop",
                "Simulierter Ausfall bei 30m Höhe, Recovery auslösen",
                "t_open, v_impact",
                "t_open > 3s oder v_impact > sicher",
                "safety_ladder S2 + learning",
            ),
            FalsifikationsPlan(
                "Energie-Margin Flight",
                "Vollast Flight bis SOC 20%, Verbrauch messen",
                "Wh/km oder Wh/min, SOC",
                "Verbrauch > 120% Modell oder SOC < 15% vor 5 min",
                "breakthrough + ingenieur",
            ),
        ]
        zusammen = (
            "PhysikerSpec für Jetpack: 4 Domänen (Energie, Kräfte, Schwingung, Wärme), "
            "3 Kern-Gleichungen mit Gültigkeitsbereich, 3 Unsicherheitsbudgets, "
            "3 Falsifikationspläne (direkt messbar, knüpfen an CAD + Manufacturing + Teststand). "
            "Naht zu vorherigen Stones + bestehenden Physics-Modulen vorbereitet."
        )
    else:
        domaenen = [PhysikDomäne("Grundmechanik", "Statik + einfache Dynamik", "generic")]
        gleichungen = [ModellGleichung("F=ma", "F = m * a", "N, kg, m/s²", "low speed, rigid body", "generic")]
        budget = [UnsicherheitsBudget("Masse", "±5%", "Lasten betroffen", "generic")]
        falsi = [FalsifikationsPlan("Grundlast-Test", "Statische Last 1.5x", "Deformation", "Deformation > Grenze", "generic")]
        zusammen = "Minimal PhysikerSpec für noch nicht detailliert analysierte Idee."

    return PhysikerSpec(
        source_idea=concept.source_idea,
        relevante_domaenen=domaenen,
        modell_gleichungen=gleichungen,
        unsicherheits_budget=budget,
        falsifikations_plan=falsi,
        zusammenfassung=zusammen,
        run_id=run_id,
        quelle="physiker (third pipeline stone) + GENESIS_PLATFORM_PLAN.md §4.3 + prior Architekt + Ingenieur + Grenz + CAD",
    )
