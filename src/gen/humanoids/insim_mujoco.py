"""insim_mujoco — load REAL open-source humanoid MJCF models into the MuJoCo engine (headless).

This is the MuJoCo analogue of :mod:`gen.humanoids.insim` (which does the same three things in PyBullet
for URDF models). It exists because some of the acquired humanoids ship a native MuJoCo model rather
than (or in addition to) a URDF — notably **Asimov v1**, whose only machine-readable model in the repo
is ``sim-model/xmls/asimov.xml``. To validate that model in its own engine, this module does what an
articulated-body engine can do that the closed-form screens and the structural XML parser cannot:

  1. LOAD + INSTANTIATE the MJCF *with its meshes* — proving the file is not just well-formed XML but a
     model MuJoCo compiles, with the body/joint/geom counts and total mass it actually instantiates
     (cross-checked against :mod:`gen.humanoids.model_parser` / catalog figures).
  2. MEASURE A POSE'S STATICS the engine's own way — MuJoCo's recursive Newton-Euler inverse dynamics
     (``mj_inverse``) at zero velocity and zero acceleration gives the generalized force needed to hold
     the configuration; its joint-space entries are the gravity-hold joint torques, the same quantity
     GENESIS's ``static_joint_torques`` predicts in closed form. The whole-body CoM is read from
     ``data.subtree_com`` of the root subtree.
  3. SIMULATE UNDER GRAVITY — a reproducible drop/stability test (set a pose, step the real dynamics,
     record the floating-base height + tilt over time: does it stay upright, how does it fall?).

MuJoCo is run **headless** (no viewer, no GL) with the model's own (fixed) timestep, so two runs are
bit-identical (the tests pin this). It is an OPTIONAL dependency: :func:`mujoco_available` lets
callers/tests skip cleanly when it is absent, exactly like ``insim.pybullet_available``.

Honesty boundaries (stated, not hidden):
  * Inverse dynamics at a held pose is the gravity (+ passive spring) term only (zero q̇, q̈) — the same
    regime as the closed form, so the comparison is fair. It is NOT a dynamic gait torque.
  * ``mj_inverse`` returns the generalized force to hold the WHOLE state, including any active
    contact/constraint forces at that configuration. Held free in space (the default for ``pose_statics``
    here), the joint-space entries are the clean gravity/spring hold torques; the first six entries are
    the floating-base wrench and are reported separately, not as a joint torque.
  * The drop test is a QUALITATIVE stability check (finite, no NaN explosion, falls/stands under
    gravity) — not a quantitative contact/energy validation.
  * SCOPE NOTE — no balance controller here. The Asimov MJCF declares **zero actuators** (``nu == 0``):
    the upper-body joints are passive damped springs and the legs have no ``<actuator>`` elements, so a
    torque/PD balance controller would first require adding actuators (or driving ``qfrc_applied``
    directly). That is deliberately out of scope for this structural+statics+drop validation module;
    the PyBullet ``insim.pd_balance`` covers the closed-loop demo for the URDF robots.

Source: MuJoCo 3.x rigid-body dynamics; ``mj_inverse`` is the recursive Newton-Euler inverse dynamics;
``model.body_mass`` / ``data.subtree_com`` give per-body mass + subtree centre of mass.
"""

from __future__ import annotations

import contextlib
import math
from dataclasses import dataclass, field
from pathlib import Path

#: Standard gravity [m/s^2] — matches GENESIS's other axes (kinematics, actuation) and insim.py.
STANDARD_GRAVITY = 9.80665

#: MuJoCo joint type codes (mjtJoint): 0 free, 1 ball, 2 slide, 3 hinge.
_JTYPE = {0: "free", 1: "ball", 2: "slide", 3: "hinge"}


def mujoco_available() -> bool:
    """True if MuJoCo can be imported in this environment (callers/tests skip cleanly otherwise)."""
    try:
        import mujoco  # noqa: F401
        return True
    except Exception:
        return False


def _load_model(mjcf_path: str):
    """Compile an MJCF *file* into an ``mjModel`` (meshes resolved via the model's own ``meshdir``).

    Raises FileNotFoundError if the path is missing (no silent empty model) — fail-loud per CLAUDE.md.
    Any MuJoCo compile error (bad schema, missing mesh) propagates verbatim, not swallowed."""
    import mujoco
    pth = Path(mjcf_path)
    if not pth.is_file():
        raise FileNotFoundError(f"MJCF not found: {pth}")
    return mujoco.MjModel.from_xml_path(str(pth))


# ── load + structure (in-engine ground truth) ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class MjJointInfo:
    """One joint as MuJoCo instantiated it (index, name, type, limits)."""
    index: int
    name: str
    type_name: str          #: "free" | "ball" | "slide" | "hinge"
    limited: bool
    lower: float
    upper: float


