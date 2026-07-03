"""Actuation — sizing a joint's muscle: electric motor+gear OR hydraulic cylinder (δ-layer).

The kinematics axis says how much TORQUE a joint must hold (``static_joint_torques``); nothing yet
said whether the chosen actuator can DELIVER it. These are the closed-form screens a first-pass
drivetrain is sized with — the electric path (motor torque–speed curve reflected through a gearbox)
and the hydraulic path (cylinder force, flow, line losses) — honest engineering screens, not a
servo-controller simulation.

Each validator is verified against an exact anchor:

  * ``electric_actuator_check`` — a motor's linear torque–speed envelope τ = τ_stall·(1 − ω/ω_noload)
    reflected through a reduction N at efficiency η: the joint sees max torque τ_stall·N·η (at zero
    speed) and max speed ω_noload/N (at zero torque). The demand (τ, ω) must sit under that envelope.
  * ``hydraulic_cylinder_check`` — F = p·A_bore − F_friction (the piston force a pressure delivers).
  * ``hydraulic_flow_check`` — Q = A_bore·v_piston (the pump flow needed to drive the piston speed).
  * ``hydraulic_pressure_drop`` — Hagen–Poiseuille line loss Δp = 128·μ·L·Q/(π·d⁴), valid only in
    the LAMINAR regime — so it also returns the Reynolds number and a ``laminar_valid`` flag rather
    than silently applying the formula where it does not hold.

Offline, deterministic, no numpy. Honest boundary: each validator is a PEAK-capability steady-state
screen — necessary, NOT sufficient alone. It does not cover reflected inertia (J·α for acceleration),
continuous/thermal torque derating (stall torque is a PEAK rating; the I²R-limited continuous torque
is lower — see thermal.py), controller bandwidth, the double-acting RETRACT stroke (annulus area +
backpressure — ``bore_area``/``pressure`` here are the extend side), piston-rod buckling on long
strokes, load/speed/temperature-dependent efficiency (η is taken constant), minor (fitting/valve)
line losses, or turbulent flow.
"""

from __future__ import annotations

import math


def electric_actuator_check(
    joint_torque: float,
    joint_speed: float,
    motor_stall_torque: float,
    motor_noload_speed: float,
    gear_ratio: float,
    efficiency: float = 0.85,
) -> dict:
    """Can an electric motor + reduction deliver the joint's (torque, speed) demand?

    A motor's torque falls linearly with speed: τ = τ_stall·(1 − ω/ω_noload). Through a reduction
    `gear_ratio` N at `efficiency` η the JOINT sees max torque τ_stall·N·η (at ω=0) and max speed
    ω_noload/N (at τ=0), with the envelope available_torque(ω) = max_torque·(1 − ω/max_speed).
    Returns ``{"max_joint_torque", "max_joint_speed", "available_torque", "safety_factor", "ok"}``;
    safety_factor = available_torque(joint_speed) / joint_torque. Note: stall torque is a PEAK
    rating — the thermally-limited CONTINUOUS torque is lower, so this is a peak-capability screen.
    Raises ValueError on non-positive motor ratings / gear ratio, an efficiency outside (0, 1], or
    negative demand."""
    if motor_stall_torque <= 0.0 or motor_noload_speed <= 0.0:
        raise ValueError("motor stall torque and no-load speed must be positive")
    if gear_ratio <= 0.0:
        raise ValueError("gear ratio must be positive")
    if not 0.0 < efficiency <= 1.0:
        raise ValueError("efficiency must be in (0, 1]")
    if joint_torque < 0.0 or joint_speed < 0.0:
        raise ValueError("joint torque and speed demand must be non-negative")

    max_joint_torque = motor_stall_torque * gear_ratio * efficiency
    max_joint_speed = motor_noload_speed / gear_ratio
    available = max_joint_torque * (1.0 - joint_speed / max_joint_speed)
    if joint_torque > 0.0:
        safety_factor = available / joint_torque
    else:
        safety_factor = float("inf")
    ok = joint_speed <= max_joint_speed and joint_torque <= available
    return {"max_joint_torque": max_joint_torque, "max_joint_speed": max_joint_speed,
            "available_torque": available, "safety_factor": safety_factor, "ok": ok}


def hydraulic_cylinder_check(
    pressure: float,
    bore_area: float,
    required_force: float,
    friction: float = 0.0,
) -> dict:
    """Does a hydraulic cylinder deliver the required force? F = pressure·bore_area − friction.

    `pressure` in Pa, `bore_area` in m², forces in N. This is the EXTEND stroke (full bore); a
    double-acting retract uses the smaller annulus area + rod-side backpressure, and piston-rod
    buckling on long strokes is not checked here. Returns ``{"force_available", "required_force",
    "safety_factor", "ok"}`` with safety_factor = force_available/required_force. Raises ValueError
    on non-positive pressure/area/required force or negative friction."""
    if pressure <= 0.0 or bore_area <= 0.0:
        raise ValueError("pressure and bore area must be positive")
    if required_force <= 0.0:
        raise ValueError("required force must be positive")
    if friction < 0.0:
        raise ValueError("friction must be non-negative")
    force_available = pressure * bore_area - friction
    safety_factor = force_available / required_force
    return {"force_available": force_available, "required_force": required_force,
            "safety_factor": safety_factor, "ok": force_available >= required_force}


def hydraulic_flow_check(bore_area: float, piston_velocity: float, pump_flow: float) -> dict:
    """Does the pump supply the flow the piston speed needs? Q_required = bore_area·piston_velocity.

    Areas in m², velocity in m/s, flows in m³/s. Returns ``{"flow_required", "pump_flow",
    "safety_factor", "ok"}`` with safety_factor = pump_flow/flow_required. Raises ValueError on
    non-positive area/velocity/pump flow."""
    if bore_area <= 0.0 or piston_velocity <= 0.0 or pump_flow <= 0.0:
        raise ValueError("bore area, piston velocity, and pump flow must be positive")
    flow_required = bore_area * piston_velocity
    safety_factor = pump_flow / flow_required
    return {"flow_required": flow_required, "pump_flow": pump_flow,
            "safety_factor": safety_factor, "ok": pump_flow >= flow_required}


def hydraulic_pressure_drop(
    flow: float,
    diameter: float,
    length: float,
    viscosity: float,
    density: float = 870.0,
) -> dict:
    """Laminar line pressure loss by Hagen–Poiseuille: Δp = 128·μ·L·Q / (π·d⁴).

    `flow` Q in m³/s, `diameter` d and `length` L in m, dynamic `viscosity` μ in Pa·s, `density`
    in kg/m³ (default ~hydraulic oil). The formula holds only in the LAMINAR regime, so the result
    also reports the Reynolds number Re = 4ρQ/(π·d·μ) and ``laminar_valid`` (Re < 2300) — the loss
    is NOT asserted where the flow is turbulent. Returns ``{"pressure_drop_pa", "reynolds",
    "laminar_valid"}``. Raises ValueError on non-positive inputs."""
    if flow <= 0.0 or diameter <= 0.0 or length <= 0.0 or viscosity <= 0.0 or density <= 0.0:
        raise ValueError("flow, diameter, length, viscosity, and density must be positive")
    pressure_drop = 128.0 * viscosity * length * flow / (math.pi * diameter**4)
    reynolds = 4.0 * density * flow / (math.pi * diameter * viscosity)
    return {"pressure_drop_pa": pressure_drop, "reynolds": reynolds,
            "laminar_valid": reynolds < 2300.0}
