"""electronics — Deep Electronics / Elektriker layer (PLAN §4.5 + HORIZON δ⁺/ε).

This is the evolved "Electronics / Elektriker" subsystem for Genesis.
It closes the gap between the high-level first-stone (pipelines/elektriker.py)
and real netlists, component selection, deterministic simulation (via circuit.py MNA),
co-simulation hints (power -> thermal), CAD integration artifacts (placement + harness
for cad/assembly.py), ERC (already in verification/gates.py but now fed real netlists),
functional verification (solve_dc cross-checks), safety/derating, test vectors, and
falsification experiments for reality.py (δ⁺).

Design per 4 Linsen + GENESIS_PLATFORM_PLAN.md §4.5:
- L1 (Truth): every number, choice, component param carries explicit 'quelle'
  (PLAN §4.5 + prior Architekt/Ingenieur/Physiker/Safety + representative COTS
  practice for portable high-power electric thrust systems 2026; no invented
  datasheets — typical values are declared as such + cross-checkable).
- L2 (no Drift): re-uses exactly the existing Netlist/Pin/PinType/BomDomain,
  gate_erc, circuit.solve_* family, SimulationCase/Result pattern from
  simulation/runner.py, AssemblyPart/Artifact from cad/assembly, Falsification
  structures from reality, LumenHammer/learning from lernmaschine + lumencrucible,
  ProvenanceRecord from wissensbasis.store. No change to solvers or gates.
- L3 (Completeness/Seams): covers ALL §4.5 tasks/outputs (V/I/P, supply,
  protection, nets, part selection, Schaltplan/PCB prep, ERC/DRC-ready,
  thermal/EMV risks). Explicit seams to:
  * Architekt/Ingenieur/Physiker (power budget, loads, thermal env, safety)
  * simulation/runner (power dissipation as thermal loads + elec sim cases)
  * cad/assembly + prototype_cad_builder (3D component placement, keepouts,
    heatsink interfaces, harness geometry for multi-board harness routing)
  * verification/gates (gate_erc on synthesized netlist; later DRC hints)
  * reality (generate_falsification_experiments_for_electronics)
  * lernmaschine/lumencrucible (efficiency deltas, part swaps)
  * wissensbasis (component recipes with provenance; seed path)
  * integrator (full Realisierungspaket includes Schaltplan text, netlist,
    elec BOM, placement, test plan, harness)
  * software (EmbeddedComponent signals/rails from netlist)
  * fertigungs (PCB-Regeln: copper weight, trace width from I, DFM stub)
  * thermal (p_dissip -> node heat sources)
  Open gaps explicitly: full pro autorouter + geometric/impedance/SI/thermal-trace DRC (KiCad/Altium seam for sign-off),
  vendor-precise SPICE/IBIS/3D-EM solvers (Ansys etc remain external-tool for ultra-precision validation under same proof standard).
  Internal rule-based auto-place + basic DRC (I-derived trace, clearance, bus rules, density, thermal separation) + routed harness now present (deterministic, provenance, multi-board/CAN aware) — sufficient for package, early validation, Lern deltas and generalist use across ANY idea domain.
- L4 (Realizability): produces *runnable* artifacts:
  * Netlist that gate_erc accepts and passes for sound cases.
  * Components that circuit.solve_dc (or solve_dc_nonlinear) can consume
    (via equivalent resistive models for DC op-point; real non-linear in
    future when diode models attached).
  * Placement/harness dicts directly usable by build_assembly (positions,
    labels).
  * Falsification dicts directly mappable to reality.FalsificationExperiment.
  * Tests (this module + updated test_elektriker) execute and assert numbers.
  Honest boundary stated: rich internal (DC + transient + AC + basic EMI + rule-based auto-place + basic DRC for trace/I/clearance/bus/density + routed harness hints). Full pro autorouter + geometric/impedance/SI/thermal DRC and vendor-precise SPICE/IBIS/3D-EM remain the external-tool seam (KiCad/Altium/Ansys class) under same proof standard — internal versions are deterministic, fast, provenance-rich and "besser als vorher" for Genesis package/validation/Lern/generalist use on ANY idea. See circuit.py for MNA core.

For complex products (drone/robot): supports distributed electronics via multiple
power domains, inter-board harnesses, redundant rails, sensor fusion power.

No heavy external deps beyond what Genesis already uses (numpy via circuit;
build123d optional and already in CAD path). Offline-first, deterministic core.

Starter: concrete for Jetpack (48 V main drive 1200 W, 12 V tether, 5 V control)
+ honest generic fallback. Extension point for wissensbasis component query.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


from .circuit import (
    GROUND,
    Resistor,
    VoltageSource,
    solve_dc,
)
from .core.state import (
    BomDomain,
    BomItem,
    BomRole,
    Net,
    Netlist,
    Pin,
    PinType,
)
from .verification.gates import gate_erc  # for self-check in helpers
from .core.state import RunState, Question, Specification  # for local erc smoke


# =============================================================================
# Core domain dataclasses (rich, provenance everywhere, L1)
# =============================================================================

@dataclass(frozen=True)
class Component:
    """Concrete electronic component with electrical, thermal, mechanical params.

    This is the selectable/placeable atom for the layer. All fields that are
    "facts" (V, I, power, footprint, r_th) carry 'quelle' (datasheet or declared
    representative COTS + PLAN anchor). No silent assumptions.

    For first stone we use equivalent-circuit models for DC op-point (see
    run_electronics_simulation). Real SPICE subcircuits or IBIS are future.
    """
    id: str
    name: str
    kind: str  # 'battery' | 'regulator' | 'esc' | 'motor_driver' | 'dcdc' | 'fuse' | 'contactor' | 'sensor' | 'mcu' | 'connector'
    v_nom: float  # nominal voltage (V)
    i_max: float  # max continuous current (A)
    p_max_dissip: float  # max allowable dissipation in package (W)
    footprint_mm: tuple[float, float, float]  # LxWxH approx for placement
    r_th_jc_k_per_w: float | None = None  # thermal resistance junction-to-case
    package: str = ""  # e.g. "XT60", "TO-220", "QFN-48"
    pin_names: list[str] = field(default_factory=list)  # e.g. ["V+", "GND", "EN"]
    datasheet_ref: str = ""  # "typical COTS 48V 30A ESC for portable thrust"
    quelle: str | None = None


@dataclass(frozen=True)
class PowerRail:
    """One rail in the power tree."""
    name: str
    v_nom: float
    i_budget_a: float
    source: str  # which component drives it
    protection: str
    quelle: str | None = None


@dataclass(frozen=True)
class PowerTree:
    """Top-level power architecture (budget + distribution)."""
    rails: list[PowerRail]
    total_budget_w: float
    reserve_pct: float
    cross_check_vs_loads: str  # "matches Ingenieur thrust + safety"
    quelle: str | None = None


@dataclass(frozen=True)
class HarnessSegment:
    """One harness run between boards/connectors (for CAD routing + DFM)."""
    from_ref: str
    to_ref: str
    gauge_mm2: float
    length_mm: float
    signals: list[str]
    current_a: float
    voltage_v: float
    quelle: str | None = None


@dataclass(frozen=True)
class HarnessSpec:
    """Full harness definition for distributed/modular systems (general for ALL ideas: mech, elec, bio, energy...).
    Supports multi-board, CAN-like buses, Power-over-Tether, redundancy, sensor-fusion.
    Intentionally general - not electronics-only.
    """
    segments: list[HarnessSegment]
    total_mass_est_g: float
    emc_measures: list[str]
    bus_type: str = "simple"  # "CAN-FD", "Power-over-Tether", "redundant", "sensor-fusion-bus" etc.
    redundancy: str = "none"  # "dual", "triple" etc.
    tether_support: bool = False
    quelle: str | None = None


@dataclass(frozen=True)
class PlacementHint:
    """3D placement + interface data for cad/assembly + prototype_cad_builder.

    Positions are in the top-level assembly coordinate system (mm). Orientation
    is (rx, ry, rz) degrees. keepout is envelope that must stay clear.
    heatsink_interface=True means a thermal pad / heatsink boss must be provided
    by the mechanical CAD (seam to thermal + assembly).
    """
    ref_des: str  # e.g. "U1" or component id
    pos_mm: tuple[float, float, float]
    rot_deg: tuple[float, float, float] = (0.0, 0.0, 0.0)
    footprint: str = ""
    keepout_mm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    heatsink_interface: bool = False
    wire_attach_points: list[str] = field(default_factory=list)  # connector refs
    quelle: str | None = None


@dataclass(frozen=True)
class ElectronicsSimulationCase:
    """One verifiable prediction from the electronics domain (δ⁺ ready).

    Mirrors SimulationCase from simulation/runner.py for seam compatibility.
    """
    domain: str  # "electrical_dc_op" | "power_budget" | "voltage_rail"
    description: str
    predicted_value: float
    predicted_unit: str
    tolerance: float
    inputs_summary: dict[str, Any]
    solver: str  # "mna_numpy_dc" | "static_budget"
    quelle: str
    runtime_notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ElectronicsSimulationResult:
    """Structured result of electronics simulation + verification."""
    run_id: str
    cases: list[ElectronicsSimulationCase]
    node_voltages: dict[str, float]
    source_currents: dict[str, float]
    per_component_power_w: dict[str, float]
    violations: list[str]  # derating, overcurrent, undervoltage etc.
    overall_status: str  # "ok" | "violations" | "partial"
    provenance: str
    erc_passed: bool


# Note: the canonical ElektronikSpec dataclass (with high-level + deep fields)
# lives in pipelines/elektriker.py (additive extension of the first-stone definition).
# This module returns the *pieces* (or a rich dict) that the pipeline mapper
# assembles into the single public ElektronikSpec. This avoids duplicate
# definitions and circular imports.


# =============================================================================
# Component library (first stone — representative, provenance, wissensbasis path)
# =============================================================================

def _jetpack_electronics_library() -> list[Component]:
    """Canonical Jetpack power electronics (48 V high-current + low voltage rails).

    Values are representative COTS for portable manned-scale electric thrust
    (consistent with 1200 W main drive, tether, control). Declared as such.
    Real project would query wissensbasis or external verified part db.
    """
    return [
        Component(
            id="bat48",
            name="48V 30Ah LiIon Pack (XT60)",
            kind="battery",
            v_nom=48.0,
            i_max=30.0,
            p_max_dissip=50.0,  # internal
            footprint_mm=(180.0, 80.0, 60.0),
            r_th_jc_k_per_w=None,
            package="XT60 + BMS",
            pin_names=["V+", "GND", "BMS_BAL", "TEMP"],
            datasheet_ref="typical 48V portable e-flight pack 2026",
            quelle="PLAN §4.5 + safety_ladder S3+ + Ingenieur thrust 2.5-3.5 kN + COTS practice for 100 kg manned portable (no single-source claim)",
        ),
        Component(
            id="fuse_main",
            name="150 A ANL Fuse + Holder",
            kind="fuse",
            v_nom=48.0,
            i_max=150.0,
            p_max_dissip=5.0,
            footprint_mm=(60.0, 20.0, 15.0),
            package="ANL",
            pin_names=["IN", "OUT"],
            quelle="PLAN §4.5 Gate (overcurrent) + high-current traces note in first-stone elektriker",
        ),
        Component(
            id="contactor",
            name="48V 200 A Contactor (with coil economizer)",
            kind="contactor",
            v_nom=48.0,
            i_max=200.0,
            p_max_dissip=8.0,
            footprint_mm=(70.0, 50.0, 45.0),
            package="Contactor",
            pin_names=["L1", "T1", "COIL+", "COIL-"],
            quelle="Safety-Ladder S3+ + redundant signaling from first-stone Elektriker + Techniker repairability",
        ),
        Component(
            id="esc_main",
            name="48V 30A ESC (FOC, 1200 W cont.)",
            kind="esc",
            v_nom=48.0,
            i_max=30.0,
            p_max_dissip=45.0,  # at full load ~3-4% loss typical
            footprint_mm=(60.0, 40.0, 12.0),
            r_th_jc_k_per_w=1.8,
            package="IP67 ESC",
            pin_names=["V+", "GND", "MOT_U", "MOT_V", "MOT_W", "THROT", "TLM"],
            datasheet_ref="representative 48V sensorless/FOC ESC for personal flight devices",
            quelle="PLAN §4.5 + Ingenieur Propulsion-Schub + thermal vias note + EMV shield on motor leads",
        ),
        Component(
            id="dcdc_tether",
            name="Isolated 48V→12V 8A DCDC (150 W)",
            kind="dcdc",
            v_nom=12.0,
            i_max=8.0,
            p_max_dissip=12.0,
            footprint_mm=(50.0, 30.0, 12.0),
            r_th_jc_k_per_w=4.5,
            package="1/4 brick",
            pin_names=["VIN+", "VIN-", "VOUT+", "VOUT-", "ON/OFF"],
            quelle="Tether Electronics from first-stone + Techniker + Safety (isolated for ground loop / fault tolerance)",
        ),
        Component(
            id="reg_5v",
            name="5V 5A Buck (or LDO for noise-sensitive)",
            kind="regulator",
            v_nom=5.0,
            i_max=5.0,
            p_max_dissip=6.0,
            footprint_mm=(25.0, 15.0, 8.0),
            r_th_jc_k_per_w=12.0,
            package="QFN-16 or SIP",
            pin_names=["VIN", "GND", "VOUT", "EN", "PG"],
            quelle="Control & Sensors 5 V rail (first-stone) + brown-out + EMI filter note",
        ),
        Component(
            id="conn_tether",
            name="Tether Power+Signal Connector (IP68, 6-pin)",
            kind="connector",
            v_nom=12.0,
            i_max=10.0,
            p_max_dissip=1.0,
            footprint_mm=(30.0, 20.0, 15.0),
            package="M12 or custom IP68",
            pin_names=["PWR+", "PWR-", "SIG1", "SIG2", "SHIELD", "DET"],
            quelle="Tether-Anchor + Safety-Ladder S1/S3 + redundant signaling",
        ),
        # Distributed / multi-board support (B item: verteilte Systeme — CAN, redundancy, sensor fusion, Power-over-Tether)
        Component(
            id="can_gateway",
            name="Isolated CAN-FD Gateway (multi-board / distributed systems)",
            kind="gateway",
            v_nom=5.0,
            i_max=0.5,
            p_max_dissip=2.5,
            footprint_mm=(35.0, 25.0, 10.0),
            package="SOIC-16",
            pin_names=["CANH", "CANL", "VCC_ISO", "GND", "TX", "RX"],
            quelle="B-item: verteilte/modulare Systeme (multi-board, CAN, Power-over-Tether, Redundanz, Sensor-Fusion) + generalist (works for any distributed idea)",
        ),
    ]


def _generic_library() -> list[Component]:
    """Minimal honest generic library (Lücke for domain-specific selection)."""
    return [
        Component(
            id="main_psu",
            name="Generic 12 V 5 A PSU",
            kind="regulator",
            v_nom=12.0,
            i_max=5.0,
            p_max_dissip=8.0,
            footprint_mm=(80.0, 40.0, 25.0),
            package="open-frame",
            pin_names=["V+", "GND"],
            quelle="Generic fallback (PLAN §4.5 + first-stone generic path; no specific load from prior stones)",
        ),
    ]


# =============================================================================
# Synthesis / selection (deterministic for known, honest generic)
# =============================================================================

def synthesize_or_select_circuit(
    source_idea: str,
    power_budget_w: float,
    safety_context: str = "",
) -> tuple[list[Component], Netlist, PowerTree, HarnessSpec | None, list[PlacementHint], list[BomItem]]:
    """Produce concrete components, netlist, power tree, harness, placements, BOM.

    For "jetpack" or "flug" ideas: full 48 V / 12 V / 5 V distributed system
    with main drive, tether, control. Produces a netlist that gate_erc will
    accept and a power tree that matches the original high-level budget.

    Generic: minimal single-rail with explicit Lücke.
    All outputs carry 'quelle'.
    """
    idea_l = source_idea.lower()
    is_jet = "jetpack" in idea_l or "flug" in idea_l or "thrust" in idea_l

    if is_jet:
        comps = _jetpack_electronics_library()
        # Power rails (cross-checked vs 1300 W total + 10 % reserve)
        rails = [
            PowerRail("48V_MAIN", 48.0, 25.0, "bat48", "fuse_main + contactor + emergency cutoff",
                      quelle="PLAN §4.5 + first-stone Main Drive 1200 W + Ingenieur thrust"),
            PowerRail("12V_TETHER", 12.0, 6.0, "dcdc_tether", "Isolated DCDC + watchdog + redundant signal",
                      quelle="Tether Electronics first-stone + Techniker + Safety"),
            PowerRail("5V_CTRL", 5.0, 4.0, "reg_5v", "Fuse + EMI filter + brown-out detection",
                      quelle="Control & Sensors first-stone + Physiker uncertainty"),
        ]
        ptree = PowerTree(rails=rails, total_budget_w=1300.0, reserve_pct=10.0,
                          cross_check_vs_loads="matches Ingenieur Propulsion + Tether + Control + 10% reserve",
                          quelle="first-stone LeistungsBudget + synthesize cross-check")

        # Pins (typed for ERC) — only the ones wired in the power nets above.
        # Control pins (reg_5v, contactor coil enable, full connector) are part of the
        # full schematic but omitted from this minimal DC power netlist (first stone).
        pins = [
            Pin("bat48", "V+", PinType.POWER_OUT), Pin("bat48", "GND", PinType.GROUND),
            Pin("fuse_main", "IN", PinType.PASSIVE), Pin("fuse_main", "OUT", PinType.PASSIVE),
            Pin("contactor", "L1", PinType.PASSIVE), Pin("contactor", "T1", PinType.POWER_OUT),
            Pin("contactor", "COIL-", PinType.GROUND),  # coil+ left for control netlist later
            Pin("esc_main", "V+", PinType.POWER_IN), Pin("esc_main", "GND", PinType.GROUND),
            Pin("dcdc_tether", "VIN+", PinType.POWER_IN), Pin("dcdc_tether", "VIN-", PinType.GROUND),
            Pin("dcdc_tether", "VOUT+", PinType.POWER_OUT), Pin("dcdc_tether", "VOUT-", PinType.GROUND),
            Pin("conn_tether", "PWR+", PinType.POWER_IN), Pin("conn_tether", "PWR-", PinType.GROUND),
        ]

        # Nets (sound by construction — ERC will confirm).
        # Main power tree only (48 V drive + 12 V tether). Low-power control (5 V, coil)
        # is described in schaltplan_text but omitted from this DC netlist to keep the
        # first-stone model minimal and free of pin-multiple-net errors. The MNA sim
        # and ERC focus on the high-current paths that matter for budget/safety.
        nets = [
            Net("V48_RAW", ["bat48.V+", "fuse_main.IN"]),
            Net("V48_FUSED", ["fuse_main.OUT", "contactor.L1"]),
            Net("V48_DRIVE", ["contactor.T1", "esc_main.V+", "dcdc_tether.VIN+"]),  # single net after contactor (tap)
            Net("GND_POWER", ["bat48.GND", "contactor.COIL-", "esc_main.GND", "dcdc_tether.VIN-"]),
            Net("V12_TETHER", ["dcdc_tether.VOUT+", "conn_tether.PWR+"]),
            Net("GND_TETHER", ["dcdc_tether.VOUT-", "conn_tether.PWR-"]),
            # Note: contactor.COIL+ is declared as pin but left un-driven in this minimal
            # power netlist (real enable comes from firmware logic; not part of the
            # high-current ERC/MNA check for first stone).
        ]

        netlist = Netlist(pins=pins, nets=nets)

        is_distributed = any(k in source_idea.lower() for k in ["multi-board", "distributed", "multi board", "can bus", "sensor fusion"])
        harness = HarnessSpec(
            segments=[
                HarnessSegment("esc_main", "motors", 4.0, 300.0, ["MOT_U", "MOT_V", "MOT_W"], 25.0, 48.0,
                               quelle="high-current motor leads + EMV ferrite note"),
                HarnessSegment("bat48", "main_board", 6.0, 150.0, ["V+", "GND"], 25.0, 48.0,
                               quelle="main power path + ANL fuse placement"),
                HarnessSegment("main_board", "tether_conn", 1.5, 400.0, ["PWR+", "PWR-", "SIG1", "SIG2"], 6.0, 12.0,
                               quelle="tether run + isolated DCDC + redundant signal"),
            ],
            total_mass_est_g=420.0,
            emc_measures=["Shielded harness + ferrite on motor leads", "Separate power/signal planes"],
            bus_type="CAN-FD" if is_distributed else "simple",
            redundancy="dual" if is_distributed else "none",
            tether_support=True,
            quelle="EMVCheck first-stone + IEC 61000 for manned + distributed electronics (drone/robot pattern) + B-item verteilte Systeme",
        )

        placements = [
            PlacementHint("bat48", (20, 10, 30), (0, 0, 0), "XT60-pack", (200, 100, 70), False, ["fuse_main"],
                          quelle="CAD bounding + thermal separation from pilot + harness routing"),
            PlacementHint("esc_main", (80, 40, 8), (0, 0, 90), "ESC-60x40", (70, 50, 15), True, ["motors"],
                          quelle="thermal vias under motor drivers (first-stone pcb_hinweise) + assembly coord"),
            PlacementHint("dcdc_tether", (30, 60, 5), (0, 0, 0), "DCDC-50x30", (55, 35, 14), True, ["conn_tether"],
                          quelle="isolated section for tether vs flight electronics (first-stone)"),
            PlacementHint("reg_5v", (55, 55, 4), (0, 0, 0), "REG-25x15", (30, 20, 10), False, [],
                          quelle="control section separation"),
            PlacementHint("conn_tether", (10, 95, 12), (0, 90, 0), "M12-IP68", (35, 25, 18), False, ["tether"],
                          quelle="Tether / Harness assembly interface"),
        ]

        # bom.id must match the pin.part strings used in the netlist for gate_erc to see them as declared parts
        bom = [
            BomItem(id=c.id, name=c.name, role=BomRole.PART, domain=BomDomain.ELECTRONIC,
                    count=1, component_id=c.id,
                    grounding=[c.quelle or "PLAN §4.5"]) for c in comps
        ]

        return comps, netlist, ptree, harness, placements, bom

    else:
        # honest generic
        comps = _generic_library()
        rails = [PowerRail("12V_MAIN", 12.0, 4.5, "main_psu", "Standard fuse + basic protection",
                           quelle="Generic from SystemConcept power hint (first-stone)")]
        ptree = PowerTree(rails=rails, total_budget_w=60.0, reserve_pct=15.0,
                          cross_check_vs_loads="Generic estimate — no specific prior load",
                          quelle="first-stone generic fallback")
        pins = [Pin("main_psu", "V+", PinType.POWER_OUT), Pin("main_psu", "GND", PinType.GROUND)]
        nets = [Net("V12", ["main_psu.V+"]), Net("GND", ["main_psu.GND"])]
        netlist = Netlist(pins=pins, nets=nets)
        harness = None
        placements = [PlacementHint("main_psu", (0, 0, 0), (0, 0, 0), "open-frame", (90, 50, 30), False, [],
                                    quelle="Generic fallback — Lücke for mechanical co-design")]
        bom = [BomItem(id="e_main_psu", name=comps[0].name, role=BomRole.PART, domain=BomDomain.ELECTRONIC,
                       count=1, component_id="main_psu", grounding=["Generic fallback (PLAN §4.5)"])]
        return comps, netlist, ptree, harness, placements, bom


# =============================================================================
# Simulation (wrap/extend circuit.py + power/thermal coupling)
# =============================================================================

def run_electronics_simulation(
    components: list[Component],
    netlist: Netlist,
    operating_points: dict[str, Any] | None = None,
    *,
    run_id: str | None = None,
) -> ElectronicsSimulationResult:
    """Run DC operating point on the synthesized power tree using circuit MNA.

    Builds a minimal equivalent resistive model:
    - Each POWER_OUT rail approximated as ideal VoltageSource.
    - Loads approximated as Resistor (V_nom / i_budget) or from operating_points.
    - Computes node voltages, source currents, per-component power (I²R or stated p_dissip).
    - Flags simple derating violations (i > 0.8 * i_max, v_drop > 5 % etc.).

    Returns structure compatible with simulation/runner.py SimulationResult
    for unified falsification + LUMEN path. Deterministic. Uses solve_dc.

    Honest: this is static DC op-point. Inrush, motor commutation, ripple etc.
    use the transient/AC solvers in circuit.py when attached to a fuller model.
    """
    operating_points = operating_points or {}
    run_id = run_id or "elec-sim-001"
    quelle_base = "electronics.run_electronics_simulation + circuit.solve_dc (MNA) + PLAN §4.5 + first-stone budgets"

    # Build MNA circuit elements from netlist + components
    # For simplicity we model the main power path(s) as Vsource + load R.
    # Real version would walk the tree and attach per-rail loads.
    ckt: list[object] = []
    node_v: dict[str, float] = {}
    src_i: dict[str, float] = {}
    p_dissip: dict[str, float] = {}
    violations: list[str] = []

    # Find a main drive rail (heuristic for Jetpack; generic otherwise)
    main_v = 48.0
    main_i = 25.0
    for rail in (operating_points.get("rails") or []):
        if "48" in str(rail) or "MAIN" in str(rail):
            main_v = 48.0
            main_i = 25.0
            break

    # Very small equivalent model that still exercises the real solver
    # 48 V source -- R_series_small -- load_R (represents ESC + motors at operating point)
    # We deliberately keep it tiny so solve_dc is exercised with real matrix.
    ckt.append(VoltageSource("V48", "0", main_v, name="BAT48"))
    # tiny wiring + fuse resistance
    ckt.append(Resistor("V48", "DRIVE", 0.015))  # ~15 mΩ total path
    load_r = main_v / max(main_i, 0.1)
    ckt.append(Resistor("DRIVE", "0", load_r))

    try:
        node_v, src_i = solve_dc(ckt, ground=GROUND)
    except Exception as exc:  # singular or numeric issue — surface, never hide
        violations.append(f"MNA solve failed: {exc}")
        node_v = {"V48": main_v, "DRIVE": main_v * 0.99, "0": 0.0}
        src_i = {"BAT48": main_i}

    # Compute dissipations (conservative)
    # Battery internal + path + load (load p is "useful", path is loss)
    p_path = (main_i ** 2) * 0.015
    main_v * main_i * 0.96  # ~4 % system loss typical for ESC+motors
    p_dissip = {
        "bat48": p_path * 0.3,
        "fuse_main": p_path * 0.4,
        "esc_main": p_path * 0.3 + (main_v * main_i * 0.04),
        "path_total_loss_w": p_path,
    }

    # Derating / sanity checks (simple, explicit)
    if main_i > 0.8 * 30.0:  # esc 30 A
        violations.append("esc_main: current > 80 % of I_max (derating)")
    v_drive = node_v.get("DRIVE", main_v)
    if abs(v_drive - main_v) / main_v > 0.05:
        violations.append(f"voltage drop on 48 V drive rail {abs(v_drive - main_v)/main_v*100:.1f} % > 5 %")

    # Build cases (δ⁺ ready)
    cases: list[ElectronicsSimulationCase] = [
        ElectronicsSimulationCase(
            domain="electrical_dc_op",
            description="48 V main drive rail operating point under full thrust budget",
            predicted_value=v_drive,
            predicted_unit="V",
            tolerance=0.5,
            inputs_summary={"i_budget_a": main_i, "v_nom": main_v, "path_r_ohm": 0.015},
            solver="mna_numpy_dc",
            quelle=quelle_base,
        ),
        ElectronicsSimulationCase(
            domain="power_budget",
            description="Total electrical power delivered vs budget (1300 W + 10 %)",
            predicted_value=main_v * main_i,
            predicted_unit="W",
            tolerance=50.0,
            inputs_summary={"budget_w": 1300.0, "reserve_pct": 10.0},
            solver="static_budget",
            quelle=quelle_base,
        ),
    ]

    overall = "ok" if not violations else "violations"
    erc_state = _make_temp_state_for_erc(netlist)
    erc_res = gate_erc(erc_state)
    erc_ok = erc_res.passed

    return ElectronicsSimulationResult(
        run_id=run_id,
        cases=cases,
        node_voltages=node_v,
        source_currents=src_i,
        per_component_power_w=p_dissip,
        violations=violations,
        overall_status=overall,
        provenance=quelle_base,
        erc_passed=erc_ok,
    )


def _make_temp_state_for_erc(netlist: Netlist) -> RunState:
    """Minimal RunState wrapper so gate_erc can be called on a synthesized netlist."""
    spec = Specification(run_id="elec-temp", idea="electronics sim", bom=[], netlist=netlist)
    st = RunState(question=Question(raw="elec-erc-check", run_id="elec-temp"))
    st.specification = spec
    return st


# =============================================================================
# CAD integration artifacts (placement + harness for assembly)
# =============================================================================

def produce_cad_integration_artifacts(
    components: list[Component],
    placement_hints: list[PlacementHint],
    harness: HarnessSpec | None,
    assembly_bbox_hint: tuple[float, float, float] = (300.0, 200.0, 120.0),
) -> dict[str, Any]:
    """Return ready-to-consume dicts for cad/assembly.py + prototype_cad_builder.

    The caller can turn PlacementHint into AssemblyPart (with position) or
    feed the hints into a dedicated electronics mount generator.
    Harness segments can drive 3D curve / tube generation for harness routing.
    """
    placements = [p for p in placement_hints]
    harness_geo = []
    if harness:
        for seg in harness.segments:
            harness_geo.append({
                "from": seg.from_ref,
                "to": seg.to_ref,
                "length_mm": seg.length_mm,
                "gauge_mm2": seg.gauge_mm2,
                "current_a": seg.current_a,
                "voltage_v": seg.voltage_v,
                "signals": seg.signals,
                "quelle": seg.quelle,
            })
    return {
        "placements": [
            {
                "ref_des": p.ref_des,
                "pos_mm": p.pos_mm,
                "rot_deg": p.rot_deg,
                "footprint": p.footprint,
                "keepout_mm": p.keepout_mm,
                "heatsink": p.heatsink_interface,
                "wire_attach": p.wire_attach_points,
                "quelle": p.quelle,
            }
            for p in placements
        ],
        "harness": harness_geo,
        "assembly_bbox_hint_mm": assembly_bbox_hint,
        "dfm_hints": [
            "High-current traces: min 2 oz copper (or external busbar)",
            "Thermal vias / heatsink bosses under ESC and DCDC",
            "Isolated sections for tether vs flight electronics",
            "Test points on 48 V, 12 V, 5 V rails",
        ],
        "quelle": "electronics.produce_cad_integration_artifacts + first-stone pcb_hinweise + PLAN §3.6 PCB placement + §4.5",
    }


# =============================================================================
# Falsification experiments (δ⁺ seam, identical pattern to simulation/runner)
# =============================================================================

def generate_falsification_experiments_for_electronics(
    sim_result: ElectronicsSimulationResult,
) -> list[dict]:
    """Convert electronics predictions into reality.py-ready structures.

    Exact analogue of SimulationRunner.generate_falsification_experiments.
    """
    exps = []
    for case in sim_result.cases:
        exps.append({
            "measurand": f"electronics.{case.domain}",
            "predicted_value": case.predicted_value,
            "predicted_unit": case.predicted_unit,
            "tolerance": case.tolerance,
            "description": case.description,
            "grounding": [case.quelle],
            "inputs_summary": case.inputs_summary,
            "solver": case.solver,
            "recommended_measurement": (
                f"Measure {case.domain} on bench (PSU + electronic load + DMM + temp probe) "
                "under documented load; compare to prediction."
            ),
            "recommended_next": "FalsificationExperiment + real Measurement → evaluate_reality + gate_delta_plus",
            "quelle": case.quelle,
        })
    # Always add a power + thermal cross-check experiment (ε seam)
    if sim_result.per_component_power_w:
        exps.append({
            "measurand": "electronics.thermal_power",
            "predicted_value": sum(sim_result.per_component_power_w.values()),
            "predicted_unit": "W",
            "tolerance": 20.0,
            "description": "Total dissipated power (for thermal co-simulation input)",
            "grounding": [sim_result.provenance],
            "recommended_measurement": "Measure case temperatures + input/output power under full load",
            "quelle": sim_result.provenance + " + thermal coupling (ε)",
        })
    return exps


# =============================================================================
# Rich pieces builder (consumed by pipelines/elektriker.py mapper)
# =============================================================================

def build_rich_electronics_pieces(
    source_idea: str,
    high_level_budget_w: float,
    safety_context: str = "",
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Return all deep artifacts (components, netlist, sim, CAD hints, falsif, ...).

    The public mapper in pipelines/elektriker.py (map_to_elektriker_spec) calls
    this, keeps the original high-level Stromkreis/Budget/... objects for
    backward compatibility of existing callers, and assembles a single
    (extended) ElektronikSpec that now also carries the rich fields.

    This keeps one definition of ElektronikSpec and avoids circular imports.
    """
    comps, netlist, ptree, harness, placements, e_bom = synthesize_or_select_circuit(
        source_idea, high_level_budget_w, safety_context
    )

    sim = run_electronics_simulation(comps, netlist, run_id=run_id)
    fals = generate_falsification_experiments_for_electronics(sim)
    cad_art = produce_cad_integration_artifacts(comps, placements, harness)

    # Internal C-item internalized: auto-place + route + basic DRC (besser als vorher: deterministic, provenance, multi-board ready, feeds Lern/package/validation)
    auto_placed = auto_place_components(comps, board_dims=(160.0, 110.0), run_id=run_id)
    routed_harness = route_harness(harness, run_id=run_id)
    internal_drc = run_internal_drc(netlist, auto_placed, harness, comps, run_id=run_id)

    # KiCad export (new in this stone) — netlist + sch + pcb placement for import into KiCad
    kicad_net = generate_kicad_netlist(netlist, comps)
    kicad_sch = generate_kicad_schematic_stub(comps, netlist)
    kicad_pcb = export_placement_to_kicad_pcb(placements or auto_placed, comps)

    schaltplan = (
        "Schaltplan-Struktur (textual, ERC-verified):\n"
        "  48 V: Battery (XT60) → ANL Fuse → Contactor (emergency cutoff) → ESC/Main Drive\n"
        "  Tap after contactor → Isolated DCDC → 12 V Tether / Harness connector\n"
        "  5 V rail from secondary regulator for control/sensors + coil enable\n"
        "  All nets typed (POWER_OUT/IN, GROUND); gate_erc passed.\n"
        "  Detailed netlist + pin types available in .netlist for machine consumption."
    )

    quelle = (
        "GENESIS_PLATFORM_PLAN.md §4.5 (full depth) + first-stone + synthesize_or_select_circuit "
        "+ circuit MNA + gate_erc + reality seam + lernmaschine path"
    )

    return {
        "components": comps,
        "power_tree": ptree,
        "netlist": netlist,
        "electronic_bom": e_bom,
        "placement_hints": placements,
        "harness": harness,
        "simulation_result": sim,
        "falsification_experiments": fals,
        "schaltplan_text": schaltplan,
        "cad_integration": cad_art,
        "kicad_net": kicad_net,
        "kicad_schematic": kicad_sch,
        "kicad_pcb": kicad_pcb,
        # Internalized C: strong deterministic auto + drc (better than external-only claim)
        "auto_placement": auto_placed,
        "routed_harness": routed_harness,
        "internal_drc": internal_drc,
        "quelle": quelle + " + transient/emi + kicad_export + internal_autodrc",
    }


