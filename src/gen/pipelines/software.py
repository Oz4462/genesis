"""software — Software-/Firmware-Pipeline first stone (PLAN §4).

Gemäß GENESIS_PLATFORM_PLAN.md §4:
- Aufgabe: Steuerung, Embedded, APIs, Tests, Updatefähigkeit, Fehlerzustände.
- Outputs: Software-Architektur, Embedded Spec, API contracts, Testplan, Update/OTA hints, Failure states.
- Gate: no undriven load (software analog), no unhandled failure state, no update without rollback, no API without contract.

Erster Stein: deterministischer Mapper von SystemConcept + prior (Elektriker for control, Techniker for update) zu SoftwareSpec.
Jetpack example: Thrust controller (embedded on motor side), Tether safety interlock, API for ground station, OTA update path, error states (loss of tether, overtemp).
Generic Fallback with honest gaps.

Naht: Takes prior (Elektriker for signals, Techniker for maintenance/update, DFM for thermal, Lern for test cases). Output feeds Realisierungspaket (firmware in package) and Regulatorik (safety software).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .architekt import SystemConcept
from .ingenieur import IngenieurSpec


@dataclass(frozen=True)
class EmbeddedComponent:
    """Embedded controller or sensor node."""
    name: str
    funktion: str
    interface: str
    fehler_zustaende: list[str]
    quelle: str | None = None


@dataclass(frozen=True)
class APISpec:
    """API contract (ground station / telemetry)."""
    name: str
    beschreibung: str
    input: str
    output: str
    sicherheit: str
    quelle: str | None = None


@dataclass(frozen=True)
class UpdatePfad:
    """OTA / Update path and rollback."""
    methode: str
    rollback: str
    test: str
    quelle: str | None = None


@dataclass(frozen=True)
class SoftwareSpec:
    """Output of the Software/Firmware Pipeline (first stone)."""
    source_idea: str
    embedded_components: list[EmbeddedComponent]
    apis: list[APISpec]
    update_pfad: UpdatePfad
    testplan: list[str]
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


def map_to_software_spec(
    concept: SystemConcept,
    ingenieur: IngenieurSpec,
    *,
    run_id: str | None = None,
) -> SoftwareSpec:
    """
    Erster Stein Software-Pipeline.
    Jetpack: Thrust controller + Tether safety + ground API + OTA + error states.
    Generic: honest gaps.
    """
    idee_lower = concept.source_idea.lower()

    if "jetpack" in idee_lower or "flug" in idee_lower:
        embedded = [
            EmbeddedComponent("ThrustController", "Closed-loop thrust from pilot command to motor drivers", "PWM + CAN (from Elektriker)", ["overtemp", "loss_of_feedback", "comm_loss"], quelle="Elektriker + DFM thermal + PLAN §4"),
            EmbeddedComponent("TetherSafety", "Interlock: only enable if tether present + emergency line high", "Digital in + discrete enable", ["tether_loss", "false_positive"], quelle="Techniker safety + Elektriker redundant signaling"),
        ]
        apis = [
            APISpec("GroundTelemetry", "Real-time state (thrust, temp, tether, battery) to ground station", "sensor data", "JSON telemetry + alerts", "signed, rate-limited, loss-of-link timeout", quelle="Lern test cases + Regulatorik"),
        ]
        update = UpdatePfad("OTA via tether or wireless (staged: sim -> bench -> flight)", "Rollback to last known-good image on CRC fail or manual command", "A/B partition + health check before commit", quelle="Techniker Wartung + Lern 'updatefähigkeit'"),
        testplan = [
            "Unit tests for state machines (thrust, safety interlock)",
            "HIL bench with real motor driver (from DFM/assembly)",
            "Fault injection (tether loss, overtemp) - must go to safe state",
            "OTA roundtrip test (sim + rollback)",
        ]
        zusammen = "Jetpack SoftwareSpec: Embedded (ThrustController + TetherSafety), API (GroundTelemetry), OTA with rollback, testplan with fault injection. Naht to Elektriker/Techniker/DFM/Lern/Realisierungspaket."
        quelle = "GENESIS_PLATFORM_PLAN.md §4 (Software-Pipeline) + prior Elektriker/Techniker/DFM/Lern + Jetpack-Kanon"
    else:
        embedded = [EmbeddedComponent("MainController", "Basic control loop", "simple I/O", ["comm_loss"], quelle="Generic")]
        apis = [APISpec("BasicAPI", "Status query", "none", "status JSON", "basic auth", quelle="Generic")]
        update = UpdatePfad("Manual flash", "No rollback (Lücke)", "Manual verify", quelle="Generic + PLAN §4")
        testplan = ["Basic unit + integration (Lücke for fault injection)"]
        zusammen = f"Generische SoftwareSpec für '{concept.source_idea[:40]}...'. Viele Details als Lücke (keine spezifische control/safety from prior)."
        quelle = "GENESIS_PLATFORM_PLAN.md §4 + generic fallback (ehrliche Lücken)"

    return SoftwareSpec(
        source_idea=concept.source_idea,
        embedded_components=embedded,
        apis=apis,
        update_pfad=update,
        testplan=testplan,
        zusammenfassung=zusammen,
        run_id=run_id,
        quelle=quelle,
    )
