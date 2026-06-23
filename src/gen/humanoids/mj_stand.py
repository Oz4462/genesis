"""mj_stand — actuated stand / balance test for the torque-motor MuJoCo humanoids (K-Bot, Fourier N1).

Why this exists separately from :mod:`gen.humanoids.insim_mujoco`:
  * ``insim_mujoco`` validates *structure + held statics + a PASSIVE drop* (no actuator commands). That is
    enough for Asimov (whose MJCF defines ``nu == 0`` — no actuators) but a no-op for K-Bot and Fourier N1,
    which ship **fully actuated** MJCFs with ``<motor>`` (raw-torque) actuators. A passive drop of an
    actuated robot just lets it collapse; to make it STAND we must close a control loop on the motors.
  * K-Bot and N1 both use TORQUE actuators (``<motor>``), so the stand controller here is a joint-space
    PD law computed in Python — ``τ_i = clamp( kp_i·(q*_i − q_i) − kd_i·q̇_i , ±τ_limit_i )`` — written into
    ``data.ctrl`` each step. This mirrors how these robots are actually driven on hardware (K-Bot publishes
    per-joint kp/kd/torque-limit in ``metadata.json``; we reuse them).

What it does, honestly:
  1. Builds a SELF-CONTAINED scene: the bare ``robot.mjcf`` + a plain ``type="plane"`` floor with
     ``contype=1 conaffinity=1`` (so it collides with the robots' ``class="collision"`` geoms, which are
     ``conaffinity=1``) — sidestepping each repo's idiosyncratic floor (K-Bot ships an ``hfield`` with
     ``conaffinity=0`` offset to ``z=-0.1``; we want a clean, reproducible ground).
  2. Drops the robot from a held standing/crouch pose onto that floor and runs the PD hold for a fixed
     horizon at the model's own timestep (deterministic).
  3. Reports the HONEST measured outcome: upright-seconds (lean relative to the settled start stays < a
     threshold), whether it held the full horizon, base height drift, foot-contact count, max lean.

Boundaries (stated, not hidden):
  * This is a STAND/HOLD test, not a gait or a push-recovery policy. Per the project's established law,
    a stiff PD hold of a sensible pose is the strongest STATIC strategy for a tall mesh-foot humanoid.
  * "upright" is measured as the base's rotation away from its t=settle orientation (frame-independent),
    not absolute world-up, because some authored base frames are not identity-upright.
  * No claim that the published kp/kd are optimal — they are the vendor's hardware gains, used as a
    grounded, non-arbitrary starting point; a gain scan is provided to find what actually holds.

Source: MuJoCo 3.x rigid-body dynamics; ``mj_step`` integrates the real contact dynamics. Joint-space PD
on torque motors is the standard low-level humanoid stand controller.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

STANDARD_GRAVITY = 9.80665

#: Minimal MuJoCo scene wrapper: include a robot mjcf + a clean colliding ground plane.
#: contype=1 conaffinity=1 floor collides with the robots' collision geoms (conaffinity=1, contype=0).
_SCENE_TEMPLATE = """<mujoco model="{name}_stand_scene">
  <include file="{robot_mjcf}"/>
  <!-- implicitfast integrator: MuJoCo's recommended integrator for STIFF actuators (high-kp position
       servos). The robots ship with Euler (integrator=0) + zero joint damping, which injects energy
       under a stiff PD hold and makes a held stand slowly diverge (a numerical artifact, not physics).
       implicitfast integrates the actuator/damping terms implicitly so a stiff hold stays put. -->
  <option integrator="implicitfast"/>
  <statistic center="0 0 0.6" extent="1.4"/>
  <visual>
    <headlight diffuse="0.6 0.6 0.6" ambient="0.35 0.35 0.35" specular="0 0 0"/>
    <global azimuth="150" elevation="-20"/>
  </visual>
  <asset>
    <texture type="2d" name="groundplane" builtin="checker" mark="edge"
             rgb1="0.2 0.3 0.4" rgb2="0.1 0.2 0.3" markrgb="0.8 0.8 0.8" width="300" height="300"/>
    <material name="groundplane" texture="groundplane" texuniform="true" texrepeat="5 5" reflectance="0.2"/>
  </asset>
  <worldbody>
    <light pos="0 0 3.5" dir="0 0 -1" directional="true"/>
    <geom name="stand_floor" type="plane" size="0 0 0.05" material="groundplane"
          contype="1" conaffinity="1" condim="6" friction="1.0 0.02 0.01"/>
  </worldbody>
