"""The anti-hallucination guarantee as a measured metric.

The gates are proven by unit tests; this harness aggregates them into one number
the VISION asks for: over a curated set of SOUND and UNSOUND gamma specs, GATE
gamma must pass every sound case (including honest abstention) and fail every
unsound one. The non-negotiable metric is LEAKS == 0 (no hallucination class
slips through).

Offline, no LLM.

Run:  pytest tests/test_evaluation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.evaluation import (  # noqa: E402
    all_cases,
    anti_hallucination_cases,
    evaluate,
    format_report,
    physics_cases,
)


def test_zero_leaks_and_zero_false_alarms():
    report = evaluate(anti_hallucination_cases())
    assert report.leaks == [], f"hallucinations slipped through: {report.leaks}"
    assert report.false_alarms == [], f"sound specs wrongly blocked: {report.false_alarms}"
    assert report.correct == report.total


def test_cases_cover_sound_and_unsound():
    cases = anti_hallucination_cases()
    assert any(c.expected_pass for c in cases)          # at least one sound case
    assert any(not c.expected_pass for c in cases)      # and one unsound case
    # honest abstention (empty spec) is among the SOUND cases
    assert any(c.expected_pass and "abstention" in c.name for c in cases)


def test_each_unsound_case_actually_fails_the_gate():
    from gen.verification.gates import gate_gamma
    for c in anti_hallucination_cases():
        if not c.expected_pass:
            assert not gate_gamma(c.state).passed, f"{c.name} ({c.hallucination_class}) leaked"


def test_report_renders():
    out = format_report(evaluate(anti_hallucination_cases()))
    assert "Leaks (durchgerutschte Halluzinationen): 0" in out
    assert "Ergebnis:" in out


# --- multi-gate harness: the delta-physics gate is measured too -----------------

def test_full_multigate_harness_zero_leaks():
    # the anti-hallucination (gamma) gate AND the delta-physics gate, scored together:
    # no unsound case of EITHER gate may slip through, and no sound case is over-blocked.
    report = evaluate(all_cases())
    assert report.leaks == [], f"leaks across gates: {report.leaks}"
    assert report.false_alarms == [], f"over-blocked: {report.false_alarms}"
    assert report.correct == report.total
    assert report.leak_rate == 0.0
    assert report.n_unsound > 0 and report.n_sound > 0          # the set has both


def test_physics_gate_discrimination():
    from gen.physics_selection import evaluate_spec_physics
    cases = physics_cases()
    assert any(c.expected_pass for c in cases) and any(not c.expected_pass for c in cases)
    for c in cases:
        passed = evaluate_spec_physics(c.state.specification)["gate"].passed
        assert passed == c.expected_pass, f"{c.name}: physics gate {passed}, expected {c.expected_pass}"


def test_leak_rate_denominator_counts_unsound_cases():
    report = evaluate(all_cases())
    assert report.n_unsound == sum(1 for c in all_cases() if not c.expected_pass)
    assert report.n_sound == sum(1 for c in all_cases() if c.expected_pass)
    out = format_report(report)
    assert "Rate 0%" in out                                     # leak rate rendered, 0%
