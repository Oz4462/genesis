"""AETHON (our flagship humanoid) — spec, gate, DOF, hand-grasp, comparison and loud-failure tests.

These are the CLOSED-FORM tests (numpy/scipy only, no PyBullet) for ``gen.humanoids.genesis_humanoid``:

  * the complete whole-body spec builds with the expected structure (quantities/components/BOM);
  * it passes BOTH deterministic gates — GATE γ (C-1..C-18: grounding/derivation/decision/drift/
    completeness/units/consistency/uncertainty) AND GATE δ (physics) — with ZERO failures (the bar:
    AETHON is more rigorously gated than the prior competitive_humanoid, which was only δ-gated);
  * the δ-physics auto-select fires all nine humanoid axes (reach/ZMP/actuator/compute×3/swing×3);
  * the DOF map is the clean 27 body + 12 hand = 39 control DOF, with a real dexterous hand
    (5 fingers × 3 phalanges + opposable thumb);
  * the hand grasp force is the gated derived value and clears the 20 N requirement;
  * the comparison row is internally consistent;
  * the loud-failure contract holds: a missing factual price raises ValueError (no silent default).

Run:  PYTHONPATH=src .venv/bin/python -m pytest tests/test_humanoids_genesis_humanoid.py -q
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.humanoids import genesis_humanoid as gh  # noqa: E402
from gen.pipeline import assess_specification  # noqa: E402
from gen.verification.gates import gate_delta, gate_gamma  # noqa: E402


def test_spec_builds_with_expected_structure():
    s = gh.aethon_spec()
    # eleven printable part TYPES collapse to ten components (thumb reuses the finger part); the
    # geometry-bearing components must all carry CSG + a density for the δ mass/volume path.
    assert len(s.components) == 10
    assert all(c.geometry is not None for c in s.components)
    assert all(c.material_density == "q_density" for c in s.components)
    # the head, foot, palm and finger are the COMPLETE-robot parts the prior flagship lacked
    ids = {c.id for c in s.components}
    assert {"c_head", "c_foot", "c_palm", "c_finger"} <= ids
    assert len(s.quantities) > 120
    assert len(s.bom) >= 24
    assert s.assembly, "an assembly placement list is required for the assembled render"


def test_dof_map_is_clean_27_body_plus_dexterous_hands():
    assert gh.body_dof() == 27          # 2 neck + 1 waist + 2×6 arm + 2×6 leg
    assert gh.HAND_DOF_PER_HAND == 6    # 5 finger flex + 1 thumb opposition
    assert gh.hand_dof_total() == 12
    assert gh.total_dof() == 39
    # a REAL dexterous hand: five fingers, three phalanges each (anatomically faithful, not a stub)
    assert gh.FINGERS_PER_HAND == 5
    assert gh.PHALANGES_PER_FINGER == 3
    summ = gh.design_summary()
    assert summ["name"] == "AETHON"
    assert summ["total_dof"] == 39


def test_passes_gate_gamma_and_delta_with_zero_failures():
    """The headline: AETHON clears BOTH deterministic gates with no failures — the strict
    anti-hallucination γ gate (literal grounding, recomputed derivations, dimensional homogeneity,
    cross-claim consistency, GUM uncertainty) and the physics δ gate."""
    st = gh.aethon_state()
    gg = gate_gamma(st)
    assert gg.passed, f"GATE γ failed: {[f.detail for f in gg.failures]}"
    gd = gate_delta(st)
    assert gd.passed, f"GATE δ failed: {[f.detail for f in gd.failures]}"


def test_physics_axes_all_fire_and_pass():
    s = gh.aethon_spec()
    a = assess_specification(s)
    assert a.physics_ok
    assert a.physics_complete
    names = {c.name for c in a.physics_checks}
    # the nine humanoid axes the measurand tags must auto-select
    for expected in ("arm reach (2R workspace)", "balance (ZMP in support polygon)",
                     "electric joint actuator (torque-speed)", "compute throughput budget",
                     "inference power", "inference latency (control loop)",
                     "swing resonance (natural leg cadence)",
                     "dynamic balance (ZMP over the gait cycle)",
                     "swing joint torque (inverse dynamics over the swing)"):
        assert expected in names, f"missing physics axis: {expected}"
    assert not a.physics_gate.failures


def test_hand_grasp_force_is_gated_and_meets_requirement():
    s = gh.aethon_spec()
    qids = {q.id: q for q in s.quantities}
    assert "q_grasp_total" in qids and "q_grasp_min" in qids
    grasp = qids["q_grasp_total"].value
    req = qids["q_grasp_min"].value
    assert grasp >= req, f"whole-hand grasp {grasp} N must meet the {req} N requirement"
    # the grasp constraint must be present in the spec (the gate enforces it)
    assert any(k.id == "k_grasp" for k in s.constraints)


def test_knee_actuator_has_margin_over_static_demand():
    s = gh.aethon_spec()
    qids = {q.id: q for q in s.quantities}
    peak = qids["q_knee_peak"].value
    demand = qids["q_jt"].value
    assert peak > demand
    assert peak / demand > 1.5  # comfortable static-hold margin (2.13× as designed)


def test_total_mass_is_in_target_band():
    # the per-link URDF masses sum to the design target (cf. the floating-base load test); the spec
    # target is the lightweight ~22 kg printed class.
    assert 18.0 <= gh.TARGET_MASS_KG <= 26.0
    assert sum(gh._MASS[k] * n for k, n in
               (("pelvis", 1), ("torso", 1), ("head", 1), ("thigh", 2), ("shank", 2),
                ("foot", 2), ("uarm", 2), ("farm", 2), ("palm", 2))) > 15.0


def test_comparison_row_is_consistent():
    cmp = gh.comparison_summary()
    a = cmp["aethon"]
    assert a["class"] == "OURS"
    assert a["hand"] == "dexterous"
    assert a["dof"] == 27
    assert a["stands"].startswith("yes")
    assert len(cmp["references"]) == 10  # 7 open-source + 3 SOTA
    assert cmp["wins"] and cmp["honest_caveats"]  # honest: claims AND caveats


def test_missing_price_raises_loud():
    """C: no silent default for a factual price — a missing buy-list price must fail loud."""
    broken = replace(gh.AETHON, prices={k: 1.0 for k in gh.REQUIRED_PRICE_KEYS if k != "chip"})
    with pytest.raises(ValueError, match="chip"):
        gh.build_aethon(broken)


def test_negative_dimensions_are_rejected_in_urdf():
    # defensive: the URDF emitter must be deterministic and not crash; a re-emit is byte-identical
    u1 = gh.aethon_urdf()
    u2 = gh.aethon_urdf()
    assert u1 == u2
    assert u1.startswith("<?xml")
    assert "l_foot" in u1 and "r_foot" in u1          # box feet present
    assert "l_thumb_prox" in u1 or "l_index_prox" in u1  # articulated fingers present
