"""Novelty as measured prior-art distance, not an LLM opinion (inventor/novelty.py).

Pins the second axis of honesty: a near-verbatim duplicate of retrieved prior art is nicht_neu (with the
nearest-prior-art id as evidence); the same goal with a DIFFERENT mechanism is neuer_mechanismus (the owner
bar — a new mechanism counts as novel); something far from all prior art is neu. No prior art retrieved ->
an honest evidenced "neu", never a hidden assumption. Cross-model obviousness flags only on unanimous judges.
Offline, deterministic (char-n-gram embedder; dense Ollama is the opt-in upgrade).
"""

import asyncio
from datetime import datetime, timezone

from gen.core.state import Possibility, SourceCandidate
from gen.inventor.domains import MechatronicsDomain
from gen.inventor.novelty import (
    NEU, NEUER_MECHANISMUS, NICHT_NEU, assess_novelty, obviousness_flag,
)
from gen.llm.base import ScriptedLLM

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def run(coro):
    return asyncio.run(coro)


def _concept(statement, mechanism):
    return Possibility(id="c", statement=statement, mechanism=mechanism, grounding=["x"],
                       produced_by="council", model="m", created_at=_T0)


class _Fake:
    name = "fake"

    def __init__(self, candidates):
        self._candidates = candidates

    async def search(self, query, limit):
        return self._candidates[:limit]


class _Boom:
    name = "boom"

    async def search(self, query, limit):
        raise RuntimeError("backend down")


def test_a_near_verbatim_duplicate_is_nicht_neu_with_evidence():
    concept = _concept("resonant tendon gripper mount", "printed flexures store elastic energy")
    backend = _Fake([SourceCandidate(url_or_id="openalex:W9", title="resonant tendon gripper mount",
                                     backend="fake", relevance_note="printed flexures store elastic energy")])
    v = run(assess_novelty(concept, [backend]))
    assert v.verdict == NICHT_NEU and not v.is_novel
    assert v.nearest_prior_art == "openalex:W9"          # the verdict cites its evidence
    assert v.distance < 0.05


def test_same_goal_new_mechanism_is_neuer_mechanismus():
    concept = _concept("gripper that holds delicate objects", "magnetohydrodynamic levitation field, no contact")
    backend = _Fake([SourceCandidate(url_or_id="openalex:W8", title="gripper that holds delicate objects",
                                     backend="fake", relevance_note="vacuum suction cup pneumatic rubber seal")])
    v = run(assess_novelty(concept, [backend]))
    assert v.verdict == NEUER_MECHANISMUS and v.is_novel   # owner bar: a new mechanism counts as novel


def test_far_from_all_prior_art_is_neu():
    concept = _concept("Magnetohydrodynamic seawater thruster", "Lorentz force on ionized brine")
    v = run(assess_novelty(concept, MechatronicsDomain().prior_art_sources()))
    assert v.verdict == NEU and v.is_novel


def test_no_prior_art_retrieved_is_an_honest_evidenced_neu():
    v = run(assess_novelty(_concept("anything", "anyhow"), []))
    assert v.verdict == NEU and v.distance == 1.0 and v.nearest_prior_art is None


def test_a_failing_backend_does_not_fabricate_novelty():
    # the boom backend errors; with no other source there is no prior art -> honest neu, not a crash
    v = run(assess_novelty(_concept("x", "y"), [_Boom()]))
    assert v.verdict == NEU and v.nearest_prior_art is None


def test_obviousness_flags_only_on_unanimous_judges():
    concept = _concept("a concept", "a mechanism")
    yes = ScriptedLLM("j1", '{"obvious": true, "reason": "trivial"}')
    no = ScriptedLLM("j2", '{"obvious": false, "reason": "novel"}')
    assert run(obviousness_flag(concept, [yes, yes])) is True       # all say obvious -> flagged
    assert run(obviousness_flag(concept, [yes, no])) is False       # one dissent clears it
    assert run(obviousness_flag(concept, [])) is False              # no judges -> not flagged


def test_an_unparseable_judge_does_not_flag():
    concept = _concept("a concept", "a mechanism")
    bad = ScriptedLLM("j", "not json")
    assert run(obviousness_flag(concept, [bad])) is False