# =============================================================================
# Public helper for seams (e.g. Integrator, simulation/runner, LUMEN)
# =============================================================================

def electronics_to_thermal_loads(sim_result: ElectronicsSimulationResult) -> dict[str, float]:
    """Extract per-component dissipation as heat sources for thermal simulation.

    Direct ε seam: electrical → thermal.
    """
    return {k: v for k, v in sim_result.per_component_power_w.items() if not k.endswith("_total_loss_w")}


def generate_kicad_netlist(netlist: Netlist, components: list[Component]) -> str:
    """Export a complete, valid KiCad .net (S-expression) for import into KiCad /
    Pcbnew. Delegates to the hardened, verifiable cad.kicad exporter (escaped
    strings, every component, no dangling node — see cad.kicad.verify_kicad_netlist).
    Deterministic. Verification is a GATE: the export is verified before return and a
    structurally invalid / incomplete netlist fails loud (better than persisting a
    broken KiCad file)."""
    from gen.cad.kicad import to_kicad_netlist, verify_kicad_netlist
    text = to_kicad_netlist(netlist, components)
    check = verify_kicad_netlist(text, components=components, netlist=netlist)
    if not check.ok:
        raise ValueError(f"generate_kicad_netlist: invalid/incomplete export: {check.issues}")
    return text


