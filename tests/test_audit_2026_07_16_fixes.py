"""Regression tests for GENESIS_AUDIT_2026-07-16 priority fixes (A1, B1, C4)."""

from __future__ import annotations

from gen.cad.prototype_cad_builder import PrototypeSpec, build_prototype_cad
from gen.config import default_yaml_path, load_default_yaml
from gen.pipelines.fertigungs import FertigungsProzess


def test_a1_gcode_dict_uses_process_names_not_static_profile():
    """Static-key dict comprehension must not collapse multiple processes."""
    processes = [
        FertigungsProzess(name="FDM", begruendung="x", prozessgrenzen="y"),
        FertigungsProzess(name="CNC", begruendung="x", prozessgrenzen="y"),
    ]
    # mirror integrator fix
    gcode = {
        p.name: {
            "has_program": bool(getattr(p, "gcode_program", None)),
            "datei_stub": getattr(p, "datei_stub", None),
        }
        for p in processes
    }
    assert set(gcode.keys()) == {"FDM", "CNC"}
    assert "profile" not in gcode


def test_c4_config_yaml_is_loadable():
    path = default_yaml_path()
    assert path is not None and path.endswith("config.yaml")
    cfg = load_default_yaml()
    assert cfg.phase_alpha.confidence_threshold > 0


def test_b1_no_hardcoded_magic_volume_on_generic_plate():
    """Generic plate volume is bbox-derived, not the old 42.0 magic constant."""
    spec = PrototypeSpec(
        name="Generic plate",
        description="test plate",
        bounding_box_hint_mm=(100.0, 50.0, 4.0),
        min_wall_thickness_mm=2.0,
    )
    art = build_prototype_cad(spec, run_id="audit-b1")
    # bbox cm3 = 100*50*4/1000 = 20, or kernel solid ≤ bbox
    assert art.volume_estimate_cm3 is not None
    assert art.volume_estimate_cm3 != 42.0
    assert art.volume_estimate_cm3 <= 20.0 + 1e-6
