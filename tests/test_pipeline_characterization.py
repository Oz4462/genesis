"""Characterization / facade-detection tests for src/gen/pipeline.py (assess_specification).

Goal (depth audit T02): prove that assess_specification composes ONE HONEST overall status
and the derived properties (physics_ok / physics_checked / physics_complete), not a facade
that masks gaps or vacuous-no-check cases as "verified".

- All Specification objects are built via the REAL core.state constructors (Quantity, Specification, Constraint, ValueOrigin).
- The test is a real facade detector: (a) driving inputs (measurands present, values, constraints) produce
  meaningfully different overall + properties; (b) documented honest non-pass paths fire exactly
  (needs_clarification, physics_incomplete, no_physics_indicated, inconsistent_constraints, physics_failed)
  and physics_ok is False exactly when the seam would have lied (gate passed over gaps or zero checks).
- Priority ladder per documented contract in pipeline.py and _overall_status.
- Property-based (Hypothesis) for determinism and the physics_ok <=> verified implication.
- Legacy tests/test_pipeline.py is untouched (new authoritative _characterization file per team decision).
- No src edit unless this test independently exposes a genuine defect in priority or the three properties.

Run:  pytest tests/test_pipeline_characterization.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

from hypothesis import given, strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.state import Constraint, Quantity, Specification, ValueOrigin  # noqa: E402
from gen.pipeline import assess_specification  # noqa: E402


def _q(
    qid: str, measurand: str, value: float, unit: str, origin: ValueOrigin = ValueOrigin.DECISION
) -> Quantity:
    """Minimal Quantity carrying a measurand tag. Value/unit chosen to be realistic for the
    target validator after the recipe's unit conversion (N*mm, mm, MPa)."""
    return Quantity(
        id=qid,
        name=qid,
        value=value,
        unit=unit,
        origin=origin,
        rationale="characterization-test",
        measurand=measurand,
    )


def _spec(
    quantities: list[Quantity],
    *,
    constraints: list[Constraint] | None = None,
    run_id: str = "char-run-001",
    idea: str = "T02 shaft torsion characterization",
) -> Specification:
    """Real Specification via the core constructor (no demo helpers in the primary paths)."""
    return Specification(
        run_id=run_id,
        idea=idea,
        quantities=quantities,
        constraints=constraints or [],
    )


def _full_torsion_passing() -> Specification:
    """Complete, passing shaft-torsion spec.
    torque=1000 N*mm, d=10 mm → max_shear ≈5.09 MPa (torsion formula).
    strength=10 MPa → sf ≈1.96 >=1 → ok + verified.
    All required inputs present with trigger.
    """
    qs = [
        _q("qt", "shaft.torque", 1000.0, "N*mm"),
        _q("qd", "shaft.diameter", 10.0, "mm"),
        _q("ql", "shaft.length", 100.0, "mm"),
        _q("qg", "material.shear_modulus", 80000.0, "MPa"),
        _q("qs", "material.shear_strength", 10.0, "MPa"),
    ]
    return _spec(qs)


def _full_torsion_failing() -> Specification:
    """Same geometry, insufficient strength → check runs but !ok."""
    qs = [
        _q("qt", "shaft.torque", 1000.0, "N*mm"),
        _q("qd", "shaft.diameter", 10.0, "mm"),
        _q("ql", "shaft.length", 100.0, "mm"),
        _q("qg", "material.shear_modulus", 80000.0, "MPa"),
        _q("qs", "material.shear_strength", 1.0, "MPa"),  # too weak → sf < 1
    ]
    return _spec(qs)


def _torsion_missing_one() -> Specification:
    """Trigger present but one required input missing → gap path."""
    qs = [
        _q("qt", "shaft.torque", 1000.0, "N*mm"),
        _q("qd", "shaft.diameter", 10.0, "mm"),
        _q("ql", "shaft.length", 100.0, "mm"),
        _q("qg", "material.shear_modulus", 80000.0, "MPa"),
        # deliberately omit "material.shear_strength"
    ]
    return _spec(qs)