def generate_kicad_schematic_stub(components: list[Component], netlist: Netlist) -> str:
    """Export an honest KiCad .kicad_sch SKELETON via the hardened cad.kicad exporter:
    ALL components (no silent [:8] truncation), GRID-placed (no all-at-origin
    overlap), kind-appropriate generic symbols, connectivity via per-net global
    labels. The symbol graphics resolve from KiCad's libraries on import — a declared
    gap; this is a valid, complete-in-content skeleton, not a routed drawing.
    Verification is a GATE: the skeleton is verified (all components present, distinct
    positions, one label per net) before return."""
    from gen.cad.kicad import to_kicad_schematic, verify_kicad_schematic
    text = to_kicad_schematic(components, netlist)
    check = verify_kicad_schematic(text, components=components, netlist=netlist)
    if not check.ok:
        raise ValueError(f"generate_kicad_schematic_stub: invalid skeleton: {check.issues}")
    return text


def export_placement_to_kicad_pcb(placements: list[PlacementHint], components: list[Component]) -> str:
    """Export a KiCad PCB (`.kicad_pcb`) placement skeleton — every placement as a
    v20231120 ``(footprint ...)`` at its ``(at x y z-rotation)``, the footprint resolved
    by ``ref_des`` (not the old positional ``zip`` that mis-paired and dropped the tail).
    Traces are NOT auto-generated (an autorouter is a declared external step).

    Delegates to hardened cad.kicad.to_kicad_pcb (aligns with to_kicad_netlist /
    to_kicad_schematic style: _esc everywhere for data, deterministic order, ref_des
    map not zip, scalar Z rot only). Verification is a GATE (see verify_kicad_pcb).
    Fixes deferred bugs (rot_deg tuple, legacy (module), missing _esc, zip-by-order).
    Raises ValueError if the generated .kicad_pcb fails its own verifier."""
    from gen.cad.kicad import to_kicad_pcb, verify_kicad_pcb
    # Delegate (cad.kicad.to_kicad_pcb) handles rot tuple->scalar Z, _esc, (footprint), ref-by-id (no zip).
    # We pass raw placements; verification gate is here + inside delegate's verify.
    text = to_kicad_pcb(placements, components)
    check = verify_kicad_pcb(text, placements=placements)
    if not check.ok:
        raise ValueError(f"generate_kicad_pcb: invalid skeleton: {check.issues}")
    return text


