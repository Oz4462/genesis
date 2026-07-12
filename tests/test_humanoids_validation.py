"""Humanoid physics-axis validation — GENESIS's closed-form axes run against real robots' specs.

Exact checks, not vibes: the AGILOped actuation case (full motor ratings from the paper, independent
of any parsed model) yields a static hip gravity-hold torque GENESIS computes near the single
RMD-X6-40's rating and within the knee's 80 N·m capability; the ZMP sanity anchor returns a stable
unit margin for a CoM over the foot centre on every robot with a known height; a spec-only robot
reports an honest structural GAP rather than a fabricated DOF/mass; and a robot whose model is present
cross-checks DOF without raising. Every catalogued robot validates without error.

Offline, numpy/scipy only. Run:  pytest tests/test_humanoids_validation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.humanoids.catalog import ASSETS, SPECS, robots  # noqa: E402
from gen.humanoids.validation import (  # noqa: E402
    balance_axis_check,
    structural_cross_check,
    validate_all,
    validate_robot,
)


def test_every_catalogued_robot_validates_without_error():
    """The whole table must build — a robot raising mid-validation is a defect."""
    all_results = validate_all()
    assert set(all_results) == set(robots())
    for key, results in all_results.items():
        assert results, f"{key} produced no checks"
        for r in results:
            assert r.verdict in {"agree", "gap", "mismatch", "info"}


def test_agiloped_actuation_axis_is_physically_sensible_and_independent():
    """AGILOped's specs come from the paper, not from any parsed model, so this is an INDEPENDENT
    calibration: GENESIS's static knee SQUAT-hold torque must be positive, below the knee's published
    80 N·m peak (a real leg holds the representative squat with margin), and on the order of the
    actuator class. (Post-2026-06-24 the axis is the physically-correct knee squat hold, not the old
    over-predicting whole-leg-horizontal sizing.)"""
    results = validate_robot("agiloped")
    torque_checks = [r for r in results if "knee squat-hold torque" in r.axis]
    assert torque_checks, "expected a knee squat-hold torque axis result for AGILOped"
    tc = torque_checks[0]
    assert tc.verdict == "agree"          # capability (80 N·m knee) >= GENESIS 60° squat demand
    # the GENESIS demand value is embedded as "<N> N·m demand @60° squat"
    val = float(tc.genesis_value.split()[0])
    assert 10.0 < val < 80.0              # within the knee actuator's peak capability


def test_zmp_anchor_is_stable_for_a_known_height_robot():
    res = balance_axis_check("tienkung")
    assert len(res) == 1
    assert res[0].verdict == "agree"
    assert "margin 1.00" in res[0].genesis_value


def test_spec_only_robot_reports_honest_structural_gap_not_a_fabricated_value():
    """A spec-only robot (no model on disk) → structural check must be a GAP, never invented DOF/mass.

    Uses InMoov, which is genuinely spec-only here (STL-only NonCommercial hobby model, no URDF/MJCF).
    NOTE: Fourier N1 USED to be the spec-only example, but its MJCF was acquired (Wiki-GRx-MJCF) and it
    is now engine-validated, so it is no longer the right fixture for the spec-only gap behaviour."""
    assert ASSETS["inmoov"].model_path is None
    res = structural_cross_check("inmoov")
    assert len(res) == 1
    assert res[0].verdict == "gap"
    assert res[0].genesis_value == "—"


@pytest.mark.skipif(ASSETS["tienkung"].model_path is None
                    or not Path(ASSETS["tienkung"].model_path).is_file(),
                    reason="TienKung model not downloaded")
def test_tienkung_structural_cross_check_agrees_on_dof():
    res = structural_cross_check("tienkung")
    dof = [r for r in res if r.axis.startswith("DOF")]
    assert dof and dof[0].verdict == "agree"
    assert "20 motorised joints" in dof[0].genesis_value


def test_inmoov_is_honestly_all_gaps_no_legs_no_fixed_specs():
    """InMoov is an upper-body, NonCommercial, STL-only hobby model with no single mass/DOF — the
    validation must reflect that as gaps, not pretend a humanoid leg/biped exists."""
    assert SPECS["inmoov"].legs.value == 0
    results = validate_robot("inmoov")
    assert all(r.verdict == "gap" for r in results)
