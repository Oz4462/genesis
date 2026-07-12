"""insim — load REAL open-source humanoid URDFs into a real physics engine (PyBullet, headless).

This is the in-engine counterpart to :mod:`gen.humanoids.model_parser` (which only reads the XML) and
to GENESIS's own closed-form physics axes (:mod:`gen.kinematics`). It does the three things a real
articulated-body engine can do that the closed-form screens and the structural parser cannot:

  1. LOAD + ARTICULATE a downloaded humanoid URDF *with its meshes* — proving the file is not just
     well-formed XML but a model a real engine accepts, with the DOF and total mass it actually
     instantiates (cross-checked, fixed-base vs floating-base, against the parser/catalog figures).
  2. MEASURE A POSE'S STATICS the engine's own way — PyBullet's recursive Newton-Euler inverse
     dynamics (``calculateInverseDynamics``) at zero velocity/acceleration gives the gravity-hold
     joint torques and, via the base reaction, the centre of mass. These are what GENESIS's
     ``static_joint_torques`` / ``zmp_balance_check`` predict in closed form — so they can be compared
     honestly, axis by axis (done in :mod:`gen.humanoids.validation_insim`).
  3. SIMULATE UNDER GRAVITY — a reproducible drop/stability test (set a pose, step the real dynamics
     on a ground plane, record the CoM + base trajectory: does it stay upright, how does it fall?) and
     a minimal closed-loop PD stand/balance controller (proves the harness is usable for control /
     training, and reports how long the robot stays up).

PyBullet is used **headless** (``p.DIRECT``: no GUI, no window, no network) with a fixed time step and
fixed solver iterations, so two runs are bit-identical (the tests pin this). It is an OPTIONAL
dependency: :func:`pybullet_available` lets callers/tests skip cleanly when it is absent, exactly like
the project's existing ``gen.simulation.pybullet_sim``. Each loader owns its physics client and
disconnects it on exit — no leaked clients.

Honesty boundaries (stated, not hidden):
  * Inverse dynamics at a held pose is the gravity term only (zero q̇, q̈) — the same regime as the
    closed form, so the comparison is fair. It is NOT a dynamic gait torque.
  * The drop test is a QUALITATIVE stability check (finite, no NaN explosion, no gross floor
    tunnelling, falls/stands under gravity) — not a quantitative contact/energy validation.
  * Real humanoid URDFs branch and (in free fall) ride a 6-DOF floating base; a clean *serial-chain*
    torque comparison is only made on an isolated open sub-chain (e.g. one arm held horizontal), and
    that scope is reported. Whole-body multibody coupling is exercised by the sim, not closed-form-proven.

Source: PyBullet (Bullet 3) articulated-body dynamics; ``calculateInverseDynamics`` is the recursive
Newton-Euler inverse dynamics; ``getDynamicsInfo`` / ``getLinkStates`` give per-link mass + COM.
"""

from __future__ import annotations

import contextlib
import math
from dataclasses import dataclass, field
from pathlib import Path

#: Standard gravity [m/s^2] (CGPM convention) — matches GENESIS's other axes (kinematics, actuation).
STANDARD_GRAVITY = 9.80665

#: Fixed integration step [s] and solver iteration count — pinned so a run is reproducible.
_FIXED_TIMESTEP = 1.0 / 240.0
_SOLVER_ITERS = 80


def pybullet_available() -> bool:
    """True if PyBullet can be imported in this environment (callers/tests skip cleanly otherwise)."""
    try:
        import pybullet  # noqa: F401
        return True
    except Exception:
        return False


# ── load + structure (in-engine ground truth) ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class JointInfo:
    """One movable joint as the engine instantiated it (index, name, type, limits)."""
    index: int
    name: str
    type_name: str          #: "revolute" | "prismatic" | "fixed" | ...
    lower: float
    upper: float
    child_link: str


