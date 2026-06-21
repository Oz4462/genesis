"""Optimization + evolution seams (inventor/optimize.py, inventor/evolve_engine.py).

Pins the offline-first / external-opt-in discipline for the inventor's search layer: the offline ParetoOptimizer
keeps exactly the non-dominated inventions (via the verified inverse_design.dominates), and the offline
MapElitesEngine is a deterministic quality-diversity search that fills every reachable niche with its best
genome. Both external adapters (pymoo, openevolve) skip cleanly when absent — never a silently-wrong result.
Offline, deterministic.
"""

import pytest

from gen.inventor.evolve_engine import (
    EvolveEngine, EvolveEngineUnavailable, MapElitesEngine, OpenEvolveEngine, default_engine,
)
from gen.inventor.optimize import (
    Optimizer, OptimizerUnavailable, ParetoOptimizer, PymooOptimizer, default_optimizer,
)
from gen.inverse_design import DesignObjective, InverseDesignGoal, ObjectiveDirection

_GOAL = InverseDesignGoal(id="g", description="cheap+light", objectives=[
    DesignObjective(id="cost", quantity_id="cost", direction=ObjectiveDirection.MINIMIZE, unit="EUR", target=None),
    DesignObjective(id="mass", quantity_id="mass", direction=ObjectiveDirection.MINIMIZE, unit="kg", target=None),
])
# NOTE: inventor optimize uses this style _GOAL; real bridge/derive used in loop for inventor specs → ParetoFront/RunState (γ+ full)
_CANDS = [
    {"name": "A", "cost": 10.0, "mass": 2.0},
    {"name": "B", "cost": 5.0, "mass": 5.0},
    {"name": "C", "cost": 12.0, "mass": 3.0},   # dominated by A (dearer AND heavier)
    {"name": "D", "cost": 6.0, "mass": 4.0},
]
def _VOF(c):
    return {"cost": c["cost"], "mass": c["mass"]}


# --- optimize ---------------------------------------------------------------

def test_pareto_optimizer_keeps_only_non_dominated():
    opt = ParetoOptimizer()
    assert isinstance(opt, Optimizer)
    front = opt.select(_CANDS, _VOF, _GOAL)
    assert sorted(c["name"] for c in front) == ["A", "B", "D"]    # C is dominated, excluded
    assert default_optimizer().name == "pareto"


def test_pareto_optimizer_is_order_stable_and_handles_empty():
    assert ParetoOptimizer().select([], _VOF, _GOAL) == []
    twice = [ParetoOptimizer().select(_CANDS, _VOF, _GOAL) for _ in range(2)]
    assert twice[0] == twice[1]


def test_pymoo_optimizer_skips_cleanly_without_the_tool():
    opt = PymooOptimizer()
    assert isinstance(opt, Optimizer)
    if opt.available():
        assert sorted(c["name"] for c in opt.select(_CANDS, _VOF, _GOAL)) == ["A", "B", "D"]
    else:
        with pytest.raises(OptimizerUnavailable):
            opt.select(_CANDS, _VOF, _GOAL)


# --- evolve_engine ----------------------------------------------------------

def _evaluate(g):
    return -float((g - 7) ** 2)          # quality peaks at genome 7


def _mutate(g, rng):
    return max(0, min(9, g + rng.choice([-1, 1])))


def _niche(g):
    return g % 3                         # three behavioral niches


def test_map_elites_fills_every_niche_with_its_best_genome():
    eng = MapElitesEngine()
    assert isinstance(eng, EvolveEngine)
    elites = eng.evolve([0], evaluate=_evaluate, mutate=_mutate, niche_of=_niche, generations=200, seed=0)
    assert sorted(e.niche for e in elites) == [0, 1, 2]
    best = {e.niche: e for e in elites}
    assert best[1].genome == 7 and best[1].score == 0.0          # the optimum lands in niche 7%3==1
    assert default_engine().name == "map-elites"


def test_map_elites_is_deterministic():
    eng = MapElitesEngine()
    a = eng.evolve([0], evaluate=_evaluate, mutate=_mutate, niche_of=_niche, generations=150, seed=0)
    b = eng.evolve([0], evaluate=_evaluate, mutate=_mutate, niche_of=_niche, generations=150, seed=0)
    assert [(e.niche, e.genome, e.score) for e in a] == [(e.niche, e.genome, e.score) for e in b]


def test_islands_cover_the_niches_and_require_a_seed():
    isl = MapElitesEngine(islands=4)
    elites = isl.evolve([0], evaluate=_evaluate, mutate=_mutate, niche_of=_niche, generations=80, seed=0)
    assert sorted(e.niche for e in elites) == [0, 1, 2]
    with pytest.raises(ValueError):
        MapElitesEngine().evolve([], evaluate=_evaluate, mutate=_mutate, niche_of=_niche, generations=10)
    with pytest.raises(ValueError):
        MapElitesEngine(islands=0)


def test_openevolve_engine_skips_cleanly_without_the_tool():
    eng = OpenEvolveEngine()
    assert isinstance(eng, EvolveEngine)
    if not eng.available():
        with pytest.raises(EvolveEngineUnavailable):
            eng.evolve([0], evaluate=_evaluate, mutate=_mutate, niche_of=_niche, generations=1)
