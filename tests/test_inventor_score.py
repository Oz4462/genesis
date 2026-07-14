"""5-axis Pareto scoring of inventions (inventor/score.py) over the verified inverse_design seam.

Pins the honest scoring: an invention is scored on cost↓/mass↓/performance↑/complexity↓/novelty↑, computed
deterministically from the grounded spec with NEUTRAL fallbacks (never a fabricated favourable number), and
only the non-dominated grounded inventions survive (via the verified ParetoOptimizer). A dominated invention
is excluded; an ungrounded one is not a competitor at all. Offline, deterministic.
"""

import asyncio
import dataclasses
from datetime import datetime, timezone

import pytest

from gen.core.state import Possibility
from gen.inventor import Invention, InventionBrief
from gen.inventor.domains import MechatronicsDomain, scripted_mechatronics_architect
from gen.inventor.score import (
    INVENTION_GOAL,
    ScoreVector,
    inventions_to_pareto_front,
    pareto_inventions,
    score_invention,
)

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def run(coro):
    return asyncio.run(coro)


def _grounded(statement_id="c", first_natural_hz=150.0):
    dom = MechatronicsDomain()
    brief = InventionBrief(field="gripper", run_id="inv")
    concept = Possibility(id=statement_id, statement="mount", mechanism="flexures",
                          grounding=["https://openalex.org/W-actuator-mount"], produced_by="council",
                          model="m", created_at=_T0)
    return run(dom.ground(concept, brief, scripted_mechatronics_architect(first_natural_hz=first_natural_hz)))


def test_score_is_deterministic_with_honest_neutral_fallbacks():
    sv = score_invention(_grounded())
    assert isinstance(sv, ScoreVector)
    assert sv.performance == 3.0          # modal margin = first_natural 150 / excitation 50
    assert sv.mass == 1.0                 # no .mass measurand -> neutral 1.0, not a fabricated low mass
    assert sv.novelty == 0.5              # Phase N has not run -> neutral, not a claimed high novelty
    assert sv.complexity == 2.0           # two quantities


def test_thermal_invention_scores_conduction_margin_not_neutral_one():
    """Self-improve: cold-plate specs use overtemperature ratio max_service/peak, not fake 1.0."""
    from gen.inventor.domains import ThermalDomain, scripted_thermal_architect

    dom = ThermalDomain()
    brief = InventionBrief(field="cooling", run_id="th")
    concept = Possibility(
        id="t1",
        statement="copper cold plate",
        mechanism="conduction",
        grounding=["https://openalex.org/W-direct-to-chip"],
        produced_by="council",
        model="m",
        created_at=_T0,
    )
    inv = run(dom.ground(concept, brief, scripted_thermal_architect()))
    assert inv.physics_verified
    sv = score_invention(inv)
    # default copper plate: k from registry (~401); ΔT = P·L/(k·A); peak = amb+ΔT
    from gen.materials import get_material
    from gen.thermal import overtemperature_check

    k = float(get_material("COPPER").thermal_conductivity_w_mk or 401.0)
    ot = overtemperature_check(
        1000.0, k, 0.0025, 0.003, ambient=323.15, max_service_temp=373.15
    )
    assert sv.performance > 1.0
    assert abs(sv.performance - 373.15 / ot["peak_temp"]) < 1e-6


def test_novelty_verdict_maps_into_the_score_when_present():
    inv = dataclasses.replace(_grounded(), novelty_verdict="neuer_mechanismus")
    assert score_invention(inv).novelty == 1.0
    assert score_invention(dataclasses.replace(inv, novelty_verdict="nicht_neu")).novelty == 0.0


def test_scoring_an_ungrounded_invention_raises():
    concept = Possibility(id="x", statement="s", mechanism="m", grounding=["a"], produced_by="c",
                          model="m", created_at=_T0)
    with pytest.raises(ValueError):
        score_invention(Invention(concept=concept))      # no specification -> cannot score


def test_pareto_excludes_a_dominated_invention():
    a = dataclasses.replace(_grounded("A"), concept=dataclasses.replace(_grounded("A").concept, id="A"))
    b = dataclasses.replace(_grounded("B"), concept=dataclasses.replace(_grounded("B").concept, id="B"))

    def fake(inv):  # A is better on every axis -> A dominates B
        return ScoreVector(10, 2, 3.0, 5, 0.9) if inv.concept.id == "A" else ScoreVector(20, 4, 1.0, 8, 0.2)

    front = pareto_inventions([a, b], score=fake)
    assert [i.concept.id for i in front] == ["A"]         # the dominated invention is excluded


def test_pareto_keeps_genuine_tradeoffs_and_drops_ungrounded():
    a = dataclasses.replace(_grounded("A"), concept=dataclasses.replace(_grounded("A").concept, id="A"))
    b = dataclasses.replace(_grounded("B"), concept=dataclasses.replace(_grounded("B").concept, id="B"))
    ungrounded = Invention(concept=Possibility(id="U", statement="s", mechanism="m", grounding=["x"],
                                               produced_by="c", model="m", created_at=_T0))

    def fake(inv):  # A cheaper, B lighter -> a genuine trade-off, both non-dominated
        return ScoreVector(10, 5, 2.0, 5, 0.5) if inv.concept.id == "A" else ScoreVector(15, 2, 2.0, 5, 0.5)

    front = pareto_inventions([a, b, ungrounded], score=fake)
    assert sorted(i.concept.id for i in front) == ["A", "B"]   # ungrounded U is not a competitor


def test_inventions_to_pareto_front_bridges_gamma_plus_proxy():
    """γ+ bridge: grounded inventions become a ParetoFront with score_proxy provenance."""
    a = dataclasses.replace(_grounded("A"), concept=dataclasses.replace(_grounded("A").concept, id="A"))
    b = dataclasses.replace(_grounded("B"), concept=dataclasses.replace(_grounded("B").concept, id="B"))
    ungrounded = Invention(concept=Possibility(id="U", statement="s", mechanism="m", grounding=["x"],
                                               produced_by="c", model="m", created_at=_T0))

    def fake(inv):
        return ScoreVector(10, 5, 2.0, 5, 0.5) if inv.concept.id == "A" else ScoreVector(15, 2, 2.0, 5, 0.5)

    front = pareto_inventions([a, b, ungrounded], score=fake)
    pf = inventions_to_pareto_front([a, b, ungrounded], front, score=fake)
    assert pf.produced_by == "inventor.score_proxy"
    assert pf.goal is INVENTION_GOAL or pf.goal.id == "invention"
    assert sorted(c.id for c in pf.candidates) == ["A", "B"]
    assert sorted(c.id for c in pf.evaluated_candidates) == ["A", "B"]
    assert any("score proxies" in g for g in pf.gaps)
    assert any("ungrounded" in g for g in pf.gaps)
    # objective values are the proxies, not empty
    assert pf.candidates[0].objective_values["cost"] in (10.0, 15.0)


def test_inventions_to_pareto_front_empty_is_honest_abstention():
    ungrounded = Invention(concept=Possibility(id="U", statement="s", mechanism="m", grounding=["x"],
                                               produced_by="c", model="m", created_at=_T0))
    pf = inventions_to_pareto_front([ungrounded], [])
    assert pf.candidates == []
    assert pf.evaluated_candidates == []
    assert any("No grounded" in g or "ungrounded" in g for g in pf.gaps)


def test_goal_has_five_axes():
    assert len(INVENTION_GOAL.objectives) == 5
    assert {o.id for o in INVENTION_GOAL.objectives} == {"cost", "mass", "performance", "complexity", "novelty"}
