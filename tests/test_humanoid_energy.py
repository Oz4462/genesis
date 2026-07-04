"""Teilprojekt 1 (Energie & Thermik): Laufzeit- und Motor-Thermik-Checks der Humanoiden."""
from dataclasses import replace

from gen.competitive_humanoid import FLAGSHIP, PRINTED, build_humanoid
from gen.physics_selection import select_physics_checks
from gen.pipeline import assess_specification


def _quantity(spec, qid):
    m = {q.id: q for q in spec.quantities}
    assert qid in m, f"{qid} fehlt in Spec {spec.run_id}"
    return m[qid]


def test_energy_quantities_present_and_consistent():
    for cfg in (PRINTED, FLAGSHIP):
        spec = build_humanoid(cfg)
        cap = _quantity(spec, "q_batt_cap")
        assert cap.unit == "Wh" and cap.value == cfg.battery_capacity_wh
        assert cap.measurand == "battery.capacity"
        req = _quantity(spec, "q_endurance_req")
        assert req.unit == "min" and req.value == cfg.required_endurance_min
        # Leistungskette: Werte konsistent mit den Formeln
        p_mech = _quantity(spec, "q_p_mech_joint")
        assert abs(p_mech.value - cfg.joint_torque_nm * cfg.joint_speed_rad_s * cfg.locomotion_duty) < 1e-9
        p_loco = _quantity(spec, "q_p_loco")
        assert abs(p_loco.value - cfg.n_drive_motors * p_mech.value / cfg.efficiency) < 1e-9
        p_total = _quantity(spec, "q_p_total")
        assert abs(p_total.value - (p_loco.value + cfg.compute_power_budget_w)) < 1e-9
        assert p_total.measurand == "robot.total_power"
        assert req.measurand == "robot.required_endurance"
        # Formeln sind DERIVED (Gate rechnet nach), Kapazität ist GROUNDED
        assert p_total.derivation is not None and cap.grounding


def _check_names(assessment):
    return {c.name for c in assessment.physics_checks}


def test_battery_endurance_check_fires_and_passes():
    for cfg in (PRINTED, FLAGSHIP):
        a = assess_specification(build_humanoid(cfg))
        assert "robot battery endurance" in _check_names(a)
        assert a.overall == "physics_verified", a.overall


def test_undersized_battery_fails_endurance():
    tiny = replace(PRINTED, run_id="printed_tiny_batt", battery_capacity_wh=200.0)
    a = assess_specification(build_humanoid(tiny))
    assert a.overall != "physics_verified"
    assert a.physics_gate.failures and any("battery" in f.detail for f in a.physics_gate.failures)


def test_robot_battery_endurance_check_selected_with_no_gaps():
    checks, gaps = select_physics_checks(build_humanoid(PRINTED))
    assert gaps == [], f"Gaps: {gaps}"
    check_names = {c.name for c in checks}
    assert "robot battery endurance" in check_names
    # Ensure exactly one battery-endurance check
    battery_checks = [c for c in checks if "battery endurance" in c.name]
    assert len(battery_checks) == 1
