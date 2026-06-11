"""Run telemetry — a structured, exportable trace of a GENESIS run (research #4).

Production-agent practice (NIST AI RMF; OpenTelemetry GenAI) is to capture a full reasoning
trail: every gate, tool call, and decision as a structured span with attributes and status,
so a run is auditable and regressions are caught — teams with observability reach ~2.2x the
reliability. GENESIS records facts in the ledger; this module records the PROCESS: which gates
ran, their verdicts and failures, refine rounds, timings — a trace that complements the ledger.

It is dependency-light by design: it builds an in-process trace whose events export to an
OpenTelemetry-shaped dict (name + attributes + status), so a real OTel exporter can consume it
without GENESIS depending on the OTel SDK. Timing is observability-only metadata (never part of
any gate verdict or reproducible output) and the clock is INJECTABLE, so a trace is fully
deterministic under a fixed clock — the tests pin exact durations. Offline, no model calls.
"""

from __future__ import annotations

import time
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable

from .core.interfaces import GateResult


@dataclass(frozen=True)
class TraceEvent:
    """One recorded step of a run.

    `name`         the step label (e.g. "gate:delta-physics", "refine:round").
    `kind`         a coarse category ("gate" | "select" | "refine" | "clarify" | ...).
    `attributes`   structured key/values (verdict, failure codes, counts, ...).
    `status`       "ok" or "error" (a failed gate / raised step is "error").
    `duration_ms`  wall time of the step (observability metadata, not a verdict input).
    """

    name: str
    kind: str
    attributes: dict
    status: str
    duration_ms: float


@dataclass
class RunTrace:
    """An ordered, exportable trace of one run. `clock` is injectable for deterministic
    tests (defaults to a real monotonic clock)."""

    run_id: str
    clock: Callable[[], float] = time.perf_counter
    events: list[TraceEvent] = field(default_factory=list)

    def record(self, name: str, kind: str, *, status: str = "ok",
               duration_ms: float = 0.0, **attributes) -> TraceEvent:
        """Append a fully-formed event (for steps timed elsewhere or instantaneous)."""
        event = TraceEvent(name, kind, dict(attributes), status, duration_ms)
        self.events.append(event)
        return event

    @contextmanager
    def span(self, name: str, kind: str, **attributes):
        """Time a step and record it. Yields a mutable dict the body may update — set
        ``rec["status"]`` or add keys to ``rec["attributes"]``; a raised exception is
        recorded as status "error" and re-raised (the failure is surfaced, not swallowed)."""
        rec: dict = {"status": "ok", "attributes": {}}
        start = self.clock()
        try:
            yield rec
        except Exception:
            rec["status"] = "error"
            raise
        finally:
            duration = (self.clock() - start) * 1000.0
            self.record(name, kind, status=rec["status"], duration_ms=duration,
                        **{**attributes, **rec["attributes"]})

    def record_gate(self, name: str, result: GateResult, *, duration_ms: float = 0.0) -> TraceEvent:
        """Record a gate verdict as an event: status "error" when it did NOT pass, with the
        failure codes as an attribute — the observability twin of the gate's own honesty."""
        return self.record(
            f"gate:{name}", "gate",
            status="ok" if result.passed else "error", duration_ms=duration_ms,
            passed=result.passed, n_failures=len(result.failures),
            failure_codes=[f.code for f in result.failures],
        )

    def summary(self) -> dict:
        """Aggregate the trace: event/error counts, per-kind counts, total time."""
        return {
            "run_id": self.run_id,
            "n_events": len(self.events),
            "n_errors": sum(1 for e in self.events if e.status == "error"),
            "by_kind": dict(Counter(e.kind for e in self.events)),
            "total_ms": sum(e.duration_ms for e in self.events),
        }

    def to_otel(self) -> list[dict]:
        """Export each event as an OpenTelemetry-shaped span dict (name, attributes with the
        kind folded in, status, duration) — consumable by a real OTel exporter without this
        module depending on the OTel SDK."""
        return [
            {
                "name": e.name,
                "attributes": {"genesis.kind": e.kind, **e.attributes},
                "status": "OK" if e.status == "ok" else "ERROR",
                "duration_ms": e.duration_ms,
            }
            for e in self.events
        ]
