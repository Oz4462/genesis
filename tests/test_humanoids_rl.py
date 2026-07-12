"""Tests for the RL adapter + PPO proof-of-concept (gen.humanoids.rl_env / rl_train).

Skip-guarded on gymnasium / stable-baselines3 / PyBullet / the asset. These verify the env is a VALID
gymnasium environment and that the PoC training path runs end-to-end on a tiny budget — NOT that PPO
converges (the brief is explicit: PoC that the env is trainable, honest result either way). So the PPO
test uses a tiny timestep budget and only asserts the result object is coherent and the reward curve and
head-to-head are populated.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from gen.humanoids import catalog
from gen.humanoids.insim import pybullet_available
from gen.humanoids.rl_env import gymnasium_available, make_balance_gym_env
from gen.humanoids.rl_train import sb3_available, train_ppo_poc

pytestmark = pytest.mark.skipif(
    not (gymnasium_available() and pybullet_available()),
    reason="gymnasium + PyBullet required")


def _present(robot: str) -> bool:
    ref = catalog.ASSETS.get(robot)
    return ref is not None and ref.model_path is not None and Path(ref.model_path).is_file()


_BK = pytest.mark.skipif(not _present("berkeley_lite"), reason="berkeley_lite asset missing")
_TK = pytest.mark.skipif(not _present("tienkung"), reason="tienkung asset missing")


@_BK
def test_gym_env_obeys_gymnasium_api():
    """The adapter is a real gymnasium.Env: Box spaces, reset->(obs,info), step->5-tuple, bounds honoured."""
    import gymnasium as gym
    env = make_balance_gym_env("berkeley_lite", horizon_s=0.3)
    try:
        assert isinstance(env, gym.Env)
        assert env.action_space.shape == (env.inner.action_dim,)
        assert env.observation_space.shape == (env.inner.observation_dim,)
        obs, info = env.reset(seed=0)
        assert env.observation_space.contains(obs)
        assert isinstance(info, dict)
        act = env.action_space.sample()
        obs2, rew, terminated, truncated, info2 = env.step(act)
        assert env.observation_space.shape == obs2.shape
        assert np.isfinite(rew)
        assert isinstance(terminated, bool) and isinstance(truncated, bool)
    finally:
        env.close()


@_BK
def test_gym_env_action_is_bounded_and_scaled():
    """A normalised action of +1 maps to exactly the env's physical action limit (bounded by construction)."""
    env = make_balance_gym_env("berkeley_lite", horizon_s=0.3, action_mode="position")
    try:
        assert env.action_space.high.max() == pytest.approx(1.0)
        assert env.action_space.low.min() == pytest.approx(-1.0)
        assert env._scale == pytest.approx(env.cfg.action_angle_limit)
    finally:
        env.close()


@_BK
def test_gym_env_seeded_reset_is_reproducible():
    """Same seed + same actions -> identical upright-seconds (reproducible perturbed resets)."""
    def run():
        env = make_balance_gym_env("berkeley_lite", horizon_s=0.4, reset_perturb=0.05)
        try:
            env.reset(seed=123)
            done = False
            while not done:
                _, _, t, tr, _ = env.step(np.zeros(env.action_space.shape[0], dtype=np.float32))
                done = t or tr
            return env.upright_seconds
        finally:
            env.close()
    assert run() == run()


@pytest.mark.skipif(not sb3_available(), reason="stable-baselines3 not installed")
@_TK
def test_ppo_poc_runs_tiny_budget_and_reports_honestly():
    """PPO PoC runs end-to-end on a tiny budget and returns a coherent, honest TrainResult.

    Not a convergence test: a few thousand steps only. Asserts the result is well-formed — timesteps were
    trained, a reward curve exists, and the head-to-head vs the passive baseline is populated with finite
    upright-seconds for both. ``beats_baseline`` may be True or False; we only require it be consistent
    with the measured means (honest, not aspirational)."""
    res = train_ppo_poc("tienkung", timesteps=2048, minutes=5.0, perturb=0.04, eval_episodes=2, seed=0)
    assert res.timesteps_trained > 0
    assert len(res.reward_curve) >= 1
    assert all(np.isfinite(x) for x in res.reward_curve)
    assert res.eval_episodes == 2
    assert len(res.baseline_upright_eps) == 2 and len(res.policy_upright_eps) == 2
    assert np.isfinite(res.baseline_upright_mean) and np.isfinite(res.policy_upright_mean)
    assert 0.0 <= res.policy_upright_mean <= res.horizon_s + 1e-6
    # beats_baseline must be CONSISTENT with the means (no dishonest flag)
    assert res.beats_baseline == (res.policy_upright_mean > res.baseline_upright_mean + 1e-3)
    assert res.note  # an honest verdict string is always present