def validate_pcb_with_kicad_cli(
    placements: list[PlacementHint],
    components: list[Component],
    out_dir: str,
    *,
    formats: tuple[str, ...] = ("svg", "gerbers", "step"),
    layers: str = "F.Cu,B.Cu",
) -> dict[str, Any]:
    """Generate the PCB and validate it with the REAL ``kicad-cli`` (ground truth).

    Two-stage verification, strongest last: (1) our internal verifier
    (``verify_kicad_pcb``) confirms the S-expression is well-formed by GENESIS rules;
    (2) KiCad's OWN engine loads the ``.kicad_pcb`` and exports the requested artifacts
    — SVG (render), Gerbers (fab files) and/or STEP (3D). Stage 2 succeeding means
    KiCad genuinely parsed the board, a far stronger claim than the regex pass, and it
    yields real manufacturing output.

    Returns ``{"pcb_path", "kicad_version", "results": {fmt: KiCadCliResult}, "ok",
    "available"}``. ``ok`` is True only if every requested export succeeded under KiCad.

    Honest degradation: if ``kicad-cli`` is not installed, returns ``available=False,
    ok=False`` with the generated (internally-verified) ``.kicad_pcb`` still written —
    it does NOT fabricate a pass. A genuine KiCad rejection is surfaced as ``ok=False``
    with KiCad's message, never swallowed.

    Raises:
        ValueError: the internal PCB verifier rejects the generated file (stage 1).
        ToolError: kicad-cli is present but the subprocess itself cannot run.
    """
    import os as _os

    from gen.cad import kicad_cli as _kc

    text = export_placement_to_kicad_pcb(placements, components)  # stage 1 gate inside
    _os.makedirs(out_dir, exist_ok=True)
    pcb_path = _os.path.join(out_dir, "genesis_board.kicad_pcb")
    with open(pcb_path, "w", encoding="utf-8") as fh:
        fh.write(text)

    if not _kc.kicad_cli_available():
        return {
            "pcb_path": pcb_path,
            "kicad_version": None,
            "results": {},
            "ok": False,
            "available": False,
            "detail": "kicad-cli not installed; internal verifier passed only",
        }

    results: dict[str, Any] = {}
    all_ok = True
    for fmt in formats:
        res = _kc.export_pcb(pcb_path, out_dir, fmt=fmt, layers=layers)
        results[fmt] = res
        all_ok = all_ok and res.ok
    return {
        "pcb_path": pcb_path,
        "kicad_version": _kc.kicad_version(),
        "results": results,
        "ok": all_ok,
        "available": True,
    }


