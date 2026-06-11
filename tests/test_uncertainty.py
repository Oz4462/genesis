"""GATE γ C-18 — GUM uncertainty propagation, code computes / gate recomputes.

GENESIS otherwise treats values as exact. A real input carries an uncertainty;
for "every value is backed" to stay rigorous, that uncertainty must propagate. A
DERIVED quantity may declare a combined standard uncertainty, and GATE γ C-18
INDEPENDENTLY recomputes it from the inputs by the GUM law of propagation
(JCGM 100, first-order, uncorrelated) — the exact defense-in-depth of C-6, applied
to the uncertainty rather than the value.

Offline, no LLM, no network.

Run:  pytest tests/test_uncertainty.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.errors import InvalidDerivationError  # noqa: E402
from gen.core.state import (  # noqa: E402
    Derivation,
    Question,
    Quantity,
    RunState,
    Specification,
    ValueOrigin,
)
from gen.uncertainty import (  # noqa: E402
    combine_standard_uncertainty,
    expanded_uncertainty,
)
from gen.verification.gates import gate_gamma  # noqa: E402


# --- the propagation math (GUM eq. 10) -----------------------------------------

def test_sum_in_quadrature():
    # u_c(a + b) = sqrt(u_a^2 + u_b^2): 3, 4 -> 5
    u = combine_standard_uncertainty("a + b", {"a": 10.0, "b": 20.0}, {"a": 3.0, "b": 4.0})
    assert math.isclose(u, 5.0, rel_tol=1e-6)


def test_product_rule():
    # u_c(a*b) = sqrt((b u_a)^2 + (a u_b)^2)
    u = combine_standard_uncertainty("a * b", {"a": 3.0, "b": 4.0}, {"a": 0.1, "b": 0.2})
    assert math.isclose(u, math.sqrt((4 * 0.1) ** 2 + (3 * 0.2) ** 2), rel_tol=1e-6)


def test_exact_input_contributes_zero():
    # F = m*g with g exact: u_c = g * u_m
    u = combine_standard_uncertainty("m * g", {"m": 12.0, "g": 9.80665}, {"m": 0.5})
    assert math.isclose(u, 9.80665 * 0.5, rel_tol=1e-6)


def test_expanded_uncertainty_k2():
    assert expanded_uncertainty(1.1, k=2.0) == 2.2


# --- the gate recomputes a declared uncertainty (C-18) -------------------------

def _state(derived_uncertainty: float) -> RunState:
    """F = m*g, m = 12 +/- 0.5 (exact g), with a DECLARED uncertainty on F."""
    quantities = [
        Quantity(id="m", name="mass", value=12.0, unit="kg",
                 origin=ValueOrigin.DECISION, rationale="x", uncertainty=0.5),
        Quantity(id="g", name="gravity", value=9.80665, unit="m/s^2",
                 origin=ValueOrigin.DECISION, rationale="x"),
        Quantity(id="F", name="force", value=12.0 * 9.80665, unit="N",
                 origin=ValueOrigin.DERIVED,
                 derivation=Derivation(formula="m * g", inputs=("m", "g")),
                 uncertainty=derived_uncertainty),
    ]
    spec = Specification(run_id="r", idea="u", quantities=quantities)
    st = RunState(question=Question(raw="u", run_id="r"))
    st.specification = spec
    return st


def test_correct_declared_uncertainty_passes():
    correct = 9.80665 * 0.5
    result = gate_gamma(_state(correct))
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]


def test_wrong_declared_uncertainty_is_caught():
    # declare a too-small uncertainty -> the GUM recompute disagrees
    codes = {f.code for f in gate_gamma(_state(0.1)).failures}
    assert codes == {"BROKEN_UNCERTAINTY"}, codes


# --- end-to-end in the capstone ------------------------------------------------

def test_capstone_propagates_load_uncertainty_to_stress():
    from gen.demo import capstone_state
    st = capstone_state()
    assert gate_gamma(st).passed
    q = {x.id: x for x in st.specification.quantities}
    # the declared shelf-load uncertainty reaches the peak stress
    assert q["q_load"].uncertainty == 0.6
    assert q["q_sigma_peak"].uncertainty is not None and q["q_sigma_peak"].uncertainty > 0
    # and even the worst-case (value + U95) stays under the strength
    sp = q["q_sigma_peak"]
    assert sp.value + expanded_uncertainty(sp.uncertainty) < q["q_strength"].value


# --- the field must be honest --------------------------------------------------

def test_negative_uncertainty_rejected_at_construction():
    with pytest.raises(InvalidDerivationError):
        Quantity(id="q", name="q", value=1.0, unit="V",
                 origin=ValueOrigin.DECISION, rationale="x", uncertainty=-0.1)
