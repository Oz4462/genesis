"""simulation/pybullet_sim.py — the full-contact multibody simulation, in a real physics engine.

``multibody.py`` is GENESIS's own deterministic single-DOF integrator. This module is the second,
INDEPENDENT check: it loads the ``urdf_bridge`` URDF into PyBullet — a real articulated-body engine —
and does three things the closed-form screens cannot:

  1. PROVES THE URDF LOADS — a real engine parses and articulates the emitted robot (njoints, links).
     If the bridge emitted a malformed tree, PyBullet would reject it.
  2. CROSS-CHECKS ONE CLOSED FORM IN A SECOND ENGINE — PyBullet's own inverse dynamics
     (``calculateInverseDynamics``) at a fixed-base, zero-velocity/acceleration pose reduces to the
     SINGLE-LINK gravity-hold torque m·g·d·sin θ (com at d = length/2). A second, independent engine
     reproducing GENESIS's closed form to machine precision is strong evidence for THAT term — the
     elementary statics anchor, and a check that the URDF carries the com where the bridge intends.
     It does NOT by itself validate multibody joint coupling, base reactions or contact forces; those
     are only exercised qualitatively by the drop smoke-test, not proven here.
  3. RUNS A REPRODUCIBLE DROP SMOKE-TEST — drops the leg onto a ground plane and steps the real
     dynamics with a fixed time step and fixed solver iterations (so two runs are identical, which the
     test pins). This is a QUALITATIVE stability check — finite (no NaN explosion), falls under
     gravity, no gross floor tunneling — NOT a quantitative contact/energy validation.

PyBullet is an OPTIONAL dependency, used headless (``p.DIRECT``: no GUI, no window, no network) with a
fixed time step (deterministic). The tests skip when it is absent, exactly like the cadquery STL path.
Each call owns its physics client and temp file and cleans both up — no leaked clients, no leaked files.

Source: PyBullet (Bullet 3) articulated-body dynamics; ``calculateInverseDynamics`` is the recursive
Newton–Euler inverse dynamics. The single-link gravity torque m·g·d·sin θ is the elementary statics
anchor the cross-check is pinned to.
"""

from __future__ import annotations

import contextlib
import math
import os
import shutil
import tempfile

#: Standard gravity [m/s²] (CGPM convention) — matches GENESIS's other axes.
STANDARD_GRAVITY = 9.80665


@contextlib.contextmanager
def _world(urdf_str: str, *, fixed_base: bool, with_plane: bool = False,
           base_position: tuple[float, float, float] = (0.0, 0.0, 0.0)):
    """A headless PyBullet world with the URDF loaded (inertia taken from the file), gravity set, and
    an optional ground plane. Yields ``(p, client_id, body_id)``; disconnects the client and deletes
    the temp URDF on exit, always."""
    import pybullet as p
    import pybullet_data

    client = p.connect(p.DIRECT)
    tmpdir = tempfile.mkdtemp(prefix="genesis_urdf_")
    try:
        path = os.path.join(tmpdir, "robot.urdf")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(urdf_str)
        p.setGravity(0.0, 0.0, -STANDARD_GRAVITY, physicsClientId=client)
        if with_plane:
            p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=client)
            p.loadURDF("plane.urdf", physicsClientId=client)
        body = p.loadURDF(
            path, basePosition=list(base_position),
            useFixedBase=1 if fixed_base else 0,
            flags=p.URDF_USE_INERTIA_FROM_FILE, physicsClientId=client,
        )
        yield p, client, body
    finally:
        p.disconnect(client)
        shutil.rmtree(tmpdir, ignore_errors=True)


def urdf_joint_count(urdf_str: str) -> int:
    """The number of articulated joints a real engine finds in the emitted URDF (proves it loads)."""
    with _world(urdf_str, fixed_base=True) as (p, client, body):
        return int(p.getNumJoints(body, physicsClientId=client))


def gravity_hold_torques(urdf_str: str, joint_angles: list[float]) -> list[float]:
    """PyBullet's own inverse-dynamics joint torques to HOLD the fixed-base robot at ``joint_angles``
    (zero velocity and acceleration → pure gravity compensation). For a single link this is
    m·g·d·sin θ — the number GENESIS's closed form must also produce. Raises ValueError if the angle
    count does not match the joint count."""
    with _world(urdf_str, fixed_base=True) as (p, client, body):
        n = int(p.getNumJoints(body, physicsClientId=client))
        if len(joint_angles) != n:
            raise ValueError(f"expected {n} joint angles, got {len(joint_angles)}")
        zeros = [0.0] * n
        tau = p.calculateInverseDynamics(
            body, list(joint_angles), zeros, zeros, physicsClientId=client)
        return list(tau)