@dataclass(frozen=True)
class LoadResult:
    """What a real engine instantiated from the URDF — the in-engine corroboration of the structure."""
    robot: str
    urdf_path: str
    num_joints: int                       #: all joints incl. fixed welds (PyBullet's getNumJoints)
    revolute_dof: int                     #: movable revolute joints = the actuated DOF
    prismatic_dof: int
    fixed_joints: int
    total_mass_fixed_base_kg: float       #: Σ link mass with the base welded (base inertial excluded)
    total_mass_floating_base_kg: float    #: Σ link mass incl. the floating base link — the true mass
    base_link_name: str
    base_mass_kg: float
    joints: tuple[JointInfo, ...] = field(default_factory=tuple)

    @property
    def actuated_dof(self) -> int:
        return self.revolute_dof + self.prismatic_dof

    def summary(self) -> dict:
        return {
            "robot": self.robot, "num_joints": self.num_joints,
            "actuated_dof": self.actuated_dof, "revolute": self.revolute_dof,
            "prismatic": self.prismatic_dof, "fixed": self.fixed_joints,
            "mass_floating_kg": round(self.total_mass_floating_base_kg, 4),
            "mass_fixed_kg": round(self.total_mass_fixed_base_kg, 4),
            "base_link": self.base_link_name, "base_mass_kg": round(self.base_mass_kg, 4),
        }


@contextlib.contextmanager
def _engine():
    """A headless PyBullet client with deterministic stepping params. Disconnects on exit, always."""
    import pybullet as p
    client = p.connect(p.DIRECT)
    try:
        p.setGravity(0.0, 0.0, -STANDARD_GRAVITY, physicsClientId=client)
        p.setPhysicsEngineParameter(fixedTimeStep=_FIXED_TIMESTEP,
                                    numSolverIterations=_SOLVER_ITERS, physicsClientId=client)
        yield p, client
    finally:
        with contextlib.suppress(Exception):
            p.disconnect(client)


_JTYPE = {0: "revolute", 1: "prismatic", 2: "spherical", 3: "planar", 4: "fixed"}


def _load_urdf(p, client, urdf_path: str, *, fixed_base: bool,
               base_position=(0.0, 0.0, 0.0), base_orientation=(0.0, 0.0, 0.0, 1.0)) -> int:
    """Load a URDF *file* into the given client, resolving its meshes from the URDF's own directory.

    PyBullet resolves relative mesh paths against the URDF file's directory when given an absolute
    URDF path, so no chdir is needed; we pass the absolute path verbatim. Raises FileNotFoundError if
    the path is missing (no silent empty body)."""
    pth = Path(urdf_path)
    if not pth.is_file():
        raise FileNotFoundError(f"URDF not found: {pth}")
    flags = p.URDF_USE_INERTIA_FROM_FILE  # trust the model's authored inertials (the truth under test)
    return p.loadURDF(str(pth), basePosition=list(base_position),
                      baseOrientation=list(base_orientation), useFixedBase=fixed_base,
                      flags=flags, physicsClientId=client)


def load_structure(robot: str, urdf_path: str) -> LoadResult:
    """Load the URDF in a real engine and read off the structure it instantiates.

    Loads twice (fixed base, then floating base) so the true total mass — which a fixed-base load
    *excludes* for the welded base link — is reported alongside, exactly the subtlety that made a
    naive fixed-base mass read look ~5 kg light. This is the in-engine cross-check of the parser's
    DOF + mass. Raises if PyBullet is unavailable (call :func:`pybullet_available` first) or the URDF
    is missing."""
    import pybullet  # noqa: F401 — engine binds client as p
    with _engine() as (p, c):
        # fixed base: enumerate joints + fixed-base mass (base inertial welded out of the dynamics)
        bid = _load_urdf(p, c, urdf_path, fixed_base=True)
        nj = p.getNumJoints(bid, physicsClientId=c)
        joints: list[JointInfo] = []
        rev = pris = fixed = 0
        link_mass_fixed = 0.0
        for j in range(nj):
            ji = p.getJointInfo(bid, j, physicsClientId=c)
            tname = _JTYPE.get(ji[2], str(ji[2]))
            if tname == "revolute":
                rev += 1
            elif tname == "prismatic":
                pris += 1
            elif tname == "fixed":
                fixed += 1
            joints.append(JointInfo(index=j, name=ji[1].decode(), type_name=tname,
                                    lower=float(ji[8]), upper=float(ji[9]),
                                    child_link=ji[12].decode()))
            link_mass_fixed += p.getDynamicsInfo(bid, j, physicsClientId=c)[0]
        base_name = p.getBodyInfo(bid, physicsClientId=c)[0].decode()

        # floating base: the base link's inertial mass now participates → true total mass
        bid2 = _load_urdf(p, c, urdf_path, fixed_base=False)
        base_mass = p.getDynamicsInfo(bid2, -1, physicsClientId=c)[0]
        link_mass_float = sum(p.getDynamicsInfo(bid2, j, physicsClientId=c)[0] for j in range(nj))

    return LoadResult(
        robot=robot, urdf_path=urdf_path, num_joints=nj, revolute_dof=rev, prismatic_dof=pris,
        fixed_joints=fixed, total_mass_fixed_base_kg=link_mass_fixed,
        total_mass_floating_base_kg=base_mass + link_mass_float,
        base_link_name=base_name, base_mass_kg=base_mass, joints=tuple(joints))


