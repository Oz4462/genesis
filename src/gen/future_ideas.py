"""future_ideas — five forward-looking engineering ideas run end-to-end through GENESIS.

Each function returns a complete, GATED ``Specification`` for a different future-facing product, so
``pipeline.assess_specification`` fires the relevant δ-physics axes and ``bundle.emit_bundle`` writes
real artifacts (printable STL parts, a build manual, a BOM split into printed vs bought). They are the
deterministic stand-in for the live-LLM architect (owner-gated until GENESIS is finished): authored,
not generated, but run through the SAME gated machinery as every other spec — an honest physics
verdict, never a masked pass.

The five (deliberately diverse domains + signature axis clusters):
  1. delivery_drone_spec   — autonomous last-mile eVTOL: the FLIGHT axes (rotor hover, battery
     endurance, ESC/battery current, attitude PD) + a load-bearing printed arm.
  2. home_battery_spec      — modular home energy-storage wall: the energy/current axes (general
     power math, honestly not "flight") + an enclosure bracket.
  3. harvest_arm_spec       — vertical-farming harvesting arm: kinematics (2R reach) + electric
     actuator sizing + onboard vision COMPUTE + a structural link.
  4. hydraulic_boom_spec    — autonomous construction actuator module: the HYDRAULIC axes (cylinder
     force, pump flow) + reach + a structural boom.
  5. exo_knee_spec          — assistive exoskeleton knee: electric actuator + kinematics + swing
     dynamics (inverse-dynamics torque over the gait) + a printed brace.

Deterministic, offline, no LLM. No trading/ASYA/MT5. Language contract per demo.py (German prose;
English ids/units/measurands). Reuses demo.py's quantity/claim helpers — the single spec-data layer.
"""

from __future__ import annotations

from .core.state import (
    BomDomain,
    BomItem,
    BomRole,
    Component,
    Constraint,
    Decision,
    GeometryNode,
    Sourcing,
    Specification,
    Step,
)
from .demo import _claim, _d, _der, _dm, _g, _gm
from .dfm import FDM_MIN_HOLE_DIAMETER_MM, FDM_NOZZLE_DIAMETER_MM, FDM_WALL_PERIMETERS_MIN, min_wall_formula
from .mechanics_formulas import rod_inertia_about_end
from .structural import (
    STANDARD_GRAVITY,
    STRESS_CONCENTRATION_CIRCULAR_HOLE,
    cantilever_bending_stress_formula,
    peak_stress_formula,
    weight_formula,
)


def _link(sx, sy, sz, r1, off1, r2, off2) -> GeometryNode:
    """A printed structural link: a box minus two through-bores at ±x ends (all args are quantity-ids)."""
    return GeometryNode(kind="difference", children=[
        GeometryNode(kind="box", params={"size_x": sx, "size_y": sy, "size_z": sz}),
        GeometryNode(kind="translate", params={"x": off1, "y": "q_zero", "z": "q_zero"},
                     children=[GeometryNode(kind="cylinder", params={"radius": r1, "height": sz})]),
        GeometryNode(kind="translate", params={"x": off2, "y": "q_zero", "z": "q_zero"},
                     children=[GeometryNode(kind="cylinder", params={"radius": r2, "height": sz})]),
    ])


def _dfm_quantities() -> list:
    """The shared FDM printability quantities (nozzle, perimeters, min wall/hole) every printed spec
    carries, plus the zero-offset used by every bore."""
    return [
        _d("q_zero", "Null-Versatz", 0.0, "mm", "y/z-Versatz der Bohrungen (mittig)"),
        _g("q_nozzle", "FDM-Düsendurchmesser", FDM_NOZZLE_DIAMETER_MM, "mm", ["c_fdm_nozzle"]),
        _g("q_perimeters", "Mindestzahl Wand-Perimeter", FDM_WALL_PERIMETERS_MIN, "1", ["c_fdm_wall"]),
        _der("q_min_wall", "kleinste druckbare Wanddicke",
             FDM_WALL_PERIMETERS_MIN * FDM_NOZZLE_DIAMETER_MM, "mm",
             min_wall_formula("q_nozzle", "q_perimeters"), ("q_nozzle", "q_perimeters")),
        _g("q_min_hole", "kleinster druckbarer Lochdurchmesser", FDM_MIN_HOLE_DIAMETER_MM, "mm",
           ["c_fdm_hole"]),
    ]


def _dfm_claims() -> list:
    return [
        _claim("c_gravity", "Die Normfallbeschleunigung ist definiert als 9.80665 m/s^2."),
        _claim("c_pla", "FDM-gedrucktes PLA, in der Druckebene belastet, hat eine Zugfestigkeit "
               "von etwa 50 MPa."),
        _claim("c_kirsch", "Ein kreisrundes Loch in einer Platte unter Zug hat einen "
               "Spannungskonzentrationsfaktor von 3 (Kirsch-Lösung)."),
        _claim("c_fdm_nozzle", "Eine Standard-FDM-Düse hat 0.4 mm Durchmesser."),
        _claim("c_fdm_wall", "Eine FDM-Wand sollte mindestens 2 Perimeterlinien breit sein."),
        _claim("c_fdm_hole", "Das kleinste zuverlässig druckbare horizontale Loch im FDM-Druck hat "
               "2.0 mm Durchmesser."),
    ]


def _struct_quantities(force_n: float, arm_mm: float, b_mm: float, h_mm: float) -> list:
    """The shared cantilever-bending statics on a printed load-bearing link: nominal + peak stress at
    a bore vs PLA strength (the σ-constraint), plus the PLA strength/density."""
    sigma_nom = 6.0 * force_n * arm_mm / (b_mm * h_mm * h_mm)
    return [
        _g("q_strength", "PLA-Zugfestigkeit in der Druckebene", 50.0, "MPa", ["c_pla"]),
        _d("q_density", "PLA-Dichte", 0.00124, "g/mm^3", "PLA ~1.24 g/cm³, je mm³"),
        _g("q_kt", "Spannungskonzentrationsfaktor (kreisrundes Loch, Kirsch)",
           STRESS_CONCENTRATION_CIRCULAR_HOLE, "1", ["c_kirsch"]),
        _der("q_sigma_nom", "nominale Biegespannung (Kragarm)", sigma_nom, "MPa",
             cantilever_bending_stress_formula("q_force", "q_arm", "q_b", "q_h"),
             ("q_force", "q_arm", "q_b", "q_h")),
        _der("q_sigma_peak", "Spitzenspannung am Loch",
             STRESS_CONCENTRATION_CIRCULAR_HOLE * sigma_nom, "MPa",
             peak_stress_formula("q_sigma_nom", "q_kt"), ("q_kt", "q_sigma_nom")),
    ]