def track_joint_swing(urdf_str: str, joint_index: int, *, amplitude_rad: float,
                      frequency_hz: float, max_torque: float, duration: float,
                      dt: float = 1.0 / 240.0) -> dict:
    """Drive ``joint_index`` to FOLLOW θ(t)=amplitude·sin(2π·f·t) by position control (all other joints
    held at 0) on the fixed-base leg, step the real dynamics, and report whether the leg actually MOVES
    as commanded: does the joint track the swing, and does the end-effector (last link) trace an arc?

    Returns ``{"max_tracking_error", "ee_travel", "finite"}``: ``max_tracking_error`` is the worst
    |achieved−commanded| joint angle [rad] (small ⇒ it follows the motion), ``ee_travel`` the span the
    end-effector moved [m] (>0 ⇒ visible motion), ``finite`` that nothing went NaN. ``max_torque`` caps
    the motor effort, so a starved actuator tracks worse (a qualitative sensitivity, NOT a proof of the
    screen's threshold). Honest boundary: position control with a high force limit tracks trivially, the
    base is FIXED, and the load is self-weight + inertia only (no foot contact or payload) — the signal
    is the MOTION and the foot arc, not a full contact gait.
    Fixed step + fixed solver iterations ⇒ reproducible. Raises ValueError on non-positive inputs or an
    out-of-range joint index."""
    if amplitude_rad <= 0.0 or frequency_hz <= 0.0 or max_torque <= 0.0 or duration <= 0.0 or dt <= 0.0:
        raise ValueError("amplitude, frequency, max_torque, duration and dt must be positive")
    with _world(urdf_str, fixed_base=True) as (p, client, body):
        p.setTimeStep(dt, physicsClientId=client)
        p.setPhysicsEngineParameter(numSolverIterations=50, numSubSteps=1,
                                    deterministicOverlappingPairs=1, physicsClientId=client)
        n = int(p.getNumJoints(body, physicsClientId=client))
        if not 0 <= joint_index < n:
            raise ValueError(f"joint_index {joint_index} out of range (0..{n - 1})")
        ee_link = n - 1
        omega = 2.0 * math.pi * frequency_hz
        max_err = 0.0
        ee_xyz: list[tuple[float, float, float]] = []
        for step in range(int(round(duration / dt))):
            target = amplitude_rad * math.sin(omega * step * dt)
            for j in range(n):
                p.setJointMotorControl2(body, j, p.POSITION_CONTROL,
                                        targetPosition=(target if j == joint_index else 0.0),
                                        force=max_torque, physicsClientId=client)
            p.stepSimulation(physicsClientId=client)
            achieved = p.getJointState(body, joint_index, physicsClientId=client)[0]
            max_err = max(max_err, abs(achieved - target))
            ee_xyz.append(p.getLinkState(body, ee_link, physicsClientId=client)[0])
        finite = math.isfinite(max_err) and all(math.isfinite(c) for xyz in ee_xyz for c in xyz)
        xs = [x for x, _, _ in ee_xyz]
        zs = [z for _, _, z in ee_xyz]
        ee_travel = ((max(xs) - min(xs)) ** 2 + (max(zs) - min(zs)) ** 2) ** 0.5
        return {"max_tracking_error": max_err, "ee_travel": ee_travel, "finite": finite}


