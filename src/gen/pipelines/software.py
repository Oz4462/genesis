"""software — Software-/Firmware-Pipeline first stone (PLAN §4).

Gemäß GENESIS_PLATFORM_PLAN.md §4:
- Aufgabe: Steuerung, Embedded, APIs, Tests, Updatefähigkeit, Fehlerzustände.
- Outputs: Software-Architektur, Embedded Spec, API contracts, Testplan, Update/OTA hints, Failure states.
- Gate: no undriven load (software analog), no unhandled failure state, no update without rollback, no API without contract.

Erster Stein: deterministischer Mapper von SystemConcept + prior (Elektriker for control, Techniker for update) zu SoftwareSpec.
Jetpack example: Thrust controller (embedded on motor side), Tether safety interlock, API for ground station, OTA update path, error states (loss of tether, overtemp).
Generic Fallback with honest gaps.

Naht: Takes prior (Elektriker for signals, Techniker for maintenance/update, DFM for thermal, Lern for test cases). Output feeds Realisierungspaket (firmware in package) and Regulatorik (safety software). Executable artifacts are validated by ``gen.software.run_python_artifact`` via ``gate_code`` (verification/gates.py) — correctness proven by execution, not model judgement.
"""

from __future__ import annotations

from dataclasses import dataclass

from .architekt import AssemblyConcept, SystemConcept
from .ingenieur import FailureMode, IngenieurSpec

# Keywords that mark an assembly as needing active control/monitoring (i.e. an
# embedded node), as opposed to being purely structural. German + English so the
# generic mapper works for any idea, not just the jetpack canon. WHY a keyword
# heuristic instead of a hardcoded list: the only honest signal we have about a
# non-jetpack idea is the assembly's own declared name/purpose/interfaces — we
# derive control-relevance from THOSE, we do not invent it.
_CONTROL_KEYWORDS: tuple[str, ...] = (
    "control", "steuer", "regel", "sensor", "sensing", "motor", "antrieb",
    "propuls", "schub", "power", "energie", "energy", "drive", "actuat",
    "aktor", "valve", "ventil", "pump", "pumpe", "heat", "therm", "comm",
    "signal", "flight", "flug", "navig", "telemetr", "battery", "akku",
    "interlock", "safety", "recovery",
)


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


def _needs_control(assembly: AssemblyConcept) -> bool:
    """Return True if an assembly plausibly needs an embedded controller/monitor.

    The decision is derived ONLY from the assembly's own declared name, purpose and
    interfaces (no invented system knowledge), so a purely structural assembly does
    not silently grow a fabricated controller.
    """
    haystack = " ".join(
        [assembly.name, assembly.purpose, *assembly.interfaces]
    ).lower()
    return any(kw in haystack for kw in _CONTROL_KEYWORDS)


def _failure_states_for(
    assembly: AssemblyConcept, failure_modes: list[FailureMode]
) -> list[str]:
    """Derive an embedded component's declared failure states.

    Every embedded node carries the universal ``comm_loss`` baseline (a genuine,
    non-fabricated failure mode of any communicating controller), plus every
    Ingenieur-declared failure mode whose originating assembly matches this one.
    The gate intent — *no unhandled failure state* — is honoured because the list
    is never empty.
    """
    states = ["comm_loss"]
    name_l = assembly.name.lower()
    for fm in failure_modes:
        quelle_l = fm.aus_baugruppe.lower()
        # Match in either direction so "Propulsion / Frame" links to a
        # "Propulsion" assembly and vice versa.
        if name_l and (name_l in quelle_l or quelle_l in name_l):
            states.append(fm.name)
    return states


