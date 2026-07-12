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
from dataclasses import dataclass, field

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


def _signed_action(env: BalanceEnv, cmd: dict[str, float]) -> np.ndarray:
    """Map a {joint-substring: command} dict onto the env's controlled-joint action vector.

    For each controlled joint, the first ``cmd`` key that is a substring of the joint name supplies its
    value (0 if none match). This lets a whole-body controller address hip/knee/ankle pitch+roll joints by
    name-fragment without depending on the joint ordering. Units follow ``action_mode`` (rad in the default
    position mode). ``_l_``/``_r_`` suffixes are matched too, so e.g. ``"hip_pitch"`` hits both legs."""
    a = np.zeros(env.action_dim)
    for i, name in enumerate(env.action_labels):
        for frag, val in cmd.items():
            if frag in name:
                a[i] = val
                break
    return a


@dataclass
class WholeBodyPDController(BalanceController):
    """Whole-body sagittal+lateral balance using HIP+KNEE(+ankle) authority — the hip strategy.

    The proven ankle-only ceiling on a tall humanoid is that tilting the ankle lifts the sole and breaks
    foot contact. This controller instead shifts the CoM back over the support by COORDINATED hip/knee
    motion that keeps the soles flat: a forward CoM error (CoM ahead of its EQUILIBRIUM offset) is
    corrected by flexing the hips/knees to draw the trunk mass back, and vice-versa. A small optional
    ankle term is added but is NOT the primary lever (it can be set to 0 to prove hip+knee alone works).

    CRITICAL — regulate around the standing pose's EQUILIBRIUM CoM offset, not zero. The verified crouch
    sits with its CoM at a small natural backward offset from the geometric support centre (TienKung:
    ``com_dx`` ≈ −0.055 m at rest). That offset is the stable operating point, NOT an error. A first version
    of this controller regulated ``com_dx`` to zero and immediately destabilised the crouch (measured: lean
    0.5°→49° in 0.25 s, feet left the ground) because it kept driving the hips to "fix" the natural offset.
    The fix: capture the CoM offset at the first :meth:`act` after :meth:`reset` as the setpoint, and do PD
    on the DEVIATION from it. So the controller holds the crouch and only reacts to disturbances.

    The control law is PD on (CoM offset − equilibrium) + CoM velocity about the fixed support reference
    (the clean, contact-independent signal), distributed onto the sagittal chain (hip_pitch, knee_pitch,
    ankle_pitch) with per-joint gain signs/scales, and a separate lateral PD onto the roll chain (hip_roll,
    ankle_roll). The signs (:pyattr:`hip_pitch_sign` etc.) encode which way each joint moves the CoM for
    THIS robot's URDF sign convention; defaults are TienKung's, MEASURED by :func:`calibrate_whole_body_signs`
    (re-derive them for a different robot).

    Gains are interpreted in the env's ``action_mode`` units (rad of joint-angle correction in the default
    position mode). ``kp`` [rad per m of CoM offset], ``kd`` [rad per m/s of CoM velocity]."""

    kp: float = 1.6
    kd: float = 0.35
    kp_lat: float = 1.2
    kd_lat: float = 0.25
    # Defaults are TienKung's MEASURED signs (calibrate_whole_body_signs): +hip_pitch moves the CoM
    # BACKWARD (dcom_x ≈ −0.26 m/rad), so to oppose a +com_dx (CoM ahead of foot) we command +hip_pitch
    # → sign +1. knee_pitch similarly (dcom_x ≈ −0.20) with a smaller 0.6 weight (it mostly lowers the CoM).
    # hip_roll +delta moves the CoM +y (dcom_y ≈ +0.12), so to oppose +com_dy we command −hip_roll.
    hip_pitch_sign: float = 1.0       #: command to hip_pitch per +1 sagittal correction (MEASURED)
    knee_pitch_sign: float = 0.6      #: command to knee_pitch per +1 sagittal correction (smaller, vertical)
    ankle_pitch_sign: float = 0.0     #: ankle contribution (default OFF — prove hip+knee alone; ankle breaks contact)
    hip_roll_sign: float = -1.0       #: command to hip_roll per +1 lateral correction (MEASURED)
    ankle_roll_sign: float = 0.0
    max_cmd: float = 0.30             #: clip each per-joint command [rad] (matches env action_angle_limit)

    #: equilibrium CoM offset (dx0, dy0) captured at the first act() after reset; PD regulates DEVIATION
    #: from this, so the controller holds the crouch's natural offset instead of fighting it.
    _eq: tuple[float, float] | None = field(default=None, repr=False, compare=False)

    def reset(self) -> None:
        """Clear the captured equilibrium so it is re-measured on the next episode's first act()."""
        self._eq = None

    def act(self, obs: np.ndarray, env: BalanceEnv) -> np.ndarray:
        ix = _obs_index(env)
        dx, dy = obs[ix["com_dx"]], obs[ix["com_dy"]]
        vx, vy = obs[ix["com_vx"]], obs[ix["com_vy"]]
        if self._eq is None:
            self._eq = (float(dx), float(dy))   # capture the standing equilibrium offset as the setpoint
        ex, ey = dx - self._eq[0], dy - self._eq[1]   # deviation from equilibrium
        # sagittal correction magnitude: positive when CoM is ahead of its equilibrium and/or moving forward
        sag = self.kp * ex + self.kd * vx
        lat = self.kp_lat * ey + self.kd_lat * vy
        clip = self.max_cmd
        cmd = {
            "hip_pitch": float(np.clip(self.hip_pitch_sign * sag, -clip, clip)),
            "knee_pitch": float(np.clip(self.knee_pitch_sign * sag, -clip, clip)),
            "ankle_pitch": float(np.clip(self.ankle_pitch_sign * sag, -clip, clip)),
            "hip_roll": float(np.clip(self.hip_roll_sign * lat, -clip, clip)),
            "ankle_roll": float(np.clip(self.ankle_roll_sign * lat, -clip, clip)),
        }
        return _signed_action(env, cmd)


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


