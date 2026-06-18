"""Kinematics — the closed-form axes a legged/armed robot lives or dies by (δ-layer).

The structural validators catch a limb that breaks; the flight axes catch a vehicle that
cannot lift. Nothing yet caught a robot arm that cannot REACH its target, a joint sized for
the wrong TORQUE, or a humanoid that TIPS OVER. These are exactly the closed forms a first-pass
robot is sized with — honest engineering screens, not a full multibody dynamics simulation.

Four building blocks + two checks, each verified against an exact anchor (not vibes):

  * ``forward_kinematics_dh`` — the Denavit–Hartenberg product. Each link i contributes the
    standard homogeneous transform A_i(a,α,d,θ); the end-effector pose is A_1·…·A_n. For a planar
    2R arm (α=d=0) it reduces to x=l₁cosθ₁+l₂cos(θ₁+θ₂), y=l₁sinθ₁+l₂sin(θ₁+θ₂) — the test pins
    the general DH product against this closed form to machine precision.
  * ``inverse_kinematics_2r`` — the analytic 2-link inverse (law of cosines): a target is
    reachable iff |(r²−l₁²−l₂²)/(2l₁l₂)| ≤ 1, and the elbow-up/down solution inverts the forward
    map exactly (the test round-trips FK→IK→FK). Full numerical IK is iterative and out of scope;
    only the closed-form 2R case is gate-able here.
  * ``static_joint_torques`` — the gravity torque each planar joint must hold: τ_i = g·Σ_{distal}
    m_j·(x_j − x_jointᵢ), the horizontal lever arm of every mass beyond the joint. A massless link
    of length L holding payload m horizontally needs τ = m·g·L at the base — pinned exactly. This
    is the demand the actuator axis is sized against.
  * ``reach_check`` — is a target within the arm's workspace annulus |l₁−l₂| ≤ r ≤ l₁+l₂?
  * ``zmp_balance_check`` — the Zero-Moment-Point stability screen: ZMP_x = x_com − (z_com/g)·a_x;
    the robot is statically/dynamically balanced iff the ZMP lies inside the support polygon
    [x_min, x_max]. Centered → margin 1, at the edge → margin 0, outside → ``ok=False``.

Offline, deterministic, numpy for the matrix products. Honest boundary: planar gravity statics +
the closed-form 2R inverse — not full 3-D recursive Newton–Euler and not a dynamic walk.
"""

from __future__ import annotations

import math

import numpy as np

#: Standard gravity (m/s²) — the sizing default; pass your own for the Moon.
STANDARD_GRAVITY = 9.80665


def _dh_matrix(a: float, alpha: float, d: float, theta: float) -> np.ndarray:
    """One Denavit–Hartenberg homogeneous transform A_i(a, α, d, θ) (Craig/Spong convention)."""
    ca, sa = math.cos(alpha), math.sin(alpha)
    ct, st = math.cos(theta), math.sin(theta)
    return np.array([
        [ct, -st * ca,  st * sa, a * ct],
        [st,  ct * ca, -ct * sa, a * st],
        [0.0,      sa,       ca,      d],
        [0.0,     0.0,      0.0,    1.0],
    ], dtype=float)


def forward_kinematics_dh(links: list[tuple[float, float, float, float]]) -> dict:
    """End-effector pose of a serial chain from its Denavit–Hartenberg links.

    `links` is a list of (a, alpha, d, theta) tuples (lengths in m, angles in rad). Returns
    ``{"position": (x, y, z), "pose": 4x4 list}`` — the product A_1·…·A_n. Raises ValueError on
    an empty chain."""
    if not links:
        raise ValueError("need at least one link")
    t = np.eye(4)
    for a, alpha, d, theta in links:
        t = t @ _dh_matrix(a, alpha, d, theta)
    pos = t[:3, 3]
    return {"position": (float(pos[0]), float(pos[1]), float(pos[2])),
            "pose": t.tolist()}


def inverse_kinematics_2r(l1: float, l2: float, x: float, y: float, *, elbow_up: bool = True) -> dict:
    """Analytic inverse kinematics of a planar 2R arm reaching (x, y).

    Returns ``{"theta1", "theta2", "reachable"}`` (angles in rad). ``reachable`` is False when the
    target lies outside the workspace annulus (then the angles are NaN). Raises ValueError on
    non-positive link lengths. At a SINGULAR configuration — fully extended (r = l₁+l₂) or fully
    folded (r = |l₁−l₂|, e.g. the origin when l₁=l₂) — the Jacobian is rank-deficient and θ₁ is
    geometrically indeterminate; the function returns one valid branch (θ₁ from ``atan2(y, x)``)
    that still satisfies forward kinematics, but it is not the unique pose."""
    if l1 <= 0.0 or l2 <= 0.0:
        raise ValueError("link lengths must be positive")
    r2 = x * x + y * y
    cos_t2 = (r2 - l1 * l1 - l2 * l2) / (2.0 * l1 * l2)
    if abs(cos_t2) > 1.0:
        return {"theta1": float("nan"), "theta2": float("nan"), "reachable": False}
    t2 = math.acos(max(-1.0, min(1.0, cos_t2)))
    if not elbow_up:
        t2 = -t2
    t1 = math.atan2(y, x) - math.atan2(l2 * math.sin(t2), l1 + l2 * math.cos(t2))
    return {"theta1": float(t1), "theta2": float(t2), "reachable": True}


