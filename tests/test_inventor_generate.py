"""Concept council (inventor/generate.py): a PROPOSER that widens to bold but GROUNDED concepts.

Pins the proposer half of the loop: the offline ScriptedLLM default yields Possibility concepts; junk is
dropped (no grounding anchor / empty statement / malformed JSON) and duplicates are removed BEFORE any
grounding — concept-level anti-hallucination. A malformed council reply is an honest empty list, never a
crash or a fabricated concept. Deterministic, offline.
"""

import asyncio
from datetime import datetime, timezone

from gen.inventor import InventionBrief
from gen.inventor.generate import generate_concepts, scripted_council
from gen.llm.base import ScriptedLLM

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def run(coro):
    return asyncio.run(coro)


_CONCEPTS = [
    {"statement": "Resonant tendon gripper", "mechanism": "printed flexures store elastic energy",
     "grounding": ["https://openalex.org/W1"]},
    {"statement": "no grounding junk", "mechanism": "magic", "grounding": []},            # dropped: no anchor
    {"statement": "  resonant   TENDON gripper  ", "mechanism": "dup", "grounding": ["x"]},  # dup of #1
    {"statement": "Electroadhesive pad", "mechanism": "electrostatic clamping",
     "grounding": ["patentsview:US123"]},
    {"mechanism": "no statement", "grounding": ["y"]},                                     # dropped: no statement
]


def test_council_yields_grounded_concepts_skipping_junk_and_duplicates():
    brief = InventionBrief(field="compliant gripper", run_id="r1", max_concepts=5)
    out = run(generate_concepts(brief, scripted_council(_CONCEPTS), now=_T0))
    assert [p.statement for p in out] == ["Resonant tendon gripper", "Electroadhesive pad"]
    assert all(p.grounding for p in out)                       # every kept concept carries an anchor
    assert [p.id for p in out] == ["r1-c1", "r1-c2"]
    assert all(p.produced_by == "inventor.council" for p in out)


def test_max_concepts_bounds_the_proposer():
    brief = InventionBrief(field="x", run_id="r2", max_concepts=1)
    out = run(generate_concepts(brief, scripted_council(_CONCEPTS), now=_T0))
    assert len(out) == 1 and out[0].statement == "Resonant tendon gripper"


def test_malformed_reply_is_an_honest_empty_list_not_a_crash():
    brief = InventionBrief(field="x", run_id="r3")
    assert run(generate_concepts(brief, ScriptedLLM("m", "this is not json at all"))) == []


def test_generation_is_deterministic():
    brief = InventionBrief(field="x", run_id="r4", max_concepts=5)
    a = run(generate_concepts(brief, scripted_council(_CONCEPTS), now=_T0))
    b = run(generate_concepts(brief, scripted_council(_CONCEPTS), now=_T0))
    assert [(p.id, p.statement) for p in a] == [(p.id, p.statement) for p in b]


def test_a_bare_json_list_is_also_accepted():
    import json
    brief = InventionBrief(field="x", run_id="r5")
    client = ScriptedLLM("m", json.dumps([_CONCEPTS[0]]))     # bare list, not {"concepts":[...]}
    out = run(generate_concepts(brief, client, now=_T0))
    assert len(out) == 1 and out[0].statement == "Resonant tendon gripper"
