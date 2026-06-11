"""Tests for the safe derivation evaluator — the only place DERIVED values come
from (PHASE_GAMMA.md §3.2). No LLM, no network: pure arithmetic, loud failure.

The contract under test: anything outside the tiny grammar (numbers, declared
input names, + - * /, unary minus, parentheses) raises FormulaError; topological
resolution computes chains, names cycles, and never silently guesses a value.

Run:  pytest tests/test_derivation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make src importable without packaging during early dev.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.errors import FormulaError  # noqa: E402
from gen.core.state import Derivation  # noqa: E402
from gen.verification.derivation import (  # noqa: E402
    evaluate_formula,
    topological_values,
    within_tolerance,
)


# --- evaluate_formula: the grammar -------------------------------------------

def test_basic_arithmetic_and_precedence():
    assert evaluate_formula("a + b * 2", {"a": 1.0, "b": 3.0}) == 7.0
    assert evaluate_formula("(a + b) * 2", {"a": 1.0, "b": 3.0}) == 8.0
    assert evaluate_formula("a / b - 1", {"a": 9.0, "b": 3.0}) == 2.0
    assert evaluate_formula("-a + +b", {"a": 2.0, "b": 5.0}) == 3.0


def test_unknown_input_fails_loudly():
    with pytest.raises(FormulaError):
        evaluate_formula("a + ghost", {"a": 1.0})


def test_division_by_zero_fails_loudly():
    with pytest.raises(FormulaError):
        evaluate_formula("a / b", {"a": 1.0, "b": 0.0})


@pytest.mark.parametrize(
    "formula",
    [
        "a ** 2",                  # power not in the grammar
        "__import__('os')",        # calls are disallowed syntax
        "a if b else 0",           # conditionals
        "a < b",                   # comparisons
        "[1, 2]",                  # containers
        "a.real",                  # attribute access
        "'text'",                  # non-numeric constant
        "True",                    # bools are not numbers
        "1 +",                     # not parseable
    ],
)
def test_everything_outside_the_grammar_fails(formula):
    with pytest.raises(FormulaError):
        evaluate_formula(formula, {"a": 1.0, "b": 2.0})


# --- topological_values: chains, cycles, honesty ------------------------------

def test_chain_resolves_in_dependency_order():
    values, errors = topological_values(
        known={"q_load": 12.0, "q_sf": 2.0},
        derived={
            # listed out of order on purpose: q_total needs q_design first
            "q_total": Derivation(formula="q_design + q_load", inputs=("q_design", "q_load")),
            "q_design": Derivation(formula="q_load * q_sf", inputs=("q_load", "q_sf")),
        },
    )
    assert errors == {}
    assert values["q_design"] == 24.0
    assert values["q_total"] == 36.0


def test_cycle_is_named_not_guessed():
    values, errors = topological_values(
        known={},
        derived={
            "a": Derivation(formula="b + 1", inputs=("b",)),
            "b": Derivation(formula="a + 1", inputs=("a",)),
        },
    )
    assert "a" in errors and "b" in errors
    assert "a" not in values and "b" not in values  # never a silent value


def test_unknown_input_is_an_error_for_that_item_only():
    values, errors = topological_values(
        known={"x": 1.0},
        derived={
            "ok": Derivation(formula="x * 2", inputs=("x",)),
            "bad": Derivation(formula="ghost + 1", inputs=("ghost",)),
        },
    )
    assert values["ok"] == 2.0
    assert "bad" in errors and "ghost" in errors["bad"]


def test_failed_dependency_cascades_honestly():
    values, errors = topological_values(
        known={},
        derived={
            "bad": Derivation(formula="ghost", inputs=("ghost",)),
            "child": Derivation(formula="bad * 2", inputs=("bad",)),
        },
    )
    assert "bad" in errors
    assert "child" in errors and "bad" in errors["child"]
    assert "child" not in values


def test_undeclared_name_in_formula_is_drift():
    # The formula references q2, but only q1 was declared as input: the binding
    # is restricted to declared inputs, so this must fail even though q2 exists.
    values, errors = topological_values(
        known={"q1": 1.0, "q2": 2.0},
        derived={"d": Derivation(formula="q1 + q2", inputs=("q1",))},
    )
    assert "d" in errors
    assert "d" not in values  # never a silent value


def test_within_tolerance_is_relative():
    assert within_tolerance(1e9, 1e9 + 0.5, tolerance=1e-9)
    assert not within_tolerance(1.0, 1.1, tolerance=1e-9)


# --- min/max: the only permitted calls ----------------------------------------

def test_min_max_evaluate():
    assert evaluate_formula("max(2, 0.1 * w)", {"w": 60.0}) == 6.0
    assert evaluate_formula("max(2, 0.1 * w)", {"w": 10.0}) == 2.0   # floor wins
    assert evaluate_formula("min(a, b, c)", {"a": 5.0, "b": 3.0, "c": 9.0}) == 3.0


def test_other_calls_still_rejected():
    # the min/max allowance must NOT open the door to arbitrary calls
    for bad in ("__import__('os')", "open('x')", "abs(a)", "pow(a, 2)", "a.bit_length()"):
        with pytest.raises(FormulaError):
            evaluate_formula(bad, {"a": 1.0})


def test_min_max_referenced_names():
    from gen.verification.derivation import referenced_names
    assert referenced_names("max(q_floor, 0.1 * q_w)") == {"q_floor", "q_w"}
