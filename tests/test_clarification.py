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
    assert "scherfestigkeit" in q.question.lower()


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


# --- the dialog loop: answers close the gap and the verdict turns green ----------

def test_answers_take_an_underspecified_spec_to_verified():
    from gen.clarification import apply_answers, expected_unit
    from gen.demo import drive_shaft_spec
    from gen.pipeline import assess_specification

    spec = drive_shaft_spec()
    spec.quantities = [q for q in spec.quantities
                       if q.measurand != "material.shear_strength"]
    before = assess_specification(spec)
    assert before.overall == "needs_clarification"
    assert expected_unit("material.shear_strength") == "MPa"

    answered = apply_answers(spec, {"material.shear_strength": (260.0, "MPa")})
    after = assess_specification(answered)
    assert after.overall == "physics_verified"                  # the loop closes
    added = next(q for q in answered.quantities
                 if q.measurand == "material.shear_strength")
    assert added.origin.value == "decision"                     # declared, with provenance
    assert "Klärungsdialog" in added.rationale
    assert len(spec.quantities) == len(answered.quantities) - 1  # input not mutated


def test_answers_never_overwrite_an_existing_declaration():
    from gen.clarification import apply_answers
    from gen.demo import drive_shaft_spec

    spec = drive_shaft_spec()                                    # fully specified
    answered = apply_answers(spec, {"shaft.torque": (999.0, "N*m")})
    torque = [q for q in answered.quantities if q.measurand == "shaft.torque"]
    assert len(torque) == 1 and torque[0].value == 150.0         # original wins, no dup


def test_unblocks_lists_only_checks_an_answer_alone_makes_runnable():
    # When a check (torsion) is missing TWO inputs, answering ONE does NOT make it runnable.
    # priority still counts it (EVPI: it is needed), but unblocks must not CLAIM it — that would
    # overstate what the answer achieves. Before the fix, unblocks listed every contributing check.
    spec = drive_shaft_spec()
    spec.quantities = [q for q in spec.quantities
                       if q.measurand not in ("material.shear_strength", "material.shear_modulus")]
    by_m = {q.measurand: q for q in clarifying_questions(spec)}
    q_ss = by_m["material.shear_strength"]
    assert q_ss.priority >= 1                       # still counted as needed (EVPI proxy)
    assert "shaft torsion" not in q_ss.unblocks     # but it does NOT alone make torsion runnable


def test_clarified_qid_is_stable_across_answer_batches():
    # G3: the generated quantity id must depend only on the measurand, not on the batch it
    # arrived in (reproducibility — CLAUDE.md §5). Before the fix the id carried the batch index.
    from gen.clarification import apply_answers
    spec = Specification(run_id="r", idea="x", quantities=[])
    solo = apply_answers(spec, {"shaft.torque": (150.0, "N*m")})
    batch = apply_answers(spec, {"material.uts": (400.0, "MPa"), "shaft.torque": (150.0, "N*m")})
    id_solo = next(q.id for q in solo.quantities if q.measurand == "shaft.torque")
    id_batch = next(q.id for q in batch.quantities if q.measurand == "shaft.torque")
    assert id_solo == id_batch