# ── in-engine CoM (for the ZMP/balance comparison) ────────────────────────────────────────────────

def _world_com(p, client, body_id, num_joints: int,
               base_mass_override: float | None = None) -> tuple[tuple[float, float, float], float]:
    """Mass-weighted whole-body centre of mass in world coordinates, and the total mass, read from the
    engine's per-link states (base + every child link). The honest 'where the engine thinks the mass
    is' that the ZMP screen's CoM assumption is checked against.

    ``base_mass_override`` supplies the base link's true mass when the body is loaded FIXED-base (then
    PyBullet reports ``getDynamicsInfo(-1)`` mass as 0, which would otherwise drop the often-heavy
    pelvis/torso from the CoM — exactly the subtlety that made a naive fixed-base CoM read wrong)."""
    total = 0.0
    acc = [0.0, 0.0, 0.0]
    # base link: its world CoM = base frame origin + (base rotation · local inertial offset)
    base_mass = p.getDynamicsInfo(body_id, -1, physicsClientId=client)[0]
    if base_mass_override is not None:
        base_mass = base_mass_override
    local_inertial_pos = p.getDynamicsInfo(body_id, -1, physicsClientId=client)[3]
    base_pos, base_orn = p.getBasePositionAndOrientation(body_id, physicsClientId=client)
    rot = p.getMatrixFromQuaternion(base_orn)
    off = (
        rot[0] * local_inertial_pos[0] + rot[1] * local_inertial_pos[1] + rot[2] * local_inertial_pos[2],
        rot[3] * local_inertial_pos[0] + rot[4] * local_inertial_pos[1] + rot[5] * local_inertial_pos[2],
        rot[6] * local_inertial_pos[0] + rot[7] * local_inertial_pos[1] + rot[8] * local_inertial_pos[2],
    )
    base_world_com = (base_pos[0] + off[0], base_pos[1] + off[1], base_pos[2] + off[2])
    for k in range(3):
        acc[k] += base_mass * base_world_com[k]
    total += base_mass
    # child links: getLinkState()[0] is the link's centre-of-mass position in world coordinates
    for j in range(num_joints):
        m = p.getDynamicsInfo(body_id, j, physicsClientId=client)[0]
        if m <= 0.0:
            continue
        ls = p.getLinkState(body_id, j, computeForwardKinematics=True, physicsClientId=client)
        com_world = ls[0]
        for k in range(3):
            acc[k] += m * com_world[k]
        total += m
    if total <= 0.0:
        raise ValueError("total mass is zero — cannot compute CoM")
    return (acc[0] / total, acc[1] / total, acc[2] / total), total


@dataclass(frozen=True)
class PoseStatics:
    """The engine's statics at one held pose (fixed base): CoM + gravity-hold joint torques."""
    robot: str
    com_world: tuple[float, float, float]
    total_mass_kg: float
    joint_torques: dict[str, float]       #: name -> gravity-hold torque [N·m] from inverse dynamics


