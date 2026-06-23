"""step_controller — controllers + honest evaluation for :class:`gen.humanoids.step_env.StepEnv`.

This is the dynamic-stepping counterpart to :mod:`gen.humanoids.balance_controller` (which targets the
sway-in-place :class:`~gen.humanoids.balance_env.BalanceEnv`). It provides:

  * :class:`HoldController` — the honest baseline: NEVER step (the crouch+hold strategy, run inside the
    StepEnv so the comparison is apples-to-apples in the same plant).
  * :class:`CaptureStepController` — the interpretable analytic stepper. It watches the capture point
    ξ = CoM + v·√(h/g) (which the env exposes as ``cap_dx, cap_dy`` relative to the support centre). While ξ
    stays inside the support polygon, it does nothing (the stiff hold recovers small pushes — the proven
    static strategy). When ξ ESCAPES the support by more than a margin, it COMMITS A STEP, commanding the
    swing foot to land at the capture point (the textbook capture-point footfall: stepping to ξ brings the
    LIP to rest), bounded to the env's reachable step length. After a step it waits out the double-support
    settle before considering another. This is the classic "take a step to where you're falling" recovery —
    the physically-correct cure the sway env structurally cannot perform.

  * :func:`run_step_controller` — run a controller in a FRESH StepEnv under a reproducible push and report
    the measured upright-seconds (never asserts success — measures it).
  * :func:`evaluate_recovery` — the honest head-to-head: for a set of push magnitudes/directions, score
    EACH controller fresh-env-per-episode (mandatory — PyBullet leaks solver state across resets in one
    client; see [[rl-eval-methodology]]) and report per-condition success rate + mean upright-seconds. This
    is how "does stepping recover where crouch+hold falls" is answered honestly.

CLAUDE.md: fail-loud (raises if PyBullet/URDF/leg-chain missing), no hidden success, upright-seconds is the
honest metric (not reward). Deterministic given the push parameters.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from gen.humanoids.step_env import StepEnv, StepEnvConfig


class StepController:
    """Interface: ``__call__(observation, env) -> action`` (length :pyattr:`StepEnv.action_dim` = 3)."""

    def reset(self) -> None:
        """Hook for stateful controllers (default no-op)."""

    def act(self, obs: np.ndarray, env: StepEnv) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError

    def __call__(self, obs: np.ndarray, env: StepEnv) -> np.ndarray:
        return self.act(obs, env)


def _obs_index(env: StepEnv) -> dict[str, int]:
    return {n: i for i, n in enumerate(env.observation_labels)}


class HoldController(StepController):
    """The honest baseline: never trigger a step (crouch+hold), run inside the StepEnv plant.

    Returns ``[-1, 0, 0]`` every tick (no step trigger), so the env just holds the stiff crouch — exactly
    the static strategy proven to be the best in-place option. This is the bar a stepping controller must
    beat at perturbations where the hold falls."""

    def act(self, obs: np.ndarray, env: StepEnv) -> np.ndarray:
        return np.array([-1.0, 0.0, 0.0])


@dataclass
class CaptureStepController(StepController):
    """Analytic capture-point stepper: step to where the CoM is falling when it escapes the support.

    Law: read the capture-point offset ξ = (``cap_dx``, ``cap_dy``) from the support centre (the env builds
    it from the CLEAN base velocity, robust to contact transients). The support polygon is asymmetric — for
    TienKung the feet are ~0.26 m apart but only ~0.22 m long, so the lateral safe half-extent (~0.18 m) is
    much larger than the fore/aft one (~0.11 m). The controller therefore triggers when ξ leaves an
    elliptical safe region: ``(cap_dx/margin_x)^2 + (cap_dy/margin_y)^2 > 1`` (inside it the stiff hold / wide
    stance recovers, and a needless step would only break contact — the measured failure mode of eager
    stepping). On trigger (and no swing in progress, ≤ ``max_steps`` taken) it commands ``[1, bias_x, bias_y]``:
    the env plants the swing foot at the absolute capture point ξ by default; the bias (``overstep`` beyond ξ,
    in metres, along the fall direction) is the only "where" knob — a small overstep adds recovery margin. The
    env auto-selects the swing leg (the foot on the side the robot is falling toward) and runs the
    lift-swing-plant motion; this controller decides WHEN and the overstep.

    Defaults are TienKung's measured geometry. ``max_steps`` caps recovery steps per episode (a single
    capture step is the canonical case; a couple allows a second correction for a large push)."""

    margin_x: float = 0.11        #: fore/aft safe half-extent [m] (~half foot length) before stepping
    margin_y: float = 0.17        #: lateral safe half-extent [m] (~stance half-width) before stepping
    overstep: float = 0.06        #: plant the foot this far BEYOND ξ along the fall direction [m] (margin)
    max_steps: int = 2

    _stepped: int = field(default=0, repr=False, compare=False)

    def reset(self) -> None:
        self._stepped = 0

    def act(self, obs: np.ndarray, env: StepEnv) -> np.ndarray:
        ix = _obs_index(env)
        if obs[ix["swing_active"]] > 0.5:
            return np.array([-1.0, 0.0, 0.0])  # let the in-progress swing finish
        cap = np.array([obs[ix["cap_dx"]], obs[ix["cap_dy"]]])
        escaped = (cap[0] / self.margin_x) ** 2 + (cap[1] / self.margin_y) ** 2 > 1.0
        if escaped and self._stepped < self.max_steps:
            self._stepped += 1
            # overstep beyond the capture point along the fall direction, as a bounded action bias [-1,1]
            mag = float(np.hypot(*cap)) or 1.0
            bias = (cap / mag) * self.overstep
            bxn = float(np.clip(bias[0] / env.cfg.max_step_len, -1.0, 1.0))
            byn = float(np.clip(bias[1] / env.cfg.max_step_len, -1.0, 1.0))
            return np.array([1.0, bxn, byn])
        return np.array([-1.0, 0.0, 0.0])


@dataclass(frozen=True)
class StepRunResult:
    """Honest outcome of one controller run in the StepEnv under a push."""

    robot: str
    controller: str
    perturb: float
    direction_deg: float
    upright_seconds: float
    horizon_s: float
    fell: bool
    max_lean_deg: float
    n_steps_taken: int
    held_full_horizon: bool

    def summary(self) -> dict:
        return {
            "controller": self.controller, "perturb": self.perturb,
            "dir_deg": round(self.direction_deg, 0), "upright_s": round(self.upright_seconds, 3),
            "fell": self.fell, "max_lean_deg": round(self.max_lean_deg, 1),
            "n_steps": self.n_steps_taken, "held_full": self.held_full_horizon,
        }


def run_step_controller(robot: str, controller: StepController, *, perturb: float = 0.0,
                        direction_rad: float = 0.0, seconds: float = 3.0,
                        urdf_path: str | None = None, config: StepEnvConfig | None = None,
                        **cfg_overrides) -> StepRunResult:
    """Run ``controller`` in a FRESH :class:`StepEnv` under a reproducible base-velocity push.

    The push has magnitude ``perturb`` [m/s] in horizontal direction ``direction_rad`` applied right after
    reset (the disturbance to recover from). Returns the measured upright-seconds — never asserts success.
    A fresh env is built and closed here so callers get history-independent results. Raises if
    PyBullet/URDF/leg-chain are unavailable (fail-loud)."""
    if config is None:
        config = StepEnvConfig(robot=robot, urdf_path=urdf_path, horizon_s=seconds, **cfg_overrides)
    env = StepEnv(config)
    try:
        obs = env.reset()
        controller.reset()
        if perturb > 0.0:
            env.perturb_base_velocity(perturb * math.cos(direction_rad),
                                      perturb * math.sin(direction_rad))
            obs = env._observe()
        done = False
        fell = False
        steps = 0
        while not done:
            action = controller(obs, env)
            res = env.step(action)
            obs = res.observation
            done = res.done
            fell = res.fell
            steps += 1
        held = (not fell) and steps * config.control_dt >= config.horizon_s - 1e-9
        return StepRunResult(
            robot=robot, controller=type(controller).__name__, perturb=perturb,
            direction_deg=math.degrees(direction_rad), upright_seconds=env.upright_seconds,
            horizon_s=config.horizon_s, fell=fell, max_lean_deg=env.max_lean_deg,
            n_steps_taken=env._n_steps_taken, held_full_horizon=held)
    finally:
        env.close()


@dataclass(frozen=True)
class RecoveryStats:
    """Aggregated recovery performance of one controller across a push sweep (the honest summary)."""

    controller: str
    perturb: float
    n_conditions: int
    success_rate: float                    #: fraction of pushes survived to the full horizon
    mean_upright_s: float
    median_upright_s: float
    per_condition: tuple[StepRunResult, ...] = field(default_factory=tuple)

    def summary(self) -> dict:
        return {
            "controller": self.controller, "perturb": self.perturb,
            "n": self.n_conditions, "success_rate": round(self.success_rate, 3),
            "mean_upright_s": round(self.mean_upright_s, 3),
            "median_upright_s": round(self.median_upright_s, 3),
        }


def evaluate_recovery(robot: str, controllers: dict[str, StepController], *, perturb: float,
                      n_directions: int = 8, seconds: float = 3.0, urdf_path: str | None = None,
                      success_lean_horizon: bool = True,
                      **cfg_overrides) -> dict[str, RecoveryStats]:
    """Honest head-to-head: score each controller over ``n_directions`` evenly-spaced pushes of ``perturb``.

    For each controller and each push direction a FRESH StepEnv is built (mandatory — see
    [[rl-eval-methodology]]: PyBullet does not fully clear solver/contact state across resets within one
    client, which silently contaminated a prior eval). Returns ``{name: RecoveryStats}`` with the per-push
    results, the fraction that held the full horizon (success rate), and the mean/median upright-seconds.

    ``perturb`` should be a magnitude where the crouch+hold FAILS (so the question — does stepping recover
    where the hold cannot — is the one being answered). Directions are ``2π·k/n_directions``. Fresh
    controller instances are reset per run (their step-count state is per-episode)."""
    directions = [2.0 * math.pi * k / n_directions for k in range(n_directions)]
    out: dict[str, RecoveryStats] = {}
    for name, ctrl in controllers.items():
        results: list[StepRunResult] = []
        for d in directions:
            r = run_step_controller(robot, ctrl, perturb=perturb, direction_rad=d, seconds=seconds,
                                    urdf_path=urdf_path, **cfg_overrides)
            results.append(r)
        ups = [r.upright_seconds for r in results]
        succ = sum(1 for r in results if r.held_full_horizon) / len(results)
        out[name] = RecoveryStats(
            controller=name, perturb=perturb, n_conditions=len(results), success_rate=succ,
            mean_upright_s=float(np.mean(ups)), median_upright_s=float(np.median(ups)),
            per_condition=tuple(results))
    return out
