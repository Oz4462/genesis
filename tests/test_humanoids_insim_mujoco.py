"""Tests for gen.humanoids.insim_mujoco — the MuJoCo in-engine validation path (Asimov MJCF).

These run REAL MuJoCo (headless, the model's own timestep) on the downloaded Asimov v1 model, so they
are skipped cleanly when MuJoCo or the asset is absent (mirrors test_humanoids_insim.py's pybullet
guards). Numbers asserted are the honest engine outputs, with tolerances, not hard-coded fictions.
"""

from __future__ import annotations

import math
import os

import pytest

from gen.humanoids import catalog
from gen.humanoids import insim_mujoco as mj

ASIMOV_MJCF = catalog.ASSETS["asimov"].model_path

_have_mujoco = mj.mujoco_available()
_have_model = ASIMOV_MJCF is not None and os.path.isfile(ASIMOV_MJCF)
pytestmark = pytest.mark.skipif(
    not (_have_mujoco and _have_model),
    reason="MuJoCo and/or the Asimov MJCF asset not available in this environment",
)


def test_mujoco_available_is_bool():
    # the guard itself must never raise and must be a plain bool (callers branch on it)
    assert isinstance(mj.mujoco_available(), bool)


def test_load_structure_matches_catalog():
    lr = mj.load_structure("asimov", ASIMOV_MJCF)
    # in-engine structure cross-check against the parsed catalog figures (27 hinge + free base, ~32.37 kg)
    assert lr.nbody == 29
    assert lr.free_joints == 1
    assert lr.hinge_joints == 27
    assert lr.njnt == 28
    assert lr.actuated_hinge_dof == 27
    # the Asimov MJCF defines NO actuators — this is the documented scope limit, assert it explicitly
    assert lr.num_actuators == 0
    assert lr.nq == 34 and lr.nv == 33
    assert math.isclose(lr.total_mass_kg, 32.3713, rel_tol=1e-3)
    # every joint carries a non-empty name and a known type
    assert all(j.name for j in lr.joints)
    assert {j.type_name for j in lr.joints} <= {"free", "ball", "slide", "hinge"}


def test_load_structure_summary_keys():
    s = mj.load_structure("asimov", ASIMOV_MJCF).summary()
    for key in ("robot", "nbody", "njnt", "hinge", "actuators", "nq", "nv", "ngeom", "total_mass_kg"):
        assert key in s


def test_pose_statics_gravity_hold_is_physical():
    ps = mj.pose_statics("asimov", ASIMOV_MJCF)
    # whole-body CoM and total mass are finite and the mass matches the model
    assert math.isclose(ps.total_mass_kg, 32.3713, rel_tol=1e-3)
    assert all(math.isfinite(c) for c in ps.com_world)
    # one gravity-hold entry per scalar (hinge) joint = 27, all finite
    assert len(ps.joint_torques) == 27
    assert all(math.isfinite(v) for v in ps.joint_torques.values())
    assert ps.max_joint_torque_nm > 0.0  # a real humanoid held in a pose needs non-zero hold torque
    # the free base is lifted clear of the floor → the base vertical wrench == the true weight
    # (clean gravity hold, no contact reaction). m*g = 32.3713 * 9.80665 ≈ 317.5 N.
    assert len(ps.base_wrench) == 6
    weight = ps.total_mass_kg * mj.STANDARD_GRAVITY
    assert math.isclose(abs(ps.base_wrench[2]), weight, rel_tol=0.02), (
        f"base z-wrench {ps.base_wrench[2]:.2f} N should equal weight {weight:.2f} N"
    )


def test_pose_statics_unknown_joint_raises():
    # fail-loud on a bad joint name (no silent default) — the required negative test
    with pytest.raises(ValueError):
        mj.pose_statics("asimov", ASIMOV_MJCF, joint_positions={"no_such_joint": 0.3})


def test_pose_statics_flexed_pose_changes_torque():
    # bending the knees must change the gravity-hold torque map (statics actually depend on the pose)
    base = mj.pose_statics("asimov", ASIMOV_MJCF)
    flexed = mj.pose_statics("asimov", ASIMOV_MJCF,
                             joint_positions={"left_knee_joint": 0.6, "right_knee_joint": 0.6})
    assert flexed.joint_torques["left_knee_joint"] != base.joint_torques["left_knee_joint"]


def test_drop_test_is_finite_and_on_floor():
    dr = mj.drop_test("asimov", ASIMOV_MJCF, seconds=1.0)
    # the Asimov MJCF DOES define a ground plane and a free base — assert the test used them
    assert dr.has_floor is True
    assert dr.has_free_base is True
    assert dr.finite is True                      # no NaN/inf blow-up
    assert dr.steps > 0
    assert dr.timestep_s > 0.0
    assert all(math.isfinite(z) for z in dr.base_z_trace)
    # an unactuated humanoid dropped on a plane will not stand — it settles/tips. Just assert it did
    # not tunnel arbitrarily far below its start (qualitative sanity), matching insim.drop_test's intent.
    assert dr.base_z_min > dr.base_z_start - 1.0


def test_drop_test_deterministic():
    # headless + fixed timestep ⇒ bit-identical reruns (same contract as the pybullet harness)
    a = mj.drop_test("asimov", ASIMOV_MJCF, seconds=0.5)
    b = mj.drop_test("asimov", ASIMOV_MJCF, seconds=0.5)
    assert a.base_z_end == b.base_z_end
    assert a.base_tilt_end_deg == b.base_tilt_end_deg
    assert a.base_z_trace == b.base_z_trace


def test_missing_model_raises():
    # fail-loud on a missing file (no silent empty model) — second negative test
    with pytest.raises(FileNotFoundError):
        mj.load_structure("asimov", "/nonexistent/path/to/model.xml")
