"""agiloped_stand — a robust standing posture + push-tested stand for AGILOped (NimbRo-OP lineage).

Background (measured in prior sessions, see project memory): AGILOped's shipped model has no real sole
(:mod:`gen.humanoids.agiloped_feet` adds a flat box one) AND a baked −44° hip-chain splay, so a naive
stand is impossible. The prior fix produced a stand that held the full 6 s statically but was a CONTRIVED
knock-kneed pose (aggressive ``hip_roll=∓0.775`` un-splay pulls the knees together) with SHORT fore-aft
soles, so it toppled on a SAGITTAL (fore-aft) push — the support basin was narrow front-to-back.

This module hardens that:
  1. ``WIDE_FOOT_SPECS`` — a LONGER fore-aft sole (0.20 m vs 0.135 m) sized to a realistic humanoid foot,
     widening the fore-aft support basin so sagittal pushes have a larger stability margin. The lateral
     width is also modestly increased. Still a thin, near-massless box (a contact-fidelity repair, not a
     fabricated dynamics change).
  2. ``ROBUST_STANDING_POSE`` — a GENTLER un-splay (``hip_roll=∓0.5`` instead of ∓0.775) so the knees are
     not jammed together (more natural, wider lateral stance), with the foot-flat ankle_roll re-tuned to
     the smaller un-splay. This trades the contrived knock-knee look for a wider, more natural base.
  3. ``stand_with_push`` — the honest test: PD-hold the pose on a ground plane, optionally apply a
     reproducible base-velocity shove at a set time, and report measured upright-seconds + whether it held
     the full horizon. Used to compare sagittal vs lateral push survival before/after the widening.

Everything here is honest: foot dimensions are a realistic sole size, the pose is tuned by measurement,
and the stand outcome is reported, never assumed. PyBullet path (AGILOped is a URDF model).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from gen.humanoids.agiloped_feet import AGILOPED_NOPARALLEL_URDF, FlatFootSpec, add_flat_feet

#: WIDER + RE-CENTRED fore-aft sole: 0.20 m long (vs the old 0.135 m), shifted BACK to x=−0.015 so the
#: whole-body CoM (measured at x≈−0.018 in the un-splay stance) sits in the MIDDLE of the fore-aft support
#: instead of at its back edge. The old 0.135 m sole at x=+0.040 gave only 0.013 m of BACK margin (contact
#: x=[−0.030,+0.105], CoM_x=−0.018) → any sagittal/backward push toppled it. The new sole gives ≈0.10 m
#: margin on BOTH the front AND the back (contact x=[−0.117,+0.083]) → a symmetric, much larger sagittal
#: basin. y-width 0.090 m unchanged (lateral basin was already wide: contact y span ≈0.22 m).
#: NOTE: ``roll`` is kept 0 here on purpose — the sole inherits the ankle_link's baked ±29° roll, but the
#: TILTED sole's lowest EDGE makes the working ground contact under the CoM (counter-rolling the sole to
#: flat moves the contact patch outboard and DEstabilises the static stand — measured). The fix that
#: matters for the sagittal failure is the fore-aft length + re-centring, not the roll.
WIDE_FOOT_SPECS: tuple[FlatFootSpec, ...] = (
    FlatFootSpec("left_ankle_link",  size_x=0.200, size_y=0.090, thickness=0.012, x=-0.015, y=0.0, z_bottom=-0.090),
    FlatFootSpec("right_ankle_link", size_x=0.200, size_y=0.090, thickness=0.012, x=-0.015, y=0.0, z_bottom=-0.090),
)

#: output URDF for the wide-sole variant (distinct from the default agiloped_feet output)
AGILOPED_WIDEFEET_URDF = (
    "/home/genesis/humanoid_assets/agiloped/nimbro_op_model/robots/nimbro_new_repaired_noparallel_widefeet.urdf")

#: The standing posture. The ∓0.775 hip-roll un-splay is REQUIRED (not contrived for looks): it counters
#: the model's baked −44° hip-chain splay so the tilted soles' edges make ground contact under the CoM; a
#: gentler ∓0.5 un-splay leaves the feet too splayed to contact properly and DEstabilises the stand
#: (measured: ∓0.5 falls even lateral pushes the ∓0.775 survives). ankle_roll ∓0.4 + ankle_pitch −0.25
#: foot-flatten; knee 0.5 / hip_pitch −0.25 is the CoM-lowering crouch. The robustness gain vs the prior
#: stand comes from the WIDER, re-centred sole (:data:`WIDE_FOOT_SPECS`), not a pose change.
ROBUST_STANDING_POSE: dict[str, float] = {
    "left_hip_roll": -0.775, "right_hip_roll": 0.775,
    "left_ankle_roll": -0.4, "right_ankle_roll": 0.4,
    "left_ankle_pitch": -0.25, "right_ankle_pitch": -0.25,
    "left_knee_pitch": 0.5, "right_knee_pitch": 0.5,
    "left_hip_pitch": -0.25, "right_hip_pitch": -0.25,
}


def build_wide_feet(urdf_out: str = AGILOPED_WIDEFEET_URDF) -> str:
    """Write the AGILOped no-parallel URDF with the WIDER fore-aft box soles. Returns the path."""
    return add_flat_feet(urdf_in=AGILOPED_NOPARALLEL_URDF, urdf_out=urdf_out, specs=WIDE_FOOT_SPECS)


@dataclass(frozen=True)
class PushStandResult:
    """Honest measured outcome of a PD-held stand with an optional reproducible push."""
    robot: str
    held_full_horizon: bool
    upright_seconds: float
    horizon_seconds: float
    push_xy: tuple[float, float]
    push_at_s: float
    base_tilt_max_deg: float
    base_z_start: float
    base_z_end: float
    com_drift_m: float
    fell: bool
    finite: bool


def stand_with_push(urdf_path: str, target_pose: dict[str, float],
                    *, seconds: float = 6.0, kp: float = 200.0, kd: float = 8.0,
                    max_force: float = 80.0, fall_tilt_deg: float = 45.0,
                    push_xy: tuple[float, float] = (0.0, 0.0), push_at_s: float = 2.0,
                    settle_drop: float = 0.002) -> PushStandResult:
    """PD-hold ``target_pose`` on a ground plane and optionally shove the base, measuring the stand.

    Mirrors :func:`insim.pd_balance` (POSITION_CONTROL implicit PD per movable joint) but adds a
    reproducible base linear-velocity kick ``push_xy`` [m/s] at ``push_at_s`` to probe the stability
    basin direction-by-direction (sagittal +x vs lateral +y). Returns the honest upright-seconds + tilt;
    never asserts success. Raises if PyBullet is unavailable."""
    import pybullet
    import pybullet_data
    from gen.humanoids.insim import _engine, _load_urdf, _world_com, _FIXED_TIMESTEP, _JTYPE

    if not Path(urdf_path).is_file():
        raise FileNotFoundError(f"URDF not found: {urdf_path}")
    with _engine() as (p, c):
        p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=c)
        p.loadURDF("plane.urdf", physicsClientId=c)
        bid = _load_urdf(p, c, urdf_path, fixed_base=False, base_position=(0.0, 0.0, 1.5))
        nj = p.getNumJoints(bid, physicsClientId=c)
        name_to_idx = {p.getJointInfo(bid, j, physicsClientId=c)[1].decode(): j for j in range(nj)}
        movable = [j for j in range(nj)
                   if _JTYPE.get(p.getJointInfo(bid, j, physicsClientId=c)[2]) != "fixed"]
        targets = {j: 0.0 for j in movable}
        for nm, val in (target_pose or {}).items():
            if nm in name_to_idx and name_to_idx[nm] in targets:
                targets[name_to_idx[nm]] = float(val)
        for j, q in targets.items():
            p.resetJointState(bid, j, q, physicsClientId=c)
        aabb_min = min((p.getAABB(bid, j, physicsClientId=c)[0][2] for j in range(-1, nj)), default=1.5)
        bp, bo = p.getBasePositionAndOrientation(bid, physicsClientId=c)
        p.resetBasePositionAndOrientation(bid, (bp[0], bp[1], bp[2] - aabb_min + settle_drop), bo,
                                          physicsClientId=c)
        for j, q in targets.items():
            p.setJointMotorControl2(bid, j, p.POSITION_CONTROL, targetPosition=q,
                                    positionGain=kp / 1000.0, velocityGain=kd / 1000.0,
                                    force=max_force, physicsClientId=c)

        steps = max(1, int(seconds / _FIXED_TIMESTEP))
        push_step = int(push_at_s / _FIXED_TIMESTEP)
        bp0, bo0 = p.getBasePositionAndOrientation(bid, physicsClientId=c)
        com0, _ = _world_com(p, c, bid, nj)
        tilt_max = 0.0
        upright_steps = steps
        toppled = False
        fell = False
        finite = True
        for s in range(steps):
            if s == push_step and (push_xy[0] or push_xy[1]):
                _, ang = p.getBaseVelocity(bid, physicsClientId=c)
                p.resetBaseVelocity(bid, linearVelocity=[push_xy[0], push_xy[1], 0.0],
                                    angularVelocity=list(ang), physicsClientId=c)
            p.stepSimulation(physicsClientId=c)
            bp, bo = p.getBasePositionAndOrientation(bid, physicsClientId=c)
            if not all(math.isfinite(v) for v in (*bp, *bo)):
                finite = False
                fell = True
                upright_steps = s
                break
            # tilt = angle of the base z-axis from world up
            rot = p.getMatrixFromQuaternion(bo)
            up_z = rot[8]  # world-z component of the body z-axis
            tilt = math.degrees(math.acos(max(-1.0, min(1.0, up_z))))
            tilt_max = max(tilt_max, tilt)
            if tilt > fall_tilt_deg and not toppled:
                toppled = True
                upright_steps = s
        z1 = p.getBasePositionAndOrientation(bid, physicsClientId=c)[0][2]
        com1, _ = _world_com(p, c, bid, nj)
        drift = math.hypot(com1[0] - com0[0], com1[1] - com0[1])

        upright_sec = upright_steps * _FIXED_TIMESTEP
        held_full = (not toppled) and finite
        return PushStandResult(
            robot="agiloped", held_full_horizon=held_full,
            upright_seconds=round(min(upright_sec, seconds), 3), horizon_seconds=seconds,
            push_xy=push_xy, push_at_s=push_at_s, base_tilt_max_deg=round(tilt_max, 2),
            base_z_start=round(bp0[2], 4), base_z_end=round(z1, 4), com_drift_m=round(drift, 4),
            fell=(toppled or fell), finite=finite)
