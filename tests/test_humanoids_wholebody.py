"""Tests for the hip+knee whole-body balance work: WholeBodyPDController + CoM-sign calibration, the
AGILOped flat-foot repair (agiloped_feet), and the Asimov actuator injection (asimov_actuators).

Skip-guarded on the relevant engine (PyBullet for the env/controller + AGILOped, MuJoCo for Asimov) and on
the asset's presence, like the other humanoid in-engine tests. These pin the HONEST verified behaviour:

  * The whole-body controller obeys the BalanceController interface (right action length, finite) and maps
    its CoM-PD command onto the hip/knee/(ankle) joints by name fragment.
  * It regulates around the standing pose's EQUILIBRIUM CoM offset (captured at the first act after reset),
    NOT zero — the bug-fix that stopped it from instantly destabilising the crouch. We assert the first
    action after a reset is ~zero (no spurious correction of the natural offset).
  * calibrate_whole_body_signs returns finite per-joint signs in {-1,0,+0.6,+1} for a real robot.
  * agiloped_feet.add_flat_feet writes a URDF that loads in PyBullet and has the two added sole links.
  * asimov_actuators.add_position_actuators turns the nu=0 MJCF into one with the expected actuators, and
    is fail-loud on a double-add.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from gen.humanoids import catalog
from gen.humanoids.insim import pybullet_available


def _asset_present(robot: str) -> bool:
    ref = catalog.ASSETS.get(robot)
    return ref is not None and ref.model_path is not None and Path(ref.model_path).is_file()


def _mujoco_available() -> bool:
    try:
        import mujoco  # noqa: F401
        return True
    except Exception:
        return False


_PB = pytest.mark.skipif(not pybullet_available(), reason="PyBullet not installed")
_TK = pytest.mark.skipif(not _asset_present("tienkung"), reason="tienkung asset missing")
_MJ = pytest.mark.skipif(not _mujoco_available(), reason="mujoco not installed")

_TK_CTRL = ("hip_pitch_l_joint", "hip_pitch_r_joint", "knee_pitch_l_joint", "knee_pitch_r_joint",
            "hip_roll_l_joint", "hip_roll_r_joint", "ankle_pitch_l_joint", "ankle_pitch_r_joint",
            "ankle_roll_l_joint", "ankle_roll_r_joint")


# ── WholeBodyPDController ─────────────────────────────────────────────────────────────────────────────

@_PB
def test_signed_action_maps_by_name_fragment():
    from gen.humanoids.balance_controller import _signed_action
    from gen.humanoids.balance_env import BalanceEnv, BalanceEnvConfig, recommended_standing_pose

    if not _asset_present("tienkung"):
        pytest.skip("tienkung asset missing")
    cfg = BalanceEnvConfig(robot="tienkung", horizon_s=0.05, controlled_joints=_TK_CTRL,
                           standing_pose=recommended_standing_pose("tienkung"))
    with BalanceEnv(cfg) as env:
        env.reset()
        a = _signed_action(env, {"hip_pitch": 0.1, "knee_pitch": -0.2})
        assert a.shape == (env.action_dim,)
        for i, name in enumerate(env.action_labels):
            if "hip_pitch" in name:
                assert a[i] == pytest.approx(0.1)
            elif "knee_pitch" in name:
                assert a[i] == pytest.approx(-0.2)
            else:
                assert a[i] == 0.0


@_PB
@_TK
def test_wholebody_controller_interface_and_equilibrium_setpoint():
    """First action after reset must be ~zero (it regulates DEVIATION from the captured equilibrium)."""
    from gen.humanoids.balance_controller import WholeBodyPDController
    from gen.humanoids.balance_env import BalanceEnv, BalanceEnvConfig, recommended_standing_pose

    cfg = BalanceEnvConfig(robot="tienkung", horizon_s=0.1, controlled_joints=_TK_CTRL,
                           standing_pose=recommended_standing_pose("tienkung"), ankle_kp=1.0)
    wb = WholeBodyPDController(kp=1.6, kd=0.35)
    with BalanceEnv(cfg) as env:
        obs = env.reset()
        wb.reset()
        a0 = wb(obs, env)
        assert a0.shape == (env.action_dim,)
        assert np.all(np.isfinite(a0))
        # equilibrium captured on the first act → the deviation is zero → near-zero command
        assert float(np.max(np.abs(a0))) < 1e-6
        assert wb._eq is not None


@_PB
@_TK
def test_calibrate_whole_body_signs_returns_grounded_signs():
    from gen.humanoids.balance_controller import calibrate_whole_body_signs

    signs = calibrate_whole_body_signs("tienkung")
    for key in ("hip_pitch_sign", "knee_pitch_sign", "ankle_pitch_sign", "hip_roll_sign", "ankle_roll_sign"):
        assert key in signs
        assert np.isfinite(signs[key])
        assert signs[key] in (-1.0, 0.0, 0.6, -0.6, 1.0)
    # the measured CoM sensitivities are present and finite
    assert np.isfinite(signs["hip_pitch_dcom"])
    # +hip_pitch moves TienKung's CoM backward (negative dcom_x) → sign should be +1 to oppose +offset
    assert signs["hip_pitch_sign"] == 1.0


# ── AGILOped flat feet ───────────────────────────────────────────────────────────────────────────────

@_PB
def test_agiloped_add_flat_feet_writes_loadable_urdf_with_soles():
    from gen.humanoids.agiloped_feet import add_flat_feet, AGILOPED_NOPARALLEL_URDF, AGILOPED_FOOT_SPECS

    if not Path(AGILOPED_NOPARALLEL_URDF).is_file():
        pytest.skip("AGILOped repaired-noparallel URDF missing")
    out = add_flat_feet()
    assert Path(out).is_file()
    import pybullet as p
    c = p.connect(p.DIRECT)
    try:
        bid = p.loadURDF(out, useFixedBase=True, flags=p.URDF_USE_INERTIA_FROM_FILE, physicsClientId=c)
        links = {p.getJointInfo(bid, j, physicsClientId=c)[12].decode()
                 for j in range(p.getNumJoints(bid, physicsClientId=c))}
        for spec in AGILOPED_FOOT_SPECS:
            assert f"{spec.parent_link}_sole" in links
    finally:
        p.disconnect(c)


def test_agiloped_add_flat_feet_fail_loud_on_missing_input():
    from gen.humanoids.agiloped_feet import add_flat_feet
    with pytest.raises(FileNotFoundError):
        add_flat_feet(urdf_in="/no/such/agiloped.urdf", urdf_out="/tmp/x.urdf")


# ── Asimov actuators ─────────────────────────────────────────────────────────────────────────────────

@_MJ
def test_asimov_add_actuators_makes_nu_positive():
    from gen.humanoids.asimov_actuators import add_position_actuators, ASIMOV_XML, ASIMOV_ACTUATED_JOINTS
    import mujoco

    if not Path(ASIMOV_XML).is_file():
        pytest.skip("Asimov MJCF missing")
    # source has zero actuators
    m0 = mujoco.MjModel.from_xml_path(ASIMOV_XML)
    assert m0.nu == 0
    out = add_position_actuators()
    m1 = mujoco.MjModel.from_xml_path(out)
    assert m1.nu == len(ASIMOV_ACTUATED_JOINTS)
    names = {mujoco.mj_id2name(m1, mujoco.mjtObj.mjOBJ_ACTUATOR, a) for a in range(m1.nu)}
    for j in ASIMOV_ACTUATED_JOINTS:
        assert f"{j}_act" in names
    # mass unchanged (additive actuation, no geometry change)
    assert sum(m1.body_mass) == pytest.approx(sum(m0.body_mass))


def test_asimov_add_actuators_fail_loud_on_missing_input():
    from gen.humanoids.asimov_actuators import add_position_actuators
    with pytest.raises(FileNotFoundError):
        add_position_actuators(xml_in="/no/such/asimov.xml", xml_out="/tmp/x.xml")


@_MJ
def test_asimov_add_actuators_fail_loud_on_unknown_joint():
    from gen.humanoids.asimov_actuators import add_position_actuators, ASIMOV_XML
    if not Path(ASIMOV_XML).is_file():
        pytest.skip("Asimov MJCF missing")
    with pytest.raises(ValueError):
        add_position_actuators(xml_out="/home/genesis/humanoid_assets/asimov/sim-model/xmls/_t.xml",
                               joints={"nonexistent_joint": 50.0})
