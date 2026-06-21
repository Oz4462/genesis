"""End-to-end acceptance: the humanoid knee-actuator mount is a COMPLETE, gated robot part —
it fires the robot delta-physics axes (electric_actuator + reach) through the honest wiring AND
emits the three real deliverables the bracket does: a print-ready STL, a buy-list BOM with an
honest partial cost, and a Markdown build manual. This is the spec that closes the "robot has no
buildable artifact" gap; here it is proven to actually produce them.

Offline, no LLM. The watertight boolean STL needs the OCCT kernel (cadquery); that one check skips
honestly when the kernel is absent, exactly as the spec's gap declares. Run:  pytest tests/test_robot_artifact.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.costing import bom_cost  # noqa: E402
from gen.demo import knee_mount_spec  # noqa: E402
from gen.export.markdown import specification_to_markdown  # noqa: E402
from gen.pipeline import assess_specification  # noqa: E402


def test_mount_fires_the_robot_axes_and_passes_honestly():
    """The measurand tags alone select electric_actuator (knee motor vs joint torque) and reach
    (2R leg), both clear their margin, and there is no indicated-but-unrunnable gap — so the wired
    engine reports physics as genuinely verified, not a masked pass."""
    a = assess_specification(knee_mount_spec())
    fired = {c.validator for c in a.physics_checks}
    assert {"electric_actuator", "reach"} <= fired
    assert a.physics_gaps == []
    assert a.physics_gate.passed
    assert a.physics_ok


def test_build_manual_carries_geometry_bom_and_steps():
    """The Markdown manual is a real deliverable: it shows the printable component, the buy-list
    (the gearmotor, the bearing, the bolts) and the numbered build steps with the torque spec."""
    md = specification_to_markdown(knee_mount_spec())
    assert "Knie-Aktuator-Halterung" in md
    assert "Stückliste (Mechanik)" in md
    assert "Knie-Gelenkmotor" in md and "6800-2RS" in md
    assert "Bauschritte" in md
    assert "2.5 N*m" in md  # the motor-flange tightening torque appears in a step


def test_bom_cost_is_an_honest_partial():
    """The priced commodity items (bearing + 4 bolts) roll up to 5.18 EUR; the printed mount and
    the not-yet-sourced motor are flagged unpriced — a partial lower bound, never a guessed total."""
    cost = bom_cost(knee_mount_spec())
    assert cost.subtotals.get("EUR") == pytest.approx(3.50 + 4 * 0.42)
    assert "b_mount" in cost.unpriced and "b_motor" in cost.unpriced
    assert not cost.complete


def test_print_ready_stl_is_watertight_and_emittable(tmp_path):
    """The boolean CSG (plate minus two bores) tessellates to a print-ready mesh that passes the
    mesh-integrity gate (watertight, consistent winding, outward volume) and writes to disk as a
    real STL file. Skips honestly when the OCCT kernel is absent — exactly the declared gap."""
    pytest.importorskip("cadquery")  # the OCCT kernel; skip honestly when absent
    from gen.export.brep_stl import specification_to_brep_stl
    from gen.mesh_integrity import stl_integrity_check

    stl = specification_to_brep_stl(knee_mount_spec())
    verdict = stl_integrity_check(stl)
    assert verdict["ok"], verdict.get("issues")

    out = tmp_path / "knee_mount.stl"
    out.write_text(stl, encoding="utf-8")
    assert out.exists() and out.stat().st_size > 0
    assert "endsolid" in stl
