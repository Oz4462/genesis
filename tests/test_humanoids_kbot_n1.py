"""Tests for the K-Bot + Fourier-N1 engine validation, the MuJoCo stand harness, and N1 box feet.

These run REAL MuJoCo (headless) on the acquired K-Bot and Fourier-N1 MJCF models, so they skip cleanly
when MuJoCo or the assets are absent (mirrors the other in-engine test guards). Numbers asserted are the
honest engine outputs with tolerances — the load structure (DOF/mass) and the N1 box-feet stand result —
not hard-coded fictions. The K-Bot stand is intentionally NOT asserted to succeed: its measured outcome
is a documented topple (weak ankle), so we only assert the harness runs and reports an honest result.
"""

from __future__ import annotations

import math
import os

import pytest

from gen.humanoids import catalog
from gen.humanoids import insim_mujoco as mj
from gen.humanoids import mj_stand
from gen.humanoids import n1_feet

KBOT_MJCF = catalog.ASSETS["kbot"].model_path
N1_MJCF = catalog.ASSETS["fourier_n1"].model_path

_have_mujoco = mj.mujoco_available()
_have_kbot = KBOT_MJCF is not None and os.path.isfile(KBOT_MJCF)
_have_n1 = N1_MJCF is not None and os.path.isfile(N1_MJCF)

pytestmark = pytest.mark.skipif(
    not _have_mujoco, reason="MuJoCo not available in this environment"
)


# ── load + structure (spec-only → engine-validated) ──────────────────────────────────────────────

@pytest.mark.skipif(not _have_kbot, reason="K-Bot MJCF asset not present")
def test_kbot_loads_in_engine():
    lr = mj.load_structure("kbot", KBOT_MJCF)
    # 20 actuated hinge DOF + 1 free base, fully actuated (nu == 20), mass ~35.65 kg (spec ~34, +5%)
    assert lr.free_joints == 1
    assert lr.hinge_joints == 20
    assert lr.num_actuators == 20
    assert lr.actuated_hinge_dof == 20
    assert math.isclose(lr.total_mass_kg, 35.65, rel_tol=2e-2)
    # gravity wrench self-consistency: held free in space, base Fz ≈ m*g
    ps = mj.pose_statics("kbot", KBOT_MJCF)
    assert ps.base_wrench  # has a free base
    assert math.isclose(ps.base_wrench[2], ps.total_mass_kg * mj.STANDARD_GRAVITY, rel_tol=5e-3)


@pytest.mark.skipif(not _have_n1, reason="Fourier-N1 MJCF asset not present")
def test_n1_loads_in_engine():
    lr = mj.load_structure("fourier_n1", N1_MJCF)
    # 23 actuated hinge DOF + 1 free base (6 L-leg + 6 R-leg + 1 waist + 5 L-arm + 5 R-arm), nu == 23
    assert lr.free_joints == 1
    assert lr.hinge_joints == 23
    assert lr.num_actuators == 23
    assert math.isclose(lr.total_mass_kg, 39.73, rel_tol=2e-2)
    names = {j.name for j in lr.joints}
    assert "waist_yaw_joint" in names
    assert "left_knee_pitch_joint" in names and "right_ankle_pitch_joint" in names


# ── MuJoCo stand harness ─────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _have_kbot, reason="K-Bot MJCF asset not present")
def test_build_stand_scene_and_kbot_stand_runs_honestly(tmp_path):
    scene = mj_stand.build_stand_scene(
        "kbot", KBOT_MJCF, str(tmp_path / "kbot_stand.mjcf"))
    assert os.path.isfile(scene)
    # short run: assert the harness produces an honest, finite result (NOT that K-Bot holds — it topples)
    r = mj_stand.pd_stand("kbot", scene, standing_pose={}, position_servo=True,
                          default_kp=120, default_kd=6, seconds=1.0)
    assert r.finite
    assert 0.0 <= r.upright_seconds <= 1.0
    assert r.steps > 0
    assert r.mean_foot_contacts >= 0.0


