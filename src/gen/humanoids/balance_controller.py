"""balance_controller — baseline stand/balance controllers for :class:`gen.humanoids.balance_env.BalanceEnv`.

These are the reusable, deterministic CONTROL LAWS that act on the env's observation to keep a humanoid
standing (the env is the plant; these are the policy). They are also the honest baselines an LQR or a
learned RL policy is compared against. Each is a pure function of the observation vector (so it is
trivially swappable for a neural policy with the same signature), reading named entries via the env's
:pyattr:`observation_labels`.

Provided strategies (the standard human balance repertoire, ankle-level):
  * :class:`AnkleCoMController` — ankle torque ∝ −(k_p·CoM_offset + k_d·CoM_velocity) about the fixed
    support reference. The classic CoM-feedback ankle strategy.
  * :class:`AttitudeAnkleController` — ankle torque ∝ −(k_p·base_lean + k_d·base_angular_velocity); the
    "IMU" attitude-feedback ankle strategy (clean signal, no contact-centroid dependence).
  * :class:`CapturePointController` — ankle torque drives the capture point ξ = CoM + CoM_vel·√(h/g)
    back over the support; the momentum-aware ankle law.

Honest scope (CLAUDE.md: report what is true): these ankle laws are baselines and, measured here, NONE
of them improves on a passive stiff hold for the bundled robots — on Berkeley the hold already stands the
full horizon, and on Tien Kung moving the ankles breaks the marginal foot contact and does worse than
holding. The way Tien Kung is actually kept upright the full horizon is the env's verified CROUCHED
standing pose + stiff hold (see :data:`gen.humanoids.balance_env.RECOMMENDED_STANDING_POSE`), NOT these
ankle laws. They remain useful as the honest comparison baseline an LQR / learned policy must beat, and
as worked examples of reading the observation. Use :func:`run_controller` to get the ACTUAL upright-seconds
for a (robot, controller) pair; it never asserts success, it measures it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from gen.humanoids.balance_env import BalanceEnv, BalanceEnvConfig
from gen.humanoids.insim import STANDARD_GRAVITY


class BalanceController:
    """Interface: ``__call__(observation, env) -> action`` (an array of length ``env.action_dim``).

    Stateless across resets; given the observation and the env (for labels/dims/pendulum height) it
    returns the torque vector for the controlled joints. Subclasses implement :meth:`act`."""

    def reset(self) -> None:
        """Hook for stateful controllers (default no-op)."""

    def act(self, obs: np.ndarray, env: BalanceEnv) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError

    def __call__(self, obs: np.ndarray, env: BalanceEnv) -> np.ndarray:
        return self.act(obs, env)


def _obs_index(env: BalanceEnv) -> dict[str, int]:
    return {name: i for i, name in enumerate(env.observation_labels)}


def _ankle_action(env: BalanceEnv, cmd_pitch: float, cmd_roll: float) -> np.ndarray:
    """Map a (fore/aft pitch, lateral roll) ankle command onto the env's controlled-joint action vector.

    Pitch command goes to the ``*ankle_pitch*`` joints, roll to the ``*ankle_roll*`` joints; any other
    controlled joints get 0. The command's UNITS follow the env's ``action_mode``: N·m in "torque" mode,
    rad (an ankle-angle correction) in "position" mode — the controller gains below are interpreted in
    whichever the env uses, so the same law works in both. This keeps controllers agnostic to ordering."""
    a = np.zeros(env.action_dim)
    for i, name in enumerate(env.action_labels):
        if "ankle_pitch" in name:
            a[i] = cmd_pitch
        elif "ankle_roll" in name:
            a[i] = cmd_roll
    return a


@dataclass
class AnkleCoMController(BalanceController):
    """Ankle torque ∝ −(kp·CoM_offset + kd·CoM_velocity) about the fixed support reference.

    Restores the CoM over the centre of the foot. ``kp`` [N·m per m], ``kd`` [N·m per m/s]."""

    kp: float = 200.0
    kd: float = 40.0

    def act(self, obs: np.ndarray, env: BalanceEnv) -> np.ndarray:
        ix = _obs_index(env)
        dx, dy = obs[ix["com_dx"]], obs[ix["com_dy"]]
        vx, vy = obs[ix["com_vx"]], obs[ix["com_vy"]]
        tau_p = -(self.kp * dx + self.kd * vx)
        tau_r = -(self.kp * dy + self.kd * vy)
        return _ankle_action(env, tau_p, tau_r)


@dataclass
class AttitudeAnkleController(BalanceController):
    """Ankle torque ∝ −(kp·base_lean + kd·base_angular_velocity) — IMU attitude-feedback ankle strategy.

    Uses the relative base pitch/roll (deg→rad) and base angular velocity, the cleanest fall signals."""

    kp: float = 100.0
    kd: float = 20.0

    def act(self, obs: np.ndarray, env: BalanceEnv) -> np.ndarray:
        ix = _obs_index(env)
        pitch = math.radians(obs[ix["base_pitch_rel_deg"]])
        roll = math.radians(obs[ix["base_roll_rel_deg"]])
        wx, wy = obs[ix["base_wx"]], obs[ix["base_wy"]]
        tau_p = -(self.kp * pitch + self.kd * wy)
        tau_r = -(self.kp * roll + self.kd * wx)
        return _ankle_action(env, tau_p, tau_r)


@dataclass
class CapturePointController(BalanceController):
    """Ankle torque drives the capture point ξ = CoM + CoM_vel·√(h/g) back over the support reference.

    ``k`` is the gain [N·m per m of capture-point error]. The capture point predicts where the CoM will
    come to rest under the LIP model; keeping it inside the foot keeps the robot recoverable."""

    k: float = 500.0

    def act(self, obs: np.ndarray, env: BalanceEnv) -> np.ndarray:
        ix = _obs_index(env)
        # CoM offset from support + CoM velocity → capture-point offset from support
        dx, dy = obs[ix["com_dx"]], obs[ix["com_dy"]]
        vx, vy = obs[ix["com_vx"]], obs[ix["com_vy"]]
        w = math.sqrt(STANDARD_GRAVITY / max(0.05, env.pendulum_height))
        xi_x = dx + vx / w
        xi_y = dy + vy / w
        return _ankle_action(env, -self.k * xi_x, -self.k * xi_y)


@dataclass(frozen=True)
class ControllerRunResult:
    """Honest outcome of running a controller in the env: how long it stood, and the trajectory summary."""

    robot: str
    controller: str
    upright_seconds: float
    horizon_s: float
    fell: bool
    max_lean_deg: float
    steps: int
    total_reward: float
    held_full_horizon: bool

    def summary(self) -> dict:
        return {
            "robot": self.robot, "controller": self.controller,
            "upright_s": round(self.upright_seconds, 3), "horizon_s": self.horizon_s,
            "fell": self.fell, "max_lean_deg": round(self.max_lean_deg, 1),
            "held_full_horizon": self.held_full_horizon,
            "total_reward": round(self.total_reward, 2),
        }


def run_controller(robot: str, controller: BalanceController, *,
                   config: BalanceEnvConfig | None = None, seconds: float = 3.0,
                   **cfg_overrides) -> ControllerRunResult:
    """Run ``controller`` in a fresh :class:`BalanceEnv` for ``robot`` and report the ACTUAL upright time.

    Builds the env (defaults from the catalog, ``seconds`` horizon, plus any ``config``/keyword overrides),
    resets, then steps the controller's action until the episode ends. Returns a
    :class:`ControllerRunResult` with the measured ``upright_seconds`` and whether it held the full
    horizon — it never asserts success. Raises if PyBullet/URDF are unavailable (fail-loud)."""
    if config is None:
        config = BalanceEnvConfig(robot=robot, horizon_s=seconds, **cfg_overrides)
    env = BalanceEnv(config)
    try:
        obs = env.reset()
        controller.reset()
        total_r = 0.0
        done = False
        fell = False
        steps = 0
        while not done:
            action = controller(obs, env)
            res = env.step(action)
            obs = res.observation
            total_r += res.reward
            done = res.done
            fell = res.fell
            steps += 1
        upright = env.upright_seconds
        held = (not fell) and steps * config.control_dt >= config.horizon_s - 1e-9
        return ControllerRunResult(
            robot=robot, controller=type(controller).__name__,
            upright_seconds=upright, horizon_s=config.horizon_s, fell=fell,
            max_lean_deg=env.max_lean_deg, steps=steps, total_reward=total_r,
            held_full_horizon=held)
    finally:
        env.close()
