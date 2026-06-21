"""visionary_ideas — three concepts a DREAMER (grok-build, as visionary) invented, then GENESIS grounded.

The owner asked grok-build to be a visionary and dream up three things that do not exist yet; GENESIS
then builds each as a GATED ``Specification`` and runs it through the same δ-physics machinery as every
other spec. grok decided the WHAT; GENESIS supplies the verified HOW — and where grok's dreamer figures
were not self-consistent (e.g. a resonance cadence that did not match the leg it described), the numbers
are tuned to physical consistency and the tuning is declared. The dream is grok's; the honesty is GENESIS's.

The three grok-decided concepts:
  1. skyclaw_spec     — SkyClaw: a backpack-portable, field-printable FLYING MANIPULATOR (quad-rotor +
     2R arm + gripper) that repairs bridges at height and lifts people from shafts without a crane.
     Fires the full FLIGHT stack + kinematics + actuation + compute + structure — the richest spec.
  2. resostrider_spec — ResoStrider: a radically simple, fully printable RESONANCE-DRIVEN quadruped for
     months of autonomous exploration of rubble or other worlds — it walks by riding its legs' own
     natural swing. Fires swing RESONANCE + inverse-dynamics torque + dynamic ZMP + reach + actuation.
  3. forgehydra_spec  — ForgeHydra: an air-droppable, ultralight, field-printable HYDRAULIC system that
     a drone drops into a collapsed building or mine to move heavy loads without trucking in an excavator.
     Fires the hydraulic axes (F=p·A, Q=A·v) + reach + compute + structure.

Deterministic, offline, no LLM in the build path (grok only DECIDED the ideas, as the owner asked).
No trading/ASYA/MT5. German prose; English ids/units/measurands. Reuses the future_ideas spec helpers.
"""

from __future__ import annotations

from .core.state import (
    BomDomain,
    BomItem,
    BomRole,
    Component,
    Constraint,
    Decision,
    Specification,
    Step,
)
from .demo import _claim, _d, _dm, _gm
from .future_ideas import _dfm_claims, _dfm_quantities, _link, _struct_quantities
from .mechanics_formulas import rod_inertia_about_end


# ============================================================================================
# 1. SkyClaw — a backpack-portable flying manipulator (grok's dream #1)
# ============================================================================================

def skyclaw_claims() -> list:
    return _dfm_claims() + [
        _claim("c_skyclaw", "Ein fliegender Manipulator vereint einen Quadrocopter mit einem 2-Glied-"
               "Arm und Greifer, um in der Höhe zu arbeiten, ohne Kran oder Gerüst."),
        _claim("c_bldc", "Ein 2212-Drohnen-BLDC-Motor mit 12-Zoll-Propeller liefert ~22 N Schub."),
        _claim("c_armmotor", "Ein Arm-Getriebemotor liefert ~2.0 N*m Stall vor der 50:1-Untersetzung."),
        _claim("c_lipo6s", "Ein 6S-LiPo (22.2 V, 25C) speist Antrieb, Arm und Avionik."),
        _claim("c_jetson", "Ein Jetson Orin Nano liefert ~40 INT8-TOPS für die Flug-/Greifregelung."),
    ]