@dataclass(frozen=True)
class MjLoadResult:
    """What MuJoCo instantiated from the MJCF — the in-engine corroboration of the structure."""
    robot: str
    mjcf_path: str
    nbody: int                            #: bodies incl. the world body (MuJoCo convention)
    njnt: int                             #: all joints incl. the free base
    free_joints: int
    ball_joints: int
    slide_joints: int
    hinge_joints: int
    num_actuators: int                    #: nu — number of <actuator> elements (0 = none defined)
    nq: int                               #: generalized-position dimension
    nv: int                               #: generalized-velocity / DOF dimension
    ngeom: int
    total_mass_kg: float                  #: Σ body mass (world body has mass 0) — the true total mass
    joints: tuple[MjJointInfo, ...] = field(default_factory=tuple)

    @property
    def actuated_hinge_dof(self) -> int:
        """Hinge joints = the rotary DOF (the headline 'DOF' for a humanoid, base excluded)."""
        return self.hinge_joints + self.ball_joints + self.slide_joints

    def summary(self) -> dict:
        return {
            "robot": self.robot, "nbody": self.nbody, "njnt": self.njnt,
            "free": self.free_joints, "hinge": self.hinge_joints, "ball": self.ball_joints,
            "slide": self.slide_joints, "actuators": self.num_actuators,
            "nq": self.nq, "nv": self.nv, "ngeom": self.ngeom,
            "total_mass_kg": round(self.total_mass_kg, 4),
        }


def load_structure(robot: str, mjcf_path: str) -> MjLoadResult:
    """Compile the MJCF in MuJoCo and read off the structure it instantiates.

    The in-engine cross-check of the parser's DOF + mass: body/joint/geom counts, the joint-type split
    (free/ball/slide/hinge), the actuator count (``nu``), the generalized coordinate sizes (nq, nv) and
    the true total mass (Σ ``model.body_mass``; the world body contributes 0). Raises if MuJoCo is
    unavailable (call :func:`mujoco_available` first) or the MJCF is missing/uncompilable."""
    import mujoco
    m = _load_model(mjcf_path)
    free = ball = slide = hinge = 0
    joints: list[MjJointInfo] = []
    for j in range(m.njnt):
        t = int(m.jnt_type[j])
        tname = _JTYPE.get(t, str(t))
        if tname == "free":
            free += 1
        elif tname == "ball":
            ball += 1
        elif tname == "slide":
            slide += 1
        elif tname == "hinge":
            hinge += 1
        name = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, j) or f"joint{j}"
        limited = bool(m.jnt_limited[j])
        lo, hi = float(m.jnt_range[j][0]), float(m.jnt_range[j][1])
        joints.append(MjJointInfo(index=j, name=name, type_name=tname,
                                  limited=limited, lower=lo, upper=hi))
    total_mass = float(sum(m.body_mass))  # world body mass is 0 → this is the robot's total mass
    return MjLoadResult(
        robot=robot, mjcf_path=mjcf_path, nbody=int(m.nbody), njnt=int(m.njnt),
        free_joints=free, ball_joints=ball, slide_joints=slide, hinge_joints=hinge,
        num_actuators=int(m.nu), nq=int(m.nq), nv=int(m.nv), ngeom=int(m.ngeom),
        total_mass_kg=total_mass, joints=tuple(joints))


# ── pose statics (gravity-hold inverse dynamics + CoM) ────────────────────────────────────────────

@dataclass(frozen=True)
class MjPoseStatics:
    """The engine's statics at one held pose: whole-body CoM + gravity-hold generalized forces.

    ``joint_torques`` maps each hinge/ball/slide joint name to its gravity-hold generalized force
    [N·m or N]; ``base_wrench`` is the six free-base entries (force x/y/z, torque x/y/z) reported
    separately because they are NOT a joint torque (see the module honesty boundaries)."""
    robot: str
    com_world: tuple[float, float, float]
    total_mass_kg: float
    joint_torques: dict[str, float]
    base_wrench: tuple[float, ...]         #: the nv free-base entries, or () if the root is not free
    max_joint_torque_nm: float


