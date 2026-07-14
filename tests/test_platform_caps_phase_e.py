"""Phase E: caps matrix, multi-physics receipt, mesh refs, bundle caps honesty."""
from __future__ import annotations

from gen.platform_caps import (
    CAPS_SURFACE_MATRIX,
    caps_matrix_report,
    extract_caps_snapshot,
)
from gen.simulation.runner import (
    analytical_mesh_series_case,
    get_reference_cases,
    mesh_convergence_gate,
    multi_physics_receipt,
)


def test_s1_caps_matrix_has_assess_and_bundle_full():
    rep = caps_matrix_report()
    assert rep["schema"] == "genesis-caps-matrix-v1"
    assert rep["total_modes"] >= 8
    by_mode = {r["mode"]: r for r in rep["rows"]}
    for m in ("assess", "bundle", "realize"):
        assert by_mode[m]["proof_package"] is True
        assert by_mode[m]["readiness"] is True
        assert by_mode[m]["teacher"] is True
        assert by_mode[m]["community"] is True
    assert CAPS_SURFACE_MATRIX["research"]["proof_package"] is False


def test_s1_extract_caps_from_assessment_like_object():
    class _A:
        proof_package = "out/proof_packages/x"
        readiness_level = "TRL4"
        teacher_notes = {"step": "assess"}
        community_evidence = {
            "community_score": 0.0,
            "agent_sourced": True,
            "user_data_required": False,
        }

    snap = extract_caps_snapshot(assessment=_A())
    assert snap.present["proof_package"] is True
    assert snap.present["teacher"] is True
    assert snap.community_score == 0.0
    assert snap.user_data_required is False


def test_s2_multi_physics_receipt_closed_forms():
    rec = multi_physics_receipt(power_w=10.0, r_th_k_per_w=2.0, force_n=100.0)
    assert rec["schema"] == "genesis-multi-physics-receipt-v1"
    assert abs(rec["thermal"]["delta_t_k"] - 20.0) < 1e-9
    assert rec["structural"]["tip_deflection_m"] > 0
    assert "electrical" in rec["closed_loop"]["domains"]
    assert rec["gaps"]


def test_s3_reference_cases_include_thermal_and_electrical():
    refs = get_reference_cases()
    names = {r["name"] for r in refs}
    assert "lumped_thermal_rc" in names
    assert "ohmic_power" in names
    assert "plate_bending_center_load" in names
    assert len(refs) >= 6


def test_s3_mesh_convergence_synthetic_series_ok():
    case = analytical_mesh_series_case(predicted_value=1.0, relative_tol=0.05)
    gate = mesh_convergence_gate(case, relative_tol=0.05)
    assert gate["ok"] is True
    assert gate["converged"] is True


def test_s3_mesh_convergence_none_is_honest_fail():
    gate = mesh_convergence_gate(None)
    assert gate["ok"] is False
    assert gate["gaps"]
