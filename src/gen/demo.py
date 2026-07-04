"""Deterministic capstone demo data (Phase γ-depth §6): a complete specification.

A single, scripted-world specification — a wall-mounted LED shelf bracket — that
carries every depth element: mechanical geometry (with mass), a separate
electronics BOM, claim-backed sourcing, a fastener clearance fit, assembly steps
with tool + torque, and site/environment requirements. Every factual detail is a
VERIFIED claim or a declared/recomputed quantity — nothing invented.

This lives in `gen` (not in tests) so both the CLI capstone demo and the
acceptance test consume the SAME spec — no drift between what is demonstrated and
what is verified. Real data replaces the scripted claims via live α-research, with
no code change.

Language contract (owner directive 2026-06-12, PHASE_DELTA §57): every
human-facing string (claim texts, quantity names, rationales, steps, checks,
decisions, gaps, ideas) is GERMAN; ids, units, formulas stay English, and every
number keeps its source spelling byte-for-byte — GATE γ C-4 checks each grounded
value verbatim against its claim text, so "4.5 mm" must never become "4,5 mm".
"""

from __future__ import annotations

from .uncertainty import combine_standard_uncertainty as _uc
from .dfm import (
    FDM_MIN_HOLE_DIAMETER_MM,
    FDM_NOZZLE_DIAMETER_MM,
    FDM_WALL_PERIMETERS_MIN,
    min_wall_formula,
)
from .tolerance import (
    iso2768_medium_linear_tolerance,
    worst_case_min_clearance_formula,
)
from .mechanics_formulas import rod_inertia_about_end
from .structural import (
    BOLT_SHEAR_COEFFICIENT_88,
    BOLT_UTS_CLASS_88_MPA,
    M4_TENSILE_STRESS_AREA_MM2,
    STANDARD_GRAVITY,
    STRESS_CONCENTRATION_CIRCULAR_HOLE,
    bolt_shear_capacity_formula,
    cantilever_bending_stress_formula,
    peak_stress_formula,
    per_fastener_shear_formula,
    weight_formula,
)
from .core.state import (
    Approach,
    BomDomain,
    BomItem,
    BomRole,
    Claim,
    ClaimStatus,
    CodeArtifact,
    Component,
    Constraint,
    Decision,
    Derivation,
    ExperimentDesign,
    GeometryNode,
    Net,
    Netlist,
    Pin,
    PinType,
    Question,
    Quantity,
    RunState,
    SiteRequirements,
    Sourcing,
    SourceRef,
    SourceSupport,
    Specification,
    Step,
    ValueOrigin,
)


def _claim(cid: str, text: str) -> Claim:
    return Claim(
        id=cid, text=text,
        sources=[SourceRef(f"https://{cid}", True, support=SourceSupport.SUPPORTS)],
        status=ClaimStatus.VERIFIED, confidence=0.95,
        verification=[SourceRef(f"https://i/{cid}", True, support=SourceSupport.SUPPORTS)],
    )


def capstone_claims() -> list[Claim]:
    return [
        _claim("c_anchor", "Kragarm-Halterungen werden für wandmontierte LED-Regale verwendet."),
        _claim("c_load", "Ein typisches Wandregal muss eine Last von 12 kg tragen."),
        _claim("c_screw", "Eine M4-Schraube hat einen Nenndurchmesser von 4 mm."),
        _claim("c_iso273",
               "ISO 273 legt für eine M4-Schraube einen mittleren "
               "Durchgangsloch-Durchmesser von 4.5 mm fest."),
        _claim("c_led", "Der LED-Streifen läuft mit 12 V und zieht 1.5 A."),
        _claim("c_psu", "Das Netzteil liefert 12 V bei bis zu 2 A."),
        _claim("c_src", "McMaster-Carr führt das Teil 91290A115, eine M4x16-Innensechskantschraube."),
        _claim("c_price",
               "Die M4x16-Innensechskantschraube kostet bei McMaster-Carr 0.42 EUR pro Stück."),
        _claim("c_gravity", "Die Normfallbeschleunigung ist definiert als 9.80665 m/s^2."),
        _claim("c_pla",
               "FDM-gedrucktes PLA, in der Druckebene belastet (entlang der "
               "Druckschichten), hat eine Zugfestigkeit von etwa 50 MPa."),
        _claim("c_kirsch",
               "Ein kreisrundes Loch in einer Platte unter Zug hat einen "
               "Spannungskonzentrationsfaktor von 3 (Kirsch-Lösung)."),
        _claim("c_screw_class",
               "Eine Schraube der Festigkeitsklasse 8.8 nach ISO 898-1 hat eine "
               "Zugfestigkeit von 800 MPa."),
        _claim("c_screw_area",
               "Eine M4-Schraube mit Regelgewinde hat einen Spannungsquerschnitt "
               "von 8.78 mm^2."),
        _claim("c_screw_shear",
               "EN 1993-1-8 gibt für Schrauben der Festigkeitsklasse 8.8 einen "
               "Abscherbeiwert von 0.6 an."),
        _claim("c_iso2768",
               "ISO 2768-1 Klasse m legt für ein Längenmaß über 3 bis 6 mm eine "
               "Allgemeintoleranz von 0.1 mm fest."),
        _claim("c_fdm_nozzle", "Eine Standard-FDM-Düse hat 0.4 mm Durchmesser."),
        _claim("c_fdm_wall",
               "Eine FDM-Wand sollte mindestens 2 Perimeterlinien breit sein, um "
               "zuverlässig zu drucken."),
        _claim("c_fdm_hole",
               "Das kleinste zuverlässig druckbare horizontale Loch im FDM-Druck "
               "hat 2.0 mm Durchmesser."),
    ]


def _g(qid, name, value, unit, grounding, unc=None):
    return Quantity(id=qid, name=name, value=value, unit=unit,
                    origin=ValueOrigin.GROUNDED, grounding=grounding, uncertainty=unc)


def _d(qid, name, value, unit, rationale, unc=None):
    return Quantity(id=qid, name=name, value=value, unit=unit,
                    origin=ValueOrigin.DECISION, rationale=rationale, uncertainty=unc)


def _der(qid, name, value, unit, formula, inputs, unc=None):
    return Quantity(id=qid, name=name, value=value, unit=unit,
                    origin=ValueOrigin.DERIVED,
                    derivation=Derivation(formula=formula, inputs=inputs), uncertainty=unc)


