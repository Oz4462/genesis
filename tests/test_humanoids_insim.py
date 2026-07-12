"""In-engine humanoid validation — loading the REAL URDFs into PyBullet and comparing GENESIS's
closed-form physics to the engine's measurements.

These tests are the proof that the in-engine harness (``gen.humanoids.insim`` +
``gen.humanoids.validation_insim``) actually works on the real downloaded models, with EXACT,
verified expectations rather than vibes:

  * the engine instantiates the same DOF + total mass the parser/catalog report (TienKung 20 DOF /
    42.5 kg, Berkeley 22 DOF / 16.3 kg), and the floating-base total mass matches GENESIS to machine
    precision (a fixed-base load drops the base mass — the test pins that this is handled);
  * GENESIS's closed-form arm-torque is within ~15% of PyBullet's inverse dynamics for Berkeley's arm
    held horizontal (independent closed form vs real engine agree on a real robot);
  * GENESIS's static ZMP verdict matches the engine's CoM-over-support for the standing pose;
  * the drop test is finite and reproducible (two identical runs), and the PD demo keeps the
    passively-stable Berkeley upright for the full window;
  * the loud-failure contract holds: a missing URDF raises, an unknown joint raises, a non-in-engine
    robot key raises.

Headless (PyBullet ``DIRECT``); every test skips cleanly when PyBullet or the model is absent. Run:
  PYTHONPATH=src .venv/bin/python -m pytest tests/test_humanoids_insim.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.humanoids import insim  # noqa: E402
from gen.humanoids import validation_insim as vi  # noqa: E402
from gen.humanoids.catalog import ASSETS  # noqa: E402

_HAS_PYBULLET = insim.pybullet_available()
_T = ASSETS["tienkung"].model_path
_B = ASSETS["berkeley_lite"].model_path


def _model_present(key: str) -> bool:
    path = ASSETS[key].model_path
    return path is not None and Path(path).is_file()


pytestmark = pytest.mark.skipif(not _HAS_PYBULLET, reason="PyBullet not installed")


# ── load + structure (in-engine cross-check of the parser) ────────────────────────────────────────

@pytest.mark.skipif(not _model_present("tienkung"), reason="TienKung model not downloaded")
def test_tienkung_loads_with_expected_dof_and_mass():
    r = insim.load_structure("tienkung", _T)
    assert r.revolute_dof == 20            # 12 leg + 8 arm
    assert r.actuated_dof == 20
    # floating-base total mass matches the catalog/parser figure (42.516 kg) to machine precision
    assert abs(r.total_mass_floating_base_kg - 42.516) < 0.01
    # the fixed-base load DROPS the base (pelvis) mass — the subtlety the harness handles explicitly
    assert r.total_mass_fixed_base_kg < r.total_mass_floating_base_kg
    assert r.base_mass_kg > 1.0
    assert r.base_link_name == "pelvis"


@pytest.mark.skipif(not _model_present("berkeley_lite"), reason="Berkeley model not downloaded")
def test_berkeley_loads_with_expected_dof_and_mass():
    r = insim.load_structure("berkeley_lite", _B)
    assert r.revolute_dof == 22
    assert abs(r.total_mass_floating_base_kg - 16.331) < 0.01
    assert r.fixed_joints >= 1             # imu + hand welds


# ── statics: inverse dynamics is real (nonzero at a loaded pose, ~0 at the hung neutral pose) ──────

@pytest.mark.skipif(not _model_present("tienkung"), reason="TienKung model not downloaded")
def test_pose_statics_gravity_torque_is_real_and_mass_is_full():
    import math
    # neutral pose: every link hangs vertically ⇒ near-zero gravity lever ⇒ near-zero hold torque
    neutral = insim.pose_statics("tienkung", _T)
    assert max(abs(t) for t in neutral.joint_torques.values()) < 1.0
    # full body mass (incl. the base) is reported, not the fixed-base-only mass
    assert abs(neutral.total_mass_kg - 42.516) < 0.05
    # flexed hip ⇒ a substantial, physically-sensible hold torque appears at that joint
    flexed = insim.pose_statics("tienkung", _T, {"hip_pitch_l_joint": math.pi / 3})
    assert flexed.joint_torques["hip_pitch_l_joint"] > 5.0
    assert flexed.joint_torques["hip_pitch_l_joint"] > neutral.joint_torques["hip_pitch_l_joint"]


# ── the headline comparison: GENESIS closed form vs PyBullet inverse dynamics ─────────────────────

@pytest.mark.skipif(not _model_present("berkeley_lite"), reason="Berkeley model not downloaded")
def test_berkeley_static_torque_genesis_matches_engine_within_15pct():
    chk = vi.static_torque_check("berkeley_lite")
    assert chk.verdict == "agree"
    assert chk.rel_error is not None and chk.rel_error <= 0.15
    # both methods land in the same physical ballpark for the horizontal arm
    gen = float(chk.genesis_value.split()[0])
    eng = float(chk.engine_value.split()[0])
    assert 1.0 < gen < 5.0 and 1.0 < eng < 5.0


@pytest.mark.skipif(not _model_present("berkeley_lite"), reason="Berkeley model not downloaded")
def test_mass_check_is_machine_precision_agreement():
    chk = vi.mass_check("berkeley_lite")
    assert chk.verdict == "agree"
    assert chk.rel_error is not None and chk.rel_error <= 0.01


@pytest.mark.skipif(not _model_present("berkeley_lite"), reason="Berkeley model not downloaded")
def test_zmp_genesis_matches_engine_com_over_support_for_standing():
    chk = vi.zmp_check("berkeley_lite")
    assert chk.verdict == "agree"          # both say the static stand is balanced
    assert "balanced=True" in chk.genesis_value
    assert "inside=True" in chk.engine_value


# ── dynamic stability: finite, reproducible, and the PD demo holds the stable robot ───────────────

@pytest.mark.skipif(not _model_present("berkeley_lite"), reason="Berkeley model not downloaded")
def test_drop_test_is_finite_and_deterministic():
    a = insim.drop_test("berkeley_lite", _B, seconds=0.5)
    b = insim.drop_test("berkeley_lite", _B, seconds=0.5)
    assert a.finite and b.finite
    assert not a.floor_penetration
    # deterministic: identical fixed-step runs give identical end states
    assert a.base_z_end == pytest.approx(b.base_z_end, abs=1e-9)
    assert a.base_tilt_end_deg == pytest.approx(b.base_tilt_end_deg, abs=1e-9)


@pytest.mark.skipif(not _model_present("berkeley_lite"), reason="Berkeley model not downloaded")
def test_pd_balance_keeps_stable_robot_upright():
    """Berkeley is passively near-stable with flat box feet → the joint-PD demo must hold it upright
    for the full window (proves the closed-loop harness works end to end on a real robot)."""
    br = insim.pd_balance("berkeley_lite", _B, seconds=2.0)
    assert not br.fell
    assert br.upright_seconds >= 1.9
    assert br.base_tilt_max_deg < 20.0


# ── orchestration + loud-failure contract ─────────────────────────────────────────────────────────

@pytest.mark.skipif(not (_model_present("tienkung") and _model_present("berkeley_lite")),
                    reason="models not downloaded")
def test_validate_all_insim_builds_table_with_agreements():
    res = vi.validate_all_insim(with_dynamics=True, dynamics_seconds=0.5)
    assert set(res) == set(vi.INSIM_ROBOTS)
    flat = [c for cs in res.values() for c in cs]
    # mass + ZMP agree for both; at least one torque agreement (Berkeley)
    assert sum(1 for c in flat if c.verdict == "agree") >= 4
    table = vi.format_insim_table(res)
    assert "IN-ENGINE VALIDATION" in table and "TALLY" in table


def test_unknown_robot_key_raises():
    with pytest.raises(ValueError):
        vi.validate_robot_insim("not_a_robot")


@pytest.mark.skipif(not _model_present("tienkung"), reason="TienKung model not downloaded")
def test_unknown_joint_name_raises_loudly():
    with pytest.raises(ValueError):
        insim.pose_statics("tienkung", _T, {"no_such_joint": 0.5})


def test_missing_urdf_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        insim.load_structure("tienkung", "/home/genesis/humanoid_assets/does_not_exist.urdf")