# ============================================================================================
# 1. Autonomous last-mile delivery drone — the FLIGHT axes
# ============================================================================================

def delivery_drone_claims() -> list:
    return _dfm_claims() + [
        _claim("c_drone", "Ein Quadrocopter erzeugt seinen Schub mit vier Rotoren; eine sichere "
               "Auslegung hat ein Schub-Gewicht-Verhältnis von mindestens 2."),
        _claim("c_bldc", "Ein Drohnen-BLDC-Motor mit 10-Zoll-Propeller liefert je ~15 N Schub."),
        _claim("c_lipo6s", "Ein 6S-LiPo (22.2 V) mit 25C-Entladung speist Antrieb und Avionik."),
    ]


def delivery_drone_spec() -> Specification:
    """Eine autonome urbane Paket-Lieferdrohne (Quadrocopter): die vier Flug-Closed-Forms
    (Rotor-Schwebe/Impulstheorie, Akku-Flugzeit, ESC/Akku-Strombudget, PD-Lageregelungs-Dämpfung)
    plus ein lasttragender gedruckter Motorausleger. Die Flug-Achsen, die nichts sonst nutzt."""
    arm_force = 15.0  # per-rotor thrust [N] bends the arm as a cantilever at the motor mount
    quantities = [
        *_dfm_quantities(),
        *_struct_quantities(arm_force, 180.0, 25.0, 12.0),
        _d("q_force", "Schub am Motorende (Auslegerlast)", arm_force, "N", "Rotorschub je Arm"),
        _d("q_arm", "Biege-Hebelarm Ausleger", 180.0, "mm", "Nabe→Motor"),
        _d("q_b", "Auslegerbreite / size_y", 25.0, "mm", "Breite b"),
        _d("q_h", "Auslegerhöhe / size_z", 12.0, "mm", "Höhe h"),
        _d("q_arm_x", "Auslegerlänge / size_x", 200.0, "mm", "Nabe→Motor + Überstand"),
        _d("q_motor_bore", "Motorbohrungsradius", 4.0, "mm", "M8-Motorwelle/Schraubbild"),
        _d("q_hub_bore", "Nabenbohrungsradius", 4.0, "mm", "Verschraubung an der Nabe"),
        _d("q_off_p", "Bohrungsversatz +", 90.0, "mm", "+x Motor"),
        _d("q_off_n", "Bohrungsversatz -", -90.0, "mm", "-x Nabe"),
        # flight: rotor hover (momentum theory)
        _dm("q_mass", "Abflugmasse", 2.5, "kg", "Drohne + Paket", "vehicle.mass"),
        _dm("q_disk", "Rotor-Kreisfläche", 0.0531, "m^2", "10-Zoll-Prop, r=0.13 m", "rotor.disk_area"),
        _dm("q_nrot", "Rotorzahl", 4.0, "1", "Quadrocopter", "rotor.count"),
        _gm("q_thrust", "max. Gesamtschub", 60.0, "N", ["c_bldc"], "rotor.max_total_thrust"),
        # flight: battery endurance
        _dm("q_cap_wh", "Akkukapazität", 100.0, "Wh", "6S 4.5 Ah", "battery.capacity"),
        _dm("q_hover_w", "Schwebeleistung", 240.0, "W", "Impulstheorie + FoM 0.7", "flight.hover_power"),
        _dm("q_endur", "geforderte Flugzeit", 15.0, "min", "Liefermission", "flight.required_endurance"),
        # flight: current budget (ESC + battery C)
        _dm("q_pmax", "Spitzenleistung", 600.0, "W", "Vollgas-Steigflug", "flight.max_power"),
        _gm("q_volt", "Akkuspannung", 22.2, "V", ["c_lipo6s"], "battery.voltage"),
        _dm("q_esc", "ESC-Stromgrenze", 40.0, "A", "je Motor 4-in-1-ESC", "esc.current_limit"),
        _dm("q_cap_ah", "Akkukapazität", 4.5, "Ah", "6S", "battery.capacity_ah"),
        _gm("q_crate", "Akku-C-Rating", 25.0, "1", ["c_lipo6s"], "battery.c_rating"),
        # flight: attitude PD damping
        _dm("q_Ivehicle", "Roll-/Nick-Trägheit", 0.05, "kg*m^2", "um die Roll-Achse",
            "vehicle.attitude_inertia"),
        _dm("q_kp", "Lageregler P-Verstärkung", 2.0, "N*m", "Proportional", "control.attitude_kp"),
        _dm("q_kd", "Lageregler D-Verstärkung", 0.4, "N*m*s", "Differential", "control.attitude_kd"),
    ]
    arm_geom = _link("q_arm_x", "q_b", "q_h", "q_hub_bore", "q_off_n", "q_motor_bore", "q_off_p")
    components = [
        Component(id="c_arm", name="Motorausleger", geometry=arm_geom,
                  quantity_ids=["q_arm_x", "q_b", "q_h", "q_hub_bore", "q_motor_bore",
                                "q_off_p", "q_off_n", "q_zero"], material_density="q_density"),
    ]
    bom = [
        BomItem(id="b_arm", name="Motorausleger (gedruckt)", role=BomRole.PART, count=4,
                component_id="c_arm", domain=BomDomain.MECHANICAL, grounding=["c_drone"]),
        BomItem(id="b_motor", name="BLDC-Antriebsmotor + 10-Zoll-Propeller", role=BomRole.PART,
                count=4, domain=BomDomain.MECHANICAL, grounding=["c_bldc"]),
        BomItem(id="b_esc", name="4-in-1-ESC (40 A)", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC),
        BomItem(id="b_fc", name="Flight-Controller + GNSS + IMU", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC),
        BomItem(id="b_batt", name="6S-LiPo 4.5 Ah (25C)", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC, grounding=["c_lipo6s"]),
        BomItem(id="b_hook", name="Paket-Abwurfhaken (Servo)", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC),
        BomItem(id="b_printer", name="3D-Drucker", role=BomRole.TOOL, count=1),
    ]
    steps = [
        Step(id="s1", index=1, action="Vier Motorausleger drucken.", uses=["b_printer"],
             inputs=["b_arm"], outputs=["a_arms"], check="Alle Ausleger gedruckt, Bohrungen frei.",
             tool="3D-Drucker", quantity_refs=["q_arm_x"]),
        Step(id="s2", index=2, action="Motoren an die Ausleger, Ausleger an die Nabe schrauben.",
             inputs=["a_arms", "b_motor"], outputs=["a_frame"], check="Rahmen steif, Motoren fluchten."),
        Step(id="s3", index=3, action="ESC, Flight-Controller, Akku und Abwurfhaken verdrahten.",
             inputs=["a_frame", "b_esc", "b_fc", "b_batt", "b_hook"], outputs=["a_done"],
             check="Schub-Gewicht ≥ 2; Strombudget unter ESC- und Akku-Grenze; Lageregler gedämpft.",
             quantity_refs=["q_thrust", "q_pmax"]),
    ]
    constraints = [
        Constraint(id="k_stress", kind="le", left="q_sigma_peak", right="q_strength",
                   reason="die Spitzenspannung am Motorende des Auslegers bleibt unter der PLA-Festigkeit"),
        Constraint(id="k_wall", kind="ge", left="q_h", right="q_min_wall",
                   reason="die Auslegerhöhe ist mindestens die kleinste druckbare FDM-Wand"),
    ]
    decisions = [
        Decision(id="d_frame", title="Rahmen", choice="gedruckte Ausleger, X-Quadrocopter",
                 rationale="Ausleger schnell druckbar; Serienrahmen aus CFK", informed_by=["c_pla"]),
    ]
    return Specification(
        run_id="delivery_drone",
        idea="Eine autonome urbane Paket-Lieferdrohne (Quadrocopter) — gegatet gegen Rotor-Schwebe, "
             "Akku-Flugzeit, ESC/Akku-Strombudget, Lageregelungs-Dämpfung und die Auslegerfestigkeit",
        approach_id="ap_drone", quantities=quantities, components=components, bom=bom,
        steps=steps, constraints=constraints, decisions=decisions,
        gaps=[
            "PLA-Ausleger sind der druckbare Prototyp; eine zertifizierte Lieferdrohne braucht CFK-Arme "
            "und eine Crash-/Failsafe-Auslegung (Redundanz, Fallschirm), die hier nicht modelliert ist.",
            "Die Flug-Checks sind erste-Ordnung-Closed-Forms (Impulstheorie, lineare Motorkennlinie, "
            "PD-Dämpfung); Vorwärtsflug-Aerodynamik, Wind und Sensorfusion liegen außerhalb des Gates.",
            "Avionik/Antrieb sind über Kennwerte spezifiziert; konkrete SKUs/Preise liefert die "
            "Live-α-Recherche nach.",
        ],
        claim_ids_used=[c.id for c in delivery_drone_claims()], produced_by="delivery_drone",
    )


