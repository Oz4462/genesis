"""Proactive clarification — detect underspecification, ask the high-value questions.

An indicated physics missing an input must produce a targeted question; a question that
unblocks several checks must rank first (EVPI proxy) and be asked once; a fully specified or
physics-free spec must ask nothing (no nagging). Offline, no LLM, pure functions.

Run:  pytest tests/test_clarification.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.clarification import clarifying_questions, is_underspecified  # noqa: E402
from gen.core.state import Quantity, Specification, ValueOrigin  # noqa: E402
from gen.demo import drive_shaft_spec  # noqa: E402


def _q(qid: str, unit: str, measurand: str) -> Quantity:
    return Quantity(id=qid, name=qid, value=1.0, unit=unit,
                    origin=ValueOrigin.DECISION, rationale="x", measurand=measurand)


def _spec(quantities) -> Specification:
    return Specification(run_id="r", idea="x", quantities=quantities)


def test_fully_specified_shaft_asks_nothing():
    spec = drive_shaft_spec()                     # all inputs present
    assert clarifying_questions(spec) == []
    assert not is_underspecified(spec)


def test_physics_free_spec_asks_nothing():
    # no trigger measurand at all -> no physics indicated -> do not interrogate the user
    spec = _spec([_q("w", "mm", "geometry.width")])
    assert clarifying_questions(spec) == []
    assert not is_underspecified(spec)


def test_missing_input_yields_one_targeted_question():
    # a shaft with torque/diameter/length/G but no shear strength -> torsion underspecified
    spec = _spec([
        _q("t", "N*m", "shaft.torque"), _q("d", "mm", "shaft.diameter"),
        _q("L", "mm", "shaft.length"), _q("g", "MPa", "material.shear_modulus"),
    ])
    questions = clarifying_questions(spec)
    assert is_underspecified(spec)
    assert len(questions) == 1
    q = questions[0]
    assert q.measurand == "material.shear_strength"
    assert q.unblocks == ("shaft torsion",)
    assert "shear strength" in q.question.lower()


def test_high_value_question_ranks_first_and_is_asked_once():
    # both fatigue and notch fatigue are indicated, both missing material.endurance_limit ->
    # one question that unblocks BOTH, priority 2, ahead of any priority-1 question.
    spec = _spec([
        _q("sa", "MPa", "fatigue.stress_amplitude"), _q("sm", "MPa", "fatigue.mean_stress"),
        _q("uts", "MPa", "material.uts"),
        _q("kt", "1", "notch.kt"), _q("nn", "MPa", "notch.nominal_alternating_stress"),
        _q("nr", "mm", "notch.radius"), _q("pc", "mm", "material.peterson_constant"),
    ])
    questions = clarifying_questions(spec)
    endurance = [q for q in questions if q.measurand == "material.endurance_limit"]
    assert len(endurance) == 1                    # asked once, not per check
    assert endurance[0].priority == 2
    assert set(endurance[0].unblocks) == {"fatigue (Goodman)", "notch fatigue"}
    assert questions[0].measurand == "material.endurance_limit"   # highest priority first


def test_top_k_caps_the_questions():
    spec = _spec([_q("t", "N*m", "shaft.torque")])   # torsion indicated, 4 inputs missing
    assert len(clarifying_questions(spec)) > 1
    assert len(clarifying_questions(spec, top_k=2)) == 2


def test_is_deterministic():
    spec = _spec([_q("t", "N*m", "shaft.torque"), _q("d", "mm", "shaft.diameter")])
    a = clarifying_questions(spec)
    b = clarifying_questions(spec)
    assert [(q.measurand, q.priority) for q in a] == [(q.measurand, q.priority) for q in b]
