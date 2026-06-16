"""Tests for the hardened simulation layer (Punkt 4 completion).

Two tests:
- Jetpack-style tethered component (structural + modal)
- Generic plate (shows fallback + provenance)

All outputs must carry provenance and be usable for reality.py falsification.
"""

from gen.simulation.runner import (
    SimulationRunner,
    run_simulations_for_design,
    run_simulations_for_hammer,
    build_simulation_report,
)
from gen.grenzverschiebung.lumencrucible import LumenHammer
from gen.cad.prototype_cad_builder import PrototypeSpec, BuildArtifact


def test_simulation_runner_jetpack_tether_produces_structural_and_modal():
    spec = PrototypeSpec(
        name="jetpack_tether_anchor_plate",
        description="Tether anchor for manned jetpack recovery",
        bounding_box_hint_mm=(150, 120, 8),
        quelle="test_simulation_runner",
    )
    artifact = BuildArtifact(
        spec=spec,
        generated_code="# real CAD would be here",
        exports={},
        dfm_report=[],
        volume_estimate_cm3=42.0,
        quelle="test",
    )

    runner = SimulationRunner(run_id="sim-test-jet-001")
    result = runner.run_for_artifact(
        artifact,
        loads={"tether_load_n": 2800.0},
        material={"e_modulus_mpa": 3500.0, "density_kg_m3": 1250.0},
    )

    assert result.overall_status in ("predictions_ready", "partial")
    domains = [c.domain for c in result.cases]
    assert "structural_linear" in domains
    assert "modal" in domains

    # Check provenance and units
    for case in result.cases:
        assert "simulation.runner" in case.quelle
        assert case.predicted_unit in ("mm", "MPa", "Hz")
        assert case.tolerance > 0

    # Can be turned into falsification experiments
    report = build_simulation_report("jetpack_tether", result)
    assert len(report.recommended_falsification_experiments) >= 1
    assert "structural_linear" in str(report.recommended_falsification_experiments)

    # Verify thermal generation works when power is supplied
    thermal_result = runner.run_for_artifact(
        artifact,
        loads={"power_w": 12.0},
        material={"thermal_conductivity_w_per_mm_k": 0.0002},
    )
    assert any(c.domain == "thermal_steady" for c in thermal_result.cases)
    exps = runner.generate_falsification_experiments(thermal_result)
    assert any("thermal_steady" in e.get("measurand", "") or "thermal" in str(e) for e in exps)

    # Buckling and Fatigue concrete domains
    buckle_result = runner.run_for_artifact(artifact, loads={"axial_load_n": 1200.0})
    assert any(c.domain == "buckling_euler" for c in buckle_result.cases)

    fat_result = runner.run_for_artifact(artifact, loads={"stress_amplitude_mpa": 25.0})
    assert any(c.domain == "fatigue_life" for c in fat_result.cases)

    # The generator produces rich, reality-ready output (new structure)
    all_exps = runner.generate_falsification_experiments(fat_result)
    assert all("predicted_value" in e and "tolerance" in e and "quelle" in e for e in all_exps)
    assert any("fatigue_life" in e.get("measurand", "") or "fatigue" in str(e) for e in all_exps)


def test_simulation_runner_generic_and_hammer_integration():
    hammer = LumenHammer(
        experiment_name="generic_plate_test_hammer",
        description="Small structural test plate under point load",
        next_step="Build and measure deflection + first mode",
        gate_to_pass="gate_delta_plus",
        frontier_snapshot={},
        quelle="test",
    )

    sim = run_simulations_for_hammer(hammer, run_id="sim-test-generic-002")
    assert sim is not None
    assert len(sim.cases) >= 1
    assert any("simulation.runner" in c.quelle for c in sim.cases)

    report = build_simulation_report(hammer.experiment_name, sim)
    assert report.design_name == hammer.experiment_name
    assert len(report.recommended_falsification_experiments) > 0