# ============================================================================================
# 2. Modular home energy-storage wall — the general energy/current axes
# ============================================================================================

def home_battery_claims() -> list:
    return _dfm_claims() + [
        _claim("c_bess", "Ein modularer Heim-Energiespeicher puffert PV-/Netzenergie und liefert "
               "eine Notlaufzeit aus seiner nutzbaren Kapazität."),
        _claim("c_lfp", "LiFePO4-Zellen (48 V Modul) erlauben tiefe Entladung mit ~80 % nutzbarem "
               "Energieanteil und 1C Dauerentladung."),
        _claim("c_bms", "Ein 48-V-BMS schützt den Strang und begrenzt den Dauerstrom auf 50 A."),
    ]


def home_battery_spec() -> Specification:
    """Eine modulare Heim-Energiespeicher-Wand: die Energie-/Strom-Closed-Forms (allgemeine
    Leistungsmathematik — die measurand-Namen tragen historisch das 'flight'-Präfix) plus ein
    lasttragender gedruckter Modulhalter, der das Zellpaket trägt."""
    module_mass = 40.0  # kg of one cell pack hanging on the printed bracket
    force_n = module_mass * STANDARD_GRAVITY
    quantities = [
        *_dfm_quantities(),
        *_struct_quantities(force_n, 50.0, 60.0, 20.0),
        _d("q_module_mass", "Modulmasse", module_mass, "kg", "Zellpaket je Halter"),
        _g("q_g", "Normfallbeschleunigung", STANDARD_GRAVITY, "m/s^2", ["c_gravity"]),
        _der("q_force", "Halterlast (Modulgewicht)", force_n, "N",
             weight_formula("q_module_mass", "q_g"), ("q_module_mass", "q_g")),
        _d("q_arm", "Biege-Hebelarm Halter", 50.0, "mm", "Wand→Schwerpunkt"),
        _d("q_b", "Halterbreite / size_y", 60.0, "mm", "Breite b"),
        _d("q_h", "Halterhöhe / size_z", 20.0, "mm", "Höhe h"),
        _d("q_hx", "Halterlänge / size_x", 140.0, "mm", "Wandauskragung"),
        _d("q_bore", "Schraubbohrungsradius", 4.0, "mm", "M8-Wandanker"),
        _d("q_off_p", "Bohrungsversatz +", 55.0, "mm", "+x Modulseite"),
        _d("q_off_n", "Bohrungsversatz -", -55.0, "mm", "-x Wandseite"),
        # energy: usable-energy backup runtime (battery_endurance, general power math)
        _gm("q_cap", "Speicherkapazität", 5000.0, "Wh", ["c_lfp"], "battery.capacity"),
        _dm("q_load", "Haushaltslast", 800.0, "W", "Dauerlast im Notbetrieb", "flight.hover_power"),
        _dm("q_backup", "geforderte Notlaufzeit", 240.0, "min", "4 h Überbrückung",
            "flight.required_endurance"),
        # current: BMS + cell C-rating (current_budget)
        _dm("q_pmax", "Spitzenlast", 800.0, "W", "Wechselrichter-Eingang", "flight.max_power"),
        _dm("q_volt", "Strangspannung", 48.0, "V", "16S LFP", "battery.voltage"),
        _gm("q_bms", "BMS-Dauerstromgrenze", 50.0, "A", ["c_bms"], "esc.current_limit"),
        _dm("q_cap_ah", "Strangkapazität", 100.0, "Ah", "48 V · 100 Ah ≈ 5 kWh", "battery.capacity_ah"),
        _gm("q_crate", "Zell-C-Rating", 1.0, "1", ["c_lfp"], "battery.c_rating"),
    ]
    geom = _link("q_hx", "q_b", "q_h", "q_bore", "q_off_n", "q_bore", "q_off_p")
    components = [
        Component(id="c_bracket", name="Modulhalter", geometry=geom,
                  quantity_ids=["q_hx", "q_b", "q_h", "q_bore", "q_off_p", "q_off_n", "q_zero"],
                  material_density="q_density"),
    ]
    bom = [
        BomItem(id="b_bracket", name="Modulhalter (gedruckt)", role=BomRole.PART, count=4,
                component_id="c_bracket", domain=BomDomain.MECHANICAL, grounding=["c_bess"]),
        BomItem(id="b_cells", name="LiFePO4-Zellpaket (48 V, 100 Ah)", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC, grounding=["c_lfp"]),
        BomItem(id="b_bms", name="48-V-BMS (50 A)", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC, grounding=["c_bms"]),
        BomItem(id="b_busbar", name="Kupfer-Busbars + Anschlussklemmen", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC),
        BomItem(id="b_contactor", name="Vorlade-Schütz + Sicherung", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC),
        BomItem(id="b_printer", name="3D-Drucker", role=BomRole.TOOL, count=1),
    ]
    steps = [
        Step(id="s1", index=1, action="Vier Modulhalter drucken und an die Wand dübeln.",
             uses=["b_printer"], inputs=["b_bracket"], outputs=["a_wall"],
             check="Halter sitzen, tragen das Modulgewicht.", tool="3D-Drucker", quantity_refs=["q_hx"]),
        Step(id="s2", index=2, action="Zellpaket einsetzen, BMS, Busbars und Schütz verdrahten.",
             inputs=["a_wall", "b_cells", "b_bms", "b_busbar", "b_contactor"], outputs=["a_done"],
             check="Notlaufzeit ≥ 4 h; Strom unter BMS- und Zell-C-Grenze.",
             quantity_refs=["q_cap", "q_pmax"]),
    ]
    constraints = [
        Constraint(id="k_stress", kind="le", left="q_sigma_peak", right="q_strength",
                   reason="die Spitzenspannung am Halter bleibt unter der PLA-Festigkeit"),
        Constraint(id="k_wall", kind="ge", left="q_h", right="q_min_wall",
                   reason="die Halterhöhe ist mindestens die kleinste druckbare FDM-Wand"),
    ]
    decisions = [
        Decision(id="d_chem", title="Zellchemie", choice="LiFePO4 (48 V)",
                 rationale="lange Zyklenzahl, thermisch gutmütig, tiefentladbar", informed_by=["c_lfp"]),
    ]
    return Specification(
        run_id="home_battery",
        idea="Eine modulare Heim-Energiespeicher-Wand — gegatet gegen Notlaufzeit (nutzbare Energie), "
             "BMS/Zell-Strombudget und die Modulhalter-Festigkeit",
        approach_id="ap_bess", quantities=quantities, components=components, bom=bom,
        steps=steps, constraints=constraints, decisions=decisions,
        gaps=[
            "Die Energie-/Strom-Achsen sind allgemeine Leistungsmathematik; ihre measurand-Namen "
            "tragen historisch das 'flight'-Präfix (hover_power = Haushaltslast). Das Ergebnis ist "
            "korrekt, die Benennung ist eine offene Aufräum-Aufgabe (domänenneutrale Recipes).",
            "Zell-Thermik (Lade-/Entlade-Wärme, Kühlung), Wechselrichter-Wirkungsgrad und Brandschutz "
            "sind nicht modelliert — sie gehören zu einer Serien-BESS-Auslegung.",
            "Der PLA-Halter ist der druckbare Prototyp; ein Wandhalter für 40 kg in Serie wäre aus "
            "Stahl/Alu.",
        ],
        claim_ids_used=[c.id for c in home_battery_claims()], produced_by="home_battery",
    )


