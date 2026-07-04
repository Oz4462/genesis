"""software — Software-/Firmware-Pipeline first stone (PLAN §4).

Gemäß GENESIS_PLATFORM_PLAN.md §4:
- Aufgabe: Steuerung, Embedded, APIs, Tests, Updatefähigkeit, Fehlerzustände.
- Outputs: Software-Architektur, Embedded Spec, API contracts, Testplan, Update/OTA hints, Failure states.
- Gate: no undriven load (software analog), no unhandled failure state, no update without rollback, no API without contract.

Erster Stein: deterministischer Mapper von SystemConcept zu SoftwareSpec.
Jetpack example: Thrust controller (embedded on motor side), Tether safety interlock, API for ground station, OTA update path, error states (loss of tether, overtemp).
Generic Fallback with honest gaps.

HONESTY (Schritt-8-Review S-1): the ``ingenieur`` parameter is accepted for API stability but
currently NOT consumed — no prior (Elektriker/Techniker/DFM/Lern) feeds this mapper yet. Every
output is a PLAN §4 canon template; the declared gap is a real prior evaluation. Planned seam
(NOT yet wired): prior pipelines in, Realisierungspaket (firmware) and Regulatorik out.
"""

from __future__ import annotations

from dataclasses import dataclass

from ._triggers import is_flight_idea
from .architekt import SystemConcept
from .ingenieur import IngenieurSpec

#: Honest provenance label for the flight-canon outputs (S-1): a template, not a consumed prior.
_CANON_QUELLE = "PLAN §4 Kanon-Vorlage, kein Prior konsumiert (Lücke: echte Prior-Auswertung)"


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
    Erster Stein Software-Pipeline: deterministic PLAN §4 canon template per concept.

    ``ingenieur`` is reserved for the planned prior seam and currently NOT consumed
    (S-1) — the spec never claims a prior-derived detail; the flight canon declares
    its assumptions as such. Flight terms match on word boundaries (S-2), so
    "Ausflug"/"Flughafen" fall through to the generic path with honest gaps.
    """
    if is_flight_idea(concept.source_idea):
        embedded = [
            EmbeddedComponent("ThrustController", "Closed-loop thrust from pilot command to motor drivers", "PWM + CAN", ["overtemp", "loss_of_feedback", "comm_loss"], quelle=_CANON_QUELLE),
            EmbeddedComponent("TetherSafety", "Interlock: only enable if tether present + emergency line high", "Digital in + discrete enable", ["tether_loss", "false_positive"], quelle=_CANON_QUELLE),
        ]
        apis = [
            APISpec("GroundTelemetry", "Real-time state (thrust, temp, tether, battery) to ground station", "sensor data", "JSON telemetry + alerts", "signed, rate-limited, loss-of-link timeout", quelle=_CANON_QUELLE),
        ]
        update = UpdatePfad("OTA via tether or wireless (staged: sim -> bench -> flight)", "Rollback to last known-good image on CRC fail or manual command", "A/B partition + health check before commit", quelle=_CANON_QUELLE)
        testplan = [
            "Unit tests for state machines (thrust, safety interlock)",
            "HIL bench with real motor driver",
            "Fault injection (tether loss, overtemp) - must go to safe state",
            "OTA roundtrip test (sim + rollback)",
        ]
        zusammen = (
            "Jetpack SoftwareSpec: Embedded (ThrustController + TetherSafety), API (GroundTelemetry), "
            "OTA mit Rollback, Testplan mit Fault Injection. "
            "Lücke: Fehlerzustände und OTA-Details sind Kanon-Annahmen (aus keinem Prior abgeleitet) — "
            "die geplante Naht zu Prior-Pipelines/Realisierungspaket ist noch nicht verdrahtet."
        )
        quelle = "GENESIS_PLATFORM_PLAN.md §4 (Software-Pipeline) — Kanon-Vorlage, kein Prior konsumiert (Lücke: echte Prior-Auswertung)"
    else:
        embedded = [EmbeddedComponent("MainController", "Basic control loop", "simple I/O", ["comm_loss"], quelle="Generic")]
        apis = [APISpec("BasicAPI", "Status query", "none", "status JSON", "basic auth", quelle="Generic")]
        update = UpdatePfad("Manual flash", "No rollback (Lücke)", "Manual verify", quelle="Generic + PLAN §4")
        testplan = ["Basic unit + integration (Lücke for fault injection)"]
        zusammen = f"Generische SoftwareSpec für '{concept.source_idea[:40]}...'. Viele Details als Lücke (keine spezifische control/safety, kein Prior konsumiert)."
        quelle = "GENESIS_PLATFORM_PLAN.md §4 + generic fallback (ehrliche Lücken, kein Prior konsumiert)"

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
