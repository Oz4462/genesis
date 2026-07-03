"""Phase delta+ coverage proof — undeclared failure modes + completeness certificate.

The gate is deterministic and LLM-free. It proves that every failure mode indicated by
declared measurands or constraints is present in the certificate and is either CHECKED
with evidence or explicitly UNTESTABLE with residual risk.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.errors import UngroundedFailureModeError, UncoveredFailureModeError  # noqa: E402
from gen.core.state import (  # noqa: E402
    Constraint,
    CoverageCertificate,
    CoverageStatus,
    FailureMode,
    FailureModeCoverage,
    Quantity,
    Specification,
    ValueOrigin,
)
from gen.coverage import (  # noqa: E402
    build_coverage_certificate,
    coverage_requirements,
    gate_delta_plus_coverage,
)


def _q(qid: str, value: float, unit: str, measurand: str) -> Quantity:
    return Quantity(
        id=qid,
        name=qid,
        value=value,
        unit=unit,
        origin=ValueOrigin.DECISION,
        rationale="declared design input",
        measurand=measurand,
    )


def _shaft_spec(*, complete: bool = True) -> Specification:
    quantities = [
        _q("t", 5.0, "N*m", "shaft.torque"),
        _q("d", 20.0, "mm", "shaft.diameter"),
        _q("L", 1000.0, "mm", "shaft.length"),
        _q("G", 80000.0, "MPa", "material.shear_modulus"),
    ]
    if complete:
        quantities.append(_q("tau", 100.0, "MPa", "material.shear_strength"))
    return Specification(run_id="r-cover", idea="covered shaft", quantities=quantities)


def test_structural_guards_reject_groundless_or_evidenceless_coverage():
    with pytest.raises(UngroundedFailureModeError):
        FailureMode(id="fm0", label="invented mode", source="test", grounding=[])
    with pytest.raises(UncoveredFailureModeError):
        FailureModeCoverage(mode_id="fm1", status=CoverageStatus.CHECKED, evidence=[])
    with pytest.raises(UncoveredFailureModeError):
        FailureModeCoverage(mode_id="fm1", status=CoverageStatus.UNTESTABLE, residual_risk="")


def test_builder_certificate_passes_for_runnable_physics_mode():
    spec = _shaft_spec()
    cert = build_coverage_certificate(spec)
    assert [c.status for c in cert.coverage] == [CoverageStatus.CHECKED]
    res = gate_delta_plus_coverage(spec, cert)
    assert res.passed, res.failures


def test_undeclared_failure_mode_fails():
    spec = _shaft_spec()
    cert = build_coverage_certificate(spec)
    missing = cert.failure_modes[0].id
    bad = CoverageCertificate(
        spec_run_id=spec.run_id,
        failure_modes=[m for m in cert.failure_modes if m.id != missing],
        coverage=[c for c in cert.coverage if c.mode_id != missing],
        complete=True,
    )
    res = gate_delta_plus_coverage(spec, bad)
    assert not res.passed
    assert any(f.code == "UNDECLARED_FAILURE_MODE" for f in res.failures)


def test_checkable_mode_cannot_be_called_untestable():
    spec = _shaft_spec()
    req = coverage_requirements(spec)[0]
    bad = CoverageCertificate(
        spec_run_id=spec.run_id,
        failure_modes=[req.mode],
        coverage=[
            FailureModeCoverage(
                mode_id=req.mode.id,
                status=CoverageStatus.UNTESTABLE,
                evidence=["not run"],
                residual_risk="not run",
            )
        ],
        complete=True,
    )
    res = gate_delta_plus_coverage(spec, bad)
    assert not res.passed
    assert any(f.code == "REQUIRED_CHECK_NOT_PERFORMED" for f in res.failures)


def test_unrunnable_mode_is_valid_only_as_explicit_residual_gap():
    spec = _shaft_spec(complete=False)
    cert = build_coverage_certificate(spec)
    assert cert.coverage[0].status is CoverageStatus.UNTESTABLE
    assert "material.shear_strength" in cert.coverage[0].residual_risk
    assert gate_delta_plus_coverage(spec, cert).passed

    req = coverage_requirements(spec)[0]
    bad = CoverageCertificate(
        spec_run_id=spec.run_id,
        failure_modes=[req.mode],
        coverage=[
            FailureModeCoverage(
                mode_id=req.mode.id,
                status=CoverageStatus.CHECKED,
                evidence=["fake check"],
            )
        ],
        complete=True,
    )
    res = gate_delta_plus_coverage(spec, bad)
    assert not res.passed
    assert any(f.code == "UNRUNNABLE_MODE_CLAIMED_CHECKED" for f in res.failures)


def test_incomplete_certificate_cannot_pass():
    spec = _shaft_spec()
    cert = build_coverage_certificate(spec)
    bad = CoverageCertificate(
        spec_run_id=spec.run_id,
        failure_modes=cert.failure_modes,
        coverage=cert.coverage,
        complete=False,
    )
    res = gate_delta_plus_coverage(spec, bad)
    assert not res.passed
    assert any(f.code == "NOT_COMPLETE_CERTIFICATE" for f in res.failures)


def test_constraints_add_smt_coverage_mode():
    spec = Specification(
        run_id="r-smt",
        idea="constraint coverage",
        constraints=[Constraint(id="k1", left="a", kind="gt", right="b", reason="order")],
    )
    cert = build_coverage_certificate(spec)
    assert [m.id for m in cert.failure_modes] == ["smt:constraint_feasibility"]
    assert cert.coverage[0].status in {CoverageStatus.CHECKED, CoverageStatus.UNTESTABLE}
    assert gate_delta_plus_coverage(spec, cert).passed


def test_reviewed_failure_modes_become_required_residual_gaps():
    spec = Specification(run_id="r-review", idea="reviewed coverage")
    reviewed = FailureMode(
        id="review:thermal_runaway",
        label="thermal runaway",
        source="n_judge_consensus",
        grounding=["consensus:thermal_runaway:v1"],
    )

    missing = build_coverage_certificate(spec)
    res = gate_delta_plus_coverage(spec, missing, reviewed_failure_modes=[reviewed])
    assert not res.passed
    assert any(f.code == "UNDECLARED_FAILURE_MODE" for f in res.failures)

    cert = build_coverage_certificate(spec, reviewed_failure_modes=[reviewed])
    assert cert.failure_modes == [reviewed]
    assert cert.coverage[0].status is CoverageStatus.UNTESTABLE
    assert "deterministic validator" in cert.coverage[0].residual_risk
    assert gate_delta_plus_coverage(spec, cert, reviewed_failure_modes=[reviewed]).passed
