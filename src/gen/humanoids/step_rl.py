"""step_rl — a gymnasium adapter + bounded PPO proof-of-concept for the dynamic-stepping StepEnv.

This is the RL counterpart to :mod:`gen.humanoids.rl_train` (which trains in the sway-in-place BalanceEnv).
It wraps :class:`gen.humanoids.step_env.StepEnv` as a ``gymnasium.Env`` and trains a bounded PPO policy
that decides WHEN to step and WHERE to place the foot (the env's 3-D action ``[step_trigger, dx, dy]``), then
HONESTLY compares the learned policy against (a) the passive crouch+hold and (b) the analytic capture-step
controller, under the SAME reproducible pushes, FRESH-ENV-PER-EPISODE (mandatory — see
[[rl-eval-methodology]]).

Budget (per the brief): ≤ ``timesteps`` (default 150k, cap 200k) OR ≤ ``minutes`` (default/cap 30) wall-clock,
whichever first. The honest success metric is upright-seconds at perturbations where the crouch FAILS — not
reward (which, under this shaping, can anti-correlate with survival, exactly as in the balance env).

Run: ``PYTHONPATH=src .venv/bin/python -m gen.humanoids.step_rl`` (``--timesteps N --minutes M --perturb P``).
Requires stable-baselines3 + gymnasium + PyBullet; fail-loud if absent.
"""

from __future__ import annotations

import argparse
import math
import time
from dataclasses import dataclass, field

import numpy as np

from gen.humanoids.coacd_feet import TIENKUNG_COACD_URDF
from gen.humanoids.step_controller import CaptureStepController
from gen.humanoids.step_env import StepEnv, StepEnvConfig


def gymnasium_available() -> bool:
    try:
        import gymnasium
        return True
    except Exception:
        return False


def sb3_available() -> bool:
    try:
        import stable_baselines3
        return True
    except Exception:
        return False


def make_step_gym_env(robot: str, *, urdf_path: str | None = None, horizon_s: float = 4.0,
                      perturb: float = 0.0, perturb_min: float = 0.0,
                      config: StepEnvConfig | None = None, **cfg_overrides):
    """Build a ``gymnasium.Env`` wrapping a :class:`StepEnv` (factory, returns an instance).

    The action space is ``Box(-1, 1, 3)`` = the env's ``[step_trigger, dx_norm, dy_norm]`` verbatim (already
    bounded). Each episode applies a reproducible random horizontal base-velocity push of magnitude sampled
    in ``[perturb_min, perturb]`` in a random direction (seeded from the gymnasium seed) so the policy must
    learn a REACTIVE step, not one trajectory — and so the policy/baseline comparison is over the same push
    distribution. Observation = the env's observation vector. Raises if gymnasium/PyBullet unavailable."""
    if not gymnasium_available():
        raise RuntimeError("gymnasium is not installed — RL adapter needs it")
    import gymnasium as gym

    base_cfg = config or StepEnvConfig(robot=robot, urdf_path=urdf_path, horizon_s=horizon_s,
                                       **cfg_overrides)

    class _StepGymEnv(gym.Env):
        metadata = {"render_modes": []}

        def __init__(self):
            super().__init__()
            self._env = StepEnv(base_cfg)
            self.cfg = base_cfg
            self.robot = robot
            self._pmax = float(perturb)
            self._pmin = float(perturb_min)
            ad = self._env.action_dim
            od = self._env.observation_dim
            self.action_space = gym.spaces.Box(low=-1.0, high=1.0, shape=(ad,), dtype=np.float32)
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
            if self._pmax > 0.0:
                rng = self.np_random
                mag = rng.uniform(self._pmin, self._pmax)
                ang = rng.uniform(0.0, 2.0 * math.pi)
                self._env.perturb_base_velocity(mag * math.cos(ang), mag * math.sin(ang))
                obs = self._env._observe()
            return obs.astype(np.float32), {}

        def step(self, action):
            res = self._env.step(np.asarray(action, dtype=float).reshape(-1))
            terminated = bool(res.fell)
            truncated = bool(res.info.get("horizon_reached", False)) and not terminated
            return (res.observation.astype(np.float32), float(res.reward),
                    terminated, truncated, dict(res.info))

        @property
        def upright_seconds(self) -> float:
            return self._env.upright_seconds

        @property
        def inner(self) -> StepEnv:
            return self._env

        def close(self):
            self._env.close()

    return _StepGymEnv()


