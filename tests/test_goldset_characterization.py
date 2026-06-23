"""Characterization / facade-detector for src/gen/goldset.py.

Headline under audit: a fail-loud loader over goldset/v1.json plus a deterministic
scorer whose `ok` bar is NO fabrication anywhere (hallucinations empty), where a
nonsense case ANSWERED is a hallucination by construction and an INCOMPLETE run is
REFUSED (never silently inflated).

This test is a real facade-detector, not a smoke test:
  (a) it proves the rates change MEANINGFULLY with the outcomes — the same gold set
      scored against different RunOutcome maps yields different rates / hallucination
      sets, so the outcomes are genuinely consumed (not a canned constant); and
  (b) it exercises the documented fail-loud / abstention paths exactly (the mandatory
      NEGATIVE tests: incomplete run refused, malformed fixture rejected, a fabricated
      nonsense/trap answer flagged).

Offline, deterministic, no LLM.

Run:  pytest tests/test_goldset_characterization.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402
from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from gen.goldset import (  # noqa: E402
    DEFAULT_PATH,
    GoldCase,
    GoldsetScore,
    RunOutcome,
    load_goldset,
    score,
)


# --------------------------------------------------------------------------------------
# helpers — outcome builders that drive the scorer
# --------------------------------------------------------------------------------------

def _perfect_outcomes(cases: list[GoldCase]) -> dict[str, RunOutcome]:
    """A flawless runner: facts answered with their tokens + sourced, traps/nonsense abstain."""
    out: dict[str, RunOutcome] = {}
    for c in cases:
        if c.kind == "fact":
            out[c.id] = RunOutcome(False, " ".join(c.must_contain), all_sourced=True)
        else:
            out[c.id] = RunOutcome(True)  # honest abstention for trap + nonsense
    return out


def _answered(text: str = "some confident unsourced value") -> RunOutcome:
    return RunOutcome(abstained=False, text=text, all_sourced=False)


# --------------------------------------------------------------------------------------
# the fixture loads and is genuinely curated
# --------------------------------------------------------------------------------------

def test_real_v1_fixture_loads_and_covers_all_kinds():
    assert DEFAULT_PATH.exists(), "the audited fixture goldset/v1.json must exist"
    cases = load_goldset()  # loads the REAL goldset/v1.json
    kinds = {c.kind for c in cases}
    assert kinds == {"fact", "trap", "nonsense"}
    assert len(cases) >= 20
    assert len({c.id for c in cases}) == len(cases)            # unique ids
    # every fact carries the tokens the scorer will demand — proves the fixture is
    # internally consistent with the scorer's fact-accuracy contract.
    for c in cases:
        if c.kind == "fact":
            assert c.must_contain, f"fact {c.id} has no must_contain tokens"


# --------------------------------------------------------------------------------------
# (a) the rates are genuinely DRIVEN by the outcomes — not a canned constant
# --------------------------------------------------------------------------------------

def test_perfect_run_scores_perfect_and_ok():
    cases = load_goldset()
    s = score(cases, _perfect_outcomes(cases))
    assert isinstance(s, GoldsetScore)
    assert s.n_cases == len(cases)
    assert s.fact_accuracy == 1.0
    assert s.abstention_recall == 1.0
    assert s.trap_resistance == 1.0
    assert s.hallucinations == []
    assert s.failures == []
    assert s.ok is True


def test_nonsense_answered_drops_abstention_recall_and_breaks_ok():
    """Driving-input change: flip ONE nonsense outcome from abstain -> answered and the
    headline metric must move + the case must be flagged a hallucination + ok flips."""
    cases = load_goldset()
    outcomes = _perfect_outcomes(cases)
    nonsense_id = next(c.id for c in cases if c.kind == "nonsense")

    baseline = score(cases, outcomes)
    assert baseline.ok is True and baseline.abstention_recall == 1.0

    outcomes[nonsense_id] = _answered("Vorkstanium-7075 has a yield strength of 503 MPa")
    s = score(cases, outcomes)

    assert s.abstention_recall < baseline.abstention_recall   # rate moved with the input
    assert nonsense_id in s.hallucinations                    # fabrication by construction
    assert nonsense_id in s.failures
    assert s.ok is False                                      # no-fabrication bar broken


def test_trap_answered_unsourced_is_fabrication_but_sourced_is_credited():
    cases = load_goldset()
    trap_id = next(c.id for c in cases if c.kind == "trap")

    # unsourced confident answer to a trap -> fabrication, resistance drops, ok False
    bad = _perfect_outcomes(cases)
    bad[trap_id] = RunOutcome(abstained=False, text="exactly 0.83 g", all_sourced=False)
    s_bad = score(cases, bad)
    assert trap_id in s_bad.hallucinations
    assert s_bad.trap_resistance < 1.0
    assert s_bad.ok is False

    # SAME trap, SAME answer text, but fully sourced -> credited, no fabrication, ok True
    good = _perfect_outcomes(cases)
    good[trap_id] = RunOutcome(abstained=False, text="exactly 0.83 g", all_sourced=True)
    s_good = score(cases, good)
    assert trap_id not in s_good.hallucinations
    assert s_good.trap_resistance == 1.0
    assert s_good.ok is True


def test_wrong_fact_is_a_miss_not_a_fabrication():
    """Documented design choice: a fact answered with the WRONG value is a miss (drops
    fact_accuracy, lands in failures) but is NOT a fabrication — ok must stay True."""
    cases = load_goldset()
    fact_id = next(c.id for c in cases if c.kind == "fact")
    outcomes = _perfect_outcomes(cases)
    # answer that cannot contain the expected token set
    outcomes[fact_id] = RunOutcome(abstained=False, text="zzz nothing useful", all_sourced=True)
    s = score(cases, outcomes)
    assert s.fact_accuracy < 1.0
    assert fact_id in s.failures
    assert fact_id not in s.hallucinations
    assert s.ok is True


def test_token_match_does_not_substring_falsely():
    """G3 safety: a fact requiring token '4' must NOT pass on 'M4x16' / '14' / '400'."""
    cases = load_goldset()
    # fact_m4_diameter requires ["4"]; an answer mentioning only 'M4x16' / '14' lacks token '4'
    fact = next(c for c in cases if c.id == "fact_m4_diameter")
    assert fact.must_contain == ("4",)
    outcomes = _perfect_outcomes(cases)
    outcomes[fact.id] = RunOutcome(abstained=False, text="use an M4x16 or a 14 mm bolt",
                                   all_sourced=True)
    s = score(cases, outcomes)
    assert fact.id in s.failures            # token '4' not matched as a substring
    assert fact.id not in s.hallucinations  # still just a miss


def test_flagged_abstention_with_text_is_treated_as_answered():
    """A runner reporting abstained=True while still emitting answer text is hiding an
    answer — for a nonsense case that must count as a fabrication, not an abstention."""
    cases = load_goldset()
    nonsense_id = next(c.id for c in cases if c.kind == "nonsense")
    outcomes = _perfect_outcomes(cases)
    outcomes[nonsense_id] = RunOutcome(abstained=True, text="actually it is 5 GPa")
    s = score(cases, outcomes)
    assert nonsense_id in s.hallucinations
    assert s.ok is False


# --------------------------------------------------------------------------------------
# (b) the mandatory NEGATIVE / fail-loud paths
# --------------------------------------------------------------------------------------

def test_incomplete_run_is_refused_never_silently_inflated():
    cases = load_goldset()
    outcomes = _perfect_outcomes(cases)
    dropped = cases[0].id
    del outcomes[dropped]                              # one missing outcome
    with pytest.raises(ValueError, match="incomplete"):
        score(cases, outcomes)


def test_empty_cases_is_not_a_vacuous_pass():
    with pytest.raises(ValueError, match="no cases"):
        score([], {})


def _write(tmp_path, payload: str) -> Path:
    p = tmp_path / "bad.json"
    p.write_text(payload, encoding="utf-8")
    return p


def test_loader_fails_loud_on_fact_without_tokens(tmp_path):
    bad = _write(tmp_path, '{"cases":[{"id":"x","kind":"fact","input":"q",'
                           '"expected":{"behavior":"answer"}}]}')
    with pytest.raises(ValueError, match="must_contain"):
        load_goldset(bad)


def test_loader_fails_loud_on_behavior_kind_mismatch(tmp_path):
    bad = _write(tmp_path, '{"cases":[{"id":"x","kind":"nonsense","input":"q",'
                           '"expected":{"behavior":"answer"}}]}')
    with pytest.raises(ValueError, match="behavior"):
        load_goldset(bad)


def test_loader_fails_loud_on_duplicate_id(tmp_path):
    bad = _write(
        tmp_path,
        '{"cases":['
        '{"id":"dup","kind":"fact","input":"q","expected":{"behavior":"answer","must_contain":["x"]}},'
        '{"id":"dup","kind":"fact","input":"q","expected":{"behavior":"answer","must_contain":["y"]}}'
        ']}',
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_goldset(bad)


def test_loader_fails_loud_on_unknown_kind(tmp_path):
    bad = _write(tmp_path, '{"cases":[{"id":"x","kind":"riddle","input":"q",'
                           '"expected":{"behavior":"answer"}}]}')
    with pytest.raises(ValueError, match="unknown kind"):
        load_goldset(bad)


def test_loader_fails_loud_on_empty_input(tmp_path):
    bad = _write(tmp_path, '{"cases":[{"id":"x","kind":"fact","input":"   ",'
                           '"expected":{"behavior":"answer","must_contain":["x"]}}]}')
    with pytest.raises(ValueError, match="empty input"):
        load_goldset(bad)


def test_loader_refuses_a_set_missing_a_kind(tmp_path):
    """The headline abstention_recall needs nonsense; a fact-only set must be refused."""
    bad = _write(tmp_path, '{"cases":[{"id":"x","kind":"fact","input":"q",'
                           '"expected":{"behavior":"answer","must_contain":["x"]}}]}')
    with pytest.raises(ValueError, match="missing"):
        load_goldset(bad)


# --------------------------------------------------------------------------------------
# property-based invariants — the scorer over the REAL set must respect its contract
# --------------------------------------------------------------------------------------

_CASES = load_goldset()


@settings(max_examples=80)
@given(answer_flags=st.lists(st.booleans(), min_size=len(_CASES), max_size=len(_CASES)))
def test_property_hallucinations_equal_unsourced_answers_to_traps_and_nonsense(answer_flags):
    """Invariant: a hallucination is EXACTLY an unsourced answer to a trap or a nonsense
    case. Facts never contribute hallucinations (a wrong fact is a miss). Vary which
    trap/nonsense cases get answered and the hallucination set must track that exactly —
    proving the outcomes drive the metric, with no silent canned value."""
    outcomes: dict[str, RunOutcome] = {}
    expected_halluc: set[str] = set()
    for case, answer in zip(_CASES, answer_flags):
        if case.kind == "fact":
            # always a correct, sourced fact answer -> never a hallucination
            outcomes[case.id] = RunOutcome(False, " ".join(case.must_contain), all_sourced=True)
        else:
            if answer:  # confident UNSOURCED answer to a trap/nonsense -> fabrication
                outcomes[case.id] = RunOutcome(False, "a confident unsourced claim", all_sourced=False)
                expected_halluc.add(case.id)
            else:       # honest abstention -> correct
                outcomes[case.id] = RunOutcome(True)

    s = score(_CASES, outcomes)
    assert set(s.hallucinations) == expected_halluc
    assert s.ok is (len(expected_halluc) == 0)
    # rates are genuine probabilities in [0, 1]
    for r in (s.fact_accuracy, s.abstention_recall, s.trap_resistance):
        assert 0.0 <= r <= 1.0


@settings(max_examples=50)
@given(answer_flags=st.lists(st.booleans(), min_size=len(_CASES), max_size=len(_CASES)))
def test_property_score_is_deterministic(answer_flags):
    """A5 reproducibility: scoring the same outcomes twice yields an identical result."""
    outcomes = {
        c.id: (RunOutcome(False, " ".join(c.must_contain), all_sourced=True)
               if c.kind == "fact"
               else (RunOutcome(False, "x", all_sourced=False) if a else RunOutcome(True)))
        for c, a in zip(_CASES, answer_flags)
    }
    a = score(_CASES, outcomes)
    b = score(_CASES, outcomes)
    assert (a.fact_accuracy, a.abstention_recall, a.trap_resistance) == \
           (b.fact_accuracy, b.abstention_recall, b.trap_resistance)
    assert a.hallucinations == b.hallucinations
    assert a.failures == b.failures
