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
    isru_electrolysis_o2_check,
    life_support_o2_balance_check,
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


# --- ISRU electrolysis validator tests (direct calls, per auflage on commit 744bd2d) ---
# Exact stoich 36 kg H2O -> 32 kg O2 (molar 2H2O->O2+2H2), scaled by efficiency.
# Covers positive (incl target), invalid inputs, negative margin cases.
# These + epsilon tests increase coverage and guard against regression on ISRU/LIFE.


def test_isru_electrolysis_o2_check_stoich_positive():
    """36kg water at eff=1.0 yields exactly 32kg O2; eff=0.8/0.9 scale and meet reasonable targets."""
    # exact stoich eff=1
    res = isru_electrolysis_o2_check(36.0, efficiency=1.0)
    assert res["ok"] is True
    assert abs(res["o2_produced_kg"] - 32.0) < 1e-9
    assert res["water_consumed_kg"] == 36.0
    assert res["efficiency"] == 1.0

    # eff=0.8 → 25.6 kg
    res80 = isru_electrolysis_o2_check(36.0, efficiency=0.8)
    assert res80["ok"] is True
    assert abs(res80["o2_produced_kg"] - 25.6) < 1e-9

    # eff=0.9 yields ~28.8 >= target 25.0 (and >= target*0.95)
    res_tgt = isru_electrolysis_o2_check(36.0, efficiency=0.9, o2_target_kg=25.0)
    assert res_tgt["ok"] is True
    assert res_tgt["o2_produced_kg"] > 25.0

    # no target (o2_target<=0) is always ok if inputs valid
    res_notgt = isru_electrolysis_o2_check(10.0, efficiency=0.75)
    assert res_notgt["ok"] is True


def test_isru_electrolysis_o2_check_invalid_and_negative_cases():
    """Invalid (water<=0, eff not in (0,1]) → error; unmet target → ok=False."""
    res_bad_w = isru_electrolysis_o2_check(water_kg=0.0)
    assert res_bad_w["ok"] is False
    assert res_bad_w.get("error") == "invalid_inputs"

    res_bad_eff = isru_electrolysis_o2_check(10.0, efficiency=0.0)
    assert res_bad_eff["ok"] is False
    assert res_bad_eff.get("error") == "invalid_inputs"

    res_neg = isru_electrolysis_o2_check(-5.0, efficiency=0.8)
    assert res_neg["ok"] is False

    # valid inputs but target not met (16kg produced < 20*0.95=19)
    res_unmet = isru_electrolysis_o2_check(36.0, efficiency=0.5, o2_target_kg=20.0)
    assert res_unmet["ok"] is False
    assert res_unmet["o2_produced_kg"] < 20.0


# --- LIFE_SUPPORT O2 balance validator tests (symmetric to ISRU stoich; per task for LIFE one) ---
# Proxy: 0.84 kg O2 / crew / day * closure_rate (0-1). Covers positive (target met / no target),
# invalid inputs, unmet target (falsifiable margin). Lean + negative cases.


def test_life_support_o2_balance_check_positive():
    """Valid crew, default/valid rates: no-target always ok; target met when closure >= target*0.95."""
    # basic valid no target (closure default 0) -> ok
    res = life_support_o2_balance_check(crew=3.0)
    assert res["ok"] is True
    assert abs(res["o2_consumed_kg_day"] - 3.0 * 0.84) < 1e-9
    assert res["o2_produced_kg_day"] == 0.0
    assert res["closure_rate"] == 0.0

    # with closure 0.8, no target -> ok
    res80 = life_support_o2_balance_check(crew=2.0, closure_rate=0.8)
    assert res80["ok"] is True
    assert abs(res80["o2_produced_kg_day"] - 2.0 * 0.84 * 0.8) < 1e-9

    # target met: closure 0.9 >= 0.8*0.95
    res_tgt = life_support_o2_balance_check(crew=1.0, closure_rate=0.9, target_closure=0.8)
    assert res_tgt["ok"] is True
    assert res_tgt["safety_factor"] > 1.0


def test_life_support_o2_balance_check_invalid_and_negative_cases():
    """Invalid (crew<=0, consumption<=0, closure out of [0,1]) -> error; unmet target -> ok=False."""
    res_bad_crew = life_support_o2_balance_check(crew=0.0)
    assert res_bad_crew["ok"] is False
    assert res_bad_crew.get("error") == "invalid_inputs"

    res_bad_rate = life_support_o2_balance_check(crew=2.0, o2_consumption_kg_per_day=0.0)
    assert res_bad_rate["ok"] is False
    assert res_bad_rate.get("error") == "invalid_inputs"

    res_bad_closure = life_support_o2_balance_check(crew=1.0, closure_rate=1.5)
    assert res_bad_closure["ok"] is False

    # negative crew
    res_neg = life_support_o2_balance_check(crew=-1.0)
    assert res_neg["ok"] is False

    # valid inputs, target not met (closure 0.5 < 0.9*0.95)
    res_unmet = life_support_o2_balance_check(crew=4.0, closure_rate=0.5, target_closure=0.9)
    assert res_unmet["ok"] is False
    assert res_unmet["closure_rate"] < 0.9 * 0.95