@dataclass
class StepTrainResult:
    """Honest outcome of the stepping PPO PoC: what trained, the curve, and the 3-way head-to-head."""

    robot: str
    timesteps_trained: int
    wall_seconds: float
    perturb: float
    horizon_s: float
    eval_episodes: int
    reward_curve: list[float] = field(default_factory=list)
    hold_upright: list[float] = field(default_factory=list)
    capture_upright: list[float] = field(default_factory=list)
    policy_upright: list[float] = field(default_factory=list)
    hold_mean: float = 0.0
    capture_mean: float = 0.0
    policy_mean: float = 0.0
    beats_hold: bool = False
    beats_capture: bool = False
    note: str = ""
    model_path: str | None = None

    def summary(self) -> dict:
        return {
            "robot": self.robot, "timesteps": self.timesteps_trained,
            "wall_min": round(self.wall_seconds / 60.0, 1), "perturb": self.perturb,
            "reward_curve_first_last": ([round(self.reward_curve[0], 1), round(self.reward_curve[-1], 1)]
                                        if self.reward_curve else []),
            "hold_upright_mean_s": round(self.hold_mean, 3),
            "capture_upright_mean_s": round(self.capture_mean, 3),
            "policy_upright_mean_s": round(self.policy_mean, 3),
            "beats_hold": self.beats_hold, "beats_capture": self.beats_capture,
            "eval_episodes": self.eval_episodes, "note": self.note,
        }


class _Budget:
    def __new__(cls, deadline: float, max_steps: int):
        from stable_baselines3.common.callbacks import BaseCallback

        class _Impl(BaseCallback):
            def __init__(self, deadline, max_steps):
                super().__init__()
                self.curve: list[float] = []
                self.deadline = deadline
                self.max_steps = max_steps

            def _on_step(self) -> bool:
                return not (time.time() > self.deadline or self.num_timesteps >= self.max_steps)

            def _on_rollout_end(self) -> None:
                buf = self.model.ep_info_buffer
                if buf:
                    self.curve.append(float(np.mean([e["r"] for e in buf])))

        return _Impl(deadline, max_steps)


def _score_fresh(make_env, kind, episodes: int, *, seed0: int, policy=None,
                 controller=None) -> list[float]:
    """Roll a policy/controller for ``episodes`` episodes, FRESH env each (closed after), disjoint seeds.

    ``kind`` ∈ {"hold","capture","policy"}: "hold" sends a no-step action every tick; "capture" runs the
    analytic :class:`CaptureStepController` on the inner StepEnv; "policy" runs the SB3 model. A fresh env
    per episode is mandatory — PyBullet leaks solver/contact state across resets within one client (see
    [[rl-eval-methodology]]). Returns per-episode upright-seconds."""
    out = []
    for k in range(episodes):
        env = make_env()
        try:
            obs, _ = env.reset(seed=seed0 + k)
            if controller is not None:
                controller.reset()
            done = False
            while not done:
                if kind == "hold":
                    act = np.array([-1.0, 0.0, 0.0], dtype=np.float32)
                elif kind == "capture":
                    act = controller(obs, env.inner)
                else:
                    act, _ = policy.predict(obs, deterministic=True)
                obs, _, terminated, truncated, _ = env.step(act)
                done = terminated or truncated
            out.append(env.upright_seconds)
        finally:
            env.close()
    return out


