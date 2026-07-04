"""regulatorik — Sicherheits-/Regulatorik-Pipeline first stone (PLAN §4).

Gemäß GENESIS_PLATFORM_PLAN.md §4:
- Aufgabe: Normen, Risiken, Warnungen, menschliche Freigabe, Haftungsgrenzen.
- Outputs: Normen-Liste, Risiko-Matrix, Warnhinweise, Freigabe-Prozess, Haftungsgrenzen.
- Gate: no Netzspannung without safety path, no claim without human sign-off, risks visible.

Erster Stein: Mapper from prior (Elektriker safety, Techniker, Lern test cases, DFM) to RegulatorikSpec.
Jetpack: EASA-like for manned tether flight, human pilot sign-off, tether failure risk, battery fire, liability.
Generic: honest gaps.

Naht: Pulls from Elektriker (safety interlock), Techniker (maintenance), Lern (fault tests), DFM (printable risks), Realisierungspaket (regulatorik hints in package).
"""

from __future__ import annotations

from dataclasses import dataclass

from ._triggers import is_flight_idea
from .architekt import SystemConcept
from .ingenieur import IngenieurSpec


@dataclass(frozen=True)
class Norm:
    name: str
    anwendung: str
    quelle: str | None = None


@dataclass(frozen=True)
class Risiko:
    name: str
    beschreibung: str
    schwere: str  # low/medium/high
    massnahme: str
    freigabe: str  # human sign-off required
    quelle: str | None = None


@dataclass(frozen=True)
class RegulatorikSpec:
    """Output of the Regulatorik Pipeline (first stone)."""
    source_idea: str
    normen: list[Norm]
    risiken: list[Risiko]
    warnhinweise: list[str]
    freigabe_prozess: str
    haftungsgrenzen: str
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


def map_to_regulatorik_spec(
    concept: SystemConcept,
    ingenieur: IngenieurSpec,
    *,
    run_id: str | None = None,
) -> RegulatorikSpec:
    """
    Erster Stein Regulatorik-Pipeline.
    Jetpack: manned tether flight norms, human pilot sign-off, specific risks.
    Generic: honest gaps.
    """
    if is_flight_idea(concept.source_idea):
        normen = [
            Norm("EASA CS-23 / equivalent for experimental manned tether", "Manned personal flight device with tether recovery", quelle="PLAN §4 + Elektriker safety + Safety-Ladder"),
            Norm("EN ISO 12100 (Machinery safety)", "General risk assessment for the system", quelle="PLAN §4"),
        ]
        risiken = [
            Risiko("Tether failure / loss of recovery", "Free fall or uncontrolled flight in crowd", "high", "Redundant cutoff + pilot training + tether inspection (Techniker)", "Mandatory pilot + ground crew sign-off before flight", quelle="Lern fault injection + Techniker + Elektriker"),
            Risiko("Battery fire / thermal runaway", "Fire during tethered flight", "high", "BMS + thermal monitoring + fire suppression consideration", "Human pilot sign-off + pre-flight thermal check", quelle="DFM thermal + Elektriker"),
        ]
        warn = [
            "WARNING: This is an experimental tethered flight device. Only for trained pilots in controlled areas.",
            "Liability: Operator is fully responsible; manufacturer provides no certification for manned use without local authority approval.",
        ]
        freigabe = "Human pilot + safety officer sign-off required for every flight (no autonomous release). Pre-flight checklist + post-flight report mandatory."
        haftung = "Full operator liability for any damage/injury. Device is prototype/experimental - no warranty for safety in real use. Consult local aviation authority before any public demo."
        zusammen = "Jetpack RegulatorikSpec: EASA-like + ISO norms, high risks (tether, battery) with massnahmen + human freigabe, warnings, full haftung. Naht to Elektriker/Techniker/Lern/DFM/Realisierungspaket."
        quelle = "GENESIS_PLATFORM_PLAN.md §4 (Regulatorik-Pipeline) + prior Elektriker/Techniker/Lern/DFM + Jetpack-Kanon"
    else:
        normen = [Norm("Basic machinery safety (ISO 12100)", "Generic device", quelle="Generic")]
        risiken = [Risiko("Generic failure", "Underspecified", "medium", "Basic interlock", "Human sign-off", quelle="Generic + PLAN §4")]
        warn = ["WARNING: Experimental device - use at own risk."]
        freigabe = "Human operator sign-off required."
        haftung = "Full operator liability. No certification."
        zusammen = f"Generische RegulatorikSpec für '{concept.source_idea[:40]}...'. Viele Details als Lücke."
        quelle = "GENESIS_PLATFORM_PLAN.md §4 + generic fallback (ehrliche Lücken)"

    return RegulatorikSpec(
        source_idea=concept.source_idea,
        normen=normen,
        risiken=risiken,
        warnhinweise=warn,
        freigabe_prozess=freigabe,
        haftungsgrenzen=haftung,
        zusammenfassung=zusammen,
        run_id=run_id,
        quelle=quelle,
    )
