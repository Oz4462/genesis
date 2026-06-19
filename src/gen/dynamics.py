"""Dynamics — the closed-form axes a walking robot lives or dies by, OVER THE MOTION (δ-layer).

The robot kinematics/actuation axes (kinematics.py, actuation.py) screen ONE pose: does the arm
reach, is the leg statically balanced, is the motor big enough to HOLD the joint. None of them ask
the dynamic question the user did — can it actually MOVE: does fast stepping tip it over, can the
motor ACCELERATE the limb (not just hold it)? These axes answer that, over a gait cycle, in closed
form — honest engineering screens, not a multibody contact simulation and not a learned controller.

Three validators (each verified against exact anchors in the tests):

  * ``pendulum_period`` / ``swing_resonance_check`` — a swing leg is a PHYSICAL PENDULUM:
    T = 2·π·√(I / (m·g·d)) (I about the hip, d = hip→CoM). Its natural swing frequency
    f_n = 1/T is the cadence the passive dynamics give for free; stepping much faster than f_n
    is what costs torque (passive-dynamic-walking insight). ok ⟺ step cadence ≤ f_n.
  * ``zmp_dynamic_check`` — DYNAMIC balance via the cart-table / ZMP model over a gait cycle.
    For a CoM swaying as x(t) = x0 + A·sin(ω·t) at height z, the Zero-Moment-Point is
    ZMP(t) = x(t) − (z/g)·ẍ(t) = x0 + A·(1 + (z/g)·ω²)·sin(ω·t). The peak excursion is therefore
    A·(1 + (z/g)·ω²): the static sway A AMPLIFIED by (z/g)·ω² — so a sway that is fine standing
    still walks the ZMP right off the foot as the cadence rises (the dynamic tip-over the static
    zmp_balance_check cannot see). ok ⟺ the whole ZMP trajectory stays in the support polygon.
  * ``joint_swing_torque_check`` — INVERSE DYNAMICS of one swinging limb over the cycle: the
    actuator torque to drive θ(t) = A·sin(ω·t) is τ(t) = I·θ̈(t) + m·g·d·sin(θ(t)). The inertial
    term peaks at I·A·ω² — the torque to ACCELERATE the limb, which the static hold check omits
    entirely. The required peak |τ| over the cycle is sampled deterministically and screened
    against the actuator's available torque. ok ⟺ available ≥ peak required.

Units: SI throughout (kg, m, s, rad, N·m, Hz; ω = 2·π·f). Standard gravity g = 9.80665 m/s².

Honest boundary: these are PLANAR, single-DOF, RIGID-body screens on a SINUSOIDAL trajectory
approximation. They are NOT a multibody simulation (no ground-contact/friction model, no whole-body
coupling between joints, no double-support dynamics) and NOT a learned/optimised gait. They answer
"is this cadence/limb dynamically feasible at first order", the deterministic bridge toward motion —
full dynamic walking is the URDF → MuJoCo/Isaac path (an opt-in export, not a closed-form gate). A
passed check is necessary, not sufficient.

Sources: physical-pendulum period — standard classical mechanics (e.g. Goldstein, *Classical
Mechanics*). ZMP / cart-table model ZMP = x − (z/g)·ẍ — M. Vukobratović & B. Borovac, "Zero-Moment
Point — thirty-five years of its life" (2004); S. Kajita et al., *Introduction to Humanoid Robotics*
(Springer), the linear-inverted-pendulum / cart-table preview. Single-link inverse dynamics
τ = I·θ̈ + m·g·d·sin θ — M. Spong, *Robot Modeling and Control*, standard Euler–Lagrange result.
"""

from __future__ import annotations

import math

#: Standard gravity [m/s²] (CGPM convention).
STANDARD_GRAVITY = 9.80665


def pendulum_period(inertia: float, mass: float, com_distance: float,
                    g: float = STANDARD_GRAVITY) -> float:
    """Physical-pendulum period T = 2·π·√(I / (m·g·d)) [s] (I about the pivot, d = pivot→CoM).

    For a point mass at length L (I = m·L², d = L) this reduces to the simple-pendulum
    T = 2·π·√(L/g). Raises ValueError on a non-positive inertia, mass, distance or g."""
    if inertia <= 0.0:
        raise ValueError("inertia must be positive")
    if mass <= 0.0:
        raise ValueError("mass must be positive")
    if com_distance <= 0.0:
        raise ValueError("CoM distance must be positive")
    if g <= 0.0:
        raise ValueError("gravity must be positive")
    return 2.0 * math.pi * math.sqrt(inertia / (mass * g * com_distance))


def swing_resonance_check(inertia: float, mass: float, com_distance: float,
                          step_frequency: float, g: float = STANDARD_GRAVITY) -> dict:
    """Does the planned cadence ride the leg's natural swing (efficient) or fight it (costly)?

    Computes the swing leg's natural frequency f_n = 1/T from the physical-pendulum period and
    compares it to the planned ``step_frequency``. Returns ``{"natural_period_s", "natural_frequency_hz",
    "step_frequency_hz", "safety_factor", "ok"}`` with safety_factor = f_n / step_frequency; ok when
    the cadence is at or below the natural frequency (the passive dynamics carry the swing). Raises
    ValueError on a non-positive step frequency (others via ``pendulum_period``)."""
    if step_frequency <= 0.0:
        raise ValueError("step frequency must be positive")
    period = pendulum_period(inertia, mass, com_distance, g)
    f_natural = 1.0 / period
    safety_factor = f_natural / step_frequency
    return {
        "natural_period_s": period,
        "natural_frequency_hz": f_natural,
        "step_frequency_hz": step_frequency,
        "safety_factor": safety_factor,
        "ok": step_frequency <= f_natural,
    }


