"""Inventor request/result types (inventor/brief.py): composing core.state, no new fact types.

Pins that the inventor adds only ORCHESTRATION hulls: InventionBrief (the request — validated, no ledger
entry) and Invention (the per-concept result, where specification=None is an honest first-class gap). A bold
concept is a core.state.Possibility, which ALREADY enforces concept-level grounding (no anchor -> cannot
exist) — the anti-hallucination invariant holds before the inventor even starts. Offline, deterministic.
"""

from datetime import datetime, timezone

import pytest

from gen.core.state import Possibility
from gen.inventor import Invention, InventionBrief

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _concept():
    return Possibility(id="c1", statement="resonant tendon gripper",
                       mechanism="store elastic energy in printed flexures",
                       grounding=["https://openalex.org/W123"], produced_by="council",
                       model="scripted", created_at=_T0)


def test_brief_constructs_and_validates():
    b = InventionBrief(field="compliant robot gripper", run_id="r1", goal="cheap, printable",
                       constraints=("mass<0.5kg",))
    assert b.field == "compliant robot gripper" and b.max_concepts == 8
    assert b.constraints == ("mass<0.5kg",)


@pytest.mark.parametrize("kwargs", [
    {"field": "", "run_id": "r"},
    {"field": "x", "run_id": ""},
    {"field": "x", "run_id": "r", "max_concepts": 0},
])
def test_brief_rejects_invalid_input(kwargs):
    with pytest.raises(ValueError):
        InventionBrief(**kwargs)


def test_ungrounded_invention_reports_an_honest_gap_not_grounded():
    inv = Invention(concept=_concept())
    assert inv.specification is None and not inv.physics_verified
    assert not inv.grounded                       # honest: a concept is not yet a grounded invention
    assert inv.safety_ok and inv.novelty_verdict is None   # later phases fill these


def test_concept_level_grounding_is_already_enforced_by_core():
    from gen.core.errors import UngroundedPossibilityError
    with pytest.raises(UngroundedPossibilityError):
        Possibility(id="c2", statement="too bold", mechanism="magic", grounding=[],
                    produced_by="council", model="scripted", created_at=_T0)
