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
"""

from __future__ import annotations

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
    Component,
    Constraint,
    Decision,
    Derivation,
    GeometryNode,
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
        _claim("c_anchor", "Cantilever brackets are used for wall-mounted LED shelves."),
        _claim("c_load", "A typical wall shelf must carry a load of 12 kg."),
        _claim("c_screw", "An M4 screw has a nominal diameter of 4 mm."),
        _claim("c_iso273",
               "ISO 273 specifies a medium clearance hole diameter of 4.5 mm for an M4 screw."),
        _claim("c_led", "The LED strip runs at 12 V and draws 1.5 A."),
        _claim("c_psu", "The power supply provides 12 V at up to 2 A."),
        _claim("c_src", "McMaster-Carr lists part 91290A115, an M4x16 socket head screw."),
        _claim("c_price",
               "The M4x16 socket head screw costs 0.42 EUR per piece at McMaster-Carr."),
        _claim("c_gravity", "Standard gravity is defined as 9.80665 m/s^2."),
        _claim("c_pla",
               "FDM-printed PLA loaded in-plane (along the print layers) has a "
               "tensile strength of about 50 MPa."),
        _claim("c_kirsch",
               "A circular hole in a plate under tension has a stress "
               "concentration factor of 3 (Kirsch solution)."),
        _claim("c_screw_class",
               "An ISO 898-1 property class 8.8 screw has an ultimate tensile "
               "strength of 800 MPa."),
        _claim("c_screw_area",
               "An M4 coarse-pitch screw has a tensile stress area of 8.78 mm^2."),
        _claim("c_screw_shear",
               "EN 1993-1-8 gives a shear coefficient of 0.6 for property class "
               "8.8 bolts."),
    ]


def _g(qid, name, value, unit, grounding):
    return Quantity(id=qid, name=name, value=value, unit=unit,
                    origin=ValueOrigin.GROUNDED, grounding=grounding)


def _d(qid, name, value, unit, rationale):
    return Quantity(id=qid, name=name, value=value, unit=unit,
                    origin=ValueOrigin.DECISION, rationale=rationale)


def _der(qid, name, value, unit, formula, inputs):
    return Quantity(id=qid, name=name, value=value, unit=unit,
                    origin=ValueOrigin.DERIVED,
                    derivation=Derivation(formula=formula, inputs=inputs))


def capstone_spec() -> Specification:
    quantities = [
        _g("q_load", "verified shelf load", 12.0, "kg", ["c_load"]),
        _g("q_screw_d", "screw diameter", 4.0, "mm", ["c_screw"]),
        _g("q_hole_d", "clearance hole diameter", 4.5, "mm", ["c_iso273"]),
        _d("q_sf", "safety factor", 2.0, "1", "conservative for static indoor load"),
        _der("q_design", "design load", 24.0, "kg", "q_load * q_sf", ("q_load", "q_sf")),
        _der("q_hole_r", "hole radius", 2.25, "mm", "q_hole_d / 2", ("q_hole_d",)),
        _d("q_w", "bracket projection", 60.0, "mm",
           "shelf projection depth from the wall — the load's lever arm (L)"),
        _d("q_h", "bracket breadth", 80.0, "mm",
           "breadth across the wall — the bending section breadth (b)"),
        _d("q_t", "bracket thickness", 12.0, "mm",
           "section depth in the load direction (h); sized so the peak hole stress "
           "at the design load stays below the in-plane PLA strength"),
        _d("q_density", "PLA density", 0.00124, "g/mm^3", "PLA ~1.24 g/cm³ per mm³"),
        _g("q_led_v", "LED voltage", 12.0, "V", ["c_led"]),
        _g("q_led_a", "LED current", 1.5, "A", ["c_led"]),
        _g("q_psu_v", "PSU voltage", 12.0, "V", ["c_psu"]),
        _g("q_psu_a", "PSU current", 2.0, "A", ["c_psu"]),
        _d("q_torque", "bolt torque", 2.5, "N*m", "M4 in plastic, snug"),
        _g("q_price", "screw unit price", 0.42, "EUR", ["c_price"]),
        # δ-layer-2 statics: does the bracket hold the verified load — counting the
        # safety factor, the mount-hole stress raiser, the print orientation, and
        # the fastener shear? Each value is grounded (g, Kt, strength, screw specs)
        # or recomputed (force, stress, capacity); GENESIS does the arithmetic
        # (verification/derivation.py), GATE γ recomputes it (C-6), checks it
        # dimensionally (C-15), and tests every verdict numerically (C-13).
        _g("q_g", "standard gravity", STANDARD_GRAVITY, "m/s^2", ["c_gravity"]),
        _der("q_force", "design-load force at the bracket tip",
             24.0 * STANDARD_GRAVITY, "N",
             weight_formula("q_design", "q_g"), ("q_design", "q_g")),
        _der("q_sigma_nom", "nominal bending stress at the design load "
             "(cantilever, arm=q_w, b=q_h, h=q_t)",
             6.0 * (24.0 * STANDARD_GRAVITY) * 60.0 / (80.0 * 12.0 * 12.0), "MPa",
             cantilever_bending_stress_formula("q_force", "q_w", "q_h", "q_t"),
             ("q_force", "q_w", "q_h", "q_t")),
        _g("q_kt", "stress concentration factor (circular hole, Kirsch)",
           STRESS_CONCENTRATION_CIRCULAR_HOLE, "1", ["c_kirsch"]),
        _der("q_sigma_peak", "peak stress at the mounting hole",
             STRESS_CONCENTRATION_CIRCULAR_HOLE
             * (6.0 * (24.0 * STANDARD_GRAVITY) * 60.0 / (80.0 * 12.0 * 12.0)), "MPa",
             peak_stress_formula("q_sigma_nom", "q_kt"), ("q_kt", "q_sigma_nom")),
        _g("q_strength", "in-plane PLA tensile strength", 50.0, "MPa", ["c_pla"]),
        # fastener shear (bracket-side, EN 1993-1-8): demand per screw vs capacity
        _g("q_bolt_uts", "class-8.8 screw ultimate tensile strength",
           BOLT_UTS_CLASS_88_MPA, "MPa", ["c_screw_class"]),
        _g("q_bolt_area", "M4 tensile stress area",
           M4_TENSILE_STRESS_AREA_MM2, "mm^2", ["c_screw_area"]),
        _g("q_shear_coeff", "EN 1993-1-8 shear coefficient (class 8.8)",
           BOLT_SHEAR_COEFFICIENT_88, "1", ["c_screw_shear"]),
        _der("q_screw_shear_cap", "per-screw shear capacity",
             BOLT_SHEAR_COEFFICIENT_88 * BOLT_UTS_CLASS_88_MPA
             * M4_TENSILE_STRESS_AREA_MM2, "N",
             bolt_shear_capacity_formula("q_shear_coeff", "q_bolt_uts", "q_bolt_area"),
             ("q_shear_coeff", "q_bolt_uts", "q_bolt_area")),
        _d("q_n_screws", "number of mounting screws", 2.0, "1",
           "two mounting screws (matches BOM item b_screw)"),
        _der("q_screw_shear", "shear demand per screw at the design load",
             (24.0 * STANDARD_GRAVITY) / 2.0, "N",
             per_fastener_shear_formula("q_force", "q_n_screws"),
             ("q_force", "q_n_screws")),
        _d("sx", "available width", 200.0, "mm", "shelf niche width"),
        _d("sy", "available height", 200.0, "mm", "shelf niche height"),
        _d("sz", "available depth", 200.0, "mm", "shelf niche depth"),
    ]
    geometry = GeometryNode(kind="difference", children=[
        GeometryNode(kind="box", params={"size_x": "q_w", "size_y": "q_h", "size_z": "q_t"}),
        GeometryNode(kind="cylinder", params={"radius": "q_hole_r", "height": "q_t"}),
    ])
    components = [
        Component(id="c_bracket", name="bracket", geometry=geometry,
                  quantity_ids=["q_w", "q_h", "q_t", "q_hole_d", "q_hole_r"],
                  material_density="q_density"),
    ]
    bom = [
        BomItem(id="b_bracket", name="bracket", role=BomRole.PART, count=1,
                component_id="c_bracket", domain=BomDomain.MECHANICAL),
        BomItem(id="b_screw", name="M4x16 socket head screw", role=BomRole.PART, count=2,
                domain=BomDomain.MECHANICAL, grounding=["c_screw"],
                sourcing=Sourcing(supplier="McMaster-Carr", part_number="91290A115",
                                  price_quantity_id="q_price", grounding=["c_src", "c_price"])),
        BomItem(id="b_led", name="12 V LED strip", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC, grounding=["c_led"]),
        BomItem(id="b_psu", name="12 V / 2 A power supply", role=BomRole.PART, count=1,
                domain=BomDomain.ELECTRONIC, grounding=["c_psu"]),
        BomItem(id="b_printer", name="3D printer", role=BomRole.TOOL, count=1),
        BomItem(id="b_hex", name="4 mm hex key", role=BomRole.TOOL, count=1),
    ]
    steps = [
        Step(id="s1", index=1, action="3D-print the bracket per its CSG geometry.",
             uses=["b_printer"], inputs=["b_bracket"], outputs=["a_printed"],
             check="Printed part measures 60 x 80 x 12 mm within tolerance.",
             tool="3D printer", quantity_refs=["q_w", "q_h", "q_t"]),
        Step(id="s2", index=2, action="Mount the bracket to the wall with both screws.",
             uses=["b_hex", "b_screw"], inputs=["a_printed"], outputs=["a_mounted"],
             check="Bracket carries the design load without movement.",
             tool="4 mm hex key", torque_quantity_id="q_torque", quantity_refs=["q_design"]),
        Step(id="s3", index=3, action="Attach the LED strip and connect the power supply.",
             uses=["b_led", "b_psu"], inputs=["a_mounted"], outputs=["a_done"],
             check="LED lights at 12 V; supply current within its 2 A rating.",
             quantity_refs=["q_led_v", "q_psu_a"]),
    ]
    constraints = [
        Constraint(id="k_fit", kind="ge", left="q_hole_d", right="q_screw_d",
                   reason="clearance hole admits the screw"),
        Constraint(id="k_volt", kind="eq", left="q_led_v", right="q_psu_v",
                   reason="supply voltage must match the LED strip"),
        Constraint(id="k_curr", kind="ge", left="q_psu_a", right="q_led_a",
                   reason="supply current must meet the LED draw"),
        Constraint(id="k_wall", kind="ge", left="q_t", right="max(2, 0.05 * q_w)",
                   reason="wall thickness at least 2 mm or 5% of width"),
        Constraint(id="k_stress", kind="le", left="q_sigma_peak", right="q_strength",
                   reason="peak hole stress at the design load (Kt·σ_nom) stays below "
                          "the in-plane PLA strength — necessary, not sufficient"),
        Constraint(id="k_shear", kind="le", left="q_screw_shear", right="q_screw_shear_cap",
                   reason="per-screw shear demand at the design load stays below the "
                          "class-8.8 screw shear capacity (bracket-side fastener limit)"),
    ]
    decisions = [
        Decision(id="d_mat", title="Material", choice="PLA, 3D-printed",
                 rationale="available; sufficient for static indoor load"),
        Decision(id="d_hole", title="Hole type",
                 choice="through / clearance hole (ISO 273 medium)",
                 rationale="bolt passes through the bracket", informed_by=["c_iso273"]),
        Decision(id="d_print", title="Print orientation",
                 choice="on-edge — print layers parallel to the bending stress",
                 rationale="FDM interlayer bonds are ~30-50% weaker than in-plane; "
                           "orienting the layers in-plane keeps the loaded direction at "
                           "the higher in-plane strength used in the stress check",
                 informed_by=["c_pla"]),
    ]
    site = SiteRequirements(
        available_space=("sx", "sy", "sz"),
        requirements=[
            Decision(id="d_loc", title="Location", choice="indoor, dry wall",
                     rationale="electronics are not weatherproof"),
            Decision(id="d_vent", title="Ventilation",
                     choice="passive, 5 cm clearance above the PSU",
                     rationale="dissipate power-supply heat"),
        ],
    )
    return Specification(
        run_id="capstone",
        idea="A wall-mounted LED shelf bracket carrying the verified load",
        approach_id="ap1", quantities=quantities, components=components, bom=bom,
        steps=steps, constraints=constraints, decisions=decisions, site=site,
        gaps=[
            # The σ-check now counts the safety factor, the Kirsch hole stress raiser,
            # the print orientation and the fastener shear. What honestly remains is
            # external or declared-out — narrowed, not a blanket disclaimer.
            "Fastener PULL-OUT from the wall is not checked — it depends on the wall "
            "substrate and anchor (drywall plug vs concrete vs timber), which the "
            "spec does not fix; only the bracket-side screw shear is checked.",
            "The hole stress uses the conservative Kirsch Kt=3 (uniaxial circular "
            "hole); the exact bending / finite-width peak (≤3) needs FEM or "
            "Peterson's tables.",
            "Fatigue and dynamic / impact loading are out of scope by the declared "
            "static indoor-load case; only the static design load (safety factor 2) "
            "is checked.",
            "The 50 MPa in-plane strength assumes a good print (high infill, correct "
            "temperature) at the declared on-edge orientation; a poor or wrongly "
            "oriented print is weaker.",
        ],
        claim_ids_used=[c.id for c in capstone_claims()], produced_by="capstone",
    )


def capstone_state() -> RunState:
    """The full RunState (claims + approach + spec) for gate verification."""
    st = RunState(question=Question(raw="led shelf bracket", run_id="capstone"))
    st.claims = capstone_claims()
    st.approaches = [Approach(id="ap1", name="Cantilever LED bracket", grounding=["c_anchor"])]
    st.specification = capstone_spec()
    return st