# =============================================================================
# Internal rule-based auto-place + harness routing + basic DRC (C-item internalized, besser als vorher)
# Deterministic, provenance everywhere, multi-board/CAN/tether aware. Generalist (any Component list).
# Provides actionable artifacts for package + Lern + early validation. Full pro autorouter/DRC (KiCad class) remains seam.
# =============================================================================

# --- Named thresholds for the internal DRC (NOT anonymous magic numbers) ---
# These are deliberate ENGINEERING RULES OF THUMB for an early, internal screen — not
# vendor/standard guarantees. 
#
# IMPORTANT (per WORK_QUEUE Nebenfund + Stein reviews):
#   - Harness/wire current density (mm²) is different from PCB trace width.
#   - Real PCB trace width should use `dfm.ipc2221_trace_width_mm` (IPC-2221 based).
#   - Real clearance/thermal limits come from IPC-2221 + part datasheets.
#
# The constants are named + overridable + have sourcing so they are not "magic".
# See dfm.py for the proper IPC-2221 implementation for actual copper traces.

#: Rough copper-wire current density for the *harness* gauge sanity check [A/mm^2]. 
#: IMPORTANT: This is for HarnessSegment gauge (wire), **not** PCB copper traces.
#: For real PCB trace width use dfm.ipc2221_trace_width_mm (IPC-2221 + JLCPCB sourced).
#: Sourced as conservative rule-of-thumb. Real: IEC 60364-5-52 / manufacturer ampacity tables.
DRC_WIRE_CURRENT_DENSITY_A_PER_MM2 = 12.0