def calibrate_whole_body_signs(robot: str, *, delta: float = 0.05,
                               config: BalanceEnvConfig | None = None,
                               **cfg_overrides) -> dict[str, float]:
    """Measure each balance joint's effect on the whole-body CoM, returning grounded controller signs.

    For ``robot`` in its standing pose, this nudges hip_pitch / knee_pitch / ankle_pitch (both legs
    together) by +``delta`` rad and measures the resulting change in CoM_x, and nudges hip_roll /
    ankle_roll and measures the change in CoM_y — i.e. a one-column CoM Jacobian per joint group. It then
    returns the SIGN each joint should get in :class:`WholeBodyPDController` so that a positive sagittal/
    lateral correction (used to oppose a +offset) actually moves the CoM the right way. This replaces
    guessing the URDF sign convention with a measurement (CLAUDE.md: no silent assumed values).

    Returns a dict with keys ``hip_pitch_sign``, ``knee_pitch_sign``, ``ankle_pitch_sign``,
    ``hip_roll_sign``, ``ankle_roll_sign`` plus ``*_dcom`` raw sensitivities [m/rad] for transparency.
    Fail-loud if PyBullet/URDF unavailable."""
    if config is None:
        config = BalanceEnvConfig(robot=robot, horizon_s=0.1, **cfg_overrides)
    env = BalanceEnv(config)
    try:
        env.reset()
        p, c, bid = env._p, env._client, env._bid
        name2idx = env._name2idx

        def com_after_nudge(frag: str, axis: int) -> float:
            # set joints whose name contains frag to (current standing target + delta), settle briefly,
            # read whole-body CoM along axis; then restore. We re-reset to isolate each probe.
            env.reset()
            for nm, j in name2idx.items():
                if frag in nm:
                    tgt = env._ankle_targets.get(j)
                    base = tgt if tgt is not None else p.getJointState(bid, j, physicsClientId=c)[0]
                    p.resetJointState(bid, j, base + delta, physicsClientId=c)
                    p.setJointMotorControl2(bid, j, p.POSITION_CONTROL, targetPosition=base + delta,
                                            positionGain=0.3, velocityGain=0.05, force=400.0,
                                            physicsClientId=c)
            for _ in range(40):
                p.stepSimulation(physicsClientId=c)
            return float(env._whole_com()[axis])

        env.reset()
        for _ in range(40):
            p.stepSimulation(physicsClientId=c)
        com0 = env._whole_com()
        out: dict[str, float] = {}
        for frag, axis in (("hip_pitch", 0), ("knee_pitch", 0), ("ankle_pitch", 0),
                            ("hip_roll", 1), ("ankle_roll", 1)):
            present = any(frag in nm for nm in name2idx)
            if not present:
                out[f"{frag}_sign"] = 0.0
                out[f"{frag}_dcom"] = 0.0
                continue
            dcom = (com_after_nudge(frag, axis) - com0[axis]) / delta  # m per rad
            out[f"{frag}_dcom"] = dcom
            # to OPPOSE a +offset we want a command that moves CoM negative; command = sign * correction,
            # correction>0 for +offset, so sign = -1 if +joint moves CoM +, +1 if it moves CoM -.
            out[f"{frag}_sign"] = (0.0 if abs(dcom) < 1e-4
                                   else (-1.0 if dcom > 0 else 1.0) * (0.6 if "knee" in frag else 1.0))
        return out
    finally:
        env.close()


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
