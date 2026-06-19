"""The honest realization bundle: emit_bundle writes every producible deliverable AND a manifest
that names, by construction, exactly what is missing — never a silent pass. A complete part (the
knee mount) yields the manual + SCAD + STL + BOM + manifest; a geometry-less spec (the drive shaft)
still gets a manual but its MANIFEST honestly records that there is no printable part. The BOM is
split into printed vs bought parts (owner directive: maximise what the 3D printer makes).

Offline, no LLM. The STL needs the OCCT kernel; the assertion adapts honestly to its presence.
Run:  pytest tests/test_bundle.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.bundle import classify_printability, emit_bundle  # noqa: E402
from gen.demo import drive_shaft_spec, knee_mount_spec, leg_assembly_spec  # noqa: E402
from gen.pipeline import assess_specification  # noqa: E402

_HAS_CADQUERY = importlib.util.find_spec("cadquery") is not None


def test_knee_mount_bundle_writes_every_deliverable(tmp_path):
    """A complete robot part emits the manual, the OpenSCAD print source, the BOM and a manifest;
    the watertight STL too when the OCCT kernel is present (else honestly recorded as missing)."""
    m = emit_bundle(knee_mount_spec(), tmp_path)
    assert "BAUANLEITUNG.md" in m.written
    assert "knee_mount.scad" in m.written
    assert "bom.json" in m.written and "MANIFEST.json" in m.written
    for name in ("BAUANLEITUNG.md", "knee_mount.scad", "bom.json", "MANIFEST.json"):
        assert (tmp_path / name).stat().st_size > 0
    assert m.overall == "physics_verified" and m.physics_ok
    if _HAS_CADQUERY:
        assert "knee_mount.stl" in m.written and (tmp_path / "knee_mount.stl").stat().st_size > 0
        assert m.files_complete                       # every producible file was written
    else:
        assert any("knee_mount.stl" in x for x in m.missing)  # honest: kernel absent, not silent


def test_print_split_maximises_printed_and_names_bought():
    """Owner directive: the printed share is reported and only the truly non-printable parts (motor,
    bearing, bolts) are on the buy-list; the structural mount is fabricated in-house."""
    split = classify_printability(knee_mount_spec())
    assert split.printed == ["b_mount"]
    assert set(split.bought) == {"b_motor", "b_bearing", "b_bolts"}
    assert split.printed_share == pytest.approx(0.25)


def test_missing_md_surfaces_the_unpriced_motor_and_gaps(tmp_path):
    """The honest gap list is impossible to overlook: MISSING.md exists and names the not-yet-sourced
    motor (unpriced) — the cost is a partial lower bound, surfaced not swallowed."""
    m = emit_bundle(knee_mount_spec(), tmp_path)
    assert "MISSING.md" in m.written
    text = (tmp_path / "MISSING.md").read_text(encoding="utf-8")
    assert "b_motor" in text
    assert not m.cost_complete and "b_motor" in m.unpriced


def test_geometryless_spec_is_honest_not_a_silent_pass(tmp_path):
    """A quantities-only spec (the drive shaft) has no printable part. The bundle still writes the
    manual, but the MANIFEST records the absence explicitly — the exact failure GENESIS prevents:
    an incomplete output presented as complete."""
    m = emit_bundle(drive_shaft_spec(), tmp_path)
    assert "BAUANLEITUNG.md" in m.written
    assert not m.files_complete
    assert any("keine Bauteil-Geometrie" in x for x in m.missing)
    on_disk = json.loads((tmp_path / "MANIFEST.json").read_text(encoding="utf-8"))
    assert any("Geometrie" in x for x in on_disk["missing"])


def test_failing_geometry_is_recorded_not_crashed(tmp_path):
    """Adversarial property (grok P2): a spec whose geometry references a non-existent quantity makes
    the STL export fail — but the catch-all records it as an explicit MISSING entry and still writes
    the manifest. One bad deliverable never aborts the bundle; the failure is surfaced, never a silent
    pass and never a crash."""
    from gen.core.state import Component, GeometryNode, Specification

    broken = GeometryNode(kind="box", params={"size_x": "nope", "size_y": "nope", "size_z": "nope"})
    spec = Specification(run_id="broken", idea="kaputte Geometrie",
                         components=[Component(id="c", name="c", geometry=broken)])
    m = emit_bundle(spec, tmp_path)                 # must NOT raise
    assert "MANIFEST.json" in m.written             # the manifest is still written
    assert any(".stl" in x for x in m.missing)      # the STL failure is recorded, not swallowed
    assert not m.files_complete                     # honestly reported as incomplete


def test_leg_assembly_emits_per_part_stls_and_fires_dynamics(tmp_path):
    """The MULTI-PART leg assembly: the gate auto-fires the dynamic robot axes (ZMP-over-gait, swing
    inverse dynamics, swing resonance) + the knee actuator + the 2R reach; emit_bundle writes ONE STL
    per printed link (thigh + shank, each its own watertight mesh) plus the combined BOM + assembly
    manual. The assembled robot, not a single part — through the same gated machinery."""
    spec = leg_assembly_spec()
    a = assess_specification(spec)
    fired = {c.validator for c in a.physics_checks}
    assert {"zmp_dynamic", "joint_swing_torque", "swing_resonance",
            "electric_actuator", "reach"} <= fired
    assert a.physics_gaps == [] and a.physics_ok
    m = emit_bundle(spec, tmp_path)
    assert set(m.printed_parts) == {"b_thigh", "b_shank"}              # two printed parts
    md = (tmp_path / "BAUANLEITUNG.md").read_text(encoding="utf-8")
    assert "Oberschenkel-Glied" in md and "Unterschenkel-Glied" in md
    if _HAS_CADQUERY:
        assert "leg_assembly__c_thigh.stl" in m.written               # one STL per printed part
        assert "leg_assembly__c_shank.stl" in m.written
        assert (tmp_path / "leg_assembly__c_thigh.stl").stat().st_size > 0


def test_cli_bundle_mode_emits_the_bundle(tmp_path, monkeypatch):
    """`gen --mode bundle` writes the honest bundle for the demo specs (the manifest is always there,
    recording exactly what was produced). Runs in tmp_path so it writes no repo files."""
    monkeypatch.chdir(tmp_path)
    from gen.cli import main
    rc = main(["--mode", "bundle"])
    assert rc in (0, 3)                                                  # 0 with kernel, 3 if STL missing
    assert (tmp_path / "out" / "bundle" / "knee_mount" / "MANIFEST.json").exists()
    assert (tmp_path / "out" / "bundle" / "knee_mount" / "BAUANLEITUNG.md").exists()
