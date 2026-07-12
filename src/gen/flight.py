"""Flight — the closed-form axes a multirotor lives or dies by (δ-layer).

The structural validators catch a frame that breaks; nothing yet caught a drone
that cannot LIFT, cannot stay in the air long enough, browns out its ESC/battery,
or wobbles because its attitude gains are wrong. These four axes are exactly the
closed forms a first-pass vehicle design is sized with — honest engineering
screens, not CFD and not a flight simulation.

Four validators (each verified against exact anchors in the tests):

  * ``rotor_hover_check`` — actuator-disk MOMENTUM THEORY: induced velocity
    v_i = sqrt(T/(2·ρ·A)), ideal induced power P_ideal = T·v_i ≡ T^(3/2)/sqrt(2·ρ·A)
    (the two forms are an algebraic identity, pinned to machine precision), real
    hover power P = P_ideal/FM with the figure of merit FM (rotors typically
    0.5–0.7), and the thrust-to-weight screen T/W ≥ 2 — the standard multirotor
    sizing rule (hover at ~half throttle, control authority in gusts).
  * ``battery_endurance_check`` — the energy budget: usable energy = capacity ×
    usable fraction (LiPo rule: never below 20 % — usable 0.8), endurance =
    E_usable / P_hover. Deterministic arithmetic; Peukert/temperature effects are
    declared out of scope.
  * ``current_budget_check`` — the electric budget that browns out builds:
    I = P/V must clear BOTH the ESC continuous rating and the battery's maximum
    continuous discharge I_max = C-rating × capacity[Ah] (the C-rating convention).
  * ``attitude_pd_check`` — the attitude loop as the standard 2nd-order system:
    a PD-controlled rigid axis I·θ̈ = −Kp·θ − Kd·θ̇ has natural frequency
    ωn = sqrt(Kp/I) and damping ratio ζ = Kd/(2·sqrt(Kp·I)); the classic design
    band is 0.4 ≤ ζ ≤ 0.8 (acceptable transient response). Linearized
    rigid-body hover, no motor/ESC lag — declared.

Units: this module is SI (kg, m, s, N, W, V, A, Ah, Wh — aerodynamics and
electrics live in SI, unlike the N-mm-MPa structural modules; the auto-select
recipes convert declared units soundly). Standard gravity g = 9.80665 m/s²,
ISA sea-level air density ρ = 1.225 kg/m³ as overridable defaults.

Honest boundary: momentum theory is the IDEAL lower bound on induced power made
real only through the measured-or-assumed figure of merit; it models hover, not
forward flight or gusts. The endurance is hover endurance. The PD check proves
the linearized loop's damping, not outdoor flight performance — tuning on the
vehicle remains real. A passed check is necessary, not sufficient.

Sources: momentum theory & figure of merit — J. G. Leishman, *Principles of
Helicopter Aerodynamics* (Cambridge), standard actuator-disk results; T/W ≥ 2:1
multirotor sizing rule and FM 0.5–0.7 — Tyto Robotics drone design guide /
standard builder practice; LiPo 80 % usable-capacity rule and the C-rating
convention I_max = C×Ah — standard LiPo guides (Oscar Liang; battery vendors);
2nd-order damping band 0.4–0.8 — K. Ogata, *Modern Control Engineering*
(transient-response design); ρ = 1.225 kg/m³ — ISA sea level.
"""

from __future__ import annotations

import math

#: Standard gravity [m/s²] (CGPM convention).
STANDARD_GRAVITY = 9.80665

#: ISA sea-level air density [kg/m³].
AIR_DENSITY_SEA_LEVEL = 1.225

#: Multirotor sizing rule: max thrust ≥ this × weight. 2.0 is the classic "hover at half throttle,
#: control authority in gusts" default — but the real-fleet calibration (2026-06-24, gen.aero) showed
#: a single universal 2.0 MIS-CLASSIFIES shipping drones at BOTH ends: it FALSE-FAILS the DJI Matrice
#: 350 RTK (max-gross T/W = 9.2 kg MTOW / 6.47 kg loaded = 1.42×, a survey drone that flies daily), and
#: is far too LAX for FPV/racing (real floor 8–14×). It is RETAINED as the unclassed default (a safe
#: middle), with the per-mission-class floors below as the calibrated replacement. See
#: ``min_thrust_weight_for_class`` and PHASE_DELTA / gen.aero.calibration.
MIN_THRUST_WEIGHT_RATIO = 2.0

