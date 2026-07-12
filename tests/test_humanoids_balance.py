"""Tests for the stand/balance environment + baseline controllers (gen.humanoids.balance_env / _controller).

These run REAL PyBullet DIRECT sims on the downloaded humanoid URDFs, so they are skip-guarded on
PyBullet + the asset's presence (like tests/test_humanoids_insim.py). They pin the honest, verified
behaviour rather than an aspirational one:

  * The env is a valid, deterministic Gym-style plant (reset/step/obs/reward, fixed-seed reproducible).
  * POSITIVE CONTROL: Berkeley Humanoid Lite holds a stand for the full 3 s horizon under the env's
    stiff implicit-PD hold (zero action) — proving the env + loop are correct (matches insim.pd_balance).
  * HONEST NEGATIVE: Tien Kung does NOT hold the full horizon — it tips in ~1-2 s; this is asserted as a
    measured fact (its true upright-seconds is positive but < horizon), not hidden.
  * Controllers obey their interface (right action length, finite) and run_controller returns a coherent
    ControllerRunResult.
  * Negative tests: bad robot, bad action length, bad action_mode raise (fail-loud).
"""

from __future__ import annotations

import numpy as np
import pytest

from gen.humanoids import catalog
from gen.humanoids.insim import pybullet_available

pytestmark = pytest.mark.skipif(not pybullet_available(), reason="PyBullet not installed")

from gen.humanoids.balance_env import BalanceEnv, BalanceEnvConfig  # noqa: E402
from gen.humanoids.balance_controller import (  # noqa: E402
    AnkleCoMController, AttitudeAnkleController, CapturePointController,
    BalanceController, run_controller,
)


def _asset_present(robot: str) -> bool:
    from pathlib import Path
    ref = catalog.ASSETS.get(robot)
    return ref is not None and ref.model_path is not None and Path(ref.model_path).is_file()


_BK = pytest.mark.skipif(not _asset_present("berkeley_lite"), reason="berkeley_lite asset missing")
_TK = pytest.mark.skipif(not _asset_present("tienkung"), reason="tienkung asset missing")


class _ZeroController(BalanceController):
    def act(self, obs, env):
        return np.zeros(env.action_dim)


# ── env structural / API ────────────────────────────────────────────────────────────────────────────

@_BK
def test_env_builds_and_reset_returns_observation():
    with BalanceEnv(BalanceEnvConfig(robot="berkeley_lite", horizon_s=0.2)) as env:
        obs = env.reset()
        assert obs.shape == (env.observation_dim,)
        assert len(env.observation_labels) == env.observation_dim
        assert env.action_dim == len(env.action_labels) >= 2  # at least ankle pitch+roll on one leg
        assert np.all(np.isfinite(obs))
        # foot links were detected (so placement/contact tuning is real, not the global-AABB fallback)
        assert len(env._foot_links) >= 1


@_BK
def test_env_step_returns_coherent_stepresult():
    with BalanceEnv(BalanceEnvConfig(robot="berkeley_lite", horizon_s=0.2)) as env:
        env.reset()
        res = env.step(np.zeros(env.action_dim))
        assert res.observation.shape == (env.observation_dim,)
        assert np.isfinite(res.reward)
        assert isinstance(res.done, bool) and isinstance(res.fell, bool)
        for key in ("lean_deg", "upright_seconds", "n_contacts", "com_offset"):
            assert key in res.info


@_BK
def test_env_is_deterministic():
    """Two identical zero-action rollouts give identical upright-seconds (pinned reproducibility)."""
    def rollout():
        with BalanceEnv(BalanceEnvConfig(robot="berkeley_lite", horizon_s=0.5)) as env:
            env.reset()
            done = False
            while not done:
                done = env.step(np.zeros(env.action_dim)).done
            return env.upright_seconds
    assert rollout() == rollout()


# ── positive control: Berkeley stands the full horizon under the stiff hold ──────────────────────────

@_BK
def test_berkeley_holds_full_horizon_zero_action():
    """Berkeley (flat feet, near-statically-stable) stays upright the whole 3 s under the env's hold.

    This is the POSITIVE CONTROL: it proves the env's reset/placement/contact/hold and the step loop are
    correct (it reproduces insim.pd_balance's 3 s result). If this regresses, the env is broken."""
    r = run_controller("berkeley_lite", _ZeroController(), seconds=3.0)
    assert r.held_full_horizon is True
    assert r.fell is False
    assert r.upright_seconds == pytest.approx(3.0, abs=1e-6)
    assert r.max_lean_deg < 10.0


# ── Tien Kung: tips from the straight ZERO pose, but HOLDS the full horizon from the crouch ───────────