def capstone_spec() -> Specification:
    # GUM uncertainty chain (JCGM 100): the shelf load is a declared Type-B
    # estimate (~5 %), and that uncertainty propagates deterministically all the
    # way to the peak stress. Each derived uncertainty is computed with the SAME
    # combiner GATE γ C-18 uses to recompute it — so they match by construction.
    _u_load = 0.6
    _u_design = _uc("q_load * q_sf", {"q_load": 12.0, "q_sf": 2.0}, {"q_load": _u_load})
    _u_force = _uc(weight_formula("q_design", "q_g"),
                   {"q_design": 24.0, "q_g": STANDARD_GRAVITY}, {"q_design": _u_design})
    _snom_val = 6.0 * (24.0 * STANDARD_GRAVITY) * 60.0 / (80.0 * 12.0 * 12.0)
    _u_snom = _uc(cantilever_bending_stress_formula("q_force", "q_w", "q_h", "q_t"),
                  {"q_force": 24.0 * STANDARD_GRAVITY, "q_w": 60.0, "q_h": 80.0, "q_t": 12.0},
                  {"q_force": _u_force})
    _u_speak = _uc(peak_stress_formula("q_sigma_nom", "q_kt"),
                   {"q_sigma_nom": _snom_val, "q_kt": STRESS_CONCENTRATION_CIRCULAR_HOLE},
                   {"q_sigma_nom": _u_snom})
    quantities = [
        _g("q_load", "belegte Regallast", 12.0, "kg", ["c_load"], _u_load),
        _g("q_screw_d", "Schraubendurchmesser", 4.0, "mm", ["c_screw"]),
        _g("q_hole_d", "Durchgangsloch-Durchmesser", 4.5, "mm", ["c_iso273"]),
        _d("q_sf", "Sicherheitsfaktor", 2.0, "1", "konservativ für statische Innenraumlast"),
        _der("q_design", "Auslegungslast", 24.0, "kg", "q_load * q_sf", ("q_load", "q_sf"),
             _u_design),
        _der("q_hole_r", "Lochradius", 2.25, "mm", "q_hole_d / 2", ("q_hole_d",)),
        _d("q_w", "Halter-Auskragung", 60.0, "mm",
           "Regaltiefe ab der Wand — der Hebelarm der Last (L)"),
        _d("q_h", "Halter-Breite", 80.0, "mm",
           "Breite entlang der Wand — die Breite b des Biegequerschnitts"),
        _d("q_t", "Halter-Dicke", 12.0, "mm",
           "Querschnittshöhe in Lastrichtung (h); so dimensioniert, dass die "
           "Spitzenspannung am Loch bei Auslegungslast unter der PLA-Festigkeit "
           "in der Druckebene bleibt"),
        _d("q_density", "PLA-Dichte", 0.00124, "g/mm^3", "PLA ~1.24 g/cm³, je mm³ ausgedrückt"),
        _g("q_led_v", "LED-Spannung", 12.0, "V", ["c_led"]),
        _g("q_led_a", "LED-Strom", 1.5, "A", ["c_led"]),
        _g("q_psu_v", "Netzteil-Spannung", 12.0, "V", ["c_psu"]),
        _g("q_psu_a", "Netzteil-Strom", 2.0, "A", ["c_psu"]),
        _d("q_fw_current_limit", "Firmware-Strombegrenzung", 1.5, "A",
           "der led_resistance-Helfer arbeitet am LED-Nennstrom (1,5 A); die "
           "Firmware-Seite der Code↔Elektrik-Naht darf nie mehr ziehen, als das "
           "Netzteil liefert (Phase-ε-Pflichtpaar ELECTRICAL–FIRMWARE)"),
        _d("q_torque", "Schrauben-Anzugsmoment", 2.5, "N*m", "M4 in Kunststoff, handfest"),
        _g("q_price", "Schrauben-Stückpreis", 0.42, "EUR", ["c_price"]),
        # δ-layer-2 statics: does the bracket hold the verified load — counting the
        # safety factor, the mount-hole stress raiser, the print orientation, and
        # the fastener shear? Each value is grounded (g, Kt, strength, screw specs)
        # or recomputed (force, stress, capacity); GENESIS does the arithmetic
        # (verification/derivation.py), GATE γ recomputes it (C-6), checks it
        # dimensionally (C-15), and tests every verdict numerically (C-13).
        _g("q_g", "Normfallbeschleunigung", STANDARD_GRAVITY, "m/s^2", ["c_gravity"]),
        _der("q_force", "Auslegungskraft an der Halterspitze",
             24.0 * STANDARD_GRAVITY, "N",
             weight_formula("q_design", "q_g"), ("q_design", "q_g"), _u_force),
        _der("q_sigma_nom", "nominale Biegespannung bei Auslegungslast "
             "(Kragarm, Arm=q_w, b=q_h, h=q_t)",
             6.0 * (24.0 * STANDARD_GRAVITY) * 60.0 / (80.0 * 12.0 * 12.0), "MPa",
             cantilever_bending_stress_formula("q_force", "q_w", "q_h", "q_t"),
             ("q_force", "q_w", "q_h", "q_t"), _u_snom),
        _g("q_kt", "Spannungskonzentrationsfaktor (kreisrundes Loch, Kirsch)",
           STRESS_CONCENTRATION_CIRCULAR_HOLE, "1", ["c_kirsch"]),
        _der("q_sigma_peak", "Spitzenspannung am Befestigungsloch",
             STRESS_CONCENTRATION_CIRCULAR_HOLE
             * (6.0 * (24.0 * STANDARD_GRAVITY) * 60.0 / (80.0 * 12.0 * 12.0)), "MPa",
             peak_stress_formula("q_sigma_nom", "q_kt"), ("q_kt", "q_sigma_nom"), _u_speak),
        _g("q_strength", "PLA-Zugfestigkeit in der Druckebene", 50.0, "MPa", ["c_pla"]),
        # fastener shear (bracket-side, EN 1993-1-8): demand per screw vs capacity
        _g("q_bolt_uts", "Zugfestigkeit der Schraube (Klasse 8.8)",
           BOLT_UTS_CLASS_88_MPA, "MPa", ["c_screw_class"]),
        _g("q_bolt_area", "Spannungsquerschnitt M4",
           M4_TENSILE_STRESS_AREA_MM2, "mm^2", ["c_screw_area"]),
        _g("q_shear_coeff", "Abscherbeiwert EN 1993-1-8 (Klasse 8.8)",
           BOLT_SHEAR_COEFFICIENT_88, "1", ["c_screw_shear"]),
        _der("q_screw_shear_cap", "Abschertragfähigkeit je Schraube",
             BOLT_SHEAR_COEFFICIENT_88 * BOLT_UTS_CLASS_88_MPA
             * M4_TENSILE_STRESS_AREA_MM2, "N",
             bolt_shear_capacity_formula("q_shear_coeff", "q_bolt_uts", "q_bolt_area"),
             ("q_shear_coeff", "q_bolt_uts", "q_bolt_area")),
        _d("q_n_screws", "Anzahl der Befestigungsschrauben", 2.0, "1",
           "zwei Befestigungsschrauben (entspricht Stücklisten-Position b_screw)"),
        _der("q_screw_shear", "Scherbeanspruchung je Schraube bei Auslegungslast",
             (24.0 * STANDARD_GRAVITY) / 2.0, "N",
             per_fastener_shear_formula("q_force", "q_n_screws"),
             ("q_force", "q_n_screws")),
        # δ-tolerance: worst-case fit. With ISO 2768-1 m general tolerances on the
        # hole and the screw, does the clearance hole still admit the screw at the
        # WORST extreme (largest screw, smallest hole)? Deterministic stack-up.
        _g("q_hole_tol", "Allgemeintoleranz Loch (ISO 2768-1 m)",
           iso2768_medium_linear_tolerance(4.5), "mm", ["c_iso2768"]),
        _g("q_screw_tol", "Allgemeintoleranz Schraube (ISO 2768-1 m)",
           iso2768_medium_linear_tolerance(4.0), "mm", ["c_iso2768"]),
        _der("q_min_clearance", "Worst-Case-Mindestspiel (Loch über Schraube)",
             (4.5 - iso2768_medium_linear_tolerance(4.5))
             - (4.0 + iso2768_medium_linear_tolerance(4.0)), "mm",
             worst_case_min_clearance_formula("q_hole_d", "q_hole_tol",
                                              "q_screw_d", "q_screw_tol"),
             ("q_hole_d", "q_hole_tol", "q_screw_d", "q_screw_tol")),
        # δ-DFM: is the part printable? minimum wall = 2 perimeters of a 0.4 mm
        # nozzle; minimum printable hole 2.0 mm. Deterministic, grounded rules.
        _g("q_nozzle", "FDM-Düsendurchmesser", FDM_NOZZLE_DIAMETER_MM, "mm", ["c_fdm_nozzle"]),
        _g("q_perimeters", "Mindestzahl Wand-Perimeter", FDM_WALL_PERIMETERS_MIN, "1",
           ["c_fdm_wall"]),
        _der("q_min_wall", "kleinste druckbare Wanddicke",
             FDM_WALL_PERIMETERS_MIN * FDM_NOZZLE_DIAMETER_MM, "mm",
             min_wall_formula("q_nozzle", "q_perimeters"), ("q_nozzle", "q_perimeters")),
        _g("q_min_hole", "kleinster druckbarer Lochdurchmesser", FDM_MIN_HOLE_DIAMETER_MM, "mm",
           ["c_fdm_hole"]),
        _d("sx", "verfügbare Breite", 200.0, "mm", "Breite der Regalnische"),
        _d("sy", "verfügbare Höhe", 200.0, "mm", "Höhe der Regalnische"),
        _d("sz", "verfügbare Tiefe", 200.0, "mm", "Tiefe der Regalnische"),
    ]
    geometry = GeometryNode(kind="difference", children=[
        GeometryNode(kind="box", params={"size_x": "q_w", "size_y": "q_h", "size_z": "q_t"}),
        GeometryNode(kind="cylinder", params={"radius": "q_hole_r", "height": "q_t"}),
    ])
    components = [
        Component(id="c_bracket", name="Halter", geometry=geometry,
                  quantity_ids=["q_w", "q_h", "q_t", "q_hole_d", "q_hole_r"],
                  material_density="q_density"),
    ]
    bom = [
        BomItem(id="b_bracket", name="Halter", role=BomRole.PART, count=1,
                component_id="c_bracket", domain=BomDomain.MECHANICAL),
        BomItem(id="b_screw", name="M4x16-Innensechskantschraube", role=BomRole.PART, count=2,
                domain=BomDomain.MECHANICAL, grounding=["c_screw"],
                sourcing=Sourcing(supplier="McMaster-Carr", part_number="91290A115",
                                  price_quantity_id="q_price", grounding=["c_src", "c_price"])),
        BomItem(id="b_led", name="12-V-LED-Streifen", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC, grounding=["c_led"]),
        BomItem(id="b_psu", name="Netzteil 12 V / 2 A", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC, grounding=["c_psu"]),
        BomItem(id="b_printer", name="3D-Drucker", role=BomRole.TOOL, count=1),
        BomItem(id="b_hex", name="4-mm-Innensechskantschlüssel", role=BomRole.TOOL, count=1),
    ]
    steps = [
        Step(id="s1", index=1, action="Den Halter gemäß seiner CSG-Geometrie 3D-drucken.",
             uses=["b_printer"], inputs=["b_bracket"], outputs=["a_printed"],
             check="Das gedruckte Teil misst 60 x 80 x 12 mm innerhalb der Toleranz.",
             tool="3D-Drucker", quantity_refs=["q_w", "q_h", "q_t"]),
        Step(id="s2", index=2, action="Den Halter mit beiden Schrauben an der Wand montieren.",
             uses=["b_hex", "b_screw"], inputs=["a_printed"], outputs=["a_mounted"],
             check="Der Halter trägt die Auslegungslast ohne Bewegung.",
             tool="4-mm-Innensechskantschlüssel", torque_quantity_id="q_torque",
             quantity_refs=["q_design"]),
        Step(id="s3", index=3, action="Den LED-Streifen anbringen und das Netzteil anschließen.",
             uses=["b_led", "b_psu"], inputs=["a_mounted"], outputs=["a_done"],
             check="Die LED leuchtet bei 12 V; der Versorgungsstrom bleibt innerhalb "
                   "der 2-A-Nennleistung.",
             quantity_refs=["q_led_v", "q_psu_a"]),
    ]
    constraints = [
        Constraint(id="k_fit", kind="ge", left="q_hole_d", right="q_screw_d",
                   reason="das Durchgangsloch lässt die Schraube durch"),
        Constraint(id="k_volt", kind="eq", left="q_led_v", right="q_psu_v",
                   reason="die Versorgungsspannung muss zum LED-Streifen passen"),
        Constraint(id="k_curr", kind="ge", left="q_psu_a", right="q_led_a",
                   reason="der Versorgungsstrom muss den LED-Bedarf decken"),
        Constraint(id="k_dfm_wall", kind="ge", left="q_t", right="q_min_wall",
                   reason="der Querschnitt ist mindestens die kleinste druckbare "
                          "FDM-Wand (zwei Perimeter einer 0.4-mm-Düse)"),
        Constraint(id="k_dfm_hole", kind="ge", left="q_hole_d", right="q_min_hole",
                   reason="das Durchgangsloch ist mindestens der kleinste zuverlässig "
                          "druckbare FDM-Lochdurchmesser"),
        Constraint(id="k_stress", kind="le", left="q_sigma_peak", right="q_strength",
                   reason="die Spitzenspannung am Loch bei Auslegungslast (Kt·σ_nom) "
                          "bleibt unter der PLA-Festigkeit in der Druckebene — "
                          "notwendig, nicht hinreichend"),
        Constraint(id="k_shear", kind="le", left="q_screw_shear", right="q_screw_shear_cap",
                   reason="die Scherbeanspruchung je Schraube bei Auslegungslast bleibt "
                          "unter der Abschertragfähigkeit der Klasse-8.8-Schraube "
                          "(halterseitige Verbindungsgrenze)"),
        Constraint(id="k_assemble", kind="ge", left="q_min_clearance", right="0",
                   reason="das Worst-Case-Mindestspiel bleibt nicht-negativ — das Loch "
                          "lässt die Schraube auch am ungünstigsten Toleranzextrem durch"),
    ]
    decisions = [
        Decision(id="d_mat", title="Material", choice="PLA, 3D-gedruckt",
                 rationale="verfügbar; ausreichend für statische Innenraumlast"),
        Decision(id="d_hole", title="Lochtyp",
                 choice="Durchgangsloch (ISO 273 mittel)",
                 rationale="die Schraube geht durch den Halter hindurch", informed_by=["c_iso273"]),
        Decision(id="d_tol", title="Allgemeintoleranzklasse",
                 choice="ISO 2768-1 mittel (m)",
                 rationale="übliche Werkstatt-Toleranz; bestimmt die Allgemeintoleranzen "
                           "von Loch und Schraube für die Worst-Case-Passungsprüfung",
                 informed_by=["c_iso2768"]),
        Decision(id="d_print", title="Druck-Orientierung",
                 choice="hochkant — Druckschichten parallel zur Biegespannung",
                 rationale="FDM-Schichtverbindungen sind ~30-50% schwächer als die "
                           "Druckebene; mit den Schichten in der Lastebene trägt die "
                           "belastete Richtung die höhere Festigkeit, die auch die "
                           "Spannungsprüfung ansetzt",
                 informed_by=["c_pla"]),
    ]
    site = SiteRequirements(
        available_space=("sx", "sy", "sz"),
        requirements=[
            Decision(id="d_loc", title="Ort", choice="innen, trockene Wand",
                     rationale="die Elektronik ist nicht wetterfest"),
            Decision(id="d_vent", title="Belüftung",
                     choice="passiv, 5 cm Freiraum über dem Netzteil",
                     rationale="Abwärme des Netzteils abführen"),
        ],
    )
    # software deliverable: a tiny helper that computes the LED operating-point
    # resistance the DC analysis uses. GATE CODE proves it correct by EXECUTION
    # (the machine runs the check), the strongest deterministic validator.
    code_artifacts = [
        CodeArtifact(
            id="ca_led_r", name="led_resistance", language="python",
            description="Arbeitspunkt-Widerstand R = V / I des LED-Streifens",
            source=(
                "def led_resistance(volts, amps):\n"
                "    '''Operating-point resistance of a load drawing `amps` at `volts`.'''\n"
                "    if amps <= 0:\n"
                "        raise ValueError('current must be positive')\n"
                "    return volts / amps\n"
            ),
            check=(
                "assert led_resistance(12, 1.5) == 8.0\n"
                "assert led_resistance(12, 2) == 6.0\n"
                "try:\n"
                "    led_resistance(12, 0); raise SystemExit('no guard')\n"
                "except ValueError:\n"
                "    pass\n"
            ),
        ),
    ]
    # electrical netlist: the PSU drives the LED strip over a 12 V rail + ground.
    # The deterministic ERC (gate_erc) proves the wiring is sound — no SPICE.
    netlist = Netlist(
        pins=[
            Pin(part="b_psu", name="V+", type=PinType.POWER_OUT),
            Pin(part="b_psu", name="GND", type=PinType.GROUND),
            Pin(part="b_led", name="V+", type=PinType.POWER_IN),
            Pin(part="b_led", name="GND", type=PinType.GROUND),
        ],
        nets=[
            Net(name="VCC_12V", pins=["b_psu.V+", "b_led.V+"]),
            Net(name="GND", pins=["b_psu.GND", "b_led.GND"]),
        ],
    )
    spec = Specification(
        run_id="capstone",
        idea="Ein wandmontierter LED-Regalhalter, der die belegte Last trägt",
        approach_id="ap1", quantities=quantities, components=components, bom=bom,
        steps=steps, constraints=constraints, decisions=decisions, site=site,
        netlist=netlist, code_artifacts=code_artifacts,
        gaps=[
            # The σ-check now counts the safety factor, the Kirsch hole stress raiser,
            # the print orientation and the fastener shear. What honestly remains is
            # external or declared-out — narrowed, not a blanket disclaimer.
            "Der AUSZUG der Schrauben aus der Wand ist nicht geprüft — er hängt vom "
            "Wanduntergrund und Dübel ab (Gipskartondübel vs Beton vs Holz), den die "
            "Spezifikation nicht festlegt; geprüft ist nur der halterseitige "
            "Schrauben-Abschub.",
            "Die Lochspannung nutzt das konservative Kirsch-Kt=3 (einachsig, "
            "kreisrundes Loch). Das kanonische Zug-Kt wird inzwischen von der "
            "3-D-FEM BERECHNET (plate_hole.py: ~3.1, Kirsch 3 + endliche Breite); "
            "der konkrete Biegung+Loch-Fall des Halters ist eine direkte "
            "Erweiterung desselben Lösers.",
            "Ermüdung und dynamische / stoßartige Lasten sind durch den erklärten "
            "statischen Innenraum-Lastfall außerhalb des Geltungsbereichs; geprüft "
            "ist nur die statische Auslegungslast (Sicherheitsfaktor 2).",
            "Die 50 MPa Festigkeit in der Druckebene setzen einen guten Druck "
            "(hohe Füllung, korrekte Temperatur) in der erklärten "
            "Hochkant-Orientierung voraus; ein schlechter oder falsch orientierter "
            "Druck ist schwächer.",
            "Überhang/Stützmaterial ist orientierungsabhängig und wird separat "
            "geprüft (orientation.overhang_check über das BREP): flach gedruckt "
            "(+Z) braucht der Halter keine Stützen; auf der Seite gedruckt hängt "
            "das Loch über. Brückenspannweiten und Stützvolumen-Kosten sind noch "
            "nicht modelliert.",
        ],
        claim_ids_used=[c.id for c in capstone_claims()], produced_by="capstone",
    )
    # Phase-ε seam: firmware and electronics are BOTH present (code_artifacts +
    # netlist), so the ELECTRICAL–FIRMWARE coupling is a required pair — the demo
    # declares it honestly instead of shipping an uncertified seam: the firmware
    # current cap must stay under the PSU capacity (1.5 A <= 2.0 A, dimensional,
    # machine-checked by gate_epsilon). build_seam_certificate auto-adds the
    # COST_ROLLUP seam for the priced BOM.
    from dataclasses import replace as _replace

    from .seams import DomainSeam, SeamDomain, SeamRelation, build_seam_certificate
    fw_seam = DomainSeam(
        id="s_fw_strom",
        left_domain=SeamDomain.FIRMWARE,
        right_domain=SeamDomain.ELECTRICAL,
        relation=SeamRelation.LE,
        left_expr="q_fw_current_limit",
        right_expr="q_psu_a",
        rationale="Die Firmware-Strombegrenzung (LED-Nennstrom 1,5 A) muss unter der "
                  "Netzteil-Kapazität (2,0 A) bleiben — die deklarierte Code↔Elektrik-Naht.",
    )
    return _replace(spec, seam_certificate=build_seam_certificate(spec, [fw_seam]))


def capstone_state() -> RunState:
    """The full RunState (claims + approach + spec) for gate verification."""
    st = RunState(question=Question(raw="led shelf bracket", run_id="capstone"))
    st.claims = capstone_claims()
    st.approaches = [Approach(id="ap1", name="Kragarm-LED-Halter", grounding=["c_anchor"])]
    st.specification = capstone_spec()
    return st


