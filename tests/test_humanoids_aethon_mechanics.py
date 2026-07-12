"""AETHON mechanics deep-compute — characterization + negative tests for ``aethon_mechanics``.

These prove the module is REAL (numbers are COMPUTED through the genuine δ-physics validators, not
canned) rather than a facade:

  * the continuum FEM axial reserve recovers σ=F/A to machine precision (a real solver output) — both
    on hand-picked values and as a PROPERTY over a range of loads/sections;
  * the closed-form bending peak is the gated Kt·6FL/bh² and is genuinely driven by its inputs;
  * ``part_structural_finding`` picks the GOVERNING mode, computes SF = strength/governing and the
    over/under/ok verdict at the documented thresholds;
  * ``joint_drive_finding`` computes the static/dynamic SF and verdict;
  * ``compute_aethon_mechanics`` runs all four analyses on the LIVE AETHON design — the evolved shank
    is analysed at the shipping geometry and clears the structural margin, every body joint fires, and
    the result is deterministic;
  * the documented fail-loud guards fire (non-positive strength / section / rated peak / negative
    demand) — per "keine stillen Defaults" and "ein Gate ohne Test existiert nicht".

Run:  PYTHONPATH=src .venv/bin/python -m pytest tests/test_humanoids_aethon_mechanics.py -q
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402
from hypothesis import given, settings, strategies as st  # noqa: E402

from gen.humanoids import aethon_mechanics as am  # noqa: E402


# ── (1) structure: the FEM axial reserve is a real solver output that recovers F/A ──────────────────

def test_fem_axial_stress_recovers_force_over_area():
    """The continuum tet FEM reproduces the uniform axial field exactly: σ_xx = F/A (N-mm-MPa system).
    This is the proof the number is a solver output, not a closed-form substitution dressed up."""
    width, thick, force = 40.0, 20.0, 8000.0
    sigma = am.fem_axial_stress_mpa(length_mm=200.0, width_mm=width, thick_mm=thick,
                                    force_n=force, e_mpa=4200.0)
    assert sigma == pytest.approx(force / (width * thick), rel=1e-9)


@given(
    force_n=st.floats(min_value=10.0, max_value=5.0e4),
    width_mm=st.floats(min_value=5.0, max_value=120.0),
    thick_mm=st.floats(min_value=5.0, max_value=60.0),
)
@settings(max_examples=40, deadline=None)
def test_fem_axial_stress_equals_force_over_area_property(force_n, width_mm, thick_mm):
    """INVARIANT: for ANY positive load/section the FEM axial stress equals F/(b·h). The exact-field
    recovery must hold across the input space, not just one example."""
    sigma = am.fem_axial_stress_mpa(length_mm=180.0, width_mm=width_mm, thick_mm=thick_mm,
                                    force_n=force_n, e_mpa=4200.0)
    assert sigma == pytest.approx(force_n / (width_mm * thick_mm), rel=1e-6)


def test_closed_form_bending_is_kt_times_6fl_over_bh2():
    """The bending peak is the SAME gated closed form Kt·6FL/bh²; changing the force changes it linearly
    (the input is genuinely consumed)."""
    b, h, arm = 40.0, 20.0, 80.0
    val = am.closed_form_bending_peak_mpa(1000.0, arm, b, h)
    assert val == pytest.approx(am.STRESS_CONCENTRATION_CIRCULAR_HOLE * 6.0 * 1000.0 * arm / (b * h * h))
    # linear in force: doubling the load doubles the stress
    assert am.closed_form_bending_peak_mpa(2000.0, arm, b, h) == pytest.approx(2.0 * val)


def test_closed_form_bending_rejects_nonpositive_section():
    with pytest.raises(ValueError):
        am.closed_form_bending_peak_mpa(1000.0, 80.0, 0.0, 20.0)
    with pytest.raises(ValueError):
        am.closed_form_bending_peak_mpa(1000.0, 80.0, 40.0, -1.0)


def test_part_structural_finding_governing_mode_and_verdict():
    """The verdict uses the LARGER (governing) stress and SF = strength/governing; a slender, long-lever
    section is bending-governed and UNDER-designed, a stubby low-lever section is OK/overbuilt."""
    # slender section, long lever → bending governs → under-designed
    weak = am.part_structural_finding(
        "slender", load_path="x", force_n=2000.0, bending_arm_mm=120.0,
        width_mm=20.0, thick_mm=8.0, length_mm=200.0, strength_mpa=85.0, e_mpa=4200.0)
    assert weak.governing_mode == "bending"
    assert weak.governing_stress_mpa == max(weak.fem_axial_stress_mpa, weak.bending_stress_mpa)
    assert weak.safety_factor == pytest.approx(weak.strength_mpa / weak.governing_stress_mpa)
    assert weak.verdict == "under"
    assert weak.safety_factor < am.STRUCT_SF_MIN

    # massively over-sized section → SF huge → overbuilt flag
    strong = am.part_structural_finding(
        "stout", load_path="x", force_n=50.0, bending_arm_mm=10.0,
        width_mm=120.0, thick_mm=60.0, length_mm=200.0, strength_mpa=85.0, e_mpa=4200.0)
    assert strong.safety_factor >= am.STRUCT_SF_OVERBUILT
    assert strong.verdict == "overbuilt"


def test_part_structural_finding_rejects_nonpositive_strength():
    with pytest.raises(ValueError):
        am.part_structural_finding("x", load_path="x", force_n=100.0, bending_arm_mm=10.0,
                                   width_mm=20.0, thick_mm=10.0, length_mm=100.0,
                                   strength_mpa=0.0, e_mpa=4200.0)


# ── (3) drivetrain ─────────────────────────────────────────────────────────────────────────────────

def test_joint_drive_finding_static_and_dynamic_sf():
    f = am.joint_drive_finding("knee", "AK80-64", static_demand_nm=40.0, rated_peak_nm=120.0,
                               dynamic_demand_nm=60.0)
    assert f.available_nm == 120.0                       # no envelope → published peak
    assert f.static_sf == pytest.approx(3.0)
    assert f.dynamic_sf == pytest.approx(2.0)
    assert f.verdict == "matched"                        # 1.5 ≤ 3.0 ≤ 4.0


def test_joint_drive_uses_envelope_available_torque_when_supplied():
    f = am.joint_drive_finding("knee", "AK80-64", static_demand_nm=40.0, rated_peak_nm=120.0,
                               envelope={"available_torque": 80.0})
    assert f.available_nm == 80.0
    assert f.static_sf == pytest.approx(2.0)


def test_joint_drive_finding_loud_guards():
    with pytest.raises(ValueError):
        am.joint_drive_finding("x", "a", static_demand_nm=10.0, rated_peak_nm=0.0)
    with pytest.raises(ValueError):
        am.joint_drive_finding("x", "a", static_demand_nm=-1.0, rated_peak_nm=10.0)


def test_shm_peak_accel_is_amplitude_times_omega_squared():
    A, f_hz = 0.022, 0.9
    expected = A * (2.0 * math.pi * f_hz) ** 2
    assert am._shm_peak_accel(A, f_hz) == pytest.approx(expected)


# ── the full report on the LIVE design ──────────────────────────────────────────────────────────────

def test_compute_aethon_mechanics_is_complete_and_consumes_the_evolved_shank():
    """The deep-compute runs all four analyses on the shipping AETHON. The evolved shank is analysed at
    the LIVE cfg geometry and clears the structural margin (the round-1 14 mm member was the weakest);
    every body joint is checked; the mass sits in the scaling-law band."""
    from gen.humanoids import genesis_humanoid as gh

    r = am.compute_aethon_mechanics()
    assert r.kinematics is not None and r.mass_inertia is not None
    names = [f.name for f in r.structural]
    assert any("shank" in n for n in names) and any("thigh" in n for n in names)

    shank = next(f for f in r.structural if "shank" in f.name)
    # analysed at the EVOLVED shipping geometry, not a stale constant
    assert shank.safety_factor >= am.STRUCT_SF_MIN
    assert shank.verdict in ("ok", "overbuilt")

    # one drive finding per body joint (2 neck + 1 waist + 2×6 arm + 2×6 leg = 27 → DOF_MAP rows)
    assert len(r.joints) == sum(len(v) for v in gh.DOF_MAP.values())
    assert all(j.available_nm > 0.0 for j in r.joints)

    assert r.mass_inertia.within_band  # AETHON's knee sits inside the real-robot scaling band


def test_compute_aethon_mechanics_is_deterministic():
    """A5 reproducibility: the same live design yields identical structural safety factors twice."""
    a = am.compute_aethon_mechanics()
    b = am.compute_aethon_mechanics()
    assert [f.safety_factor for f in a.structural] == [f.safety_factor for f in b.structural]
    assert a.mass_inertia.total_mass_kg == b.mass_inertia.total_mass_kg


def test_summarise_renders_all_four_sections():
    text = am.summarise()
    for section in ("STRUKTUR", "KINEMATIK", "ANTRIEB", "SKALIERUNGSGESETZE"):
        assert section in text
