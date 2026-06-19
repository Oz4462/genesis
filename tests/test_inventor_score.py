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
from gen.inventor.score import INVENTION_GOAL, ScoreVector, pareto_inventions, score_invention

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


def test_goal_has_five_axes():
    assert len(INVENTION_GOAL.objectives) == 5
    assert {o.id for o in INVENTION_GOAL.objectives} == {"cost", "mass", "performance", "complexity", "novelty"}