#: CALIBRATED minimum thrust-to-weight floors per mission class, each grounded in the real-drone fleet
#: (gen.aero.drone_catalog): heavy/survey/agri hover + gentle profiles clear ≥1.3 (M350 1.42×); stable
#: consumer/cinematic photo/video ≥1.5 (hovers ~50–66 % throttle); small nano craft need ≥1.8 in gusts
#: (Crazyflie 2.25×); fpv/freestyle/racing ≥4.0 (aggressive maneuver — 2.0 would wrongly pass a sluggish
#: build). This replaces the single universal 2.0 the way the humanoid squat-hold fix replaced the
#: whole-leg-horizontal knee sizing: a one-design-point screen made class-correct against ground truth.
MIN_THRUST_WEIGHT_BY_CLASS: dict[str, float] = {
    "heavy": 1.3,
    "consumer": 1.5,
    "cinematic": 1.5,
    "nano": 1.8,
    "fpv": 4.0,
}

#: Typical hover figure of merit (sourced range 0.5–0.7; mid default).
DEFAULT_FIGURE_OF_MERIT = 0.6

#: LiPo rule: never discharge below 20 % — 80 % of capacity is usable.
LIPO_USABLE_FRACTION = 0.8

#: Classic 2nd-order transient-response design band for the damping ratio.
ZETA_DESIGN_MIN = 0.4
ZETA_DESIGN_MAX = 0.8


def induced_velocity(thrust: float, disk_area: float,
                     air_density: float = AIR_DENSITY_SEA_LEVEL) -> float:
    """Momentum-theory induced velocity v_i = sqrt(T/(2·ρ·A)) [m/s] at hover.

    Raises ValueError on non-positive disk area or air density, or negative
    thrust (a hover rotor pushes air down)."""
    if disk_area <= 0.0:
        raise ValueError("rotor disk area must be positive")
    if air_density <= 0.0:
        raise ValueError("air density must be positive")
    if thrust < 0.0:
        raise ValueError("thrust must be non-negative")
    return math.sqrt(thrust / (2.0 * air_density * disk_area))


def ideal_induced_power(thrust: float, disk_area: float,
                        air_density: float = AIR_DENSITY_SEA_LEVEL) -> float:
    """Ideal (momentum-theory) induced hover power P = T^(3/2)/sqrt(2·ρ·A) [W].

    Algebraically identical to T·v_i — the identity is pinned in the tests.
    This is the LOWER bound no real rotor beats; real power = ideal/FM."""
    return thrust * induced_velocity(thrust, disk_area, air_density)


def rotor_hover_check(
    mass: float,
    rotor_disk_area: float,
    n_rotors: float,
    max_total_thrust: float,
    figure_of_merit: float = DEFAULT_FIGURE_OF_MERIT,
    air_density: float = AIR_DENSITY_SEA_LEVEL,
    min_thrust_weight: float = MIN_THRUST_WEIGHT_RATIO,
) -> dict:
    """Can it lift — and with the standard control margin?

    Checks the multirotor sizing rule ``max_total_thrust / (m·g) ≥ 2`` and
    computes the real hover power from momentum theory + figure of merit
    (the number the battery check needs). Returns ``{"weight_n",
    "thrust_weight_ratio", "induced_velocity", "hover_power_w",
    "safety_factor", "ok"}`` with safety_factor = ratio / min_thrust_weight.
    Raises ValueError on non-positive mass / rotor count / disk area, an FM
    outside (0, 1], or a negative thrust."""
    if mass <= 0.0:
        raise ValueError("vehicle mass must be positive")
    if n_rotors < 1.0:
        raise ValueError("rotor count must be at least 1")
    if not 0.0 < figure_of_merit <= 1.0:
        raise ValueError("figure of merit must be in (0, 1]")
    if min_thrust_weight <= 0.0:
        raise ValueError("minimum thrust-to-weight must be positive")
    # A negative max thrust is physically meaningless and would silently yield a
    # negative thrust-to-weight ratio (and misleading safety_factor) instead of
    # failing loud. 0.0 is allowed: a meaningful evaluable case (ratio 0, ok=False),
    # matching induced_velocity's non-negative thrust convention.
    if max_total_thrust < 0.0:
        raise ValueError("max total thrust must be non-negative")
    weight = mass * STANDARD_GRAVITY
    ratio = max_total_thrust / weight
    per_rotor_hover_thrust = weight / n_rotors
    v_i = induced_velocity(per_rotor_hover_thrust, rotor_disk_area, air_density)
    p_ideal_total = n_rotors * per_rotor_hover_thrust * v_i
    hover_power = p_ideal_total / figure_of_merit
    safety_factor = ratio / min_thrust_weight
    return {
        "weight_n": weight,
        "thrust_weight_ratio": ratio,
        "induced_velocity": v_i,
        "hover_power_w": hover_power,
        "safety_factor": safety_factor,
        "ok": ratio >= min_thrust_weight,
    }


def min_thrust_weight_for_class(klass: str) -> float:
    """The CALIBRATED minimum thrust-to-weight floor for a mission class (the calibration fix).

    Returns the real-fleet-grounded floor from ``MIN_THRUST_WEIGHT_BY_CLASS``, or the unclassed
    ``MIN_THRUST_WEIGHT_RATIO`` (2.0) default for an unknown class. Pass the result as
    ``rotor_hover_check(..., min_thrust_weight=...)`` to gate a real drone by its class rather than the
    one-size constant that false-fails survey drones and rubber-stamps sluggish racers. This is the
    single source of truth for the class→floor mapping, so the gate and any report agree."""
    return MIN_THRUST_WEIGHT_BY_CLASS.get(klass, MIN_THRUST_WEIGHT_RATIO)


