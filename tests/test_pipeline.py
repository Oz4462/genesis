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
    # With epsilon seams (cost rollup from BOM), if no seam_certificate supplied the
    # honest top-level is "seams_failed" (required coupling not certified). Physics
    # vacuous status is still visible via properties.
    a = assess_specification(capstone_spec(), claims=capstone_claims())
    # Overall may be seams_failed (cost obligations) or no_physics_indicated depending on cert.
    # The key honesty property: not physics_verified.
    assert a.overall in ("no_physics_indicated", "seams_failed")
    assert not a.physics_checked or a.overall == "seams_failed"
    assert not a.physics_ok                          # never a fake verified pass


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
    assert a.corroboration is not None and not a.corroboration.ok
    assert a.physics_ok                               # the PHYSICS is clean...
    assert a.overall == "grounding_failed"            # ...but the grounding failure overrides the headline


# --- geometry cross-check wiring (D15: geometry_verification -> assess) ----------

def _fake_kernel_available(monkeypatch):
    # simulate an installed cadquery without needing the real OCCT kernel: the
    # availability probe (`import cadquery`) succeeds, and the BREP build is
    # stubbed with a solid derived from the ANALYTIC layer (so a consistent
    # geometry verifies, and a divergence is injectable).
    import types
    monkeypatch.setitem(sys.modules, "cadquery", types.ModuleType("cadquery"))


class _StubBB:
    def __init__(self, ex, ey, ez):
        self.xmin, self.xmax = -ex / 2.0, ex / 2.0
        self.ymin, self.ymax = -ey / 2.0, ey / 2.0
        self.zmin, self.zmax = -ez / 2.0, ez / 2.0


class _StubSolid:
    def __init__(self, volume, extent):
        self._volume, self._extent = volume, extent

    def isValid(self):  # noqa: N802 - cadquery API name
        return True

    def Volume(self):  # noqa: N802 - cadquery API name
        return self._volume

    def BoundingBox(self):  # noqa: N802 - cadquery API name
        return _StubBB(*self._extent)


def _stub_brep(monkeypatch, volume_scale=1.0):
    import gen.geometry_verification as gv
    from gen.verification.geometry import aabb_of, volume_of

    def build(node, quantities):
        return _StubSolid(volume_scale * volume_of(node, quantities).value,
                          aabb_of(node, quantities).extent)

    monkeypatch.setattr(gv, "csg_to_solid", build)


def test_geometry_cross_check_runs_and_verifies_when_the_kernel_is_available(monkeypatch):
    _fake_kernel_available(monkeypatch)
    _stub_brep(monkeypatch)                          # BREP consistent with the spec
    trace = RunTrace("run", clock=lambda: 0.0)
    a = assess_specification(capstone_spec(), claims=capstone_claims(), trace=trace)
    assert a.geometry_status == "verified" and a.geometry_ok
    assert a.geometry_checks and all(r["ok"] for r in a.geometry_checks)
    assert a.overall in ("no_physics_indicated", "seams_failed")   # headline unchanged
    assert "geometry" in {e.kind for e in trace.events}


def test_a_geometry_divergence_is_a_blocker(monkeypatch):
    # NEGATIVTEST: the built solid has HALF the declared volume (hemisphere-class)
    _fake_kernel_available(monkeypatch)
    _stub_brep(monkeypatch, volume_scale=0.5)
    a = assess_specification(capstone_spec(), claims=capstone_claims())
    assert a.geometry_status == "failed" and not a.geometry_ok
    assert a.overall == "geometry_failed"            # flows into the honest verdict


def test_missing_cad_kernel_is_an_honest_skip_not_a_pass(monkeypatch):
    monkeypatch.setitem(sys.modules, "cadquery", None)   # import cadquery -> ImportError
    a = assess_specification(capstone_spec(), claims=capstone_claims())
    assert a.geometry_status == "unavailable"
    assert not a.geometry_ok                          # surfaced, never a silent pass...
    assert a.overall != "geometry_failed"             # ...but not a fail either


def test_a_spec_without_geometry_is_vacuous_no_geometry():
    a = assess_specification(drive_shaft_spec(), claims=drive_shaft_state().claims)
    assert a.geometry_status == "no_geometry" and not a.geometry_ok
    assert a.overall == "physics_verified"            # vacuous case does not block
