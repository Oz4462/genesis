"""elektriker — Elektriker-/Elektronik-Pipeline (PLAN §4.5, full depth).

Gemäß GENESIS_PLATFORM_PLAN.md §4.5:
- Aufgabe: Spannung/Strom/Leistung bestimmen, Versorgung auslegen, Schutzmechanismen,
  Netze/Stecker planen, Bauteile wählen (mit Datenblatt), Schaltplan/PCB vorbereiten,
  ERC/DRC laufen lassen, thermische und EMV-Risiken sichtbar machen.
- Outputs: Schaltplanstruktur, BOM Elektronik, Netlist, Strombudget, Schutzkonzept, PCB-Regeln.
- Gate: kein undriven Load, keine zwei Treiber auf einem Netz, keine überlastete Leitung,
  keine Bauteilwahl ohne Datenblatt, keine Netzspannung ohne Sicherheits-/Regulatorikpfad.

Evolution of the first stone (high-level Stromkreis + Budget + EMV + Safety):
- Now synthesizes concrete Component selection, typed Netlist (for gate_erc),
  PowerTree, HarnessSpec, PlacementHint (for cad/assembly), electronic BOM (domain=ELECTRONIC).
- Runs deterministic DC operating-point simulation via circuit.py MNA (solve_dc),
  produces ElectronicsSimulationResult + falsification experiments (reality.py δ⁺ seam).
- Produces CAD integration artifacts (positions, keepouts, harness geometry, thermal interfaces).
- All numbers/choices carry explicit 'quelle' (L1). Re-uses existing Netlist/gate_erc/circuit
  without drift (L2). Covers every §4.5 task + seams to 8+ layers (L3). Produces runnable
  artifacts (netlist that gate_erc + solve_dc consume, placements for assembly, falsif dicts
  for evaluate_reality) with honest limits stated (L4).

Jetpack-Beispiel (canonical): 48 V 1200 W Main Drive + 12 V Tether + 5 V Control, full netlist,
ERC-pass, MNA-verified voltages/currents, CAD placements + harness, thermal power loads,
falsification experiments for bench measurement.

Generic: honest Lücken, minimal structure, no over-claim.

Naht: Nimmt SystemConcept + IngenieurSpec (+ optional Physiker loads/thermal), erzeugt
Elektronik-Anforderungen + Netlist + BOM + CAD-Artifacts die in Specification (γ), gate_erc,
simulation/runner (thermal co-sim), cad/assembly, integrator (Realisierungspaket), lernmaschine,
wissensbasis, software (Embedded signals), fertigungs (PCB DFM) und reality fließen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .architekt import SystemConcept
from .ingenieur import IngenieurSpec

# Deep electronics layer (PLAN §4.5 full depth, no drift on existing high-level path)
try:
    from gen.electronics import (
        build_rich_electronics_pieces,
        Component as ElectronicsComponent,
        ElectronicsSimulationResult,
        PlacementHint,
        PowerTree,
        HarnessSpec,
    )
except Exception:  # pragma: no cover - exercised when deep layer not importable
    build_rich_electronics_pieces = None  # type: ignore
    ElectronicsComponent = None  # type: ignore
    ElectronicsSimulationResult = None  # type: ignore
    PlacementHint = None  # type: ignore
    PowerTree = None  # type: ignore
    HarnessSpec = None  # type: ignore


@dataclass(frozen=True)
class Stromkreis:
    """Ein Stromkreis mit Leistung und Schutz."""
    name: str
    spannung_v: float
    leistung_w: float
    schutz: str  # z.B. "Fuse 15A + Isolierung"
    quelle: str | None = None


@dataclass(frozen=True)
class LeistungsBudget:
    """Gesamt-Budget und Verteilung."""
    gesamt_w: float
    verteilung: dict[str, float]  # Komponente -> Watt
    reserve_prozent: float
    quelle: str | None = None


@dataclass(frozen=True)
class EMVCheck:
    """EMV / Störungs-Schutz (einfach aber ehrlich)."""
    massnahme: str
    betroffene_komponenten: list[str]
    nachweis: str  # z.B. "Shielding + Filter nach IEC 61000"
    quelle: str | None = None


@dataclass(frozen=True)
class SicherheitsAnforderung:
    """Sicherheits- und Fail-Safe Anforderungen."""
    name: str
    beschreibung: str
    failure_mode: str
    massnahme: str
    quelle: str | None = None


@dataclass(frozen=True)
class ElektronikSpec:
    """Output der Elektriker-/Elektronik-Pipeline (PLAN §4.5 full depth).

    High-level fields (Stromkreis etc.) preserved from first stone for continuity.
    Rich fields (components, netlist, placement_hints, simulation_result, ...) added
    by the deep layer (gen.electronics) — all with 'quelle', all deterministic,
    all directly consumable by gate_erc, circuit.solve_*, cad/assembly, reality,
    lernmaschine and integrator.
    """
    source_idea: str
    stromkreise: list[Stromkreis]
    leistungs_budget: LeistungsBudget
    emv_checks: list[EMVCheck]
    sicherheits_anforderungen: list[SicherheitsAnforderung]
    pcb_hinweise: list[str]
    pruefplan: list[str]
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None

    # --- deep / rich fields (additive, default=None/empty for backward compat) ---
    components: list = field(default_factory=list)  # list[electronics.Component]
    power_tree: Any | None = None
    netlist: Any | None = None  # core.state.Netlist (typed pins + nets)
    electronic_bom: list = field(default_factory=list)  # list[core.state.BomItem] domain=ELECTRONIC
    placement_hints: list = field(default_factory=list)  # list[electronics.PlacementHint]
    harness: Any | None = None
    simulation_result: Any | None = None  # electronics.ElectronicsSimulationResult
    falsification_experiments: list = field(default_factory=list)  # δ⁺ ready
    schaltplan_text: str = ""
    cad_integration: dict[str, Any] = field(default_factory=dict)


def map_to_elektriker_spec(
    concept: SystemConcept,
    ingenieur: IngenieurSpec,
    *,
    run_id: str | None = None,
) -> ElektronikSpec:
    """
    Elektriker-Pipeline (PLAN §4.5 full depth).

    High-level path (Stromkreis, Budget, EMV, Safety, pcb_hinweise, pruefplan,
    zusammenfassung) is preserved exactly for the original first-stone callers
    and the two existing tests.

    Additionally (when the deep layer is available): calls into
    electronics.build_rich_electronics_pieces to attach:
    - components (with electrical/thermal/footprint + quelle)
    - power_tree, netlist (typed for gate_erc), electronic_bom (domain=ELECTRONIC)
    - placement_hints + harness (for cad/assembly)
    - simulation_result (MNA DC via circuit.py) + falsification_experiments (reality.py)
    - schaltplan_text + cad_integration

    The resulting ElektronikSpec is a strict superset — all original attributes
    are identical for the Jetpack and generic cases.
    """
    idee_lower = concept.source_idea.lower()
    is_jet = "jetpack" in idee_lower or "flug" in idee_lower

    # --- high-level (exact same numbers/texts as first stone for test compat) ---
    if is_jet:
        stromkreise = [
            Stromkreis("Main Drive", 48.0, 1200.0, "High-current fuse + contactor + emergency cutoff", quelle="PLAN §4.5 + Ingenieur Lastfälle + Jetpack Thrust"),
            Stromkreis("Tether Electronics", 12.0, 60.0, "Isolated DC-DC + watch-dog + redundant signal", quelle="Tether-Anchor aus Techniker + Safety-Ladder"),
            Stromkreis("Control & Sensors", 5.0, 25.0, "Fuse + EMI filter + brown-out detection", quelle="Architekt Systemgrenzen + Physiker Unsicherheit"),
        ]
        budget = LeistungsBudget(gesamt_w=1300.0, verteilung={"Main Drive": 1200.0, "Tether": 60.0, "Control": 25.0, "Reserve": 15.0}, reserve_prozent=10.0, quelle="Thrust-Anforderung aus Grenz + Ingenieur + CAD Volumen")
        emv = [
            EMVCheck("Shielded harness + ferrite on motor leads", ["Main Drive", "Tether"], "IEC 61000-6-2/6-3 for manned flight equipment", quelle="EMV für bemannte Systeme + Regulatorik-Pfad"),
        ]
        safety = [
            SicherheitsAnforderung("Emergency Power Cut", "Total power disconnect on pilot command or tether tension loss", "Loss of control / fire", "Independent relay + manual override + battery BMS", quelle="Safety-Ladder S3+ + Techniker Reparatur/Sicherheit"),
            SicherheitsAnforderung("Redundant signaling", "Two independent channels for motor enable", "Single point failure", "Diverse sensors + cross-check in firmware", quelle="PLAN §4.5 + Ingenieur Failure-Modes"),
        ]
        pcb = ["High-current traces for 48V drive (min 2oz copper)", "Isolated sections for tether vs. flight electronics", "Thermal vias under motor drivers", "Test points for in-flight diagnostics"]
        pruef = ["Power-on self-test + brown-out", "Full load endurance 5 min (Gate)", "EMV immunity sweep", "Tether disconnect simulation (Safety Gate)"]
        zusammen = "Jetpack Elektronik: 48V Main Drive (1200W), 12V Tether (60W), 5V Control. Budget 1300W mit 10% Reserve. EMV + dual Safety Cutoff. PCB + Prüfplan für bemannten Betrieb."
        high_quelle = "GENESIS_PLATFORM_PLAN.md §4.5 (Elektriker-Pipeline) + prior Architekt/Ingenieur/Techniker/Safety + CAD real artifacts + Jetpack-Kanon"
    else:
        # Ehrlicher generischer Fallback (unchanged)
        stromkreise = [Stromkreis("Main Power", 12.0, 50.0, "Standard fuse + basic protection", quelle="Generic from SystemConcept power hint")]
        budget = LeistungsBudget(gesamt_w=60.0, verteilung={"Main": 50.0, "Reserve": 10.0}, reserve_prozent=15.0, quelle="Generic estimate")
        emv = [EMVCheck("Basic filtering", ["Main"], "Standard consumer EMI compliance", quelle="Minimal assumption - Lücke für spezifische Norm")]
        safety = [SicherheitsAnforderung("Basic overcurrent", "Fuse protection", "Overload", "Replaceable fuse", quelle="Minimal")]
        pcb = ["Standard 1oz copper for low power", "Clear separation of power and signal if needed"]
        pruef = ["Basic power-up test", "Load test to spec"]
        zusammen = f"Generische Elektronik-Spec für '{concept.source_idea[:40]}...'. Viele Details als Lücke markiert (keine spezifische Last aus vorherigen Steinen)."
        high_quelle = "GENESIS_PLATFORM_PLAN.md §4.5 + generic fallback (ehrliche Lücken)"

    # --- deep layer (full §4.5 synthesis) ---
    deep: dict[str, Any] = {
        "components": [],
        "power_tree": None,
        "netlist": None,
        "electronic_bom": [],
        "placement_hints": [],
        "harness": None,
        "simulation_result": None,
        "falsification_experiments": [],
        "schaltplan_text": "",
        "cad_integration": {},
        "quelle": high_quelle,
    }
    if build_rich_electronics_pieces is not None:
        try:
            pieces = build_rich_electronics_pieces(
                concept.source_idea,
                budget.gesamt_w if hasattr(budget, "gesamt_w") else 60.0,
                safety_context=getattr(ingenieur, "quelle", "") or "",
                run_id=run_id,
            )
            deep.update(pieces)
            # merge provenance
            deep["quelle"] = (high_quelle + " | " + pieces.get("quelle", "")).strip(" |")
        except Exception:
            # never hide — fall back to high-level only (honest Lücke)
            deep["schaltplan_text"] = "Deep synthesis unavailable in this environment (Lücke)."
            deep["quelle"] = high_quelle + " + deep layer unavailable (Lücke)"

    return ElektronikSpec(
        source_idea=concept.source_idea,
        stromkreise=stromkreise,
        leistungs_budget=budget,
        emv_checks=emv,
        sicherheits_anforderungen=safety,
        pcb_hinweise=pcb,
        pruefplan=pruef,
        zusammenfassung=zusammen,
        run_id=run_id,
        quelle=deep["quelle"],
        # rich (populated when deep layer succeeded)
        components=deep["components"],
        power_tree=deep["power_tree"],
        netlist=deep["netlist"],
        electronic_bom=deep["electronic_bom"],
        placement_hints=deep["placement_hints"],
        harness=deep["harness"],
        simulation_result=deep["simulation_result"],
        falsification_experiments=deep["falsification_experiments"],
        schaltplan_text=deep["schaltplan_text"],
        cad_integration=deep["cad_integration"],
    )
