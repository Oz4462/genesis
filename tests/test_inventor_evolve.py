"""Evolve / refine (inventor/archive.py, inventor/refinement.py) — TE1/TE2/TE3, the M3 DoD.

Pins the quality-diversity + self-refine half of the loop:
  * REFINEMENT (M3 DoD): a physics-failing concept is repaired by gate-feedback regeneration until it passes;
    an unrepairable regenerator is honestly reported stuck=True (identical δ-physics failure recurs).
  * ARCHIVE (MAP-Elites): a higher-fitness invention replaces its niche incumbent; different niches coexist.
  * RECOMBINATION: two elite concepts cross into a grounded hybrid whose grounding is the union of the parents.
Offline, deterministic.
"""

import asyncio
from datetime import datetime, timezone

import pytest

from gen.core.state import Possibility
from gen.inventor import Invention, InventionBrief
from gen.inventor.archive import (
    InventionArchive, invention_fitness, invention_niche, recombine_concepts,
)
from gen.inventor.domains import MechatronicsDomain, scripted_mechatronics_architect
from gen.inventor.refinement import refine_invention, strengthening_schedule

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def run(coro):
    return asyncio.run(coro)


def _concept(cid="c", mechanism="flexures store energy"):
    return Possibility(id=cid, statement="mount", mechanism=mechanism, grounding=["x"],
                       produced_by="council", model="m", created_at=_T0)


def _grounded(first_natural_hz=150.0, mechanism="flexures store energy"):
    dom = MechatronicsDomain()
    brief = InventionBrief(field="x", run_id="r")
    return run(dom.ground(_concept(mechanism=mechanism), brief,
                          scripted_mechatronics_architect(first_natural_hz=first_natural_hz)))


# --- refinement (M3 DoD) ----------------------------------------------------

def test_a_failing_concept_is_repaired_by_gate_feedback():
    dom, brief = MechatronicsDomain(), InventionBrief(field="x", run_id="r")
    result = run(refine_invention(_concept(), brief, dom, strengthening_schedule(start_hz=30.0, step_hz=40.0)))
    assert result.converged and not result.stuck       # 30 (fail) -> 70 (fail) -> 110 (pass)
    assert result.invention.physics_verified and result.rounds == 2
    assert result.history[0] == (0, False) and result.history[-1][1] is True


def test_an_unrepairable_concept_is_reported_stuck_not_a_fake_pass():
    dom, brief = MechatronicsDomain(), InventionBrief(field="x", run_id="r")
    result = run(refine_invention(_concept(), brief, dom, strengthening_schedule(start_hz=30.0, step_hz=0.0)))
    assert result.stuck and not result.converged       # the same failing design recurs
    assert not result.invention.physics_verified
    assert result.directives                           # honest gate-feedback for the residual failure


def test_refine_rejects_a_nonpositive_budget():
    dom, brief = MechatronicsDomain(), InventionBrief(field="x", run_id="r")
    with pytest.raises(ValueError):
        run(refine_invention(_concept(), brief, dom, strengthening_schedule(), max_rounds=0))


# --- archive (MAP-Elites) ---------------------------------------------------

def test_archive_keeps_the_higher_fitness_invention_per_niche():
    # fitness = the mount's first natural frequency (quantities[1]); quantities[0] is the shared excitation
    archive = InventionArchive(niche_of=lambda inv: "single-niche",
                               fitness=lambda inv: inv.specification.quantities[1].value)
    low = _grounded(first_natural_hz=100.0)
    high = _grounded(first_natural_hz=150.0)
    assert archive.consider(low) is True               # first into the niche
    assert archive.consider(high) is True              # strictly higher fitness replaces it
    assert archive.consider(low) is False              # lower fitness rejected
    assert len(archive) == 1 and archive.elites()[0] is high


def test_archive_lets_distinct_niches_coexist():
    archive = InventionArchive()
    a = _grounded(mechanism="flexures store energy")    # mechanism family "flexures"
    b = _grounded(mechanism="electrostatic clamping")   # mechanism family "electrostatic"
    archive.extend([a, b])
    assert len(archive) == 2                            # two families -> two cells, both kept


def test_ungrounded_inventions_are_not_elites():
    inv = Invention(concept=_concept())
    assert invention_fitness(inv) == float("-inf")
    assert invention_niche(inv) == ("flexures", -1)


# --- recombination ----------------------------------------------------------

def test_recombination_crosses_two_concepts_into_a_grounded_hybrid():
    a = Possibility(id="a", statement="resonant gripper", mechanism="flexures", grounding=["s1"],
                    produced_by="c", model="m", created_at=_T0)
    b = Possibility(id="b", statement="electroadhesive pad", mechanism="electrostatic", grounding=["s2"],
                    produced_by="c", model="m", created_at=_T0)
    hybrid = recombine_concepts(a, b, now=_T0)
    assert "resonant gripper" in hybrid.statement and "electroadhesive pad" in hybrid.statement
    assert hybrid.grounding == ["s1", "s2"]            # grounding is the union -> hybrid stays anchored


def test_recombining_two_anchorless_concepts_is_impossible():
    # core grounding invariant forbids an anchorless Possibility, so neither parent can be anchorless;
    # recombine_concepts also guards the union explicitly.
    from gen.core.errors import UngroundedPossibilityError
    with pytest.raises(UngroundedPossibilityError):
        Possibility(id="x", statement="s", mechanism="m", grounding=[], produced_by="c", model="m",
                    created_at=_T0)
