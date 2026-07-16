"""H8: multi-physics receipt depth (thermoelastic + fatigue screen)."""

from __future__ import annotations

import pytest

from gen.simulation.runner import multi_physics_receipt


def test_h8_thermoelastic_and_stress_screen():
    rec = multi_physics_receipt(
        power_w=10.0,
        r_th_k_per_w=2.0,
        force_n=100.0,
        alpha_per_k=23e-6,
        sigma_allow_pa=200e6,
        run_id="h8",
    )
    assert rec["thermal"]["delta_t_k"] == pytest.approx(20.0)
    assert rec["thermoelastic"] is not None
    assert rec["thermoelastic"]["axial_expansion_m"] > 0
    assert rec["structural"]["tip_deflection_total_m"] >= rec["structural"]["tip_deflection_m"]
    assert rec["stress_screen"] is not None
    assert "sigma_pa" in rec["stress_screen"]
    assert "thermoelastic" in rec["closed_loop"]["domains"]


def test_h8_fatigue_screen_when_cycles_set():
    rec = multi_physics_receipt(cycles=1000, force_n=50.0, basquin_a=1e20, basquin_b=3.0)
    assert rec["fatigue"] is not None
    assert rec["fatigue"]["cycles_requested"] == 1000
    assert rec["fatigue"]["n_predicted"] > 0
    assert "fatigue_screen" in rec["closed_loop"]["domains"]


def test_h8_bad_cycles_is_loud():
    with pytest.raises(ValueError, match="cycles"):
        multi_physics_receipt(cycles=0)
    with pytest.raises(ValueError, match="cycles"):
        multi_physics_receipt(cycles=-1)


def test_s2_backward_compatible_closed_forms():
    rec = multi_physics_receipt(power_w=10.0, r_th_k_per_w=2.0, force_n=100.0)
    assert abs(rec["thermal"]["delta_t_k"] - 20.0) < 1e-9
    assert rec["structural"]["tip_deflection_m"] > 0
    assert rec["gaps"]
