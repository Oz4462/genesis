"""Depth-audit characterization tests for the ExplorationController (controller.py).

These tests are facade-detectors: each one fails loudly if the controller were a hollow stub
that ignores its knobs. They prove the THREE headline claims of the module's docstring really
hold against driving inputs, not that the code merely runs:

  * CHECKPOINT / RESUME equivalence (the DoD) — a campaign checkpointed mid-way and resumed
    yields a graph + completed set + budget IDENTICAL to one uninterrupted run. Asserted both
    by example and by a Hypothesis property over many (checkpoint_point, budget) combinations,
    because "resume == uninterrupted" is an invariant that must hold for ALL split points.
  * BUDGET — a tight budget starves the expensive tournament (fewer tournament-provenance
    nodes, lower spend) while every problem still completes on the cheap single-shot; a
    generous budget on the MAX tier spends strictly more. Output MUST change with the knob.
  * FAIL-LOUD guards — an unknown tier name raises ValueError, and
    prioritize_by_information_gain combined with checkpoint_after / resume_from raises
    ValueError (an honest refusal, not a silently-broken resume).

Deterministic problems with explicit run_ids; offline; numpy-only.
"""

import math

import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

from gen.discovery import Constant, DiscoveryProblem, Variable
from gen.discovery import ExplorationController, ExplorationState
from gen.discovery.controller import MAX, MEDIUM

MU_SUN = 1.32712440018e20


def _kepler(run_id: str) -> DiscoveryProblem:
    """A FULLY-DETERMINED problem (Kepler): the dimensional solve forces the exponents, the
    single-shot already nails the fit, so the tournament is honestly skipped (already solved)."""
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11])
    period = 2.0 * math.pi * a ** 1.5 / math.sqrt(MU_SUN)
    return DiscoveryProblem(
        idea="Kepler", target=Variable("T", "s", tuple(period)),
        inputs=(Variable("a", "m", tuple(a)),),
        constants=(Constant("mu", MU_SUN, "m^3/s^2"),), run_id=run_id)


def _free_pi(run_id: str) -> DiscoveryProblem:
    """An UNDER-determined problem (two same-dimension inputs): a free π-group the data must
    choose among, so the tournament can measurably improve on the least-norm single-shot —
    this is where budget actually buys something."""
    x1 = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    x2 = np.array([1.5, 3.0, 1.0, 4.0, 2.0, 5.0])
    y = 3.0 * x1 ** 2
    return DiscoveryProblem(
        idea="free pi group", target=Variable("y", "m^2", tuple(y)),
        inputs=(Variable("x1", "m", tuple(x1)), Variable("x2", "m", tuple(x2))),
        run_id=run_id)


def _campaign() -> list[DiscoveryProblem]:
    """A deterministic mixed campaign: determined + under-determined problems, explicit ids."""
    return [_kepler("c-kepler"), _free_pi("c-free-1"), _kepler("c-kepler-2"), _free_pi("c-free-2")]


def _records(result) -> list[dict]:
    """Graph records in a canonical, position-independent order (sorted by node id)."""
    return sorted(result.graph.to_ledger_records(), key=lambda r: r["id"])


def _has_tournament_node(result) -> bool:
    return any("tournament" in node.provenance for node in result.graph.nodes())


# --------------------------------------------------------------------------- #
# (0) Sanity: the controller actually DISCOVERS (not a stub that returns nothing)
# --------------------------------------------------------------------------- #

def test_controller_really_runs_discovery_and_confirms_a_law():
    """Facade-killer: the populated graph must contain a genuinely confirmed discovery
    (Kepler's bestaetigt power law), proving real engine work happened — not an empty stub."""
    res = ExplorationController("medium", base_seed=0).run(_campaign())
    assert len(res.graph) > 0
    confirmed = res.graph.confirmed()
    assert confirmed, "controller produced no confirmed laws — discovery did not actually run"
    # the confirmed Kepler law really has the dimensionally-forced exponents a^3/2 · mu^-1/2
    kepler_nodes = [n for n in confirmed if n.input_idea == "Kepler"]
    assert kepler_nodes
    exps = kepler_nodes[0].exponent_signature
    assert exps.get("a") == pytest.approx(1.5, abs=1e-3)
    assert exps.get("mu") == pytest.approx(-0.5, abs=1e-3)


