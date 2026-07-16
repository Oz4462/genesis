"""rl_env — a gymnasium.Env adapter around :class:`gen.humanoids.balance_env.BalanceEnv` for RL.

:class:`BalanceEnv` is Gym-STYLE (reset/step/observation/reward) but not a ``gymnasium.Env`` (no
``action_space``/``observation_space``, and its ``step`` returns a ``StepResult`` dataclass). Stable-
Baselines3 needs the real gymnasium interface, so this is a thin, honest adapter — it adds the
``Box`` spaces and the ``(obs, reward, terminated, truncated, info)`` tuple, and nothing else physical
(the plant, reward and termination all stay in :class:`BalanceEnv`, the single source of truth).

Design choices for a HONEST proof-of-concept that the env is trainable (NOT a convergence chase):
  * Action space = ``Box(-1, 1, action_dim)``: the policy outputs normalised actions, scaled to the env's
    physical action limit (``action_angle_limit`` rad in position mode — the default — or
    ``action_torque_limit`` N·m in torque mode). So the policy is BOUNDED by construction, matching the
    brief's "bounded RL policy".
  * Optional small per-episode RESET PERTURBATION (``reset_perturb``): a tiny random base
    velocity/posture nudge each episode so the policy must learn a reactive mapping (otherwise the env is
    one deterministic trajectory and there is nothing to generalise). The perturbation is reproducible
    from the gymnasium ``seed``. This also makes the "does the policy beat the passive hold" comparison
    meaningful — both are scored under the SAME perturbation distribution.
  * Observation = the env's observation vector verbatim; ``observation_space`` is a finite ``Box`` with
    generous bounds (the obs entries are bounded physical quantities — lean deg, ang-vel, CoM offset, …).

Fail-loud: requires gymnasium + PyBullet; raises if absent (no silent stub env). Deterministic given a
seed (the underlying PyBullet client is fixed-timestep deterministic; only the reset perturbation uses the
seeded RNG).
"""

from __future__ import annotations


import numpy as np

from gen.humanoids.balance_env import BalanceEnv, BalanceEnvConfig, recommended_standing_pose


def gymnasium_available() -> bool:
    try:
        import gymnasium
        return True
    except Exception:
        return False


def _gym_base():
    """Return ``gymnasium.Env`` (imported lazily so the module imports without gymnasium present)."""
    import gymnasium as gym
    return gym.Env


class BalanceGymEnv:  # subclasses gymnasium.Env at runtime via _make; see make_balance_gym_env
    """Not used directly — see :func:`make_balance_gym_env`. Kept as a marker for discoverability."""


def make_balance_gym_env(robot: str, *, urdf_path: str | None = None, horizon_s: float = 5.0,
                         action_mode: str = "position", reset_perturb: float = 0.0,
                         standing_pose: dict | None = None, controlled_joints: tuple[str, ...] | None = None,
                         **cfg_overrides):
    """Build a ``gymnasium.Env`` wrapping a :class:`BalanceEnv` for ``robot`` (factory, returns instance).

    ``reset_perturb`` scales a small random initial base linear+angular velocity (m/s, rad/s) applied at
    each reset so the policy must react (0 = perfectly deterministic start). ``standing_pose`` defaults to
    the robot's verified crouch. Other keyword args pass through to :class:`BalanceEnvConfig`. Raises if
    gymnasium/PyBullet are unavailable."""
    if not gymnasium_available():
        raise RuntimeError("gymnasium is not installed — RL adapter needs it")
    import gymnasium as gym

    pose = standing_pose if standing_pose is not None else recommended_standing_pose(robot)
    base_cfg = BalanceEnvConfig(robot=robot, urdf_path=urdf_path, horizon_s=horizon_s,
                                action_mode=action_mode, standing_pose=pose,
                                controlled_joints=controlled_joints, **cfg_overrides)

    class _BalanceGymEnv(gym.Env):
        """gymnasium.Env over BalanceEnv: Box action in [-1,1] scaled to the physical limit."""

        metadata = {"render_modes": []}

        def __init__(self):
            super().__init__()
            self._env = BalanceEnv(base_cfg)
            self.cfg = base_cfg
            self.robot = robot
            self._scale = (base_cfg.action_angle_limit if base_cfg.action_mode == "position"
                           else base_cfg.action_torque_limit)
            self._perturb = float(reset_perturb)
            ad = self._env.action_dim
            od = self._env.observation_dim
            self.action_space = gym.spaces.Box(low=-1.0, high=1.0, shape=(ad,), dtype=np.float32)
            # generous finite bounds; obs entries are bounded physical quantities
            hi = np.full((od,), 1e3, dtype=np.float32)
            self.observation_space = gym.spaces.Box(low=-hi, high=hi, dtype=np.float32)

        @property
        def action_labels(self):
            return self._env.action_labels

        @property
        def observation_labels(self):
            return self._env.observation_labels

        def reset(self, *, seed=None, options=None):
            super().reset(seed=seed)
            obs = self._env.reset()
            if self._perturb > 0.0:
                rng = self.np_random
                lin = (rng.standard_normal(3) * self._perturb).tolist()
                ang = (rng.standard_normal(3) * self._perturb).tolist()
                p, c, bid = self._env._p, self._env._client, self._env._bid
                p.resetBaseVelocity(bid, lin, ang, physicsClientId=c)
                obs = self._env._observe()
            return obs.astype(np.float32), {}

        def step(self, action):
            a = np.asarray(action, dtype=float).reshape(-1) * self._scale
            res = self._env.step(a)
            terminated = bool(res.fell)
            truncated = bool(res.info.get("horizon_reached", False)) and not terminated
            return (res.observation.astype(np.float32), float(res.reward),
                    terminated, truncated, dict(res.info))

        @property
        def upright_seconds(self) -> float:
            return self._env.upright_seconds

        @property
        def max_lean_deg(self) -> float:
            return self._env.max_lean_deg

        @property
        def inner(self) -> BalanceEnv:
            return self._env

        def close(self):
            self._env.close()

    return _BalanceGymEnv()