def articulate_and_track(urdf_str: str, *, drives: list[tuple[str, float, float]],
                         track_links: list[str], max_torque: float, duration: float,
                         dt: float = 1.0 / 240.0) -> dict:
    """Drive several NAMED joints through swings (others held at 0) on the fixed-base robot and report
    how far each NAMED link travels — for a branched WHOLE-BODY tree, where one driven joint moves a
    different limb than another (e.g. a hand AND a foot moving at once), which the single-chain
    ``track_joint_swing`` cannot show.

    ``drives`` is a list of ``(joint_name, amplitude_rad, frequency_hz)``; ``track_links`` the link
    names to follow. Returns ``{"travels": {link_name: metres}, "finite": bool}``. Deterministic.
    Raises ValueError on an unknown joint/link name or a non-positive torque/duration/dt."""
    if max_torque <= 0.0 or duration <= 0.0 or dt <= 0.0:
        raise ValueError("max_torque, duration and dt must be positive")
    with _world(urdf_str, fixed_base=True) as (p, client, body):
        p.setTimeStep(dt, physicsClientId=client)
        p.setPhysicsEngineParameter(numSolverIterations=50, numSubSteps=1,
                                    deterministicOverlappingPairs=1, physicsClientId=client)
        n = int(p.getNumJoints(body, physicsClientId=client))
        joint_idx: dict[str, int] = {}
        link_idx: dict[str, int] = {}
        for j in range(n):
            info = p.getJointInfo(body, j, physicsClientId=client)
            joint_idx[info[1].decode()] = j
            link_idx[info[12].decode()] = j  # PyBullet: the child link index equals the joint index
        for jn, _, _ in drives:
            if jn not in joint_idx:
                raise ValueError(f"unknown joint {jn!r}")
        for ln in track_links:
            if ln not in link_idx:
                raise ValueError(f"unknown link {ln!r}")
        driven = {joint_idx[jn]: (amp, 2.0 * math.pi * f) for jn, amp, f in drives}
        positions: dict[str, list[tuple[float, float, float]]] = {ln: [] for ln in track_links}
        for step in range(int(round(duration / dt))):
            t = step * dt
            for j in range(n):
                if j in driven:
                    amp, omega = driven[j]
                    target = amp * math.sin(omega * t)
                else:
                    target = 0.0
                p.setJointMotorControl2(body, j, p.POSITION_CONTROL, targetPosition=target,
                                        force=max_torque, physicsClientId=client)
            p.stepSimulation(physicsClientId=client)
            for ln in track_links:
                positions[ln].append(p.getLinkState(body, link_idx[ln], physicsClientId=client)[0])
        travels: dict[str, float] = {}
        finite = True
        for ln, pts in positions.items():
            if not all(math.isfinite(c) for xyz in pts for c in xyz):
                finite = False
                travels[ln] = float("nan")
                continue
            spans = [max(v[k] for v in pts) - min(v[k] for v in pts) for k in range(3)]
            travels[ln] = (spans[0] ** 2 + spans[1] ** 2 + spans[2] ** 2) ** 0.5
        return {"travels": travels, "finite": finite}