# --------------------------------------------------------------------------- #
# (1) CHECKPOINT / RESUME equivalence — the headline DoD
# --------------------------------------------------------------------------- #

def test_resume_equals_uninterrupted_run():
    """Resume == uninterrupted: identical graph, identical budget, identical completion set."""
    full = ExplorationController("medium", base_seed=3).run(_campaign())

    ctrl = ExplorationController("medium", base_seed=3)
    partial = ctrl.run(_campaign(), checkpoint_after=2)
    # the checkpoint really stops mid-campaign and leaves work for the resume
    assert len(partial.completed) == 2
    assert len(partial.deferred_to_resume) == 2
    resumed = ctrl.run(_campaign(), resume_from=partial.state)

    assert _records(resumed) == _records(full)
    assert resumed.budget_spent == full.budget_spent
    assert set(resumed.completed) == set(full.completed)
    # the completed set is the full set of problem ids (nothing dropped on the seam)
    assert set(resumed.completed) == {p.run_id for p in _campaign()}


def test_resume_state_json_round_trips_losslessly():
    """The checkpoint is the whole resume contract: it must survive a JSON round-trip exactly,
    else 'resume from disk' would silently diverge from 'resume in memory'."""
    res = ExplorationController("medium", base_seed=0).run(_campaign(), checkpoint_after=1)
    again = ExplorationState.from_json(res.state.to_json())
    assert again.problems_done == res.state.problems_done
    assert again.budget_spent == res.state.budget_spent
    assert again.graph_records == res.state.graph_records
    assert again.tier == res.state.tier
    assert again.base_seed == res.state.base_seed
    assert again.budget == res.state.budget


# Property: resume == uninterrupted must hold for EVERY split point and budget, not just k=2.
# Medium tier keeps each tournament cheap; small campaign + capped examples keep it fast.
_CAMPAIGN_LEN = len(_campaign())


@settings(max_examples=20, deadline=None)
@given(
    checkpoint_after=st.integers(min_value=1, max_value=_CAMPAIGN_LEN - 1),
    budget=st.sampled_from([None, 5, 60, 5000]),
    tier=st.sampled_from(["fast", "medium", "max"]),
)
def test_resume_equals_uninterrupted_property(checkpoint_after, budget, tier):
    """Invariant: for any checkpoint split point, any budget and any tier, a checkpointed-then-
    resumed campaign is byte-identical (graph + budget + completion) to the uninterrupted one.

    This holds because each problem is solved with its OWN seed (base_seed + index) and the
    budget spend is a pure sequential accumulation restored exactly on resume — so a problem's
    outcome never depends on campaign position or prior RNG state. If that ever breaks, the
    checkpoint/resume claim is a facade and this property fails."""
    full = ExplorationController(tier, budget=budget, base_seed=7).run(_campaign())

    ctrl = ExplorationController(tier, budget=budget, base_seed=7)
    partial = ctrl.run(_campaign(), checkpoint_after=checkpoint_after)
    resumed = ctrl.run(_campaign(), resume_from=partial.state)

    assert _records(resumed) == _records(full)
    assert resumed.budget_spent == full.budget_spent
    assert set(resumed.completed) == set(full.completed)


# --------------------------------------------------------------------------- #
# (2) BUDGET — the knob must visibly redirect / starve the expensive tournament
# --------------------------------------------------------------------------- #

def test_tight_budget_skips_tournament_but_every_problem_completes():
    """A tiny budget forbids the 768-eval MAX tournament; the campaign still finishes on the
    cheap single-shot solve, and the spend never exceeds the cap. No tournament node appears."""
    res = ExplorationController("max", budget=10, base_seed=1).run(_campaign())
    assert res.budget_spent <= 10
    assert len(res.completed) == _CAMPAIGN_LEN          # all problems done, single-shot only
    assert not _has_tournament_node(res)                # the expensive path was starved


def test_generous_budget_on_max_spends_more_and_runs_the_tournament():
    """Driving the budget knob from tight to generous MUST change the output: the MAX tier with
    an unbounded budget runs the tournament where it helps (free-π problems) and so spends
    strictly more than the starved run. A stub that ignored the budget would spend the same."""
    tight = ExplorationController("max", budget=10, base_seed=2).run(_campaign())
    generous = ExplorationController("max", budget=None, base_seed=2).run(_campaign())

    assert _has_tournament_node(generous)               # tournament actually ran
    assert not _has_tournament_node(tight)
    assert generous.budget_spent > tight.budget_spent   # budget genuinely buys compute
    # both still complete every problem (budget only gates the *expensive* refinement)
    assert len(tight.completed) == len(generous.completed) == _CAMPAIGN_LEN


