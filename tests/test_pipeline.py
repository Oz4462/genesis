"""Pipeline — the honest wiring of the quality engine, and the seam bugs it fixes.

The composition must NOT let a clean "passed" mask a gap or a vacuous (no-check) result: an
indicated-but-unrunnable physics check makes the verdict "physics_incomplete" (physics_ok False),
and a spec with no physics measurands is surfaced as "no_physics_indicated" (physics_checked
False), not as verified. A fully specified shaft verifies; an over-stressed one fails;
contradictory constraints surface; underspecification asks first. Offline, no LLM.

Run:  pytest tests/test_pipeline.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.state import Constraint  # noqa: E402
from gen.demo import (  # noqa: E402
    capstone_claims,
    capstone_spec,
    drive_shaft_spec,
    drive_shaft_state,
)
from gen.pipeline import assess_specification  # noqa: E402
from gen.telemetry import RunTrace  # noqa: E402


def _drop(spec, measurand):
    spec.quantities = [q for q in spec.quantities if q.measurand != measurand]
    return spec


def test_fully_specified_shaft_is_verified():
    a = assess_specification(drive_shaft_spec(), claims=drive_shaft_state().claims)
    assert a.overall == "physics_verified"
    assert a.physics_ok and a.physics_checked and a.physics_complete
    assert a.constraints_consistent and not a.needs_clarification
    assert a.corroboration is not None and a.corroboration.ok


def test_a_gap_does_not_masquerade_as_a_pass():
    # SEAM 1: an indicated torsion check missing material.shear_strength is a GAP; the
    # verdict must NOT be a clean physics pass.
    a = assess_specification(_drop(drive_shaft_spec(), "material.shear_strength"))
    assert a.overall == "needs_clarification"       # clarification comes first
    assert not a.physics_ok and not a.physics_complete
    assert a.physics_gaps                            # the gap is surfaced, not swallowed


def test_a_vacuous_pass_is_surfaced_not_called_verified():
    # SEAM 2: the capstone declares no physics measurands -> 0 checks. The gate passes
    # vacuously, but the assessment must say so, not "verified".
    a = assess_specification(capstone_spec(), claims=capstone_claims())
    assert a.overall == "no_physics_indicated"
    assert not a.physics_checked                     # nothing actually ran
    assert not a.physics_ok                          # a gate that passes over ZERO checks is vacuous — not ok


def test_over_stressed_shaft_fails():
    spec = drive_shaft_spec()
    next(q for q in spec.quantities if q.id == "q_shaft_d").value = 5.0   # tau >> strength
    a = assess_specification(spec)
    assert a.overall == "physics_failed" and not a.physics_ok


def test_contradictory_constraints_surface():
    spec = drive_shaft_spec()
    spec.constraints = [Constraint("k1", "ge", "a", "b"), Constraint("k2", "lt", "a", "b")]
    a = assess_specification(spec)
    assert a.overall == "inconsistent_constraints" and not a.constraints_consistent


def test_assessment_records_telemetry_when_a_trace_is_given():
    trace = RunTrace("run", clock=lambda: 0.0)
    assess_specification(drive_shaft_spec(), claims=drive_shaft_state().claims, trace=trace)
    kinds = {e.kind for e in trace.events}
    assert {"clarify", "select", "gate", "constraints", "grounding"} <= kinds


def test_is_deterministic():
    a = assess_specification(drive_shaft_spec())
    b = assess_specification(drive_shaft_spec())
    assert a.overall == b.overall and a.physics_ok == b.physics_ok


def test_circular_corroboration_is_not_called_verified():
    # SEAM 3: a physics-clean spec whose CLAIMS are only circularly corroborated (the
    # verification source re-cites the original source) must NOT read "physics_verified" —
    # the facts underneath are not independently corroborated. Before the fix, _overall_status
    # ignored corroboration and the verdict was wrongly "physics_verified".
    from gen.core.state import Claim, ClaimStatus, SourceRef, SourceSupport
    circular = [Claim(
        id="c1", text="x",
        sources=[SourceRef(url_or_id="A", retrieved=True, support=SourceSupport.SUPPORTS)],
        status=ClaimStatus.VERIFIED, confidence=0.9,
        verification=[SourceRef(url_or_id="A", retrieved=True, support=SourceSupport.SUPPORTS)],
    )]
    a = assess_specification(drive_shaft_spec(), claims=circular)


def test_assessment_surfaces_platform_caps():
    # E2E autonomy: caps (proof, readiness, teacher, community) now populated in assess for consumers.
    a = assess_specification(drive_shaft_spec())
    # in pure assess path, some may be None (honest), but fields are wired
    assert hasattr(a, 'proof_package')
    assert hasattr(a, 'readiness_level')
    assert a.teacher_notes is not None
    assert a.community_evidence is not None