@pytest.mark.skipif(not _have_n1, reason="Fourier-N1 MJCF asset not present")
def test_n1_box_feet_build_and_stand():
    # box feet require MjSpec + trimesh; skip if either is missing
    if not (n1_feet.mujoco_spec_available() and n1_feet.trimesh_available()):
        pytest.skip("MjSpec or trimesh not available")
    out = n1_feet.add_box_feet()
    assert os.path.isfile(out)
    # the box-feet model must still load with 23 actuators and now carry two colliding box soles
    import mujoco
    m = mujoco.MjModel.from_xml_path(out)
    assert int(m.nu) == 23
    box_soles = [g for g in range(m.ngeom)
                 if (mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, g) or "").endswith("box_sole")]
    assert len(box_soles) == 2
    # THE STAND: with box feet, N1 holds the full horizon from the gentle crouch (the verified result)
    scene = mj_stand.build_stand_scene(
        "fourier_n1", out, "/home/genesis/humanoid_assets/fourier_n1/model/scene/_test_stand.mjcf")
    crouch = {"left_knee_pitch_joint": 0.3, "right_knee_pitch_joint": 0.3,
              "left_hip_pitch_joint": -0.15, "right_hip_pitch_joint": -0.15,
              "left_ankle_pitch_joint": -0.15, "right_ankle_pitch_joint": -0.15}
    r = mj_stand.pd_stand("fourier_n1", scene, standing_pose=crouch, position_servo=True,
                          default_kp=200, default_kd=10, seconds=3.0, settle_drop=0.008)
    assert r.held_full_horizon, f"N1 box-feet crouch should hold; got {r.upright_seconds}s lean {r.max_lean_deg}"
    assert r.max_lean_deg < 20.0
    assert r.mean_foot_contacts > 5.0  # dense box contact (mesh feet give ~3-4)


# ── Asimov box feet (improves contact, honest non-sustained stand) ───────────────────────────────

from gen.humanoids import asimov_feet  # noqa: E402

_ASIMOV_ACT = asimov_feet.ASIMOV_ACTUATED
_have_asimov = os.path.isfile(_ASIMOV_ACT)


@pytest.mark.skipif(not _have_asimov, reason="Asimov actuated MJCF not present")
def test_asimov_box_feet_build_and_improves_stand():
    if not asimov_feet.mujoco_spec_available():
        pytest.skip("MjSpec not available")
    out = asimov_feet.add_box_feet()
    assert os.path.isfile(out)
    import mujoco
    import numpy as np
    m = mujoco.MjModel.from_xml_path(out)
    # actuators + mass preserved, two box soles added (centred under the CoM)
    assert int(m.nu) == 13
    assert math.isclose(float(sum(m.body_mass)), 32.371, rel_tol=5e-3)
    box_soles = [g for g in range(m.ngeom)
                 if (mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, g) or "").endswith("box_sole")]
    assert len(box_soles) == 2
    # honest stand check: the box-feet zero-pose stand lasts longer than the bare-capsule ~1.4 s, but is
    # NOT a sustained stand — assert it improves on ~1.4 s (does not assert a full hold, which it can't do)
    from gen.humanoids.mj_stand import _lowest_collision_z
    d = mujoco.MjData(m)
    aj = {}
    for a in range(m.nu):
        jnm = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, int(m.actuator_trnid[a, 0]))
        aj[jnm] = a
    floor = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, "floor")
    mujoco.mj_resetData(m, d)
    mujoco.mj_forward(m, d)
    low = _lowest_collision_z(m, d, floor)
    if low is not None:
        d.qpos[2] += (0.005 - low)
    mujoco.mj_forward(m, d)
    q0 = np.array(d.qpos[3:7])
    topple = -1
    for s in range(int(5.0 / m.opt.timestep)):
        for a in aj.values():
            d.ctrl[a] = 0.0
        mujoco.mj_step(m, d)
        w = abs(float(np.dot(d.qpos[3:7], [q0[0], -q0[1], -q0[2], -q0[3]])))
        lean = math.degrees(2 * math.acos(min(1.0, w)))
        if topple < 0 and lean > 30:
            topple = s
    upright_s = topple * m.opt.timestep if topple >= 0 else 5.0
    assert upright_s > 1.6, f"box feet should beat the ~1.4s bare-capsule stand; got {upright_s}s"