def _planar_joint_positions(link_lengths: list[float], joint_angles: list[float]) -> list[tuple[float, float]]:
    """World positions of each joint (and the end-effector) for a planar serial chain with
    CUMULATIVE joint angles. Returns n+1 points p_0=(0,0) … p_n (end-effector)."""
    pts = [(0.0, 0.0)]
    cum = 0.0
    x, y = 0.0, 0.0
    for length, angle in zip(link_lengths, joint_angles):
        cum += angle
        x += length * math.cos(cum)
        y += length * math.sin(cum)
        pts.append((x, y))
    return pts


def static_joint_torques(
    link_lengths: list[float],
    joint_angles: list[float],
    link_masses: list[float],
    payload_mass: float = 0.0,
    g: float = STANDARD_GRAVITY,
) -> dict:
    """Gravity torque each planar joint must hold against link weights + a tip payload.

    τ_i = g·Σ_{distal} m_j·(x_j − x_jointᵢ): every mass beyond joint i contributes its weight times
    its horizontal lever arm. Link masses act at link midpoints; the payload at the end-effector.
    Returns ``{"torques", "max_torque"}`` (N·m). Coordinate frame: ``x`` is the GLOBAL horizontal
    world axis (joint angles are cumulative from +x) and gravity acts along −y; the result is the
    GRAVITY-ONLY static hold torque (no joint speed/acceleration, no friction — sized in the
    actuation axis). Raises ValueError on length mismatch, non-positive g, or negative masses/lengths."""
    n = len(link_lengths)
    if not (len(joint_angles) == n and len(link_masses) == n) or n == 0:
        raise ValueError("link_lengths, joint_angles, link_masses must be the same non-zero length")
    if g <= 0.0:
        raise ValueError("g must be positive")
    if any(m < 0.0 for m in link_masses) or payload_mass < 0.0 or any(l < 0.0 for l in link_lengths):
        raise ValueError("masses and lengths must be non-negative")

    pts = _planar_joint_positions(link_lengths, joint_angles)
    link_com_x = [0.5 * (pts[k][0] + pts[k + 1][0]) for k in range(n)]   # midpoint of link k
    end_x = pts[n][0]

    torques = []
    for i in range(n):                       # joint i is located at pts[i]
        joint_x = pts[i][0]
        tau = g * sum(link_masses[k] * (link_com_x[k] - joint_x) for k in range(i, n))
        tau += g * payload_mass * (end_x - joint_x)
        torques.append(float(tau))
    return {"torques": tuple(torques), "max_torque": float(max(abs(t) for t in torques))}


def reach_check(l1: float, l2: float, x: float, y: float) -> dict:
    """Is target (x, y) inside the planar 2R workspace annulus |l₁−l₂| ≤ r ≤ l₁+l₂?

    Returns ``{"reach", "max_reach", "min_reach", "safety_factor", "ok"}``; safety_factor is the
    fraction of the max reach still available (max_reach / reach), >1 when inside. Raises ValueError
    on non-positive link lengths."""
    if l1 <= 0.0 or l2 <= 0.0:
        raise ValueError("link lengths must be positive")
    reach = math.hypot(x, y)
    max_reach = l1 + l2
    min_reach = abs(l1 - l2)
    ok = min_reach <= reach <= max_reach
    safety_factor = max_reach / reach if reach > 0.0 else float("inf")
    return {"reach": reach, "max_reach": max_reach, "min_reach": min_reach,
            "safety_factor": safety_factor, "ok": ok}


def zmp_balance_check(
    com_x: float,
    com_z: float,
    support_min_x: float,
    support_max_x: float,
    accel_x: float = 0.0,
    g: float = STANDARD_GRAVITY,
) -> dict:
    """Zero-Moment-Point stability screen for a planar robot.

    ZMP_x = com_x − (com_z/g)·accel_x (static: accel_x = 0 → ZMP = com_x). The robot is balanced
    iff the ZMP lies inside the support polygon [support_min_x, support_max_x]. Returns
    ``{"zmp_x", "support_min_x", "support_max_x", "stability_margin", "ok"}`` — stability_margin is
    the distance from the ZMP to the nearest edge normalised by the half-width (1 = centred, 0 = on
    the edge, <0 = outside → ok=False). ``x`` is the global horizontal world axis. This is the
    simplified inverted-pendulum ZMP: it neglects vertical CoM acceleration, angular momentum about
    the CoM, and multi-body rotation (the full-body dynamic ZMP is the declared boundary). Raises
    ValueError on a degenerate support polygon, negative com_z, or non-positive g."""
    if support_max_x <= support_min_x:
        raise ValueError("support polygon must have support_max_x > support_min_x")
    if com_z < 0.0:
        raise ValueError("com height must be non-negative")
    if g <= 0.0:
        raise ValueError("g must be positive")
    zmp_x = com_x - (com_z / g) * accel_x
    half_width = 0.5 * (support_max_x - support_min_x)
    margin = min(zmp_x - support_min_x, support_max_x - zmp_x) / half_width
    return {"zmp_x": float(zmp_x), "support_min_x": support_min_x, "support_max_x": support_max_x,
            "stability_margin": float(margin), "ok": support_min_x <= zmp_x <= support_max_x}
