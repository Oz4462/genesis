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
from .demo import capstone_state, drive_shaft_state
from .physics_selection import evaluate_spec_physics
from .verification.gates import gate_gamma


@dataclass
class Case:
    """One evaluation case: a name, the state, and whether it SHOULD pass its gate.
    `hallucination_class` labels what an unsound case tries to sneak through; `gate`
    selects which gate scores it ("gamma" — the anti-hallucination spec gate — or
    "physics" — the δ-physics validator gate)."""

    name: str
    state: RunState
    expected_pass: bool
    hallucination_class: str = ""
    gate: str = "gamma"


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
    """Curated sound + unsound γ cases — a REPRESENTATIVE subset, one case per targeted
    hallucination class (C-2/C-4/C-6/C-15/C-17), NOT all of C-1..C-18; the uncovered codes
    are an honest coverage gap, not a proven-leak-free claim over every class."""
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


def _shaft_mutated(mutate) -> RunState:
    st = drive_shaft_state()
    mutate(st)
    return st


def physics_cases() -> list[Case]:
    """Sound + unsound cases for the δ-physics gate: a sound drive shaft passes; an
    over-stressed shaft must be CAUGHT (a failed margin), and a contradictory geometry
    (zero diameter) must be SURFACED (a validator error), never silently passed."""
    return [
        Case("drive shaft (sound design)", drive_shaft_state(), True, gate="physics"),
        Case("over-stressed shaft (d=5 mm)", _shaft_mutated(_set_value("q_shaft_d", 5.0)),
             False, "physics-margin-not-cleared", gate="physics"),
        Case("contradictory geometry (d=0)", _shaft_mutated(_set_value("q_shaft_d", 0.0)),
             False, "physics-uncomputable-input", gate="physics"),
    ]


def all_cases() -> list[Case]:
    """The full multi-gate discrimination set — the anti-hallucination γ gate AND the
    δ-physics gate, sound and unsound, scored together."""
    return anti_hallucination_cases() + physics_cases()


@dataclass
class EvalReport:
    total: int
    correct: int
    leaks: list[str]          # unsound cases that wrongly PASSED (must be empty)
    false_alarms: list[str]   # sound cases that wrongly FAILED
    verdicts: list[tuple[str, bool, bool]]  # (name, expected_pass, actual_pass)
    n_unsound: int = 0        # how many cases SHOULD fail (the leak denominator)
    n_sound: int = 0          # how many cases SHOULD pass (the false-alarm denominator)

    @property
    def leak_rate(self) -> float | None:
        """Fraction of unsound cases that wrongly passed — the false-accept rate of the
        guarantee. MUST be 0. None when there are NO unsound cases: a vacuous 0% over zero
        unsound cases would falsely read as a held guarantee (nothing was discriminated)."""
        return len(self.leaks) / self.n_unsound if self.n_unsound else None

    @property
    def false_alarm_rate(self) -> float | None:
        """Fraction of sound cases wrongly blocked (over-blocking). None when there are no
        sound cases (nothing to discriminate)."""
        return len(self.false_alarms) / self.n_sound if self.n_sound else None


def _gate_verdict(case: Case) -> bool:
    """Pass/fail of `case` under its declared gate. Pure, deterministic, offline."""
    if case.gate == "gamma":
        return gate_gamma(case.state).passed
    if case.gate == "physics":
        # gate.passed is True both when the checks cleared AND when an indicated check could
        # not run (a gap). An indicated-but-unrunnable check is NOT a clean pass — same honesty
        # as pipeline.physics_ok, so a non-empty gap list counts as not-passed here too.
        result = evaluate_spec_physics(case.state.specification)
        return result["gate"].passed and not result["gaps"]
    raise ValueError(f"unknown gate {case.gate!r} in case {case.name!r}")


def evaluate(cases: list[Case]) -> EvalReport:
    """Run each case under its gate and score the discrimination (leaks / false alarms)."""
    leaks: list[str] = []
    false_alarms: list[str] = []
    verdicts: list[tuple[str, bool, bool]] = []
    correct = 0
    for c in cases:
        actual = _gate_verdict(c)
        verdicts.append((c.name, c.expected_pass, actual))
        if actual == c.expected_pass:
            correct += 1
        elif c.expected_pass and not actual:
            false_alarms.append(c.name)
        else:  # not expected_pass and actual -> a hallucination slipped through
            leaks.append(c.name)
    n_unsound = sum(1 for c in cases if not c.expected_pass)
    return EvalReport(len(cases), correct, leaks, false_alarms, verdicts,
                      n_unsound=n_unsound, n_sound=len(cases) - n_unsound)


def _pct(rate: float | None) -> str:
    """None-safe percentage: 'n/a' when there was nothing to discriminate (never a vacuous 0%)."""
    return "n/a" if rate is None else f"{rate:.0%}"


def format_report(report: EvalReport) -> str:
    lines = ["Anti-Halluzinations-Gate-Evaluation (deterministisch, offline):", ""]
    for name, exp, act in report.verdicts:
        mark = "OK " if exp == act else "XX "
        lines.append(f"  {mark}{'PASS' if act else 'FAIL'} (erwartet {'PASS' if exp else 'FAIL'})  {name}")
    lines.append("")
    lines.append(f"  Ergebnis: {report.correct}/{report.total} korrekt "
                 f"({report.n_unsound} unsound / {report.n_sound} sound — kuratierte Offline-Fixtures, "
                 "misst Gate-Diskriminierung, nicht Live-Modell-Qualität)")
    lines.append(f"  Leaks (durchgerutschte Halluzinationen): {len(report.leaks)}  "
                 f"(Rate {_pct(report.leak_rate)})  <- muss 0 sein")
    lines.append(f"  Fehlalarme (fälschlich blockierte solide Specs): {len(report.false_alarms)}  "
                 f"(Rate {_pct(report.false_alarm_rate)})")
    return "\n".join(lines)
