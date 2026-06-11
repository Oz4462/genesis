"""Acceptance tests for tolerance / fit declarations (Phase δ, mechanism from γ).

These prove that the existing expression-constraint machinery (GATE γ C-13) is
sufficient to declare and CHECK real mechanical fits — clearance fit, interference
(press) fit, a symmetric tolerance band, and a monotone size chain — and, crucially,
that the gate NEVER invents a fit: an undeclared tight clearance passes, because
GENESIS imposes no ISO tolerance the human did not state. There is no new engine
here; this file is the executable proof + honesty guarantee for the fit pattern.

Run:  pytest tests/test_fits.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.state import (  # noqa: E402
    Claim,
    ClaimStatus,
    Constraint,
    Question,
    Quantity,
    RunState,
    SourceRef,
    SourceSupport,
    Specification,
    ValueOrigin,
)
from gen.verification.gates import gate_gamma  # noqa: E402


def _decision(qid: str, value: float, unit: str = "mm") -> Quantity:
    return Quantity(id=qid, name=qid, value=value, unit=unit,
                    origin=ValueOrigin.DECISION, rationale="fit parameter")


def _state(quantities, constraints) -> RunState:
    st = RunState(question=Question(raw="fit", run_id="r"))
    st.specification = Specification(
        run_id="r", idea="fit", quantities=quantities, constraints=constraints,
    )
    return st


def _passes(quantities, constraints) -> bool:
    return gate_gamma(_state(quantities, constraints)).passed


def _codes(quantities, constraints) -> set[str]:
    return {f.code for f in gate_gamma(_state(quantities, constraints)).failures}


# --- clearance (slip) fit: hole >= shaft + min clearance ----------------------

def test_clearance_fit_holds_and_is_caught():
    qs = [_decision("hole", 4.5), _decision("shaft", 4.0), _decision("clear", 0.2)]
    fit = [Constraint(id="k", kind="ge", left="hole", right="shaft + clear", reason="slip fit")]
    assert _passes(qs, fit)                               # 4.5 >= 4.2
    qs[0].value = 4.1                                     # too tight: 4.1 < 4.2
    assert "CONSTRAINT_VIOLATION" in _codes(qs, fit)


# --- interference (press) fit: shaft >= hole + min interference ----------------

def test_interference_fit():
    qs = [_decision("hole", 10.0), _decision("shaft", 10.03), _decision("inter", 0.02)]
    fit = [Constraint(id="k", kind="ge", left="shaft", right="hole + inter", reason="press fit")]
    assert _passes(qs, fit)                               # 10.03 >= 10.02
    qs[1].value = 10.01                                  # not enough interference
    assert "CONSTRAINT_VIOLATION" in _codes(qs, fit)


# --- symmetric tolerance band: nominal - tol <= actual <= nominal + tol --------

def test_symmetric_tolerance_band():
    qs = [_decision("actual", 20.04), _decision("nominal", 20.0), _decision("tol", 0.05)]
    band = [
        Constraint(id="lo", kind="ge", left="actual", right="nominal - tol", reason="band low"),
        Constraint(id="hi", kind="le", left="actual", right="nominal + tol", reason="band high"),
    ]
    assert _passes(qs, band)                              # 19.95 <= 20.04 <= 20.05
    qs[0].value = 20.07                                  # above the band
    assert "CONSTRAINT_VIOLATION" in _codes(qs, band)


# --- monotone diameter chain (stepped shaft) d1 >= d2 >= d3 --------------------

def test_monotone_diameter_chain():
    qs = [_decision("d1", 12.0), _decision("d2", 10.0), _decision("d3", 8.0)]
    chain = [
        Constraint(id="a", kind="ge", left="d1", right="d2", reason="step down"),
        Constraint(id="b", kind="ge", left="d2", right="d3", reason="step down"),
    ]
    assert _passes(qs, chain)
    qs[1].value = 7.0                                    # breaks monotonicity (d2 < d3)
    assert "CONSTRAINT_VIOLATION" in _codes(qs, chain)


# --- the anti-invention guarantee: the gate invents no fit/tolerance ----------

def test_gate_invents_no_tolerance():
    # a hole barely larger than a shaft, with NO declared clearance constraint.
    # GENESIS must not impose an ISO/industry tolerance the human did not state.
    qs = [_decision("hole", 4.001), _decision("shaft", 4.0)]
    assert _passes(qs, [])                                # nothing declared -> nothing checked


def test_grounded_shaft_diameter_drives_the_fit():
    # a fit anchored to a VERIFIED fact (M4 = 4 mm) plus a declared clearance
    claim = Claim(
        id="c_m4", text="An M4 screw has a nominal diameter of 4 mm.",
        sources=[SourceRef("https://s", True, support=SourceSupport.SUPPORTS)],
        status=ClaimStatus.VERIFIED, confidence=0.9,
        verification=[SourceRef("https://i", True, support=SourceSupport.SUPPORTS)],
    )
    shaft = Quantity(id="shaft", name="M4 shaft", value=4.0, unit="mm",
                     origin=ValueOrigin.GROUNDED, grounding=["c_m4"])
    qs = [_decision("hole", 4.5), shaft, _decision("clear", 0.2)]
    fit = [Constraint(id="k", kind="ge", left="hole", right="shaft + clear", reason="slip fit")]
    st = _state(qs, fit)
    st.claims = [claim]
    assert gate_gamma(st).passed