def test_budget_gates_only_the_tournament_not_the_mandatory_single_shot():
    """Pins the controller's DOCUMENTED budget contract precisely (not a looser claim it never
    makes): the cheap single-shot solve runs for EVERY problem unconditionally — that floor is
    always paid even by a cap below it — while the EXPENSIVE tournament is the only thing the
    budget gates. So:

      * spend never drops below the single-shot floor (every problem completes), and
      * the tournament portion (spend above the floor) never pushes spend over the budget.

    A cap below the floor therefore yields spend == floor (> cap is allowed, and documented:
    'a budget exhaustion does NOT defer a problem — it only skips its expensive tournament').
    This catches BOTH facades: a budget that silently gated single-shots (deferring problems)
    AND a budget that let the tournament run away past the cap."""
    # the single-shot floor is the spend of the FAST tier (single-shot only), tier-independent
    floor = ExplorationController("fast", base_seed=4).run(_campaign()).budget_spent
    assert floor > 0

    for cap in (5, 10, 800, 2000):
        res = ExplorationController("max", budget=cap, base_seed=4).run(_campaign())
        assert len(res.completed) == _CAMPAIGN_LEN          # completion never sacrificed to budget
        assert res.budget_spent >= floor                    # mandatory single-shots always paid
        if cap >= floor:
            assert res.budget_spent <= cap                  # the tournament respects the cap
        else:
            assert res.budget_spent == floor                # cap below floor can't gate single-shots


# --------------------------------------------------------------------------- #
# (3) DEPTH TIER — the tier knob must visibly change whether the tournament runs
# --------------------------------------------------------------------------- #

def test_tier_knob_drives_tournament_presence_and_cost():
    """fast (single-shot only) vs max (+ long tournament): the tier MUST change the output.
    fast spends only single-shot evals and never records a tournament node; max does both."""
    fast = ExplorationController("fast", base_seed=5).run(_campaign())
    biggest = ExplorationController("max", base_seed=5).run(_campaign())

    assert not _has_tournament_node(fast)
    assert _has_tournament_node(biggest)
    # fast's spend is only a handful of single-shot evals per problem — far below one tournament
    assert fast.budget_spent < MEDIUM.generations * MEDIUM.population
    # max spends at least one full tournament more than fast (the refinement it actually ran)
    assert biggest.budget_spent >= fast.budget_spent + MAX.generations * MAX.population


# --------------------------------------------------------------------------- #
# (4) FAIL-LOUD guards — documented errors must actually raise
# --------------------------------------------------------------------------- #

def test_unknown_tier_raises_value_error():
    with pytest.raises(ValueError, match="unknown tier"):
        ExplorationController("turbo")


def test_prioritize_with_checkpoint_after_raises_value_error():
    """The InfoBAX path's greedy order is not checkpoint-invariant, so it must REFUSE
    checkpoint_after rather than silently break the resume==uninterrupted guarantee."""
    ctrl = ExplorationController("medium", prioritize_by_information_gain=True)
    with pytest.raises(ValueError, match="not supported with checkpoint/resume"):
        ctrl.run(_campaign(), checkpoint_after=1)


def test_prioritize_with_resume_from_raises_value_error():
    ctrl = ExplorationController("medium", prioritize_by_information_gain=True)
    # build a legitimate state to attempt a resume with the forbidden combination
    seed_state = ExplorationState(tier="medium", base_seed=0, budget=None)
    with pytest.raises(ValueError, match="not supported with checkpoint/resume"):
        ctrl.run(_campaign(), resume_from=seed_state)


def test_prioritize_single_pass_is_a_real_working_path():
    """The guard refuses ONLY the checkpoint combination — the information-gain knob itself is a
    live, single-pass feature that still completes every problem and discovers laws (so the
    ValueError above is an honest limitation, not a dead/broken feature)."""
    res = ExplorationController("max", budget=900, base_seed=1,
                               prioritize_by_information_gain=True).run(_campaign())
    assert len(res.completed) == _CAMPAIGN_LEN
    assert res.graph.confirmed()                        # real discoveries on the prioritized path
    assert res.budget_spent <= 900