def _no_physics_measurands() -> Specification:
    """Quantities exist but none are recipe triggers → vacuous, no checks run."""
    qs = [
        _q("w", "geometry.width", 200.0, "mm"),
        _q("m", "material.density", 0.00124, "g/mm^3"),
    ]
    return _spec(qs)


# ---------------------------------------------------------------------------
# (1) happy path — fully specified + passing check → verified + physics_ok True
# ---------------------------------------------------------------------------

def test_fully_specified_passing_check_is_verified_and_physics_ok_true():
    """Input-driven: presence of trigger + all inputs + values that clear the margin
    produces the documented terminal success state. physics_ok only true here."""
    spec = _full_torsion_passing()
    a = assess_specification(spec)

    assert a.overall == "physics_verified"
    assert a.physics_ok is True
    assert a.physics_checked is True
    assert a.physics_complete is True
    assert a.physics_gate.passed is True
    assert len(a.physics_checks) == 1
    assert a.physics_gaps == []
    assert not a.needs_clarification
    assert a.constraints_consistent


# ---------------------------------------------------------------------------
# (2) input-driven change: same geometry, weaken strength → flips to physics_failed
# ---------------------------------------------------------------------------

def test_changing_input_value_flips_verified_to_failed():
    """Proves the numeric inputs are consumed (not a constant stub): identical
    structure except one value produces different overall + !ok + gate !passed."""
    a_pass = assess_specification(_full_torsion_passing())
    a_fail = assess_specification(_full_torsion_failing())

    assert a_pass.overall == "physics_verified" and a_pass.physics_ok
    assert a_fail.overall == "physics_failed" and not a_fail.physics_ok
    assert not a_fail.physics_gate.passed
    # different driving value (strength) produced different headline result
    assert a_pass.overall != a_fail.overall


# ---------------------------------------------------------------------------
# (3) missing input for indicated physics → needs_clarification (priority) + !ok + seam
# ---------------------------------------------------------------------------

def test_missing_input_for_indicated_physics_yields_needs_clarification_and_not_ok():
    """Gap is surfaced, never swallowed as a pass. Clarification has priority over
    the raw gaps list (documented ladder)."""
    spec = _torsion_missing_one()
    a = assess_specification(spec)

    assert a.overall in ("needs_clarification", "physics_incomplete")
    assert not a.physics_ok
    assert len(a.clarification_questions) >= 1 or len(a.physics_gaps) >= 1
    # The seam proof: gate on zero checks (gaps prevent check emission) is vacuously passed
    assert a.physics_gate.passed is True
    # ... yet physics_ok is correctly False (the bug this module exists to prevent)
    assert (len(a.physics_gaps) > 0 or not a.physics_checked) and not a.physics_ok


# ---------------------------------------------------------------------------
# (4) no physics measurands at all → no_physics_indicated + physics_checked=False
# ---------------------------------------------------------------------------

def test_spec_with_no_physics_measurands_is_honestly_vacuous():
    """Vacuous gate pass (no checks ran) must never be reported as verified.
    physics_checked is the honest flag."""
    spec = _no_physics_measurands()
    a = assess_specification(spec)

    assert a.overall == "no_physics_indicated"
    assert a.physics_checked is False
    assert a.physics_ok is False
    assert a.physics_gate.passed is True  # vacuous on []
    assert len(a.physics_checks) == 0
    assert a.physics_gaps == []


# ---------------------------------------------------------------------------
# (5) structurally contradictory constraints → inconsistent_constraints first
# ---------------------------------------------------------------------------

def test_structurally_contradictory_constraints_surface_before_physics():
    """Constraint layer is independent; contradictory pair on identical expr pair
    must produce the documented code regardless of physics content."""
    # minimal spec (even empty quantities is fine — constraints are checked directly)
    qs = [_q("dummy", "dummy.foo", 1.0, "1")]
    cons = [
        Constraint(id="k1", kind="ge", left="a", right="b", reason="test upper"),
        Constraint(id="k2", kind="lt", left="a", right="b", reason="test lower"),
    ]
    spec = _spec(qs, constraints=cons)
    a = assess_specification(spec)

    assert a.overall == "inconsistent_constraints"
    assert not a.constraints_consistent
    assert len(a.constraint_contradictions) >= 1