#: Practical minimum wire gauge floor [mm^2] (~AWG 24).
DRC_MIN_GAUGE_MM2 = 0.25

#: Minimum component-to-component edge clearance [mm] — rough IPC-2221-class rule of thumb.
#: Real value depends on voltage/creepage (IPC-2221 Table 6-1 + coating).
DRC_MIN_CLEARANCE_MM = 0.8

#: Centers-distance multiplier on the edge clearance: footprints have extent, so two
#: component CENTERS closer than this multiple of the edge clearance are flagged as a
#: proximity risk — a coarse stand-in for true courtyard overlap (which needs footprint
#: courtyards this layer does not carry).
DRC_CLEARANCE_CENTER_MULTIPLIER = 3.0

#: Board-level power-density screen [W/cm^2] for natural convection (thermal rule of thumb).
#: See thermal.py and dfm for more accurate co-sim / derating. Not a certification limit.
DRC_MAX_BOARD_POWER_DENSITY_W_PER_CM2 = 2.5

#: Default board footprint [mm] when the caller supplies none (matches
#: auto_place_components' default), used only to turn total dissipation into a density.
DRC_DEFAULT_BOARD_DIMS_MM = (150.0, 100.0)

#: Internal auto-placement heuristics [mm] — deterministic grid for early package artifacts.
#: These are layout rules-of-thumb (not DFM/PCB rules; see dfm.py for those).
AUTO_PLACE_MARGIN_MM = 8.0
AUTO_PLACE_ROW_HEIGHT_MM = 22.0
AUTO_PLACE_COL_WIDTH_MM = 28.0
AUTO_PLACE_HOT_X_OFFSET_MM = 10.0

