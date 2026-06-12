"""Gold set — the measurement contract for the deferred live runs.

The fixture must load and validate (fail-loud on malformed cases); the scorer must give a
perfect scripted runner perfect rates, expose a hallucinating runner (nonsense answered ->
abstention recall drops, the case lands in `hallucinations`, ok=False), credit a sourced
trap answer, and REFUSE to score an incomplete run. Offline, no LLM.

Run:  pytest tests/test_goldset.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.goldset import GoldCase, RunOutcome, load_goldset, score  # noqa: E402


def _perfect_outcomes(cases):
    out = {}
    for c in cases:
        if c.kind == "fact":
            out[c.id] = RunOutcome(False, " ".join(c.must_contain), all_sourced=True)
        else:                                       # trap & nonsense: honest abstention
            out[c.id] = RunOutcome(True)
    return out


# --- the fixture ----------------------------------------------------------------

def test_goldset_v1_loads_and_covers_all_three_kinds():
    cases = load_goldset()
    kinds = {c.kind for c in cases}
    assert kinds == {"fact", "trap", "nonsense"}
    assert len(cases) >= 20
    assert len({c.id for c in cases}) == len(cases)            # unique ids


def test_loader_fails_loud_on_malformed_cases(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"cases":[{"id":"x","kind":"fact","input":"q",'
                   '"expected":{"behavior":"answer"}}]}', encoding="utf-8")
    with pytest.raises(ValueError, match="must_contain"):      # a fact needs tokens
        load_goldset(bad)
    bad.write_text('{"cases":[{"id":"x","kind":"nonsense","input":"q",'
                   '"expected":{"behavior":"answer"}}]}', encoding="utf-8")
    with pytest.raises(ValueError, match="behavior"):          # nonsense must abstain
        load_goldset(bad)


# --- the scorer -----------------------------------------------------------------

def test_perfect_runner_scores_perfectly():
    cases = load_goldset()
    s = score(cases, _perfect_outcomes(cases))
    assert s.fact_accuracy == 1.0 and s.abstention_recall == 1.0
    assert s.trap_resistance == 1.0 and s.hallucinations == [] and s.ok


def test_hallucinating_runner_is_exposed():
    cases = load_goldset()
    outcomes = _perfect_outcomes(cases)
    nonsense = [c for c in cases if c.kind == "nonsense"]
    victim = nonsense[0]
    outcomes[victim.id] = RunOutcome(False, "a confidently invented answer")
    s = score(cases, outcomes)
    assert s.abstention_recall < 1.0
    assert victim.id in s.hallucinations and not s.ok          # the headline bar fails


def test_sourced_trap_answer_is_credited_unsourced_is_fabrication():
    cases = load_goldset()
    outcomes = _perfect_outcomes(cases)
    trap = next(c for c in cases if c.kind == "trap")
    outcomes[trap.id] = RunOutcome(False, "answer with sources", all_sourced=True)
    assert score(cases, outcomes).trap_resistance == 1.0       # sourced answer is fine
    outcomes[trap.id] = RunOutcome(False, "a confident unsourced number")
    s = score(cases, outcomes)
    assert s.trap_resistance < 1.0 and trap.id in s.hallucinations


def test_incomplete_run_refuses_to_score():
    cases = load_goldset()
    outcomes = _perfect_outcomes(cases)
    outcomes.pop(cases[0].id)
    with pytest.raises(ValueError, match="incomplete"):
        score(cases, outcomes)


def test_wrong_fact_is_a_miss_not_a_fabrication():
    cases = [GoldCase("f", "fact", "q", "answer", ("42",))]
    s = score(cases, {"f": RunOutcome(False, "the answer is 41")})
    assert s.fact_accuracy == 0.0
    assert s.hallucinations == [] and s.ok                     # wrong != fabricated