def pose_statics(robot: str, urdf_path: str,
                 joint_positions: dict[str, float] | None = None) -> PoseStatics:
    """Hold the (fixed-base) robot at ``joint_positions`` and read the engine's gravity statics.

    PyBullet ``calculateInverseDynamics`` with zero velocity and zero acceleration returns the joint
    torques that hold the pose against gravity — the engine's own answer to what GENESIS's
    ``static_joint_torques`` predicts. The whole-body CoM is read from per-link states. Joints not in
    ``joint_positions`` are held at 0. Raises if PyBullet is unavailable or a named joint is unknown."""
    with _engine() as (p, c):
        # one floating-base load to capture the base link's true mass (a fixed-base load reports it 0)
        bidf = _load_urdf(p, c, urdf_path, fixed_base=False)
        base_mass = p.getDynamicsInfo(bidf, -1, physicsClientId=c)[0]
        p.removeBody(bidf, physicsClientId=c)

        bid = _load_urdf(p, c, urdf_path, fixed_base=True)
        nj = p.getNumJoints(bid, physicsClientId=c)
        name_to_idx = {p.getJointInfo(bid, j, physicsClientId=c)[1].decode(): j for j in range(nj)}
        # the movable (non-fixed) joints, in index order — inverse dynamics expects exactly these
        movable = [j for j in range(nj)
                   if _JTYPE.get(p.getJointInfo(bid, j, physicsClientId=c)[2]) != "fixed"]
        positions = [0.0] * len(movable)
        if joint_positions:
            for nm, val in joint_positions.items():
                if nm not in name_to_idx:
                    raise ValueError(f"unknown joint {nm!r}; have {sorted(name_to_idx)[:6]}…")
                if name_to_idx[nm] in movable:
                    positions[movable.index(name_to_idx[nm])] = float(val)
        # set the kinematic state so getLinkState/CoM reflect the held pose
        for slot, j in enumerate(movable):
            p.resetJointState(bid, j, positions[slot], physicsClientId=c)
        zeros = [0.0] * len(movable)
        tau = p.calculateInverseDynamics(bid, positions, zeros, zeros, physicsClientId=c)
        torques = {p.getJointInfo(bid, movable[i], physicsClientId=c)[1].decode(): float(tau[i])
                   for i in range(len(movable))}
        com, mass = _world_com(p, c, bid, nj, base_mass_override=base_mass)
    return PoseStatics(robot=robot, com_world=com, total_mass_kg=mass, joint_torques=torques)


# ── drop / stability test (gravity, ground plane) ─────────────────────────────────────────────────

@dataclass(frozen=True)
class DropResult:
    """A reproducible drop-under-gravity result: did it stay upright, and the recorded trajectory."""
    robot: str
    steps: int
    duration_s: float
    base_z_start: float
    base_z_end: float
    base_z_min: float
    base_tilt_start_deg: float            #: angle of the base +z axis from world +z at start
    base_tilt_end_deg: float
    com_start: tuple[float, float, float]
    com_end: tuple[float, float, float]
    com_horizontal_drift_m: float         #: how far the CoM moved in the ground plane
    upright_end: bool                     #: base still roughly upright (tilt < 45°) at the end
    finite: bool                          #: no NaN/inf blow-up
    floor_penetration: bool               #: base sank well below its start (gross tunnelling)
    base_z_trace: tuple[float, ...] = ()  #: down-sampled base height over time
    com_z_trace: tuple[float, ...] = ()


def _tilt_deg(orn) -> float:
    """Angle [deg] between the body's local +z axis and world +z (0 = body z aligned with up)."""
    import pybullet as p
    rot = p.getMatrixFromQuaternion(orn)
    body_z_world = (rot[2], rot[5], rot[8])  # third column = body z in world
    cos = max(-1.0, min(1.0, body_z_world[2]))
    return math.degrees(math.acos(cos))


def _relative_tilt_deg(p, orn, orn_ref) -> float:
    """Angle [deg] the base has rotated AWAY from its reference (t=0 standing) orientation.

    This is the convention-robust uprightness metric: some URDF base links are reported by PyBullet in
    a rotated inertial/principal frame (e.g. TienKung's pelvis reads a ~25° pitch even when the robot
    stands perfectly upright in world space), so an absolute base-z-vs-world-z tilt is misleading. The
    *change* from the standing start orientation is frame-independent — it measures real lean/fall."""
    inv = p.invertTransform([0.0, 0.0, 0.0], orn_ref)[1]
    _, rel = p.multiplyTransforms([0.0, 0.0, 0.0], orn, [0.0, 0.0, 0.0], inv)
    # the relative rotation's angle: 2·acos(|w|)
    w = max(-1.0, min(1.0, abs(rel[3])))
    return math.degrees(2.0 * math.acos(w))