def skyclaw_spec() -> Specification:
    """SkyClaw — rucksack-transportabler fliegender Manipulator: Quadrocopter + 2R-Arm + Greifer.
    Feuert die volle Flug-Achse (Schwebe/Akku/Strom/Lage) + Kinematik + Aktuation + Compute +
    Auslegerfestigkeit. grok's Vision, GENESIS-konsistente Zahlen."""
    quantities = [
        *_dfm_quantities(),
        *_struct_quantities(45.0, 120.0, 30.0, 15.0),
        _d("q_force", "Greiferlast am Armende", 45.0, "N", "~4.6 kg Nutzlast"),
        _d("q_arm", "Biege-Hebelarm Armsegment", 120.0, "mm", "Gelenk→Greifer"),
        _d("q_b", "Armbreite / size_y", 30.0, "mm", "Breite b"),
        _d("q_h", "Armhöhe / size_z", 15.0, "mm", "Höhe h"),
        _d("q_ax", "Armsegmentlänge / size_x", 300.0, "mm", "Glied 1"),
        _d("q_abore", "Armgelenkbohrung", 5.0, "mm", "Lagersitz"),
        _d("q_aoff_p", "Armbohrung +", 135.0, "mm", "+x"),
        _d("q_aoff_n", "Armbohrung -", -135.0, "mm", "-x"),
        _d("q_bx", "Zentralkörper / size_x", 220.0, "mm", "Monocoque"),
        _d("q_by", "Zentralkörper / size_y", 160.0, "mm", "Breite"),
        _d("q_bz", "Zentralkörper / size_z", 30.0, "mm", "Höhe"),
        _d("q_bbore", "Körperbohrung", 4.0, "mm", "Armsockel/Akku-Schraube"),
        _d("q_boff_p", "Körperbohrung +", 80.0, "mm", "+x"),
        _d("q_boff_n", "Körperbohrung -", -80.0, "mm", "-x"),
        _d("q_rx", "Rotorarm / size_x", 240.0, "mm", "Nabe→Motor"),
        _d("q_ry", "Rotorarm / size_y", 22.0, "mm", "Breite"),
        _d("q_rz", "Rotorarm / size_z", 12.0, "mm", "Höhe"),
        _d("q_rbore", "Rotorarmbohrung", 4.0, "mm", "Motor/Nabe"),
        _d("q_roff_p", "Rotorbohrung +", 110.0, "mm", "+x Motor"),
        _d("q_roff_n", "Rotorbohrung -", -110.0, "mm", "-x Nabe"),
        # flight: rotor hover
        _dm("q_mass", "Abflugmasse", 3.8, "kg", "Plattform + Arm + Nutzlast", "vehicle.mass"),
        _dm("q_disk", "Rotor-Kreisfläche", 0.073, "m^2", "12-Zoll-Prop, r=0.152 m", "rotor.disk_area"),
        _dm("q_nrot", "Rotorzahl", 4.0, "1", "Quadrocopter", "rotor.count"),
        _gm("q_thrust", "max. Gesamtschub", 90.0, "N", ["c_bldc"], "rotor.max_total_thrust"),
        # flight: endurance
        _dm("q_cap_wh", "Akkukapazität", 150.0, "Wh", "6S 6.8 Ah", "battery.capacity"),
        _dm("q_hover_w", "Schwebeleistung", 386.0, "W", "Impulstheorie + FoM 0.7", "flight.hover_power"),
        _dm("q_endur", "geforderte Flugzeit", 12.0, "min", "Arbeitsmission", "flight.required_endurance"),
        # flight: current
        _dm("q_pmax", "Spitzenleistung", 950.0, "W", "Steigflug + Armlast", "flight.max_power"),
        _gm("q_volt", "Akkuspannung", 22.2, "V", ["c_lipo6s"], "battery.voltage"),
        _dm("q_esc", "ESC-Stromgrenze", 60.0, "A", "4-in-1-ESC", "esc.current_limit"),
        _dm("q_cap_ah", "Akkukapazität", 6.8, "Ah", "6S", "battery.capacity_ah"),
        _gm("q_crate", "Akku-C-Rating", 25.0, "1", ["c_lipo6s"], "battery.c_rating"),
        # flight: attitude PD
        _dm("q_Iv", "Roll-/Nick-Trägheit", 0.08, "kg*m^2", "mit ausgefahrenem Arm",
            "vehicle.attitude_inertia"),
        _dm("q_kp", "Lageregler P", 2.5, "N*m", "Proportional", "control.attitude_kp"),
        _dm("q_kd", "Lageregler D", 0.58, "N*m*s", "Differential (ζ≈0.65)", "control.attitude_kd"),
        # kinematics: 2R arm reach
        _dm("q_l1", "Armglied 1", 0.55, "m", "Sockel–Ellbogen", "arm.link1_length"),
        _dm("q_l2", "Armglied 2", 0.50, "m", "Ellbogen–Greifer", "arm.link2_length"),
        _dm("q_tx", "Ziel x", 0.80, "m", "Arbeitsreichweite", "arm.target_x"),
        _dm("q_ty", "Ziel y", 0.40, "m", "Höhe", "arm.target_y"),
        # actuation: arm shoulder
        _dm("q_jt", "Arm-Schultermoment (Bedarf)", 50.0, "N*m", "Last am Hebel", "actuator.joint_torque"),
        _dm("q_js", "Arm-Schulterdrehzahl", 1.5, "rad/s", "Greifbewegung", "actuator.joint_speed"),
        _gm("q_stall", "Motor-Stall", 2.0, "N*m", ["c_armmotor"], "motor.stall_torque"),
        _dm("q_noload", "Motor-Leerlaufdrehzahl", 300.0, "rad/s", "~2865 rpm", "motor.noload_speed"),
        _dm("q_gear", "Untersetzung", 50.0, "1", "Harmonic Drive", "drivetrain.gear_ratio"),
        _dm("q_eff", "Wirkungsgrad", 0.85, "1", "Getriebe", "drivetrain.efficiency"),
        # compute: onboard flight + grasp inference
        _dm("q_work", "Rechenlast", 10.0, "1", "Flug + Greif-Wahrnehmung, INT8-TOPS",
            "compute.workload_tops"),
        _gm("q_chip", "Chip-Spitzenleistung (Orin Nano)", 50.0, "1", ["c_jetson"], "compute.chip_tops"),
        _dm("q_util", "Auslastung", 0.6, "1", "haltbar", "compute.utilisation"),
        _dm("q_ceff", "Effizienz", 5.0, "1", "TOPS/W", "compute.efficiency_tops_per_w"),
        _dm("q_pbud", "Compute-Budget", 20.0, "W", "Avionik", "compute.power_budget"),
        _dm("q_iops", "Operationen je Inferenz", 5.0e6, "1", "Regel-/Greif-Netz",
            "compute.inference_ops"),
        _dm("q_thru", "Durchsatz", 5.0e13, "1", "50 TOPS", "compute.throughput_ops_per_s"),
        _dm("q_period", "Regelschleifen-Periode", 0.012, "s", "≤12 ms", "control.period"),
    ]
    components = [
        Component(id="c_body", name="Zentralkörper (Monocoque)", geometry=_link(
            "q_bx", "q_by", "q_bz", "q_bbore", "q_boff_n", "q_bbore", "q_boff_p"),
            quantity_ids=["q_bx", "q_by", "q_bz", "q_bbore", "q_boff_p", "q_boff_n", "q_zero"],
            material_density="q_density"),
        Component(id="c_armseg", name="Armsegment", geometry=_link(
            "q_ax", "q_b", "q_h", "q_abore", "q_aoff_n", "q_abore", "q_aoff_p"),
            quantity_ids=["q_ax", "q_b", "q_h", "q_abore", "q_aoff_p", "q_aoff_n", "q_zero"],
            material_density="q_density"),
        Component(id="c_rotorarm", name="Rotorarm", geometry=_link(
            "q_rx", "q_ry", "q_rz", "q_rbore", "q_roff_n", "q_rbore", "q_roff_p"),
            quantity_ids=["q_rx", "q_ry", "q_rz", "q_rbore", "q_roff_p", "q_roff_n", "q_zero"],
            material_density="q_density"),
    ]
    bom = [
        BomItem(id="b_body", name="Zentralkörper (gedruckt)", role=BomRole.PART, count=1,
                component_id="c_body", domain=BomDomain.MECHANICAL, grounding=["c_skyclaw"]),
        BomItem(id="b_armseg", name="Armsegment (gedruckt)", role=BomRole.PART, count=2,
                component_id="c_armseg", domain=BomDomain.MECHANICAL, grounding=["c_skyclaw"]),
        BomItem(id="b_rotorarm", name="Rotorarm (gedruckt)", role=BomRole.PART, count=4,
                component_id="c_rotorarm", domain=BomDomain.MECHANICAL, grounding=["c_skyclaw"]),
        BomItem(id="b_motors", name="2212-BLDC + 12-Zoll-Propeller", role=BomRole.PART, count=4,
                domain=BomDomain.MECHANICAL, grounding=["c_bldc"]),
        BomItem(id="b_armmotor", name="Arm-Getriebemotor (2.0 N*m, 50:1)", role=BomRole.PART, count=2,
                domain=BomDomain.MECHANICAL, grounding=["c_armmotor"]),
        BomItem(id="b_gripper", name="Greifer + Kraft-/Drehmomentsensor", role=BomRole.PART, count=1,
                domain=BomDomain.MECHANICAL),
        BomItem(id="b_fc", name="Flight-Controller + Jetson Orin Nano + Kamera", role=BomRole.PART,
                count=1, domain=BomDomain.ELECTRONIC, grounding=["c_jetson"]),
        BomItem(id="b_esc", name="4-in-1-ESC (60 A)", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC),
        BomItem(id="b_batt", name="6S-LiPo 6.8 Ah (25C)", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC, grounding=["c_lipo6s"]),
        BomItem(id="b_printer", name="3D-Drucker", role=BomRole.TOOL, count=1),
    ]
    steps = [
        Step(id="s1", index=1, action="Zentralkörper, zwei Armsegmente und vier Rotorarme drucken.",
             uses=["b_printer"], inputs=["b_body", "b_armseg", "b_rotorarm"], outputs=["a_print"],
             check="Alle Teile gedruckt, Bohrungen frei.", tool="3D-Drucker", quantity_refs=["q_bx"]),
        Step(id="s2", index=2, action="Rotorarme + Motoren an den Körper, Arm + Armmotoren + Greifer "
             "an den Sockel montieren.",
             inputs=["a_print", "b_motors", "b_armmotor", "b_gripper"], outputs=["a_mech"],
             check="Rahmen steif, Arm beugt frei, Rotoren fluchten."),
        Step(id="s3", index=3, action="Flight-Controller, Jetson, ESC und Akku verdrahten.",
             inputs=["a_mech", "b_fc", "b_esc", "b_batt"], outputs=["a_done"],
             check="Schub-Gewicht ≥ 2; Strom im ESC/Akku-Budget; Lage gedämpft; Arm erreicht das Ziel; "
                   "Inferenz unter der Regel-Deadline.",
             quantity_refs=["q_thrust", "q_tx", "q_work"]),
    ]
    constraints = [
        Constraint(id="k_stress", kind="le", left="q_sigma_peak", right="q_strength",
                   reason="die Spitzenspannung am Armsegment bleibt unter der PLA-Festigkeit"),
        Constraint(id="k_wall", kind="ge", left="q_h", right="q_min_wall",
                   reason="die Armhöhe ist mindestens die kleinste druckbare FDM-Wand"),
    ]
    decisions = [
        Decision(id="d_frame", title="Bauweise", choice="gedrucktes Monocoque + faltbarer 2R-Arm",
                 rationale="rucksack-faltbar, vor Ort druckbar; CFK-Verstärkung für die Serie",
                 informed_by=["c_skyclaw"]),
    ]
    return Specification(
        run_id="skyclaw",
        idea="SkyClaw — ein rucksack-transportabler, vor Ort druckbarer fliegender Manipulator "
             "(Quadrocopter + 2R-Arm + Greifer) für Arbeit in der Höhe ohne Kran — gegatet gegen Schwebe, "
             "Flugzeit, Strom, Lage, Reichweite, Aktuator, Compute und Auslegerfestigkeit",
        approach_id="ap_skyclaw", quantities=quantities, components=components, bom=bom,
        steps=steps, constraints=constraints, decisions=decisions,
        gaps=[
            "Die Kopplung Flug↔Arm (Reaktionsmoment der Armbewegung auf die Fluglage, Schwerpunkt-"
            "verschiebung mit der Nutzlast) ist NICHT modelliert — jede Achse wird einzeln geprüft; ein "
            "fliegender Manipulator braucht zusätzlich eine gekoppelte Ganzkörper-Regelung (extern).",
            "PLA(+CF) ist der druckbare Prototyp; eine zertifizierte Höhen-Arbeitsdrohne braucht "
            "CFK-Arme, Redundanz und eine Absturz-/Failsafe-Auslegung.",
            "Antrieb/Avionik sind über Kennwerte spezifiziert; SKUs/Preise via Live-α-Recherche.",
        ],
        claim_ids_used=[c.id for c in skyclaw_claims()], produced_by="skyclaw",
    )