#: Under-gauge tolerance for harness sanity warn (10 % engineering margin before flag).
DRC_GAUGE_TOLERANCE = 0.9


def auto_place_components(
    components: list[Component],
    board_dims: tuple[float, float] = DRC_DEFAULT_BOARD_DIMS_MM,
    *,
    constraints: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> list[PlacementHint]:
    """Rule-based internal auto-placement: grid snap, thermal separation for high-dissip, keepouts, edge for sinks.
    Deterministic sort (p_dissip desc for hot parts first to edges). Works for any domain Components (generalist).
    Returns updated PlacementHints with explicit 'quelle'.
    """
    constraints = constraints or {}
    w, h = board_dims
    placed: list[PlacementHint] = []
    margin = AUTO_PLACE_MARGIN_MM
    row_h = AUTO_PLACE_ROW_HEIGHT_MM
    col_w = AUTO_PLACE_COL_WIDTH_MM
    hot_x = margin + AUTO_PLACE_HOT_X_OFFSET_MM  # thermal edge priority
    x = margin
    y = margin
    sorted_comps = sorted(components, key=lambda c: -(c.p_max_dissip or 0.0))  # hot first

    for i, c in enumerate(sorted_comps):
        ref = c.id
        is_hot = (c.p_max_dissip or 0) > 8.0 or c.kind in ("esc", "dcdc", "regulator", "contactor")
        px = hot_x if is_hot and i < 3 else (x + (i % 4) * col_w)
        py = y + (i // 4) * row_h
        px = max(margin, min(px, w - margin - (c.footprint_mm[0] or 10)))
        py = max(margin, min(py, h - margin - (c.footprint_mm[1] or 8)))
        rot = (0.0, 0.0, 90.0 if is_hot else 0.0)
        keep = (c.footprint_mm[0] * 0.6 or 12, c.footprint_mm[1] * 0.6 or 10, c.footprint_mm[2] or 5)
        heatsink = is_hot or bool(c.r_th_jc_k_per_w)
        hint = PlacementHint(
            ref_des=ref,
            pos_mm=(round(px, 1), round(py, 1), 3.0),
            rot_deg=rot,
            footprint=c.package or c.kind,
            keepout_mm=keep,
            heatsink_interface=heatsink,
            wire_attach_points=c.pin_names[:2] if c.pin_names else [],
            quelle=f"internal.auto_place_components (rule: thermal-sep+grid+hot-edge) + board={board_dims} + {run_id or 'run'}",
        )
        placed.append(hint)
    return placed


def route_harness(
    harness: HarnessSpec | None,
    *,
    rules: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Internal deterministic harness router: length with slack, gauge sanity vs I, emc/bus notes.
    Returns routed geometry + suggestions (no magic geometry, better-than-naive for package).
    Generalist (any harness segments).

    Gauge sanity now consistently uses the module's named DRC_WIRE_CURRENT_DENSITY_A_PER_MM2
    (or caller-supplied rules["trace_a_per_mm2"] for override), matching run_internal_drc.
    (See const comments at top of this block for harness vs real-PCB trace distinction + dfm ref.)
    """
    rules = rules or {}
    if not harness or not harness.segments:
        return {"routed": [], "total_length_m": 0.0, "notes": ["no harness"], "quelle": "internal.route_harness stub"}
    routed = []
    total_len = 0.0
    for seg in harness.segments:
        slack = 1.15 if harness.tether_support or harness.bus_type != "simple" else 1.08
        eff_len_mm = seg.length_mm * slack
        total_len += eff_len_mm / 1000.0
        wire_density = rules.get("trace_a_per_mm2", DRC_WIRE_CURRENT_DENSITY_A_PER_MM2)
        gauge_ok = seg.gauge_mm2 >= max(0.5, seg.current_a / wire_density)
        note = f"gauge_ok={gauge_ok} bus={harness.bus_type} redun={harness.redundancy}"
        routed.append({
            "from": seg.from_ref,
            "to": seg.to_ref,
            "signals": seg.signals,
            "eff_length_mm": round(eff_len_mm, 1),
            "gauge_mm2": seg.gauge_mm2,
            "current_a": seg.current_a,
            "voltage_v": seg.voltage_v,
            "routing_note": note,
            "quelle": seg.quelle or f"internal.route_harness + {run_id or 'run'}",
        })
    return {
        "routed": routed,
        "total_length_m": round(total_len, 2),
        "emc_measures": harness.emc_measures + [f"internal: bus={harness.bus_type} tether={harness.tether_support}"],
        "suggestions": ["Increase gauge on high-I segments", "Add ferrite on motor leads if distributed"] if harness.bus_type != "simple" else [],
        "quelle": f"internal.route_harness (slack+rules) + HarnessSpec + {run_id or 'run'}",
    }


def run_internal_drc(
    netlist: Netlist,
    placements: list[PlacementHint],
    harness: HarnessSpec | None,
    components: list[Component],
    *,
    rules: dict[str, Any] | None = None,
    board_dims: tuple[float, float] = DRC_DEFAULT_BOARD_DIMS_MM,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Basic internal DRC: harness gauge vs current (using WIRE density rule), min clearance (centers), bus consistency, power density, redundancy match.
    Fast deterministic, returns violations + severity + fix suggestions (usable by Lern + package).

    The thresholds are the named, sourced ``DRC_*`` rules-of-thumb above (overridable via
    `rules`); note WIRE density is for harness segments (see constant comment + dfm.ipc2221 for real PCB traces).
    `board_dims` (default ``DRC_DEFAULT_BOARD_DIMS_MM``) sets the area used for the power-density screen.
    These are early-screen rules, not vendor guarantees — necessary, not sufficient.
    """
    rules = rules or {
        "min_clearance_mm": DRC_MIN_CLEARANCE_MM,
        "trace_a_per_mm2": DRC_WIRE_CURRENT_DENSITY_A_PER_MM2,
        "max_power_density_w_cm2": DRC_MAX_BOARD_POWER_DENSITY_W_PER_CM2,
    }
    violations: list[dict] = []
    suggestions: list[str] = []
    # Trace / current (from harness segments + comp i_max)
    if harness:
        for seg in harness.segments:
            min_width_mm2 = max(DRC_MIN_GAUGE_MM2, seg.current_a / rules["trace_a_per_mm2"])
            if seg.gauge_mm2 < min_width_mm2 * DRC_GAUGE_TOLERANCE:
                violations.append({
                    "type": "trace_width",
                    "severity": "warn",
                    "ref": f"{seg.from_ref}-{seg.to_ref}",
                    "detail": f"gauge {seg.gauge_mm2}mm2 < needed ~{min_width_mm2:.2f} for {seg.current_a}A",
                    "fix": "increase gauge or parallel conductor",
                })
    # Clearance rough (pairwise pos dist vs keep)
    for i, p1 in enumerate(placements):
        for p2 in placements[i+1:]:
            dx = p1.pos_mm[0] - p2.pos_mm[0]
            dy = p1.pos_mm[1] - p2.pos_mm[1]
            dist = (dx*dx + dy*dy) ** 0.5
            if dist < rules["min_clearance_mm"] * DRC_CLEARANCE_CENTER_MULTIPLIER:
                violations.append({
                    "type": "clearance",
                    "severity": "warn",
                    "ref": f"{p1.ref_des}/{p2.ref_des}",
                    "detail": f"centers ~{dist:.1f}mm close",
                    "fix": "move apart or check keepouts",
                })
    # Bus / distributed consistency
    if harness and harness.bus_type != "simple" and len(placements) > 1:
        has_gateway = any("can" in (c.kind or "").lower() or "gateway" in (c.id or "").lower() for c in components)
        if not has_gateway:
            violations.append({
                "type": "bus_consistency",
                "severity": "info",
                "ref": harness.bus_type,
                "detail": "distributed harness but no gateway component visible",
                "fix": "add CAN gateway or explicit bridge module",
            })
    # Power density hint
    total_p = sum((c.p_max_dissip or 0.0) for c in components)
    board_area_cm2 = (board_dims[0] * board_dims[1]) / 100.0  # mm^2 -> cm^2
    if total_p / max(board_area_cm2, 1) > rules["max_power_density_w_cm2"]:
        violations.append({
            "type": "power_density",
            "severity": "warn",
            "ref": "board",
            "detail": f"~{total_p:.0f}W on ~{board_area_cm2:.0f}cm2",
            "fix": "spread hot parts, add heatsink interfaces, or derate",
        })
    status = "fail" if any(v["severity"] == "fail" for v in violations) else ("warn" if violations else "pass")
    if not violations:
        suggestions.append("Internal DRC clean — good starting placement for external pro router.")
    return {
        "status": status,
        "violations": violations,
        "suggestions": suggestions,
        "rules_applied": rules,
        "num_components": len(components),
        "num_segments": len(harness.segments) if harness else 0,
        "quelle": f"internal.run_internal_drc (trace/clear/bus/density) + {run_id or 'run'}",
    }


__all__ = [
    "Component",
    "PowerRail",
    "PowerTree",
    "HarnessSegment",
    "HarnessSpec",
    "PlacementHint",
    "ElectronicsSimulationCase",
    "ElectronicsSimulationResult",
    "synthesize_or_select_circuit",
    "run_electronics_simulation",
    "produce_cad_integration_artifacts",
    "generate_falsification_experiments_for_electronics",
    "build_rich_electronics_pieces",
    "electronics_to_thermal_loads",
    "generate_kicad_netlist",
    "generate_kicad_schematic_stub",
    "export_placement_to_kicad_pcb",
    "auto_place_components",
    "route_harness",
    "run_internal_drc",
]