# ============================================================================================
# 3. Vertical-farming harvest arm — kinematics + actuator + vision compute
# ============================================================================================

def harvest_arm_claims() -> list:
    return _dfm_claims() + [
        _claim("c_harvest", "Ein autonomer Ernteroboter greift Früchte mit einem 2-Glied-Arm und "
               "erkennt sie per Kamera-Inferenz."),
        _claim("c_servo", "Ein Robotik-Servogetriebemotor liefert ~1.5 N*m Stall vor der Untersetzung."),
        _claim("c_edgetpu", "Ein Edge-KI-Beschleuniger liefert ~50 INT8-TOPS bei ~10 W."),
    ]


def harvest_arm_spec() -> Specification:
    """Ein autonomer Vertical-Farming-Ernteroboter-Arm: 2R-Reichweite (Kinematik) + Elektro-Aktuator-
    Sizing + Onboard-Kamera-Inferenz (Compute) plus ein lasttragendes gedrucktes Armglied."""
    quantities = [
        *_dfm_quantities(),
        *_struct_quantities(40.0, 300.0, 30.0, 16.0),
        _d("q_force", "Greiferlast am Armende", 40.0, "N", "Frucht + Greifer"),
        _d("q_arm", "Biege-Hebelarm Arm", 300.0, "mm", "Schulter→Greifer"),
        _d("q_b", "Armbreite / size_y", 30.0, "mm", "Breite b"),
        _d("q_h", "Armhöhe / size_z", 16.0, "mm", "Höhe h"),
        _d("q_ax", "Armlänge / size_x", 420.0, "mm", "Glied 1"),
        _d("q_bore", "Gelenkbohrungsradius", 5.0, "mm", "Lagersitz"),
        _d("q_off_p", "Bohrungsversatz +", 195.0, "mm", "+x Ellbogen"),
        _d("q_off_n", "Bohrungsversatz -", -195.0, "mm", "-x Schulter"),
        # kinematics: 2R reach
        _dm("q_l1", "Glied 1 Länge", 0.40, "m", "Schulter–Ellbogen", "arm.link1_length"),
        _dm("q_l2", "Glied 2 Länge", 0.35, "m", "Ellbogen–Greifer", "arm.link2_length"),
        _dm("q_tx", "Ziel x", 0.50, "m", "Fruchtposition", "arm.target_x"),
        _dm("q_ty", "Ziel y", 0.20, "m", "Fruchthöhe", "arm.target_y"),
        # actuation: shoulder gearmotor
        _dm("q_jt", "Schulter-Drehmoment (Bedarf)", 12.0, "N*m", "statisches Armmoment",
            "actuator.joint_torque"),
        _dm("q_js", "Schulter-Drehzahl", 2.0, "rad/s", "Greifbewegung", "actuator.joint_speed"),
        _gm("q_stall", "Motor-Stall-Moment", 1.5, "N*m", ["c_servo"], "motor.stall_torque"),
        _dm("q_noload", "Motor-Leerlaufdrehzahl", 400.0, "rad/s", "~3820 rpm", "motor.noload_speed"),
        _dm("q_gear", "Getriebeuntersetzung", 30.0, "1", "Planetengetriebe", "drivetrain.gear_ratio"),
        _dm("q_eff", "Wirkungsgrad", 0.85, "1", "Getriebe", "drivetrain.efficiency"),
        # compute: onboard vision inference
        _dm("q_work", "Inferenzlast (Fruchterkennung)", 20.0, "1", "Detektor INT8-TOPS",
            "compute.workload_tops"),
        _gm("q_chip", "Beschleuniger-Spitzenleistung", 50.0, "1", ["c_edgetpu"], "compute.chip_tops"),
        _dm("q_util", "nachhaltige Auslastung", 0.6, "1", "real haltbar", "compute.utilisation"),
        _dm("q_ceff", "Recheneffizienz", 5.0, "1", "≈50 TOPS / 10 W", "compute.efficiency_tops_per_w"),
        _dm("q_pbud", "Compute-Leistungsbudget", 20.0, "W", "Arm-Recheneinheit", "compute.power_budget"),
        _dm("q_iops", "Operationen je Inferenz", 1.0e7, "1", "Detektor je Bild", "compute.inference_ops"),
        _dm("q_thru", "Chip-Durchsatz", 5.0e13, "1", "50 TOPS = 5e13 ops/s",
            "compute.throughput_ops_per_s"),
        _dm("q_period", "Greifschleifen-Periode", 0.02, "s", "50 Hz Pick-Loop", "control.period"),
    ]
    geom = _link("q_ax", "q_b", "q_h", "q_bore", "q_off_n", "q_bore", "q_off_p")
    components = [
        Component(id="c_armlink", name="Armglied 1", geometry=geom,
                  quantity_ids=["q_ax", "q_b", "q_h", "q_bore", "q_off_p", "q_off_n", "q_zero"],
                  material_density="q_density"),
    ]
    bom = [
        BomItem(id="b_armlink", name="Armglied (gedruckt)", role=BomRole.PART, count=2,
                component_id="c_armlink", domain=BomDomain.MECHANICAL, grounding=["c_harvest"]),
        BomItem(id="b_servo", name="Servogetriebemotor (1.5 N*m Stall, 30:1)", role=BomRole.PART,
                count=2, domain=BomDomain.MECHANICAL, grounding=["c_servo"]),
        BomItem(id="b_gripper", name="Weichgreifer + Drucksensor", role=BomRole.PART, count=1,
                domain=BomDomain.MECHANICAL),
        BomItem(id="b_cam", name="RGB-D-Kamera", role=BomRole.PART, count=1, domain=BomDomain.ELECTRONIC),
        BomItem(id="b_accel", name="Edge-KI-Beschleuniger (~50 TOPS)", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC, grounding=["c_edgetpu"]),
        BomItem(id="b_printer", name="3D-Drucker", role=BomRole.TOOL, count=1),
    ]
    steps = [
        Step(id="s1", index=1, action="Zwei Armglieder drucken.", uses=["b_printer"],
             inputs=["b_armlink"], outputs=["a_links"], check="Glieder gedruckt, Bohrungen frei.",
             tool="3D-Drucker", quantity_refs=["q_ax"]),
        Step(id="s2", index=2, action="Servos, Greifer und Kamera montieren, Beschleuniger verdrahten.",
             inputs=["a_links", "b_servo", "b_gripper", "b_cam", "b_accel"], outputs=["a_done"],
             check="Arm erreicht das Ziel; Schultermoment im Budget; Inferenz unter der Pick-Deadline.",
             quantity_refs=["q_tx", "q_jt", "q_work"]),
    ]
    constraints = [
        Constraint(id="k_stress", kind="le", left="q_sigma_peak", right="q_strength",
                   reason="die Spitzenspannung am Armglied bleibt unter der PLA-Festigkeit"),
        Constraint(id="k_wall", kind="ge", left="q_h", right="q_min_wall",
                   reason="die Armhöhe ist mindestens die kleinste druckbare FDM-Wand"),
    ]
    decisions = [
        Decision(id="d_grip", title="Greifer", choice="Weichgreifer (Fin-Ray)",
                 rationale="schonend für Früchte, fehlertolerant", informed_by=["c_harvest"]),
    ]
    return Specification(
        run_id="harvest_arm",
        idea="Ein autonomer Vertical-Farming-Ernteroboter-Arm — gegatet gegen 2R-Reichweite, "
             "Schulter-Aktuator-Sizing, Onboard-Kamera-Inferenz und die Armglied-Festigkeit",
        approach_id="ap_harvest", quantities=quantities, components=components, bom=bom,
        steps=steps, constraints=constraints, decisions=decisions,
        gaps=[
            "Die Greifkraft-/Frucht-Interaktion (Kontaktmechanik, Beschädigungsschwelle) und die "
            "Detektor-Genauigkeit sind empirisch — das Compute-Gate prüft nur das Durchsatz-/"
            "Latenz-Budget, nicht die Erkennungsrate.",
            "Der σ-Check nutzt PLA bei Prototyp-Greiferlast; ein Dauerbetrieb-Arm wäre aus Alu.",
            "Motor/Kamera/Beschleuniger sind über Kennwerte spezifiziert; SKUs/Preise via Live-α-Recherche.",
        ],
        claim_ids_used=[c.id for c in harvest_arm_claims()], produced_by="harvest_arm",
    )


