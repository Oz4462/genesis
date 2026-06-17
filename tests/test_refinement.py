"""Verify -> refine loop — convergence on a fixable defect, honesty on an unfixable one.

The loop must CONVERGE when a (scripted, deterministic) regenerator can address the gate's
directives, and must be HONEST when it cannot: a regeneration round that changes nothing
stops the loop with stuck=True (no fake success), and an exhausted budget returns
converged=False with the residual failures. The actual LLM regenerator is deferred; this
proves the deterministic loop around any gate. Offline, no LLM.

Run:  pytest tests/test_refinement.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.interfaces import GateFailure, GateResult  # noqa: E402
from gen.demo import drive_shaft_state  # noqa: E402
from gen.physics_selection import evaluate_spec_physics  # noqa: E402
from gen.refinement import (  # noqa: E402
    DIRECTIVE_TEMPLATES,
    directives_from_gate,
    refine_until_pass,
)


def _physics_gate(state) -> GateResult:
    return evaluate_spec_physics(state.specification)["gate"]


def _set_diameter(state, value: float) -> None:
    next(q for q in state.specification.quantities if q.id == "q_shaft_d").value = value


def _over_stressed_shaft():
    st = drive_shaft_state()
    _set_diameter(st, 5.0)                       # tau ~6112 MPa >> 260 -> torsion fails
    return st


def _strengthen_by(step: float):
    """A scripted regenerator: when told the margin is not cleared, grow the shaft."""
    def regen(state, directives):
        if any(d.code == "PHYSICS_CHECK_FAILED" for d in directives):
            q = next(x for x in state.specification.quantities if x.id == "q_shaft_d")
            _set_diameter(state, q.value + step)
        return state
    return regen


# --- convergence ---------------------------------------------------------------

def test_loop_converges_on_a_fixable_defect():
    result = refine_until_pass(_over_stressed_shaft(), _strengthen_by(5.0), _physics_gate,
                               max_rounds=5)
    assert result.converged and result.residual_failures == [] and not result.stuck
    assert result.rounds == 2                     # d 5 -> 10 -> 15 (passes)


def test_already_sound_converges_immediately():
    result = refine_until_pass(drive_shaft_state(), _strengthen_by(5.0), _physics_gate)
    assert result.converged and result.rounds == 0


# --- honesty: never a fake success --------------------------------------------

def test_no_progress_regenerator_is_reported_stuck():
    def noop(state, directives):
        return state                              # changes nothing
    result = refine_until_pass(_over_stressed_shaft(), noop, _physics_gate, max_rounds=5)
    assert not result.converged and result.stuck
    assert result.residual_failures and result.residual_failures[0].code == "PHYSICS_CHECK_FAILED"
    assert result.rounds < 5                       # stopped early, didn't waste the budget


def test_too_slow_regenerator_exhausts_the_budget_honestly():
    # +0.5/round never reaches the ~14.3 mm needed within 5 rounds -> not converged, not stuck
    result = refine_until_pass(_over_stressed_shaft(), _strengthen_by(0.5), _physics_gate,
                               max_rounds=5)
    assert not result.converged and not result.stuck
    assert result.rounds == 5 and result.residual_failures


def test_rejects_nonpositive_budget():
    with pytest.raises(ValueError):
        refine_until_pass(drive_shaft_state(), _strengthen_by(1.0), _physics_gate, max_rounds=0)


# --- directives ----------------------------------------------------------------

def test_directives_map_failures_to_instructions():
    gate = _physics_gate(_over_stressed_shaft())
    directives = directives_from_gate(gate)
    assert len(directives) == 1
    assert directives[0].code == "PHYSICS_CHECK_FAILED"
    assert directives[0].instruction == DIRECTIVE_TEMPLATES["PHYSICS_CHECK_FAILED"]


def test_unknown_code_gets_a_generic_directive_not_a_fabricated_fix():
    result = GateResult(gate="x", passed=False,
                        failures=[GateFailure(code="MYSTERY_CODE", detail="something odd")])
    directives = directives_from_gate(result)
    assert directives[0].code == "MYSTERY_CODE"
    assert "something odd" in directives[0].instruction      # carries the detail, no invention


def test_is_deterministic():
    a = refine_until_pass(_over_stressed_shaft(), _strengthen_by(5.0), _physics_gate)
    b = refine_until_pass(_over_stressed_shaft(), _strengthen_by(5.0), _physics_gate)
    assert (a.converged, a.rounds, a.stuck) == (b.converged, b.rounds, b.stuck)


def _oscillate(a: float, b: float):
    """A scripted regenerator that CYCLES the diameter between two distinct FAILING values: it
    never repeats the LAST signature, but it makes no real progress — a cycle the set-based
    detector must catch (a consecutive-only check would burn the whole budget instead)."""
    def regen(state, directives):
        q = next(x for x in state.specification.quantities if x.id == "q_shaft_d")
        _set_diameter(state, b if q.value == a else a)
        return state
    return regen


def test_oscillating_regenerator_is_caught_as_stuck_not_run_to_budget():
    # d 5 <-> 6 both fail torsion; consecutive signatures always differ, so the old last-only
    # check ran to the full budget as 'exhausted'. The cycle (set) detector catches the repeat.
    result = refine_until_pass(_over_stressed_shaft(), _oscillate(5.0, 6.0), _physics_gate,
                               max_rounds=8)
    assert result.stuck and not result.converged
    assert result.rounds < 8                      # caught at the cycle, not at the budget
