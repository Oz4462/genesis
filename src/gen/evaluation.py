"""Anti-hallucination evaluation harness — the guarantee as a measured metric.

The VISION asks that abstention/refusal be *measured*, not asserted. The gates are
proven by unit tests; this harness aggregates them into a single, reportable
metric over a curated set of SOUND and UNSOUND γ specifications: does GATE γ pass
every sound case (including honest abstention) and fail every unsound one?

Two numbers matter, and one is non-negotiable:
  * leaks       — UNSOUND cases that the gate let PASS. This is a hallucination
                  slipping through. It must be ZERO.
  * false_alarms — SOUND cases the gate wrongly failed (over-blocking).

This is offline and LLM-free (the gates are). It does NOT measure live model
quality (that needs the deferred real-model run); it measures the deterministic
discrimination of the anti-hallucination gate itself, end-to-end over real specs.
"""

from __future__ import annotations

from dataclasses import dataclass

from .core.state import (
    Claim,
    ClaimStatus,
    Derivation,
    Question,
    Quantity,
    RunState,
    SourceRef,
    SourceSupport,
    Specification,
    ValueOrigin,
)
from .demo import capstone_state
from .verification.gates import gate_gamma


@dataclass
class Case:
    """One evaluation case: a name, the state, and whether it SHOULD pass GATE γ.
    `hallucination_class` labels what an unsound case tries to sneak through."""

    name: str
    state: RunState
    expected_pass: bool
    hallucination_class: str = ""


def _claim(cid: str, text: str) -> Claim:
    return Claim(
        id=cid, text=text,
        sources=[SourceRef(f"https://{cid}", True, support=SourceSupport.SUPPORTS)],
        status=ClaimStatus.VERIFIED, confidence=0.95,
        verification=[SourceRef(f"https://i/{cid}", True, support=SourceSupport.SUPPORTS)],
    )


def _capstone_mutated(mutate) -> RunState:
    st = capstone_state()
    mutate(st)
    return st


def _set_value(qid: str, value: float):
    def _m(st: RunState) -> None:
        q = next(x for x in st.specification.quantities if x.id == qid)
        q.value = value
    return _m


def _drop_claim(cid: str):
    def _m(st: RunState) -> None:
        st.claims = [c for c in st.claims if c.id != cid]
    return _m


def _abstention_state() -> RunState:
    spec = Specification(run_id="r", idea="unanswerable", gaps=["nothing could be grounded"])
    st = RunState(question=Question(raw="?", run_id="r"))
    st.specification = spec
    return st


def _contradiction_state() -> RunState:
    def g(qid, val, m):
        return Quantity(id=qid, name=qid, value=val, unit="V", origin=ValueOrigin.GROUNDED,
                        grounding=[f"c_{qid}"], measurand=m)
    spec = Specification(run_id="r", idea="conflict",
                         quantities=[g("a", 12.0, "rail.v"), g("b", 24.0, "rail.v")])
    st = RunState(question=Question(raw="?", run_id="r"))
    st.claims = [_claim("c_a", "The rail is 12 V."), _claim("c_b", "The rail is 24 V.")]
    st.specification = spec
    return st


def _dimension_mismatch_state() -> RunState:
    quantities = [
        Quantity(id="m", name="m", value=2.0, unit="kg", origin=ValueOrigin.DECISION, rationale="x"),
        Quantity(id="l", name="l", value=3.0, unit="m", origin=ValueOrigin.DECISION, rationale="x"),
        # declared as length but the formula yields mass*length -> C-15
        Quantity(id="bad", name="bad", value=6.0, unit="m", origin=ValueOrigin.DERIVED,
                 derivation=Derivation(formula="m * l", inputs=("m", "l"))),
    ]
    spec = Specification(run_id="r", idea="dim", quantities=quantities)
    st = RunState(question=Question(raw="?", run_id="r"))
    st.specification = spec
    return st


def anti_hallucination_cases() -> list[Case]:
    """Curated sound + unsound γ cases, one per hallucination class GATE γ guards."""
    return [
        Case("capstone (full sound spec)", capstone_state(), True),
        Case("honest abstention (empty + gaps)", _abstention_state(), True),
        Case("invented price not in claim", _capstone_mutated(_set_value("q_price", 9.99)),
             False, "C-4 value-not-in-grounding"),
        Case("broken derivation (design load)", _capstone_mutated(_set_value("q_design", 99.0)),
             False, "C-6 broken-derivation"),
        Case("value grounded in missing claim", _capstone_mutated(_drop_claim("c_load")),
             False, "C-2 value-unknown-claim"),
        Case("contradiction between facts", _contradiction_state(), False,
             "C-17 cross-claim-conflict"),
        Case("dimensional nonsense", _dimension_mismatch_state(), False,
             "C-15 dimension-mismatch"),
    ]


@dataclass
class EvalReport:
    total: int
    correct: int
    leaks: list[str]          # unsound cases that wrongly PASSED (must be empty)
    false_alarms: list[str]   # sound cases that wrongly FAILED
    verdicts: list[tuple[str, bool, bool]]  # (name, expected_pass, actual_pass)


def evaluate(cases: list[Case]) -> EvalReport:
    """Run GATE γ over every case and score the discrimination."""
    leaks: list[str] = []
    false_alarms: list[str] = []
    verdicts: list[tuple[str, bool, bool]] = []
    correct = 0
    for c in cases:
        actual = gate_gamma(c.state).passed
        verdicts.append((c.name, c.expected_pass, actual))
        if actual == c.expected_pass:
            correct += 1
        elif c.expected_pass and not actual:
            false_alarms.append(c.name)
        else:  # not expected_pass and actual -> a hallucination slipped through
            leaks.append(c.name)
    return EvalReport(len(cases), correct, leaks, false_alarms, verdicts)


def format_report(report: EvalReport) -> str:
    lines = ["Anti-hallucination gate evaluation (deterministic, offline):", ""]
    for name, exp, act in report.verdicts:
        mark = "OK " if exp == act else "XX "
        lines.append(f"  {mark}{'PASS' if act else 'FAIL'} (expected {'PASS' if exp else 'FAIL'})  {name}")
    lines.append("")
    lines.append(f"  score: {report.correct}/{report.total} correct")
    lines.append(f"  leaks (hallucinations that passed): {len(report.leaks)}  <- must be 0")
    lines.append(f"  false alarms (sound specs blocked): {len(report.false_alarms)}")
    return "\n".join(lines)
