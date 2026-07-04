"""GATE δ-physics — the validator-registry gate that aggregates engineering checks.

The gate passes only if every declared check actually ran and reported ok; an unknown
validator, a validator that raises, and a validator that clears no margin each produce a
distinct hard failure (never a silent pass). Offline, no LLM, pure functions.

Run:  pytest tests/test_physics_validation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.physics_validation import (  # noqa: E402
    VALIDATORS,
    PhysicsCheck,
    gate_delta_physics,
    run_physics_checks,
    vacuum_radiation_balance_check,
)

# For recipe/dose mapping test (real, non-decorative)
from gen.physics_selection import select_physics_checks  # noqa: E402
from gen.core.state import Quantity, ValueOrigin, Specification, Component  # noqa: E402

# a few checks with inputs that pass their own margin
_TORSION_OK = PhysicsCheck("drive shaft", "torsion", dict(
    torque=100000.0, diameter=20.0, length=1000.0, shear_modulus_g=80000.0, shear_strength=100.0))
_FATIGUE_OK = PhysicsCheck("bracket fillet", "fatigue", dict(
    stress_amplitude=80.0, mean_stress=60.0, uts=500.0, endurance=250.0))
_RESONANCE_OK = PhysicsCheck("mount", "resonance", dict(
    first_natural_hz=300.0, excitation_hz=100.0))


def test_all_passing_checks_pass_the_gate():
    result = gate_delta_physics([_TORSION_OK, _FATIGUE_OK, _RESONANCE_OK])
    assert result.gate == "delta-physics"
    assert result.passed and result.failures == []


def test_empty_checklist_passes_vacuously():
    result = gate_delta_physics([])
    assert result.passed and result.failures == []


def test_a_failing_check_fails_the_gate():
    # same shaft, but a weak material: max_shear ~63.7 MPa > 30 MPa strength -> not ok
    weak = PhysicsCheck("drive shaft", "torsion", dict(
        torque=100000.0, diameter=20.0, length=1000.0, shear_modulus_g=80000.0, shear_strength=30.0))
    result = gate_delta_physics([_TORSION_OK, weak])
    assert not result.passed
    codes = [f.code for f in result.failures]
    assert codes == ["PHYSICS_CHECK_FAILED"]
    assert "drive shaft" in result.failures[0].detail


def test_unknown_validator_is_a_hard_failure():
    result = gate_delta_physics([PhysicsCheck("mystery", "no_such_validator", {})])
    assert not result.passed
    assert result.failures[0].code == "PHYSICS_UNKNOWN_VALIDATOR"


def test_erroring_validator_is_surfaced_not_swallowed():
    # a zero diameter makes the torsion validator raise; the gate must FAIL, not pass
    bad = PhysicsCheck("broken shaft", "torsion", dict(
        torque=100000.0, diameter=0.0, length=1000.0, shear_modulus_g=80000.0, shear_strength=100.0))
    result = gate_delta_physics([bad])
    assert not result.passed
    assert result.failures[0].code == "PHYSICS_CHECK_ERROR"
    assert "broken shaft" in result.failures[0].detail


def test_run_physics_checks_returns_evidence():
    rows = run_physics_checks([_TORSION_OK, PhysicsCheck("x", "nope", {})])
    assert rows[0]["status"] == "ran" and rows[0]["ok"] is True
    assert rows[0]["result"]["safety_factor"] > 1.0          # the computed margin
    assert rows[1]["status"] == "unknown" and rows[1]["ok"] is False


def test_registry_exposes_the_expected_validators():
    for key in ("torsion", "buckling", "fatigue", "contact", "pressure_vessel",
                "creep", "overtemperature", "thermal_mismatch", "resonance",
                "notch_fatigue", "fracture", "plate_bending", "bolted_joint"):
        assert key in VALIDATORS and callable(VALIDATORS[key])


def test_mixed_batch_reports_each_distinct_failure():
    result = gate_delta_physics([
        _TORSION_OK,                                                    # ok
        PhysicsCheck("u", "ghost", {}),                                 # unknown
        PhysicsCheck("e", "torsion", dict(                              # error (d=0)
            torque=1.0, diameter=0.0, length=1.0, shear_modulus_g=1.0, shear_strength=1.0)),
        PhysicsCheck("f", "fatigue", dict(                             # failed margin
            stress_amplitude=300.0, mean_stress=300.0, uts=500.0, endurance=250.0)),
    ])
    assert not result.passed
    assert {f.code for f in result.failures} == {
        "PHYSICS_UNKNOWN_VALIDATOR", "PHYSICS_CHECK_ERROR", "PHYSICS_CHECK_FAILED"}


# --- vacuum radiation validator fixes (Befund 4/5/6 honesty) ---

def test_vacuum_radiation_equilibrium_ok():
    """Balanced case (net ~0) passes without designed flag. Use ~radiated value for 300K/0.8/0.5."""
    res = vacuum_radiation_balance_check(183.7, 0.8, 0.5, 300.0, tol=0.1)
    assert res["ok"] is True
    assert "radiation_dose_sv" in res  # always present (Befund 5)
    assert res["radiation_dose_sv"] == 0.0


def test_vacuum_radiation_eclipse_without_designed_fails():
    """Eclipse (absorbed=0) pure radiator without designed flag fails (net !=0)."""
    res = vacuum_radiation_balance_check(0.0, 0.8, 0.5, 300.0, tol=0.1)
    assert res["ok"] is False
    assert res["net_heat_w"] < 0


def test_vacuum_radiation_designed_sink_passes_in_eclipse():
    """Designed sink support (Befund 6): eclipse radiator with flag passes despite imbalance."""
    res = vacuum_radiation_balance_check(
        0.0, 0.8, 0.5, 300.0, tol=0.1, designed_as_sink_or_source=True
    )
    assert res["ok"] is True
    assert "designed_note" in res


def test_vacuum_radiation_dose_is_real_limit_check_not_echo():
    """Dose always mapped + participates in ok (limit check); high dose fails even if balance ok (Befund 5)."""
    res_low = vacuum_radiation_balance_check(183.7, 0.8, 0.5, 300.0, radiation_dose_sv=5.0, dose_limit_sv=10.0)
    assert res_low["radiation_dose_sv"] == 5.0
    assert res_low["dose_ok"] is True
    assert res_low["ok"] is True

    res_high = vacuum_radiation_balance_check(183.7, 0.8, 0.5, 300.0, radiation_dose_sv=20.0, dose_limit_sv=10.0)
    assert res_high["dose_ok"] is False
    assert res_high["ok"] is False
    assert "dose_note" in res_high


def test_radiation_recipe_maps_dose_real_via_select():
    """Recipe update + select: dose from radiation measurand is mapped into PhysicsCheck
    (not decorative) and fed to validator (Befund 5).
    """
    qs = [
        Quantity(id="abs", name="abs", value=120.0, unit="W", origin=ValueOrigin.DECISION, rationale="test", measurand="thermal.radiation_absorbed"),
        Quantity(id="eps", name="eps", value=0.85, unit="1", origin=ValueOrigin.DECISION, rationale="test", measurand="material.emissivity"),
        Quantity(id="area", name="area", value=0.6, unit="m^2", origin=ValueOrigin.DECISION, rationale="test", measurand="surface.area"),
        Quantity(id="tk", name="tk", value=290.0, unit="K", origin=ValueOrigin.DECISION, rationale="test", measurand="thermal.temperature"),
        Quantity(id="dose", name="dose", value=4.2, unit="Sv", origin=ValueOrigin.DECISION, rationale="test", measurand="radiation.total_ionizing_dose"),
    ]
    spec = Specification(
        run_id="r-dose-map",
        idea="space radiator dose mapping test",
        quantities=qs,
        components=[Component(id="rad", name="panel")],
        bom=[],
    )
    checks, gaps = select_physics_checks(spec)
    rad_checks = [c for c in checks if "radiation" in c.validator]
    assert len(rad_checks) == 1
    chk = rad_checks[0]
    assert chk.validator == "vacuum_radiation_balance"
    assert "radiation_dose_sv" in chk.inputs
    assert chk.inputs["radiation_dose_sv"] == 4.2
    # also designed from extra
    assert chk.inputs.get("designed_as_sink_or_source") is False
