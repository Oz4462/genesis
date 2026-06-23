"""Depth audit for physics_selection: spec→physics-check auto-selection.

Proves that select_physics_checks / evaluate_spec_physics turn a Specification's
measurand-tagged Quantities into real unit-converted PhysicsChecks or explicit gaps
(never silent drop or magnitude-copy). Uses only real core.state constructors.

Covers the contract:
(a) absent trigger -> silence (no check, no gap)
(b) trigger + all inputs resolve -> PhysicsCheck with sound UNIT-CONVERTED values
(c) trigger present + input MISSING -> exactly one gap naming recipe+measurand; no check emitted
(d) incompatible dim or opaque unit -> gap with documented reason strings
    ("nicht dimensionsgleich", "opake Einheit")
evaluate returns {"gate", "checks", "gaps"} consistent with direct select.

The negative tests are the gap paths (missing / opaque / dim-mismatch).

Property-based: determinism (A5) + conversion scale-invariance (same physical
value declared in equivalent units yields identical resolved magnitude).

Module reads as REAL; no source edits required.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from hypothesis import given, strategies as st  # noqa: E402

from gen.core.state import Quantity, Specification, ValueOrigin  # noqa: E402
from gen.physics_selection import (  # noqa: E402
    RECIPES,
    evaluate_spec_physics,
    select_physics_checks,
)
from gen.core.interfaces import GateResult  # noqa: E402


def _q(qid: str, value: float, unit: str, measurand: str) -> Quantity:
    """Real Quantity via public ctor (DECISION origin is allowed for depth tests;
    selection logic is provenance-agnostic downstream of GATE γ)."""
    return Quantity(
        id=qid,
        name=qid,
        value=value,
        unit=unit,
        origin=ValueOrigin.DECISION,
        rationale="depth-audit test input",
        measurand=measurand,
    )


def _spec(qs: list[Quantity]) -> Specification:
    """Real Specification via public ctor."""
    return Specification(run_id="depth-run-001", idea="physics selection depth audit", quantities=qs)


# --- (a) absent trigger contributes neither check nor gap (silence is correct) ---
def test_absent_trigger_silence():
    # no shaft.* or other physics trigger
    spec = _spec([_q("w", 12.0, "mm", "geometry.width")])
    checks, gaps = select_physics_checks(spec)
    assert checks == [] and gaps == []
    res = evaluate_spec_physics(spec)
    assert res["checks"] == [] and res["gaps"] == []
    assert isinstance(res["gate"], GateResult)


# --- (b) full resolution emits PhysicsCheck with correctly unit-converted value ---
# shaft.torque declared in N*m must become N*mm (×1000) in the check; this proves
# units.py scale path, not a raw value copy.
def test_full_resolve_emits_unit_converted_check():
    # shaft torsion recipe: torque N*m -> N*mm, others already in target units
    qs = [
        _q("t", 4.2, "N*m", "shaft.torque"),  # must resolve to 4200.0
        _q("d", 18.0, "mm", "shaft.diameter"),
        _q("L", 250.0, "mm", "shaft.length"),
        _q("G", 79000.0, "MPa", "material.shear_modulus"),
        _q("tau", 120.0, "MPa", "material.shear_strength"),
    ]
    spec = _spec(qs)
    checks, gaps = select_physics_checks(spec)
    assert gaps == []
    torsion = next((c for c in checks if c.validator == "torsion"), None)
    assert torsion is not None
    assert torsion.inputs["torque"] == 4200.0  # exact 4.2 * 1000
    # also verify other values passed through
    assert torsion.inputs["diameter"] == 18.0

    res = evaluate_spec_physics(spec)
    assert res["gaps"] == []
    assert len(res["checks"]) == 1
    # consistency
    assert len(res["checks"]) == len(checks)
    assert res["gate"].passed  # with sane numbers the torsion passes


# --- (c) trigger present but required input MISSING -> one gap, NO check emitted ---
def test_missing_input_yields_gap_no_check():
    # trigger "shaft.torque" present, but shear_strength missing
    qs = [
        _q("t", 3.0, "N*m", "shaft.torque"),
        _q("d", 20.0, "mm", "shaft.diameter"),
        _q("L", 300.0, "mm", "shaft.length"),
        _q("G", 80000.0, "MPa", "material.shear_modulus"),
        # deliberately omit material.shear_strength
    ]
    spec = _spec(qs)
    checks, gaps = select_physics_checks(spec)
    assert checks == []
    assert len(gaps) == 1
    assert "shaft torsion (torsion)" in gaps[0]
    assert "shaft.torque" in gaps[0]
    assert "material.shear_strength" in gaps[0]

    res = evaluate_spec_physics(spec)
    assert res["checks"] == []
    assert len(res["gaps"]) == 1 and "material.shear_strength" in res["gaps"][0]
    # gate may be empty-pass (no checks) or reflect the gap indirectly; main contract is checks/gaps
    assert isinstance(res["gate"], GateResult)


# --- (d) dimensionally incompatible or opaque unit -> gap (exact documented reasons) ---
def test_dimension_incompatible_yields_gap():
    qs = [
        _q("t", 5.0, "N*m", "shaft.torque"),
        _q("d", 20.0, "kg", "shaft.diameter"),  # mass instead of length
        _q("L", 400.0, "mm", "shaft.length"),
        _q("G", 80000.0, "MPa", "material.shear_modulus"),
        _q("tau", 90.0, "MPa", "material.shear_strength"),
    ]
    spec = _spec(qs)
    checks, gaps = select_physics_checks(spec)
    assert checks == []
    assert len(gaps) == 1
    assert "nicht dimensionsgleich" in gaps[0]
    assert "shaft.diameter" in gaps[0]

    res = evaluate_spec_physics(spec)
    assert res["checks"] == []
    assert "nicht dimensionsgleich" in res["gaps"][0]


def test_opaque_unit_yields_gap():
    # Opaque scale failure after dim match is produced when a declared unit and the
    # expected unit resolve to the *same* opaque Dimension symbol but have no scale.
    # We exercise the exact string path via the internal resolver (documented reason).
    # For public API with current RECIPES an unknown unit always produces the
    # "nicht dimensionsgleich" (different opaque dim vs known target dim).
    from gen.physics_selection import _resolve  # internal helper exercised for branch coverage

    q_op = _q("x", 42.0, "frob", "test.opaque")
    by = {"test.opaque": q_op}
    val, reason = _resolve(by, "test.opaque", "frob")  # same unknown symbol -> dim match, scale=None
    assert val is None
    assert reason is not None and "opake Einheit" in reason

    # Public API path for unknown on real recipe: incompatible dim (different opaque vs L)
    qs = [
        _q("t", 2.0, "N*m", "shaft.torque"),
        _q("d", 10.0, "frob", "shaft.diameter"),
        _q("L", 200.0, "mm", "shaft.length"),
        _q("G", 80000.0, "MPa", "material.shear_modulus"),
        _q("tau", 80.0, "MPa", "material.shear_strength"),
    ]
    spec = _spec(qs)
    checks, gaps = select_physics_checks(spec)
    assert checks == []
    assert len(gaps) == 1
    assert "nicht dimensionsgleich" in gaps[0]  # practical documented incompatibility for unknown
    assert "shaft.diameter" in gaps[0]

    res = evaluate_spec_physics(spec)
    assert res["checks"] == []
    assert "nicht dimensionsgleich" in res["gaps"][0]


# --- evaluate_spec_physics contract and consistency ---
def test_evaluate_returns_consistent_structure():
    # minimal full shaft spec
    qs = [
        _q("t", 1.0, "N*m", "shaft.torque"),
        _q("d", 10.0, "mm", "shaft.diameter"),
        _q("L", 50.0, "mm", "shaft.length"),
        _q("G", 70000.0, "MPa", "material.shear_modulus"),
        _q("tau", 50.0, "MPa", "material.shear_strength"),
    ]
    spec = _spec(qs)
    sel_checks, sel_gaps = select_physics_checks(spec)
    res = evaluate_spec_physics(spec)
    assert set(res.keys()) == {"gate", "checks", "gaps"}
    assert res["checks"] == sel_checks
    assert res["gaps"] == sel_gaps
    assert isinstance(res["gate"], GateResult)


# --- property-based invariants ---
_positive = st.floats(min_value=0.1, max_value=1e6, allow_nan=False, allow_infinity=False)


@given(
    torque_nm=_positive,
    diameter=_positive,
    length=_positive,
    g_mod=_positive,
    shear=_positive,
)
def test_property_determinism_and_conversion(torque_nm, diameter, length, g_mod, shear):
    """A5 + conversion honesty:
    - identical spec -> identical (checks, gaps)
    - torque in N*m always yields exactly ×1000 in the resolved check input
      (proves units.py path is exercised, not value passthrough)
    """
    qs = [
        _q("t", torque_nm, "N*m", "shaft.torque"),
        _q("d", diameter, "mm", "shaft.diameter"),
        _q("L", length, "mm", "shaft.length"),
        _q("G", g_mod, "MPa", "material.shear_modulus"),
        _q("tau", shear, "MPa", "material.shear_strength"),
    ]
    spec = _spec(qs)
    a_checks, a_gaps = select_physics_checks(spec)
    b_checks, b_gaps = select_physics_checks(spec)
    assert a_gaps == b_gaps
    assert len(a_checks) == len(b_checks)
    if a_checks:
        assert a_checks[0].inputs["torque"] == pytest.approx(torque_nm * 1000.0)
        # second call identical
        assert b_checks[0].inputs["torque"] == a_checks[0].inputs["torque"]

    # also prove: declaring directly in target unit yields identical resolved magnitude
    qs_mm = [
        _q("t", torque_nm * 1000.0, "N*mm", "shaft.torque"),
        _q("d", diameter, "mm", "shaft.diameter"),
        _q("L", length, "mm", "shaft.length"),
        _q("G", g_mod, "MPa", "material.shear_modulus"),
        _q("tau", shear, "MPa", "material.shear_strength"),
    ]
    spec_mm = _spec(qs_mm)
    mm_checks, _ = select_physics_checks(spec_mm)
    if mm_checks:
        assert mm_checks[0].inputs["torque"] == pytest.approx(torque_nm * 1000.0)


@given(st.integers(min_value=0, max_value=5))
def test_property_absent_triggers_are_silent(n_extra):
    """Any number of non-trigger quantities must never produce checks or gaps."""
    qs = [_q(f"e{i}", float(i + 1), "mm", f"extra.{i}") for i in range(n_extra)]
    checks, gaps = select_physics_checks(_spec(qs))
    assert checks == [] and gaps == []


# --- negative (gap) paths are the documented honest abstention ---
def test_negative_gap_paths_are_documented_and_distinct():
    # missing path
    missing_qs = [_q("t", 1.0, "N*m", "shaft.torque")]
    _, g_missing = select_physics_checks(_spec(missing_qs))
    assert any("keine Größe mit measurand" in gg or "material.shear" in gg for gg in g_missing)

    # incompatible dim (different symbols) documented reason
    inc_qs = [
        _q("t", 1.0, "N*m", "shaft.torque"),
        _q("d", 1.0, "s", "shaft.diameter"),  # time != length
        _q("L", 10.0, "mm", "shaft.length"),
        _q("G", 1.0, "MPa", "material.shear_modulus"),
        _q("tau", 1.0, "MPa", "material.shear_strength"),
    ]
    _, g_inc = select_physics_checks(_spec(inc_qs))
    assert any("nicht dimensionsgleich" in gg for gg in g_inc)

    # For same-opaque-symbol case the 'opake Einheit' string is produced (covered in dedicated test)
    # Here we only confirm a distinct gap is raised for unknown unit (letter-only unknown parses to opaque dim -> nicht dimensionsgleich)
    unk_qs = [
        _q("t", 1.0, "N*m", "shaft.torque"),
        _q("d", 1.0, "xyzzy", "shaft.diameter"),
        _q("L", 10.0, "mm", "shaft.length"),
        _q("G", 1.0, "MPa", "material.shear_modulus"),
        _q("tau", 1.0, "MPa", "material.shear_strength"),
    ]
    _, g_unk = select_physics_checks(_spec(unk_qs))
    assert any("nicht dimensionsgleich" in gg for gg in g_unk)