</mujoco>
"""


def mujoco_available() -> bool:
    """True if MuJoCo can be imported (callers/tests skip cleanly otherwise)."""
    try:
        import mujoco  # noqa: F401
        return True
    except Exception:
        return False


def _lowest_collision_z(m, d, floor_gid: int) -> float | None:
    """World-z of the lowest point of any COLLIDING geom (conaffinity≠0), honouring its orientation.

    Why only colliding geoms: visual meshes (group 0) carry huge bounding sizes at odd offsets and using
    ``max(geom_size)`` over them picks a bogus "lowest" point far below the real contact surface (the
    bug that put the base meters too low). Why orientation-aware: a foot BOX laid flat has a small z
    half-extent (its thickness) even though its longest size is the foot length — projecting the box
    half-sizes through the geom's world rotation gives the true downward reach. Returns None if no
    colliding geom exists."""
    import numpy as np
    lows: list[float] = []
    for g in range(m.ngeom):
        if g == floor_gid:
            continue
        if int(m.geom_conaffinity[g]) == 0 and int(m.geom_contype[g]) == 0:
            continue  # non-colliding (pure visual) geom — ignore for ground placement
        cz = float(d.geom_xpos[g][2])
        sz = m.geom_size[g]
        R = np.asarray(d.geom_xmat[g], dtype=float).reshape(3, 3)
        gtype = int(m.geom_type[g])
        # half-extent along world-z = |R[2,:] · half_sizes| with the right half-size per geom type
        if gtype == 6:  # box: half sizes are sz[0:3]
            half_z = float(abs(R[2, 0]) * sz[0] + abs(R[2, 1]) * sz[1] + abs(R[2, 2]) * sz[2])
        elif gtype in (2, 3, 4, 5):  # sphere/capsule/ellipsoid/cylinder — use bounding radius (safe)
            half_z = float(np.max(sz))
        else:  # mesh/plane/hfield collision: fall back to rbound (bounding sphere) — conservative
            half_z = float(m.geom_rbound[g]) if m.geom_rbound[g] > 0 else float(np.max(sz))
        lows.append(cz - half_z)
    return min(lows) if lows else None


def build_stand_scene(robot: str, robot_mjcf: str, out_path: str) -> str:
    """Write a self-contained stand scene (robot + clean colliding floor) next to the robot mjcf.

    The scene ``<include>``s the robot file by RELATIVE path so MuJoCo resolves the robot's own meshdir.
    Returns the written scene path. Raises if the robot mjcf is missing."""
    rp = Path(robot_mjcf)
    if not rp.is_file():
        raise FileNotFoundError(f"robot mjcf not found: {rp}")
    op = Path(out_path)
    # include path relative to the scene file's directory
    rel = Path(robot_mjcf).resolve()
    try:
        rel_inc = rel.relative_to(op.resolve().parent)
        inc = rel_inc.as_posix()
    except ValueError:
        inc = rel.as_posix()
    op.write_text(_SCENE_TEMPLATE.format(name=robot, robot_mjcf=inc))
    return str(op)


# ── PD-hold stand ─────────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StandResult:
    """Honest measured outcome of an actuated PD stand on the real contact dynamics."""
    robot: str
    held_full_horizon: bool
    upright_seconds: float
    horizon_seconds: float
    timestep_s: float
    steps: int
    base_z_start: float
    base_z_end: float
    base_z_min: float
    max_lean_deg: float
    final_lean_deg: float
    mean_foot_contacts: float
    min_foot_contacts: int
    com_horizontal_drift_m: float
    finite: bool
    note: str = ""
    lean_trace: tuple[float, ...] = field(default_factory=tuple)


def _quat_lean_deg(q, q_ref) -> float:
    """Angle [deg] the body rotated away from a reference orientation (frame-independent uprightness)."""
    import numpy as np
    q = np.asarray(q, dtype=float); qr = np.asarray(q_ref, dtype=float)
    w0, x0, y0, z0 = q
    w1, x1, y1, z1 = qr[0], -qr[1], -qr[2], -qr[3]
    w_rel = w0 * w1 - x0 * x1 - y0 * y1 - z0 * z1
    w_rel = max(-1.0, min(1.0, abs(float(w_rel))))
    return math.degrees(2.0 * math.acos(w_rel))


def _make_position_servos(m, act_for_joint: dict[str, int],
                          joint_gains: dict[str, tuple[float, float]],
                          default_kp: float, default_kd: float) -> None:
    """Convert the compiled model's torque ``<motor>`` actuators into implicit position-velocity servos.

    Mutates ``m`` in place: for each actuated joint, set ``gaintype=FIXED, gainprm=[kp,0,0]`` and
    ``biastype=AFFINE, biasprm=[0,-kp,-kd]`` so the generated force is ``kp·(ctrl − q) − kd·q̇``. MuJoCo
    integrates these actuators IMPLICITLY, which is stable at the high kp a stand needs — the MuJoCo
    analogue of PyBullet's POSITION_CONTROL that beat explicit torque-PD on every prior robot (the
    established stiffness-wins law). The control input then becomes a target ANGLE per joint, not a torque.

    ``actuatorfrcrange`` (the model's per-joint force clamp) still bounds the servo force, so this respects
    the real actuator torque limits."""
    import mujoco
    GAIN_FIXED = int(mujoco.mjtGain.mjGAIN_FIXED)
    BIAS_AFFINE = int(mujoco.mjtBias.mjBIAS_AFFINE)
    for nm, aid in act_for_joint.items():
        kp, kd = joint_gains.get(nm, (default_kp, default_kd))
        m.actuator_gaintype[aid] = GAIN_FIXED
        m.actuator_gainprm[aid][:3] = [kp, 0.0, 0.0]
        m.actuator_biastype[aid] = BIAS_AFFINE
        m.actuator_biasprm[aid][:3] = [0.0, -kp, -kd]
        # widen ctrlrange to allow any target angle (the force clamp still limits torque)
        m.actuator_ctrllimited[aid] = 0


def pd_stand(robot: str, scene_mjcf: str,
             standing_pose: dict[str, float] | None = None,
             joint_gains: dict[str, tuple[float, float]] | None = None,
             *, default_kp: float = 80.0, default_kd: float = 4.0,
             torque_limit: dict[str, float] | None = None, default_torque: float = 60.0,
             seconds: float = 5.0, settle_drop: float = 0.03,
             upright_threshold_deg: float = 30.0,
             position_servo: bool = False,
             base_xy_shift: tuple[float, float] = (0.0, 0.0),
             perturb_xy: tuple[float, float] | None = None,
             perturb_at_s: float = 0.5) -> StandResult:
    """Drop the actuated robot from a held pose onto the scene floor and PD-hold it; measure the stand.

    The controller writes ``data.ctrl`` (torque) every step from a joint-space PD law on the named
    standing pose (joints absent from ``standing_pose`` target 0). ``joint_gains[name] = (kp, kd)`` per
    joint (defaults to ``default_kp/kd``); torques are clamped to ``torque_limit[name]`` (else
    ``default_torque``). The base is lowered so the lowest geom sits ``settle_drop`` above z=0 at t=0.

    ``perturb_xy`` optionally adds an instantaneous base linear-velocity kick [m/s] at ``perturb_at_s``
    (a reproducible shove) to probe the stand's basin.

    Returns an honest :class:`StandResult` (upright-seconds, held-full, contacts, lean) — never asserts
    success. Raises if MuJoCo is unavailable or the scene/joint is unknown."""
    import mujoco
    import numpy as np

    sp = Path(scene_mjcf)
    if not sp.is_file():
        raise FileNotFoundError(f"scene not found: {sp}")
    m = mujoco.MjModel.from_xml_path(str(sp))
    d = mujoco.MjData(m)

    # map joint name -> (qpos addr, qvel/dof addr, actuator id) for the actuated hinge joints
    name_to_qadr: dict[str, int] = {}
    name_to_vadr: dict[str, int] = {}
    for j in range(m.njnt):
        if int(m.jnt_type[j]) == 3:  # hinge
            nm = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, j) or f"joint{j}"
            name_to_qadr[nm] = int(m.jnt_qposadr[j])
            name_to_vadr[nm] = int(m.jnt_dofadr[j])
    # actuator -> the joint it drives (trnid[:,0] is the joint id for joint transmission)
    act_for_joint: dict[str, int] = {}
    for a in range(m.nu):
        jid = int(m.actuator_trnid[a, 0])
        jnm = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, jid)
        if jnm is not None:
            act_for_joint[jnm] = a

    standing_pose = standing_pose or {}
    joint_gains = joint_gains or {}
    torque_limit = torque_limit or {}
    for nm in list(standing_pose) + list(joint_gains):
        if nm not in name_to_qadr:
            raise ValueError(f"unknown joint {nm!r}; have e.g. {sorted(name_to_qadr)[:6]}…")

    if position_servo:
        _make_position_servos(m, act_for_joint, joint_gains, default_kp, default_kd)

    mujoco.mj_resetData(m, d)
    # set the held pose
    for nm, val in standing_pose.items():
        d.qpos[name_to_qadr[nm]] = float(val)
    mujoco.mj_forward(m, d)

    floor_gid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, "stand_floor")
    # lower the free base so the lowest COLLIDING geom (feet) sits settle_drop above the plane
    has_free = any(int(m.jnt_type[j]) == 0 for j in range(m.njnt))
    if has_free:
        low = _lowest_collision_z(m, d, floor_gid)
        if low is not None:
            d.qpos[2] += (settle_drop - low)
        # shift the base in x/y so the CoM starts over the support centre (cures a fore-aft/lateral
        # tip when the feet are mounted offset from the body CoM — e.g. K-Bot's feet sit ~4cm forward
        # of the torso CoM, so the bare stand tips backward; a small forward base shift centres it).
        d.qpos[0] += float(base_xy_shift[0])
        d.qpos[1] += float(base_xy_shift[1])
        mujoco.mj_forward(m, d)

    # PD targets are the held pose values (0 if unspecified)
    targets = {nm: float(standing_pose.get(nm, 0.0)) for nm in name_to_qadr}
    steps = max(1, int(round(seconds / m.opt.timestep)))
    perturb_step = int(round(perturb_at_s / m.opt.timestep)) if perturb_xy else -1

    # settle the orientation reference a few steps in (after first ground contact transient)
    q_ref = None
    z0 = float(d.qpos[2]) if has_free else 0.0
    com0 = np.array(d.subtree_com[0], dtype=float)
    z_min = z0
    max_lean = 0.0
    topple_step = -1            # step at which lean first crosses the upright threshold (-1 = never)
    contacts: list[int] = []
    finite = True
    lean_trace: list[float] = []
    stride = max(1, steps // 50)

    for s in range(steps):
        if position_servo:
            # implicit position-velocity servo: ctrl = target ANGLE (kp/kd live in the actuator now)
            for nm, aid in act_for_joint.items():
                d.ctrl[aid] = targets[nm]
        else:
            # explicit joint-space torque PD into data.ctrl
            for nm, aid in act_for_joint.items():
                q = float(d.qpos[name_to_qadr[nm]])
                qd = float(d.qvel[name_to_vadr[nm]])
                kp, kd = joint_gains.get(nm, (default_kp, default_kd))
                tau = kp * (targets[nm] - q) - kd * qd
                tlim = torque_limit.get(nm, default_torque)
                d.ctrl[aid] = max(-tlim, min(tlim, tau))

        if s == perturb_step and has_free and perturb_xy is not None:
            d.qvel[0] += float(perturb_xy[0])
            d.qvel[1] += float(perturb_xy[1])

        mujoco.mj_step(m, d)

        if not all(math.isfinite(float(v)) for v in d.qpos[:7]):
            finite = False
            break

        # establish the reference orientation a few steps after the initial settle
        if q_ref is None and s >= max(3, int(0.05 / m.opt.timestep)):
            q_ref = np.array(d.qpos[3:7]) if has_free else np.array([1.0, 0, 0, 0])

        z = float(d.qpos[2]) if has_free else 0.0
        z_min = min(z_min, z)
        if q_ref is not None:
            lean = _quat_lean_deg(d.qpos[3:7], q_ref) if has_free else 0.0
            max_lean = max(max_lean, lean)
            # record the time the base FIRST exceeds the upright threshold (the honest topple time)
            if topple_step < 0 and lean >= upright_threshold_deg:
                topple_step = s
        # count foot/ground contacts
        nc = 0
        for ci in range(d.ncon):
            c = d.contact[ci]
            if c.geom1 == floor_gid or c.geom2 == floor_gid:
                nc += 1
        contacts.append(nc)
        if s % stride == 0 and q_ref is not None:
            lean_trace.append(round(_quat_lean_deg(d.qpos[3:7], q_ref) if has_free else 0.0, 2))

    z1 = float(d.qpos[2]) if has_free else 0.0
    com1 = np.array(d.subtree_com[0], dtype=float)
    final_lean = _quat_lean_deg(d.qpos[3:7], q_ref) if (has_free and q_ref is not None) else 0.0
    # upright_seconds = first topple time (if it crossed) or full horizon; if it went non-finite, the
    # break step is when it blew up.
    if topple_step >= 0:
        upright_sec = topple_step * float(m.opt.timestep)
    elif not finite:
        upright_sec = s * float(m.opt.timestep)
    else:
        upright_sec = seconds

    held_full = finite and (max_lean < upright_threshold_deg)
    drift = float(math.hypot(com1[0] - com0[0], com1[1] - com0[1]))
    return StandResult(
        robot=robot, held_full_horizon=held_full,
        upright_seconds=round(min(upright_sec, seconds), 3), horizon_seconds=seconds,
        timestep_s=float(m.opt.timestep), steps=steps,
        base_z_start=round(z0, 4), base_z_end=round(z1, 4), base_z_min=round(z_min, 4),
        max_lean_deg=round(max_lean, 2), final_lean_deg=round(final_lean, 2),
        mean_foot_contacts=round(float(np.mean(contacts)) if contacts else 0.0, 2),
        min_foot_contacts=int(min(contacts)) if contacts else 0,
        com_horizontal_drift_m=round(drift, 4), finite=finite,
        note="", lean_trace=tuple(lean_trace))