# --- bio ε domain: a reproducibility-sound plant-growth protocol ----------------
# Realizes the VISION example ("how can plants be shown to grow better?") across a
# completely different domain than the bracket — the same γ machinery (sourced
# values, safety-limit constraint via C-13, units via C-15) plus the bio-specific
# reproducibility design gate (gate_protocol): a measured outcome with a control
# group and enough replicates. Nothing invented; the safety limit is claim-backed.
# (Biology kept per user correction: "doch Biologie kann drin bleiben")

def protocol_claims() -> list[Claim]:
    return [
        _claim("c_bio_anchor",
               "Kontrollierte Nährstoffdosierung wird zur Untersuchung des "
               "Pflanzenwachstums eingesetzt."),
        _claim("c_bio_tox",
               "Die Nährlösung ist oberhalb von 200 g/m^3 phytotoxisch."),
    ]


def protocol_spec() -> Specification:
    quantities = [
        _d("q_conc", "aufgebrachte Nährstoffkonzentration", 150.0, "g/m^3",
           "unterhalb der toxischen Schwelle, im wirksamen Bereich"),
        _g("q_conc_max", "Phytotoxizitätsschwelle", 200.0, "g/m^3", ["c_bio_tox"]),
    ]
    steps = [
        Step(id="p1", index=1, action="Die Nährlösung in der Zieldosis ansetzen.",
             outputs=["a_solution"], check="Konzentration gemessen bei 150 g/m^3.",
             quantity_refs=["q_conc"]),
        Step(id="p2", index=2, action="Die Lösung auf die Behandlungsgruppe aufbringen; "
             "die Kontrollgruppe nur wässern.", inputs=["a_solution"], outputs=["a_dosed"],
             check="Jede Pflanze erhält das gleiche Volumen."),
        Step(id="p3", index=3, action="Die Stängelhöhe nach 14 Tagen messen.",
             inputs=["a_dosed"], outputs=["a_data"],
             check="Stängelhöhe je Pflanze erfassen, blind zur Gruppe."),
    ]
    constraints = [
        Constraint(id="k_safe", kind="le", left="q_conc", right="q_conc_max",
                   reason="die aufgebrachte Dosis bleibt unter der Phytotoxizitätsschwelle"),
    ]
    experiment = ExperimentDesign(
        measured="Stängelhöhe", groups=["Behandlung", "Kontrolle"],
        control="Kontrolle", replicates=5,
    )
    return Specification(
        run_id="protocol", idea="Zeigen, ob Nährstoffdosierung das Pflanzenwachstum steigert",
        approach_id="ap_bio", quantities=quantities, steps=steps, constraints=constraints,
        experiment=experiment,
        decisions=[Decision(id="d_blind", title="Verblindung",
                            choice="blind zur Gruppe messen",
                            rationale="beseitigt Mess-Bias")],
        gaps=[
            "Effektstärke, Dosis-Wirkung jenseits der einen getesteten Dosis und "
            "Feld- (vs. kontrollierte) Bedingungen werden nicht behauptet — sie "
            "erfordern den tatsächlichen Versuchslauf, den GENESIS spezifiziert, "
            "aber nicht durchführt.",
        ],
        claim_ids_used=[c.id for c in protocol_claims()], produced_by="protocol",
    )


def protocol_state() -> RunState:
    st = RunState(question=Question(raw="plant growth protocol", run_id="protocol"))
    st.claims = protocol_claims()
    st.approaches = [Approach(id="ap_bio", name="Kontrollierte Nährstoffdosierung",
                             grounding=["c_bio_anchor"])]
    st.specification = protocol_spec()
    return st


# --- delta mechanical domain: a load-bearing part the physics validators fit -----
# The bracket is a STATIC flat part whose stress/shear are already checked by the
# gamma constraints; the delta-physics validators (torsion, fatigue, resonance, ...)
# do not apply to it. This second spec is a part where they DO: a rotating drive
# shaft, with quantities tagged by `measurand` so physics_selection auto-builds the
# applicable checks and gate_delta_physics returns one verdict end to end. Material
# properties are grounded in claims (as the bracket's are); the engineering inputs
# (torque, diameter, speeds) are declared design choices.

def drive_shaft_claims() -> list[Claim]:
    return [
        _claim("c_shaft_anchor",
               "Rotierende Antriebswellen übertragen Drehmoment zwischen "
               "Maschinenelementen."),
        _claim("c_steel_g", "Baustahl hat einen Schubmodul von etwa 80 GPa."),
        _claim("c_steel_tau",
               "AISI-1045-Stahl mit mittlerem Kohlenstoffgehalt hat eine "
               "Scherfestigkeit von etwa 260 MPa."),
        _claim("c_steel_uts",
               "Kaltgezogener AISI-1045-Stahl hat eine Zugfestigkeit von etwa "
               "585 MPa."),
        _claim("c_steel_se",
               "AISI-1045-Stahl hat eine Biege-Dauerfestigkeit von etwa 290 MPa."),
    ]


def _gm(qid, name, value, unit, grounding, measurand):
    return Quantity(id=qid, name=name, value=value, unit=unit,
                    origin=ValueOrigin.GROUNDED, grounding=grounding, measurand=measurand)


def _dm(qid, name, value, unit, rationale, measurand):
    return Quantity(id=qid, name=name, value=value, unit=unit,
                    origin=ValueOrigin.DECISION, rationale=rationale, measurand=measurand)


def drive_shaft_spec() -> Specification:
    quantities = [
        # torsion: a rated torque twisting a steel shaft of chosen size
        _dm("q_torque", "übertragenes Drehmoment", 150.0, "N*m",
            "Nenn-Antriebsmoment (in N*m deklariert, um die Einheitenumrechnung "
            "nach N*mm zu beweisen)",
            "shaft.torque"),
        _dm("q_shaft_d", "Wellendurchmesser", 25.0, "mm", "gewählte Wellengröße",
            "shaft.diameter"),
        _dm("q_shaft_L", "Wellenlänge zwischen den Lagern", 600.0, "mm",
            "Lagerabstand", "shaft.length"),
        _gm("q_steel_g", "Schubmodul Stahl", 80000.0, "MPa", ["c_steel_g"],
            "material.shear_modulus"),
        _gm("q_steel_tau", "Scherfestigkeit Stahl", 260.0, "MPa", ["c_steel_tau"],
            "material.shear_strength"),
        # rotating-bending fatigue: an alternating bending stress on the spinning shaft
        _dm("q_bend_amp", "Umlaufbiegung: Spannungsamplitude", 80.0, "MPa",
            "wechselnde Biegung an der Lastspanne", "fatigue.stress_amplitude"),
        _dm("q_bend_mean", "mittlere (statische) Spannung", 20.0, "MPa",
            "statischer Spannungsanteil", "fatigue.mean_stress"),
        _gm("q_steel_uts", "Zugfestigkeit Stahl", 585.0, "MPa", ["c_steel_uts"],
            "material.uts"),
        _gm("q_steel_se", "Dauerfestigkeit Stahl", 290.0, "MPa", ["c_steel_se"],
            "material.endurance_limit"),
        # whirl resonance: keep the first whirl mode well above the running speed
        _dm("q_op_speed", "Betriebsdrehfrequenz", 50.0, "Hz",
            "3000 rpm = 50 Hz", "vibration.excitation_frequency"),
        _dm("q_whirl", "erste biegekritische Drehzahl (Whirl)", 150.0, "Hz",
            "erste Lateral-/Whirl-Mode, 3x über der Betriebsdrehzahl gehalten",
            "vibration.first_natural_frequency"),
    ]
    return Specification(
        run_id="drive_shaft",
        idea="Eine rotierende Antriebswelle, ausgelegt gegen Torsion, "
             "Umlaufbiegungs-Ermüdung und Whirl-Resonanz",
        approach_id="ap_shaft", quantities=quantities,
        gaps=[
            "Spannungskonzentrationen an Passfedernut / Wellenabsatz sind in den "
            "Nominal-Prüfungen nicht modelliert — separat einen "
            "Ermüdungs-Kerbfaktor K_f ansetzen (notch_fatigue).",
            "Lagerlebensdauer, Kupplung und Welle-Nabe-Verbindung sind außerhalb "
            "des Geltungsbereichs; geprüft sind nur Torsion, Ermüdung und Whirl "
            "des Wellenkörpers.",
        ],
        claim_ids_used=[c.id for c in drive_shaft_claims()], produced_by="drive_shaft",
    )


def drive_shaft_state() -> RunState:
    st = RunState(question=Question(raw="rotating drive shaft", run_id="drive_shaft"))
    st.claims = drive_shaft_claims()
    st.approaches = [Approach(id="ap_shaft", name="Rotierende Antriebswelle",
                             grounding=["c_shaft_anchor"])]
    st.specification = drive_shaft_spec()
    return st


# --- delta robot domain: a printable humanoid knee-actuator mount ----------------
# The bracket is a static shelf part; the drive shaft is a rotating body with NO
# geometry. This third complete spec is a ROBOT part that carries BOTH at once: a
# printable CSG body (so it emits a real STL + BOM + Markdown build manual, exactly
# like the bracket) AND measurand-tagged quantities that auto-fire the robot
# delta-physics axes — electric_actuator (does the knee gearmotor hold the joint
# torque through its reduction?) and reach (does the 2R thigh+shank leg the mount
# serves reach its foot target?) — PLUS the gamma structural chain (does the printed
# mount itself hold the leg load in bending at the pivot, counting the hole stress
# raiser?). One coherent part, gated end to end. This is the spec that closes the
# "robot has no buildable artifact" gap: it drives the same machinery the bracket does.

def knee_mount_claims() -> list[Claim]:
    return [
        _claim("c_knee_anchor",
               "Eine Gelenkhalterung verbindet den Aktuator mit dem Strukturrohr eines "
               "humanoiden Beins und überträgt das Knie-Gelenkmoment."),
        _claim("c_knee_load",
               "Das Bein-Strukturteil eines leichten Humanoiden trägt eine statische "
               "Auslegungslast von 20 kg (anteiliges Körpergewicht)."),
        _claim("c_gravity", "Die Normfallbeschleunigung ist definiert als 9.80665 m/s^2."),
        _claim("c_pla",
               "FDM-gedrucktes PLA, in der Druckebene belastet (entlang der "
               "Druckschichten), hat eine Zugfestigkeit von etwa 50 MPa."),
        _claim("c_kirsch",
               "Ein kreisrundes Loch in einer Platte unter Zug hat einen "
               "Spannungskonzentrationsfaktor von 3 (Kirsch-Lösung)."),
        _claim("c_knee_motor",
               "Ein bürstenloser Robotik-Gelenkmotor der NEMA-23-Klasse liefert ein "
               "Haltemoment (Stall) von etwa 2.0 N*m vor der Untersetzung."),
        _claim("c_fdm_nozzle", "Eine Standard-FDM-Düse hat 0.4 mm Durchmesser."),
        _claim("c_fdm_wall",
               "Eine FDM-Wand sollte mindestens 2 Perimeterlinien breit sein, um "
               "zuverlässig zu drucken."),
        _claim("c_fdm_hole",
               "Das kleinste zuverlässig druckbare horizontale Loch im FDM-Druck hat "
               "2.0 mm Durchmesser."),
        _claim("c_bolt_src",
               "McMaster-Carr führt das Teil 91290A115, eine M4x16-Innensechskantschraube."),
        _claim("c_bolt_price",
               "Die M4x16-Innensechskantschraube kostet bei McMaster-Carr 0.42 EUR pro Stück."),
        _claim("c_bearing_price",
               "Ein Rillenkugellager 6800-2RS (10 mm Bohrung) kostet etwa 3.50 EUR pro Stück."),
    ]


