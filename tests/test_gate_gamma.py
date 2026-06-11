"""Tests for GATE γ — proving the Phase γ guarantee WITHOUT any LLM.

These tests are the executable form of PHASE_GAMMA.md §5/§6. They run with plain
pytest, no models, no network. If these are green, the γ gate logic is provably
correct; the architect then only has to feed it honest data.

The γ guarantee in one line: a specification may contain no fabricated value
(grounded = literally in a VERIFIED claim), no unrecomputable arithmetic, no
dangling reference, no hidden decision, and no structurally incomplete step.
Each test below attacks exactly one of those faces; the happy path proves a
complete, honest build plan passes.

Run:  pytest tests/test_gate_gamma.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make src importable without packaging during early dev.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.errors import (  # noqa: E402
    InvalidDerivationError,
    UndeclaredDecisionError,
    UngroundedValueError,
)
from gen.core.state import (  # noqa: E402
    Approach,
    BomItem,
    BomRole,
    Claim,
    ClaimStatus,
    Component,
    Constraint,
    Decision,
    Derivation,
    GeometryNode,
    Quantity,
    Question,
    RunState,
    SourceRef,
    SourceSupport,
    Specification,
    Step,
    ValueOrigin,
)
from gen.verification.gates import gate_gamma, value_in_text  # noqa: E402


# --- builders ----------------------------------------------------------------

def _src(url: str, retrieved: bool = True) -> SourceRef:
    return SourceRef(url_or_id=url, retrieved=retrieved, support=SourceSupport.SUPPORTS)


def _claim(
    cid: str,
    text: str,
    *,
    status: ClaimStatus = ClaimStatus.VERIFIED,
    confidence: float = 0.9,
    retrieved: bool = True,
) -> Claim:
    return Claim(
        id=cid,
        text=text,
        sources=[_src(f"https://example.org/{cid}", retrieved=retrieved)],
        status=status,
        confidence=confidence,
        verification=[_src(f"https://independent.org/{cid}")]
        if status is ClaimStatus.VERIFIED
        else [],
    )


def _grounded(qid: str, name: str, value: float, unit: str, grounding: list[str]) -> Quantity:
    return Quantity(
        id=qid, name=name, value=value, unit=unit,
        origin=ValueOrigin.GROUNDED, grounding=grounding,
    )


def _decision_q(qid: str, name: str, value: float, unit: str, rationale: str = "chosen deliberately") -> Quantity:
    return Quantity(
        id=qid, name=name, value=value, unit=unit,
        origin=ValueOrigin.DECISION, rationale=rationale,
    )


def _derived(qid: str, name: str, value: float, unit: str, formula: str, inputs: tuple[str, ...]) -> Quantity:
    return Quantity(
        id=qid, name=name, value=value, unit=unit,
        origin=ValueOrigin.DERIVED,
        derivation=Derivation(formula=formula, inputs=inputs),
    )


def _happy_state() -> RunState:
    """A complete, honest wall-bracket specification that must pass GATE γ.

    Exercises every element: grounded values (literally in claim texts), a
    derived chain (recomputable), decision quantities + a decision sheet, CSG
    geometry (difference of box and cylinder), BOM with part/tool roles, two
    topologically buildable steps with checks, and a satisfied constraint —
    anchored in a grounded approach (β chain).
    """
    claims = [
        _claim("c_load", "The shelf must carry a load of 12 kg."),
        _claim("c_screw", "An M4 screw has a nominal diameter of 4 mm."),
        _claim("c_anchor", "Cantilever brackets are used for wall-mounted shelves."),
    ]
    approach = Approach(id="ap1", name="Cantilever bracket", grounding=["c_anchor"])

    quantities = [
        _grounded("q_load", "verified shelf load", 12.0, "kg", ["c_load"]),
        _grounded("q_screw_d", "screw diameter", 4.0, "mm", ["c_screw"]),
        _decision_q("q_sf", "safety factor", 2.0, "1", "conservative; 1.5 and 3 considered"),
        _derived("q_design", "design load", 24.0, "kg", "q_load * q_sf", ("q_load", "q_sf")),
        _decision_q("q_hole_d", "screw hole diameter", 4.5, "mm", "clearance fit for M4"),
        _derived("q_hole_r", "screw hole radius", 2.25, "mm", "q_hole_d / 2", ("q_hole_d",)),
        _decision_q("q_w", "bracket width", 60.0, "mm", "fits standard shelf depth"),
        _decision_q("q_h", "bracket height", 80.0, "mm", "lever arm for the load"),
        _decision_q("q_t", "bracket thickness", 6.0, "mm", "printable wall thickness"),
    ]

    geometry = GeometryNode(
        kind="difference",
        children=[
            GeometryNode(kind="box", params={"size_x": "q_w", "size_y": "q_h", "size_z": "q_t"}),
            GeometryNode(kind="cylinder", params={"radius": "q_hole_r", "height": "q_t"}),
        ],
    )
    components = [
        Component(
            id="c_bracket", name="bracket", geometry=geometry,
            quantity_ids=["q_w", "q_h", "q_t", "q_hole_d", "q_hole_r"],
        )
    ]
    bom = [
        BomItem(id="b_bracket", name="bracket", role=BomRole.PART, count=1, component_id="c_bracket"),
        BomItem(id="b_screw", name="M4 screw", role=BomRole.PART, count=2, grounding=["c_screw"]),
        BomItem(id="b_printer", name="3D printer", role=BomRole.TOOL, count=1),
        BomItem(id="b_driver", name="screwdriver", role=BomRole.TOOL, count=1),
    ]
    steps = [
        Step(
            id="s1", index=1, action="3D-print the bracket per its CSG geometry.",
            uses=["b_printer"], inputs=["b_bracket"], outputs=["a_printed"],
            check="Printed part measures q_w x q_h x q_t within printer tolerance.",
            quantity_refs=["q_w", "q_h", "q_t"],
        ),
        Step(
            id="s2", index=2, action="Mount the printed bracket to the wall with both screws.",
            uses=["b_driver", "b_screw"], inputs=["a_printed"], outputs=["a_mounted"],
            check="Bracket carries the design load q_design without movement.",
            quantity_refs=["q_design"],
        ),
    ]
    constraints = [
        Constraint(id="k1", kind="ge", left="q_hole_d", right="q_screw_d",
                   reason="screw must pass through the hole"),
    ]
    decisions = [
        Decision(id="d_mat", title="Material", choice="PLA, 3D-printed",
                 rationale="available locally; sufficient for indoor static load"),
    ]

    spec = Specification(
        run_id="r1", idea="wall-mounted shelf bracket", approach_id="ap1",
        quantities=quantities, components=components, bom=bom, steps=steps,
        constraints=constraints, decisions=decisions,
        claim_ids_used=["c_load", "c_screw", "c_anchor"],
        produced_by="architect",
    )

    st = RunState(question=Question(raw="wall-mounted shelf bracket", run_id="r1"))
    st.claims = claims
    st.approaches = [approach]
    st.specification = spec
    return st


def _codes(state: RunState) -> set[str]:
    return {f.code for f in gate_gamma(state).failures}


# --- the happy path -----------------------------------------------------------

def test_complete_honest_specification_passes():
    state = _happy_state()
    result = gate_gamma(state)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]


def test_abstention_passes_with_explicit_gap():
    state = _happy_state()
    state.specification = Specification(
        run_id="r1", idea="x",
        gaps=["No specification could be grounded for this idea."],
    )
    assert gate_gamma(state).passed  # honest emptiness asserts nothing


def test_missing_specification_fails():
    state = _happy_state()
    state.specification = None
    assert _codes(state) == {"NO_SPECIFICATION"}


# --- Wert (C-1..C-5): no fabricated value -------------------------------------

def test_constructor_rejects_grounded_without_grounding():
    with pytest.raises(UngroundedValueError):
        _grounded("q_bad", "x", 1.0, "mm", [])


def test_gate_backstops_ungrounded_value():
    state = _happy_state()
    state.specification.quantities[0].grounding = []  # bypass constructor: mutate
    assert "UNGROUNDED_VALUE" in _codes(state)


def test_unknown_grounding_claim_fails():
    state = _happy_state()
    state.specification.quantities[0].grounding = ["ghost"]
    assert "VALUE_UNKNOWN_CLAIM" in _codes(state)


def test_unverified_grounding_fails():
    state = _happy_state()
    state.claims[0].status = ClaimStatus.UNSUPPORTED
    assert "VALUE_NOT_VERIFIED" in _codes(state)


def test_underconfident_grounding_fails():
    state = _happy_state()
    state.claims[0].confidence = 0.2
    assert "VALUE_NOT_VERIFIED" in _codes(state)


def test_fabricated_value_not_in_claim_text_fails():
    state = _happy_state()
    state.specification.quantities[0].value = 14.0  # claim says 12 kg
    assert "VALUE_NOT_IN_GROUNDING" in _codes(state)


def test_value_must_not_borrow_digits_from_other_numbers():
    # "M15" contains the digit 5, but 5 is NOT stated in this claim.
    assert not value_in_text(5.0, "Use an M15 screw for the anchor.")
    assert value_in_text(15.0, "Use an M15 screw for the anchor.")
    assert value_in_text(4.0, "An M4 screw has a nominal diameter of 4 mm.")
    assert value_in_text(12.0, "The shelf must carry a load of 12 kg.")
    assert not value_in_text(0.5, "The board is 10.5 mm thick.")
    assert value_in_text(2.5, "Wall thickness of 2.5 mm is specified.")


def test_dead_citation_on_referenced_claim_fails():
    state = _happy_state()
    state.claims[0].sources = [_src("https://dead.example", retrieved=False)]
    assert "DEAD_CITATION" in _codes(state)


def test_refuted_claim_as_grounding_fails():
    state = _happy_state()
    state.claims[1].status = ClaimStatus.REFUTED
    codes = _codes(state)
    assert "REFUTED_AS_FACT" in codes and "VALUE_NOT_VERIFIED" in codes


# --- Rechnung (C-6): no arithmetic hallucination --------------------------------

def test_constructor_rejects_derived_without_derivation():
    with pytest.raises(InvalidDerivationError):
        Quantity(id="q", name="x", value=1.0, unit="mm", origin=ValueOrigin.DERIVED)


def test_wrong_derived_value_fails_recompute():
    state = _happy_state()
    q_design = next(q for q in state.specification.quantities if q.id == "q_design")
    q_design.value = 25.0  # 12 * 2 = 24, not 25
    assert "BROKEN_DERIVATION" in _codes(state)


def test_formula_outside_grammar_fails_recompute():
    state = _happy_state()
    q_design = next(q for q in state.specification.quantities if q.id == "q_design")
    q_design.derivation = Derivation(formula="q_load ** q_sf", inputs=("q_load", "q_sf"))
    assert "BROKEN_DERIVATION" in _codes(state)


def test_derivation_cycle_fails_recompute():
    state = _happy_state()
    spec = state.specification
    spec.quantities.append(
        _derived("q_a", "a", 1.0, "1", "q_b + 1", ("q_b",))
    )
    spec.quantities.append(
        _derived("q_b", "b", 2.0, "1", "q_a + 1", ("q_a",))
    )
    assert "BROKEN_DERIVATION" in _codes(state)


# --- Entscheidung (C-7): no hidden decision -------------------------------------

def test_constructor_rejects_decision_without_rationale():
    with pytest.raises(UndeclaredDecisionError):
        _decision_q("q", "x", 1.0, "mm", rationale="")
    with pytest.raises(UndeclaredDecisionError):
        Decision(id="d", title="t", choice="c", rationale="   ")


def test_gate_backstops_undeclared_decision():
    state = _happy_state()
    q_sf = next(q for q in state.specification.quantities if q.id == "q_sf")
    q_sf.rationale = ""  # bypass constructor: mutate
    state.specification.decisions[0].rationale = " "
    codes = _codes(state)
    assert "UNDECLARED_DECISION" in codes


def test_decision_informed_by_unknown_claim_fails():
    state = _happy_state()
    state.specification.decisions[0].informed_by = ["ghost"]
    assert "VALUE_UNKNOWN_CLAIM" in _codes(state)


# --- Drift (C-8/C-9): every reference resolves ----------------------------------

def test_step_using_unknown_bom_item_fails():
    state = _happy_state()
    state.specification.steps[0].uses = ["b_ghost"]
    assert "DANGLING_REFERENCE" in _codes(state)


def test_constraint_on_unknown_quantity_fails():
    state = _happy_state()
    state.specification.constraints[0].right = "q_ghost"
    assert "DANGLING_REFERENCE" in _codes(state)


def test_geometry_param_on_unknown_quantity_fails():
    state = _happy_state()
    geom = state.specification.components[0].geometry
    geom.children[0].params["size_x"] = "q_ghost"
    assert "DANGLING_REFERENCE" in _codes(state)


def test_component_quantity_and_bom_component_must_resolve():
    state = _happy_state()
    state.specification.components[0].quantity_ids.append("q_ghost")
    state.specification.bom[0].component_id = "c_ghost"
    codes = _codes(state)
    assert "DANGLING_REFERENCE" in codes


def test_material_density_must_resolve():
    state = _happy_state()
    state.specification.components[0].material_density = "q_ghost_density"
    assert "DANGLING_REFERENCE" in _codes(state)


def test_resolved_material_density_passes():
    state = _happy_state()
    spec = state.specification
    spec.quantities.append(_decision_q("q_rho", "PLA density", 0.00124, "g/mm^3"))
    spec.components[0].material_density = "q_rho"
    result = gate_gamma(state)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]


def test_duplicate_quantity_id_is_drift():
    state = _happy_state()
    state.specification.quantities.append(
        _decision_q("q_sf", "duplicate id", 3.0, "1", "duplicate")
    )
    assert "DANGLING_REFERENCE" in _codes(state)


def test_unknown_geometry_kind_fails():
    state = _happy_state()
    state.specification.components[0].geometry = GeometryNode(kind="torus", params={})
    assert "INVALID_GEOMETRY" in _codes(state)


def test_primitive_with_wrong_params_or_children_fails():
    state = _happy_state()
    geom = state.specification.components[0].geometry
    geom.children[0].params = {"size_x": "q_w", "size_y": "q_h"}  # size_z missing
    geom.children[1].children = [GeometryNode(kind="sphere", params={"radius": "q_t"})]
    codes = _codes(state)
    assert "INVALID_GEOMETRY" in codes


def test_operation_needs_two_children_and_no_params():
    state = _happy_state()
    state.specification.components[0].geometry = GeometryNode(
        kind="difference",
        params={"x": "q_w"},
        children=[GeometryNode(kind="sphere", params={"radius": "q_t"})],
    )
    codes = _codes(state)
    assert "INVALID_GEOMETRY" in codes


def test_transform_needs_exactly_one_child():
    state = _happy_state()
    state.specification.components[0].geometry = GeometryNode(
        kind="translate", params={"x": "q_w", "y": "q_h", "z": "q_t"}, children=[]
    )
    assert "INVALID_GEOMETRY" in _codes(state)


def test_non_positive_dimension_fails():
    state = _happy_state()
    q_t = next(q for q in state.specification.quantities if q.id == "q_t")
    q_t.value = 0.0
    assert "INVALID_GEOMETRY" in _codes(state)


# --- Vollständigkeit (C-10/C-11): structurally buildable -------------------------

def test_step_without_check_fails():
    state = _happy_state()
    state.specification.steps[1].check = "  "
    assert "INCOMPLETE_STEP" in _codes(state)


def test_step_without_action_fails():
    state = _happy_state()
    state.specification.steps[0].action = ""
    assert "INCOMPLETE_STEP" in _codes(state)


def test_duplicate_step_index_fails():
    state = _happy_state()
    state.specification.steps[1].index = 1
    assert "INCOMPLETE_STEP" in _codes(state)


def test_bom_count_below_one_fails():
    state = _happy_state()
    state.specification.bom[1].count = 0
    assert "INCOMPLETE_STEP" in _codes(state)


def test_input_never_produced_fails():
    state = _happy_state()
    state.specification.steps[1].inputs = ["a_never_made"]
    assert "UNBUILDABLE_ORDER" in _codes(state)


def test_input_produced_only_later_fails():
    state = _happy_state()
    s1, s2 = state.specification.steps
    s1.index, s2.index = 2, 1  # mounting now precedes printing
    assert "UNBUILDABLE_ORDER" in _codes(state)


def test_redefined_artifact_fails():
    state = _happy_state()
    state.specification.steps[1].outputs = ["a_printed"]
    assert "UNBUILDABLE_ORDER" in _codes(state)


# --- Maß (C-12/C-13): units and constraints --------------------------------------

def test_missing_unit_fails():
    state = _happy_state()
    q_sf = next(q for q in state.specification.quantities if q.id == "q_sf")
    q_sf.unit = "  "
    assert "UNIT_MISMATCH" in _codes(state)


def test_constraint_across_units_fails():
    state = _happy_state()
    state.specification.constraints[0].right = "q_load"  # mm vs kg
    assert "UNIT_MISMATCH" in _codes(state)


def test_violated_constraint_fails():
    state = _happy_state()
    q_hole = next(q for q in state.specification.quantities if q.id == "q_hole_d")
    q_hole.value = 3.5  # smaller than the 4 mm screw
    codes = _codes(state)
    assert "CONSTRAINT_VIOLATION" in codes


def test_unknown_constraint_kind_fails():
    state = _happy_state()
    state.specification.constraints[0].kind = "approx"
    assert "CONSTRAINT_VIOLATION" in _codes(state)


# --- Maß (C-15): dimensional homogeneity of derivations --------------------------

def test_adding_incommensurable_units_in_derivation_fails():
    # the Mars-Climate-Orbiter class: a derived value that adds kg to mm
    state = _happy_state()
    spec = state.specification
    spec.quantities.append(
        _derived("q_nonsense", "nonsense", 16.0, "kg", "q_load + q_w", ("q_load", "q_w"))
    )
    assert "DIMENSION_MISMATCH" in _codes(state)


def test_declared_unit_dimension_must_match_formula():
    # area (mm * mm) declared as a length (mm) -> dimension mismatch
    state = _happy_state()
    spec = state.specification
    spec.quantities.append(
        _derived("q_area", "area", 4800.0, "mm", "q_w * q_h", ("q_w", "q_h"))
    )
    codes = _codes(state)
    assert "DIMENSION_MISMATCH" in codes


def test_area_declared_with_correct_unit_passes():
    state = _happy_state()
    spec = state.specification
    spec.quantities.append(
        _derived("q_area", "area", 4800.0, "mm^2", "q_w * q_h", ("q_w", "q_h"))
    )
    result = gate_gamma(state)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]


def test_unit_conversion_derivation_is_dimensionally_valid():
    # 5 cm source -> 50 mm via q_src * 10: length * dimensionless = length. OK.
    state = _happy_state()
    spec = state.specification
    spec.quantities.append(_grounded("q_src", "source length", 5.0, "cm", ["c_screw"]))
    # c_screw text says "4 mm", not "5 cm" — so anchor q_src to a fresh claim
    state.claims.append(_claim("c_cm", "The plate edge is 5 cm wide."))
    spec.quantities[-1].grounding = ["c_cm"]
    spec.quantities.append(
        _derived("q_mm", "converted length", 50.0, "mm", "q_src * 10", ("q_src",))
    )
    result = gate_gamma(state)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]


def test_happy_state_derivations_are_dimensionally_clean():
    # the baseline bracket has q_design (kg) and q_hole_r (mm) — both must pass C-15
    state = _happy_state()
    assert "DIMENSION_MISMATCH" not in _codes(state)


# --- Maß (C-13): constraints over arithmetic expressions -------------------------

def test_expression_constraint_holds():
    # "wall thickness >= 0.1 * width": q_t=6 >= 0.1*60=6 -> holds (eq boundary)
    state = _happy_state()
    state.specification.constraints.append(
        Constraint(id="k_wall", kind="ge", left="q_t", right="0.1 * q_w",
                   reason="wall must be at least a tenth of the width")
    )
    result = gate_gamma(state)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]


def test_expression_constraint_violation():
    state = _happy_state()
    # q_t=6 must be >= 0.2*q_w=12 -> violated
    state.specification.constraints.append(
        Constraint(id="k_wall", kind="ge", left="q_t", right="0.2 * q_w", reason="x")
    )
    assert "CONSTRAINT_VIOLATION" in _codes(state)


def test_expression_constraint_unknown_id_is_dangling():
    state = _happy_state()
    state.specification.constraints.append(
        Constraint(id="k_x", kind="ge", left="q_t", right="0.1 * q_ghost", reason="x")
    )
    assert "DANGLING_REFERENCE" in _codes(state)


def test_expression_constraint_dimension_mismatch():
    state = _happy_state()
    # comparing a thickness (mm) to a load expression (kg) -> dimensions differ
    state.specification.constraints.append(
        Constraint(id="k_x", kind="le", left="q_t", right="q_load * 2", reason="x")
    )
    assert "UNIT_MISMATCH" in _codes(state)


def test_expression_constraint_mixes_units_of_same_dimension():
    state = _happy_state()
    spec = state.specification
    # q_t is mm; add a length in cm and compare -> same dimension, different unit
    spec.quantities.append(_decision_q("q_cm", "length in cm", 1.0, "cm"))
    spec.constraints.append(
        Constraint(id="k_mix", kind="ge", left="q_t", right="q_cm", reason="x")
    )
    assert "UNIT_MISMATCH" in _codes(state)


def test_internal_incommensurable_addition_in_constraint_fails():
    state = _happy_state()
    # left expression itself adds kg to mm -> dimensional nonsense inside the expr
    state.specification.constraints.append(
        Constraint(id="k_x", kind="ge", left="q_load + q_t", right="q_design", reason="x")
    )
    assert "DIMENSION_MISMATCH" in _codes(state)


# --- Plausibility constraints (declared, never invented) -------------------------

def test_positivity_plausibility_constraint():
    state = _happy_state()
    state.specification.constraints.append(
        Constraint(id="k_pos", kind="gt", left="q_t", right="0",
                   reason="thickness must be positive")
    )
    assert gate_gamma(state).passed
    # violate it: a negative thickness is now caught because the human declared it
    state.specification.quantities[
        next(i for i, q in enumerate(state.specification.quantities) if q.id == "q_t")
    ].value = -1.0
    assert "CONSTRAINT_VIOLATION" in _codes(state)


def test_range_and_monotonic_plausibility():
    state = _happy_state()
    spec = state.specification
    spec.quantities.append(_decision_q("q_min", "min width", 40.0, "mm"))
    spec.quantities.append(_decision_q("q_max", "max width", 80.0, "mm"))
    spec.constraints.append(Constraint(id="k_lo", kind="ge", left="q_w", right="q_min", reason="range lo"))
    spec.constraints.append(Constraint(id="k_hi", kind="le", left="q_w", right="q_max", reason="range hi"))
    # monotonic: height >= width >= thickness
    spec.constraints.append(Constraint(id="k_m1", kind="ge", left="q_h", right="q_w", reason="mono"))
    spec.constraints.append(Constraint(id="k_m2", kind="ge", left="q_w", right="q_t", reason="mono"))
    assert gate_gamma(state).passed


def test_max_bound_constraint():
    state = _happy_state()
    # wall thickness must be at least max(2 mm, 0.1 * width): 6 >= max(2, 6) -> holds
    state.specification.constraints.append(
        Constraint(id="k_wall", kind="ge", left="q_t", right="max(2, 0.1 * q_w)",
                   reason="wall >= max(2mm, a tenth of width)")
    )
    result = gate_gamma(state)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]


def test_gate_never_invents_a_plausibility_rule():
    # THE anti-hallucination guarantee for plausibility: with NO declared
    # constraint, the gate must NOT silently impose "thickness > 0" or any other
    # domain rule. GENESIS does not invent facts — only checks what was declared.
    state = _happy_state()
    spec = state.specification
    spec.constraints = []                                   # remove all constraints
    # a free (non-geometry) decision quantity with an implausible value
    spec.quantities.append(_decision_q("q_free", "unconstrained margin", -5.0, "mm"))
    result = gate_gamma(state)
    # the gate passes: it invented no positivity rule for q_free
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]


# --- β-Kette (C-14): anchoring ----------------------------------------------------

def test_content_without_anchor_fails():
    state = _happy_state()
    state.specification.approach_id = None
    assert "SPEC_NOT_ANCHORED" in _codes(state)


def test_unknown_anchor_fails():
    state = _happy_state()
    state.specification.approach_id = "ap_ghost"
    assert "SPEC_NOT_ANCHORED" in _codes(state)


def test_anchor_grounded_in_refuted_claim_fails():
    state = _happy_state()
    state.claims[2].status = ClaimStatus.REFUTED  # c_anchor
    codes = _codes(state)
    assert "SPEC_NOT_ANCHORED" in codes and "REFUTED_AS_FACT" in codes


def test_quantities_only_specification_needs_no_anchor():
    state = _happy_state()
    spec = state.specification
    spec.components = []
    spec.steps = []
    spec.constraints = []
    spec.bom = []
    spec.approach_id = None
    spec.gaps = ["only researched quantities; no buildable content asserted"]
    assert gate_gamma(state).passed
