"""Teilprojekt 1 (Energie & Thermik): Laufzeit- und Motor-Thermik-Checks der Humanoiden."""
from gen.competitive_humanoid import FLAGSHIP, PRINTED, build_humanoid


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
        # Formeln sind DERIVED (Gate rechnet nach), Kapazität ist GROUNDED
        assert p_total.derivation is not None and cap.grounding