def zmp_dynamic_check(
    com_height: float,
    com_amplitude: float,
    step_frequency: float,
    support_min_x: float,
    support_max_x: float,
    com_offset: float = 0.0,
    g: float = STANDARD_GRAVITY,
) -> dict:
    """Dynamic balance: does the ZMP stay under the foot for the WHOLE gait cycle?

    For a CoM swaying x(t) = com_offset + com_amplitude·sin(ω·t) at height ``com_height``, the
    cart-table model gives ZMP(t) = x(t) − (com_height/g)·ẍ(t), whose peak excursion from
    ``com_offset`` is ``com_amplitude·(1 + (com_height/g)·ω²)`` with ω = 2·π·step_frequency — the
    static sway amplified by the dynamic factor (com_height/g)·ω². Returns ``{"omega", "dynamic_factor",
    "zmp_excursion", "zmp_min", "zmp_max", "support_min_x", "support_max_x", "safety_factor", "ok"}``.
    ``ok`` iff [zmp_min, zmp_max] ⊆ [support_min_x, support_max_x]; safety_factor = (nearest support
    margin from the offset) / zmp_excursion (≥ 1 ⟺ the excursion fits). Raises ValueError on a
    non-positive height/frequency/g, a negative amplitude, or a support interval that does not contain
    the CoM offset (an already-unbalanced stance)."""
    if com_height <= 0.0:
        raise ValueError("CoM height must be positive")
    if step_frequency <= 0.0:
        raise ValueError("step frequency must be positive")
    if g <= 0.0:
        raise ValueError("gravity must be positive")
    if com_amplitude < 0.0:
        raise ValueError("CoM amplitude must be non-negative")
    if not support_min_x < support_max_x:
        raise ValueError("support polygon must have support_min_x < support_max_x")
    if not support_min_x <= com_offset <= support_max_x:
        raise ValueError("CoM offset must lie within the support polygon (stance already unbalanced)")
    omega = 2.0 * math.pi * step_frequency
    dynamic_factor = 1.0 + (com_height / g) * omega * omega
    excursion = com_amplitude * dynamic_factor
    zmp_min = com_offset - excursion
    zmp_max = com_offset + excursion
    edge_margin = min(support_max_x - com_offset, com_offset - support_min_x)
    safety_factor = math.inf if excursion == 0.0 else edge_margin / excursion
    return {
        "omega": omega,
        "dynamic_factor": dynamic_factor,
        "zmp_excursion": excursion,
        "zmp_min": zmp_min,
        "zmp_max": zmp_max,
        "support_min_x": support_min_x,
        "support_max_x": support_max_x,
        "safety_factor": safety_factor,
        "ok": support_min_x <= zmp_min and zmp_max <= support_max_x,
    }


def joint_swing_torque_check(
    inertia: float,
    mass: float,
    com_distance: float,
    amplitude_rad: float,
    step_frequency: float,
    available_torque: float,
    g: float = STANDARD_GRAVITY,
    n_samples: int = 720,
) -> dict:
    """Inverse dynamics: can the actuator ACCELERATE the limb through the swing, not just hold it?

    For a joint angle θ(t) = amplitude_rad·sin(ω·t) the actuator torque is
    τ(t) = I·θ̈(t) + m·g·d·sin(θ(t)) with ω = 2·π·step_frequency. The inertial component peaks at
    I·amplitude_rad·ω² (the dynamic torque the static hold check omits) and the gravity component at
    m·g·d·sin(amplitude_rad); the required peak |τ| over one cycle is sampled deterministically.
    Returns ``{"omega", "peak_inertial_torque", "peak_gravity_torque", "peak_required_torque",
    "available_torque", "safety_factor", "ok"}`` with safety_factor = available_torque /
    peak_required_torque. Raises ValueError on non-positive inertia/mass/distance/frequency/torque, an
    amplitude outside (0, π], or fewer than 8 samples."""
    if inertia <= 0.0 or mass <= 0.0 or com_distance <= 0.0:
        raise ValueError("inertia, mass and CoM distance must be positive")
    if not 0.0 < amplitude_rad <= math.pi:
        raise ValueError("swing amplitude must be in (0, pi] radians")
    if step_frequency <= 0.0:
        raise ValueError("step frequency must be positive")
    if available_torque <= 0.0:
        raise ValueError("available torque must be positive")
    if n_samples < 8:
        raise ValueError("need at least 8 samples to resolve the peak")
    omega = 2.0 * math.pi * step_frequency
    peak_inertial = inertia * amplitude_rad * omega * omega
    peak_gravity = mass * g * com_distance * math.sin(amplitude_rad)
    peak_required = 0.0
    for k in range(n_samples):
        wt = 2.0 * math.pi * k / n_samples
        theta = amplitude_rad * math.sin(wt)
        theta_ddot = -amplitude_rad * omega * omega * math.sin(wt)
        tau = inertia * theta_ddot + mass * g * com_distance * math.sin(theta)
        peak_required = max(peak_required, abs(tau))
    safety_factor = available_torque / peak_required
    return {
        "omega": omega,
        "peak_inertial_torque": peak_inertial,
        "peak_gravity_torque": peak_gravity,
        "peak_required_torque": peak_required,
        "available_torque": available_torque,
        "safety_factor": safety_factor,
        "ok": available_torque >= peak_required,
    }