def drop_test(robot: str, urdf_path: str, *, drop_height: float = 0.02, seconds: float = 1.5,
              joint_positions: dict[str, float] | None = None,
              base_orientation=(0.0, 0.0, 0.0, 1.0)) -> DropResult:
    """Place the robot just above a ground plane in a held pose and simulate under gravity.

    A QUALITATIVE stability test: records the base height, base tilt and whole-body CoM over a fixed
    number of steps, and reports whether the robot stayed upright, the motion stayed finite (no NaN
    explosion) and the base did not tunnel through the floor. The standing pose can be set via
    ``joint_positions`` (defaults to the model's zero pose). Deterministic (fixed step + solver iters).
    Raises if PyBullet is unavailable."""
    import pybullet  # noqa: F401
    import pybullet_data
    with _engine() as (p, c):
        p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=c)
        p.loadURDF("plane.urdf", physicsClientId=c)
        # spawn HIGH (clear of the plane) so the AABB is collision-free, set the pose, then lower the
        # base so the lowest posed point sits just above z=0. Spawning low (interpenetrating the plane)
        # produced a violent first-step push that spuriously tilted the base — fixed by lifting first.
        spawn_z = 1.5
        bid = _load_urdf(p, c, urdf_path, fixed_base=False,
                         base_position=(0.0, 0.0, spawn_z), base_orientation=base_orientation)
        nj = p.getNumJoints(bid, physicsClientId=c)
        name_to_idx = {p.getJointInfo(bid, j, physicsClientId=c)[1].decode(): j for j in range(nj)}
        if joint_positions:
            for nm, val in joint_positions.items():
                if nm in name_to_idx:
                    p.resetJointState(bid, name_to_idx[nm], float(val), physicsClientId=c)
        # lower the base so the lowest point of the (posed) body sits ``drop_height`` above z=0
        aabb_min = min((p.getAABB(bid, j, physicsClientId=c)[0][2] for j in range(-1, nj)),
                       default=spawn_z)
        bp, bo = p.getBasePositionAndOrientation(bid, physicsClientId=c)
        target_base_z = bp[2] - aabb_min + drop_height
        p.resetBasePositionAndOrientation(bid, (bp[0], bp[1], target_base_z), bo, physicsClientId=c)

        steps = max(1, int(seconds / _FIXED_TIMESTEP))
        bp0, bo0 = p.getBasePositionAndOrientation(bid, physicsClientId=c)
        com0, _ = _world_com(p, c, bid, nj)
        z_min = bp0[2]
        finite = True
        z_trace: list[float] = []
        comz_trace: list[float] = []
        stride = max(1, steps // 40)
        for s in range(steps):
            p.stepSimulation(physicsClientId=c)
            bp, bo = p.getBasePositionAndOrientation(bid, physicsClientId=c)
            if not all(math.isfinite(v) for v in (*bp, *bo)):
                finite = False
                break
            z_min = min(z_min, bp[2])
            if s % stride == 0:
                z_trace.append(bp[2])
                com_s, _ = _world_com(p, c, bid, nj)
                comz_trace.append(com_s[2])
        bp1, bo1 = p.getBasePositionAndOrientation(bid, physicsClientId=c)
        com1, _ = _world_com(p, c, bid, nj)

    import pybullet as p  # for the relative-tilt transform helpers
    lean_end = _relative_tilt_deg(p, bo1, bo0)   # how far the base rotated from its standing start
    drift = math.hypot(com1[0] - com0[0], com1[1] - com0[1])
    return DropResult(
        robot=robot, steps=steps, duration_s=steps * _FIXED_TIMESTEP,
        base_z_start=bp0[2], base_z_end=bp1[2], base_z_min=z_min,
        base_tilt_start_deg=0.0, base_tilt_end_deg=lean_end,  # relative lean from the standing start
        com_start=com0, com_end=com1, com_horizontal_drift_m=drift,
        upright_end=(lean_end < 45.0) and finite, finite=finite,
        floor_penetration=(bp1[2] < bp0[2] - 0.30),
        base_z_trace=tuple(z_trace), com_z_trace=tuple(comz_trace))


# ── minimal closed-loop PD stand/balance controller ───────────────────────────────────────────────

@dataclass(frozen=True)
class BalanceResult:
    """How long a PD joint controller kept the robot upright, and the trajectory while it did."""
    robot: str
    requested_seconds: float
    upright_seconds: float                #: time before the base tilt first exceeded the fall threshold
    fell: bool
    steps_survived: int
    base_tilt_max_deg: float
    base_z_start: float
    base_z_end: float
    com_horizontal_drift_m: float
    kp: float
    kd: float


def pd_balance(robot: str, urdf_path: str, *, seconds: float = 3.0, kp: float = 80.0, kd: float = 4.0,
               fall_tilt_deg: float = 50.0, target_pose: dict[str, float] | None = None,
               max_force: float = 200.0) -> BalanceResult:
    """Hold a standing pose with a joint-space PD controller and report how long the base stays upright.

    A minimal, deterministic closed-loop demo proving the harness is usable for control / RL: every
    movable joint is driven by PyBullet ``POSITION_CONTROL`` (an internal PD with gains ``kp``/``kd``)
    toward ``target_pose`` (default: the model's zero/neutral pose); the robot stands on a ground
    plane under gravity. We step the real dynamics and stop counting "upright" time the moment the base
    tilt exceeds ``fall_tilt_deg``. Reports ``upright_seconds`` (how long it stayed up) and whether it
    ultimately fell within the window. Not a tuned controller — a usability proof. Raises if PyBullet
    is unavailable."""
    import pybullet  # noqa: F401
    import pybullet_data
    with _engine() as (p, c):
        p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=c)
        p.loadURDF("plane.urdf", physicsClientId=c)
        # spawn HIGH (clear of the plane) so the AABB read is collision-free, then lower the posed feet
        # to just above z=0 (spawning interpenetrating the plane causes a spurious first-step kick).
        bid = _load_urdf(p, c, urdf_path, fixed_base=False, base_position=(0.0, 0.0, 1.5))
        nj = p.getNumJoints(bid, physicsClientId=c)
        name_to_idx = {p.getJointInfo(bid, j, physicsClientId=c)[1].decode(): j for j in range(nj)}
        movable = [j for j in range(nj)
                   if _JTYPE.get(p.getJointInfo(bid, j, physicsClientId=c)[2]) != "fixed"]
        targets = {j: 0.0 for j in movable}
        if target_pose:
            for nm, val in target_pose.items():
                if nm in name_to_idx and name_to_idx[nm] in targets:
                    targets[name_to_idx[nm]] = float(val)
        for j, q in targets.items():
            p.resetJointState(bid, j, q, physicsClientId=c)
        # lower the base so the feet rest just above the plane before control starts
        aabb_min = min((p.getAABB(bid, j, physicsClientId=c)[0][2] for j in range(-1, nj)), default=1.5)
        bp, bo = p.getBasePositionAndOrientation(bid, physicsClientId=c)
        p.resetBasePositionAndOrientation(bid, (bp[0], bp[1], bp[2] - aabb_min + 0.002), bo,
                                          physicsClientId=c)
        # engage PD position control on every movable joint
        for j, q in targets.items():
            p.setJointMotorControl2(bid, j, p.POSITION_CONTROL, targetPosition=q,
                                    positionGain=kp / 1000.0, velocityGain=kd / 1000.0,
                                    force=max_force, physicsClientId=c)

        steps = max(1, int(seconds / _FIXED_TIMESTEP))
        bp0, bo0 = p.getBasePositionAndOrientation(bid, physicsClientId=c)
        com0, _ = _world_com(p, c, bid, nj)
        tilt_max = 0.0
        upright_steps = 0
        fell = False
        still_up = True
        for s in range(steps):
            p.stepSimulation(physicsClientId=c)
            bp, bo = p.getBasePositionAndOrientation(bid, physicsClientId=c)
            if not all(math.isfinite(v) for v in (*bp, *bo)):
                fell = True
                break
            lean = _relative_tilt_deg(p, bo, bo0)  # lean from the standing start (frame-robust)
            tilt_max = max(tilt_max, lean)
            if still_up and lean <= fall_tilt_deg:
                upright_steps = s + 1
            elif still_up:
                still_up = False
                fell = True
        bp1, bo1 = p.getBasePositionAndOrientation(bid, physicsClientId=c)
        com1, _ = _world_com(p, c, bid, nj)

    drift = math.hypot(com1[0] - com0[0], com1[1] - com0[1])
    return BalanceResult(
        robot=robot, requested_seconds=seconds,
        upright_seconds=upright_steps * _FIXED_TIMESTEP, fell=fell,
        steps_survived=upright_steps, base_tilt_max_deg=tilt_max,
        base_z_start=bp0[2], base_z_end=bp1[2], com_horizontal_drift_m=drift, kp=kp, kd=kd)
