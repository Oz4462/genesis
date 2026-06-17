"""Run telemetry — a deterministic, OTel-shaped trace of a run's process.

Under a fixed (injected) clock the trace is exact: spans time their body, a failed gate or a
raised step is recorded status "error" (never silently ok), the summary aggregates, and the
export is OpenTelemetry-shaped. Offline, no LLM.

Run:  pytest tests/test_telemetry.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.interfaces import GateFailure, GateResult  # noqa: E402
from gen.telemetry import RunTrace  # noqa: E402


def _clock(values):
    """A deterministic clock that returns successive `values` (seconds)."""
    it = iter(values)
    return lambda: next(it)


def test_span_times_the_body_with_the_injected_clock():
    trace = RunTrace("r", clock=_clock([1.0, 1.25]))      # start 1.0 s, end 1.25 s
    with trace.span("research", "select", topic="shaft") as rec:
        rec["attributes"]["found"] = 3
    assert len(trace.events) == 1
    e = trace.events[0]
    assert e.name == "research" and e.kind == "select" and e.status == "ok"
    assert e.duration_ms == 250.0                          # 0.25 s -> 250 ms, exact
    assert e.attributes == {"topic": "shaft", "found": 3}


def test_raised_step_is_recorded_as_error_and_reraised():
    trace = RunTrace("r", clock=_clock([0.0, 0.1]))
    with pytest.raises(ValueError):
        with trace.span("derive", "refine"):
            raise ValueError("boom")
    assert trace.events[0].status == "error"               # surfaced, not swallowed
    assert trace.events[0].kind == "refine"


def test_record_gate_marks_failure_as_error_with_codes():
    trace = RunTrace("r")
    ok = GateResult(gate="gamma", passed=True, failures=[])
    bad = GateResult(gate="delta-physics", passed=False,
                     failures=[GateFailure(code="PHYSICS_CHECK_FAILED", detail="x")])
    trace.record_gate("gamma", ok)
    trace.record_gate("delta-physics", bad)
    assert trace.events[0].status == "ok" and trace.events[0].attributes["passed"] is True
    assert trace.events[1].status == "error"
    assert trace.events[1].attributes["failure_codes"] == ["PHYSICS_CHECK_FAILED"]


def test_summary_aggregates_counts_and_time():
    trace = RunTrace("r", clock=_clock([0.0, 0.5, 0.0, 1.5]))
    with trace.span("a", "gate"):
        pass
    with trace.span("b", "refine"):
        pass
    trace.record_gate("c", GateResult(gate="c", passed=False,
                                      failures=[GateFailure("E", "d")]))
    s = trace.summary()
    assert s["n_events"] == 3 and s["n_errors"] == 1
    assert s["by_kind"] == {"gate": 2, "refine": 1}        # record_gate is kind "gate"
    assert s["total_ms"] == 500.0 + 1500.0                 # 0.5 s + 1.5 s spans


def test_export_is_opentelemetry_shaped():
    trace = RunTrace("r", clock=_clock([0.0, 0.0]))
    trace.record("step", "clarify", status="ok", duration_ms=12.0, asked=2)
    span = trace.to_otel()[0]
    assert span["name"] == "step"
    assert span["attributes"] == {"genesis.kind": "clarify", "asked": 2}
    assert span["status"] == "OK" and span["duration_ms"] == 12.0


def test_is_deterministic_under_a_fixed_clock():
    def build():
        t = RunTrace("r", clock=_clock([0.0, 0.3]))
        with t.span("x", "gate"):
            pass
        return [(e.name, e.duration_ms, e.status) for e in t.events]
    assert build() == build()


def test_span_with_a_reserved_attribute_name_does_not_crash():
    # G1: an attribute named 'status'/'duration_ms'/'kind' collides with record()'s own kwargs
    # and raised TypeError in the finally. Reserved keys are dropped so the span records cleanly.
    t = RunTrace("r", clock=lambda: 0.0)
    with t.span("step", "select", status="custom", n=3):     # 'status' is reserved
        pass
    e = t.events[0]
    assert e.status == "ok" and e.attributes.get("n") == 3    # recorded, no crash
    assert "status" not in e.attributes                       # reserved key dropped


def test_span_body_exception_is_not_masked_by_a_reserved_attribute():
    # G1/G2: with a reserved attribute, the finally's record() raised TypeError and masked the
    # body's real exception. Now the body's ValueError surfaces and the step is recorded 'error'.
    t = RunTrace("r", clock=lambda: 0.0)
    with pytest.raises(ValueError):
        with t.span("step", "select", duration_ms=5):
            raise ValueError("body failed")
    assert t.events[0].status == "error"


def test_to_otel_kind_is_authoritative_over_a_colliding_attribute():
    # G4: an attribute literally named 'genesis.kind' overrode the real kind in the export.
    t = RunTrace("r", clock=lambda: 0.0)
    t.record("step", "select", **{"genesis.kind": "spoofed"})
    span = t.to_otel()[0]
    assert span["attributes"]["genesis.kind"] == "select"     # real kind wins, not the attribute
