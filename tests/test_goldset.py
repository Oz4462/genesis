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

from gen.goldset import (  # noqa: E402
    GoldCase,
    RunOutcome,
    load_goldset,
    report_to_outcome,
    run_goldset,
    score,
)


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


def test_fact_exact_token_match_prevents_substring_false_positive():
    """G3 safety: '4' must not match inside '14', 'M4x16', '400' etc. (exact token only)."""
    # Use the real fact_m4_diameter case which has must_contain=["4"]
    cases = load_goldset()
    m4 = next(c for c in cases if c.id == "fact_m4_diameter")
    # Bad LLM output containing '4' only inside other tokens -> should fail fact
    bad = RunOutcome(False, "M4x16 ISO 4762 screw has nominal 14 mm major dia (close to 4.5 clearance)")
    s_bad = score([m4], {m4.id: bad})
    assert s_bad.fact_accuracy == 0.0
    # Good: standalone 4 (or 4 in context as separate token)
    good = RunOutcome(False, "The nominal diameter of an M4 screw is 4 mm.")
    s_good = score([m4], {m4.id: good})
    assert s_good.fact_accuracy == 1.0
    # Also 4.5 should be its own token for the ISO case
    iso4 = next(c for c in cases if "iso273" in c.id.lower())
    good45 = RunOutcome(False, "ISO 273 medium for M4: 4.5 mm clearance hole.")
    assert score([iso4], {iso4.id: good45}).fact_accuracy == 1.0


def _write(tmp_path, fixture):
    import json
    f = tmp_path / "g.json"
    f.write_text(json.dumps(fixture), encoding="utf-8")
    return f


def test_loader_requires_all_three_kinds(tmp_path):
    # G1: without nonsense cases the headline abstention_recall would be a vacuous 1.0 -> fail-loud.
    f = _write(tmp_path, {"cases": [
        {"id": "f1", "kind": "fact", "input": "q", "expected": {"behavior": "answer", "must_contain": ["x"]}},
        {"id": "t1", "kind": "trap", "input": "q", "expected": {"behavior": "abstain_or_sourced"}},
    ]})
    with pytest.raises(ValueError, match="missing"):
        load_goldset(f)


def test_loader_rejects_an_empty_must_contain_token(tmp_path):
    # G2: an empty token ('' in text is always True) would auto-pass any non-abstaining fact.
    f = _write(tmp_path, {"cases": [
        {"id": "f1", "kind": "fact", "input": "q", "expected": {"behavior": "answer", "must_contain": [""]}},
    ]})
    with pytest.raises(ValueError, match="empty token"):
        load_goldset(f)


def test_loader_rejects_malformed_types(tmp_path):
    # G4/G6: a non-list 'cases' crashed with TypeError; a bare-string 'must_contain' silently
    # split into per-char tokens. Both must fail-loud with ValueError.
    with pytest.raises(ValueError, match="'cases'"):
        load_goldset(_write(tmp_path, {"cases": None}))
    with pytest.raises(ValueError, match="must_contain"):
        load_goldset(_write(tmp_path, {"cases": [
            {"id": "f1", "kind": "fact", "input": "q", "expected": {"behavior": "answer", "must_contain": "42"}},
        ]}))


def test_score_refuses_an_empty_case_set():
    # G7: score([], {}) returned all rates 1.0, ok=True -- a vacuous PASS bypassing the loader.
    with pytest.raises(ValueError, match="no cases"):
        score([], {})


def test_a_text_bearing_abstention_on_nonsense_is_a_hallucination():
    # G8: a runner flagging abstained=True while emitting answer text is hiding an answer; on a
    # nonsense case that is a fabrication, not a clean abstention.
    cases = [GoldCase("n", "nonsense", "q", "abstain")]
    s = score(cases, {"n": RunOutcome(True, "but actually here is an invented answer")})
    assert s.abstention_recall == 0.0 and "n" in s.hallucinations and not s.ok


# --- the runner: real pipeline wire, tested offline with scripted runs ---------------------------


class _FakeReport:
    """Minimal stand-in for a Phase-α Report (only the fields report_to_outcome reads)."""

    def __init__(self, statement_to_claim, body=""):
        self.statement_to_claim = statement_to_claim
        self.body = body


def test_report_to_outcome_abstains_when_no_claim_backed_statement():
    # Empty statement_to_claim -> gaps-only -> abstention (text dropped so it is not scored as an answer).
    out = report_to_outcome(_FakeReport({}, body="No claim could be verified."))
    assert out.abstained is True and out.text == "" and out.all_sourced is False


def test_report_to_outcome_is_sourced_when_statements_map_to_claims():
    out = report_to_outcome(_FakeReport({"The sky is blue.": "c1"}, body="The sky is blue."))
    assert out.abstained is False and out.all_sourced is True and "blue" in out.text


def test_run_goldset_scores_a_scripted_perfect_run():
    cases = load_goldset()

    def run_one(case):
        if case.kind == "fact":
            return RunOutcome(False, " ".join(case.must_contain), all_sourced=True)
        return RunOutcome(True)                       # trap/nonsense -> honest abstention

    outcomes, errors = run_goldset(cases, run_one)
    assert errors == {}
    s = score(cases, outcomes)
    assert s.ok and not s.hallucinations
    assert s.abstention_recall == 1.0 and s.fact_accuracy == 1.0


def test_run_goldset_catches_fabrication_and_records_errors_without_faking_abstention():
    cases = load_goldset()
    nonsense = next(c for c in cases if c.kind == "nonsense")
    a_fact = next(c for c in cases if c.kind == "fact")

    def run_one(case):
        if case.id == nonsense.id:
            return RunOutcome(False, "a confidently invented answer")   # fabrication on nonsense
        if case.id == a_fact.id:
            raise RuntimeError("backend down")                          # a real crash
        return RunOutcome(True)

    outcomes, errors = run_goldset(cases, run_one)
    # the crash is recorded honestly (NOT silently passed off as a clean abstention)...
    assert a_fact.id in errors and "backend down" in errors[a_fact.id]
    # ...yet every case still has an outcome, so the run is scorable (no silent missing case)
    assert set(outcomes) == {c.id for c in cases}
    s = score(cases, outcomes)
    # the fabricated nonsense answer is caught as a hallucination -> verdict FAIL
    assert nonsense.id in s.hallucinations and not s.ok
