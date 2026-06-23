"""step_env — a DYNAMIC STEPPING / push-recovery environment for real humanoid URDFs (PyBullet, headless).

This is the deliberate next step beyond :class:`gen.humanoids.balance_env.BalanceEnv`. That env is a
*sway-in-place* plant: it holds a stance and lets a controller nudge ankle/hip/knee angles, and the
measured, repeatedly-confirmed result (TienKung, Berkeley, AGILOped, Asimov — 3-4 robots) is that for a
tall mesh-foot humanoid a stiff implicit-PD hold of a CROUCH pose beats EVERY active joint-motion strategy
(ankle OR hip+knee, PD OR RL), because moving joints in place lifts/breaks the marginal sole contact.
Stiffness, not control authority, is the lever for STATIC balance — and that strategy has a FINITE basin:
past a push of ~0.3-0.5 m/s the capture point leaves the support polygon and NO in-place strategy can keep
the robot upright. The physically-correct recovery is then a STEP: lift a foot, swing it out toward where
the centre of mass is heading, and plant it to create a new, shifted support polygon under the falling CoM.

This module models exactly that motion that the sway env structurally cannot:

  * It tracks WHICH foot is the stance foot and which is free (per-foot ground contact, not the aggregate).
  * A :meth:`StepEnv.step` either CONTINUES the current single/double-support phase or COMMITS A STEP:
    pick the swing leg + a target foot placement (x, y) in world, and the env executes the whole swing —
    lift the foot (PyBullet inverse kinematics on that leg's 6-DOF chain), swing it over the air to the
    target, lower and PLANT it — while holding the stance leg + trunk stiff. The contact transition (the
    swing foot leaves the ground, the new foot lands at a new x, y) is handled by the real contact solver,
    not faked.
  * Observation = the LIP/capture-point balance state the analytic stepper and an RL policy both need:
    base lean + angular velocity (IMU), whole-body CoM offset + velocity relative to the CURRENT support
    centre, the live capture point ξ = CoM + v·√(h/g) relative to support, per-foot contact flags, and the
    current feet positions relative to the base. :pyattr:`observation_labels` documents every entry.
  * Reward = stay upright (the honest success metric is still :pyattr:`upright_seconds`) with a shaping term
    that rewards driving the capture point back inside the support and penalises lean/CoM-speed/effort.

Honest scope (CLAUDE.md fail-loud / no-spin): this is a SIMPLIFIED stepping model. The swing is a scripted
joint-space interpolation to an IK target (not a torque-optimal swing trajectory); the stance leg is held
by the same stiff implicit PD that the balance env proved stable. The questions it answers honestly are:
(1) does committing a step move the support polygon under a CoM that the static crouch could NOT have held,
and (2) does that recover the robot (upright-seconds, success rate) at perturbations where crouch+hold FALLS
— compared head-to-head, fresh-env-per-episode, against crouch+hold and against an RL policy. It is NOT a
claim of a full dynamic walking gait.

Determinism: one PyBullet ``DIRECT`` client per env instance, fixed timestep + solver iters (inherited from
:mod:`gen.humanoids.insim`), so a fixed action sequence is bit-reproducible (the tests pin this). PyBullet
is OPTIONAL — :func:`gen.humanoids.insim.pybullet_available` gates it. Fresh-env-per-episode evaluation is
mandatory (see [[rl-eval-methodology]]); this env is built so a new instance per episode is cheap+clean.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from gen.humanoids import catalog
from gen.humanoids.balance_env import RECOMMENDED_STANDING_POSE
from gen.humanoids.insim import (
    STANDARD_GRAVITY,
    _FIXED_TIMESTEP,
    _SOLVER_ITERS,
    pybullet_available,
)

#: Per-robot leg chain description: the ordered 6-DOF joint names per leg and the foot (sole) link name.
#: Used to drive a swing leg via inverse kinematics and to read each foot's pose/contact. Only robots a
#: stepping motion has been wired+verified for appear here (fail-loud for others).
LEG_CHAINS: dict[str, dict[str, object]] = {
    "tienkung": {
        "left": {
            "joints": ("hip_roll_l_joint", "hip_yaw_l_joint", "hip_pitch_l_joint",
                       "knee_pitch_l_joint", "ankle_pitch_l_joint", "ankle_roll_l_joint"),
            "foot_link": "ankle_roll_l_link",
        },
        "right": {
            "joints": ("hip_roll_r_joint", "hip_yaw_r_joint", "hip_pitch_r_joint",
                       "knee_pitch_r_joint", "ankle_pitch_r_joint", "ankle_roll_r_joint"),
            "foot_link": "ankle_roll_r_link",
        },
    },
}


@dataclass(frozen=True)
class StepEnvConfig:
    """Configuration for a :class:`StepEnv`. All physical knobs here so a run is reproducible."""

    robot: str                                   #: catalog key (must have a URDF + a LEG_CHAINS entry)
    urdf_path: str | None = None                 #: override; defaults to the catalog's model_path
    standing_pose: dict[str, float] = field(default_factory=dict)  #: stance pose (default: the crouch)
    fall_tilt_deg: float = 50.0                  #: base lean beyond this = fallen (episode terminates)
    horizon_s: float = 4.0                       #: max episode length [s]
    control_dt: float = 0.02                     #: decision/control period [s] (10 sim sub-steps each)

    # posture + leg hold (the stance leg + trunk are held by the proven stiff implicit PD)
    posture_kp: float = 0.3
    posture_kd: float = 0.02
    posture_max_force: float = 400.0
    leg_kp: float = 0.5                           #: position-servo gain on the actively-driven leg joints
    leg_kd: float = 0.05
    leg_max_force: float = 400.0

    # step motion
    step_duration_s: float = 0.34                #: time for one lift+swing+place cycle [s]
    step_height: float = 0.07                    #: peak foot lift during swing [m]
    max_step_len: float = 0.32                   #: max commanded foot displacement from its nominal spot [m]
    min_double_support_s: float = 0.06           #: settle time in double support after a plant before re-stepping
    ik_iters: int = 80                           #: PyBullet IK iterations per swing waypoint

    # contact
    ground_friction: float = 1.2
    foot_friction: float = 1.5
    foot_contact_stiffness: float = 1.0e5
    foot_contact_damping: float = 1.0e3
    foot_clearance: float = 0.001
    contact_force_thresh: float = 5.0            #: normal force [N] above which a foot counts as "in contact"
    settle_s: float = 0.15                       #: settle the stance this long after reset before the clock starts
    #: (measured: <0.10 s leaves the feet at clearance with the contact solver not yet engaged → the reset
    #: observation reads 0 ground contacts; 0.10-0.15 s plants both coacd-hull feet with ~200 N each, the
    #: ~42 kg robot's weight split, and a stable ~0° lean — so the first observation reflects a real stance.)


@dataclass(frozen=True)
class StepResult:
    """One env transition: next observation, reward, done flag, fell flag, and honest diagnostics."""

    observation: np.ndarray
    reward: float
    done: bool
    fell: bool
    info: dict


class StepEnv:
    """A dynamic stepping / push-recovery environment for a real humanoid URDF.

    Lifecycle: construct with a :class:`StepEnvConfig`, call :meth:`reset` for the first observation, then
    :meth:`step(action)` repeatedly. The action (length :pyattr:`action_dim` = 3) is
    ``[step_trigger, target_dx, target_dy]``:

      * ``step_trigger`` > 0 and not already mid-swing and past the min double-support time → COMMIT a step:
        the env picks the swing leg automatically (the foot on the side the capture point is escaping toward,
        i.e. the trailing foot relative to the fall) and drives it to land at the target.
      * ``target_dx, target_dy`` ∈ [-1, 1] → the desired foot LANDING position relative to that foot's
        current spot, scaled to ``max_step_len`` (so the command is bounded by construction). An analytic
        capture-step controller sets these to the capture-point offset; an RL policy learns them.
      * ``step_trigger`` ≤ 0 (or mid-swing / too soon) → hold/continue: the stance is held; if a swing is in
        progress it advances one control tick along the scripted lift-swing-place trajectory.

    Once a step is committed the env keeps advancing the SAME swing on subsequent ``step``s until the foot
    plants (the per-call action's step fields are ignored mid-swing), so a controller can fire one trigger
    and let the motion complete. The env owns one PyBullet ``DIRECT`` client for its lifetime and frees it in
    :meth:`close` (also a context manager). Raises immediately if PyBullet is unavailable, the URDF is
    missing, or the robot has no :data:`LEG_CHAINS` entry — no silent no-op env (CLAUDE.md fail-loud)."""

    ACTION_DIM = 3

    def __init__(self, config: StepEnvConfig):
        if not pybullet_available():
            raise RuntimeError("PyBullet is not available — StepEnv needs it (see insim.pybullet_available).")
        import pybullet as p
        import pybullet_data

        self.cfg = config
        if config.robot not in LEG_CHAINS:
            raise ValueError(f"no LEG_CHAINS leg description for robot {config.robot!r}; "
                             f"have {sorted(LEG_CHAINS)} — add one to step a new robot")
        urdf = config.urdf_path
        if urdf is None:
            ref = catalog.ASSETS.get(config.robot)
            if ref is None or ref.model_path is None:
                raise ValueError(f"no URDF for robot {config.robot!r}; pass urdf_path explicitly")
            if ref.model_format != "urdf":
                raise ValueError(f"robot {config.robot!r} is {ref.model_format!r}, not a URDF")
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
        self._step_ticks = max(1, int(round(config.step_duration_s / config.control_dt)))
        self._min_ds_ticks = max(0, int(round(config.min_double_support_s / config.control_dt)))
        self._settle_steps = max(0, int(round(config.settle_s / _FIXED_TIMESTEP)))

        self._plane = None
        self._bid = None
        self._build()

    # ── construction ────────────────────────────────────────────────────────────────────────────────

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
        # IK joint-limit arrays (PyBullet IK uses ALL movable joints; we apply only the leg subset)
        self._ll = [p.getJointInfo(self._bid, j, physicsClientId=c)[8] for j in range(nj)]
        self._ul = [p.getJointInfo(self._bid, j, physicsClientId=c)[9] for j in range(nj)]
        self._jr = [max(0.1, u - l) for l, u in zip(self._ll, self._ul)]

        chains = LEG_CHAINS[self.cfg.robot]
        self._leg: dict[str, dict] = {}
        for side in ("left", "right"):
            spec = chains[side]
            jnames = list(spec["joints"])
            jidx = [self._name2idx[n] for n in jnames]
            foot = spec["foot_link"]
            if foot not in self._link2idx:
                raise ValueError(f"foot link {foot!r} not in model for {self.cfg.robot!r}")
            self._leg[side] = {"jnames": jnames, "jidx": jidx, "foot_link": foot,
                               "foot_idx": self._link2idx[foot]}
        self._foot_idx = {s: self._leg[s]["foot_idx"] for s in ("left", "right")}
        self._leg_joint_set = set(j for s in ("left", "right") for j in self._leg[s]["jidx"])
        # posture joints = every movable joint NOT in a leg chain (trunk, arms, hip yaw etc. stay put)
        self._posture = [j for j in self._movable if j not in self._leg_joint_set]

        # cache static mass data (masses + base inertial offset never change) → fast _whole_com
        self._base_mass = float(p.getDynamicsInfo(self._bid, -1, physicsClientId=c)[0])
        self._base_inertial_off = np.array(p.getDynamicsInfo(self._bid, -1, physicsClientId=c)[3])
        self._massive_links = [j for j in range(nj)
                               if p.getDynamicsInfo(self._bid, j, physicsClientId=c)[0] > 0.0]
        self._massive_masses = [float(p.getDynamicsInfo(self._bid, j, physicsClientId=c)[0])
                                for j in self._massive_links]

    # ── env API ─────────────────────────────────────────────────────────────────────────────────────

    @property
    def action_dim(self) -> int:
        return self.ACTION_DIM

    @property
    def action_labels(self) -> tuple[str, ...]:
        return ("step_trigger", "target_dx_norm", "target_dy_norm")

    @property
    def observation_labels(self) -> tuple[str, ...]:
        return (
            "base_lean_deg", "base_pitch_rel_deg", "base_roll_rel_deg",
            "base_wx", "base_wy", "base_wz",
            "com_dx", "com_dy", "com_vx", "com_vy",
            "cap_dx", "cap_dy",                       # capture point relative to current support centre
            "left_contact", "right_contact",
            "swing_active", "swing_phase",            # is a step in progress, and how far through (0..1)
            "lfoot_dx", "lfoot_dy", "rfoot_dx", "rfoot_dy",   # feet relative to base (xy)
        )

    @property
    def observation_dim(self) -> int:
        return 20

    @property
    def pendulum_height(self) -> float:
        return self._h

    @property
    def upright_seconds(self) -> float:
        return self._upright_steps * self.cfg.control_dt

    @property
    def max_lean_deg(self) -> float:
        return self._max_lean

    @property
    def support_centre(self) -> np.ndarray:
        """Current support polygon centre (xy): midpoint of grounded feet, or the stance foot if single."""
        return self._support_centre().copy()

    def reset(self) -> np.ndarray:
        """Place the robot in its stance with feet on the ground; return the first observation. Deterministic."""
        p, c = self._p, self._client
        pose = self.cfg.standing_pose if self.cfg.standing_pose else RECOMMENDED_STANDING_POSE.get(
            self.cfg.robot, {})
        self._active_pose = dict(pose)
        for j in self._movable:
            nm = p.getJointInfo(self._bid, j, physicsClientId=c)[1].decode()
            p.resetJointState(self._bid, j, pose.get(nm, 0.0), physicsClientId=c)
        # lower so both feet sit just above the plane
        foot_low = min(p.getAABB(self._bid, self._foot_idx[s], physicsClientId=c)[0][2]
                       for s in ("left", "right"))
        bp, bo = p.getBasePositionAndOrientation(self._bid, physicsClientId=c)
        p.resetBasePositionAndOrientation(
            self._bid, (0.0, 0.0, bp[2] - foot_low + self.cfg.foot_clearance), bo, physicsClientId=c)
        p.resetBaseVelocity(self._bid, [0, 0, 0], [0, 0, 0], physicsClientId=c)
        for s in ("left", "right"):
            p.changeDynamics(self._bid, self._foot_idx[s], lateralFriction=self.cfg.foot_friction,
                             restitution=0.0, contactStiffness=self.cfg.foot_contact_stiffness,
                             contactDamping=self.cfg.foot_contact_damping, physicsClientId=c)

        self._base_orn_ref = p.getBasePositionAndOrientation(self._bid, physicsClientId=c)[1]
        # pendulum height = CoM height above the grounded feet (LIP length for the capture point)
        foot_now = min(p.getAABB(self._bid, self._foot_idx[s], physicsClientId=c)[0][2]
                       for s in ("left", "right"))
        self._h = max(0.05, self._whole_com()[2] - foot_now)

        # hold the trunk/arms at their stance targets, and the legs at their stance targets (the action
        # will retarget a leg during a swing). All via the proven STABLE implicit PD (POSITION_CONTROL).
        self._leg_targets: dict[int, float] = {}
        for j in self._posture:
            tgt = p.getJointState(self._bid, j, physicsClientId=c)[0]
            p.setJointMotorControl2(self._bid, j, p.POSITION_CONTROL, targetPosition=tgt,
                                    positionGain=self.cfg.posture_kp, velocityGain=self.cfg.posture_kd,
                                    force=self.cfg.posture_max_force, physicsClientId=c)
        for j in self._leg_joint_set:
            q = p.getJointState(self._bid, j, physicsClientId=c)[0]
            self._leg_targets[j] = q
            p.setJointMotorControl2(self._bid, j, p.POSITION_CONTROL, targetPosition=q,
                                    positionGain=self.cfg.leg_kp, velocityGain=self.cfg.leg_kd,
                                    force=self.cfg.leg_max_force, physicsClientId=c)

        # settle the stance briefly so the feet make real contact BEFORE the episode clock starts (the
        # feet spawn ``foot_clearance`` above the plane; without settling the first observation reads zero
        # ground contacts and an artificially "floating" support — a bug found in bring-up). A few ms of the
        # stiff hold plants them deterministically; we then re-zero the episode state.
        for _ in range(self._settle_steps):
            p.stepSimulation(physicsClientId=c)

        # nominal foot positions (relative to base) at stance — used to define each foot's "home" spot
        self._nominal_foot_rel = {s: self._foot_rel_base(s) for s in ("left", "right")}

        self._steps = 0
        self._upright_steps = 0
        self._still_up = True
        self._max_lean = 0.0
        self._prev_com = self._whole_com()
        # swing state machine
        self._swing_side: str | None = None
        self._swing_tick = 0
        self._swing_start_world: np.ndarray | None = None   # foot xyz at lift-off
        self._swing_target_world: np.ndarray | None = None  # foot xyz to land at
        self._ticks_since_plant = self._min_ds_ticks        # allow an immediate first step
        self._n_steps_taken = 0
        return self._observe()

    def perturb_base_velocity(self, vx: float, vy: float, vz: float = 0.0) -> None:
        """Apply an instantaneous base linear-velocity push (m/s) — the disturbance to recover from.

        Call right after :meth:`reset`. This is the honest, reproducible perturbation the recovery is tested
        against (the same mechanism the balance env's eval uses)."""
        p, c = self._p, self._client
        p.resetBaseVelocity(self._bid, [float(vx), float(vy), float(vz)], [0, 0, 0], physicsClientId=c)
        self._prev_com = self._whole_com()

    def step(self, action) -> StepResult:
        """Advance one control period; commit/continue a step per the action. Returns a :class:`StepResult`.

        See the class docstring for the action semantics. Raises on wrong length / non-finite action."""
        p, c = self._p, self._client
        a = np.asarray(action, dtype=float).reshape(-1)
        if a.shape[0] != self.ACTION_DIM:
            raise ValueError(f"action length {a.shape[0]}, expected {self.ACTION_DIM} "
                             f"({self.action_labels})")
        if not np.all(np.isfinite(a)):
            raise ValueError("action contains non-finite values")

        if self._swing_side is None:
            # not currently stepping: maybe COMMIT a step
            trigger = a[0] > 0.0
            if trigger and self._ticks_since_plant >= self._min_ds_ticks:
                dx = float(np.clip(a[1], -1.0, 1.0)) * self.cfg.max_step_len
                dy = float(np.clip(a[2], -1.0, 1.0)) * self.cfg.max_step_len
                self._commit_step(dx, dy)
            else:
                self._ticks_since_plant += 1
        # if a swing is in progress (just committed or ongoing), advance it this tick
        if self._swing_side is not None:
            self._advance_swing()

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
            "swing_active": self._swing_side is not None, "n_steps_taken": self._n_steps_taken,
            "left_contact": self._foot_contact("left"), "right_contact": self._foot_contact("right"),
            "capture_offset": self._capture_offset().tolist(),
            "com_offset": self._com_offset().tolist(),
            "horizon_reached": horizon_reached,
        }
        return StepResult(observation=obs, reward=reward, done=done, fell=fell, info=info)

    # ── stepping mechanics ───────────────────────────────────────────────────────────────────────────

    def _commit_step(self, dx: float, dy: float) -> None:
        """Choose the swing leg and the landing target (capture point + bounded bias), and start the swing.

        The landing target is the absolute CAPTURE POINT ξ = CoM + v·√(h/g) (:meth:`_capture_point_world`,
        from the clean base velocity) plus a bounded action bias ``(dx, dy)`` [m, already scaled]. So a zero
        action plants the foot exactly at ξ — the textbook capture step that brings the LIP to rest — and a
        policy can refine where to land. Swing-leg choice is the foot on the side the robot is FALLING toward
        (ξ relative to the CoM in y): you step the foot INTO the fall to catch yourself (a +y fall → step the
        LEFT foot out to +y). A near-sagittal fall steps the less-loaded foot. The lift-off foot pose is
        recorded so the swing interpolates from it. Self-collision is avoided by keeping the swing foot on
        its own side of the stance foot."""
        p, c = self._p, self._client
        xi = self._capture_point_world()              # absolute capture point (world xy)
        com = self._whole_com()
        fall_y = xi[1] - com[1]                        # which lateral way the CoM is heading
        if abs(fall_y) > 0.03:
            side = "left" if fall_y > 0 else "right"   # step INTO the fall (toward the capture point)
        else:
            fl = self._foot_normal_force("left")
            fr = self._foot_normal_force("right")
            side = "left" if fl <= fr else "right"     # sagittal fall: swing the less-loaded foot
        foot_w = np.array(p.getLinkState(self._bid, self._foot_idx[side],
                                         computeForwardKinematics=True, physicsClientId=c)[0])
        # target = capture point + bounded bias, clamped to a reachable step from the current foot spot
        target = np.array([xi[0] + dx, xi[1] + dy, self.cfg.foot_clearance])
        disp = target[:2] - foot_w[:2]
        dist = float(np.hypot(*disp))
        if dist > self.cfg.max_step_len:               # clamp to the reachable step length
            disp = disp * (self.cfg.max_step_len / dist)
            target[0], target[1] = foot_w[0] + disp[0], foot_w[1] + disp[1]
        # keep the swing foot on its own side of the stance foot (no leg crossing / self-collision)
        stance = "right" if side == "left" else "left"
        stance_y = p.getLinkState(self._bid, self._foot_idx[stance],
                                  computeForwardKinematics=True, physicsClientId=c)[0][1]
        if side == "left":
            target[1] = max(target[1], stance_y + 0.10)
        else:
            target[1] = min(target[1], stance_y - 0.10)
        # Solve IK ONCE for the landing target and store the target leg-joint angles. The swing then
        # interpolates the leg joints in JOINT SPACE from their lift-off values to these — gentler than
        # re-IK-ing a fixed WORLD point every tick while the base falls, whose hard correction exerts a
        # large reaction torque on the free base and topples it (measured: a stiff world-IK swing threw the
        # robot over in 0.04 s). A smooth joint-space swing places the foot relative to the moving body, the
        # way a real recovery step swings the hip/knee out, not toward an inertial coordinate.
        sol = p.calculateInverseKinematics(
            self._bid, self._foot_idx[side], target.tolist(), lowerLimits=self._ll, upperLimits=self._ul,
            jointRanges=self._jr, restPoses=[p.getJointState(self._bid, j, physicsClientId=c)[0]
                                             for j in range(self._nj)],
            maxNumIterations=self.cfg.ik_iters, residualThreshold=1e-4, physicsClientId=c)
        movable = self._movable
        sol_by_jidx = {movable[i]: sol[i] for i in range(len(movable))}
        self._swing_q0 = {j: p.getJointState(self._bid, j, physicsClientId=c)[0]
                          for j in self._leg[side]["jidx"]}
        self._swing_q1 = {j: float(sol_by_jidx[j]) for j in self._leg[side]["jidx"] if j in sol_by_jidx}
        # knee joint of the swing leg, lifted extra mid-swing for ground clearance (bend then extend)
        self._swing_knee = self._name2idx.get(f"knee_pitch_{'l' if side == 'left' else 'r'}_joint")
        self._swing_side = side
        self._swing_tick = 0
        self._swing_start_world = foot_w
        self._swing_target_world = target

    def _advance_swing(self) -> None:
        """Advance the active swing by one control tick: JOINT-SPACE interpolate the swing leg toward the IK
        target computed at commit, with an extra knee bend mid-swing for ground clearance.

        Each leg joint moves smoothly q0 → q1 over the swing (a cosine ease-in/out so the leg accelerates and
        decelerates gently, minimising the reaction torque on the free base). The swing knee gets an extra
        ``step_height``-scaled flexion that peaks at mid-swing and returns to its landing value, so the foot
        lifts clear of the ground and sets back down. The stance leg + trunk stay held by their stiff PD.
        When the final tick lands, the swing ends and the double-support settle counter resets."""
        p, c = self._p, self._client
        self._swing_tick += 1
        phase = min(1.0, self._swing_tick / self._step_ticks)
        ease = 0.5 - 0.5 * math.cos(math.pi * phase)        # smooth 0→1 (cosine ease), gentle accel/decel
        lift = math.sin(math.pi * phase)                     # 0→1→0 bump for mid-swing clearance
        side = self._swing_side
        for j in self._leg[side]["jidx"]:
            q0 = self._swing_q0[j]
            q1 = self._swing_q1.get(j, q0)
            q = q0 + (q1 - q0) * ease
            if j == self._swing_knee:
                # bend the knee an extra amount mid-swing (positive = flex on TienKung) for foot clearance,
                # blended out by the end so it lands at the IK angle. ~1.3 rad/m of step height is enough.
                q = q + (self.cfg.step_height * 13.0) * lift
            self._leg_targets[j] = q
            p.setJointMotorControl2(self._bid, j, p.POSITION_CONTROL, targetPosition=q,
                                    positionGain=self.cfg.leg_kp, velocityGain=self.cfg.leg_kd,
                                    force=self.cfg.leg_max_force, physicsClientId=c)
        if self._swing_tick >= self._step_ticks:
            # plant: end the swing, lock the leg at its current (landed) angles, start double-support timer
            for j in self._leg[side]["jidx"]:
                q = p.getJointState(self._bid, j, physicsClientId=c)[0]
                self._leg_targets[j] = q
                p.setJointMotorControl2(self._bid, j, p.POSITION_CONTROL, targetPosition=q,
                                        positionGain=self.cfg.leg_kp, velocityGain=self.cfg.leg_kd,
                                        force=self.cfg.leg_max_force, physicsClientId=c)
            self._swing_side = None
            self._swing_start_world = None
            self._swing_target_world = None
            self._ticks_since_plant = 0
            self._n_steps_taken += 1

    # ── state readers ────────────────────────────────────────────────────────────────────────────────

    def _whole_com(self) -> np.ndarray:
        """Mass-weighted whole-body CoM (world xyz). Uses cached link masses + a single batched link-state
        read (``getLinkStates``) so it is cheap enough to call twice per control tick — the per-link
        ``getDynamicsInfo``/``getLinkState`` Python loop was the env's throughput bottleneck (halving the
        pybullet calls here ~doubled steps/s)."""
        p, c = self._p, self._client
        bp, bo = p.getBasePositionAndOrientation(self._bid, physicsClientId=c)
        rot = np.array(p.getMatrixFromQuaternion(bo)).reshape(3, 3)
        acc = self._base_mass * (np.array(bp) + rot @ self._base_inertial_off)
        tot = self._base_mass
        if self._massive_links:
            states = p.getLinkStates(self._bid, self._massive_links, computeForwardKinematics=True,
                                     physicsClientId=c)
            for m, st in zip(self._massive_masses, states):
                acc += m * np.array(st[0])
                tot += m
        if tot <= 0:
            raise ValueError("total mass is zero — cannot compute CoM")
        return acc / tot

    def _foot_world(self, side: str) -> np.ndarray:
        p, c = self._p, self._client
        return np.array(p.getLinkState(self._bid, self._foot_idx[side],
                                       computeForwardKinematics=True, physicsClientId=c)[0])

    def _foot_rel_base(self, side: str) -> np.ndarray:
        p, c = self._p, self._client
        bp = np.array(p.getBasePositionAndOrientation(self._bid, physicsClientId=c)[0])
        fw = self._foot_world(side)
        return (fw - bp)[:2]

    def _foot_normal_force(self, side: str) -> float:
        p, c = self._p, self._client
        pts = p.getContactPoints(self._bid, self._plane, self._foot_idx[side], -1, physicsClientId=c)
        return float(sum(pt[9] for pt in pts))

    def _foot_contact(self, side: str) -> float:
        """1.0 if this foot carries more than the contact-force threshold, else 0.0."""
        return 1.0 if self._foot_normal_force(side) > self.cfg.contact_force_thresh else 0.0

    def _base_vel_xy(self) -> np.ndarray:
        """Base link linear velocity (xy) [m/s] — the CLEAN, immediate fall signal.

        Why base velocity and not the CoM finite-difference: at the instant of a push and during a foot
        touchdown, the support-centre reference and the per-step CoM finite difference are corrupted by
        contact transients (measured during bring-up: the CoM-relative capture point briefly flips sign at
        the push and again at each plant), whereas the base linear velocity reads the disturbance correctly
        from the first tick. The capture point used for stepping decisions is built from this."""
        p, c = self._p, self._client
        return np.array(p.getBaseVelocity(self._bid, physicsClientId=c)[0][:2])

    def _capture_point_world(self) -> np.ndarray:
        """Absolute capture point ξ = CoM_xy + v·√(h/g) in world xy, using the clean base velocity.

        This is where the LIP predicts the CoM will come to rest; planting a foot here recaptures balance.
        Built from :meth:`_base_vel_xy` (robust) rather than the contact-corrupted CoM finite difference."""
        com = self._whole_com()
        v = self._base_vel_xy()
        w = math.sqrt(STANDARD_GRAVITY / max(0.05, self._h))
        return com[:2] + v / w

    def _support_centre(self) -> np.ndarray:
        """Support polygon centre (xy): the grounded feet's mean; if neither registers, both feet's mean."""
        grounded = [s for s in ("left", "right") if self._foot_contact(s) > 0.5]
        if not grounded:
            grounded = ["left", "right"]
        xs = [self._foot_world(s) for s in grounded]
        return np.array([sum(x[0] for x in xs) / len(xs), sum(x[1] for x in xs) / len(xs)])

    def _com_offset(self) -> np.ndarray:
        com = self._whole_com()
        sc = self._support_centre()
        return np.array([com[0] - sc[0], com[1] - sc[1]])

    def _capture_offset(self) -> np.ndarray:
        """Capture point ξ relative to the current support centre (xy), from the CLEAN base velocity.

        Uses :meth:`_capture_point_world` (built on the robust base linear velocity) rather than the CoM
        per-step finite difference, which is corrupted by contact transients at the push and at each foot
        plant (measured: the finite-difference capture point briefly flips sign there). |ξ| exceeding the
        support half-extent is the signal that an in-place hold cannot recover and a step is needed."""
        xi = self._capture_point_world()
        sc = self._support_centre()
        return xi - sc

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
        cap = self._capture_offset()
        lc, rc = self._foot_contact("left"), self._foot_contact("right")
        swing_active = 1.0 if self._swing_side is not None else 0.0
        swing_phase = (self._swing_tick / self._step_ticks) if self._swing_side is not None else 0.0
        lf = self._foot_rel_base("left")
        rf = self._foot_rel_base("right")
        vals = [lean, math.degrees(pitch), math.degrees(roll),
                wv[0], wv[1], wv[2],
                d[0], d[1], comv[0], comv[1],
                cap[0], cap[1],
                lc, rc, swing_active, swing_phase,
                lf[0], lf[1], rf[0], rf[1]]
        return np.array(vals, dtype=float)

    def _reward(self, lean: float, action: np.ndarray, finite: bool) -> float:
        """Stay-upright shaping reward. Honest success metric remains :pyattr:`upright_seconds`.

        Upright bonus while within the fall threshold, minus a term pulling the CAPTURE POINT back inside
        the support (the right objective for stepping — a step that recaptures balance reduces |ξ|), minus
        lean and CoM speed, minus a small per-step step-effort cost so it does not flail. Large negative on
        a non-finite (blown-up) state."""
        if not finite:
            return -100.0
        cap = self._capture_offset()
        com = self._whole_com()
        comv = (com - self._prev_com) / self.cfg.control_dt if self._steps else np.zeros(3)
        upright_bonus = 1.0 if lean <= self.cfg.fall_tilt_deg else 0.0
        step_cost = 0.05 if (action[0] > 0.0 and self._swing_side is not None
                             and self._swing_tick <= 1) else 0.0
        r = (upright_bonus
             - 0.02 * lean
             - 1.5 * float(np.hypot(cap[0], cap[1]))
             - 0.2 * float(np.hypot(comv[0], comv[1]))
             - step_cost)
        return float(r)

    # ── lifecycle ────────────────────────────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Disconnect the PyBullet client (idempotent)."""
        if self._client is not None:
            try:
                self._p.disconnect(self._client)
            except Exception:
                pass
            self._client = None

    def __enter__(self) -> "StepEnv":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
