"""Compute + Checkpoint Controller — budget, depth tiers, and resume == uninterrupted (DoD)."""

import math

import numpy as np

from gen.discovery import Variable, Constant, DiscoveryProblem
from gen.discovery import ExplorationController, ExplorationState

MU_SUN = 1.32712440018e20


def _kepler(run_id):
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11])
    T = 2.0 * math.pi * a ** 1.5 / math.sqrt(MU_SUN)
    return DiscoveryProblem(idea="Kepler", target=Variable("T", "s", tuple(T)),
                            inputs=(Variable("a", "m", tuple(a)),),
                            constants=(Constant("mu", MU_SUN, "m^3/s^2"),), run_id=run_id)


def _free_pi(run_id):
    x1 = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    x2 = np.array([1.5, 3.0, 1.0, 4.0, 2.0, 5.0])
    y = 3.0 * x1 ** 2
    return DiscoveryProblem(idea="free pi group", target=Variable("y", "m^2", tuple(y)),
                            inputs=(Variable("x1", "m", tuple(x1)), Variable("x2", "m", tuple(x2))),
                            run_id=run_id)


def _campaign():
    return [_kepler("c-kepler"), _free_pi("c-free-1"), _kepler("c-kepler-2"), _free_pi("c-free-2")]


def _records(result):
    return sorted(result.graph.to_ledger_records(), key=lambda r: r["id"])


def test_resume_equals_uninterrupted_run():
    """The DoD: a campaign checkpointed mid-way and resumed produces the IDENTICAL graph,
    budget and completion as an uninterrupted run (pausier-/fortsetz-/reproduzierbar)."""
    full = ExplorationController("medium", base_seed=3).run(_campaign())

    ctrl = ExplorationController("medium", base_seed=3)
    partial = ctrl.run(_campaign(), checkpoint_after=2)          # stop after 2 problems
    assert len(partial.completed) == 2 and partial.deferred_to_resume
    resumed = ctrl.run(_campaign(), resume_from=partial.state)   # finish the rest

    assert _records(resumed) == _records(full)                  # identical discoveries
    assert resumed.budget_spent == full.budget_spent
    assert set(resumed.completed) == set(full.completed)


def test_budget_skips_the_expensive_tournament_but_still_completes():
    """A tiny budget forbids the expensive tournament; the campaign still finishes on the cheap
    single-shot solve, and the spend never exceeds the budget."""
    res = ExplorationController("max", budget=10, base_seed=1).run(_campaign())
    assert res.budget_spent <= 10
    assert len(res.completed) == len(_campaign())               # all done, single-shot only
    assert not any("tournament" in n.provenance for n in res.graph.nodes())  # no tournament ran


def test_fast_tier_runs_no_tournament():
    res = ExplorationController("fast", base_seed=1).run(_campaign())
    assert not any("tournament" in n.provenance for n in res.graph.nodes())
    # fast spends only single-shot evals (a few per problem), far below a tournament's cost
    assert res.budget_spent < 8 * len(_campaign())


def test_max_tier_spends_tournament_budget_where_it_helps():
    """On the free-π problems the tournament should run (and improve), so a 'tournament' node
    appears — budget flows to the promising candidates, not the already-solved Kepler ones."""
    res = ExplorationController("max", base_seed=2).run(_campaign())
    assert any("tournament" in n.provenance for n in res.graph.nodes())


def test_state_json_round_trips():
    res = ExplorationController("medium", base_seed=0).run(_campaign(), checkpoint_after=1)
    again = ExplorationState.from_json(res.state.to_json())
    assert again.problems_done == res.state.problems_done
    assert again.budget_spent == res.state.budget_spent
    assert again.graph_records == res.state.graph_records