@_TK
def test_tienkung_straight_pose_tips():
    """From the straight-leg ZERO pose, Tien Kung tips within the horizon (CoM at the back of its support).

    This is the honest BEFORE state and the reason the crouch is needed: it stands for a non-zero time
    but falls before the full 3 s. (An explicit empty standing_pose forces the zero pose.)"""
    cfg = BalanceEnvConfig(robot="tienkung", horizon_s=3.0, standing_pose={"_force_zero": 0.0})
    r = run_controller("tienkung", _ZeroController(), config=cfg)
    assert r.upright_seconds > 0.3          # it does stand briefly
    assert r.held_full_horizon is False     # but the straight pose does not survive the full horizon


@_TK
def test_tienkung_holds_full_horizon_from_recommended_crouch():
    """From the verified crouched standing pose, Tien Kung stays upright the FULL 3 s (the SOLVED state).

    The crouch lowers and centres the CoM over the feet so the stiff hold keeps a tall humanoid standing
    where ankle-only torque control could not. This is the real 'Tien Kung stays upright >= 3 s' result."""
    r = run_controller("tienkung", _ZeroController(), seconds=3.0)  # default = recommended crouch
    assert r.held_full_horizon is True
    assert r.fell is False
    assert r.upright_seconds == pytest.approx(3.0, abs=1e-6)
    assert r.max_lean_deg < 10.0


@_TK
def test_tienkung_crouch_recovers_from_small_push():
    """The crouch stance rejects a moderate lateral shove (real balance, not a fragile static pose).

    A ~300 N impulse for ~0.08 s mid-episode is applied to the base; the robot must still be upright at
    the end. (Much larger pushes DO knock it over — the basin is finite — verified separately.)"""
    import numpy as _np
    env = BalanceEnv(BalanceEnvConfig(robot="tienkung", horizon_s=3.0))
    try:
        env.reset()
        p, c, bid = env._p, env._client, env._bid
        done = False
        pushed = False
        n = 0
        while not done:
            if not pushed and n * env.cfg.control_dt >= 1.0:
                for _ in range(15):
                    p.applyExternalForce(bid, -1, [300.0, 0.0, 0.0], [0, 0, 0], p.WORLD_FRAME,
                                         physicsClientId=c)
                    p.stepSimulation(physicsClientId=c)
                pushed = True
            done = env.step(_np.zeros(env.action_dim)).done
            n += 1
        assert pushed
        assert env.max_lean_deg < env.cfg.fall_tilt_deg   # never fell
        assert env.upright_seconds >= 2.5
    finally:
        env.close()


@_TK
@pytest.mark.parametrize("ctrl", [
    AnkleCoMController(kp=3.0, kd=0.6),
    AttitudeAnkleController(kp=2.0, kd=0.4),
    CapturePointController(k=5.0),
])
def test_controllers_run_and_report_honest_seconds(ctrl):
    """Each baseline controller runs end-to-end in the env and returns a coherent, finite result.

    We do NOT assert it balances Tien Kung (it doesn't — the honest finding); we assert the control
    interface works and the measured upright-seconds is a sane, finite, bounded number."""
    r = run_controller("tienkung", ctrl, seconds=2.0)
    assert 0.0 <= r.upright_seconds <= 2.0 + 1e-6
    assert np.isfinite(r.total_reward)
    assert r.steps > 0
    assert r.controller == type(ctrl).__name__


@_BK
def test_controller_action_is_finite_and_right_length():
    with BalanceEnv(BalanceEnvConfig(robot="berkeley_lite", horizon_s=0.2)) as env:
        obs = env.reset()
        for ctrl in (AnkleCoMController(), AttitudeAnkleController(), CapturePointController()):
            a = ctrl(obs, env)
            assert a.shape == (env.action_dim,)
            assert np.all(np.isfinite(a))


@_BK
def test_torque_mode_runs():
    """The alternative torque action_mode also runs (a pure torque plant), not just the position default."""
    cfg = BalanceEnvConfig(robot="berkeley_lite", horizon_s=0.3, action_mode="torque")
    r = run_controller("berkeley_lite", _ZeroController(), config=cfg)
    assert r.steps > 0
    assert np.isfinite(r.upright_seconds)


# ── negative tests (fail-loud) ───────────────────────────────────────────────────────────────────────

def test_unknown_robot_raises():
    with pytest.raises((ValueError, KeyError)):
        BalanceEnv(BalanceEnvConfig(robot="does_not_exist"))


@_BK
def test_bad_action_length_raises():
    with BalanceEnv(BalanceEnvConfig(robot="berkeley_lite", horizon_s=0.2)) as env:
        env.reset()
        with pytest.raises(ValueError):
            env.step(np.zeros(env.action_dim + 3))


@_BK
def test_bad_action_mode_raises():
    env = BalanceEnv(BalanceEnvConfig(robot="berkeley_lite", horizon_s=0.2, action_mode="bogus"))
    try:
        with pytest.raises(ValueError):
            env.reset()
    finally:
        env.close()


@_BK
def test_non_finite_action_raises():
    with BalanceEnv(BalanceEnvConfig(robot="berkeley_lite", horizon_s=0.2)) as env:
        env.reset()
        bad = np.zeros(env.action_dim)
        bad[0] = np.nan
        with pytest.raises(ValueError):
            env.step(bad)
