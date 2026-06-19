"""Invention orchestrator (inventor/loop.py) — the M1 Definition of Done.

Pins the end-to-end loop: a full ScriptedLLM run (council + architect, offline) yields >=1 GROUNDED invention
that carries its prior-art SOURCES, passed the deterministic δ-physics GATE, and emitted a buildable ARTIFACT
— and re-running is byte-identical. Safety runs FIRST: a refused brief never reaches the proposer (zero
concepts generated). Offline, deterministic.
"""

import asyncio
import os

from gen.inventor import InventionBrief
from gen.inventor.domains import MechatronicsDomain, scripted_mechatronics_architect
from gen.inventor.generate import scripted_council
from gen.inventor.loop import run_invention

_COUNCIL = [
    {"statement": "Resonant tendon gripper", "mechanism": "printed flexures", "grounding": ["https://openalex.org/W1"]},
    {"statement": "Electroadhesive pad", "mechanism": "electrostatic clamping", "grounding": ["patentsview:US123"]},
]


def run(coro):
    return asyncio.run(coro)


def _brief():
    return InventionBrief(field="compliant gripper", run_id="M1", max_concepts=3)


def test_full_run_yields_a_grounded_invention_with_sources_gate_and_artifact(tmp_path):
    result = run(run_invention(
        _brief(), domain=MechatronicsDomain(), council=scripted_council(_COUNCIL),
        architect=scripted_mechatronics_architect(first_natural_hz=150.0), out_dir=str(tmp_path)))
    assert not result.refused
    assert len(result.concepts) == 2 and result.grounded_count >= 1
    assert result.front                                              # at least one non-dominated invention
    best = result.front[0]
    assert best.physics_verified                                    # passed the δ-physics gate
    assert best.prior_art                                           # carries its sources
    assert result.artifact_dirs and len(os.listdir(result.artifact_dirs[0])) > 0   # a real bundle was emitted


def test_the_run_is_reproducible():
    def once():
        return run(run_invention(_brief(), domain=MechatronicsDomain(),
                                 council=scripted_council(_COUNCIL),
                                 architect=scripted_mechatronics_architect()))
    a, b = once(), once()
    assert [i.concept.statement for i in a.front] == [i.concept.statement for i in b.front]
    assert [i.physics_verified for i in a.inventions] == [i.physics_verified for i in b.inventions]


def test_safety_screen_refuses_before_any_concept_is_generated():
    result = run(run_invention(
        _brief(), domain=MechatronicsDomain(), council=scripted_council(_COUNCIL),
        architect=scripted_mechatronics_architect(), safety_screen=lambda brief: False))
    assert result.refused
    assert result.concepts == () and result.inventions == ()        # proposer never called


def test_an_over_bold_run_grounds_nothing_and_yields_an_empty_front():
    # every concept grounds to a failing resonance check -> no physics-verified invention -> empty front
    result = run(run_invention(
        _brief(), domain=MechatronicsDomain(), council=scripted_council(_COUNCIL),
        architect=scripted_mechatronics_architect(first_natural_hz=30.0)))
    assert result.grounded_count == 0 and result.front == ()        # honest: nothing survived the gate
    assert all(not i.physics_verified for i in result.inventions)


def test_checkpoint_hook_is_called_per_concept():
    seen = []
    run(run_invention(_brief(), domain=MechatronicsDomain(), council=scripted_council(_COUNCIL),
                      architect=scripted_mechatronics_architect(), checkpoint=lambda inv: seen.append(inv.concept.id)))
    assert seen == ["M1-c1", "M1-c2"]