def knee_mount_spec() -> Specification:
    quantities = [
        # gamma statics: does the printed mount hold the leg load in bending at the
        # pivot hole? Same chain the bracket uses (force -> nominal bending -> Kirsch
        # peak <= PLA strength); GENESIS does the arithmetic, GATE gamma recomputes it.
        _g("q_load", "anteilige Beinlast", 20.0, "kg", ["c_knee_load"]),
        _d("q_sf", "Sicherheitsfaktor", 2.0, "1", "konservativ für statische Beinlast"),
        _der("q_design", "Auslegungslast", 40.0, "kg", "q_load * q_sf", ("q_load", "q_sf")),
        _g("q_g", "Normfallbeschleunigung", STANDARD_GRAVITY, "m/s^2", ["c_gravity"]),
        _der("q_force", "Auslegungskraft am Pivot",
             40.0 * STANDARD_GRAVITY, "N",
             weight_formula("q_design", "q_g"), ("q_design", "q_g")),
        _d("q_w", "Halter-Hebelarm / Plattenlänge", 50.0, "mm",
           "Abstand Schraubenlinie–Pivot — der Hebelarm L und die Box-Länge size_x"),
        _d("q_h", "Halter-Breite", 70.0, "mm",
           "Breite b des Biegequerschnitts und die Box-Breite size_y"),
        _d("q_t", "Halter-Dicke", 12.0, "mm",
           "Querschnittshöhe h in Lastrichtung und die Box-Dicke size_z"),
        _der("q_sigma_nom", "nominale Biegespannung bei Auslegungslast "
             "(Kragarm, Arm=q_w, b=q_h, h=q_t)",
             6.0 * (40.0 * STANDARD_GRAVITY) * 50.0 / (70.0 * 12.0 * 12.0), "MPa",
             cantilever_bending_stress_formula("q_force", "q_w", "q_h", "q_t"),
             ("q_force", "q_w", "q_h", "q_t")),
        _g("q_kt", "Spannungskonzentrationsfaktor (kreisrundes Loch, Kirsch)",
           STRESS_CONCENTRATION_CIRCULAR_HOLE, "1", ["c_kirsch"]),
        _der("q_sigma_peak", "Spitzenspannung am Pivot-Loch",
             STRESS_CONCENTRATION_CIRCULAR_HOLE
             * (6.0 * (40.0 * STANDARD_GRAVITY) * 50.0 / (70.0 * 12.0 * 12.0)), "MPa",
             peak_stress_formula("q_sigma_nom", "q_kt"), ("q_kt", "q_sigma_nom")),
        _g("q_strength", "PLA-Zugfestigkeit in der Druckebene", 50.0, "MPa", ["c_pla"]),
        _d("q_density", "PLA-Dichte", 0.00124, "g/mm^3", "PLA ~1.24 g/cm³, je mm³"),
        # CSG bores: a pivot bore (10 mm bearing) and a motor-shaft pilot bore (8 mm),
        # placed at the two ends of the centered plate (translate offsets in x).
        _d("q_pivot_d", "Pivot-Bohrung (Lagersitz)", 10.0, "mm", "Sitz für 6800-Lager (10 mm)"),
        _der("q_pivot_r", "Pivot-Lochradius", 5.0, "mm", "q_pivot_d / 2", ("q_pivot_d",)),
        _d("q_motor_d", "Motorwellen-Pilotbohrung", 8.0, "mm", "Durchgang für die Motorwelle"),
        _der("q_motor_r", "Motor-Lochradius", 4.0, "mm", "q_motor_d / 2", ("q_motor_d",)),
        _d("q_pivot_x", "Pivot-Bohrung x-Versatz", 15.0, "mm", "zum +x-Ende der Platte"),
        _d("q_motor_x", "Motor-Bohrung x-Versatz", -15.0, "mm", "zum -x-Ende der Platte"),
        _d("q_zero", "Null-Versatz", 0.0, "mm", "y- und z-Versatz der Bohrungen (mittig)"),
        # DFM: minimum wall = 2 perimeters of a 0.4 mm nozzle; minimum hole 2.0 mm.
        _g("q_nozzle", "FDM-Düsendurchmesser", FDM_NOZZLE_DIAMETER_MM, "mm", ["c_fdm_nozzle"]),
        _g("q_perimeters", "Mindestzahl Wand-Perimeter", FDM_WALL_PERIMETERS_MIN, "1",
           ["c_fdm_wall"]),
        _der("q_min_wall", "kleinste druckbare Wanddicke",
             FDM_WALL_PERIMETERS_MIN * FDM_NOZZLE_DIAMETER_MM, "mm",
             min_wall_formula("q_nozzle", "q_perimeters"), ("q_nozzle", "q_perimeters")),
        _g("q_min_hole", "kleinster druckbarer Lochdurchmesser", FDM_MIN_HOLE_DIAMETER_MM, "mm",
           ["c_fdm_hole"]),
        _d("q_torque", "Schrauben-Anzugsmoment (Motorflansch)", 2.5, "N*m", "M4 in Kunststoff, handfest"),
        _g("q_bolt_price", "Schrauben-Stückpreis", 0.42, "EUR", ["c_bolt_price"]),
        _g("q_bearing_price", "Lager-Stückpreis", 3.50, "EUR", ["c_bearing_price"]),
        # delta-robot actuation: does the knee gearmotor hold the joint torque through
        # its reduction? (electric_actuator). Numbers proven to pass in test_robot_physics.
        _dm("q_knee_torque", "Knie-Haltemoment (Bedarf)", 30.0, "N*m",
            "statisches Knie-Gelenkmoment unter Auslegungslast", "actuator.joint_torque"),
        _dm("q_knee_speed", "Knie-Gelenkdrehzahl", 3.0, "rad/s",
            "Knie-Winkelgeschwindigkeit beim Schritt", "actuator.joint_speed"),
        _gm("q_motor_stall", "Motor-Haltemoment (Stall)", 2.0, "N*m", ["c_knee_motor"],
            "motor.stall_torque"),
        _dm("q_motor_noload", "Motor-Leerlaufdrehzahl", 300.0, "rad/s",
            "~2865 rpm Leerlauf", "motor.noload_speed"),
        _dm("q_gear", "Getriebeuntersetzung", 40.0, "1", "Harmonic-Drive-Untersetzung",
            "drivetrain.gear_ratio"),
        _dm("q_eff", "Antriebsstrang-Wirkungsgrad", 0.85, "1", "Getriebe + Lager",
            "drivetrain.efficiency"),
        # delta-robot kinematics: does the 2R leg (thigh+shank) this mount serves reach
        # its foot target? (reach). arm.* = the 2R leg chain.
        _dm("q_l1", "Oberschenkellänge (Link 1)", 0.4, "m", "Hüfte–Knie", "arm.link1_length"),
        _dm("q_l2", "Unterschenkellänge (Link 2)", 0.4, "m", "Knie–Fuß", "arm.link2_length"),
        _dm("q_tx", "Fuß-Zielposition x", 0.5, "m", "Schrittweite vorwärts", "arm.target_x"),
        _dm("q_ty", "Fuß-Zielposition y", 0.1, "m", "Höhe über Hüfthorizont", "arm.target_y"),
    ]
    # CSG: a plate (box) with two bores cut out — difference(box, bore1, bore2) maps to
    # box.cut(cyl1).cut(cyl2). Primitives are centered; the bores are translated to the
    # two ends of the plate so they do not overlap.
    geometry = GeometryNode(kind="difference", children=[
        GeometryNode(kind="box", params={"size_x": "q_w", "size_y": "q_h", "size_z": "q_t"}),
        GeometryNode(kind="translate", params={"x": "q_pivot_x", "y": "q_zero", "z": "q_zero"},
                     children=[GeometryNode(kind="cylinder",
                                            params={"radius": "q_pivot_r", "height": "q_t"})]),
        GeometryNode(kind="translate", params={"x": "q_motor_x", "y": "q_zero", "z": "q_zero"},
                     children=[GeometryNode(kind="cylinder",
                                            params={"radius": "q_motor_r", "height": "q_t"})]),
    ])
    components = [
        Component(id="c_mount", name="Knie-Aktuator-Halterung", geometry=geometry,
                  quantity_ids=["q_w", "q_h", "q_t", "q_pivot_r", "q_motor_r",
                                "q_pivot_x", "q_motor_x", "q_zero"],
                  material_density="q_density"),
    ]
    bom = [
        BomItem(id="b_mount", name="Knie-Aktuator-Halterung (gedruckt)", role=BomRole.PART,
                count=1, component_id="c_mount", domain=BomDomain.MECHANICAL,
                grounding=["c_knee_anchor"]),
        BomItem(id="b_motor", name="Knie-Gelenkmotor (BLDC, NEMA-23-Klasse, ~2.0 N*m Stall)",
                role=BomRole.PART, count=1, domain=BomDomain.MECHANICAL, grounding=["c_knee_motor"]),
        BomItem(id="b_bearing", name="Rillenkugellager 6800-2RS (10 mm Bohrung)",
                role=BomRole.PART, count=1, domain=BomDomain.MECHANICAL,
                grounding=["c_bearing_price"],
                sourcing=Sourcing(supplier="(Lagerhandel)", part_number="6800-2RS",
                                  price_quantity_id="q_bearing_price", grounding=["c_bearing_price"])),
        BomItem(id="b_bolts", name="M4x16-Innensechskantschraube (Motorflansch)",
                role=BomRole.PART, count=4, domain=BomDomain.MECHANICAL, grounding=["c_bolt_src"],
                sourcing=Sourcing(supplier="McMaster-Carr", part_number="91290A115",
                                  price_quantity_id="q_bolt_price", grounding=["c_bolt_src", "c_bolt_price"])),
        BomItem(id="b_printer", name="3D-Drucker", role=BomRole.TOOL, count=1),
        BomItem(id="b_press", name="Lager-Einpresswerkzeug / Schraubstock", role=BomRole.TOOL, count=1),
        BomItem(id="b_hex", name="4-mm-Innensechskantschlüssel", role=BomRole.TOOL, count=1),
    ]
    steps = [
        Step(id="s1", index=1, action="Die Halterung gemäß ihrer CSG-Geometrie 3D-drucken.",
             uses=["b_printer"], inputs=["b_mount"], outputs=["a_printed"],
             check="Das gedruckte Teil misst 50 x 70 x 12 mm; beide Bohrungen sind frei.",
             tool="3D-Drucker", quantity_refs=["q_w", "q_h", "q_t"]),
        Step(id="s2", index=2, action="Das Pivot-Lager in die 10-mm-Bohrung einpressen.",
             uses=["b_press", "b_bearing"], inputs=["a_printed"], outputs=["a_bearing"],
             check="Das Lager sitzt fest und läuft frei.", tool="Lager-Einpresswerkzeug"),
        Step(id="s3", index=3, action="Den Knie-Gelenkmotor an die Motoraufnahme schrauben.",
             uses=["b_hex", "b_bolts", "b_motor"], inputs=["a_bearing"], outputs=["a_mounted"],
             check="Die Motorwelle fluchtet mit der Pivot-Achse.",
             tool="4-mm-Innensechskantschlüssel", torque_quantity_id="q_torque",
             quantity_refs=["q_knee_torque"]),
        Step(id="s4", index=4, action="Statische Prüfung: Der Motor hält den Knie-Winkel unter "
             "Auslegungslast ohne Durchsacken.",
             inputs=["a_mounted"], outputs=["a_done"],
             check="Das Knie hält das geforderte Gelenkmoment (electric_actuator-Reserve > 1).",
             quantity_refs=["q_knee_torque", "q_motor_stall"]),
    ]
    constraints = [
        Constraint(id="k_stress", kind="le", left="q_sigma_peak", right="q_strength",
                   reason="die Spitzenspannung am Pivot-Loch bei Auslegungslast (Kt·σ_nom) "
                          "bleibt unter der PLA-Festigkeit in der Druckebene — notwendig, "
                          "nicht hinreichend"),
        Constraint(id="k_dfm_wall", kind="ge", left="q_t", right="q_min_wall",
                   reason="die Plattendicke ist mindestens die kleinste druckbare FDM-Wand "
                          "(zwei Perimeter einer 0.4-mm-Düse)"),
        Constraint(id="k_dfm_pivot", kind="ge", left="q_pivot_d", right="q_min_hole",
                   reason="die Pivot-Bohrung ist mindestens der kleinste zuverlässig "
                          "druckbare FDM-Lochdurchmesser"),
        Constraint(id="k_dfm_motor", kind="ge", left="q_motor_d", right="q_min_hole",
                   reason="die Motor-Pilotbohrung ist mindestens der kleinste zuverlässig "
                          "druckbare FDM-Lochdurchmesser"),
    ]
    decisions = [
        Decision(id="d_mat", title="Material", choice="PLA, 3D-gedruckt (Prototyp)",
                 rationale="schnell druckbar; ausreichend für die statische Prototyp-Last — "
                           "eine Serien-Knie-Halterung in voller Baugröße braucht Alu/CFK"),
        Decision(id="d_print", title="Druck-Orientierung",
                 choice="flach (Plattenebene auf dem Druckbett)",
                 rationale="die Biegelast liegt in der Druckebene; die Bohrungen drucken "
                           "vertikal ohne Überhang",
                 informed_by=["c_pla"]),
        Decision(id="d_bearing", title="Pivot-Lager", choice="6800-2RS (10 mm Bohrung)",
                 rationale="dünnwandiges Standard-Rillenkugellager für das Kniegelenk",
                 informed_by=["c_bearing_price"]),
    ]
    return Specification(
        run_id="knee_mount",
        idea="Eine druckbare Knie-Aktuator-Halterung für ein humanoides Bein, "
             "die das Knie-Gelenkmoment trägt und den Gelenkmotor aufnimmt",
        approach_id="ap_knee", quantities=quantities, components=components, bom=bom,
        steps=steps, constraints=constraints, decisions=decisions,
        gaps=[
            "PLA ist für den druckbaren PROTOTYP; eine lasttragende Serien-Knie-Halterung "
            "in voller Humanoid-Baugröße braucht Aluminium oder CFK — der σ-Check hier "
            "nutzt PLA-Festigkeit bei der deklarierten Prototyp-Last (Sicherheitsfaktor 2), "
            "nicht die vollen dynamischen Körpergewichtslasten.",
            "Der konkrete Gelenkmotor (SKU + Preis) ist offen: das Teil ist über sein "
            "Stall-Moment spezifiziert, die Beschaffung liefert die Live-α-Recherche nach "
            "(daher als unbepreist in der Stückliste geführt, nicht geraten).",
            "Geprüft ist nur das STATISCHE Halten des Knies; dynamische Gang-/Aufprall-/"
            "Landelasten und die Bewegung über die Zeit sind außerhalb des Geltungsbereichs "
            "— das ist die fehlende Dynamik-Simulations-Achse (P3), kein Closed-Form-Gate.",
            "Die watertight Boolean-STL braucht den OCCT-Kernel (cadquery); ohne ihn ist "
            "der OpenSCAD-/build123d-Quellcode das Druck-Lieferobjekt (verweigert ehrlich, "
            "statt eine kaputte Mesh zu liefern).",
        ],
        claim_ids_used=[c.id for c in knee_mount_claims()], produced_by="knee_mount",
    )


def knee_mount_state() -> RunState:
    """The full RunState (claims + approach + spec) for gate verification."""
    st = RunState(question=Question(raw="humanoid knee actuator mount", run_id="knee_mount"))
    st.claims = knee_mount_claims()
    st.approaches = [Approach(id="ap_knee", name="Knie-Aktuator-Halterung",
                             grounding=["c_knee_anchor"])]
    st.specification = knee_mount_spec()
    return st


# --- delta robot domain: a MULTI-PART humanoid leg ASSEMBLY ----------------------
# The knee mount is one part; this is an ASSEMBLY — TWO printed link components (thigh and shank),
# each a printable CSG body with two joint bores, plus the bought actuators/bearings/bolts. It emits
# ONE STL PER PRINTED PART (each prints separately), a combined buy-list, an assembly build order, and
# fires the dynamic robot axes (ZMP over the gait, swing inverse dynamics, the knee actuator, the 2R
# reach) PLUS the gamma bending of the load-bearing thigh link. The "assembled robot, not a single
# part" deliverable, through the same gated machinery.

