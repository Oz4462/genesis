"""Depth-audit characterization of `gen.refinement` — is the verify->refine loop a REAL
bounded controller, or a facade that fakes convergence?

This is the authoritative facade-detector for T05. Unlike the legacy `test_refinement.py`
(which drives the real δ-physics gate), this test isolates the controller with a PURE,
deterministic scripted gate + regenerator — no physics, no LLM, no I/O. That isolation
lets it pin the loop's honesty contract exactly:

  • `directives_from_gate` maps EVERY failure to a directive (one per failure), known codes
    to their declared template, unknown codes to a generic directive that CARRIES the gate's
    own detail (never a fabricated specific fix).
  • `refine_until_pass` is honest: converges only on a genuinely fixable defect; reports
    stuck=True the moment a failure SIGNATURE recurs (no-progress, incl. an oscillation that
    never repeats the *last* signature); returns converged=False with the residual failures
    when the budget is exhausted; and raises on a non-positive budget.

The facade-killer pair: (a) the loop OUTCOME changes meaningfully as the scripted
regenerator's strength changes — proving the directives/state are genuinely consumed, not a
canned "converged" — and (b) the documented fail-loud / honest-abstention paths fire exactly.

Run:  pytest tests/test_refinement_characterization.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402
from hypothesis import given, settings, strategies as st  # noqa: E402

from gen.core.interfaces import GateFailure, GateResult  # noqa: E402
from gen.core.state import Question, RunState  # noqa: E402
from gen.refinement import (  # noqa: E402
    DIRECTIVE_TEMPLATES,
    RefinementDirective,
    directives_from_gate,
    refine_until_pass,
)

FIX_CODE = "PHYSICS_CHECK_FAILED"  # a known code present in DIRECTIVE_TEMPLATES


# --- a deterministic scripted world (no physics, no LLM) -----------------------
#
# The "design strength" of a state is encoded in its (real) Question.run_id as an
# integer level. The gate passes once the level clears a threshold. A regenerator
# rebuilds the state at a new level. Threading the level through the REAL RunState/
# Question constructors keeps the harness faithful while staying pure.

def _state(level: int) -> RunState:
    return RunState(question=Question(raw="scripted-defect", run_id=str(level)))


def _level(state: RunState) -> int:
    return int(state.question.run_id)


def _make_gate(threshold: int):
    """A scripted gate: PASS once level >= threshold, else FAIL with a detail that encodes
    the current level — so distinct levels yield distinct failure signatures (real progress
    is visible), while an unchanged level yields the identical signature (no progress)."""
    def gate(state: RunState) -> GateResult:
        lvl = _level(state)
        if lvl >= threshold:
            return GateResult(gate="scripted", passed=True, failures=[])
        return GateResult(
            gate="scripted",
            passed=False,
            failures=[GateFailure(code=FIX_CODE, detail=f"margin short at level {lvl}", claim_id="q1")],
        )
    return gate


def _strengthen_by(step: int):
    """A scripted regenerator that, when handed the fix directive, raises the level by `step`."""
    def regen(state: RunState, directives: list[RefinementDirective]) -> RunState:
        if any(d.code == FIX_CODE for d in directives):
            return _state(_level(state) + step)
        return state
    return regen


def _noop(state: RunState, directives: list[RefinementDirective]) -> RunState:
    return state  # changes nothing -> identical signature recurs


# --- directives: every failure mapped, unknown codes carry their detail --------

def test_directives_one_per_failure_mapping_known_and_unknown():
    result = GateResult(
        gate="g",
        passed=False,
        failures=[
            GateFailure(code=FIX_CODE, detail="torsion margin", claim_id="q_d"),
            GateFailure(code="UNSOURCED_CLAIM", detail="no source", claim_id="c1"),
            GateFailure(code="MYSTERY_CODE", detail="something odd", claim_id=None),
        ],
    )
    directives = directives_from_gate(result)

    assert len(directives) == 3                                  # one per failure, none dropped
    assert [d.code for d in directives] == [FIX_CODE, "UNSOURCED_CLAIM", "MYSTERY_CODE"]
    # known codes -> their declared template (the mapping is a table, not a guess)
    assert directives[0].instruction == DIRECTIVE_TEMPLATES[FIX_CODE]
    assert directives[1].instruction == DIRECTIVE_TEMPLATES["UNSOURCED_CLAIM"]
    # unknown code -> generic directive that CARRIES the detail, never a fabricated fix
    assert "something odd" in directives[2].instruction
    assert directives[2].instruction not in DIRECTIVE_TEMPLATES.values()
    # target tracks claim_id; "" when global
    assert directives[0].target == "q_d"
    assert directives[2].target == ""


def test_passing_gate_yields_no_directives():
    result = GateResult(gate="g", passed=True, failures=[])
    assert directives_from_gate(result) == []


# --- convergence on a fixable defect -------------------------------------------

def test_loop_converges_on_a_fixable_defect():
    # level 0 -> +3 -> +3 ; threshold 5 reached at round 2 (level 0,3,6)
    result = refine_until_pass(_state(0), _strengthen_by(3), _make_gate(5), max_rounds=5)
    assert result.converged
    assert result.residual_failures == []
    assert not result.stuck
    assert result.rounds == 2
    assert result.history[-1][1] is True                        # last recorded round passed


def test_already_sound_converges_immediately():
    result = refine_until_pass(_state(10), _strengthen_by(3), _make_gate(5))
    assert result.converged and result.rounds == 0 and result.history == [(0, True, ())]


# --- honesty: never a fake success ---------------------------------------------

def test_no_progress_regenerator_is_reported_stuck():
    result = refine_until_pass(_state(0), _noop, _make_gate(5), max_rounds=5)
    assert not result.converged and result.stuck
    assert result.residual_failures and result.residual_failures[0].code == FIX_CODE
    assert result.rounds < 5                                     # stopped early, budget not wasted


def test_oscillating_regenerator_is_caught_as_stuck_not_run_to_budget():
    # Bounce between two distinct FAILING levels: the consecutive signature always differs,
    # so a last-only check would burn the whole budget; the set-based detector catches the cycle.
    def oscillate(state: RunState, directives: list[RefinementDirective]) -> RunState:
        return _state(2 if _level(state) == 1 else 1)
    result = refine_until_pass(_state(1), oscillate, _make_gate(5), max_rounds=8)
    assert result.stuck and not result.converged
    assert result.rounds < 8


def test_too_slow_regenerator_exhausts_the_budget_honestly():
    # +1/round from 0 cannot reach threshold 100 within 5 rounds; every level is distinct so
    # it is NOT mistaken for stuck -> honest converged=False with residual failures.
    result = refine_until_pass(_state(0), _strengthen_by(1), _make_gate(100), max_rounds=5)
    assert not result.converged and not result.stuck
    assert result.rounds == 5 and result.residual_failures
    assert len(result.history) == 6                             # rounds 0..5 recorded


def test_rejects_nonpositive_budget():
    with pytest.raises(ValueError):
        refine_until_pass(_state(0), _strengthen_by(1), _make_gate(5), max_rounds=0)


# --- facade-killer: outcome is DRIVEN by the regenerator's strength ------------

def test_outcome_changes_with_regenerator_strength():
    """If the controller fabricated 'converged', a too-weak regenerator would still 'pass'.
    A strong step converges; a too-weak step under the same gate+budget does NOT — proving the
    loop genuinely consumes the regenerated state, not a canned verdict."""
    gate, budget = _make_gate(50), 4
    strong = refine_until_pass(_state(0), _strengthen_by(20), gate, max_rounds=budget)
    weak = refine_until_pass(_state(0), _strengthen_by(1), gate, max_rounds=budget)
    assert strong.converged and not weak.converged
    assert strong.rounds != weak.rounds                         # different work, different outcome


def test_is_deterministic():
    a = refine_until_pass(_state(0), _strengthen_by(3), _make_gate(5))
    b = refine_until_pass(_state(0), _strengthen_by(3), _make_gate(5))
    assert (a.converged, a.rounds, a.stuck) == (b.converged, b.rounds, b.stuck)
    assert a.history == b.history


# --- property-based invariants -------------------------------------------------

@settings(max_examples=200)
@given(
    start=st.integers(min_value=0, max_value=5),
    gap=st.integers(min_value=0, max_value=20),
    step=st.integers(min_value=1, max_value=5),
)
def test_monotone_strengthener_converges_in_exactly_ceil_steps(start, gap, step):
    """For a strictly-increasing regenerator with enough budget, the loop ALWAYS converges,
    and the number of rounds equals exactly the closed-form ceil((threshold-start)/step) — the
    controller does the minimal number of regenerations, no more, no fewer."""
    threshold = start + gap
    needed = 0 if gap == 0 else math.ceil(gap / step)
    budget = needed + 3                                         # ample headroom
    result = refine_until_pass(_state(start), _strengthen_by(step), _make_gate(threshold),
                               max_rounds=budget)
    assert result.converged
    assert result.residual_failures == [] and not result.stuck
    assert result.rounds == needed
    assert len(result.history) == result.rounds + 1            # one gate eval per round + final


@settings(max_examples=200)
@given(
    converging=st.booleans(),
    step=st.integers(min_value=1, max_value=4),
    budget=st.integers(min_value=1, max_value=6),
)
def test_result_is_always_internally_honest(converging, step, budget):
    """Whatever the scripted world, the RefinementResult never contradicts itself:
    converged <=> no residual failures and not stuck; rounds within budget; history matches."""
    regen = _strengthen_by(step)
    # threshold 0 -> immediate pass (converges); huge threshold -> unreachable (fails honestly)
    gate = _make_gate(0) if converging else _make_gate(10**9)

    result = refine_until_pass(_state(0), regen, gate, max_rounds=budget)

    # converged is mutually exclusive with the two honest-failure states.
    assert result.converged == (result.residual_failures == [] and not result.stuck)
    if not result.converged:
        assert result.residual_failures                        # never an empty failure on failure
    assert 0 <= result.rounds <= budget
    assert len(result.history) == result.rounds + 1
    # history is contiguous from round 0.
    assert [h[0] for h in result.history] == list(range(result.rounds + 1))