def battery_endurance_check(
    capacity_wh: float,
    hover_power_w: float,
    required_endurance_min: float,
    usable_fraction: float = LIPO_USABLE_FRACTION,
) -> dict:
    """Does the usable energy carry the required hover time?

    endurance [min] = capacity·usable_fraction / hover_power · 60. Returns
    ``{"usable_wh", "endurance_min", "required_min", "safety_factor", "ok"}``
    with safety_factor = endurance / required. Raises ValueError on
    non-positive capacity/power/required time or a usable fraction outside
    (0, 1]."""
    if capacity_wh <= 0.0:
        raise ValueError("battery capacity must be positive")
    if hover_power_w <= 0.0:
        raise ValueError("hover power must be positive")
    if required_endurance_min <= 0.0:
        raise ValueError("required endurance must be positive")
    if not 0.0 < usable_fraction <= 1.0:
        raise ValueError("usable fraction must be in (0, 1]")
    usable = capacity_wh * usable_fraction
    endurance = usable / hover_power_w * 60.0
    safety_factor = endurance / required_endurance_min
    return {
        "usable_wh": usable,
        "endurance_min": endurance,
        "required_min": required_endurance_min,
        "safety_factor": safety_factor,
        "ok": endurance >= required_endurance_min,
    }


def current_budget_check(
    power_w: float,
    voltage_v: float,
    esc_limit_a: float,
    battery_capacity_ah: float,
    battery_c_rating: float,
) -> dict:
    """Does the worst-case current clear BOTH the ESC and the battery?

    I = P/V; the battery's maximum continuous discharge is C·capacity[Ah]
    (the C-rating convention). Returns ``{"current_a", "battery_max_a",
    "esc_limit_a", "safety_factor", "ok"}`` — safety_factor is the SMALLER of
    the two margins (the one that browns out first). Raises ValueError on
    non-positive voltage, power, ESC limit, capacity, or C-rating."""
    if power_w <= 0.0:
        raise ValueError("power must be positive")
    if voltage_v <= 0.0:
        raise ValueError("voltage must be positive")
    if esc_limit_a <= 0.0:
        raise ValueError("ESC current limit must be positive")
    if battery_capacity_ah <= 0.0:
        raise ValueError("battery capacity must be positive")
    if battery_c_rating <= 0.0:
        raise ValueError("battery C-rating must be positive")
    current = power_w / voltage_v
    battery_max = battery_c_rating * battery_capacity_ah
    sf_esc = esc_limit_a / current
    sf_batt = battery_max / current
    safety_factor = min(sf_esc, sf_batt)
    return {
        "current_a": current,
        "battery_max_a": battery_max,
        "esc_limit_a": esc_limit_a,
        "safety_factor": safety_factor,
        "ok": safety_factor >= 1.0,
    }


def attitude_pd_check(
    inertia: float,
    kp: float,
    kd: float,
    zeta_min: float = ZETA_DESIGN_MIN,
    zeta_max: float = ZETA_DESIGN_MAX,
) -> dict:
    """Is the attitude loop damped like a textbook says it should be?

    A PD-controlled rigid axis ``I·θ̈ = −Kp·θ − Kd·θ̇`` is the standard
    2nd-order system with ωn = sqrt(Kp/I) and ζ = Kd/(2·sqrt(Kp·I)); the
    classic design band is zeta_min ≤ ζ ≤ zeta_max (0.4–0.8: acceptably fast,
    acceptably small overshoot). A negative or zero Kd yields ζ ≤ 0
    (undamped/unstable) and honestly fails rather than raising — it is a
    meaningful, evaluable gain choice. Returns ``{"natural_frequency_rad_s",
    "damping_ratio", "zeta_min", "zeta_max", "ok"}``. Raises ValueError on
    non-positive inertia or Kp (no restoring loop to evaluate) or an empty/
    invalid design band."""
    if inertia <= 0.0:
        raise ValueError("inertia must be positive")
    if kp <= 0.0:
        raise ValueError("Kp must be positive (no restoring torque otherwise)")
    if not 0.0 < zeta_min < zeta_max:
        raise ValueError("damping band must satisfy 0 < zeta_min < zeta_max")
    omega_n = math.sqrt(kp / inertia)
    zeta = kd / (2.0 * math.sqrt(kp * inertia))
    return {
        "natural_frequency_rad_s": omega_n,
        "damping_ratio": zeta,
        "zeta_min": zeta_min,
        "zeta_max": zeta_max,
        "ok": zeta_min <= zeta <= zeta_max,
    }
