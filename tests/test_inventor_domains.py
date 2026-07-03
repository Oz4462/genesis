"""Domain plugin + grounding flow (inventor/domains/{base,mechatronics}.py).

Pins the heart of the loop: a domain grounds a concept through an injectable architect into a δ-physics-VERIFIED
Specification + a buildable bundle — and an OVER-BOLD concept (resonance at/below the operating speed) is
honestly REJECTED by the deterministic gate (physics_verified=False, an explicit gap), never a fabricated pass.
A vacuous spec (no recognized measurand) is also NOT verified — "nothing to prove" != "proven". Offline,
deterministic; prior art comes from an offline RagBackend (live runs inject OpenAlex + PatentsView).
"""

import asyncio
from datetime import datetime, timezone

from gen.core.state import Possibility
from gen.inventor import InventionBrief
from gen.inventor.domains import MechatronicsDomain, scripted_mechatronics_architect
from gen.inventor.domains.base import (
    InventionDomain, ground_with_architect, parse_quantities, scripted_architect,
)
from gen.core.state import ValueOrigin

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def run(coro):
    return asyncio.run(coro)


def _concept():
    return Possibility(id="c1", statement="Resonant tendon gripper mount", mechanism="printed flexures",
                       grounding=["https://openalex.org/W-actuator-mount"], produced_by="council",
                       model="m", created_at=_T0)


def _brief():
    return InventionBrief(field="compliant gripper", run_id="inv1")


def test_domain_satisfies_the_protocol_and_exposes_prior_art():
    dom = MechatronicsDomain()
    assert isinstance(dom, InventionDomain)
    assert [b.name for b in dom.prior_art_sources()] == ["rag"]
    hits = run(dom.prior_art_sources()[0].search("resonant gripper mount", 3))
    assert any("actuator-mount" in c.url_or_id for c in hits)        # offline prior art is searchable
    assert dom.external_oracle() is None                              # no oracle wired offline


def test_a_sound_concept_grounds_to_a_physics_verified_spec_and_artifact(tmp_path):
    dom = MechatronicsDomain()
    inv = run(dom.ground(_concept(), _brief(), scripted_mechatronics_architect(first_natural_hz=150.0)))
    assert inv.physics_verified and inv.grounded
    assert inv.specification is not None and not inv.gaps
    manifest = dom.emit_artifact(inv.specification, str(tmp_path))
    assert manifest.physics_ok and len(manifest.written) > 0          # a real bundle was emitted


def test_an_over_bold_concept_is_rejected_by_the_gate_as_an_honest_gap():
    dom = MechatronicsDomain()
    inv = run(dom.ground(_concept(), _brief(), scripted_mechatronics_architect(first_natural_hz=30.0)))
    assert not inv.physics_verified and not inv.grounded             # resonance at 30 Hz < 50 Hz excitation
    assert inv.specification is not None                              # the spec was built...
    assert any("NICHT bestanden" in g for g in inv.gaps)             # ...but the gate honestly failed it


def test_a_vacuous_spec_is_not_verified():
    # quantities with no recognized measurand fire no check -> "nothing to prove" is NOT "proven"
    architect = scripted_architect([{"id": "q1", "name": "blob", "value": 1.0, "unit": "kg",
                                     "measurand": "unknown.thing"}])
    inv = run(ground_with_architect(_concept(), _brief(), architect))
    assert not inv.physics_verified
    assert any("vacuous" in g for g in inv.gaps)


def test_an_unparseable_architect_reply_is_an_honest_gap():
    from gen.llm.base import ScriptedLLM
    inv = run(ground_with_architect(_concept(), _brief(), ScriptedLLM("m", "not json")))
    assert inv.specification is None and not inv.physics_verified
    assert any("unparsebar" in g for g in inv.gaps)


def test_parse_quantities_honors_the_grounded_vs_decision_invariant():
    qs = parse_quantities([
        {"id": "g", "name": "grounded", "value": 1.0, "unit": "Hz", "measurand": "m",
         "grounding": ["src"], "rationale": "should be dropped"},
        {"id": "d", "name": "decision", "value": 2.0, "unit": "Hz", "measurand": "m", "rationale": "a choice"},
        {"id": "bad", "name": "no value", "unit": "Hz"},                # skipped: non-numeric value
    ])
    assert [q.id for q in qs] == ["g", "d"]
    grounded = next(q for q in qs if q.id == "g")
    decision = next(q for q in qs if q.id == "d")
    assert grounded.origin is ValueOrigin.GROUNDED and grounded.grounding == ["src"] and grounded.rationale == ""
    assert decision.origin is ValueOrigin.DECISION and decision.rationale == "a choice" and not decision.grounding


def test_grounding_is_deterministic():
    dom = MechatronicsDomain()
    a = run(dom.ground(_concept(), _brief(), scripted_mechatronics_architect()))
    b = run(dom.ground(_concept(), _brief(), scripted_mechatronics_architect()))
    assert a.physics_verified == b.physics_verified
    assert [q.value for q in a.specification.quantities] == [q.value for q in b.specification.quantities]
