"""C3: CNC / Laser ranged cost models — honest bands + fail-loud."""
from __future__ import annotations

import pytest

from gen.cad.cost_model import estimate_cnc_cost, estimate_laser_cost, estimate_fdm_cost


def test_estimate_cnc_cost_band_and_gaps():
    est = estimate_cnc_cost(50.0)
    assert est.process == "CNC"
    assert est.low_eur > 0 and est.high_eur >= est.low_eur
    assert est.breakdown
    assert any("toolpath" in g.lower() or "cam" in g.lower() for g in est.gaps)
    assert "Xometry" in (est.source or "") or "Protolabs" in (est.source or "")


def test_estimate_laser_cost_band_and_perimeter_gap():
    est = estimate_laser_cost(200.0, 100.0, thickness_mm=3.0)
    assert est.process == "Laser"
    assert est.low_eur > 0 and est.high_eur >= est.low_eur
    assert any("perimeter" in g.lower() or "cut_length" in g.lower() for g in est.gaps)


def test_cost_models_fail_loud_on_bad_input():
    with pytest.raises(ValueError):
        estimate_cnc_cost(0)
    with pytest.raises(ValueError):
        estimate_laser_cost(-1, 10)
    with pytest.raises(ValueError):
        estimate_fdm_cost(-5)


def test_advanced_dfm_surfaces_cnc_laser_cost_hints():
    from gen.cad.manufacturing_check import check_advanced_dfm
    from gen.cad.prototype_cad_builder import PrototypeSpec, BuildArtifact

    spec = PrototypeSpec(
        name="Cost Plate",
        description="cost test",
        bounding_box_hint_mm=(100, 80, 6),
        min_wall_thickness_mm=3.0,
        material_hint="aluminum 6061",
    )
    art = BuildArtifact(
        spec=spec, generated_code="", exports={}, dfm_report=[], volume_estimate_cm3=48.0
    )
    rep = check_advanced_dfm(art)
    cnc = next(p for p in rep.processes if p.process == "CNC")
    laser = next(p for p in rep.processes if p.process == "Laser")
    assert cnc.cost_hint and ("EUR" in cnc.cost_hint or "€" in cnc.cost_hint)
    assert laser.cost_hint and ("EUR" in laser.cost_hint or "€" in laser.cost_hint)
    assert "CNC" in (rep.cost_model_stub or "")
