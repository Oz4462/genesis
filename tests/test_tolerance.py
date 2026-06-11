"""δ-tolerance: deterministic worst-case fit stack-up, with NO new gate code.

A nominal fit (hole 4.5 >= screw 4.0) can still fail once each dimension carries a
manufacturing tolerance. The worst-case stack-up asks: at the worst extreme
(largest screw, smallest hole), does the hole still admit the screw? It rides
entirely on existing γ machinery — the tolerances are quantities, the worst-case
clearance is a DERIVED quantity (recomputed by C-6, dimension-checked by C-15),
and ``min clearance >= 0`` is a numeric constraint (C-13).

The general tolerances come from a VERIFIED subset of the ISO 2768-1 class m
table; a nominal outside the verified range RAISES rather than guess a standard
value GENESIS has not checked.

Offline, no LLM, no network.

Run:  pytest tests/test_tolerance.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.errors import ToleranceError  # noqa: E402
from gen.core.state import (  # noqa: E402
    Constraint,
    Derivation,
    Question,
    Quantity,
    RunState,
    Specification,
    ValueOrigin,
)
from gen.tolerance import (  # noqa: E402
    iso2768_medium_linear_tolerance,
    worst_case_min_clearance_formula,
)
from gen.verification.derivation import evaluate_formula  # noqa: E402
from gen.verification.gates import gate_gamma  # noqa: E402


# --- the verified ISO 2768-1 m table -------------------------------------------

def test_iso2768_medium_table_values():
    assert iso2768_medium_linear_tolerance(0.5) == 0.1
    assert iso2768_medium_linear_tolerance(3.0) == 0.1
    assert iso2768_medium_linear_tolerance(4.5) == 0.1
    assert iso2768_medium_linear_tolerance(6.0) == 0.1   # boundary: <= 6 is still 0.1
    assert iso2768_medium_linear_tolerance(6.001) == 0.2  # just over 6 -> 0.2
    assert iso2768_medium_linear_tolerance(30.0) == 0.2
    assert iso2768_medium_linear_tolerance(60.0) == 0.3
    assert iso2768_medium_linear_tolerance(120.0) == 0.3


def test_iso2768_outside_verified_range_raises():
    with pytest.raises(ToleranceError):
        iso2768_medium_linear_tolerance(0.4)     # below the encoded table
    with pytest.raises(ToleranceError):
        iso2768_medium_linear_tolerance(150.0)   # above the verified subset


def test_worst_case_formula_is_exact():
    assert (
        worst_case_min_clearance_formula("q_hole_d", "q_hole_tol", "q_screw_d", "q_screw_tol")
        == "(q_hole_d - q_hole_tol) - (q_screw_d + q_screw_tol)"
    )


# --- the stack-up rides on existing machinery (gate-level) ---------------------

def _fit_state(*, hole: float, screw: float, tol: float = 0.1) -> RunState:
    """A minimal spec carrying only the worst-case clearance chain (DECISION
    dimensions, so no claims needed). The clearance is recomputed with the real
    evaluator, so the stored value cannot drift from the formula."""
    f = worst_case_min_clearance_formula("q_hole_d", "q_hole_tol", "q_screw_d", "q_screw_tol")
    binding = {"q_hole_d": hole, "q_hole_tol": tol, "q_screw_d": screw, "q_screw_tol": tol}
    clearance = evaluate_formula(f, binding)

    def _dec(qid, value):
        return Quantity(id=qid, name=qid, value=value, unit="mm",
                        origin=ValueOrigin.DECISION, rationale="declared")

    quantities = [
        _dec("q_hole_d", hole), _dec("q_screw_d", screw),
        _dec("q_hole_tol", tol), _dec("q_screw_tol", tol),
        Quantity(id="q_min_clearance", name="min clearance", value=clearance, unit="mm",
                 origin=ValueOrigin.DERIVED,
                 derivation=Derivation(formula=f,
                                       inputs=("q_hole_d", "q_hole_tol", "q_screw_d", "q_screw_tol"))),
    ]
    spec = Specification(
        run_id="r", idea="fit", quantities=quantities,
        constraints=[Constraint(id="k_assemble", kind="ge", left="q_min_clearance",
                                right="0", reason="worst-case clearance non-negative")],
    )
    st = RunState(question=Question(raw="fit", run_id="r"))
    st.specification = spec
    return st


def test_worst_case_fit_passes_with_clearance():
    # hole 4.5 +/-0.1 over screw 4.0 +/-0.1 -> min clearance 0.3 mm >= 0
    result = gate_gamma(_fit_state(hole=4.5, screw=4.0))
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]


def test_too_tight_fit_trips_constraint():
    # hole 4.1 +/-0.1 over screw 4.0 +/-0.1 -> min clearance -0.1 mm < 0:
    # the nominal fit (4.1 >= 4.0) looked fine, but the worst case interferes.
    codes = {f.code for f in gate_gamma(_fit_state(hole=4.1, screw=4.0)).failures}
    assert codes == {"CONSTRAINT_VIOLATION"}, codes


def test_capstone_fit_is_assemblable():
    from gen.demo import capstone_state
    st = capstone_state()
    q = {x.id: x for x in st.specification.quantities}
    assert q["q_min_clearance"].value > 0
    assert gate_gamma(st).passed