def gravity_compensated_hold(urdf_str: str, pose: dict[str, float], *, compensate: bool = True,
                             kp: float = 10.0, kd: float = 1.0, duration: float = 2.0,
                             dt: float = 1.0 / 240.0) -> dict:
    """Hold a demanding WHOLE-BODY pose on a FIXED (gantry) base by COMPUTED-TORQUE control: each step
    the gravity-compensation torque is computed by the engine's OWN inverse dynamics from the link
    masses + inertials, plus a PD term to the target pose, and applied as joint torques. With
    ``compensate=True`` the limbs HOLD the pose against gravity; with ``compensate=False`` (passive,
    zero motor torque) they collapse under gravity. ``pose`` maps joint names to target angles [rad].

    Returns ``{"max_drift", "finite", "compensate"}`` — ``max_drift`` is the worst |achieved−target|
    over the posed joints [rad] (small ⇒ the pose is held). This is exactly how a humanoid lab
    validates a mass/inertia model + a computed-torque law on a gantry BEFORE free walking: it shows
    GENESIS's mass model yields hold torques a real engine confirms by ACTUALLY holding the pose.
    Honest boundary: FIXED base (no balancing), gravity + the model's own inertials only — NOT
    free-base balance, ZMP walking or a learned gait (that stays the external MuJoCo/Isaac path over
    the same URDF). The gravity feedforward carries the load, so the PD gains are deliberately GENTLE
    (a trim term); large explicit-integration gains would destabilise the light links, not help.
    Deterministic. Raises ValueError on an unknown joint name or non-positive gains/duration/dt."""
    if kp <= 0.0 or kd <= 0.0 or duration <= 0.0 or dt <= 0.0:
        raise ValueError("kp, kd, duration and dt must be positive")
    with _world(urdf_str, fixed_base=True) as (p, client, body):
        p.setTimeStep(dt, physicsClientId=client)
        p.setPhysicsEngineParameter(numSolverIterations=50, numSubSteps=1,
                                    deterministicOverlappingPairs=1, physicsClientId=client)
        n = int(p.getNumJoints(body, physicsClientId=client))
        name_to_index = {p.getJointInfo(body, j, physicsClientId=client)[1].decode(): j
                         for j in range(n)}
        for jn in pose:
            if jn not in name_to_index:
                raise ValueError(f"unknown joint {jn!r}")
        target = [0.0] * n
        posed = [name_to_index[jn] for jn in pose]
        for jn, angle in pose.items():
            j = name_to_index[jn]
            target[j] = angle
            p.resetJointState(body, j, targetValue=angle, targetVelocity=0.0, physicsClientId=client)
        # disable the default per-joint velocity motors so applied torques are not fought
        for j in range(n):
            p.setJointMotorControl2(body, j, p.VELOCITY_CONTROL, force=0.0, physicsClientId=client)
        max_drift = 0.0
        finite = True
        for _ in range(int(round(duration / dt))):
            states = [p.getJointState(body, j, physicsClientId=client) for j in range(n)]
            q = [s[0] for s in states]
            qd = [s[1] for s in states]
            if compensate:
                # computed-torque: engine inverse dynamics gives the gravity-hold torque at q
                # (zero vel/accel), then a PD term to the target pose closes the loop.
                tau_g = p.calculateInverseDynamics(body, q, [0.0] * n, [0.0] * n,
                                                   physicsClientId=client)
                tau = [tau_g[j] + kp * (target[j] - q[j]) - kd * qd[j] for j in range(n)]
            else:
                tau = [0.0] * n
            for j in range(n):
                p.setJointMotorControl2(body, j, p.TORQUE_CONTROL, force=tau[j],
                                        physicsClientId=client)
            p.stepSimulation(physicsClientId=client)
            for j in posed:
                ach = p.getJointState(body, j, physicsClientId=client)[0]
                if not math.isfinite(ach):
                    finite = False
                else:
                    max_drift = max(max_drift, abs(ach - target[j]))
        return {"max_drift": max_drift, "finite": finite, "compensate": compensate}


def drop_test(urdf_str: str, *, start_height: float = 0.6, duration: float = 2.0,
              dt: float = 1.0 / 240.0) -> dict:
    """Drop the free-base leg from ``start_height`` onto a ground plane and step the real dynamics
    with a fixed step and fixed solver iterations (reproducible run-to-run). A QUALITATIVE stability
    smoke-test, not a quantitative contact validation. Returns ``{"base_z_start", "base_z_end",
    "min_base_z", "finite", "fell", "settled"}``: ``finite`` is False if any state went NaN/Inf (an
    exploded sim — a design/inertia error); ``fell`` that the base dropped under gravity; ``settled``
    that the last 10 % of the run barely moved. Raises ValueError on a non-positive height/duration/dt."""
    if start_height <= 0.0 or duration <= 0.0 or dt <= 0.0:
        raise ValueError("start_height, duration and dt must be positive")
    with _world(urdf_str, fixed_base=False, with_plane=True,
                base_position=(0.0, 0.0, start_height)) as (p, client, body):
        p.setTimeStep(dt, physicsClientId=client)
        # fixed solver iterations + deterministic pair ordering → identical run-to-run (DIRECT is
        # single-threaded). The test pins this by asserting two runs return the same trajectory.
        p.setPhysicsEngineParameter(numSolverIterations=50, numSubSteps=1,
                                    deterministicOverlappingPairs=1, physicsClientId=client)
        n_steps = int(round(duration / dt))
        zs: list[float] = []
        for _ in range(n_steps):
            p.stepSimulation(physicsClientId=client)
            (_, _, z), _ = p.getBasePositionAndOrientation(body, physicsClientId=client)
            zs.append(z)
        finite = all(math.isfinite(z) for z in zs)
        tail = zs[max(0, len(zs) - len(zs) // 10):] or zs[-1:]
        settled = finite and (max(tail) - min(tail) < 0.01)
        return {
            "base_z_start": start_height,
            "base_z_end": zs[-1] if zs else start_height,
            "min_base_z": min(zs) if zs else start_height,
            "finite": finite,
            "fell": bool(zs and zs[-1] < start_height),
            "settled": settled,
        }