def leg_assembly_claims() -> list[Claim]:
    return [
        _claim("c_leg_anchor",
               "Ein humanoides Bein besteht aus Oberschenkel- und Unterschenkel-Gliedern, "
               "die über ein Kniegelenk verbunden sind."),
        _claim("c_leg_load",
               "Ein leichtes Humanoid-Bein trägt eine statische Auslegungslast von 20 kg "
               "(anteiliges Körpergewicht)."),
        _claim("c_gravity", "Die Normfallbeschleunigung ist definiert als 9.80665 m/s^2."),
        _claim("c_pla",
               "FDM-gedrucktes PLA, in der Druckebene belastet, hat eine Zugfestigkeit "
               "von etwa 50 MPa."),
        _claim("c_kirsch",
               "Ein kreisrundes Loch in einer Platte unter Zug hat einen "
               "Spannungskonzentrationsfaktor von 3 (Kirsch-Lösung)."),
        _claim("c_knee_motor",
               "Ein bürstenloser Robotik-Gelenkmotor der NEMA-23-Klasse liefert ein "
               "Haltemoment (Stall) von etwa 2.0 N*m vor der Untersetzung."),
        _claim("c_fdm_nozzle", "Eine Standard-FDM-Düse hat 0.4 mm Durchmesser."),
        _claim("c_fdm_wall", "Eine FDM-Wand sollte mindestens 2 Perimeterlinien breit sein."),
        _claim("c_fdm_hole",
               "Das kleinste zuverlässig druckbare horizontale Loch im FDM-Druck hat "
               "2.0 mm Durchmesser."),
        _claim("c_bolt_src",
               "McMaster-Carr führt das Teil 91290A115, eine M4x16-Innensechskantschraube."),
        _claim("c_bolt_price",
               "Die M4x16-Innensechskantschraube kostet bei McMaster-Carr 0.42 EUR pro Stück."),
        _claim("c_bearing_price",
               "Ein Rillenkugellager 6800-2RS (10 mm Bohrung) kostet etwa 3.50 EUR pro Stück."),
    ]


def leg_assembly_spec() -> Specification:
    _force_n = 40.0 * STANDARD_GRAVITY
    quantities = [
        # gamma statics on the load-bearing thigh link (cantilever bending at the hip bore)
        _g("q_load", "anteilige Beinlast", 20.0, "kg", ["c_leg_load"]),
        _d("q_sf", "Sicherheitsfaktor", 2.0, "1", "konservativ für statische Beinlast"),
        _der("q_design", "Auslegungslast", 40.0, "kg", "q_load * q_sf", ("q_load", "q_sf")),
        _g("q_g", "Normfallbeschleunigung", STANDARD_GRAVITY, "m/s^2", ["c_gravity"]),
        _der("q_force", "Auslegungskraft am Hüft-Pivot", _force_n, "N",
             weight_formula("q_design", "q_g"), ("q_design", "q_g")),
        # thigh link geometry (box minus a hip bore and a knee bore) + it is the bending member
        _d("q_thigh_len", "Oberschenkel-Länge / Box size_x", 180.0, "mm", "Hüfte–Knie, Plattenlänge"),
        _d("q_thigh_w", "Oberschenkel-Breite / size_y", 40.0, "mm", "Breite b des Biegequerschnitts"),
        _d("q_thigh_t", "Oberschenkel-Dicke / size_z", 18.0, "mm", "Querschnittshöhe h in Lastrichtung"),
        _d("q_thigh_arm", "Biege-Hebelarm Oberschenkel", 70.0, "mm", "Pivot-Abstand zur Lasteinleitung"),
        _der("q_sigma_nom", "nominale Biegespannung Oberschenkel (Kragarm)",
             6.0 * _force_n * 70.0 / (40.0 * 18.0 * 18.0), "MPa",
             cantilever_bending_stress_formula("q_force", "q_thigh_arm", "q_thigh_w", "q_thigh_t"),
             ("q_force", "q_thigh_arm", "q_thigh_w", "q_thigh_t")),
        _g("q_kt", "Spannungskonzentrationsfaktor (kreisrundes Loch, Kirsch)",
           STRESS_CONCENTRATION_CIRCULAR_HOLE, "1", ["c_kirsch"]),
        _der("q_sigma_peak", "Spitzenspannung am Hüft-Loch",
             STRESS_CONCENTRATION_CIRCULAR_HOLE * (6.0 * _force_n * 70.0 / (40.0 * 18.0 * 18.0)), "MPa",
             peak_stress_formula("q_sigma_nom", "q_kt"), ("q_kt", "q_sigma_nom")),
        _g("q_strength", "PLA-Zugfestigkeit in der Druckebene", 50.0, "MPa", ["c_pla"]),
        _d("q_density", "PLA-Dichte", 0.00124, "g/mm^3", "PLA ~1.24 g/cm³, je mm³"),
        # shank link geometry
        _d("q_shank_len", "Unterschenkel-Länge / size_x", 180.0, "mm", "Knie–Fuß"),
        _d("q_shank_w", "Unterschenkel-Breite / size_y", 35.0, "mm", "Breite"),
        _d("q_shank_t", "Unterschenkel-Dicke / size_z", 12.0, "mm", "Dicke"),
        # bores (shared knee bore Ø10; hip Ø12; ankle Ø8) + symmetric x-offset within each link
        _d("q_hip_bore_d", "Hüft-Bohrung", 12.0, "mm", "Lagersitz Hüfte"),
        _der("q_hip_bore_r", "Hüft-Lochradius", 6.0, "mm", "q_hip_bore_d / 2", ("q_hip_bore_d",)),
        _d("q_knee_bore_d", "Knie-Bohrung", 10.0, "mm", "Lagersitz Knie (6800)"),
        _der("q_knee_bore_r", "Knie-Lochradius", 5.0, "mm", "q_knee_bore_d / 2", ("q_knee_bore_d",)),
        _d("q_ankle_bore_d", "Knöchel-Bohrung", 8.0, "mm", "Knöchel-Durchgang"),
        _der("q_ankle_bore_r", "Knöchel-Lochradius", 4.0, "mm", "q_ankle_bore_d / 2", ("q_ankle_bore_d",)),
        _d("q_bore_off", "Bohrungs-Versatz vom Glied-Zentrum", 70.0, "mm", "±x-Lage der Endbohrungen"),
        _d("q_bore_neg", "negativer Bohrungs-Versatz", -70.0, "mm", "−x-Lage"),
        _d("q_zero", "Null-Versatz", 0.0, "mm", "y/z-Versatz der Bohrungen (mittig)"),
        # DFM
        _g("q_nozzle", "FDM-Düsendurchmesser", FDM_NOZZLE_DIAMETER_MM, "mm", ["c_fdm_nozzle"]),
        _g("q_perimeters", "Mindestzahl Wand-Perimeter", FDM_WALL_PERIMETERS_MIN, "1", ["c_fdm_wall"]),
        _der("q_min_wall", "kleinste druckbare Wanddicke",
             FDM_WALL_PERIMETERS_MIN * FDM_NOZZLE_DIAMETER_MM, "mm",
             min_wall_formula("q_nozzle", "q_perimeters"), ("q_nozzle", "q_perimeters")),
        _g("q_min_hole", "kleinster druckbarer Lochdurchmesser", FDM_MIN_HOLE_DIAMETER_MM, "mm",
           ["c_fdm_hole"]),
        _d("q_torque", "Schrauben-Anzugsmoment (Motorflansch)", 2.5, "N*m", "M4 in Kunststoff, handfest"),
        _g("q_bolt_price", "Schrauben-Stückpreis", 0.42, "EUR", ["c_bolt_price"]),
        _g("q_bearing_price", "Lager-Stückpreis", 3.50, "EUR", ["c_bearing_price"]),
        # delta-robot kinematics: the 2R leg (thigh+shank) reaches a foot target
        _dm("q_l1", "Oberschenkellänge (Link 1)", 0.18, "m", "Hüfte–Knie", "arm.link1_length"),
        _dm("q_l2", "Unterschenkellänge (Link 2)", 0.18, "m", "Knie–Fuß", "arm.link2_length"),
        _dm("q_tx", "Fuß-Zielposition x", 0.20, "m", "Schrittweite", "arm.target_x"),
        _dm("q_ty", "Fuß-Zielposition y", 0.05, "m", "Höhe", "arm.target_y"),
        # delta-robot actuation: the knee gearmotor holds the joint torque
        _dm("q_knee_torque", "Knie-Haltemoment (Bedarf)", 28.0, "N*m",
            "statisches Knie-Moment unter Auslegungslast", "actuator.joint_torque"),
        _dm("q_knee_speed", "Knie-Gelenkdrehzahl", 3.0, "rad/s", "Schritt", "actuator.joint_speed"),
        _gm("q_motor_stall", "Motor-Haltemoment (Stall)", 2.0, "N*m", ["c_knee_motor"],
            "motor.stall_torque"),
        _dm("q_motor_noload", "Motor-Leerlaufdrehzahl", 300.0, "rad/s", "~2865 rpm", "motor.noload_speed"),
        _dm("q_gear", "Getriebeuntersetzung", 40.0, "1", "Harmonic Drive", "drivetrain.gear_ratio"),
        _dm("q_eff", "Antriebsstrang-Wirkungsgrad", 0.85, "1", "Getriebe+Lager", "drivetrain.efficiency"),
        # delta-robot DYNAMICS: balance over the gait + the swinging shank
        _dm("q_com_x", "CoM-Versatz", 0.0, "m", "zentriert", "balance.com_x"),
        _dm("q_com_h", "CoM-Höhe", 0.9, "m", "Schwerpunkthöhe", "balance.com_height"),
        _dm("q_smin", "Stützpolygon min x", -0.10, "m", "Fußkante hinten", "balance.support_min_x"),
        _dm("q_smax", "Stützpolygon max x", 0.10, "m", "Fußkante vorn", "balance.support_max_x"),
        _dm("q_sway", "CoM-Schwankungsamplitude", 0.04, "m", "seitliche Gang-Schwankung",
            "gait.com_amplitude"),
        _dm("q_step_f", "Schrittfrequenz", 0.45, "Hz", "Gang-Kadenz", "gait.step_frequency"),
        _dm("q_limb_I", "Schenkel-Trägheit um das Gelenk", rod_inertia_about_end(2.0, 0.18), "kg*m^2",
            "m·L²/3 (gleichförmiger Stab um die Hüfte, kanonische Formel) — konsistent zu q_limb_m/q_l1",
            "limb.inertia"),
        _dm("q_limb_m", "Schenkel-Masse", 2.0, "kg", "Glied+Motor", "limb.mass"),
        _dm("q_limb_d", "Schenkel-Schwerpunktabstand", 0.09, "m", "Gelenk→CoM", "limb.com_distance"),
        _dm("q_swing", "Schwung-Amplitude", 0.4, "rad", "Knie-Schwung im Schritt", "swing.amplitude"),
        _dm("q_avail_tau", "verfügbares Aktuator-Drehmoment", 80.0, "N*m",
            "Stall·Getriebe·η am Gelenk", "actuator.available_torque"),
    ]
    thigh_geom = GeometryNode(kind="difference", children=[
        GeometryNode(kind="box", params={"size_x": "q_thigh_len", "size_y": "q_thigh_w",
                                          "size_z": "q_thigh_t"}),
        GeometryNode(kind="translate", params={"x": "q_bore_neg", "y": "q_zero", "z": "q_zero"},
                     children=[GeometryNode(kind="cylinder",
                                            params={"radius": "q_hip_bore_r", "height": "q_thigh_t"})]),
        GeometryNode(kind="translate", params={"x": "q_bore_off", "y": "q_zero", "z": "q_zero"},
                     children=[GeometryNode(kind="cylinder",
                                            params={"radius": "q_knee_bore_r", "height": "q_thigh_t"})]),
    ])
    shank_geom = GeometryNode(kind="difference", children=[
        GeometryNode(kind="box", params={"size_x": "q_shank_len", "size_y": "q_shank_w",
                                          "size_z": "q_shank_t"}),
        GeometryNode(kind="translate", params={"x": "q_bore_off", "y": "q_zero", "z": "q_zero"},
                     children=[GeometryNode(kind="cylinder",
                                            params={"radius": "q_knee_bore_r", "height": "q_shank_t"})]),
        GeometryNode(kind="translate", params={"x": "q_bore_neg", "y": "q_zero", "z": "q_zero"},
                     children=[GeometryNode(kind="cylinder",
                                            params={"radius": "q_ankle_bore_r", "height": "q_shank_t"})]),
    ])
    components = [
        Component(id="c_thigh", name="Oberschenkel-Glied", geometry=thigh_geom,
                  quantity_ids=["q_thigh_len", "q_thigh_w", "q_thigh_t", "q_hip_bore_r", "q_knee_bore_r",
                                "q_bore_off", "q_bore_neg", "q_zero"], material_density="q_density"),
        Component(id="c_shank", name="Unterschenkel-Glied", geometry=shank_geom,
                  quantity_ids=["q_shank_len", "q_shank_w", "q_shank_t", "q_knee_bore_r", "q_ankle_bore_r",
                                "q_bore_off", "q_bore_neg", "q_zero"], material_density="q_density"),
    ]
    bom = [
        BomItem(id="b_thigh", name="Oberschenkel-Glied (gedruckt)", role=BomRole.PART, count=1,
                component_id="c_thigh", domain=BomDomain.MECHANICAL, grounding=["c_leg_anchor"]),
        BomItem(id="b_shank", name="Unterschenkel-Glied (gedruckt)", role=BomRole.PART, count=1,
                component_id="c_shank", domain=BomDomain.MECHANICAL, grounding=["c_leg_anchor"]),
        BomItem(id="b_knee_motor", name="Knie-Gelenkmotor (BLDC, ~2.0 N*m Stall)", role=BomRole.PART,
                count=1, domain=BomDomain.MECHANICAL, grounding=["c_knee_motor"]),
        BomItem(id="b_hip_motor", name="Hüft-Gelenkmotor (BLDC, ~2.0 N*m Stall)", role=BomRole.PART,
                count=1, domain=BomDomain.MECHANICAL, grounding=["c_knee_motor"]),
        BomItem(id="b_bearings", name="Rillenkugellager 6800-2RS (10 mm)", role=BomRole.PART, count=3,
                domain=BomDomain.MECHANICAL, grounding=["c_bearing_price"],
                sourcing=Sourcing(supplier="(Lagerhandel)", part_number="6800-2RS",
                                  price_quantity_id="q_bearing_price", grounding=["c_bearing_price"])),
        BomItem(id="b_bolts", name="M4x16-Innensechskantschraube", role=BomRole.PART, count=8,
                domain=BomDomain.MECHANICAL, grounding=["c_bolt_src"],
                sourcing=Sourcing(supplier="McMaster-Carr", part_number="91290A115",
                                  price_quantity_id="q_bolt_price", grounding=["c_bolt_src", "c_bolt_price"])),
        BomItem(id="b_printer", name="3D-Drucker", role=BomRole.TOOL, count=1),
        BomItem(id="b_press", name="Lager-Einpresswerkzeug", role=BomRole.TOOL, count=1),
        BomItem(id="b_hex", name="4-mm-Innensechskantschlüssel", role=BomRole.TOOL, count=1),
    ]
    steps = [
        Step(id="s1", index=1, action="Oberschenkel- und Unterschenkel-Glied 3D-drucken.",
             uses=["b_printer"], inputs=["b_thigh", "b_shank"], outputs=["a_printed"],
             check="Beide Glieder gedruckt; alle vier Bohrungen frei.",
             tool="3D-Drucker", quantity_refs=["q_thigh_len", "q_shank_len"]),
        Step(id="s2", index=2, action="Die drei Lager in Hüft-, Knie- und Knöchel-Bohrung einpressen.",
             uses=["b_press", "b_bearings"], inputs=["a_printed"], outputs=["a_bearing"],
             check="Lager sitzen fest und laufen frei."),
        Step(id="s3", index=3, action="Den Knie-Gelenkmotor zwischen Oberschenkel- und "
             "Unterschenkel-Glied am Knie-Pivot verschrauben.",
             uses=["b_hex", "b_bolts", "b_knee_motor"], inputs=["a_bearing"], outputs=["a_knee"],
             check="Knie beugt frei; Motorwelle fluchtet mit dem Knie-Pivot.",
             tool="4-mm-Innensechskantschlüssel", torque_quantity_id="q_torque",
             quantity_refs=["q_knee_torque"]),
        Step(id="s4", index=4, action="Den Hüft-Gelenkmotor an das Oberschenkel-Glied am Hüft-Pivot "
             "verschrauben.",
             uses=["b_hex", "b_bolts", "b_hip_motor"], inputs=["a_knee"], outputs=["a_assembled"],
             check="Bein hängt komplett montiert; Hüfte und Knie bewegen sich frei."),
        Step(id="s5", index=5, action="Statische + dynamische Prüfung: das Knie hält die Auslegungslast "
             "und der Schwung bleibt im Drehmoment-Budget.",
             inputs=["a_assembled"], outputs=["a_done"],
             check="electric_actuator-Reserve > 1 und joint_swing_torque-Reserve > 1; ZMP im Stützpolygon.",
             quantity_refs=["q_knee_torque", "q_avail_tau", "q_step_f"]),
    ]
    constraints = [
        Constraint(id="k_stress", kind="le", left="q_sigma_peak", right="q_strength",
                   reason="die Spitzenspannung am Hüft-Loch des Oberschenkel-Glieds bleibt unter der "
                          "PLA-Festigkeit — notwendig, nicht hinreichend"),
        Constraint(id="k_dfm_thigh_wall", kind="ge", left="q_thigh_t", right="q_min_wall",
                   reason="die Oberschenkel-Dicke ist mindestens die kleinste druckbare FDM-Wand"),
        Constraint(id="k_dfm_shank_wall", kind="ge", left="q_shank_t", right="q_min_wall",
                   reason="die Unterschenkel-Dicke ist mindestens die kleinste druckbare FDM-Wand"),
        Constraint(id="k_dfm_knee_hole", kind="ge", left="q_knee_bore_d", right="q_min_hole",
                   reason="die Knie-Bohrung ist mindestens der kleinste druckbare FDM-Lochdurchmesser"),
        Constraint(id="k_dfm_ankle_hole", kind="ge", left="q_ankle_bore_d", right="q_min_hole",
                   reason="die Knöchel-Bohrung ist mindestens der kleinste druckbare FDM-Lochdurchmesser"),
    ]
    decisions = [
        Decision(id="d_mat", title="Material", choice="PLA, 3D-gedruckt (Prototyp)",
                 rationale="schnell druckbar; Prototyp-Last — eine Serien-Bein-Baugruppe braucht Alu/CFK"),
        Decision(id="d_print", title="Druck-Orientierung", choice="flach, Glieder einzeln",
                 rationale="jedes Glied druckt separat in der Plattenebene; die Bohrungen vertikal "
                           "ohne Überhang", informed_by=["c_pla"]),
    ]
    return Specification(
        run_id="leg_assembly",
        idea="Eine montierte humanoide Bein-Baugruppe (Oberschenkel- + Unterschenkel-Glied, Kniegelenk), "
             "die das Gelenkmoment trägt, sich dynamisch im Stützpolygon hält und die Glieder schwingt",
        approach_id="ap_leg", quantities=quantities, components=components, bom=bom,
        steps=steps, constraints=constraints, decisions=decisions,
        gaps=[
            "PLA ist für den druckbaren PROTOTYP; eine lasttragende Serien-Bein-Baugruppe in voller "
            "Baugröße braucht Aluminium oder CFK — der σ-Check nutzt PLA bei Prototyp-Last (SF 2).",
            "Die Gelenkmotoren (SKU + Preis) sind über ihr Stall-Moment spezifiziert; die Beschaffung "
            "liefert die Live-α-Recherche nach (daher unbepreist in der Stückliste).",
            "Geprüft sind statisches Halten + die deterministischen Dynamik-Screens (ZMP über die "
            "Gang-Trajektorie, Schwung-Drehmoment); der volle Mehrgelenk-Kontakt-Gang läuft im externen "
            "Simulator über die URDF-Brücke (PyBullet/Isaac), nicht in diesem Gate.",
            "Die Baugruppe ist die Kinematik-Kette; eine reale Hüft-/Knöchel-Anbindung an Becken bzw. "
            "Fuß ist außerhalb des Geltungsbereichs dieser Bein-Teilbaugruppe.",
        ],
        claim_ids_used=[c.id for c in leg_assembly_claims()], produced_by="leg_assembly",
    )


