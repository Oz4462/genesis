"""Tests for the dynamic-stepping env + controllers (gen.humanoids.step_env / step_controller).

These are skip-guarded on PyBullet + the TienKung asset (the same pattern as the other humanoid in-engine
tests), and they pin: structure (obs/action dims, leg chains), determinism (a fixed action sequence is
bit-reproducible), the step MECHANICS (committing a step actually moves a foot and transitions contact),
the honest baseline (HoldController never steps), fail-loud behaviour, and that the recovery evaluation is
fresh-env-per-episode and returns the documented stats. They do NOT assert that stepping beats the hold —
that is a measured research outcome reported separately, not a test invariant.
"""

from __future__ import annotations

import math
import os

import numpy as np
import pytest

from gen.humanoids.insim import pybullet_available

pytestmark = pytest.mark.skipif(not pybullet_available(), reason="PyBullet not installed")

from gen.humanoids.coacd_feet import TIENKUNG_COACD_URDF  # noqa: E402
from gen.humanoids.step_env import LEG_CHAINS, StepEnv, StepEnvConfig  # noqa: E402
from gen.humanoids import step_controller as sc  # noqa: E402

_HAS_TK = os.path.isfile(TIENKUNG_COACD_URDF)
_tk = pytest.mark.skipif(not _HAS_TK, reason="TienKung coacd URDF not present")


def _cfg(**kw):
    kw.setdefault("urdf_path", TIENKUNG_COACD_URDF)
    kw.setdefault("horizon_s", 1.0)
    return StepEnvConfig(robot="tienkung", **kw)


@_tk
def test_reset_and_observation_shape():
    env = StepEnv(_cfg())
    try:
        obs = env.reset()
        assert obs.shape == (env.observation_dim,) == (20,)
        assert len(env.observation_labels) == env.observation_dim
        assert env.action_dim == 3
        assert env.action_labels == ("step_trigger", "target_dx_norm", "target_dy_norm")
        # at the settled stance both feet should register contact and the robot stands upright
        ix = {n: i for i, n in enumerate(env.observation_labels)}
        assert obs[ix["left_contact"]] == 1.0 and obs[ix["right_contact"]] == 1.0
        assert obs[ix["base_lean_deg"]] < 2.0
        assert env.pendulum_height > 0.3  # a ~0.8 m LIP height for TienKung
    finally:
        env.close()


@_tk
def test_leg_chain_wired():
    assert "tienkung" in LEG_CHAINS
    for side in ("left", "right"):
        spec = LEG_CHAINS["tienkung"][side]
        assert len(spec["joints"]) == 6
        assert spec["foot_link"].startswith("ankle_roll")


@_tk
def test_hold_keeps_upright_no_steps():
    """The honest baseline: HoldController never triggers a step and the unperturbed crouch stays up."""
    env = StepEnv(_cfg(horizon_s=1.0))
    ctrl = sc.HoldController()
    try:
        obs = env.reset()
        done = False
        while not done:
            res = env.step(ctrl(obs, env))
            obs = res.observation
            done = res.done
        assert env._n_steps_taken == 0          # never stepped
        assert not res.fell                      # held the crouch
        assert env.upright_seconds >= 0.95       # ~full 1 s horizon
    finally:
        env.close()


@_tk
def test_commit_step_moves_a_foot_and_transitions_contact():
    """Committing a step lifts a foot (single-support: one foot loses contact) and lands it elsewhere."""
    env = StepEnv(_cfg(horizon_s=2.0))
    try:
        env.reset()
        l0 = env._foot_world("left").copy()
        r0 = env._foot_world("right").copy()
        # command a clear lateral+forward LEFT step
        env.step(np.array([1.0, 0.3, 0.6]))
        assert env._swing_side is not None        # a swing started
        swung = env._swing_side
        saw_single_support = False
        for _ in range(60):
            res = env.step(np.array([-1.0, 0.0, 0.0]))
            # during the swing the swinging foot should be off the ground at some point
            if env._foot_contact(swung) < 0.5:
                saw_single_support = True
            if not res.info["swing_active"] and res.info["n_steps_taken"] > 0:
                break
        assert env._n_steps_taken >= 1            # the step planted
        assert saw_single_support                 # there was a real single-support phase (foot lifted)
        l1 = env._foot_world("left").copy()
        r1 = env._foot_world("right").copy()
        moved = np.hypot(*(l1 - l0)[:2]) if swung == "left" else np.hypot(*(r1 - r0)[:2])
        assert moved > 0.03                       # the swing foot actually relocated
    finally:
        env.close()


@_tk
def test_determinism_same_actions_same_trajectory():
    """A fixed action sequence yields a bit-identical trajectory (fresh env each time)."""
    acts = [np.array([-1.0, 0.0, 0.0])] * 5 + [np.array([1.0, 0.2, 0.4])] + \
           [np.array([-1.0, 0.0, 0.0])] * 20

    def rollout():
        env = StepEnv(_cfg(horizon_s=2.0))
        try:
            env.reset()
            leans = []
            for a in acts:
                res = env.step(a)
                leans.append(res.info["lean_deg"])
                if res.done:
                    break
            return leans
        finally:
            env.close()

    a = rollout()
    b = rollout()
    assert a == b


@_tk
def test_perturb_then_capture_controller_runs():
    """CaptureStepController runs end-to-end under a push and reports honest, finite results."""
    res = sc.run_step_controller("tienkung", sc.CaptureStepController(), perturb=0.9,
                                 direction_rad=math.pi / 2, seconds=2.0,
                                 urdf_path=TIENKUNG_COACD_URDF)
    assert res.controller == "CaptureStepController"
    assert 0.0 <= res.upright_seconds <= 2.0
    assert math.isfinite(res.max_lean_deg)
    assert res.perturb == 0.9


@_tk
def test_evaluate_recovery_fresh_env_and_stats():
    """evaluate_recovery returns documented per-controller stats over a small push sweep (fresh env each)."""
    out = sc.evaluate_recovery(
        "tienkung", {"hold": sc.HoldController(), "capture": sc.CaptureStepController()},
        perturb=0.9, n_directions=2, seconds=1.5, urdf_path=TIENKUNG_COACD_URDF)
    assert set(out) == {"hold", "capture"}
    for name, st in out.items():
        assert st.n_conditions == 2
        assert 0.0 <= st.success_rate <= 1.0
        assert st.mean_upright_s >= 0.0
        assert len(st.per_condition) == 2


def test_unknown_robot_fails_loud():
    with pytest.raises(ValueError):
        StepEnv(StepEnvConfig(robot="definitely_not_a_robot", urdf_path=TIENKUNG_COACD_URDF))


@_tk
def test_bad_action_length_fails_loud():
    env = StepEnv(_cfg())
    try:
        env.reset()
        with pytest.raises(ValueError):
            env.step(np.array([1.0, 0.0]))        # too short
        with pytest.raises(ValueError):
            env.step(np.array([1.0, np.nan, 0.0]))  # non-finite
    finally:
        env.close()
