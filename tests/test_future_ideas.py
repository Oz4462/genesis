"""Five forward-looking ideas run end-to-end through the SAME gated GENESIS machinery: each fires its
δ-physics axes to an honest physics_verified verdict (no gap, no contradiction) and emits a real
printable artifact bundle. Together they exercise the whole δ-axis library — flight, energy/current,
vision compute, hydraulics, and swing dynamics + ZMP balance — across five distinct domains.

Offline, no LLM. STL needs the OCCT kernel; the assertion adapts honestly to its presence.
Run:  pytest tests/test_future_ideas.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.bundle import emit_bundle  # noqa: E402
from gen.future_ideas import ALL_FUTURE_IDEAS  # noqa: E402
from gen.pipeline import assess_specification  # noqa: E402

# STL is producible in-process (cadquery here) OR via the isolated cad-venv bridge.
from gen.cad.cadquery_bridge import cad_available as _cad_bridge_available  # noqa: E402

_HAS_CADQUERY = (
    importlib.util.find_spec("cadquery") is not None or _cad_bridge_available()
)

# the signature axis each idea must auto-fire from its measurand tags (proof the idea exercises the
# physics it claims to, not just any check)
_SIGNATURE = {
    "delivery_drone": {"rotor_hover", "battery_endurance", "current_budget", "attitude_pd"},
    "home_battery": {"battery_endurance", "current_budget"},
    "harvest_arm": {"reach", "electric_actuator", "compute_budget", "inference_power",
                    "inference_latency"},
    "hydraulic_boom": {"hydraulic_cylinder", "hydraulic_flow", "reach"},
    "exo_knee": {"electric_actuator", "reach", "swing_resonance", "joint_swing_torque", "zmp_dynamic"},
}

_IDS = [fn().run_id for fn, _ in ALL_FUTURE_IDEAS]


@pytest.mark.parametrize("spec_fn,claims_fn", ALL_FUTURE_IDEAS, ids=_IDS)
def test_future_idea_is_physics_verified(spec_fn, claims_fn):
    """The idea passes the δ-physics gate honestly: physics_verified, no indicated-but-uncomputable
    gap, no constraint contradiction — and its SIGNATURE axes actually fired."""
    spec = spec_fn()
    a = assess_specification(spec, claims=claims_fn())
    fired = {c.validator for c in a.physics_checks}
    assert _SIGNATURE[spec.run_id] <= fired, f"{spec.run_id}: missing {_SIGNATURE[spec.run_id] - fired}"
    assert a.physics_gaps == [], f"{spec.run_id} has uncomputable gaps: {a.physics_gaps}"
    assert a.constraint_contradictions == []
    assert a.physics_ok and a.overall == "physics_verified"


@pytest.mark.parametrize("spec_fn,claims_fn", ALL_FUTURE_IDEAS, ids=_IDS)
def test_future_idea_emits_real_artifacts(spec_fn, claims_fn, tmp_path):
    """emit_bundle writes the manual + BOM + (with the OCCT kernel) a watertight STL for the printed
    part, with nothing silently missing — a real deliverable, owner-visible."""
    spec = spec_fn()
    m = emit_bundle(spec, tmp_path)
    assert "BAUANLEITUNG.md" in m.written and "bom.json" in m.written
    assert m.printed_parts and m.bought_parts          # both a printed part and a buy-list
    if _HAS_CADQUERY:
        stls = [w for w in m.written if w.endswith(".stl")]
        assert stls and all((tmp_path / s).stat().st_size > 0 for s in stls)
        assert m.files_complete                        # every producible deliverable written


def test_five_distinct_future_domains():
    """Sanity: exactly five ideas, all distinct run_ids — five domains, not one repeated."""
    ids = [fn().run_id for fn, _ in ALL_FUTURE_IDEAS]
    assert len(ids) == 5 and len(set(ids)) == 5
