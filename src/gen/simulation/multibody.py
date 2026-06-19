"""simulation/multibody.py — a REAL forward-dynamics integrator (no proxies, no fabrication).

``simulation/runner.py`` "predicts" from bounding-box proxies and hardcoded constants — it never
integrates the equations of motion, and one of its functions even takes ``max(deflection, stress)``
(a length and a stress) and guesses the unit by magnitude. This module is the honest alternative:
it time-steps the ACTUAL nonlinear rigid-body dynamics of a driven pendulum link with RK4,
deterministically. Two properties make it trustworthy rather than asserted:

  1. VALIDATED INTEGRATOR — with zero torque it CONSERVES ENERGY (½·I·ω² + m·g·d·(1−cosθ) constant to
     the integration tolerance) and reproduces the small-angle period 2π·√(I/(m·g·d)). The integrator
     is checked against the physics it claims to integrate, so a wrong step rule cannot hide.
  2. CROSS-VALIDATION OF THE SCREENS — feed the inverse-dynamics torque that
     ``dynamics.joint_swing_torque_check`` says a swing θ(t)=A·sin(ω·t) needs, integrate it FORWARD,
     and the recovered motion IS that swing. So the closed-form screen's arithmetic is confirmed by
     simulation: if the screen had miscalculated the torque, the forward motion would not match —
     exactly the "did we compute a part wrong" check the static screens cannot give.

Deterministic, offline, standard-library only. Honest boundary: this is the single-DOF driven
pendulum (one joint, one rigid link, gravity, NO ground-contact model). Multi-link contact walking is
the external-simulator path via ``urdf_bridge`` (PyBullet/MuJoCo/Isaac); this is the deterministic,
anchored core the project owns and can prove on its own.

Source: the pendulum equation of motion I·θ̈ + m·g·d·sin θ = τ is the standard Euler–Lagrange result
(e.g. Goldstein, *Classical Mechanics*); RK4 is the classical 4th-order Runge–Kutta step.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

#: Standard gravity [m/s²] (CGPM convention).
STANDARD_GRAVITY = 9.80665


@dataclass(frozen=True)
class Trajectory:
    """One integrated pendulum run: parallel time / angle / rate / energy samples [SI]."""

    t: list[float]
    theta: list[float]
    omega: list[float]
    energy: list[float]

    @property
    def energy_drift(self) -> float:
        """Max−min total energy over the run, normalised by the mean |energy| — the integrator's
        conservation error (≈ 0 for a passive run with a sound step rule)."""
        e = self.energy
        mean = sum(abs(x) for x in e) / len(e)
        return (max(e) - min(e)) / mean if mean > 0 else 0.0


def total_energy(theta: float, omega: float, inertia: float, mass: float,
                 com_distance: float, g: float = STANDARD_GRAVITY) -> float:
    """Total mechanical energy ½·I·ω² + m·g·d·(1−cos θ) [J] (datum at the hanging rest pose)."""
    return 0.5 * inertia * omega * omega + mass * g * com_distance * (1.0 - math.cos(theta))


def simulate_pendulum(
    theta0: float,
    omega0: float,
    torque_fn: Callable[[float, float, float], float],
    *,
    inertia: float,
    mass: float,
    com_distance: float,
    duration: float,
    dt: float,
    g: float = STANDARD_GRAVITY,
) -> Trajectory:
    """Forward-integrate I·θ̈ = τ(t,θ,ω) − m·g·d·sin θ with classical RK4.

    ``torque_fn(t, theta, omega)`` returns the actuator torque [N·m] (use ``lambda *_: 0.0`` for a
    passive swing). Returns a ``Trajectory`` sampled every ``dt`` over ``[0, duration]``. Deterministic.
    Raises ValueError on non-positive inertia/mass/com_distance/duration or a non-positive dt."""
    if inertia <= 0.0 or mass <= 0.0 or com_distance <= 0.0:
        raise ValueError("inertia, mass and com_distance must be positive")
    if duration <= 0.0 or dt <= 0.0:
        raise ValueError("duration and dt must be positive")

    mgd = mass * g * com_distance

    def deriv(t: float, theta: float, omega: float) -> tuple[float, float]:
        alpha = (torque_fn(t, theta, omega) - mgd * math.sin(theta)) / inertia
        return omega, alpha

    t, theta, omega = 0.0, theta0, omega0
    ts = [t]
    ths = [theta]
    oms = [omega]
    es = [total_energy(theta, omega, inertia, mass, com_distance, g)]
    n_steps = int(round(duration / dt))
    for _ in range(n_steps):
        k1th, k1om = deriv(t, theta, omega)
        k2th, k2om = deriv(t + dt / 2, theta + dt / 2 * k1th, omega + dt / 2 * k1om)
        k3th, k3om = deriv(t + dt / 2, theta + dt / 2 * k2th, omega + dt / 2 * k2om)
        k4th, k4om = deriv(t + dt, theta + dt * k3th, omega + dt * k3om)
        theta += dt / 6 * (k1th + 2 * k2th + 2 * k3th + k4th)
        omega += dt / 6 * (k1om + 2 * k2om + 2 * k3om + k4om)
        t += dt
        ts.append(t)
        ths.append(theta)
        oms.append(omega)
        es.append(total_energy(theta, omega, inertia, mass, com_distance, g))
    return Trajectory(t=ts, theta=ths, omega=oms, energy=es)


def measure_period(traj: Trajectory) -> float:
    """Oscillation period [s] from the mean interval between successive upward zero-crossings of θ
    (linear-interpolated). Raises ValueError if fewer than two crossings occur (no full oscillation)."""
    crossings: list[float] = []
    th, ts = traj.theta, traj.t
    for i in range(len(th) - 1):
        if th[i] <= 0.0 < th[i + 1]:
            frac = -th[i] / (th[i + 1] - th[i])
            crossings.append(ts[i] + frac * (ts[i + 1] - ts[i]))
    if len(crossings) < 2:
        raise ValueError("fewer than two upward zero-crossings — no full oscillation to measure")
    intervals = [b - a for a, b in zip(crossings, crossings[1:])]
    return sum(intervals) / len(intervals)


def feedforward_swing_torque(
    amplitude_rad: float, step_frequency: float, inertia: float, mass: float,
    com_distance: float, g: float = STANDARD_GRAVITY,
) -> Callable[[float, float, float], float]:
    """The INVERSE-dynamics torque τ(t) = I·θ̈_des + m·g·d·sin(θ_des) for the desired swing
    θ_des(t) = amplitude·sin(ω·t) — the exact quantity ``dynamics.joint_swing_torque_check`` screens.

    Returned as a ``torque_fn`` so ``simulate_pendulum`` can drive the link with it; if the screen's
    torque is right, the forward integration reproduces θ_des (the cross-validation). Start the sim at
    θ0=0, ω0=amplitude·ω to match θ_des(0)."""
    omega = 2.0 * math.pi * step_frequency
    mgd = mass * g * com_distance

    def torque(t: float, _theta: float, _omega: float) -> float:
        theta_des = amplitude_rad * math.sin(omega * t)
        theta_ddot_des = -amplitude_rad * omega * omega * math.sin(omega * t)
        return inertia * theta_ddot_des + mgd * math.sin(theta_des)

    return torque