# ============================================================================================
# 4. Autonomous construction hydraulic actuator module — the HYDRAULIC axes
# ============================================================================================

def hydraulic_boom_claims() -> list:
    return _dfm_claims() + [
        _claim("c_boom", "Ein autonomes Baumaschinen-Auslegermodul bewegt seinen Ausleger mit einem "
               "Hydraulikzylinder; der Stahlausleger ist ein Kaufteil."),
        _claim("c_hpu", "Eine 200-bar-Hydraulikpumpe mit 60 L/min speist den Auslegerzylinder."),
    ]


def hydraulic_boom_spec() -> Specification:
    """Ein hydraulisches Aktuator-Modul für autonome Baumaschinen: die Hydraulik-Closed-Forms
    (Zylinderkraft F=p·A, Förderstrom Q=A·v) + 2R-Reichweite, plus ein gedruckter Ventil-/Sensor-
    Halter (der Stahlausleger und der Zylinder sind Kaufteile — Hydraulik braucht Stahl)."""
    quantities = [
        *_dfm_quantities(),
        *_struct_quantities(80.0, 60.0, 40.0, 12.0),
        _d("q_force", "Halterlast (Ventilblock)", 80.0, "N", "Ventilblock + Schläuche"),
        _d("q_arm", "Biege-Hebelarm Halter", 60.0, "mm", "Auskragung"),
        _d("q_b", "Halterbreite / size_y", 40.0, "mm", "Breite b"),
        _d("q_h", "Halterhöhe / size_z", 12.0, "mm", "Höhe h"),
        _d("q_hx", "Halterlänge / size_x", 130.0, "mm", "Länge"),
        _d("q_bore", "Befestigungsbohrungsradius", 4.0, "mm", "M8"),
        _d("q_off_p", "Bohrungsversatz +", 55.0, "mm", "+x"),
        _d("q_off_n", "Bohrungsversatz -", -55.0, "mm", "-x"),
        # hydraulics: cylinder force
        _gm("q_press", "Systemdruck", 2.0e7, "Pa", ["c_hpu"], "hydraulic.pressure"),
        _d("q_boreA", "Kolbenfläche", 0.00785, "m^2", "Ø100 mm Zylinder, r=0.05 m"),
        _dm("q_boreA_m", "Kolbenfläche (measurand)", 0.00785, "m^2", "Ø100 mm", "hydraulic.bore_area"),
        _dm("q_reqF", "geforderte Auslegerkraft", 120000.0, "N", "Hub unter Last",
            "hydraulic.required_force"),
        # hydraulics: pump flow
        _dm("q_vel", "Kolbengeschwindigkeit", 0.1, "m/s", "Hubgeschwindigkeit",
            "hydraulic.piston_velocity"),
        _gm("q_pump", "Pumpenförderstrom", 0.001, "m^3/s", ["c_hpu"], "hydraulic.pump_flow"),
        # kinematics: 2R reach of the boom
        _dm("q_l1", "Hauptausleger-Länge", 1.2, "m", "Basis–Knick", "arm.link1_length"),
        _dm("q_l2", "Stielausleger-Länge", 1.0, "m", "Knick–Werkzeug", "arm.link2_length"),
        _dm("q_tx", "Ziel x", 1.5, "m", "Reichweite", "arm.target_x"),
        _dm("q_ty", "Ziel y", 0.8, "m", "Höhe", "arm.target_y"),
    ]
    geom = _link("q_hx", "q_b", "q_h", "q_bore", "q_off_n", "q_bore", "q_off_p")
    components = [
        Component(id="c_valvebracket", name="Ventil-/Sensorhalter", geometry=geom,
                  quantity_ids=["q_hx", "q_b", "q_h", "q_bore", "q_off_p", "q_off_n", "q_zero"],
                  material_density="q_density"),
    ]
    bom = [
        BomItem(id="b_valvebracket", name="Ventil-/Sensorhalter (gedruckt)", role=BomRole.PART, count=2,
                component_id="c_valvebracket", domain=BomDomain.MECHANICAL, grounding=["c_boom"]),
        BomItem(id="b_cylinder", name="Hydraulikzylinder Ø100 mm (Stahl)", role=BomRole.PART, count=1,
                domain=BomDomain.MECHANICAL, grounding=["c_boom"]),
        BomItem(id="b_boom", name="Stahlausleger (geschweißt)", role=BomRole.PART, count=1,
                domain=BomDomain.MECHANICAL, grounding=["c_boom"]),
        BomItem(id="b_pump", name="Hydraulikpumpe 200 bar / 60 L/min", role=BomRole.PART, count=1,
                domain=BomDomain.MECHANICAL, grounding=["c_hpu"]),
        BomItem(id="b_valve", name="Proportional-Wegeventil + Drucksensor", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC),
        BomItem(id="b_printer", name="3D-Drucker", role=BomRole.TOOL, count=1),
    ]
    steps = [
        Step(id="s1", index=1, action="Ventil-/Sensorhalter drucken.", uses=["b_printer"],
             inputs=["b_valvebracket"], outputs=["a_brk"], check="Halter gedruckt.",
             tool="3D-Drucker", quantity_refs=["q_hx"]),
        Step(id="s2", index=2, action="Zylinder an den Stahlausleger, Ventilblock am Halter, Pumpe "
             "und Sensor verschlauchen.",
             inputs=["a_brk", "b_cylinder", "b_boom", "b_pump", "b_valve"], outputs=["a_done"],
             check="Zylinderkraft ≥ gefordert; Pumpenförderstrom ≥ Kolbenbedarf; Reichweite erfüllt.",
             quantity_refs=["q_press", "q_pump", "q_tx"]),
    ]
    constraints = [
        Constraint(id="k_stress", kind="le", left="q_sigma_peak", right="q_strength",
                   reason="die Spitzenspannung am gedruckten Ventilhalter bleibt unter der PLA-Festigkeit"),
        Constraint(id="k_wall", kind="ge", left="q_h", right="q_min_wall",
                   reason="die Halterhöhe ist mindestens die kleinste druckbare FDM-Wand"),
    ]
    decisions = [
        Decision(id="d_act", title="Aktuation", choice="Hydraulikzylinder",
                 rationale="höchste Kraftdichte für Auslegerlasten", informed_by=["c_boom"]),
    ]
    return Specification(
        run_id="hydraulic_boom",
        idea="Ein hydraulisches Aktuator-Modul für autonome Baumaschinen — gegatet gegen Zylinderkraft, "
             "Pumpenförderstrom, 2R-Reichweite und die Festigkeit des gedruckten Ventilhalters",
        approach_id="ap_boom", quantities=quantities, components=components, bom=bom,
        steps=steps, constraints=constraints, decisions=decisions,
        gaps=[
            "Nur der gedruckte Ventil-/Sensorhalter ist ein PLA-Teil; Zylinder, Ausleger und Pumpe sind "
            "Stahl-Kaufteile — Hydraulik bei 200 bar ist kein Druckteil.",
            "Die Hydraulik-Checks sind statische Kraft-/Flussbilanzen; Druckverlust über lange Leitungen, "
            "Schlauchnachgiebigkeit und Wärme sind nicht im Gate (der Hagen-Poiseuille-Screen existiert "
            "separat, ist hier aber nicht getriggert).",
            "Die Auslegerstruktur (Stahl) wird nicht vom PLA-σ-Check abgedeckt; sie braucht eine eigene "
            "Stahl-FEM.",
        ],
        claim_ids_used=[c.id for c in hydraulic_boom_claims()], produced_by="hydraulic_boom",
    )