# ============================================================================================
# 2. ResoStrider — a resonance-driven printable quadruped (grok's dream #2)
# ============================================================================================

def resostrider_claims() -> list:
    return _dfm_claims() + [
        _claim("c_reso", "Ein resonanzgetriebener Vierbeiner läuft, indem er die Eigenschwingung "
               "seiner Beine ausnutzt, statt sie gegen die Trägheit zu zwingen — radikal energiearm."),
        _claim("c_smotor", "Ein kleiner BLDC-Beinmotor liefert ~0.3 N*m Stall vor der 8:1-Untersetzung."),
        _claim("c_npu", "Ein Low-Power-NPU liefert ~4 INT8-TOPS bei wenigen Watt."),
        _claim("c_li", "Ein 6S-Li-Ion-Pack speist Motoren und Recheneinheit für mehrstündige Autonomie."),
    ]


def resostrider_spec() -> Specification:
    """ResoStrider — resonanzgetriebener, voll druckbarer Vierbeiner für lange autonome Erkundung.
    Feuert die Schwung-RESONANZ-Achse (läuft auf der Eigenfrequenz des Beins) + inverse Dynamik +
    dynamische ZMP + 2R-Bein-Reichweite + Aktuator. Konsistente Bein-Physik (grok's Roh-Hz auf das
    beschriebene Bein abgestimmt)."""
    # leg as a physical pendulum about the hip: uniform-rod inertia (canonical) → natural cadence
    limb_inertia = rod_inertia_about_end(0.5, 0.16)   # 0.5 kg femur, 0.16 m → 0.004267 kg·m²
    quantities = [
        *_dfm_quantities(),
        *_struct_quantities(15.0, 80.0, 20.0, 8.0),
        _d("q_force", "Beinlast (Standanteil)", 15.0, "N", "Körpergewicht/4"),
        _d("q_arm", "Biege-Hebelarm Bein", 80.0, "mm", "Hüfte→Last"),
        _d("q_b", "Beinbreite / size_y", 20.0, "mm", "Breite b"),
        _d("q_h", "Beinhöhe / size_z", 8.0, "mm", "Höhe h"),
        _d("q_lx", "Beinsegmentlänge / size_x", 160.0, "mm", "Femur"),
        _d("q_lbore", "Gelenkbohrung", 4.0, "mm", "Lagersitz"),
        _d("q_loff_p", "Beinbohrung +", 72.0, "mm", "+x Knie"),
        _d("q_loff_n", "Beinbohrung -", -72.0, "mm", "-x Hüfte"),
        _d("q_cx", "Chassis / size_x", 200.0, "mm", "Rumpf"),
        _d("q_cy", "Chassis / size_y", 120.0, "mm", "Breite"),
        _d("q_cz", "Chassis / size_z", 18.0, "mm", "Höhe"),
        _d("q_cbore", "Chassisbohrung", 4.0, "mm", "Hüftaufnahme"),
        _d("q_coff_p", "Chassisbohrung +", 85.0, "mm", "+x"),
        _d("q_coff_n", "Chassisbohrung -", -85.0, "mm", "-x"),
        # kinematics: 2R leg reach (femur+tibia)
        _dm("q_l1", "Femur", 0.16, "m", "Hüfte–Knie", "arm.link1_length"),
        _dm("q_l2", "Tibia", 0.16, "m", "Knie–Fuß", "arm.link2_length"),
        _dm("q_tx", "Fußziel x", 0.18, "m", "Schrittweite", "arm.target_x"),
        _dm("q_ty", "Fußziel y", 0.12, "m", "Höhe", "arm.target_y"),
        # actuation: leg gearmotor
        _dm("q_jt", "Hüftmoment (Bedarf)", 1.0, "N*m", "leichter Vierbeiner", "actuator.joint_torque"),
        _dm("q_js", "Hüftdrehzahl", 2.0, "rad/s", "Schritt", "actuator.joint_speed"),
        _gm("q_stall", "Motor-Stall", 0.3, "N*m", ["c_smotor"], "motor.stall_torque"),
        _dm("q_noload", "Motor-Leerlaufdrehzahl", 600.0, "rad/s", "schneller Kleinmotor",
            "motor.noload_speed"),
        _dm("q_gear", "Untersetzung", 8.0, "1", "kompakt", "drivetrain.gear_ratio"),
        _dm("q_eff", "Wirkungsgrad", 0.85, "1", "Getriebe", "drivetrain.efficiency"),
        # dynamics: swing RESONANCE (the signature axis) + inverse dynamics + dynamic ZMP
        _dm("q_limb_I", "Bein-Trägheit um die Hüfte", limb_inertia, "kg*m^2",
            "m·L²/3 (kanonische Stab-Formel)", "limb.inertia"),
        _dm("q_limb_m", "Bein-Masse", 0.5, "kg", "Segment + Motor", "limb.mass"),
        _dm("q_limb_d", "Bein-Schwerpunktabstand", 0.08, "m", "Hüfte→CoM (L/2)", "limb.com_distance"),
        _dm("q_stepf", "Schrittfrequenz", 1.4, "Hz", "knapp UNTER der Eigenfrequenz (Resonanzlauf)",
            "gait.step_frequency"),
        _dm("q_swing", "Schwung-Amplitude", 0.4, "rad", "Beinschwung", "swing.amplitude"),
        _dm("q_availtau", "verfügbares Gelenkmoment", 2.04, "N*m", "Stall·Getriebe·η",
            "actuator.available_torque"),
        _dm("q_com_x", "CoM-Versatz", 0.0, "m", "zentriert", "balance.com_x"),
        _dm("q_com_h", "CoM-Höhe", 0.20, "m", "niedriger Vierbeiner", "balance.com_height"),
        _dm("q_smin", "Stützpolygon min x", -0.08, "m", "Fußbasis", "balance.support_min_x"),
        _dm("q_smax", "Stützpolygon max x", 0.08, "m", "Fußbasis", "balance.support_max_x"),
        _dm("q_sway", "CoM-Schwankung", 0.02, "m", "Resonanzlauf", "gait.com_amplitude"),
        # compute: low-power control
        _dm("q_work", "Rechenlast", 2.0, "1", "Gangregelung + Gelände, INT8-TOPS",
            "compute.workload_tops"),
        _gm("q_chip", "NPU-Spitzenleistung", 4.0, "1", ["c_npu"], "compute.chip_tops"),
        _dm("q_util", "Auslastung", 0.6, "1", "haltbar", "compute.utilisation"),
        _dm("q_ceff", "Effizienz", 5.0, "1", "TOPS/W", "compute.efficiency_tops_per_w"),
        _dm("q_pbud", "Compute-Budget", 18.0, "W", "Low-Power", "compute.power_budget"),
        _dm("q_iops", "Operationen je Inferenz", 2.0e6, "1", "Gangregler", "compute.inference_ops"),
        _dm("q_thru", "Durchsatz", 4.0e12, "1", "4 TOPS", "compute.throughput_ops_per_s"),
        _dm("q_period", "Regelschleifen-Periode", 0.005, "s", "<5 ms", "control.period"),
    ]
    components = [
        Component(id="c_chassis", name="Chassis", geometry=_link(
            "q_cx", "q_cy", "q_cz", "q_cbore", "q_coff_n", "q_cbore", "q_coff_p"),
            quantity_ids=["q_cx", "q_cy", "q_cz", "q_cbore", "q_coff_p", "q_coff_n", "q_zero"],
            material_density="q_density"),
        Component(id="c_legseg", name="Beinsegment (mit Biegefeder)", geometry=_link(
            "q_lx", "q_b", "q_h", "q_lbore", "q_loff_n", "q_lbore", "q_loff_p"),
            quantity_ids=["q_lx", "q_b", "q_h", "q_lbore", "q_loff_p", "q_loff_n", "q_zero"],
            material_density="q_density"),
    ]
    bom = [
        BomItem(id="b_chassis", name="Chassis (gedruckt)", role=BomRole.PART, count=1,
                component_id="c_chassis", domain=BomDomain.MECHANICAL, grounding=["c_reso"]),
        BomItem(id="b_legseg", name="Beinsegment (gedruckt)", role=BomRole.PART, count=8,
                component_id="c_legseg", domain=BomDomain.MECHANICAL, grounding=["c_reso"]),
        BomItem(id="b_motors", name="Klein-BLDC + 8:1-Getriebe", role=BomRole.PART, count=8,
                domain=BomDomain.MECHANICAL, grounding=["c_smotor"]),
        BomItem(id="b_sensors", name="IMU + 4x Kraftsensor (FSR/DMS)", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC),
        BomItem(id="b_compute", name="STM32 + Low-Power-NPU (~4 TOPS)", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC, grounding=["c_npu"]),
        BomItem(id="b_batt", name="6S-Li-Ion-Pack", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC, grounding=["c_li"]),
        BomItem(id="b_printer", name="3D-Drucker", role=BomRole.TOOL, count=1),
    ]
    steps = [
        Step(id="s1", index=1, action="Chassis und acht Beinsegmente (mit integrierter Biegefeder) drucken.",
             uses=["b_printer"], inputs=["b_chassis", "b_legseg"], outputs=["a_print"],
             check="Alle Teile gedruckt; Biegefedern frei; Bohrungen maßhaltig.",
             tool="3D-Drucker", quantity_refs=["q_lx"]),
        Step(id="s2", index=2, action="Acht Beinmotoren montieren, Beine ans Chassis fügen.",
             inputs=["a_print", "b_motors"], outputs=["a_mech"], check="Alle Beine schwingen frei."),
        Step(id="s3", index=3, action="IMU, Kraftsensoren, STM32+NPU und Akku verdrahten.",
             inputs=["a_mech", "b_sensors", "b_compute", "b_batt"], outputs=["a_done"],
             check="Schrittfrequenz ≤ Eigenfrequenz (Resonanzlauf); Schwung-Drehmoment im Budget; "
                   "ZMP im Stützpolygon; Compute-Latenz < 5 ms.",
             quantity_refs=["q_stepf", "q_availtau", "q_work"]),
    ]
    constraints = [
        Constraint(id="k_stress", kind="le", left="q_sigma_peak", right="q_strength",
                   reason="die Spitzenspannung am Beinsegment bleibt unter der PLA-Festigkeit"),
        Constraint(id="k_wall", kind="ge", left="q_h", right="q_min_wall",
                   reason="die Beinhöhe ist mindestens die kleinste druckbare FDM-Wand"),
    ]
    decisions = [
        Decision(id="d_drive", title="Antriebsprinzip", choice="Resonanzlauf auf der Bein-Eigenfrequenz",
                 rationale="die passive Dynamik trägt den Schwung → minimaler Energieeinsatz",
                 informed_by=["c_reso"]),
    ]
    return Specification(
        run_id="resostrider",
        idea="ResoStrider — ein resonanzgetriebener, voll druckbarer Vierbeiner für monatelange "
             "autonome Erkundung (Trümmer, andere Himmelskörper) — gegatet gegen Schwung-Resonanz, "
             "inverse Dynamik, dynamische ZMP-Balance, Bein-Reichweite, Aktuator und Festigkeit",
        approach_id="ap_reso", quantities=quantities, components=components, bom=bom,
        steps=steps, constraints=constraints, decisions=decisions,
        gaps=[
            "grok's Roh-Eigenfrequenz (2.4–3.1 Hz) passte nicht zum beschriebenen Bein; die Zahlen sind "
            "auf ein physikalisch konsistentes Bein abgestimmt (Eigenfrequenz ≈ 1.5 Hz, Schritt knapp "
            "darunter) — die Resonanz-Idee bleibt, die Werte sind geerdet.",
            "Die Biegefeder im Beinsegment ist als Geometrie-/Massenträger modelliert; ihre exakte "
            "Federkonstante + Dämpfung (entscheidend für echten Resonanzlauf) ist ein FEM-/Mess-Schritt, "
            "nicht im Closed-Form-Gate.",
            "Der volle Mehrbein-Kontakt-Gang läuft im externen Simulator über die URDF-Brücke; das Gate "
            "prüft die planaren Schwung-/ZMP-Screens, nicht den geschlossenen Geländegang.",
        ],
        claim_ids_used=[c.id for c in resostrider_claims()], produced_by="resostrider",
    )


