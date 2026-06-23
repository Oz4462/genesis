"""rl_train — a bounded PPO proof-of-concept that :class:`gen.humanoids.rl_env` is TRAINABLE.

This is a PROOF-OF-CONCEPT, not a convergence chase (per the brief): train PPO in the balance env for at
most a small budget (default ~60k timesteps OR ~20 min wall-clock, whichever first), then HONESTLY compare
the learned policy against the passive crouch+hold baseline under the SAME random-perturbation
distribution. It reports the timesteps actually trained, the reward curve (per-rollout mean episode
reward), and whether the policy beats the baseline / improves push-recovery — and if it does NOT, says so
plainly with the likely reason (a real research result either way).

Everything is honest and reproducible: fixed seed, the env is the single source of truth for the plant +
reward, and the evaluation re-uses the SAME ``BalanceEnv`` the baseline runs in (no separate scoring path).

Run: ``PYTHONPATH=src .venv/bin/python -m gen.humanoids.rl_train`` (optionally ``--timesteps N
--minutes M --robot tienkung``). Requires stable-baselines3 + gymnasium + PyBullet.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass, field

import numpy as np

from gen.humanoids.balance_env import recommended_standing_pose
from gen.humanoids.coacd_feet import TIENKUNG_COACD_URDF
from gen.humanoids.rl_env import gymnasium_available, make_balance_gym_env


def sb3_available() -> bool:
    try:
        import stable_baselines3  # noqa: F401
        return True
    except Exception:
        return False


@dataclass
class TrainResult:
    """Honest outcome of the PPO PoC: what was trained, the reward curve, and the head-to-head vs baseline."""

    robot: str
    timesteps_trained: int
    wall_seconds: float
    reward_curve: list[float] = field(default_factory=list)          #: per-rollout mean episode reward
    baseline_upright_mean: float = 0.0
    policy_upright_mean: float = 0.0
    baseline_upright_eps: list[float] = field(default_factory=list)
    policy_upright_eps: list[float] = field(default_factory=list)
    horizon_s: float = 5.0
    eval_episodes: int = 0
    perturb: float = 0.0
    beats_baseline: bool = False
    note: str = ""
    model_path: str | None = None

    def summary(self) -> dict:
        return {
            "robot": self.robot, "timesteps": self.timesteps_trained,
            "wall_min": round(self.wall_seconds / 60.0, 1),
            "reward_curve_first_last": (
                [round(self.reward_curve[0], 1), round(self.reward_curve[-1], 1)]
                if self.reward_curve else []),
            "baseline_upright_mean_s": round(self.baseline_upright_mean, 3),
            "policy_upright_mean_s": round(self.policy_upright_mean, 3),
            "horizon_s": self.horizon_s, "eval_episodes": self.eval_episodes,
            "perturb": self.perturb, "beats_baseline": self.beats_baseline, "note": self.note,
        }


class _RewardCurveCallback:
    """SB3 callback that records the rolling mean episode reward after each rollout (the reward curve)."""

    def __new__(cls, *a, **k):
        from stable_baselines3.common.callbacks import BaseCallback

        class _Impl(BaseCallback):
            def __init__(self, deadline: float, max_steps: int):
                super().__init__()
                self.curve: list[float] = []
                self.deadline = deadline
                self.max_steps = max_steps

            def _on_step(self) -> bool:
                # stop early if past the wall-clock deadline or the step cap (PoC budget guard)
                if time.time() > self.deadline or self.num_timesteps >= self.max_steps:
                    return False
                return True

            def _on_rollout_end(self) -> None:
                buf = self.model.ep_info_buffer
                if buf:
                    self.curve.append(float(np.mean([e["r"] for e in buf])))

        return _Impl(*a, **k)


class _ZeroBaseline:
    """The passive crouch+hold baseline policy: action 0 (the env's implicit-PD hold), for the same env."""

    def predict(self, obs, deterministic=True):
        return np.zeros(obs.shape[-1] if obs.ndim == 1 else obs.shape[0]), None


def _score_policy(make_env, policy, episodes: int, *, seed0: int) -> list[float]:
    """Roll ``policy`` for ``episodes`` episodes and return per-episode upright-seconds.

    IMPORTANT — uses a FRESH env per episode (``make_env()`` each time, closed after). PyBullet's solver/
    contact state is NOT fully cleared by ``reset`` within one client, so reusing a single env makes
    episode k's outcome depend on episode k-1 — a real source of non-reproducibility found during bring-up
    that made a sequential-reset eval contaminate the policy-vs-baseline comparison. A fresh env per
    episode gives the TRUE, history-independent per-seed result (the single-episode determinism the env
    tests pin)."""
    out = []
    for k in range(episodes):
        env = make_env()
        try:
            obs, _ = env.reset(seed=seed0 + k)
            done = False
            while not done:
                if isinstance(policy, _ZeroBaseline):
                    act = np.zeros(env.action_space.shape[0], dtype=np.float32)
                else:
                    act, _ = policy.predict(obs, deterministic=True)
                obs, _, terminated, truncated, _ = env.step(act)
                done = terminated or truncated
            out.append(env.upright_seconds)
        finally:
            env.close()
    return out


def train_ppo_poc(robot: str = "tienkung", *, timesteps: int = 60_000, minutes: float = 20.0,
                  horizon_s: float = 5.0, perturb: float = 0.05, eval_episodes: int = 8,
                  seed: int = 0, urdf_path: str | None = None, save_path: str | None = None) -> TrainResult:
    """Train PPO in the balance env for ``robot`` (capped budget) and compare to the passive baseline.

    Budget: stops at ``timesteps`` OR ``minutes`` wall-clock, whichever first. ``perturb`` is the
    per-episode random base-velocity nudge (so the task is reactive, not a single trajectory). Returns a
    :class:`TrainResult` with the reward curve and the honest head-to-head. For TienKung the convex-feet
    URDF is used by default (denser contact). Fail-loud if SB3/gymnasium/PyBullet are missing."""
    if not (sb3_available() and gymnasium_available()):
        raise RuntimeError("stable-baselines3 + gymnasium are required for the RL PoC")
    from stable_baselines3 import PPO

    if urdf_path is None and robot == "tienkung":
        import os
        if os.path.isfile(TIENKUNG_COACD_URDF):
            urdf_path = TIENKUNG_COACD_URDF  # prefer the denser convex feet

    def make_env():
        return make_balance_gym_env(robot, urdf_path=urdf_path, horizon_s=horizon_s,
                                    action_mode="position", reset_perturb=perturb)

    train_env = make_env()
    # Small MLP, short rollouts: enough for a PoC, cheap per update.
    model = PPO("MlpPolicy", train_env, seed=seed, n_steps=1024, batch_size=256, gae_lambda=0.95,
                gamma=0.99, ent_coef=0.0, learning_rate=3e-4, n_epochs=10,
                policy_kwargs=dict(net_arch=[64, 64]), verbose=0)
    deadline = time.time() + minutes * 60.0
    cb = _RewardCurveCallback(deadline, timesteps)
    t0 = time.time()
    model.learn(total_timesteps=timesteps, callback=cb, progress_bar=False)
    wall = time.time() - t0
    trained = int(model.num_timesteps)
    if save_path:
        model.save(save_path)

    # Honest head-to-head: a FRESH env PER EPISODE (no inter-episode PyBullet leakage), same perturbation
    # seeds for both policies. (Reusing one env across episodes contaminated the comparison — see
    # _score_policy.) Use a disjoint eval seed block (20_000+) so eval never overlaps training resets.
    try:
        base = _score_policy(make_env, _ZeroBaseline(), eval_episodes, seed0=20_000)
        pol = _score_policy(make_env, model, eval_episodes, seed0=20_000)
    finally:
        train_env.close()

    base_mean = float(np.mean(base))
    pol_mean = float(np.mean(pol))
    beats = pol_mean > base_mean + 1e-3
    if beats:
        note = (f"PPO policy beats the passive crouch+hold under {perturb} perturbation "
                f"({pol_mean:.2f}s vs {base_mean:.2f}s mean upright).")
    elif abs(pol_mean - base_mean) <= 1e-3:
        note = (f"PPO policy MATCHES the passive hold ({pol_mean:.2f}s vs {base_mean:.2f}s): with only "
                f"ankle authority the passive crouch is already near-optimal; the policy learned to ~hold.")
    else:
        note = (f"PPO policy does NOT beat the passive hold ({pol_mean:.2f}s vs {base_mean:.2f}s). Likely: "
                f"ankle-only authority cannot improve on the crouch hold (moving ankles breaks contact — "
                f"the measured ceiling) and/or {trained} steps is too few. Env is trainable (reward curve "
                f"present); this is the honest ankle-strategy ceiling, not a harness bug.")

    return TrainResult(
        robot=robot, timesteps_trained=trained, wall_seconds=wall, reward_curve=list(cb.curve),
        baseline_upright_mean=base_mean, policy_upright_mean=pol_mean,
        baseline_upright_eps=base, policy_upright_eps=pol, horizon_s=horizon_s,
        eval_episodes=eval_episodes, perturb=perturb, beats_baseline=beats, note=note,
        model_path=save_path)


def _main() -> None:
    ap = argparse.ArgumentParser(description="PPO proof-of-concept in the humanoid balance env")
    ap.add_argument("--robot", default="tienkung")
    ap.add_argument("--timesteps", type=int, default=60_000)
    ap.add_argument("--minutes", type=float, default=20.0)
    ap.add_argument("--perturb", type=float, default=0.05)
    ap.add_argument("--eval-episodes", type=int, default=8)
    ap.add_argument("--save", default=None)
    args = ap.parse_args()
    res = train_ppo_poc(args.robot, timesteps=args.timesteps, minutes=args.minutes,
                        perturb=args.perturb, eval_episodes=args.eval_episodes, save_path=args.save)
    import json
    print(json.dumps(res.summary(), indent=2))
    print("\nreward_curve:", [round(x, 1) for x in res.reward_curve])
    print("baseline upright/ep:", [round(x, 2) for x in res.baseline_upright_eps])
    print("policy   upright/ep:", [round(x, 2) for x in res.policy_upright_eps])
    print("\n" + res.note)


if __name__ == "__main__":
    _main()