# ============================================================================================
# 5. Assistive exoskeleton knee module — actuator + kinematics + swing dynamics
# ============================================================================================

def exo_knee_claims() -> list:
    return _dfm_claims() + [
        _claim("c_exo", "Ein assistives Exoskelett-Kniemodul unterstützt das menschliche Knie über "
               "Oberschenkel- und Unterschenkelschienen mit einem motorisierten Gelenk."),
        _claim("c_exomotor", "Ein rückfahrbarer Exoskelett-Gelenkmotor liefert ~2.0 N*m Stall vor "
               "der Untersetzung."),
    ]


def exo_knee_spec() -> Specification:
    """Ein assistives Exoskelett-Kniemodul: Elektro-Aktuator-Sizing + 2R-Kinematik der Beinschiene +
    Schwung-Dynamik (Inverse-Dynamik-Drehmoment über den Gang) plus eine gedruckte Beinschiene."""
    limb_inertia = rod_inertia_about_end(2.5, 0.40)  # canonical: uniform shank about the knee
    quantities = [
        *_dfm_quantities(),
        *_struct_quantities(60.0, 200.0, 35.0, 14.0),
        _d("q_force", "Schienenlast", 60.0, "N", "Teil-Körpergewicht über die Schiene"),
        _d("q_arm", "Biege-Hebelarm Schiene", 200.0, "mm", "Knie→Befestigung"),
        _d("q_b", "Schienenbreite / size_y", 35.0, "mm", "Breite b"),
        _d("q_h", "Schienenhöhe / size_z", 14.0, "mm", "Höhe h"),
        _d("q_sx", "Schienenlänge / size_x", 380.0, "mm", "Oberschenkelschiene"),
        _d("q_bore", "Gelenkbohrungsradius", 5.0, "mm", "Knie-Lagersitz"),
        _d("q_off_p", "Bohrungsversatz +", 175.0, "mm", "+x Knie"),
        _d("q_off_n", "Bohrungsversatz -", -175.0, "mm", "-x Befestigung"),
        # actuation: knee assist motor
        _dm("q_jt", "Knie-Assistenzmoment (Bedarf)", 35.0, "N*m", "Unterstützungsmoment",
            "actuator.joint_torque"),
        _dm("q_js", "Knie-Winkelgeschwindigkeit", 3.0, "rad/s", "Gangbewegung", "actuator.joint_speed"),
        _gm("q_stall", "Motor-Stall-Moment", 2.0, "N*m", ["c_exomotor"], "motor.stall_torque"),
        _dm("q_noload", "Motor-Leerlaufdrehzahl", 350.0, "rad/s", "~3340 rpm", "motor.noload_speed"),
        _dm("q_gear", "Getriebeuntersetzung", 50.0, "1", "Cycloidgetriebe", "drivetrain.gear_ratio"),
        _dm("q_eff", "Wirkungsgrad", 0.80, "1", "Getriebe", "drivetrain.efficiency"),
        # kinematics: 2R leg reach
        _dm("q_l1", "Oberschenkelschiene", 0.42, "m", "Hüfte–Knie", "arm.link1_length"),
        _dm("q_l2", "Unterschenkelschiene", 0.40, "m", "Knie–Knöchel", "arm.link2_length"),
        _dm("q_tx", "Ziel x (Fuß)", 0.50, "m", "Schrittweite", "arm.target_x"),
        _dm("q_ty", "Ziel y (Fuß)", 0.30, "m", "Höhe", "arm.target_y"),
        # swing dynamics
        _dm("q_limb_I", "Schienen-Trägheit um das Knie", limb_inertia, "kg*m^2",
            "m·L²/3 (kanonische Formel) — Unterschenkelschiene um das Knie", "limb.inertia"),
        _dm("q_limb_m", "Schienen-Masse", 2.5, "kg", "Schiene + Motor", "limb.mass"),
        _dm("q_limb_d", "Schienen-Schwerpunktabstand", 0.20, "m", "Knie→CoM", "limb.com_distance"),
        _dm("q_swing", "Schwung-Amplitude", 0.5, "rad", "Knie-Schwung im Schritt", "swing.amplitude"),
        _dm("q_stepf", "Schrittfrequenz", 0.5, "Hz", "Gang-Kadenz", "gait.step_frequency"),
        _dm("q_availtau", "verfügbares Gelenkmoment", 80.0, "N*m", "Stall·Getriebe·η",
            "actuator.available_torque"),
        # balance: the wearer + exo over the gait (so the indicated ZMP check actually runs)
        _dm("q_com_x", "CoM-Versatz", 0.0, "m", "zentriert über dem Fuß", "balance.com_x"),
        _dm("q_com_h", "CoM-Höhe (Träger)", 0.9, "m", "menschlicher Schwerpunkt", "balance.com_height"),
        _dm("q_smin", "Stützpolygon min x", -0.10, "m", "Ferse", "balance.support_min_x"),
        _dm("q_smax", "Stützpolygon max x", 0.15, "m", "Zehe", "balance.support_max_x"),
        _dm("q_sway", "CoM-Schwankungsamplitude", 0.03, "m", "seitliche Gang-Schwankung",
            "gait.com_amplitude"),
    ]
    geom = _link("q_sx", "q_b", "q_h", "q_bore", "q_off_n", "q_bore", "q_off_p")
    components = [
        Component(id="c_splint", name="Beinschiene", geometry=geom,
                  quantity_ids=["q_sx", "q_b", "q_h", "q_bore", "q_off_p", "q_off_n", "q_zero"],
                  material_density="q_density"),
    ]
    bom = [
        BomItem(id="b_splint", name="Beinschiene (gedruckt)", role=BomRole.PART, count=2,
                component_id="c_splint", domain=BomDomain.MECHANICAL, grounding=["c_exo"]),
        BomItem(id="b_motor", name="Rückfahrbarer Gelenkmotor (2.0 N*m Stall, 50:1)", role=BomRole.PART,
                count=1, domain=BomDomain.MECHANICAL, grounding=["c_exomotor"]),
        BomItem(id="b_strap", name="Klett-Befestigungsgurte + Polster", role=BomRole.PART, count=4,
                domain=BomDomain.MECHANICAL),
        BomItem(id="b_imu", name="Gang-IMU + Drehgeber", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC),
        BomItem(id="b_batt", name="Akku + Treiber (am Gürtel)", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC),
        BomItem(id="b_printer", name="3D-Drucker", role=BomRole.TOOL, count=1),
    ]
    steps = [
        Step(id="s1", index=1, action="Zwei Beinschienen drucken.", uses=["b_printer"],
             inputs=["b_splint"], outputs=["a_splints"], check="Schienen gedruckt, Bohrungen frei.",
             tool="3D-Drucker", quantity_refs=["q_sx"]),
        Step(id="s2", index=2, action="Gelenkmotor zwischen die Schienen montieren, Gurte, IMU und "
             "Akku/Treiber anbringen.",
             inputs=["a_splints", "b_motor", "b_strap", "b_imu", "b_batt"], outputs=["a_done"],
             check="Reichweite erfüllt; Assistenzmoment im Budget; Schwung-Drehmoment unter dem "
                   "verfügbaren Gelenkmoment.",
             quantity_refs=["q_jt", "q_availtau", "q_swing"]),
    ]
    constraints = [
        Constraint(id="k_stress", kind="le", left="q_sigma_peak", right="q_strength",
                   reason="die Spitzenspannung an der Beinschiene bleibt unter der PLA-Festigkeit"),
        Constraint(id="k_wall", kind="ge", left="q_h", right="q_min_wall",
                   reason="die Schienenhöhe ist mindestens die kleinste druckbare FDM-Wand"),
    ]
    decisions = [
        Decision(id="d_act", title="Aktuation", choice="rückfahrbarer Motor (Cycloidgetriebe)",
                 rationale="rückfahrbar = sicher am Menschen, hohe Drehmomentdichte",
                 informed_by=["c_exomotor"]),
    ]
    return Specification(
        run_id="exo_knee",
        idea="Ein assistives Exoskelett-Kniemodul — gegatet gegen Aktuator-Sizing, 2R-Beinkinematik, "
             "Schwung-Drehmoment über den Gang und die Beinschienen-Festigkeit",
        approach_id="ap_exo", quantities=quantities, components=components, bom=bom,
        steps=steps, constraints=constraints, decisions=decisions,
        gaps=[
            "Die Mensch-Maschine-Interaktion (Komfort, Hautdruck, Synchronisation mit der "
            "Nutzerintention) ist empirisch und sicherheitskritisch — außerhalb des Closed-Form-Gates.",
            "Der σ-Check nutzt PLA bei Prototyp-Schienenlast; eine zertifizierte Orthese wäre aus "
            "Carbon/Alu mit Medizinprodukte-Zulassung.",
            "Der volle Gang mit Bodenkontakt läuft im externen Simulator über die URDF-Brücke; das Gate "
            "prüft die deterministischen Schwung-Screens, nicht den geschlossenen Regelkreis am Menschen.",
        ],
        claim_ids_used=[c.id for c in exo_knee_claims()], produced_by="exo_knee",
    )


#: All five future-idea specs paired with their claim builders — the runner iterates this.
ALL_FUTURE_IDEAS = [
    (delivery_drone_spec, delivery_drone_claims),
    (home_battery_spec, home_battery_claims),
    (harvest_arm_spec, harvest_arm_claims),
    (hydraulic_boom_spec, hydraulic_boom_claims),
    (exo_knee_spec, exo_knee_claims),
]
