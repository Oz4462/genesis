"""balance_env — a reusable stand/balance ENVIRONMENT for real humanoid URDFs in PyBullet (headless).

This is the "make the harness a real stand/balance TRAINING environment" deliverable. It turns the
load/measure capabilities of :mod:`gen.humanoids.insim` into a Gym-style control loop — ``reset`` /
``step`` / ``observation`` / ``reward`` — that a controller (hand-written, LQR, or an RL policy) can
drive to make a downloaded humanoid stand upright. It is NOT itself a controller: it is the plant +
observation + reward + termination that a controller/learner acts on.

Design (grounded in measured behaviour of the real models — see the honest findings below):
  * Action = a torque command (N·m) per CONTROLLED joint (default: the two ankles' pitch+roll — the
    classic ankle balance strategy), applied on top of a stiff joint-space POSTURE PD that holds every
    other joint at its neutral standing pose. The controlled-joint set is configurable, so a learner
    can be given the hips/knees too (hip strategy) — the env does not hard-code which strategy works.
  * Observation = a flat float vector a policy can consume: base lean (relative tilt from the standing
    start), base angular velocity (the clean "IMU" signal), whole-body CoM position+velocity relative
    to a FIXED geometric support reference (the foot-mesh centroid computed once by FK — deliberately
    NOT the live contact centroid, which is too sparse/noisy on mesh feet to use as a control signal,
    a lesson learned the hard way), the controlled joints' angles+velocities, and the number of
    foot-ground contacts. :pyattr:`observation_labels` documents every entry.
  * Reward = an uprightness/standing shaping signal (upright bonus − lean − CoM-offset − CoM-speed −
    action effort), so the same env is usable for RL. The reward is shaping only; the honest success
    metric is :pyattr:`upright_seconds` (continuous time the base stayed within the fall threshold).
  * Termination = the base lean exceeds ``fall_tilt_deg`` (fell), the state goes non-finite, or the
    horizon is reached.

Determinism: a fixed PyBullet ``DIRECT`` client, fixed timestep + solver iters (inherited from
:mod:`gen.humanoids.insim`), so a fixed control sequence yields a bit-identical trajectory (the tests
pin this). PyBullet is an OPTIONAL dependency — :func:`gen.humanoids.insim.pybullet_available` gates it.

Reset protocol (matches the measured-correct standing placement): joints to the (configurable) standing
pose; the base lowered so the FEET — the lowest links — sit just above z=0 (NOT a global-AABB lower,
which can rest a shin/knee on the floor and leave the feet airborne — a real bug found during bring-up);
foot links given tuned contact (friction + contact stiffness/damping) so contact does not bounce. The
``t=0`` base orientation is captured as the uprightness reference (some URDF pelvis frames read a large
constant pitch at identity — e.g. TienKung ~25° — so absolute base-z tilt is misleading; lean is always
measured RELATIVE to this standing start, the same convention as ``insim._relative_tilt_deg``).

HONEST findings this env was validated against (reported, not hidden — CLAUDE.md fail-loud/no-spin rule):
  * Berkeley Humanoid Lite stands the full horizon under the env's stiff implicit-PD hold (flat box feet,
    ~0.85 m, near statically stable) — the positive control proving the env + loop work (it reproduces
    insim.pd_balance's 3 s result).
  * Tien Kung (1.69 m) from its straight-leg ZERO pose tips in ~1.2 s (CoM at the back edge of support),
    and — measured the hard way — NO ankle-only torque/angle PD law (CoM, attitude, or capture-point, any
    gains, in torque OR position mode) keeps it up: moving the ankles breaks the marginal foot contact and
    does worse than a passive hold. That is the textbook small basin of the ankle strategy on a tall
    humanoid. The WORKING solution this env ships is a posture one: a verified CROUCHED standing pose
    (:data:`RECOMMENDED_STANDING_POSE`, bent knees + matching hip/ankle pitch) lowers and centres the CoM
    so the stiff hold keeps Tien Kung upright the FULL horizon (8 s+ tested, deterministic, max lean
    < 1 deg) and recovers from a ~300 N · 0.08 s shove (larger pushes do topple it — the basin is finite).
    Tien Kung's straight-pose ~1.2 s and its crouch-pose full-horizon hold are BOTH reported honestly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from gen.humanoids import catalog
from gen.humanoids.insim import (
    STANDARD_GRAVITY,
    _FIXED_TIMESTEP,
    _SOLVER_ITERS,
    pybullet_available,
)

#: Forward offset [m] from the ankle-roll link origin to the foot sole's geometric centroid for the
#: bundled robots' foot meshes (measured from the foot STL bounds in the link frame). Used to place the
#: FIXED support reference at the true centre of the footprint rather than under the ankle pivot.
_FOOT_CENTROID_FWD = {"tienkung": 0.0245, "berkeley_lite": 0.0}

#: Verified statically-stable "ready" standing poses (joint targets [rad]) per robot. Tien Kung's
#: straight-leg ZERO pose puts its CoM at the back edge of the support and tips in ~1.2 s; a CROUCHED
#: stance (bent knees + matching hip/ankle pitch to keep the trunk vertical) lowers AND centres the CoM,
#: so the stiff hold keeps it upright the full horizon and recovers from a ~300 N·0.08 s shove (measured).
#: Berkeley is already stable from its zero pose, so its recommended pose is empty.
RECOMMENDED_STANDING_POSE: dict[str, dict[str, float]] = {
    "tienkung": {
        "knee_pitch_l_joint": 0.5, "knee_pitch_r_joint": 0.5,
        "hip_pitch_l_joint": -0.25, "hip_pitch_r_joint": -0.25,
        "ankle_pitch_l_joint": -0.25, "ankle_pitch_r_joint": -0.25,
    },
    "berkeley_lite": {},
}


def recommended_standing_pose(robot: str) -> dict[str, float]:
    """The verified statically-stable standing pose for ``robot`` (empty dict = the zero pose is fine).

    Use as ``BalanceEnvConfig(robot=..., standing_pose=recommended_standing_pose(robot))`` to start the
    robot in a posture it can actually hold. See :data:`RECOMMENDED_STANDING_POSE` for the rationale."""
    return dict(RECOMMENDED_STANDING_POSE.get(robot, {}))


@dataclass(frozen=True)
class BalanceEnvConfig:
    """Configuration for a :class:`BalanceEnv`. All physical knobs live here so a run is reproducible."""

    robot: str                                   #: catalog key (must have a URDF model_path)
    urdf_path: str | None = None                 #: override; defaults to the catalog's model_path
    controlled_joints: tuple[str, ...] | None = None  #: torque-controlled joints; None = the ankles
    control_dt: float = _FIXED_TIMESTEP          #: control period [s]; sim steps are _FIXED_TIMESTEP
    fall_tilt_deg: float = 50.0                  #: base lean beyond this = fallen (episode terminates)
    horizon_s: float = 3.0                       #: max episode length [s]
    posture_kp: float = 0.3                      #: POSITION_CONTROL positionGain on the held posture joints
    posture_kd: float = 0.02
    posture_max_force: float = 400.0
    action_mode: str = "position"               #: "position" = action is an ankle-angle CORRECTION [rad]
    #: added to the standing target and tracked by a stable implicit PD (POSITION_CONTROL) — robust,
    #: the default; "torque" = action is a raw joint torque [N·m] added to a torque-PD hold (a pure
    #: torque plant, less numerically stable, for users who specifically want torque control).
    action_torque_limit: float = 18.0            #: |torque| cap per controlled joint in "torque" mode [N·m]
    action_angle_limit: float = 0.30             #: |angle correction| cap per controlled joint in "position" mode [rad]
    ankle_kp: float = 0.08                       #: POSITION_CONTROL positionGain on the controlled joints
    ankle_kd: float = 0.004                      #: (implicit PD; same convention as the proven insim.pd_balance)
    ankle_max_force: float = 200.0               #: force cap on the controlled-joint position servo [N·m]
    ankle_hold_kp: float = 30.0                  #: torque-PD stiffness for "torque" mode hold (action added on top)
    ankle_hold_kd: float = 2.0
    ground_friction: float = 1.2
    foot_friction: float = 1.5
    foot_contact_stiffness: float = 1.0e5
    foot_contact_damping: float = 1.0e3
    standing_pose: dict[str, float] = field(default_factory=dict)  #: non-zero standing joint targets
    foot_clearance: float = 0.001                #: feet start this far above the ground [m]


@dataclass(frozen=True)
class StepResult:
    """One env transition (Gym-style): the next observation, reward, done flag, and honest diagnostics."""

    observation: np.ndarray
    reward: float
    done: bool
    fell: bool
    info: dict


class BalanceEnv:
    """A stand/balance environment for a real humanoid URDF, driven by per-joint torque actions.

    Lifecycle: construct with a :class:`BalanceEnvConfig`, call :meth:`reset` to get the first
    observation, then :meth:`step(action)` repeatedly. ``action`` is an array of torques [N·m], one per
    controlled joint (see :pyattr:`action_labels`), internally clipped to ``action_torque_limit``. The
    env owns one PyBullet ``DIRECT`` client for its whole lifetime and frees it in :meth:`close` (also a
    context manager). Raises immediately if PyBullet is unavailable or the URDF is missing — no silent
    no-op env (CLAUDE.md: no silent defaults for factual things).
    """

    def __init__(self, config: BalanceEnvConfig):
        if not pybullet_available():
            raise RuntimeError("PyBullet is not available — BalanceEnv needs it (see insim.pybullet_available).")
        import pybullet as p
        import pybullet_data

        self.cfg = config
        urdf = config.urdf_path
        if urdf is None:
            ref = catalog.ASSETS.get(config.robot)
            if ref is None or ref.model_path is None:
                raise ValueError(f"no URDF for robot {config.robot!r}; pass urdf_path explicitly")
            if ref.model_format != "urdf":
                raise ValueError(f"robot {config.robot!r} is {ref.model_format!r}, not a URDF — "
                                 "BalanceEnv is PyBullet/URDF; use insim_mujoco for MJCF models")
            urdf = ref.model_path
        from pathlib import Path
        if not Path(urdf).is_file():
            raise FileNotFoundError(f"URDF not found: {urdf}")
        self._urdf = urdf
        self._p = p
        self._client = p.connect(p.DIRECT)
        p.setGravity(0.0, 0.0, -STANDARD_GRAVITY, physicsClientId=self._client)
        p.setPhysicsEngineParameter(fixedTimeStep=_FIXED_TIMESTEP, numSolverIterations=_SOLVER_ITERS,
                                    physicsClientId=self._client)
        p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=self._client)
        self._sub_steps = max(1, int(round(config.control_dt / _FIXED_TIMESTEP)))

        self._plane = None
        self._bid = None
        self._build()  # load plane + robot, enumerate joints, find feet — once

    # ── construction helpers ───────────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        p, c = self._p, self._client
        self._plane = p.loadURDF("plane.urdf", physicsClientId=c)
        p.changeDynamics(self._plane, -1, lateralFriction=self.cfg.ground_friction, physicsClientId=c)
        self._bid = p.loadURDF(self._urdf, basePosition=[0, 0, 1.5], useFixedBase=False,
                               flags=p.URDF_USE_INERTIA_FROM_FILE, physicsClientId=c)
        nj = p.getNumJoints(self._bid, physicsClientId=c)
        self._nj = nj
        self._name2idx = {p.getJointInfo(self._bid, j, physicsClientId=c)[1].decode(): j for j in range(nj)}
        self._link2idx = {p.getJointInfo(self._bid, j, physicsClientId=c)[12].decode(): j for j in range(nj)}
        self._movable = [j for j in range(nj)
                         if p.getJointInfo(self._bid, j, physicsClientId=c)[2] != p.JOINT_FIXED]

        # controlled joints (default: ankles) — torque-actuated
        if self.cfg.controlled_joints is not None:
            ctrl_names = list(self.cfg.controlled_joints)
        else:
            ctrl_names = [n for n in ("ankle_pitch_l_joint", "ankle_roll_l_joint",
                                      "ankle_pitch_r_joint", "ankle_roll_r_joint") if n in self._name2idx]
            if not ctrl_names:  # robots that don't use that naming: fall back to any ankle/foot joints
                ctrl_names = [n for n in self._name2idx if "ankle" in n]
        missing = [n for n in ctrl_names if n not in self._name2idx]
        if missing:
            raise ValueError(f"controlled joints not in model: {missing}; have e.g. {sorted(self._name2idx)[:8]}")
        if not ctrl_names:
            raise ValueError(f"no controllable (ankle) joints found for {self.cfg.robot!r}")
        self._ctrl = [self._name2idx[n] for n in ctrl_names]
        self._ctrl_names = ctrl_names
        self._posture = [j for j in self._movable if j not in set(self._ctrl)]

        # foot links = the lowest links among the controlled ankle joints' child links (robust to the
        # exact naming: TienKung uses 'ankle_roll_l_link', Berkeley 'leg_left_ankle_roll', etc.). We take
        # the controlled joints' OWN child links and keep the ones whose collision sits near the bottom.
        cand = []
        for j in self._ctrl:
            child = p.getJointInfo(self._bid, j, physicsClientId=c)[12].decode()
            if child in self._link2idx:
                cand.append(self._link2idx[child])
        # add explicit *roll*-link / *foot* children (the actual sole-bearing links)
        for name, idx in self._link2idx.items():
            low = name.lower()
            if ("ankle_roll" in low or "foot" in low or "sole" in low) and "plane" not in low:
                cand.append(idx)
        cand = sorted(set(cand))
        if cand:
            # keep only the lowest-sitting links (the soles), within 5 cm of the lowest, so we don't tune
            # the whole shank as a "foot"
            zmins = {li: p.getAABB(self._bid, li, physicsClientId=c)[0][2] for li in cand}
            lo = min(zmins.values())
            self._foot_links = [li for li in cand if zmins[li] <= lo + 0.05]
        else:
            self._foot_links = []

    # ── env API ─────────────────────────────────────────────────────────────────────────────────────

    @property
    def action_labels(self) -> tuple[str, ...]:
        """Names of the torque-controlled joints, in action-vector order."""
        return tuple(self._ctrl_names)

    @property
    def action_dim(self) -> int:
        return len(self._ctrl)

    @property
    def observation_labels(self) -> tuple[str, ...]:
        """Human-readable label for each entry of the observation vector (same order as :meth:`reset`)."""
        base = ["base_lean_deg", "base_pitch_rel_deg", "base_roll_rel_deg",
                "base_wx", "base_wy", "base_wz",
                "com_dx", "com_dy", "com_vx", "com_vy", "n_contacts"]
        for n in self._ctrl_names:
            base.append(f"q[{n}]")
        for n in self._ctrl_names:
            base.append(f"qd[{n}]")
        return tuple(base)

    @property
    def observation_dim(self) -> int:
        return 11 + 2 * len(self._ctrl)

    def reset(self) -> np.ndarray:
        """Place the robot in its standing pose with feet on the ground and return the first observation.

        Sets every movable joint to its standing target (``standing_pose`` overlaid on the zero pose),
        lowers the base so the FEET sit ``foot_clearance`` above z=0, tunes foot contact, captures the
        standing base orientation + support reference, engages the posture PD, and zeroes the episode
        clock. Deterministic."""
        p, c = self._p, self._client
        # standing pose: the config's explicit pose if given, else the robot's verified stable pose
        pose = self.cfg.standing_pose if self.cfg.standing_pose else RECOMMENDED_STANDING_POSE.get(
            self.cfg.robot, {})
        self._active_pose = dict(pose)
        for j in self._movable:
            p.resetJointState(self._bid, j, pose.get(
                p.getJointInfo(self._bid, j, physicsClientId=c)[1].decode(), 0.0), physicsClientId=c)
        # lower so the feet (lowest links) sit just above the plane — NOT a global-AABB lower
        if self._foot_links:
            foot_low = min(p.getAABB(self._bid, fl, physicsClientId=c)[0][2] for fl in self._foot_links)
        else:
            foot_low = min(p.getAABB(self._bid, j, physicsClientId=c)[0][2] for j in range(-1, self._nj))
        bp, bo = p.getBasePositionAndOrientation(self._bid, physicsClientId=c)
        p.resetBasePositionAndOrientation(self._bid, (0.0, 0.0, bp[2] - foot_low + self.cfg.foot_clearance),
                                          bo, physicsClientId=c)
        p.resetBaseVelocity(self._bid, [0, 0, 0], [0, 0, 0], physicsClientId=c)
        for fl in self._foot_links:
            p.changeDynamics(self._bid, fl, lateralFriction=self.cfg.foot_friction, restitution=0.0,
                             contactStiffness=self.cfg.foot_contact_stiffness,
                             contactDamping=self.cfg.foot_contact_damping, physicsClientId=c)

        self._base_orn_ref = p.getBasePositionAndOrientation(self._bid, physicsClientId=c)[1]
        self._support_ref = self._compute_support_ref()
        # pendulum height = CoM height above the (now grounded) feet. The feet sit at ~foot_clearance
        # AFTER lowering, so measure the CoM against the CURRENT foot AABB min, not the pre-lowering one
        # (using the stale pre-lowering foot_low here understated h badly — fixed).
        if self._foot_links:
            foot_now = min(p.getAABB(self._bid, fl, physicsClientId=c)[0][2] for fl in self._foot_links)
        else:
            foot_now = self.cfg.foot_clearance
        self._h = max(0.05, self._whole_com()[2] - foot_now)  # pendulum height for capture-point use
        # posture PD on the held joints (stay at their standing target)
        for j in self._posture:
            tgt = p.getJointState(self._bid, j, physicsClientId=c)[0]
            p.setJointMotorControl2(self._bid, j, p.POSITION_CONTROL, targetPosition=tgt,
                                    positionGain=self.cfg.posture_kp, velocityGain=self.cfg.posture_kd,
                                    force=self.cfg.posture_max_force, physicsClientId=c)
        # controlled joints: record their standing targets so the action is a CORRECTION on top of a hold.
        self._ankle_targets = {j: p.getJointState(self._bid, j, physicsClientId=c)[0] for j in self._ctrl}
        if self.cfg.action_mode == "position":
            # hold via the stable implicit PD (POSITION_CONTROL); the action will shift these targets
            for j in self._ctrl:
                p.setJointMotorControl2(self._bid, j, p.POSITION_CONTROL, targetPosition=self._ankle_targets[j],
                                        positionGain=self.cfg.ankle_kp, velocityGain=self.cfg.ankle_kd,
                                        force=self.cfg.ankle_max_force, physicsClientId=c)
        elif self.cfg.action_mode == "torque":
            # disable the default velocity motor so an explicit torque acts purely (torque-PD hold in step)
            for j in self._ctrl:
                p.setJointMotorControl2(self._bid, j, p.VELOCITY_CONTROL, force=0.0, physicsClientId=c)
        else:
            raise ValueError(f"action_mode must be 'position' or 'torque', got {self.cfg.action_mode!r}")

        self._steps = 0
        self._upright_steps = 0
        self._still_up = True
        self._prev_com = self._whole_com()
        self._max_lean = 0.0
        return self._observe()

    def step(self, action) -> StepResult:
        """Apply per-controlled-joint torques (clipped), advance the sim one control period, return result.

        ``action`` is array-like of length :pyattr:`action_dim`. Returns a :class:`StepResult` with the
        next observation, the shaping reward, the done flag, whether the robot fell, and an info dict
        (lean, CoM offset, contacts, upright_seconds-so-far). Raises on wrong action length / non-finite
        action (fail-loud)."""
        p, c = self._p, self._client
        a = np.asarray(action, dtype=float).reshape(-1)
        if a.shape[0] != self.action_dim:
            raise ValueError(f"action has length {a.shape[0]}, expected {self.action_dim} "
                             f"(joints {self._ctrl_names})")
        if not np.all(np.isfinite(a)):
            raise ValueError("action contains non-finite values")
        if self.cfg.action_mode == "position":
            # action = ankle-angle CORRECTION [rad] on top of the standing target, tracked by the stable
            # implicit PD. A zero action holds the standing stance; the controller nudges ankle angles to
            # shift the ZMP and balance. Robust (no explicit-torque-PD instability).
            lim = self.cfg.action_angle_limit
            a = np.clip(a, -lim, lim)
            for dq, j in zip(a, self._ctrl):
                p.setJointMotorControl2(self._bid, j, p.POSITION_CONTROL,
                                        targetPosition=self._ankle_targets[j] + float(dq),
                                        positionGain=self.cfg.ankle_kp, velocityGain=self.cfg.ankle_kd,
                                        force=self.cfg.ankle_max_force, physicsClientId=c)
        else:  # "torque": total = torque-PD hold + the clipped action correction
            lim = self.cfg.action_torque_limit
            a = np.clip(a, -lim, lim)
            kp_h, kd_h = self.cfg.ankle_hold_kp, self.cfg.ankle_hold_kd
            for tau, j in zip(a, self._ctrl):
                q, qd = p.getJointState(self._bid, j, physicsClientId=c)[:2]
                hold = kp_h * (self._ankle_targets[j] - q) - kd_h * qd
                total = float(np.clip(hold + tau, -lim - kp_h, lim + kp_h))
                p.setJointMotorControl2(self._bid, j, p.TORQUE_CONTROL, force=total, physicsClientId=c)
        for _ in range(self._sub_steps):
            p.stepSimulation(physicsClientId=c)
        self._steps += 1

        bp, bo = p.getBasePositionAndOrientation(self._bid, physicsClientId=c)
        finite = all(math.isfinite(v) for v in (*bp, *bo))
        lean = self._lean_deg(bo) if finite else 180.0
        self._max_lean = max(self._max_lean, lean)
        fell = (not finite) or (lean > self.cfg.fall_tilt_deg)
        if self._still_up and not fell:
            self._upright_steps += 1
        elif self._still_up and fell:
            self._still_up = False
        horizon_reached = self._steps * self.cfg.control_dt >= self.cfg.horizon_s
        done = fell or horizon_reached or (not finite)

        obs = self._observe() if finite else np.zeros(self.observation_dim)
        reward = self._reward(lean, a, finite)
        info = {
            "lean_deg": lean, "fell": fell, "finite": finite,
            "upright_seconds": self.upright_seconds, "steps": self._steps,
            "n_contacts": self._n_contacts(), "com_offset": self._com_offset().tolist(),
            "horizon_reached": horizon_reached,
        }
        return StepResult(observation=obs, reward=reward, done=done, fell=fell, info=info)

    @property
    def upright_seconds(self) -> float:
        """Continuous time [s] the base stayed within the fall threshold from the start (the honest metric)."""
        return self._upright_steps * self.cfg.control_dt

    @property
    def max_lean_deg(self) -> float:
        return self._max_lean

    @property
    def pendulum_height(self) -> float:
        """CoM height above the feet at reset [m] — the LIP length (for capture-point controllers)."""
        return self._h

    @property
    def support_reference(self) -> np.ndarray:
        """The fixed (x, y) support-centroid reference the observation's CoM offset is measured against."""
        return self._support_ref.copy()

    # ── internals ──────────────────────────────────────────────────────────────────────────────────

    def _compute_support_ref(self) -> np.ndarray:
        p, c = self._p, self._client
        fwd = _FOOT_CENTROID_FWD.get(self.cfg.robot, 0.0)
        if self._foot_links:
            xs = [p.getLinkState(self._bid, fl, computeForwardKinematics=True, physicsClientId=c)[0]
                  for fl in self._foot_links]
            cx = sum(s[0] for s in xs) / len(xs) + fwd
            cy = sum(s[1] for s in xs) / len(xs)
            return np.array([cx, cy])
        bp = p.getBasePositionAndOrientation(self._bid, physicsClientId=c)[0]
        return np.array([bp[0], bp[1]])

    def _whole_com(self) -> np.ndarray:
        p, c = self._p, self._client
        tot = 0.0
        acc = np.zeros(3)
        bm = p.getDynamicsInfo(self._bid, -1, physicsClientId=c)[0]
        lip = p.getDynamicsInfo(self._bid, -1, physicsClientId=c)[3]
        bp, bo = p.getBasePositionAndOrientation(self._bid, physicsClientId=c)
        rot = np.array(p.getMatrixFromQuaternion(bo)).reshape(3, 3)
        acc += bm * (np.array(bp) + rot @ np.array(lip))
        tot += bm
        for j in range(self._nj):
            m = p.getDynamicsInfo(self._bid, j, physicsClientId=c)[0]
            if m <= 0:
                continue
            cw = p.getLinkState(self._bid, j, computeForwardKinematics=True, physicsClientId=c)[0]
            acc += m * np.array(cw)
            tot += m
        if tot <= 0:
            raise ValueError("total mass is zero — cannot compute CoM")
        return acc / tot

    def _com_offset(self) -> np.ndarray:
        com = self._whole_com()
        return np.array([com[0] - self._support_ref[0], com[1] - self._support_ref[1]])

    def _lean_deg(self, bo) -> float:
        p = self._p
        inv = p.invertTransform([0, 0, 0], self._base_orn_ref)[1]
        _, rel = p.multiplyTransforms([0, 0, 0], bo, [0, 0, 0], inv)
        w = max(-1.0, min(1.0, abs(rel[3])))
        return math.degrees(2.0 * math.acos(w))

    def _rel_rpy(self, bo):
        p = self._p
        inv = p.invertTransform([0, 0, 0], self._base_orn_ref)[1]
        _, rel = p.multiplyTransforms([0, 0, 0], bo, [0, 0, 0], inv)
        return p.getEulerFromQuaternion(rel)

    def _n_contacts(self) -> int:
        p, c = self._p, self._client
        return len(p.getContactPoints(self._bid, self._plane, physicsClientId=c))

    def _observe(self) -> np.ndarray:
        p, c = self._p, self._client
        bp, bo = p.getBasePositionAndOrientation(self._bid, physicsClientId=c)
        wv = p.getBaseVelocity(self._bid, physicsClientId=c)[1]
        roll, pitch, _ = self._rel_rpy(bo)
        lean = self._lean_deg(bo)
        com = self._whole_com()
        comv = (com - self._prev_com) / self.cfg.control_dt
        self._prev_com = com
        d = self._com_offset()
        nc = self._n_contacts()
        vals = [lean, math.degrees(pitch), math.degrees(roll),
                wv[0], wv[1], wv[2], d[0], d[1], comv[0], comv[1], float(nc)]
        for j in self._ctrl:
            vals.append(p.getJointState(self._bid, j, physicsClientId=c)[0])
        for j in self._ctrl:
            vals.append(p.getJointState(self._bid, j, physicsClientId=c)[1])
        return np.array(vals, dtype=float)

    def _reward(self, lean: float, action: np.ndarray, finite: bool) -> float:
        """Standing-shaping reward (shaping only — :pyattr:`upright_seconds` is the honest success metric).

        Upright bonus while within the fall threshold, minus lean, CoM horizontal offset, CoM speed, and
        a small action-effort penalty. Large negative on a non-finite (blown-up) state."""
        if not finite:
            return -100.0
        d = self._com_offset()
        com = self._whole_com()
        comv = (com - self._prev_com) / self.cfg.control_dt if self._steps else np.zeros(3)
        upright_bonus = 1.0 if lean <= self.cfg.fall_tilt_deg else 0.0
        r = (upright_bonus
             - 0.02 * lean
             - 2.0 * float(np.hypot(d[0], d[1]))
             - 0.2 * float(np.hypot(comv[0], comv[1]))
             - 0.001 * float(np.sum(np.square(action))))
        return float(r)

    def close(self) -> None:
        """Disconnect the PyBullet client (idempotent)."""
        if self._client is not None:
            try:
                self._p.disconnect(self._client)
            except Exception:
                pass
            self._client = None

    def __enter__(self) -> "BalanceEnv":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