# --- Schritt-7-Review-Fixes (2026-07-04): NaN/Inf-Schranke, non-dict-Schutz, ehrliche Evidenz ---

def test_gate_screens_non_finite_inputs_as_error_not_pass():
    """F6: a NaN/Inf input must become PHYSICS_CHECK_ERROR at the gate boundary —
    never reach a validator whose comparison logic would silently pass it."""
    for bad in (float("nan"), float("inf"), float("-inf")):
        checks = [PhysicsCheck(name="isru", validator="isru_electrolysis_o2",
                               inputs={"water_kg": bad})]
        res = gate_delta_physics(checks)
        assert res.passed is False
        assert res.failures[0].code == "PHYSICS_CHECK_ERROR"
        assert "non-finite" in res.failures[0].detail


def test_inline_validators_reject_nan_directly():
    """F1: the three inline validators must fail loudly on non-finite inputs even
    when called directly (defence in depth below the gate screen)."""
    nan = float("nan")
    assert isru_electrolysis_o2_check(water_kg=nan)["ok"] is False
    assert life_support_o2_balance_check(crew=nan)["ok"] is False
    assert vacuum_radiation_balance_check(
        absorbed_solar_w=0.0, epsilon=0.9, area_m2=1.0, t_k=nan,
        designed_as_sink_or_source=True,
    )["ok"] is False


def test_non_dict_validator_result_is_error_not_batch_crash():
    """F5: a validator returning a non-dict must yield status=error for THAT check
    and the batch must continue (docstring contract 'cannot abort the batch')."""
    VALIDATORS["_broken_returns_none"] = lambda **kw: None
    try:
        checks = [
            PhysicsCheck(name="broken", validator="_broken_returns_none", inputs={}),
            PhysicsCheck(name="good torsion", validator="torsion", inputs={
                "torque": 10.0, "diameter": 0.02, "length": 0.5,
                "shear_modulus_g": 8.0e10, "shear_strength": 2.0e8,
            }),
        ]
        rows = run_physics_checks(checks)
        assert rows[0]["status"] == "error"
        assert "non-dict" in rows[0]["detail"]
        assert rows[1]["status"] == "ran"          # batch continued
    finally:
        del VALIDATORS["_broken_returns_none"]


def test_fatigue_negative_amplitude_raises_not_infinite_life():
    """F3: a negative stress amplitude is a sign error upstream — it must raise,
    never report infinite life with ok=True."""
    import pytest
    from gen.fatigue import goodman_check
    with pytest.raises(ValueError):
        goodman_check(stress_amplitude=-80.0, mean_stress=60.0,
                      uts=500.0, endurance=250.0)


def test_pass_without_target_reports_no_fabricated_margin():
    """F7: a pass that never falsified anything must not fabricate a margin —
    safety_factor is None when no target/absorbed flux made a real ratio."""
    no_tgt = isru_electrolysis_o2_check(10.0, efficiency=0.75)
    assert no_tgt["ok"] is True and no_tgt["safety_factor"] is None
    no_close = life_support_o2_balance_check(crew=2.0, closure_rate=0.8)
    assert no_close["ok"] is True and no_close["safety_factor"] is None
    sink = vacuum_radiation_balance_check(
        absorbed_solar_w=0.0, epsilon=0.9, area_m2=1.0, t_k=300.0,
        designed_as_sink_or_source=True,
    )
    assert sink["ok"] is True and sink["safety_factor"] is None


def test_failed_check_without_margin_says_so():
    """F8: a failing validator that reports no safety_factor/ratio must say
    'no margin reported' instead of 'safety_factor=None'."""
    VALIDATORS["_fails_marginless"] = lambda **kw: {"ok": False}
    try:
        res = gate_delta_physics([PhysicsCheck(
            name="marginless", validator="_fails_marginless", inputs={})])
        assert res.passed is False
        assert "no margin reported" in res.failures[0].detail
    finally:
        del VALIDATORS["_fails_marginless"]


def test_every_validator_has_recipe_or_is_documented_manual_only():
    """F2: silent under-coverage guard — every VALIDATORS key must either have an
    auto-select CheckRecipe or be explicitly documented as manual-only."""
    from gen.physics_selection import MANUAL_ONLY_VALIDATORS, RECIPES
    with_recipe = {r.validator for r in RECIPES}
    uncovered = set(VALIDATORS) - with_recipe
    assert uncovered <= MANUAL_ONLY_VALIDATORS, (
        f"validators without recipe and not documented manual-only: "
        f"{sorted(uncovered - MANUAL_ONLY_VALIDATORS)}"
    )
    # the whitelist must not rot: no entry that meanwhile HAS a recipe
    assert not (MANUAL_ONLY_VALIDATORS & with_recipe)
