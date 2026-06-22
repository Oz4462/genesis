"""Characterization test for the γ+ bridge inside ``inventor/loop.run_invention``.

A *facade-detector*, not a smoke test. The headline claim of T03 is that ``run_invention`` genuinely
runs the γ+ inverse-design bridge in-loop on the δ-grounded specification — it does NOT merely staple a
hardcoded proxy onto the result. These tests fail loudly if the bridge ever regresses into a facade:

  * the derived :class:`InverseDesignGoal` carries a goal id tied to the brief's ``run_id`` AND objectives
    whose ``quantity_id`` are the REAL mechatronics spec quantities (``q_fn``/``q_excite`` …), never the
    legacy proxy ``"performance"`` axis;
  * INPUT-SENSITIVITY — when the run_id changes the goal id changes, and when the architect emits different
    quantity ids the derived objectives track them (proving ``derive_goal_from_spec`` reads the spec rather
    than returning a constant);
  * ``build_pareto_front`` + ``gate_gamma_plus`` are exercised without crashing and the resulting real
    ``ParetoFront`` is set on the result AND attached to a passed ``RunState`` (the same object);
  * the M1 proxy 5-axis ``front`` keeps working (back-compat);
  * the γ+ machinery's FAIL-LOUD guard actually raises (``ObjectiveEvaluationError`` when an objective
    references a quantity the spec does not carry) — proving the gate validates rather than rubber-stamps.

All offline + deterministic (ScriptedLLM council + architect + a RagBackend prior-art corpus).
"""

import asyncio

from hypothesis import given, settings
from hypothesis import strategies as st

from gen.core.state import Question, RunState
from gen.inventor import InventionBrief
from gen.inventor.domains import (
    MechatronicsDomain,
    scripted_architect,
    scripted_mechatronics_architect,
)
from gen.inventor.generate import scripted_council
from gen.inventor.loop import run_invention
from gen.inverse_design import (
    ObjectiveEvaluationError,
    derive_goal_from_spec,
    objective_value,
)
from gen.core.state import DesignObjective, ObjectiveDirection

_COUNCIL = [
    {"statement": "Resonant tendon gripper", "mechanism": "printed flexures",
     "grounding": ["https://openalex.org/W1"]},
    {"statement": "Electroadhesive pad", "mechanism": "electrostatic clamping",
     "grounding": ["patentsview:US123"]},
]

_REAL_QID_HINTS = ("q_fn", "first_natural", "excit", "q_excite")


def _run(coro):
    return asyncio.run(coro)


def _brief(run_id: str = "M1") -> InventionBrief:
    return InventionBrief(field="compliant gripper", run_id=run_id, max_concepts=3)


def _run_grounded(run_id: str = "M1", *, state: RunState | None = None, first_natural_hz: float = 150.0):
    """Drive the full loop with the real council + δ-passing mechatronics architect."""
    return _run(run_invention(
        _brief(run_id), domain=MechatronicsDomain(), council=scripted_council(_COUNCIL),
        architect=scripted_mechatronics_architect(first_natural_hz=first_natural_hz), state=state))


# --- the bridge derives a REAL goal (not the proxy) --------------------------------------------------


def test_bridge_derives_real_goal_id_and_real_quantity_ids_not_proxy():
    """The headline: pf goal id contains 'inv-gp-<run_id>' and >=1 objective carries a REAL spec qid,
    never the legacy proxy 'performance'. A hollow facade would expose no pf or a constant proxy axis."""
    result = _run_grounded("M1")

    assert result.pareto_front is not None, "γ+ bridge produced no ParetoFront"
    pf = result.pareto_front
    assert "inv-gp-M1" in pf.goal.id

    qids = {o.quantity_id for o in pf.goal.objectives}
    assert qids, "derived goal carries no objectives"
    # at least one objective is a genuine mechatronics quantity, none is the legacy proxy axis.
    assert any(any(h in q for h in _REAL_QID_HINTS) for q in qids), f"expected real qids, got {qids}"
    assert "performance" not in qids, "γ+ goal regressed to the proxy 'performance' axis"


def test_goal_id_tracks_run_id_input_sensitivity():
    """INPUT-SENSITIVITY on run_id: change the brief's run_id and the derived goal id changes with it.
    If the bridge returned a constant goal id, this would fail."""
    a = _run_grounded("M1").pareto_front
    b = _run_grounded("ZZ9").pareto_front
    assert "inv-gp-M1" in a.goal.id
    assert "inv-gp-ZZ9" in b.goal.id
    assert a.goal.id != b.goal.id


def test_objectives_track_spec_quantities_input_sensitivity():
    """INPUT-SENSITIVITY on the spec: a custom architect that renames its quantity ids must make the
    derived objectives track those ids — proving derive_goal_from_spec reads the live spec, not a
    hardcoded objective list. Measurands are kept so the δ-physics resonance gate still fires + passes."""
    council = scripted_council([
        {"statement": "Resonant tendon gripper", "mechanism": "printed flexures",
         "grounding": ["https://openalex.org/W1"]},
    ])
    renamed_architect = scripted_architect([
        {"id": "q_eigen", "name": "first natural frequency", "value": 200.0, "unit": "Hz",
         "measurand": "vibration.first_natural_frequency", "grounding": ["https://openalex.org/W1"],
         "rationale": "fe estimate"},
        {"id": "q_drive", "name": "excitation", "value": 40.0, "unit": "Hz",
         "measurand": "vibration.excitation_frequency", "rationale": "operating rpm"},
    ])
    result = _run(run_invention(
        _brief("M1"), domain=MechatronicsDomain(), council=council, architect=renamed_architect))

    assert result.grounded_count >= 1
    qids = {o.quantity_id for o in result.pareto_front.goal.objectives}
    assert qids == {"q_eigen", "q_drive"}, f"objectives did not track the renamed spec qids: {qids}"


