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
from gen.discovery.first_principles import Axiom, derive  # noqa: E402
from gen.pipeline import assess_specification  # noqa: E402
from gen.seams import build_seam_certificate  # noqa: E402
from gen.visionary_ideas import ALL_VISIONARY_IDEAS  # noqa: E402

_HAS_CADQUERY = importlib.util.find_spec("cadquery") is not None

# the signature axis each grok-dreamed idea must auto-fire — proof GENESIS verified the physics the
# vision actually depends on. For Mars ISRU: the new domain validators + core structure.
_SIGNATURE = {
    "skyclaw": {"rotor_hover", "battery_endurance", "current_budget", "attitude_pd", "reach",
                "electric_actuator", "compute_budget"},
    "resostrider": {"swing_resonance", "joint_swing_torque", "zmp_dynamic", "reach",
                    "electric_actuator"},
    "forgehydra": {"hydraulic_cylinder", "hydraulic_flow", "reach", "compute_budget"},
    "mars_isru_o2_plant": {"isru_electrolysis_o2", "life_support_o2_balance"},
}

_IDS = [fn().run_id for fn, _ in ALL_VISIONARY_IDEAS]


@pytest.mark.parametrize("spec_fn,claims_fn", ALL_VISIONARY_IDEAS, ids=_IDS)
def test_visionary_idea_is_physics_verified(spec_fn, claims_fn):
    """The dreamed idea passes the δ-physics gate honestly: physics_verified, no uncomputable gap, no
    contradiction — and its signature axes (the physics the vision lives on) actually fired.
    For ISRU/LIFE: explicit DomainSeams looked up from VISIONARY_SEAMS and passed (avoids fallback)."""
    from gen.visionary_ideas import VISIONARY_SEAMS
    spec = spec_fn()
    claims = claims_fn()
    seams_fn = VISIONARY_SEAMS.get(spec.run_id)
    if seams_fn is not None:
        seams = seams_fn()
        cert = build_seam_certificate(spec, seams)
        a = assess_specification(spec, claims=claims, seam_certificate=cert)
    else:
        a = assess_specification(spec, claims=claims)
    fired = {c.validator for c in a.physics_checks}
    assert _SIGNATURE[spec.run_id] <= fired, f"{spec.run_id}: missing {_SIGNATURE[spec.run_id] - fired}"
    assert a.physics_gaps == [], f"{spec.run_id} has uncomputable gaps: {a.physics_gaps}"
    assert a.constraint_contradictions == []
    assert a.physics_ok and a.overall == "physics_verified"


@pytest.mark.parametrize("spec_fn,claims_fn", ALL_VISIONARY_IDEAS, ids=_IDS)
def test_visionary_idea_emits_real_artifacts(spec_fn, claims_fn, tmp_path):
    """emit_bundle writes the manual + BOM + (with the OCCT kernel) a watertight STL per printed part,
    nothing silently missing — the dream becomes owner-visible printable hardware.
    For the new ISRU plant: exercises full bundle path (honest gaps from internal cost-only seam_cert
    are ok; the explicit-seams path is proven in the physics test)."""
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
    assert len(ids) == 4 and len(set(ids)) == 4


def test_mars_isru_o2_plant_uses_isru_life_domains_and_explicit_seams():
    """Dedicated test (per 1-2 new tests rule): verifies new domains are detected, explicit
    DomainSeams declared in visionary_ideas cover the required pairs, and full assess with
    explicit cert (no fallback) yields physics_verified. Also exercises bundle path."""
    from gen.core.state import SeamDomain
    from gen.seams import domains_present, required_seam_pairs
    from gen.visionary_ideas import mars_isru_o2_plant_seams, mars_isru_o2_plant_spec, mars_isru_o2_plant_claims
    spec = mars_isru_o2_plant_spec()
    present = domains_present(spec)
    assert SeamDomain.ISRU in present, "ISRU domain must be used"
    assert SeamDomain.LIFE_SUPPORT in present, "LIFE_SUPPORT domain must be used"
    assert SeamDomain.MECHANICAL in present
    assert SeamDomain.COST in present

    req = required_seam_pairs(spec)
    assert any(set(p) == {SeamDomain.MECHANICAL, SeamDomain.ISRU} for p in req)
    assert any(set(p) == {SeamDomain.ELECTRICAL, SeamDomain.ISRU} for p in req)
    assert any(set(p) == {SeamDomain.ISRU, SeamDomain.COST} for p in req)

    # explicit seams cover exactly
    from gen.seams import _pair
    seams = mars_isru_o2_plant_seams()
    cert = build_seam_certificate(spec, seams)
    covered = {_pair(s.left_domain, s.right_domain) for s in cert.seams}
    for r in req:
        assert r in covered, f"missing seam coverage for required {r}"

    # assess with explicit (exercises assess path)
    claims = mars_isru_o2_plant_claims()
    a = assess_specification(spec, claims=claims, seam_certificate=cert)
    assert a.physics_ok and a.overall == "physics_verified"
    fired = {c.validator for c in a.physics_checks}
    assert "isru_electrolysis_o2" in fired
    assert "life_support_o2_balance" in fired

    # bundle path exercised (produces artifacts; internal cert may leave seam gaps reported honestly)
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        m = emit_bundle(spec, td)
        assert "BAUANLEITUNG.md" in m.written
        assert "bom.json" in m.written
        assert m.printed_parts  # at least the 2 printed reactor/hopper

    # first_principles integration for ISRU stoich (complete Genesis: discovery arm for multi-planetary)
    # Derive O2 from water * stoich_ratio * eff using bounded search + proof verification.
    axioms = [
        Axiom("water", 36.0, "input water mass kg"),
        Axiom("eff", 0.9, "process efficiency"),
        Axiom("r", 32.0 / 36.0, "stoichiometric O2/H2O mass ratio"),
    ]
    pt = derive(axioms, 29.0, target_name="o2", max_ops=2, tolerance=0.5)
    assert pt is not None, "first_principles derivation for ISRU yield must succeed"
    assert pt.proven
    assert "o2" in pt.target_name

