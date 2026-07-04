"""physiker — dritter Stein der Fach-Pipelines (Physiker-Pipeline).

Gemäß GENESIS_PLATFORM_PLAN.md §4.3:
- Ziel: Die echte Physik hinter der Idee sauber modellieren.
- Aufgaben: relevante physikalische Domänen identifizieren, Modelle auswählen, Modellgrenzen beschreiben, Formeln prüfen, Dimensionsanalyse, Energie-/Kraft-/Wärme-/Schwingungsbilanzen, Unsicherheiten propagieren, Falsifikationsexperimente vorschlagen.
- Outputs: Modellkarte, Gleichungen, Grenzfälle, erwartete Messgrößen, Unsicherheitsbudget, Falsifikationsplan.
- Gate: Dimensionshomogenität, Grenzfallprüfung, keine Modellanwendung außerhalb ihres Gültigkeitsbereichs, Messbarkeit der zentralen Vorhersagen.

Erster Stein: deterministischer Mapper von SystemConcept zu PhysikerSpec (Kanon-Vorlage).

HONESTY (Schritt-9-Review #1, S-1-Muster): der ``ingenieur``-Parameter wird akzeptiert
(API-Stabilität), aber derzeit NICHT konsumiert — kein Prior (Ingenieur/Grenz/CAD/
breakthrough) speist diesen Mapper. Jeder Output ist eine PLAN-§4.3-Kanon-Vorlage; die
deklarierte Lücke ist die echte Prior-Auswertung. Geplante Naht (NOCH NICHT verdrahtet):
Prior-Stones rein, Physik-Modell/Unsicherheitsbudget/Falsifikationsplan in
CAD-Anforderungen, Manufacturing-Checks und Teststände raus.
"""

from __future__ import annotations

from dataclasses import dataclass

from .architekt import SystemConcept
from .ingenieur import IngenieurSpec

#: Honest provenance label (S-1): a canon template, not a consumed prior.
_CANON_QUELLE = "PLAN §4.3 Kanon-Vorlage, kein Prior konsumiert (Lücke: echte Prior-Auswertung)"


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
    Erster Stein der Physiker-Pipeline: deterministische PLAN-§4.3-Kanon-Vorlage je Konzept.

    ``ingenieur`` ist für die geplante Prior-Naht reserviert und wird derzeit NICHT
    konsumiert (#1, S-1-Muster) — kein quelle-Feld behauptet eine Prior-Ableitung;
    alle Zahlen (±12 % Schub etc.) sind als Kanon-Annahmen deklariert.
    """
    if "jetpack" in concept.source_idea.lower():
        domaenen = [
            PhysikDomäne("Energie & Leistung", "Batterie/Propulsion Bilanz für 5+ min Flight", _CANON_QUELLE),
            PhysikDomäne("Kräfte & Dynamik", "Tether-Zug, Schub, Recovery-Impact, Aerodynamik", _CANON_QUELLE),
            PhysikDomäne("Schwingungen & Stabilität", "Vibrationen, Control-Response, Tether-Mode", _CANON_QUELLE),
            PhysikDomäne("Wärme & Thermik", "Motor/Batterie Wärme bei Last, Dissipation", _CANON_QUELLE),
        ]
        gleichungen = [
            ModellGleichung(
                "Energie-Bilanz",
                "E_in - E_out - Verluste = E_verbleibend",
                "Wh",
                "5-10 min Flight, 20-80% SOC",
                _CANON_QUELLE,
            ),
            ModellGleichung(
                "Tether-Dynamik (vereinfacht)",
                "F_tether = m * a + Drag + Gravity_comp",
                "N",
                "Low altitude, <50 km/h Wind",
                _CANON_QUELLE,
            ),
            ModellGleichung(
                "Recovery-Entfaltung",
                "t_open < 3s bei v_fall < v_max",
                "s, m/s",
                "Single-Failure Case",
                _CANON_QUELLE,
            ),
        ]
        budget = [
            UnsicherheitsBudget("Schub", "±12% (Kanon-Annahme)", "Reichweite/Energie stark betroffen", _CANON_QUELLE),
            UnsicherheitsBudget("Tether-Last", "±20% Dynamik (Kanon-Annahme)", "Struktur/Recovery Dimensionierung", _CANON_QUELLE),
            UnsicherheitsBudget("Recovery-Zeit", "±0.8s (Kanon-Annahme)", "Sicherheitsabstand", _CANON_QUELLE),
        ]
        falsi = [
            FalsifikationsPlan(
                "Tether-Überlast Test",
                "Statische + dynamische Last bis Bruch oder 1.5x Max",
                "F_max, Dehnung",
                "Bruch vor 1.5x oder Dehnung > Grenze",
                _CANON_QUELLE,
            ),
            FalsifikationsPlan(
                "Single-Failure Recovery Drop",
                "Simulierter Ausfall bei 30m Höhe, Recovery auslösen",
                "t_open, v_impact",
                "t_open > 3s oder v_impact > sicher",
                _CANON_QUELLE,
            ),
            FalsifikationsPlan(
                "Energie-Margin Flight",
                "Vollast Flight bis SOC 20%, Verbrauch messen",
                "Wh/km oder Wh/min, SOC",
                "Verbrauch > 120% Modell oder SOC < 15% vor 5 min",
                _CANON_QUELLE,
            ),
        ]
        zusammen = (
            "PhysikerSpec für Jetpack: 4 Domänen (Energie, Kräfte, Schwingung, Wärme), "
            "3 Kern-Gleichungen mit Gültigkeitsbereich, 3 Unsicherheitsbudgets, "
            "3 Falsifikationspläne (direkt messbar). "
            "Alle Werte sind Kanon-Annahmen (aus keinem Prior abgeleitet) — die geplante "
            "Naht zu Prior-Stones und Physics-Modulen ist noch nicht verdrahtet."
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
        quelle="physiker (third pipeline stone) + GENESIS_PLATFORM_PLAN.md §4.3 — Kanon-Vorlage, kein Prior konsumiert (Lücke: echte Prior-Auswertung)",
    )