# --- the front is attached to the RunState (the T03 fix) ---------------------------------------------


def test_pareto_front_is_attached_to_passed_runstate():
    """When a RunState is passed, the SAME real ParetoFront the bridge computed is attached to it.
    Before the fix the attach was gated on evaluated>0 and silently never fired — a facade."""
    state = RunState(question=Question(raw="compliant gripper", run_id="bridge-attach"))
    result = _run_grounded("M1", state=state)

    assert result.pareto_front is not None
    assert state.pareto_front is result.pareto_front, "γ+ front was not attached to the RunState"
    # the attach is recorded honestly in the run log (with evaluated/front/gaps counts).
    assert any("γ+ pareto_front attached" in entry for entry in state.log)


def test_attached_front_is_an_honest_object_with_gaps_when_it_abstains():
    """The attached front is a genuine, honest ParetoFront: the inventor's δ-grounded spec is not
    γ-complete (its prior-art claims were never skeptic-verified into the ledger), so build_pareto_front
    legitimately evaluates zero candidates and records WHY in gaps — abstention, not a fabricated front."""
    state = RunState(question=Question(raw="compliant gripper", run_id="bridge-honest"))
    pf = _run_grounded("M1", state=state).pareto_front
    # honest abstention: no fabricated candidates, and every rejection carries a stated reason.
    assert list(pf.candidates) == []
    assert pf.gaps, "an empty front must explain itself"


def test_no_runstate_means_no_attach_but_front_still_computed():
    """Back-compat: callers that omit state= still get result.pareto_front; nothing to attach to."""
    result = _run_grounded("M1", state=None)
    assert result.pareto_front is not None
    assert "inv-gp-M1" in result.pareto_front.goal.id


# --- the proxy 5-axis front still works (back-compat) ------------------------------------------------


def test_proxy_five_axis_front_still_works_backcompat():
    """The γ+ bridge is ADDITIVE: the M1 proxy ``front`` (pareto_inventions, 5-axis) is unchanged and the
    grounded invention still survives, with a physics-verified member."""
    result = _run_grounded("M1")
    assert result.front, "proxy 5-axis front regressed"
    assert any(i.physics_verified for i in result.front)
    assert result.grounded_count >= 1


# --- the γ+ machinery FAILS LOUD (the gate is real, not a rubber stamp) ------------------------------


def test_gamma_plus_objective_evaluation_fails_loud_on_missing_quantity():
    """The bridge exercises real γ+ machinery whose fail-loud guard MUST raise: an objective that
    references a quantity absent from the spec raises ObjectiveEvaluationError rather than inventing a
    value. Uses the same real grounded spec the loop produced."""
    result = _run_grounded("M1")
    grounded = [i for i in result.inventions if i.grounded and i.specification is not None]
    assert grounded, "expected a grounded δ-spec to probe"
    spec = grounded[0].specification

    bogus = DesignObjective(
        id="obj_missing", quantity_id="q_does_not_exist",
        direction=ObjectiveDirection.MINIMIZE, unit="Hz")
    raised = False
    try:
        objective_value(spec, bogus)
    except ObjectiveEvaluationError:
        raised = True
    assert raised, "objective_value must fail loud on an unknown quantity (no silent default)"


# --- property: derive_goal never invents a quantity id ----------------------------------------------


@settings(max_examples=60, deadline=None)
@given(suffix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=0, max_size=24))
def test_property_derive_goal_id_roundtrip_and_qids_subset_of_spec(suffix):
    """INVARIANT (proves the goal is computed, not canned): for ANY goal id the derived goal echoes it
    verbatim, and EVERY objective.quantity_id is one the spec actually carries — derive_goal_from_spec
    never fabricates a quantity id. The real grounded spec is built once outside the property loop."""
    goal_id = f"inv-gp-{suffix}"
    goal = derive_goal_from_spec(_SPEC_FOR_PROPERTY, goal_id, "property probe")
    assert goal.id == goal_id  # round-trip: id echoed verbatim, never rewritten

    spec_qids = {q.id for q in _SPEC_FOR_PROPERTY.quantities}
    for objective in goal.objectives:
        assert objective.quantity_id in spec_qids, (
            f"derive_goal invented quantity id {objective.quantity_id!r} not in {spec_qids}")


# Build the real grounded spec ONCE (outside @given) so the property loop is fast and deterministic.
def _grounded_spec_once():
    result = _run_grounded("PROP")
    grounded = [i for i in result.inventions if i.grounded and i.specification is not None]
    assert grounded, "fixture: expected a grounded δ-spec"
    return grounded[0].specification


_SPEC_FOR_PROPERTY = _grounded_spec_once()