def map_to_software_spec(
    concept: SystemConcept,
    ingenieur: IngenieurSpec,
    *,
    run_id: str | None = None,
) -> SoftwareSpec:
    """Erster Stein Software-Pipeline: mappt SystemConcept + IngenieurSpec → SoftwareSpec.

    Jetpack: Thrust controller + Tether safety + ground API + OTA + error states
    (kanonischer Spezialfall, byte-stabil).

    Generischer Pfad: leitet die Embedded-Komponenten aus ``concept.main_assemblies``
    ab (jede steuerungs-relevante Baugruppe wird ein Knoten), die deklarierten
    Fehlerzustände aus ``ingenieur.failure_modes`` und den Testplan aus eben diesen
    Failure-Modes (Fault-Injection je deklariertem Fehler). Wo Rollback-/OTA-Fähigkeit
    nicht analysiert ist, wird eine explizite Lücke deklariert statt still „kein
    Rollback" zu behaupten. Zwei verschiedene Eingaben → unterscheidbare Outputs.

    Gate-Intent (PLAN §4): jede ``EmbeddedComponent`` listet ≥1 Fehlerzustand, jede
    ``APISpec`` hat nicht-leeres input/output/sicherheit.

    Raises:
        ValueError: wenn weder ``concept.source_idea`` (nach strip) noch
            ``concept.main_assemblies`` ein verwertbares Signal liefern — eine
            fehlende Eingabe darf keinen fabrizierten Stub erzeugen
            (Kernprinzip: keine stillen Defaults).
    """
    if not concept.source_idea.strip() and not concept.main_assemblies:
        raise ValueError(
            "concept has no actionable signal: source_idea is blank and "
            "main_assemblies is empty — refusing to fabricate a SoftwareSpec stub"
        )

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
        idea_text = concept.source_idea.strip() or "(unbenannte Idee)"

        # Embedded: one node per control-relevant assembly, failure states drawn
        # from the Ingenieur failure modes. Purely structural assemblies do NOT
        # become controllers (no fabrication).
        embedded = [
            EmbeddedComponent(
                name=f"{a.name} Controller",
                funktion=f"Steuerung/Überwachung der Baugruppe »{a.name}« ({a.purpose})",
                interface=", ".join(a.interfaces) if a.interfaces else "I/O (Lücke: Schnittstellen nicht spezifiziert)",
                fehler_zustaende=_failure_states_for(a, ingenieur.failure_modes),
                quelle=f"abgeleitet aus Architekt-Baugruppe + Ingenieur failure_modes (concept »{idea_text}«)",
            )
            for a in concept.main_assemblies
            if _needs_control(a)
        ]
        # Honest fallback: if no assembly is control-relevant we still need a
        # software node for the system, but we declare that no control-specific
        # assembly was identified rather than inventing one.
        if not embedded:
            embedded = [
                EmbeddedComponent(
                    name="SystemMonitor",
                    funktion=f"Basis-Überwachung des Gesamtsystems »{idea_text}« "
                    "(keine steuerungs-spezifische Baugruppe identifiziert — Lücke)",
                    interface="Status-I/O (Lücke: keine Steuer-Schnittstelle aus Konzept ableitbar)",
                    # Gate intent: a component never ships without a failure state.
                    fehler_zustaende=["comm_loss"],
                    quelle="generic fallback (keine control-relevante Baugruppe)",
                )
            ]

        # API: a status/telemetry contract over the derived components. Contract is
        # non-empty (gate: no API without contract); command/write paths are an
        # explicit gap, not silently asserted.
        komponenten_namen = ", ".join(e.name for e in embedded)
        apis = [
            APISpec(
                name="StatusAPI",
                beschreibung=f"Statusabfrage der Komponenten ({komponenten_namen}) für »{idea_text}«",
                input="Statusabfrage (read-only)",
                output="JSON: Zustand + deklarierte Fehlerzustände je Komponente",
                sicherheit="Auth erforderlich, rate-limited, read-only "
                "(Lücke: Befehls-/Schreib-API noch nicht spezifiziert)",
                quelle=f"abgeleitet aus Embedded-Komponenten (concept »{idea_text}«)",
            )
        ]

        # Update path: rollback capability is NOT analysed here, so we declare an
        # explicit honest gap instead of falsely asserting 'No rollback'.
        update = UpdatePfad(
            methode="Update-Methode nicht festgelegt (Lücke: OTA/Flash je nach Hardware offen)",
            rollback="UNBEKANNT — Rollback-Fähigkeit nicht analysiert "
            "(explizite Lücke, nicht als 'kein Rollback' behauptet)",
            test="A/B- oder Health-Check-Strategie noch zu definieren (Lücke)",
            quelle="generic fallback + PLAN §4 (ehrliche Lücke statt geratener Default)",
        )

        # Testplan: fault-injection per declared failure mode (derived, not canned).
        testplan = [
            "Unit-Tests je Steuer-Komponente (State Machines)",
            "Integrationstest: Komponenten ↔ StatusAPI",
        ]
        for fm in ingenieur.failure_modes:
            testplan.append(
                f"Fault-Injection: {fm.name} ({fm.aus_baugruppe}) → muss in sicheren "
                f"Zustand übergehen (Detection: {fm.detection})"
            )
        if not ingenieur.failure_modes:
            testplan.append(
                "Fault-Injection-Tests offen (Lücke): keine Failure-Modes aus "
                "Ingenieur deklariert"
            )

        zusammen = (
            f"Generische SoftwareSpec für »{idea_text}«: {len(embedded)} Embedded-"
            f"Komponente(n) aus den Baugruppen abgeleitet, {len(apis)} API "
            f"(read-only-Kontrakt), Testplan aus {len(ingenieur.failure_modes)} "
            "Failure-Mode(s). Update/Rollback als explizite Lücke deklariert."
        )
        quelle = "GENESIS_PLATFORM_PLAN.md §4 + generischer Mapper (Inputs konsumiert, ehrliche Lücken)"

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