def pose_statics(robot: str, mjcf_path: str,
                 joint_positions: dict[str, float] | None = None,
                 *, base_height: float | None = None) -> MjPoseStatics:
    """Hold the robot at ``joint_positions`` (free in space) and read the engine's gravity statics.

    MuJoCo ``mj_inverse`` with zero velocity and zero acceleration returns the generalized force that
    holds the configuration — MuJoCo's own answer to what GENESIS's ``static_joint_torques`` predicts.
    The whole-body CoM is ``data.subtree_com[0]`` (root-subtree centre of mass) after ``mj_forward``.
    Joints not named in ``joint_positions`` keep their model default. The base is held high enough that
    the model's own foot/floor geoms do not contact (so the joint-space entries are the clean
    gravity/passive-spring hold torques, not a contact reaction); pass ``base_height`` to override.
    Raises if MuJoCo is unavailable or a named joint is unknown."""
    import mujoco
    import numpy as np
    m = _load_model(mjcf_path)
    d = mujoco.MjData(m)
    # name -> qpos address for the scalar (non-free) joints we may want to set
    name_to_qadr: dict[str, int] = {}
    for j in range(m.njnt):
        if int(m.jnt_type[j]) in (1, 2, 3):  # ball/slide/hinge are scalar-settable here (hinge/slide 1 dof)
            nm = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, j) or f"joint{j}"
            name_to_qadr[nm] = int(m.jnt_qposadr[j])
    mujoco.mj_resetData(m, d)
    # lift the free base clear of the floor plane so held statics are contact-free (if a free base exists)
    has_free = any(int(m.jnt_type[j]) == 0 for j in range(m.njnt))
    if has_free:
        # free joint occupies qpos[0:7] = (x,y,z, qw,qx,qy,qz); raise z well above any foot
        d.qpos[2] = 5.0 if base_height is None else float(base_height)
    if joint_positions:
        for nm, val in joint_positions.items():
            if nm not in name_to_qadr:
                raise ValueError(f"unknown joint {nm!r}; have {sorted(name_to_qadr)[:6]}…")
            d.qpos[name_to_qadr[nm]] = float(val)
    mujoco.mj_forward(m, d)            # establish kinematics + CoM for the held pose
    d.qvel[:] = 0.0
    d.qacc[:] = 0.0
    mujoco.mj_inverse(m, d)           # qfrc_inverse = generalized force to hold (q̇=q̈=0)
    qf = np.asarray(d.qfrc_inverse, dtype=float)

    com = tuple(float(x) for x in d.subtree_com[0])
    total_mass = float(sum(m.body_mass))
    # map each scalar joint's dof entry to its gravity-hold force; collect the free-base wrench apart
    joint_torques: dict[str, float] = {}
    base_wrench: list[float] = []
    for j in range(m.njnt):
        t = int(m.jnt_type[j])
        dofadr = int(m.jnt_dofadr[j])
        if t == 0:  # free base: 6 dof wrench
            base_wrench = [float(qf[dofadr + k]) for k in range(6)]
        elif t in (1,):  # ball: 3 dof — report the 3-vector norm under the joint name
            nm = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, j) or f"joint{j}"
            joint_torques[nm] = float(np.linalg.norm(qf[dofadr:dofadr + 3]))
        else:  # hinge/slide: 1 dof
            nm = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, j) or f"joint{j}"
            joint_torques[nm] = float(qf[dofadr])
    max_jt = max((abs(v) for v in joint_torques.values()), default=0.0)
    return MjPoseStatics(robot=robot, com_world=com, total_mass_kg=total_mass,
                         joint_torques=joint_torques, base_wrench=tuple(base_wrench),
                         max_joint_torque_nm=max_jt)


# ── drop / stability test (gravity, the model's own floor) ────────────────────────────────────────

@dataclass(frozen=True)
class MjDropResult:
    """A reproducible drop-under-gravity result: did it stay upright, and the recorded trajectory."""
    robot: str
    steps: int
    duration_s: float
    timestep_s: float
    has_floor: bool                       #: did the model define a ground-plane geom?
    has_free_base: bool                   #: did the model define a free joint at the root?
    base_z_start: float
    base_z_end: float
    base_z_min: float
    base_tilt_start_deg: float            #: 0 by construction (lean is measured relative to the start)
    base_tilt_end_deg: float              #: how far the base rotated from its standing start
    com_start: tuple[float, float, float]
    com_end: tuple[float, float, float]
    com_horizontal_drift_m: float
    upright_end: bool                     #: base still roughly upright (lean < 45°) at the end
    finite: bool                          #: no NaN/inf blow-up
    base_z_trace: tuple[float, ...] = ()  #: down-sampled base height over time
    com_z_trace: tuple[float, ...] = ()


def _quat_lean_deg(q, q_ref) -> float:
    """Angle [deg] the body has rotated AWAY from its reference (t=0 standing) orientation.

    Frame-independent uprightness metric (mirrors insim._relative_tilt_deg): the relative rotation
    angle between two unit quaternions (w,x,y,z) is 2·acos(|w_rel|). Measuring the *change* from the
    standing start avoids any dependence on how the model authored its base frame."""
    import numpy as np
    q = np.asarray(q, dtype=float)
    qr = np.asarray(q_ref, dtype=float)
    # MuJoCo quaternion order is (w, x, y, z). Relative rotation: q_rel = q * conj(q_ref).
    w0, x0, y0, z0 = q
    w1, x1, y1, z1 = qr[0], -qr[1], -qr[2], -qr[3]   # conjugate of q_ref
    w_rel = w0 * w1 - x0 * x1 - y0 * y1 - z0 * z1
    w_rel = max(-1.0, min(1.0, abs(float(w_rel))))
    return math.degrees(2.0 * math.acos(w_rel))


