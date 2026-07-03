"""ExplorationController + active_search: spend the tournament budget by Expected Information Gain.

Pins the opt-in ``prioritize_by_information_gain`` path (InfoBAX uncertainty sampling): under a budget
that cannot afford every tournament, the controller spends the affordable ones on the most-informative
eligible problems instead of input order — while the gate stays the sole authority over every verdict.

The strongest property is EQUIVALENCE: with an UNLIMITED budget the information-gain path discovers the
identical laws as the default path (every eligible problem still gets its tournament, same seeds), so the
prioritization only ever changes the budget ALLOCATION, never the discoveries. The honest limitation —
the greedy selection order is not checkpoint-invariant — is enforced as a refusal, not a silent break.
Offline, deterministic.
"""

import math

import numpy as np

from gen.discovery import Constant, DiscoveryProblem, ExplorationController, Variable

MU_SUN = 1.32712440018e20


def _free_pi(run_id):
    # y = 3·x1² with x2 a dimensionless distractor → a free π-group the single-shot solve cannot pin,
    # so the tournament is ELIGIBLE to refine it (mirrors test_discovery_controller's eligible case).
    x1 = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    x2 = np.array([1.5, 3.0, 1.0, 4.0, 2.0, 5.0])
    y = 3.0 * x1 ** 2
    return DiscoveryProblem(idea="free pi group", target=Variable("y", "m^2", tuple(y)),
                            inputs=(Variable("x1", "m", tuple(x1)), Variable("x2", "m", tuple(x2))),
                            run_id=run_id)


def _kepler(run_id):
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11])
    T = 2.0 * math.pi * a ** 1.5 / math.sqrt(MU_SUN)
    return DiscoveryProblem(idea="Kepler", target=Variable("T", "s", tuple(T)),
                            inputs=(Variable("a", "m", tuple(a)),),
                            constants=(Constant("mu", MU_SUN, "m^3/s^2"),), run_id=run_id)


def _campaign():
    return [_free_pi("a-free-1"), _kepler("a-kepler"), _free_pi("a-free-2")]


def _records(result):
    return sorted(result.graph.to_ledger_records(), key=lambda r: r["id"])


def _tournaments(result):
    return sum("tournament" in n.provenance for n in result.graph.nodes())


def test_unlimited_budget_discovers_the_same_laws_as_the_default_path():
    # EQUIVALENCE: with no budget pressure, prioritization changes nothing about WHAT is found.
    default = ExplorationController("max", base_seed=2).run(_campaign())
    prioritized = ExplorationController(
        "max", base_seed=2, prioritize_by_information_gain=True
    ).run(_campaign())
    assert _records(prioritized) == _records(default)
    assert prioritized.budget_spent == default.budget_spent
    assert _tournaments(prioritized) >= 1                       # the allocation actually spent tournaments


def test_information_gain_path_is_deterministic():
    a = ExplorationController("max", base_seed=2, prioritize_by_information_gain=True).run(_campaign())
    b = ExplorationController("max", base_seed=2, prioritize_by_information_gain=True).run(_campaign())
    assert _records(a) == _records(b)
    assert a.budget_spent == b.budget_spent


def test_tiny_budget_runs_no_tournament_but_still_completes():
    # Budget safety on the EIG path: a budget too small for any tournament spends none, yet every
    # problem still completes on the cheap single-shot solve, and the spend never exceeds the budget.
    res = ExplorationController(
        "max", budget=10, base_seed=1, prioritize_by_information_gain=True
    ).run(_campaign())
    assert res.budget_spent <= 10
    assert _tournaments(res) == 0
    assert len(res.completed) == len(_campaign())


def test_prioritization_is_refused_with_checkpointing():
    # Honest limitation: the greedy selection order is not checkpoint-invariant, so combining it with
    # checkpoint_after is refused rather than silently breaking resume==uninterrupted.
    import pytest

    ctrl = ExplorationController("medium", base_seed=0, prioritize_by_information_gain=True)
    with pytest.raises(ValueError):
        ctrl.run(_campaign(), checkpoint_after=1)


def test_prioritization_refused_with_resume_state():
    # A real resume_from state also triggers the refusal (separate from checkpoint_after).
    import pytest

    base = ExplorationController("medium", base_seed=0).run(_campaign(), checkpoint_after=1)
    ctrl = ExplorationController("medium", base_seed=0, prioritize_by_information_gain=True)
    with pytest.raises(ValueError):
        ctrl.run(_campaign(), resume_from=base.state)