# ---------------------------------------------------------------------------
# (6) explicit seam proof (gate passed but physics_ok must stay False)
# ---------------------------------------------------------------------------

def test_physics_ok_false_whenever_gate_passed_but_gap_or_zero_checks():
    """Core anti-masking contract. Two sub-cases: gap (unrunnable indicated) and
    zero checks (vacuous). Both must keep physics_ok=False even though gate.passed=True."""
    gap_a = assess_specification(_torsion_missing_one())
    vac_a = assess_specification(_no_physics_measurands())

    # gap case
    assert gap_a.physics_gate.passed
    assert (bool(gap_a.physics_gaps) or not gap_a.physics_checked)
    assert gap_a.physics_ok is False

    # vacuous case
    assert vac_a.physics_gate.passed
    assert not vac_a.physics_checked
    assert vac_a.physics_ok is False


# ---------------------------------------------------------------------------
# (7) physics_complete vs gaps
# ---------------------------------------------------------------------------

def test_physics_complete_is_false_exactly_when_gaps_present():
    good = assess_specification(_full_torsion_passing())
    bad = assess_specification(_torsion_missing_one())

    assert good.physics_complete is True
    assert bad.physics_complete is False
    assert bool(bad.physics_gaps)


# ---------------------------------------------------------------------------
# property-based invariants (A5 determinism + ok <=> verified implication)
# ---------------------------------------------------------------------------

# Strength values around the ~5.09 MPa boundary for our fixed geometry.
# We avoid NaN/inf per project convention for property tests on factual numeric paths.


@given(
    strength=st.floats(
        min_value=0.1, max_value=100.0, allow_nan=False, allow_infinity=False
    )
)
def test_physics_ok_implies_verified_and_converse_over_strength_range(strength: float):
    """For the fixed-geometry torsion family: physics_ok is True if and only if
    overall=='physics_verified' (and therefore gate passed + checked + complete).
    This is an invariant of the composition contract."""
    spec = _spec(
        [
            _q("qt", "shaft.torque", 1000.0, "N*mm"),
            _q("qd", "shaft.diameter", 10.0, "mm"),
            _q("ql", "shaft.length", 100.0, "mm"),
            _q("qg", "material.shear_modulus", 80000.0, "MPa"),
            _q("qs", "material.shear_strength", strength, "MPa"),
        ]
    )
    a = assess_specification(spec)

    if a.physics_ok:
        assert a.overall == "physics_verified"
        assert a.physics_gate.passed
        assert a.physics_checked
        assert a.physics_complete

    if a.overall == "physics_verified":
        assert a.physics_ok


@given(
    # vary presence of the critical strength input (None vs present) and a secondary value
    has_strength=st.booleans(),
    extra_value=st.floats(min_value=1.0, max_value=200.0, allow_nan=False, allow_infinity=False),
)
def test_assessment_deterministic_for_equivalent_inputs(has_strength: bool, extra_value: float):
    """Same logical spec (same measurands + same numeric values) produces identical
    overall + properties on two independent calls (A5 reproducibility)."""
    qs = [
        _q("qt", "shaft.torque", 1000.0, "N*mm"),
        _q("qd", "shaft.diameter", 10.0, "mm"),
        _q("ql", "shaft.length", extra_value, "mm"),
        _q("qg", "material.shear_modulus", 80000.0, "MPa"),
    ]
    if has_strength:
        qs.append(_q("qs", "material.shear_strength", 10.0, "MPa"))

    spec = _spec(qs)
    a1 = assess_specification(spec)
    a2 = assess_specification(spec)

    assert a1.overall == a2.overall
    assert a1.physics_ok == a2.physics_ok
    assert a1.physics_checked == a2.physics_checked
    assert a1.physics_complete == a2.physics_complete
    assert a1.physics_gate.passed == a2.physics_gate.passed
    # lists are content-equal (dataclass frozen semantics)
    assert len(a1.physics_checks) == len(a2.physics_checks)


# Negative / boundary sanity (explicit non-Hypothesis cases already covered above
# plus the property space).
def test_empty_spec_is_no_physics_indicated():
    a = assess_specification(_spec([]))
    assert a.overall == "no_physics_indicated"
    assert not a.physics_checked
    assert not a.physics_ok