# ============================================================================================
# 3. ForgeHydra — an air-droppable printable hydraulic system (grok's dream #3)
# ============================================================================================

def forgehydra_claims() -> list:
    return _dfm_claims() + [
        _claim("c_forge", "Ein per Drohne abwerfbares, ultraleichtes druckbares Hydrauliksystem bewegt "
               "schwere Lasten in Trümmern oder Minen, ohne dass ein Bagger antransportiert wird."),
        _claim("c_minihpu", "Eine 24-V-Mini-Hydraulikpumpe liefert ~4 L/min bei bis zu 40 bar."),
        _claim("c_cyl", "Ein 25-mm-Bohrungs-Hydraulikzylinder liefert bei 35 bar ~1700 N Hubkraft."),
    ]


def forgehydra_spec() -> Specification:
    """ForgeHydra — abwerfbares druckbares Hydraulik-Lastmodul. Feuert die Hydraulik-Achsen
    (Zylinderkraft F=p·A, Förderstrom Q=A·v) + 2R-Reichweite + Compute + Festigkeit der gedruckten
    Blöcke. Nur die Druckblöcke/Führungen sind PLA; Zylinder und Pumpe sind Stahl-Kaufteile."""
    quantities = [
        *_dfm_quantities(),
        *_struct_quantities(90.0, 70.0, 50.0, 14.0),
        _d("q_force", "Blocklast (Zylinderreaktion am Halter)", 90.0, "N", "Schlauch-/Ventillast"),
        _d("q_arm", "Biege-Hebelarm Block", 70.0, "mm", "Auskragung"),
        _d("q_b", "Blockbreite / size_y", 50.0, "mm", "Breite b"),
        _d("q_h", "Blockhöhe / size_z", 14.0, "mm", "Höhe h"),
        _d("q_blx", "Grundblock / size_x", 160.0, "mm", "Pumpen-/Ventilblock"),
        _d("q_blbore", "Blockbohrung", 5.0, "mm", "Verschraubung"),
        _d("q_bloff_p", "Blockbohrung +", 70.0, "mm", "+x"),
        _d("q_bloff_n", "Blockbohrung -", -70.0, "mm", "-x"),
        _d("q_segx", "Teleskop-Armsegment / size_x", 280.0, "mm", "Zylinderführung"),
        _d("q_segy", "Armsegment / size_y", 40.0, "mm", "Breite"),
        _d("q_segz", "Armsegment / size_z", 16.0, "mm", "Höhe"),
        _d("q_segbore", "Armsegmentbohrung", 5.0, "mm", "Zylinder-/Gelenkbolzen"),
        _d("q_segoff_p", "Armbohrung +", 125.0, "mm", "+x"),
        _d("q_segoff_n", "Armbohrung -", -125.0, "mm", "-x"),
        # hydraulics: cylinder force
        _gm("q_press", "Systemdruck", 3.5e6, "Pa", ["c_minihpu"], "hydraulic.pressure"),
        _dm("q_boreA", "Kolbenfläche", 4.9e-4, "m^2", "Ø25 mm Zylinder, r=0.0125 m",
            "hydraulic.bore_area"),
        _dm("q_reqF", "geforderte Hubkraft", 1100.0, "N", "schwere Last", "hydraulic.required_force"),
        # hydraulics: pump flow
        _dm("q_vel", "Kolbengeschwindigkeit", 0.05, "m/s", "Hub", "hydraulic.piston_velocity"),
        _gm("q_pump", "Pumpenförderstrom", 6.67e-5, "m^3/s", ["c_minihpu"], "hydraulic.pump_flow"),
        # kinematics: 2R reach of the telescoping arm
        _dm("q_l1", "Armsegment 1", 0.50, "m", "Basis–Knick", "arm.link1_length"),
        _dm("q_l2", "Armsegment 2", 0.45, "m", "Knick–Werkzeug", "arm.link2_length"),
        _dm("q_tx", "Ziel x", 0.70, "m", "Reichweite", "arm.target_x"),
        _dm("q_ty", "Ziel y", 0.40, "m", "Höhe", "arm.target_y"),
        # compute: simple control
        _dm("q_work", "Rechenlast", 1.5, "1", "Druck-/Positionsregelung, INT8-TOPS",
            "compute.workload_tops"),
        _gm("q_chip", "Controller-Spitzenleistung", 4.0, "1", ["c_forge"], "compute.chip_tops"),
        _dm("q_util", "Auslastung", 0.6, "1", "haltbar", "compute.utilisation"),
        _dm("q_ceff", "Effizienz", 5.0, "1", "TOPS/W", "compute.efficiency_tops_per_w"),
        _dm("q_pbud", "Compute-Budget", 10.0, "W", "ESP32+Treiber", "compute.power_budget"),
        _dm("q_iops", "Operationen je Inferenz", 1.0e6, "1", "Regler", "compute.inference_ops"),
        _dm("q_thru", "Durchsatz", 4.0e12, "1", "4 TOPS", "compute.throughput_ops_per_s"),
        _dm("q_period", "Regelschleifen-Periode", 0.01, "s", "100 Hz", "control.period"),
    ]
    components = [
        Component(id="c_block", name="Hydraulik-Grundblock", geometry=_link(
            "q_blx", "q_b", "q_h", "q_blbore", "q_bloff_n", "q_blbore", "q_bloff_p"),
            quantity_ids=["q_blx", "q_b", "q_h", "q_blbore", "q_bloff_p", "q_bloff_n", "q_zero"],
            material_density="q_density"),
        Component(id="c_armseg", name="Teleskop-Armsegment", geometry=_link(
            "q_segx", "q_segy", "q_segz", "q_segbore", "q_segoff_n", "q_segbore", "q_segoff_p"),
            quantity_ids=["q_segx", "q_segy", "q_segz", "q_segbore", "q_segoff_p", "q_segoff_n", "q_zero"],
            material_density="q_density"),
    ]
    bom = [
        BomItem(id="b_block", name="Hydraulik-Grundblock (gedruckt)", role=BomRole.PART, count=1,
                component_id="c_block", domain=BomDomain.MECHANICAL, grounding=["c_forge"]),
        BomItem(id="b_armseg", name="Teleskop-Armsegment (gedruckt)", role=BomRole.PART, count=2,
                component_id="c_armseg", domain=BomDomain.MECHANICAL, grounding=["c_forge"]),
        BomItem(id="b_cyl", name="Hydraulikzylinder Ø25 mm (Stahl, 40 bar)", role=BomRole.PART, count=2,
                domain=BomDomain.MECHANICAL, grounding=["c_cyl"]),
        BomItem(id="b_pump", name="24-V-Mini-Hydraulikpumpe (4 L/min)", role=BomRole.PART, count=1,
                domain=BomDomain.MECHANICAL, grounding=["c_minihpu"]),
        BomItem(id="b_sensors", name="Druck- + Positionssensoren", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC),
        BomItem(id="b_ctrl", name="ESP32 + Motor-Controller", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC),
        BomItem(id="b_batt", name="24-V-LiFePO4-Akku", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC),
        BomItem(id="b_printer", name="3D-Drucker", role=BomRole.TOOL, count=1),
    ]
    steps = [
        Step(id="s1", index=1, action="Grundblock und zwei Teleskop-Armsegmente drucken.",
             uses=["b_printer"], inputs=["b_block", "b_armseg"], outputs=["a_print"],
             check="Blöcke gedruckt, Zylinderführungen maßhaltig.", tool="3D-Drucker",
             quantity_refs=["q_blx"]),
        Step(id="s2", index=2, action="Zylinder in die Führungen, Pumpe an den Block, Sensoren montieren.",
             inputs=["a_print", "b_cyl", "b_pump", "b_sensors"], outputs=["a_mech"],
             check="Zylinder fahren frei; Pumpe angeschlossen."),
        Step(id="s3", index=3, action="ESP32-Controller und Akku verdrahten, Hydraulik entlüften.",
             inputs=["a_mech", "b_ctrl", "b_batt"], outputs=["a_done"],
             check="Zylinderkraft ≥ gefordert; Förderstrom ≥ Kolbenbedarf; Reichweite erfüllt.",
             quantity_refs=["q_press", "q_pump", "q_tx"]),
    ]
    constraints = [
        Constraint(id="k_stress", kind="le", left="q_sigma_peak", right="q_strength",
                   reason="die Spitzenspannung am gedruckten Grundblock bleibt unter der PLA-Festigkeit"),
        Constraint(id="k_wall", kind="ge", left="q_h", right="q_min_wall",
                   reason="die Blockhöhe ist mindestens die kleinste druckbare FDM-Wand"),
    ]
    decisions = [
        Decision(id="d_drop", title="Einsatzform", choice="per Drohne abwerfbar, vor Ort druckbar",
                 rationale="ersetzt den Antransport eines Baggers in unzugänglichem Gelände",
                 informed_by=["c_forge"]),
    ]
    return Specification(
        run_id="forgehydra",
        idea="ForgeHydra — ein per Drohne abwerfbares, ultraleichtes druckbares Hydraulik-Lastmodul "
             "für Trümmer/Minen — gegatet gegen Zylinderkraft, Förderstrom, Reichweite, Compute und die "
             "Festigkeit der gedruckten Blöcke",
        approach_id="ap_forge", quantities=quantities, components=components, bom=bom,
        steps=steps, constraints=constraints, decisions=decisions,
        gaps=[
            "Nur die gedruckten Blöcke/Führungen sind PLA; Zylinder und Pumpe sind Stahl-Kaufteile — "
            "Hydraulik bei 35 bar ist kein Druckteil.",
            "Die Hydraulik-Checks sind statische Kraft-/Flussbilanzen; Druckverlust, Schlauchnachgiebig"
            "keit und Wärme über den Dauerbetrieb sind nicht im Gate.",
            "Der abgeworfene Aufprall (Landestoß) und die Selbst-Aufrichtung nach dem Abwurf sind eine "
            "eigene dynamische Auslegung, hier nicht modelliert.",
        ],
        claim_ids_used=[c.id for c in forgehydra_claims()], produced_by="forgehydra",
    )


#: The three grok-decided visionary specs paired with their claim builders — the runner iterates this.
ALL_VISIONARY_IDEAS = [
    (skyclaw_spec, skyclaw_claims),
    (resostrider_spec, resostrider_claims),
    (forgehydra_spec, forgehydra_claims),
]