def drop_test(robot: str, mjcf_path: str, *, seconds: float = 1.5,
              joint_positions: dict[str, float] | None = None,
              drop_height: float = 0.02) -> MjDropResult:
    """Drop the robot onto the model's own ground plane in a held pose and simulate under gravity.

    A QUALITATIVE stability test mirroring :func:`insim.drop_test`: records the floating-base height,
    base lean (relative to the start) and whole-body CoM over a fixed number of steps, and reports
    whether the robot stayed upright and whether the motion stayed finite (no NaN explosion). Uses the
    model's own timestep + gravity (deterministic). If the model has NO ground-plane geom, the result's
    ``has_floor`` is False and the run is a free-fall finiteness/Newton-Euler sanity check instead (the
    base simply accelerates downward); this is labelled in the result, not hidden. If the model has no
    free base, the base cannot translate/rotate and the test degenerates to a held-pose finiteness check
    (``has_free_base`` False). Raises if MuJoCo is unavailable or the MJCF is missing."""
    import mujoco
    import numpy as np
    m = _load_model(mjcf_path)
    d = mujoco.MjData(m)
    has_floor = any(int(t) == 0 for t in m.geom_type)
    has_free = any(int(m.jnt_type[j]) == 0 for j in range(m.njnt))

    name_to_qadr: dict[str, int] = {}
    for j in range(m.njnt):
        if int(m.jnt_type[j]) in (1, 2, 3):
            nm = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, j) or f"joint{j}"
            name_to_qadr[nm] = int(m.jnt_qposadr[j])

    mujoco.mj_resetData(m, d)
    if joint_positions:
        for nm, val in joint_positions.items():
            if nm in name_to_qadr:
                d.qpos[name_to_qadr[nm]] = float(val)
    mujoco.mj_forward(m, d)

    # if there is a free base and a floor, lower the base so the lowest body sits just above the plane
    # (mirrors insim.drop_test, which lifts then drops a small height to avoid a first-step contact kick)
    if has_free and has_floor:
        # lowest world-z of any geom's AABB centre minus its size is approximated via body positions;
        # use the simplest robust lower bound: the minimum geom world z extent from mj_forward.
        geom_bottoms = []
        for g in range(m.ngeom):
            cz = float(d.geom_xpos[g][2])
            # conservative half-extent: max of the geom size components (capsule/box/sphere safe upper bound)
            half = float(np.max(m.geom_size[g])) if m.geom_size[g].size else 0.0
            geom_bottoms.append(cz - half)
        if geom_bottoms:
            lowest = min(geom_bottoms)
            d.qpos[2] += (drop_height - lowest)   # shift base up so lowest point ≈ drop_height above z=0
            mujoco.mj_forward(m, d)

    steps = max(1, int(round(seconds / m.opt.timestep)))
    q0 = np.array(d.qpos[3:7]) if has_free else np.array([1.0, 0.0, 0.0, 0.0])
    z0 = float(d.qpos[2]) if has_free else 0.0
    com0 = tuple(float(x) for x in d.subtree_com[0])
    z_min = z0
    finite = True
    z_trace: list[float] = []
    comz_trace: list[float] = []
    stride = max(1, steps // 40)
    for s in range(steps):
        mujoco.mj_step(m, d)
        z = float(d.qpos[2]) if has_free else 0.0
        if not (math.isfinite(z) and all(math.isfinite(float(v)) for v in d.qpos[:7])):
            finite = False
            break
        z_min = min(z_min, z)
        if s % stride == 0:
            z_trace.append(z)
            comz_trace.append(float(d.subtree_com[0][2]))
    z1 = float(d.qpos[2]) if has_free else 0.0
    q1 = np.array(d.qpos[3:7]) if has_free else q0
    com1 = tuple(float(x) for x in d.subtree_com[0])

    lean_end = _quat_lean_deg(q1, q0) if has_free else 0.0
    drift = math.hypot(com1[0] - com0[0], com1[1] - com0[1])
    return MjDropResult(
        robot=robot, steps=steps, duration_s=steps * float(m.opt.timestep),
        timestep_s=float(m.opt.timestep), has_floor=has_floor, has_free_base=has_free,
        base_z_start=z0, base_z_end=z1, base_z_min=z_min,
        base_tilt_start_deg=0.0, base_tilt_end_deg=lean_end,
        com_start=com0, com_end=com1, com_horizontal_drift_m=drift,
        upright_end=(lean_end < 45.0) and finite, finite=finite,
        base_z_trace=tuple(z_trace), com_z_trace=tuple(comz_trace))