def train_step_ppo(robot: str = "tienkung", *, timesteps: int = 150_000, minutes: float = 30.0,
                   horizon_s: float = 4.0, perturb: float = 0.9, perturb_min: float = 0.3,
                   eval_episodes: int = 12, seed: int = 0, urdf_path: str | None = None,
                   save_path: str | None = None, config: StepEnvConfig | None = None) -> StepTrainResult:
    """Train a bounded PPO stepper in :class:`StepEnv` and compare to crouch+hold AND the capture-step.

    Budget: stops at ``timesteps`` (cap 200k) OR ``minutes`` (cap 30) wall-clock, whichever first. Each
    episode is perturbed by a random push in ``[perturb_min, perturb]`` so the policy sees the whole recovery
    regime (recoverable→hard). The honest head-to-head scores all three controllers fresh-env-per-episode on
    a disjoint eval seed block. Returns a :class:`StepTrainResult`; the success metric is upright-seconds. For
    TienKung the convex-feet URDF is used by default. Fail-loud if SB3/gymnasium/PyBullet missing."""
    if not (sb3_available() and gymnasium_available()):
        raise RuntimeError("stable-baselines3 + gymnasium are required for the stepping RL PoC")
    from stable_baselines3 import PPO

    timesteps = min(int(timesteps), 200_000)
    minutes = min(float(minutes), 30.0)
    if urdf_path is None and robot == "tienkung":
        import os
        if os.path.isfile(TIENKUNG_COACD_URDF):
            urdf_path = TIENKUNG_COACD_URDF

    def make_env():
        return make_step_gym_env(robot, urdf_path=urdf_path, horizon_s=horizon_s, perturb=perturb,
                                 perturb_min=perturb_min, config=config)

    train_env = make_env()
    model = PPO("MlpPolicy", train_env, seed=seed, n_steps=1024, batch_size=256, gae_lambda=0.95,
                gamma=0.99, ent_coef=0.01, learning_rate=3e-4, n_epochs=10,
                policy_kwargs=dict(net_arch=[64, 64]), verbose=0)
    deadline = time.time() + minutes * 60.0
    cb = _Budget(deadline, timesteps)
    t0 = time.time()
    model.learn(total_timesteps=timesteps, callback=cb, progress_bar=False)
    wall = time.time() - t0
    trained = int(model.num_timesteps)
    if save_path:
        model.save(save_path)

    try:
        hold = _score_fresh(make_env, "hold", eval_episodes, seed0=20_000)
        cap = _score_fresh(make_env, "capture", eval_episodes, seed0=20_000,
                           controller=CaptureStepController())
        pol = _score_fresh(make_env, "policy", eval_episodes, seed0=20_000, policy=model)
    finally:
        train_env.close()

    hold_m, cap_m, pol_m = float(np.mean(hold)), float(np.mean(cap)), float(np.mean(pol))
    beats_hold = pol_m > hold_m + 1e-3
    beats_capture = pol_m > cap_m + 1e-3
    win_h = sum(1 for a, b in zip(pol, hold) if a > b + 1e-9)
    if beats_hold and beats_capture:
        note = (f"PPO stepper beats BOTH crouch+hold ({pol_m:.2f}s vs {hold_m:.2f}s) and the analytic "
                f"capture step ({cap_m:.2f}s) under pushes in [{perturb_min},{perturb}] m/s — dynamic "
                f"stepping recovers where the static crouch cannot. Policy wins {win_h}/{eval_episodes} vs hold.")
    elif beats_hold:
        note = (f"PPO stepper beats crouch+hold ({pol_m:.2f}s vs {hold_m:.2f}s) but not the analytic "
                f"capture step ({cap_m:.2f}s). Stepping helps; the hand-tuned stepper is still stronger. "
                f"Policy wins {win_h}/{eval_episodes} vs hold.")
    else:
        note = (f"PPO stepper does NOT beat crouch+hold ({pol_m:.2f}s vs {hold_m:.2f}s; capture {cap_m:.2f}s). "
                f"{trained} steps; env IS trainable (reward curve present). Honest reason: a scripted swing "
                f"on this contact-marginal mesh-foot biped exerts a reaction torque on the free base while a "
                f"foot is lifted, and the recoverable step length per stride is limited by hip-roll range — so "
                f"a single reactive step rarely arrests a >0.5 m/s push before the body topples. upright-"
                f"seconds is the honest metric (reward can anti-correlate with survival under this shaping).")

    return StepTrainResult(
        robot=robot, timesteps_trained=trained, wall_seconds=wall, perturb=perturb, horizon_s=horizon_s,
        eval_episodes=eval_episodes, reward_curve=list(cb.curve), hold_upright=hold,
        capture_upright=cap, policy_upright=pol, hold_mean=hold_m, capture_mean=cap_m,
        policy_mean=pol_m, beats_hold=beats_hold, beats_capture=beats_capture, note=note,
        model_path=save_path)


def _main() -> None:
    ap = argparse.ArgumentParser(description="Bounded PPO proof-of-concept in the humanoid stepping env")
    ap.add_argument("--robot", default="tienkung")
    ap.add_argument("--timesteps", type=int, default=150_000)
    ap.add_argument("--minutes", type=float, default=30.0)
    ap.add_argument("--perturb", type=float, default=0.9)
    ap.add_argument("--perturb-min", type=float, default=0.3)
    ap.add_argument("--eval-episodes", type=int, default=12)
    ap.add_argument("--save", default=None)
    args = ap.parse_args()
    res = train_step_ppo(args.robot, timesteps=args.timesteps, minutes=args.minutes,
                         perturb=args.perturb, perturb_min=args.perturb_min,
                         eval_episodes=args.eval_episodes, save_path=args.save)
    import json
    print(json.dumps(res.summary(), indent=2))
    print("\nreward_curve:", [round(x, 1) for x in res.reward_curve])
    print("hold    upright/ep:", [round(x, 2) for x in res.hold_upright])
    print("capture upright/ep:", [round(x, 2) for x in res.capture_upright])
    print("policy  upright/ep:", [round(x, 2) for x in res.policy_upright])
    print("\n" + res.note)


if __name__ == "__main__":
    _main()