def humanoid_claims() -> list[Claim]:
    return [
        _claim("c_humanoid_anchor",
               "Ein humanoider Roboter besteht aus Becken, Rumpf, Kopf, zwei Armen "
               "(Oberarm + Unterarm) und zwei Beinen (Oberschenkel + Unterschenkel), "
               "verbunden durch zehn angetriebene Drehgelenke."),
        _claim("c_body_mass",
               "Ein leichter Forschungs-Humanoid in dieser Bauklasse wiegt etwa 10 kg."),
        _claim("c_gravity", "Die Normfallbeschleunigung ist definiert als 9.80665 m/s^2."),
        _claim("c_pla",
               "FDM-gedrucktes PLA, in der Druckebene belastet, hat eine Zugfestigkeit "
               "von etwa 50 MPa."),
        _claim("c_kirsch",
               "Ein kreisrundes Loch in einer Platte unter Zug hat einen "
               "Spannungskonzentrationsfaktor von 3 (Kirsch-Lösung)."),
        _claim("c_knee_motor",
               "Ein bürstenloser Robotik-Gelenkmotor der NEMA-23-Klasse liefert ein "
               "Haltemoment (Stall) von etwa 2.0 N*m vor der Untersetzung."),
        _claim("c_fdm_nozzle", "Eine Standard-FDM-Düse hat 0.4 mm Durchmesser."),
        _claim("c_fdm_wall", "Eine FDM-Wand sollte mindestens 2 Perimeterlinien breit sein."),
        _claim("c_fdm_hole",
               "Das kleinste zuverlässig druckbare horizontale Loch im FDM-Druck hat "
               "2.0 mm Durchmesser."),
        _claim("c_bolt_src",
               "McMaster-Carr führt das Teil 91290A115, eine M4x16-Innensechskantschraube."),
        _claim("c_bolt_price",
               "Die M4x16-Innensechskantschraube kostet bei McMaster-Carr 0.42 EUR pro Stück."),
        _claim("c_bearing_price",
               "Ein Rillenkugellager 6800-2RS (10 mm Bohrung) kostet etwa 3.50 EUR pro Stück."),
        _claim("c_orin",
               "Das NVIDIA Jetson Orin NX liefert etwa 100 INT8-TOPS KI-Rechenleistung "
               "bei rund 25 W Leistungsaufnahme."),
        _claim("c_imu",
               "Eine 6-Achsen-IMU (z.B. Bosch BMI088) liefert Beschleunigung und Drehrate "
               "für die Lageregelung."),
        _claim("c_lipo",
               "Ein 6S-LiPo-Akku (22.2 V Nennspannung) speist die Gelenkmotoren und die "
               "Recheneinheit eines mobilen Humanoiden."),
        _claim("c_driver",
               "Ein Feldorientierter BLDC-Motortreiber (z.B. ODrive/MJBots moteus) "
               "kommutiert je einen Gelenkmotor mit Stromregelung."),
    ]


