"""Three concepts a dreamer (grok-build, as visionary) invented, then GENESIS grounded: each runs
through the same gated machinery to an honest physics_verified verdict with real printable artifacts.
grok decided the WHAT (a flying manipulator, a resonance quadruped, an air-droppable hydraulic module);
GENESIS supplies the verified HOW and fires the signature axis each idea claims.

Offline, no LLM in the build path. STL needs the OCCT kernel; the assertion adapts honestly.
Run:  pytest tests/test_visionary_ideas.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.bundle import emit_bundle  # noqa: E402
from gen.pipeline import assess_specification  # noqa: E402
from gen.visionary_ideas import ALL_VISIONARY_IDEAS  # noqa: E402

# STL is producible in-process (cadquery here) OR via the isolated cad-venv bridge.
from gen.cad.cadquery_bridge import cad_available as _cad_bridge_available  # noqa: E402

_HAS_CADQUERY = (
    importlib.util.find_spec("cadquery") is not None or _cad_bridge_available()
)

# the signature axis each grok-dreamed idea must auto-fire — proof GENESIS verified the physics the
# vision actually depends on (a flying manipulator must fire the flight stack, a resonance walker the
# swing-resonance axis, a hydraulic module the hydraulic axes)
_SIGNATURE = {
    "skyclaw": {"rotor_hover", "battery_endurance", "current_budget", "attitude_pd", "reach",
                "electric_actuator", "compute_budget"},
    "resostrider": {"swing_resonance", "joint_swing_torque", "zmp_dynamic", "reach",
                    "electric_actuator"},
    "forgehydra": {"hydraulic_cylinder", "hydraulic_flow", "reach", "compute_budget"},
}

_IDS = [fn().run_id for fn, _ in ALL_VISIONARY_IDEAS]


@pytest.mark.parametrize("spec_fn,claims_fn", ALL_VISIONARY_IDEAS, ids=_IDS)
def test_visionary_idea_is_physics_verified(spec_fn, claims_fn):
    """The dreamed idea passes the δ-physics gate honestly: physics_verified, no uncomputable gap, no
    contradiction — and its signature axes (the physics the vision lives on) actually fired."""
    spec = spec_fn()
    a = assess_specification(spec, claims=claims_fn())
    fired = {c.validator for c in a.physics_checks}
    assert _SIGNATURE[spec.run_id] <= fired, f"{spec.run_id}: missing {_SIGNATURE[spec.run_id] - fired}"
    assert a.physics_gaps == [], f"{spec.run_id} has uncomputable gaps: {a.physics_gaps}"
    assert a.constraint_contradictions == []
    assert a.physics_ok and a.overall == "physics_verified"


@pytest.mark.parametrize("spec_fn,claims_fn", ALL_VISIONARY_IDEAS, ids=_IDS)
def test_visionary_idea_emits_real_artifacts(spec_fn, claims_fn, tmp_path):
    """emit_bundle writes the manual + BOM + (with the OCCT kernel) a watertight STL per printed part,
    nothing silently missing — the dream becomes owner-visible printable hardware."""
    spec = spec_fn()
    m = emit_bundle(spec, tmp_path)
    assert "BAUANLEITUNG.md" in m.written and "bom.json" in m.written
    assert m.printed_parts and m.bought_parts
    if _HAS_CADQUERY:
        stls = [w for w in m.written if w.endswith(".stl")]
        assert len(stls) == len(spec.components)        # one STL per printed component
        assert all((tmp_path / s).stat().st_size > 0 for s in stls)
        assert m.files_complete


def test_resostrider_actually_rides_its_natural_cadence():
    """The signature claim of the resonance walker is honest: the planned step cadence is at or BELOW
    the leg's own natural swing frequency (so the passive dynamics carry the swing), i.e. swing_resonance
    passes BECAUSE step_frequency <= natural_frequency — not by luck."""
    from gen.dynamics import swing_resonance_check
    from gen.visionary_ideas import resostrider_spec
    q = {x.measurand: x.value for x in resostrider_spec().quantities if x.measurand}
    r = swing_resonance_check(q["limb.inertia"], q["limb.mass"], q["limb.com_distance"],
                              q["gait.step_frequency"])
    assert r["ok"] and r["step_frequency_hz"] <= r["natural_frequency_hz"]
    assert r["safety_factor"] >= 1.0


def test_three_distinct_visionary_domains():
    ids = [fn().run_id for fn, _ in ALL_VISIONARY_IDEAS]
    assert len(ids) == 3 and len(set(ids)) == 3