def humanoid_spec() -> Specification:
    """Ein Ganzkörper-Humanoid als komplette, gegatete GENESIS-Spezifikation: acht druckbare
    Strukturteile (Becken, Rumpf, Kopf, Oberschenkel, Unterschenkel, Oberarm, Unterarm, Fuß —
    je ein Kasten mit zwei Durchgangsbohrungen) als CAD-Komponenten → STL, plus die vollständige
    Kaufliste (zehn Gelenkmotoren, Lager, Schrauben, Onboard-Recheneinheit/Chip, Echtzeit-MCU,
    Motortreiber, IMU, Akku, Kabelbaum) und die measurand-getaggten Größen, die Kinematik,
    Aktuator-Sizing, Onboard-Compute, Tragwerk, Balance und Schwung-Dynamik im δ-Physik-Gate
    feuern. Maximal gedruckt (3D-Drucker-Direktive); nur Nicht-Druckbares steht auf der Kaufliste."""
    _force_n = 40.0 * STANDARD_GRAVITY  # 20 kg Teil-Beinlast * SF 2, am Hüft-Pivot

    def _link(sx, sy, sz, r1, off1, r2, off2):
        """Ein gedrucktes Glied: Kasten minus zwei Durchgangsbohrungen an ±x-Enden (alle Argumente
        sind quantity-ids)."""
        return GeometryNode(kind="difference", children=[
            GeometryNode(kind="box", params={"size_x": sx, "size_y": sy, "size_z": sz}),
            GeometryNode(kind="translate", params={"x": off1, "y": "q_zero", "z": "q_zero"},
                         children=[GeometryNode(kind="cylinder", params={"radius": r1, "height": sz})]),
            GeometryNode(kind="translate", params={"x": off2, "y": "q_zero", "z": "q_zero"},
                         children=[GeometryNode(kind="cylinder", params={"radius": r2, "height": sz})]),
        ])

    quantities = [
        # --- load path: the thigh is the σ-checked bending member (hip cantilever) ---
        _g("q_load", "anteilige Beinlast", 20.0, "kg", ["c_body_mass"]),
        _d("q_sf", "Sicherheitsfaktor", 2.0, "1", "konservativ für statische Beinlast"),
        _der("q_design", "Auslegungslast", 40.0, "kg", "q_load * q_sf", ("q_load", "q_sf")),
        _g("q_g", "Normfallbeschleunigung", STANDARD_GRAVITY, "m/s^2", ["c_gravity"]),
        _der("q_force", "Auslegungskraft am Hüft-Pivot", _force_n, "N",
             weight_formula("q_design", "q_g"), ("q_design", "q_g")),
        _g("q_strength", "PLA-Zugfestigkeit in der Druckebene", 50.0, "MPa", ["c_pla"]),
        _d("q_density", "PLA-Dichte", 0.00124, "g/mm^3", "PLA ~1.24 g/cm³, je mm³"),
        _g("q_kt", "Spannungskonzentrationsfaktor (kreisrundes Loch, Kirsch)",
           STRESS_CONCENTRATION_CIRCULAR_HOLE, "1", ["c_kirsch"]),
        _d("q_zero", "Null-Versatz", 0.0, "mm", "y/z-Versatz der Bohrungen (mittig)"),
        # --- shared bore radii (Ø ≥ 6 mm ≥ druckbares Mindestloch) ---
        _d("q_r_hip", "Hüft-Lochradius", 6.0, "mm", "Lagersitz Hüfte (Ø12)"),
        _d("q_r_knee", "Knie-Lochradius", 5.0, "mm", "Lagersitz Knie (Ø10, 6800)"),
        _d("q_r_ankle", "Knöchel-Lochradius", 4.0, "mm", "Knöchel-Durchgang (Ø8)"),
        _d("q_r_shoulder", "Schulter-Lochradius", 5.0, "mm", "Lagersitz Schulter (Ø10)"),
        _d("q_r_elbow", "Ellbogen-Lochradius", 4.0, "mm", "Lagersitz Ellbogen (Ø8)"),
        _d("q_r_wrist", "Handgelenk-Lochradius", 3.0, "mm", "Handgelenk-Durchgang (Ø6)"),
        _d("q_r_spine", "Spine-Lochradius", 6.0, "mm", "Rumpf-Becken-Drehachse (Ø12)"),
        _d("q_r_neck", "Hals-Lochradius", 4.0, "mm", "Kopf-Drehachse (Ø8)"),
        _d("q_r_cam", "Kamera-Lochradius", 3.0, "mm", "Kopf-Kameradurchgang (Ø6)"),
        _d("q_r_toe", "Zehen-Lochradius", 4.0, "mm", "Fuß-Vorderbohrung (Ø8)"),
        # --- pelvis: 160x60x20, two hip bores at ±60 ---
        _d("q_pelvis_x", "Becken-Länge / size_x", 160.0, "mm", "Hüfte–Hüfte-Breite"),
        _d("q_pelvis_y", "Becken-Breite / size_y", 60.0, "mm", "Tiefe"),
        _d("q_pelvis_z", "Becken-Dicke / size_z", 20.0, "mm", "Plattendicke"),
        _d("q_pelvis_off", "Becken-Bohrungsversatz +", 60.0, "mm", "+x Hüftbohrung"),
        _d("q_pelvis_neg", "Becken-Bohrungsversatz -", -60.0, "mm", "-x Hüftbohrung"),
        # --- torso: 200x120x20, spine bore (-80) + shoulder bore (+80) ---
        _d("q_torso_x", "Rumpf-Länge / size_x", 200.0, "mm", "Spine-Achse vertikal"),
        _d("q_torso_y", "Rumpf-Breite / size_y", 120.0, "mm", "Schulterbreite"),
        _d("q_torso_z", "Rumpf-Dicke / size_z", 20.0, "mm", "Plattendicke"),
        _d("q_torso_off", "Rumpf-Bohrungsversatz +", 80.0, "mm", "+x Schulterbohrung"),
        _d("q_torso_neg", "Rumpf-Bohrungsversatz -", -80.0, "mm", "-x Spine-Bohrung"),
        # --- head: 90x90x12, neck bore (-30) + camera bore (+30) ---
        _d("q_head_x", "Kopf-Länge / size_x", 90.0, "mm", "Kopfplatte"),
        _d("q_head_y", "Kopf-Breite / size_y", 90.0, "mm", "Kopfplatte"),
        _d("q_head_z", "Kopf-Dicke / size_z", 12.0, "mm", "Plattendicke"),
        _d("q_head_off", "Kopf-Bohrungsversatz +", 30.0, "mm", "+x Kamerabohrung"),
        _d("q_head_neg", "Kopf-Bohrungsversatz -", -30.0, "mm", "-x Halsbohrung"),
        # --- thigh: 180x40x18 (σ-checked), hip bore (-70) + knee bore (+70) ---
        _d("q_thigh_x", "Oberschenkel-Länge / size_x", 180.0, "mm", "Hüfte–Knie"),
        _d("q_thigh_y", "Oberschenkel-Breite / size_y", 40.0, "mm", "Breite b"),
        _d("q_thigh_z", "Oberschenkel-Dicke / size_z", 18.0, "mm", "Höhe h in Lastrichtung"),
        _d("q_thigh_arm", "Biege-Hebelarm Oberschenkel", 70.0, "mm", "Pivot-Abstand"),
        _d("q_thigh_off", "Oberschenkel-Bohrungsversatz +", 70.0, "mm", "+x Knie"),
        _d("q_thigh_neg", "Oberschenkel-Bohrungsversatz -", -70.0, "mm", "-x Hüfte"),
        _der("q_sigma_nom", "nominale Biegespannung Oberschenkel (Kragarm)",
             6.0 * _force_n * 70.0 / (40.0 * 18.0 * 18.0), "MPa",
             cantilever_bending_stress_formula("q_force", "q_thigh_arm", "q_thigh_y", "q_thigh_z"),
             ("q_force", "q_thigh_arm", "q_thigh_y", "q_thigh_z")),
        _der("q_sigma_peak", "Spitzenspannung am Hüft-Loch",
             STRESS_CONCENTRATION_CIRCULAR_HOLE * (6.0 * _force_n * 70.0 / (40.0 * 18.0 * 18.0)), "MPa",
             peak_stress_formula("q_sigma_nom", "q_kt"), ("q_kt", "q_sigma_nom")),
        # --- shank: 180x35x12, knee bore (+70) + ankle bore (-70) ---
        _d("q_shank_x", "Unterschenkel-Länge / size_x", 180.0, "mm", "Knie–Fuß"),
        _d("q_shank_y", "Unterschenkel-Breite / size_y", 35.0, "mm", "Breite"),
        _d("q_shank_z", "Unterschenkel-Dicke / size_z", 12.0, "mm", "Dicke"),
        _d("q_shank_off", "Unterschenkel-Bohrungsversatz +", 70.0, "mm", "+x Knie"),
        _d("q_shank_neg", "Unterschenkel-Bohrungsversatz -", -70.0, "mm", "-x Knöchel"),
        # --- upper arm: 140x30x12, shoulder bore (-55) + elbow bore (+55) ---
        _d("q_uarm_x", "Oberarm-Länge / size_x", 140.0, "mm", "Schulter–Ellbogen"),
        _d("q_uarm_y", "Oberarm-Breite / size_y", 30.0, "mm", "Breite"),
        _d("q_uarm_z", "Oberarm-Dicke / size_z", 12.0, "mm", "Dicke"),
        _d("q_uarm_off", "Oberarm-Bohrungsversatz +", 55.0, "mm", "+x Ellbogen"),
        _d("q_uarm_neg", "Oberarm-Bohrungsversatz -", -55.0, "mm", "-x Schulter"),
        # --- forearm: 130x28x10, elbow bore (-50) + wrist bore (+50) ---
        _d("q_farm_x", "Unterarm-Länge / size_x", 130.0, "mm", "Ellbogen–Hand"),
        _d("q_farm_y", "Unterarm-Breite / size_y", 28.0, "mm", "Breite"),
        _d("q_farm_z", "Unterarm-Dicke / size_z", 10.0, "mm", "Dicke"),
        _d("q_farm_off", "Unterarm-Bohrungsversatz +", 50.0, "mm", "+x Handgelenk"),
        _d("q_farm_neg", "Unterarm-Bohrungsversatz -", -50.0, "mm", "-x Ellbogen"),
        # --- foot: 120x60x10, ankle bore (-45) + toe bore (+45) ---
        _d("q_foot_x", "Fuß-Länge / size_x", 120.0, "mm", "Ferse–Zeh"),
        _d("q_foot_y", "Fuß-Breite / size_y", 60.0, "mm", "Breite"),
        _d("q_foot_z", "Fuß-Dicke / size_z", 10.0, "mm", "Sohlendicke"),
        _d("q_foot_off", "Fuß-Bohrungsversatz +", 45.0, "mm", "+x Zehe"),
        _d("q_foot_neg", "Fuß-Bohrungsversatz -", -45.0, "mm", "-x Knöchel"),
        # --- DFM gates ---
        _g("q_nozzle", "FDM-Düsendurchmesser", FDM_NOZZLE_DIAMETER_MM, "mm", ["c_fdm_nozzle"]),
        _g("q_perimeters", "Mindestzahl Wand-Perimeter", FDM_WALL_PERIMETERS_MIN, "1", ["c_fdm_wall"]),
        _der("q_min_wall", "kleinste druckbare Wanddicke",
             FDM_WALL_PERIMETERS_MIN * FDM_NOZZLE_DIAMETER_MM, "mm",
             min_wall_formula("q_nozzle", "q_perimeters"), ("q_nozzle", "q_perimeters")),
        _g("q_min_hole", "kleinster druckbarer Lochdurchmesser", FDM_MIN_HOLE_DIAMETER_MM, "mm",
           ["c_fdm_hole"]),
        _d("q_knee_bore_d", "Knie-Bohrung Durchmesser", 10.0, "mm", "für DFM-Lochcheck"),
        _d("q_torque", "Schrauben-Anzugsmoment (Motorflansch)", 2.5, "N*m", "M4 in Kunststoff"),
        _g("q_bolt_price", "Schrauben-Stückpreis", 0.42, "EUR", ["c_bolt_price"]),
        _g("q_bearing_price", "Lager-Stückpreis", 3.50, "EUR", ["c_bearing_price"]),
        # --- kinematics: the 2R leg reaches a foot target (arm.* recipe) ---
        _dm("q_l1", "Oberschenkellänge (Link 1)", 0.18, "m", "Hüfte–Knie", "arm.link1_length"),
        _dm("q_l2", "Unterschenkellänge (Link 2)", 0.18, "m", "Knie–Fuß", "arm.link2_length"),
        _dm("q_tx", "Fuß-Zielposition x", 0.20, "m", "Schrittweite", "arm.target_x"),
        _dm("q_ty", "Fuß-Zielposition y", 0.05, "m", "Höhe", "arm.target_y"),
        # --- actuation: the knee gearmotor holds the joint torque ---
        _dm("q_knee_torque", "Knie-Haltemoment (Bedarf)", 28.0, "N*m",
            "statisches Knie-Moment unter Auslegungslast", "actuator.joint_torque"),
        _dm("q_knee_speed", "Knie-Gelenkdrehzahl", 3.0, "rad/s", "Schritt", "actuator.joint_speed"),
        _gm("q_motor_stall", "Motor-Haltemoment (Stall)", 2.0, "N*m", ["c_knee_motor"],
            "motor.stall_torque"),
        _dm("q_motor_noload", "Motor-Leerlaufdrehzahl", 300.0, "rad/s", "~2865 rpm", "motor.noload_speed"),
        _dm("q_gear", "Getriebeuntersetzung", 40.0, "1", "Harmonic Drive", "drivetrain.gear_ratio"),
        _dm("q_eff", "Antriebsstrang-Wirkungsgrad", 0.85, "1", "Getriebe+Lager", "drivetrain.efficiency"),
        # --- balance + gait + swing dynamics ---
        _dm("q_com_x", "CoM-Versatz", 0.0, "m", "zentriert", "balance.com_x"),
        _dm("q_com_h", "CoM-Höhe", 0.55, "m", "Schwerpunkthöhe (kleiner Humanoid)", "balance.com_height"),
        _dm("q_smin", "Stützpolygon min x", -0.10, "m", "Fußkante hinten", "balance.support_min_x"),
        _dm("q_smax", "Stützpolygon max x", 0.10, "m", "Fußkante vorn", "balance.support_max_x"),
        _dm("q_sway", "CoM-Schwankungsamplitude", 0.04, "m", "seitliche Gang-Schwankung",
            "gait.com_amplitude"),
        _dm("q_step_f", "Schrittfrequenz", 0.45, "Hz", "Gang-Kadenz", "gait.step_frequency"),
        _dm("q_limb_I", "Schenkel-Trägheit um das Gelenk", rod_inertia_about_end(2.0, 0.18), "kg*m^2",
            "m·L²/3 (gleichförmiger Stab um die Hüfte, kanonische Formel) — konsistent zu q_limb_m/q_l1",
            "limb.inertia"),
        _dm("q_limb_m", "Schenkel-Masse", 2.0, "kg", "Glied+Motor", "limb.mass"),
        _dm("q_limb_d", "Schenkel-Schwerpunktabstand", 0.09, "m", "Gelenk→CoM", "limb.com_distance"),
        _dm("q_swing", "Schwung-Amplitude", 0.4, "rad", "Knie-Schwung im Schritt", "swing.amplitude"),
        _dm("q_avail_tau", "verfügbares Aktuator-Drehmoment", 80.0, "N*m",
            "Stall·Getriebe·η am Gelenk", "actuator.available_torque"),
        # --- onboard compute: the brain (the "which chip" answer) ---
        _dm("q_workload", "KI-Rechenlast (Wahrnehmung+Regelung)", 35.0, "1",
            "Personen-/Objekt-Erkennung + Ganzkörper-Policy, INT8-TOPS", "compute.workload_tops"),
        _gm("q_chip_tops", "Chip-Spitzenleistung (Jetson Orin NX)", 100.0, "1", ["c_orin"],
            "compute.chip_tops"),
        _dm("q_util", "nachhaltige Auslastung", 0.6, "1", "real haltbarer Anteil der Spitze",
            "compute.utilisation"),
        _dm("q_chip_eff", "Recheneffizienz", 4.0, "1", "≈100 TOPS / 25 W (Orin NX)",
            "compute.efficiency_tops_per_w"),
        _dm("q_chip_pbudget", "Compute-Leistungsbudget", 40.0, "W", "thermisch+Akku für die Recheneinheit",
            "compute.power_budget"),
        _dm("q_inf_ops", "Operationen je Regel-Inferenz", 5.0e7, "1", "Policy-Netz je Regelschritt",
            "compute.inference_ops"),
        _dm("q_chip_throughput", "Chip-Durchsatz", 1.0e14, "1", "100 TOPS = 1e14 ops/s",
            "compute.throughput_ops_per_s"),
        _dm("q_ctrl_period", "Regelschleifen-Periode", 1.0e-3, "s", "1 kHz Ganzkörper-Regelung",
            "control.period"),
        # --- sensor data bus: the digital nervous system (joint encoders + IMUs + F/T over CAN-FD) ---
        _dm("q_bus_n", "Bus-Teilnehmer (Encoder+IMU+F/T)", 30.0, "1",
            "≈30 Echtzeit-Sensoren am seriellen Bus", "bus.n_devices"),
        _dm("q_bus_bytes", "Bytes je Sensor-Sample", 8.0, "1", "Position+Status-Wort", "bus.bytes_per_sample"),
        _dm("q_bus_rate", "Sensor-Abtastrate", 1000.0, "1/s", "1 kHz Sensor-Schleife", "bus.sample_rate"),
        _dm("q_bus_bitrate", "Bus-Bitrate (CAN-FD)", 5.0e6, "1/s", "CAN-FD 5 Mbit/s", "bus.bitrate"),
    ]

    components = [
        Component(id="c_pelvis", name="Becken", geometry=_link(
            "q_pelvis_x", "q_pelvis_y", "q_pelvis_z", "q_r_hip", "q_pelvis_neg", "q_r_hip", "q_pelvis_off"),
            quantity_ids=["q_pelvis_x", "q_pelvis_y", "q_pelvis_z", "q_r_hip", "q_pelvis_off",
                          "q_pelvis_neg", "q_zero"], material_density="q_density"),
        Component(id="c_torso", name="Rumpf", geometry=_link(
            "q_torso_x", "q_torso_y", "q_torso_z", "q_r_spine", "q_torso_neg", "q_r_shoulder", "q_torso_off"),
            quantity_ids=["q_torso_x", "q_torso_y", "q_torso_z", "q_r_spine", "q_r_shoulder",
                          "q_torso_off", "q_torso_neg", "q_zero"], material_density="q_density"),
        Component(id="c_head", name="Kopf", geometry=_link(
            "q_head_x", "q_head_y", "q_head_z", "q_r_neck", "q_head_neg", "q_r_cam", "q_head_off"),
            quantity_ids=["q_head_x", "q_head_y", "q_head_z", "q_r_neck", "q_r_cam", "q_head_off",
                          "q_head_neg", "q_zero"], material_density="q_density"),
        Component(id="c_thigh", name="Oberschenkel-Glied", geometry=_link(
            "q_thigh_x", "q_thigh_y", "q_thigh_z", "q_r_hip", "q_thigh_neg", "q_r_knee", "q_thigh_off"),
            quantity_ids=["q_thigh_x", "q_thigh_y", "q_thigh_z", "q_r_hip", "q_r_knee", "q_thigh_off",
                          "q_thigh_neg", "q_zero"], material_density="q_density"),
        Component(id="c_shank", name="Unterschenkel-Glied", geometry=_link(
            "q_shank_x", "q_shank_y", "q_shank_z", "q_r_ankle", "q_shank_neg", "q_r_knee", "q_shank_off"),
            quantity_ids=["q_shank_x", "q_shank_y", "q_shank_z", "q_r_ankle", "q_r_knee", "q_shank_off",
                          "q_shank_neg", "q_zero"], material_density="q_density"),
        Component(id="c_uarm", name="Oberarm-Glied", geometry=_link(
            "q_uarm_x", "q_uarm_y", "q_uarm_z", "q_r_shoulder", "q_uarm_neg", "q_r_elbow", "q_uarm_off"),
            quantity_ids=["q_uarm_x", "q_uarm_y", "q_uarm_z", "q_r_shoulder", "q_r_elbow", "q_uarm_off",
                          "q_uarm_neg", "q_zero"], material_density="q_density"),
        Component(id="c_farm", name="Unterarm-Glied", geometry=_link(
            "q_farm_x", "q_farm_y", "q_farm_z", "q_r_elbow", "q_farm_neg", "q_r_wrist", "q_farm_off"),
            quantity_ids=["q_farm_x", "q_farm_y", "q_farm_z", "q_r_elbow", "q_r_wrist", "q_farm_off",
                          "q_farm_neg", "q_zero"], material_density="q_density"),
        Component(id="c_foot", name="Fuß", geometry=_link(
            "q_foot_x", "q_foot_y", "q_foot_z", "q_r_ankle", "q_foot_neg", "q_r_toe", "q_foot_off"),
            quantity_ids=["q_foot_x", "q_foot_y", "q_foot_z", "q_r_ankle", "q_r_toe", "q_foot_off",
                          "q_foot_neg", "q_zero"], material_density="q_density"),
    ]

    bom = [
        BomItem(id="b_pelvis", name="Becken (gedruckt)", role=BomRole.PART, count=1,
                component_id="c_pelvis", domain=BomDomain.MECHANICAL, grounding=["c_humanoid_anchor"]),
        BomItem(id="b_torso", name="Rumpf (gedruckt)", role=BomRole.PART, count=1,
                component_id="c_torso", domain=BomDomain.MECHANICAL, grounding=["c_humanoid_anchor"]),
        BomItem(id="b_head", name="Kopf (gedruckt)", role=BomRole.PART, count=1,
                component_id="c_head", domain=BomDomain.MECHANICAL, grounding=["c_humanoid_anchor"]),
        BomItem(id="b_thigh", name="Oberschenkel-Glied (gedruckt)", role=BomRole.PART, count=2,
                component_id="c_thigh", domain=BomDomain.MECHANICAL, grounding=["c_humanoid_anchor"]),
        BomItem(id="b_shank", name="Unterschenkel-Glied (gedruckt)", role=BomRole.PART, count=2,
                component_id="c_shank", domain=BomDomain.MECHANICAL, grounding=["c_humanoid_anchor"]),
        BomItem(id="b_uarm", name="Oberarm-Glied (gedruckt)", role=BomRole.PART, count=2,
                component_id="c_uarm", domain=BomDomain.MECHANICAL, grounding=["c_humanoid_anchor"]),
        BomItem(id="b_farm", name="Unterarm-Glied (gedruckt)", role=BomRole.PART, count=2,
                component_id="c_farm", domain=BomDomain.MECHANICAL, grounding=["c_humanoid_anchor"]),
        BomItem(id="b_foot", name="Fuß (gedruckt)", role=BomRole.PART, count=2,
                component_id="c_foot", domain=BomDomain.MECHANICAL, grounding=["c_humanoid_anchor"]),
        BomItem(id="b_motors", name="BLDC-Gelenkmotor (~2.0 N*m Stall, mit Harmonic-Drive 40:1)",
                role=BomRole.PART, count=10, domain=BomDomain.MECHANICAL, grounding=["c_knee_motor"]),
        BomItem(id="b_bearings", name="Rillenkugellager 6800-2RS (10 mm)", role=BomRole.PART, count=20,
                domain=BomDomain.MECHANICAL, grounding=["c_bearing_price"],
                sourcing=Sourcing(supplier="(Lagerhandel)", part_number="6800-2RS",
                                  price_quantity_id="q_bearing_price", grounding=["c_bearing_price"])),
        BomItem(id="b_bolts", name="M4x16-Innensechskantschraube", role=BomRole.PART, count=40,
                domain=BomDomain.MECHANICAL, grounding=["c_bolt_src"],
                sourcing=Sourcing(supplier="McMaster-Carr", part_number="91290A115",
                                  price_quantity_id="q_bolt_price", grounding=["c_bolt_src", "c_bolt_price"])),
        BomItem(id="b_compute", name="Onboard-Recheneinheit NVIDIA Jetson Orin NX (~100 TOPS)",
                role=BomRole.PART, count=1, domain=BomDomain.ELECTRONIC, grounding=["c_orin"]),
        BomItem(id="b_mcu", name="Echtzeit-MCU (STM32-Klasse) für Gelenk-Regelung", role=BomRole.PART,
                count=1, domain=BomDomain.ELECTRONIC),
        BomItem(id="b_drivers", name="FOC-BLDC-Motortreiber (ein Kanal je Gelenk)", role=BomRole.PART,
                count=10, domain=BomDomain.ELECTRONIC, grounding=["c_driver"]),
        BomItem(id="b_imu", name="6-Achsen-IMU (Bosch BMI088)", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC, grounding=["c_imu"]),
        BomItem(id="b_battery", name="6S-LiPo-Akku (22.2 V)", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC, grounding=["c_lipo"]),
        BomItem(id="b_harness", name="Kabelbaum + Stromverteilung", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC),
        BomItem(id="b_printer", name="3D-Drucker", role=BomRole.TOOL, count=1),
        BomItem(id="b_press", name="Lager-Einpresswerkzeug", role=BomRole.TOOL, count=1),
        BomItem(id="b_hex", name="4-mm-Innensechskantschlüssel", role=BomRole.TOOL, count=1),
        BomItem(id="b_solder", name="Lötkolben + Kabelwerkzeug", role=BomRole.TOOL, count=1),
    ]

    steps = [
        Step(id="s1", index=1, action="Alle acht Strukturteile drucken (Becken, Rumpf, Kopf, "
             "2x Oberschenkel, 2x Unterschenkel, 2x Oberarm, 2x Unterarm, 2x Fuß).",
             uses=["b_printer"], inputs=["b_pelvis", "b_torso", "b_head", "b_thigh", "b_shank",
                                         "b_uarm", "b_farm", "b_foot"], outputs=["a_printed"],
             check="Alle Teile gedruckt; alle Bohrungen frei und maßhaltig.",
             tool="3D-Drucker", quantity_refs=["q_thigh_x", "q_torso_x"]),
        Step(id="s2", index=2, action="Die 20 Lager in alle Gelenkbohrungen einpressen.",
             uses=["b_press", "b_bearings"], inputs=["a_printed"], outputs=["a_bearing"],
             check="Lager sitzen fest und laufen frei."),
        Step(id="s3", index=3, action="Die zehn BLDC-Gelenkmotoren montieren (2x Hüfte, 2x Knie, "
             "2x Schulter, 2x Ellbogen, 1x Spine, 1x Hals) und verschrauben.",
             uses=["b_hex", "b_bolts", "b_motors"], inputs=["a_bearing"], outputs=["a_jointed"],
             check="Alle zehn Gelenke bewegen sich frei; Motorwellen fluchten mit den Pivots.",
             tool="4-mm-Innensechskantschlüssel", torque_quantity_id="q_torque",
             quantity_refs=["q_knee_torque"]),
        Step(id="s4", index=4, action="Recheneinheit, MCU, zehn Motortreiber, IMU und Akku im Rumpf "
             "montieren und den Kabelbaum verlegen.",
             uses=["b_solder", "b_harness"], inputs=["a_jointed", "b_compute", "b_mcu", "b_drivers",
                                                     "b_imu", "b_battery"], outputs=["a_wired"],
             check="Jeder Motor an seinem Treiber; IMU im Rumpf; Recheneinheit bootet."),
        Step(id="s5", index=5, action="Statische + dynamische Endprüfung: Knie hält die Auslegungslast, "
             "Schwung bleibt im Drehmoment-Budget, ZMP im Stützpolygon, Compute-Budget eingehalten.",
             inputs=["a_wired"], outputs=["a_done"],
             check="electric_actuator-Reserve > 1; joint_swing_torque-Reserve > 1; ZMP im Stützpolygon; "
                   "compute_budget- und inference_power-Reserve > 1.",
             quantity_refs=["q_knee_torque", "q_avail_tau", "q_workload", "q_chip_tops"]),
    ]

    constraints = [
        Constraint(id="k_stress", kind="le", left="q_sigma_peak", right="q_strength",
                   reason="die Spitzenspannung am Hüft-Loch des Oberschenkel-Glieds bleibt unter der "
                          "PLA-Festigkeit — notwendig, nicht hinreichend"),
        Constraint(id="k_dfm_thigh_wall", kind="ge", left="q_thigh_z", right="q_min_wall",
                   reason="die Oberschenkel-Dicke ist mindestens die kleinste druckbare FDM-Wand"),
        Constraint(id="k_dfm_farm_wall", kind="ge", left="q_farm_z", right="q_min_wall",
                   reason="die Unterarm-Dicke ist mindestens die kleinste druckbare FDM-Wand"),
        Constraint(id="k_dfm_knee_hole", kind="ge", left="q_knee_bore_d", right="q_min_hole",
                   reason="die Knie-Bohrung ist mindestens der kleinste druckbare FDM-Lochdurchmesser"),
    ]

    decisions = [
        Decision(id="d_mat", title="Material", choice="PLA, 3D-gedruckt (Prototyp)",
                 rationale="maximal gedruckt je 3D-Drucker-Direktive; Prototyp-Last — eine "
                           "lasttragende Serien-Baugruppe braucht Alu/CFK", informed_by=["c_pla"]),
        Decision(id="d_chip", title="Recheneinheit", choice="NVIDIA Jetson Orin NX (~100 TOPS)",
                 rationale="deckt Wahrnehmung + Ganzkörper-Policy mit Reserve bei ~25 W",
                 informed_by=["c_orin"]),
        Decision(id="d_actuation", title="Aktuation", choice="BLDC + Harmonic Drive 40:1, FOC-Treiber",
                 rationale="hohe Drehmomentdichte und Rückfahrbarkeit für Gelenke", informed_by=["c_knee_motor"]),
    ]

    return Specification(
        run_id="humanoid",
        idea="Ein Ganzkörper-Humanoid (Becken, Rumpf, Kopf, zwei Arme, zwei Beine; zehn angetriebene "
             "Gelenke) mit druckbaren Strukturteilen, Onboard-Recheneinheit und der vollständigen "
             "Kaufliste — gegatet gegen Tragwerk, Kinematik, Aktuation, Compute, Balance und Schwung",
        approach_id="ap_humanoid", quantities=quantities, components=components, bom=bom,
        steps=steps, constraints=constraints, decisions=decisions,
        gaps=[
            "PLA ist für den druckbaren PROTOTYP; ein lasttragender Serien-Humanoid in voller Baugröße "
            "braucht Aluminium oder CFK — der σ-Check nutzt PLA bei Prototyp-Last (SF 2).",
            "Die acht Strukturteile sind als repräsentative druckbare Brackets (Kasten mit zwei "
            "Hauptbohrungen) modelliert; ein Serienteil trägt Versteifungsrippen, Kabelkanäle und alle "
            "Befestigungspunkte, die hier nicht einzeln ausmodelliert sind.",
            "Die Gelenkmotoren, die Recheneinheit, der Akku und die Treiber sind über Kennwerte "
            "(Stall-Moment, TOPS, Spannung) spezifiziert; konkrete SKUs/Preise liefert die Live-α-Recherche "
            "nach (daher teils unbepreist in der Stückliste).",
            "Geprüft sind statisches Halten, Onboard-Compute-Budget und die deterministischen "
            "Dynamik-Screens (2R-Reichweite, Aktuator-Sizing, ZMP über die Gang-Trajektorie, "
            "Schwung-Drehmoment); der volle Mehrgelenk-Kontakt-Gang läuft im externen Simulator über die "
            "URDF-Brücke (PyBullet/Isaac), nicht in diesem Gate.",
        ],
        claim_ids_used=[c.id for c in humanoid_claims()], produced_by="humanoid",
    )
