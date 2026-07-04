"""Auto-selection of physics checks from a Specification — the spec→gate wiring.

GATE δ-physics (physics_validation.py) runs a list of declared ``PhysicsCheck``s. This
module is what BUILDS that list from a Specification, so the gate selects its own checks
instead of being handed them. It is the deterministic, LLM-free analogue of the
derivation system: where a Derivation references quantity_ids by name, a ``CheckRecipe``
references quantities by their DECLARED ``measurand`` tag — the same explicit, non-inferred
link GATE γ C-17 already uses to prove two quantities cannot contradict.

How it works: each recipe declares a TRIGGER measurand (the presence of which means the
design has that physics — e.g. ``"shaft.torque"`` means there is a shaft in torsion) and
the measurand+unit each validator input must be resolved from. ``select_physics_checks``:

  • skips a recipe whose trigger is absent — the design simply has no such physics (no
    check, no gap: silence is correct here);
  • emits a ready ``PhysicsCheck`` when the trigger is present and EVERY input resolves —
    converting each quantity to the unit the validator expects (sound unit conversion via
    units.py, not a silent magnitude guess);
  • surfaces a GAP when the trigger is present but an input is missing, dimensionally
    incompatible, or in an opaque unit — an indicated-but-unrunnable check is reported,
    never silently dropped and never fed a wrong-unit number.

So the selection is honest by construction: a physics concern the spec declares either
becomes a real, unit-correct check or an explicit gap. The gate then runs the checks; the
gaps travel alongside, exactly as the spec gates surface what they could not certify.
Offline, pure functions, no model calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .core.errors import UnitError
from .core.state import Quantity, Specification
from .core.interfaces import GateResult
from .physics_validation import PhysicsCheck, gate_delta_physics
from .verification.units import parse_unit, unit_scale

# Phase 1+ integration point:
# Standard closed-form expressions for many recipes live in the FormulaRegistry.
# Use `from gen.formulas import FormulaRegistry` to look up provenance-backed
# expressions for a given trigger (e.g. for "column buckling" use Euler formula
# registered from CODATA/DLMF + verified).
# This does not change numeric evaluation — it adds source traceability.


@dataclass(frozen=True)
class CheckRecipe:
    """How to build one PhysicsCheck from a spec's measurand-tagged quantities.

    `name`       human label for the emitted check.
    `validator`  a key in physics_validation.VALIDATORS.
    `trigger`    a measurand whose presence indicates this physics applies.
    `inputs`     validator-kwarg name -> (measurand, expected_unit) to resolve+convert.
                 All must resolve or the check becomes a gap (honest).
    `extra`      fixed non-quantity kwargs (config the validator needs, e.g. an end
                 condition or a wall model) — declared defaults, refined later from
                 spec Decisions. Passed verbatim to validator.
    `optional_inputs`  like `inputs` but missing measurand does not gap; falls back to 0.0
                       (for e.g. radiation_dose_sv which is optional for the balance but
                       must be mapped from spec when present to be non-decorative).
    """

    name: str
    validator: str
    trigger: str
    inputs: dict[str, tuple[str, str]]
    extra: dict = field(default_factory=dict)
    optional_inputs: dict[str, tuple[str, str]] = field(default_factory=dict)


# The catalog: which checks the engine knows how to assemble from declared measurands.
# Extensible — a new validator becomes auto-selectable by adding a recipe here.
RECIPES: list[CheckRecipe] = [
    CheckRecipe(
        name="shaft torsion", validator="torsion", trigger="shaft.torque",
        inputs={
            "torque": ("shaft.torque", "N*mm"),
            "diameter": ("shaft.diameter", "mm"),
            "length": ("shaft.length", "mm"),
            "shear_modulus_g": ("material.shear_modulus", "MPa"),
            "shear_strength": ("material.shear_strength", "MPa"),
        },
    ),
    CheckRecipe(
        name="fatigue (Goodman)", validator="fatigue", trigger="fatigue.stress_amplitude",
        inputs={
            "stress_amplitude": ("fatigue.stress_amplitude", "MPa"),
            "mean_stress": ("fatigue.mean_stress", "MPa"),
            "uts": ("material.uts", "MPa"),
            "endurance": ("material.endurance_limit", "MPa"),
        },
    ),
    CheckRecipe(
        name="column buckling", validator="buckling", trigger="column.axial_load",
        inputs={
            "applied_load": ("column.axial_load", "N"),
            "e_modulus": ("material.elastic_modulus", "MPa"),
            "inertia": ("column.second_moment_area", "mm^4"),
            "length": ("column.length", "mm"),
            "area": ("column.cross_section_area", "mm^2"),
            "yield_strength": ("material.yield_strength", "MPa"),
        },
        extra={"end_condition": "pinned-pinned"},
    ),
    CheckRecipe(
        name="pressure vessel", validator="pressure_vessel", trigger="vessel.pressure",
        inputs={
            "pressure": ("vessel.pressure", "MPa"),
            "r_inner": ("vessel.inner_radius", "mm"),
            "thickness": ("vessel.wall_thickness", "mm"),
            "yield_strength": ("material.yield_strength", "MPa"),
        },
        extra={"model": "thin"},
    ),
    CheckRecipe(
        name="resonance", validator="resonance", trigger="vibration.excitation_frequency",
        inputs={
            "first_natural_hz": ("vibration.first_natural_frequency", "Hz"),
            "excitation_hz": ("vibration.excitation_frequency", "Hz"),
        },
    ),
    CheckRecipe(
        name="notch fatigue", validator="notch_fatigue", trigger="notch.kt",
        inputs={
            "nominal_alternating_stress": ("notch.nominal_alternating_stress", "MPa"),
            "kt": ("notch.kt", "1"),
            "notch_radius": ("notch.radius", "mm"),
            "peterson_constant_a": ("material.peterson_constant", "mm"),
            "smooth_endurance_se": ("material.endurance_limit", "MPa"),
        },
    ),
    # ---- printability: design errors that only show up on the print bed ----
    CheckRecipe(
        name="bridge span", validator="bridge_span", trigger="feature.bridge_span",
        inputs={"span": ("feature.bridge_span", "mm")},
    ),
    CheckRecipe(
        name="FDM fit clearance", validator="fdm_fit_clearance",
        trigger="fit.clearance",
        inputs={"clearance": ("fit.clearance", "mm")},
        extra={"fit": "loose"},
    ),
    CheckRecipe(
        name="pin diameter", validator="pin_diameter", trigger="feature.pin_diameter",
        inputs={"diameter": ("feature.pin_diameter", "mm")},
    ),
    CheckRecipe(
        name="modeled thread", validator="thread_size",
        trigger="feature.thread_major_diameter",
        inputs={"major_diameter": ("feature.thread_major_diameter", "mm")},
    ),
    CheckRecipe(
        name="unsupported wall", validator="unsupported_wall",
        trigger="feature.unsupported_wall_thickness",
        inputs={"thickness": ("feature.unsupported_wall_thickness", "mm")},
    ),
    CheckRecipe(
        name="embossed detail", validator="emboss_detail",
        trigger="feature.emboss_width",
        inputs={"width": ("feature.emboss_width", "mm")},
        extra={"kind": "emboss"},
    ),
    CheckRecipe(
        name="layer adhesion (cross-layer load)", validator="layer_adhesion",
        trigger="print.stress_across_layers",
        inputs={
            "stress_across_layers": ("print.stress_across_layers", "MPa"),
            "base_strength": ("material.uts", "MPa"),
        },
    ),
    # ---- flight: the closed-form axes a multirotor lives or dies by ----
    CheckRecipe(
        name="rotor hover (momentum theory)", validator="rotor_hover",
        trigger="rotor.disk_area",
        inputs={
            "mass": ("vehicle.mass", "kg"),
            "rotor_disk_area": ("rotor.disk_area", "m^2"),
            "n_rotors": ("rotor.count", "1"),
            "max_total_thrust": ("rotor.max_total_thrust", "N"),
        },
    ),
    CheckRecipe(
        name="battery endurance", validator="battery_endurance",
        # the REQUIREMENT indicates the check, not the component — a spec can carry a
        # battery.capacity without any endurance requirement (e.g. a non-continuous-duty pack).
        trigger="flight.required_endurance",
        inputs={
            "capacity_wh": ("battery.capacity", "Wh"),
            "hover_power_w": ("flight.hover_power", "W"),
            "required_endurance_min": ("flight.required_endurance", "min"),
        },
    ),
    CheckRecipe(
        name="current budget (ESC + battery C)", validator="current_budget",
        trigger="battery.c_rating",
        inputs={
            "power_w": ("flight.max_power", "W"),
            "voltage_v": ("battery.voltage", "V"),
            "esc_limit_a": ("esc.current_limit", "A"),
            "battery_capacity_ah": ("battery.capacity_ah", "Ah"),
            "battery_c_rating": ("battery.c_rating", "1"),
        },
    ),
    CheckRecipe(
        name="attitude PD damping", validator="attitude_pd",
        trigger="control.attitude_kp",
        inputs={
            "inertia": ("vehicle.attitude_inertia", "kg*m^2"),
            "kp": ("control.attitude_kp", "N*m"),
            "kd": ("control.attitude_kd", "N*m*s"),
        },
    ),
    # ---- security: closed-form cryptographic sizing (NIST-anchored) ----
    CheckRecipe(
        name="nonce birthday bound", validator="birthday_bound",
        trigger="crypto.nonce_bits",
        inputs={
            "space_bits": ("crypto.nonce_bits", "1"),
            "n_uses": ("crypto.messages_per_key", "1"),
        },
    ),
    CheckRecipe(
        name="symmetric key strength", validator="key_security",
        trigger="crypto.symmetric_key_bits",
        inputs={"key_bits": ("crypto.symmetric_key_bits", "1")},
        extra={"mechanism": "symmetric"},
    ),
    CheckRecipe(
        name="RSA modulus strength", validator="key_security",
        trigger="crypto.rsa_modulus_bits",
        inputs={"key_bits": ("crypto.rsa_modulus_bits", "1")},
        extra={"mechanism": "rsa"},
    ),
    CheckRecipe(
        name="ECC key strength", validator="key_security",
        trigger="crypto.ecc_key_bits",
        inputs={"key_bits": ("crypto.ecc_key_bits", "1")},
        extra={"mechanism": "ecc"},
    ),
    CheckRecipe(
        name="GCM invocation budget", validator="gcm_invocation_budget",
        trigger="crypto.gcm_invocations",
        inputs={"n_invocations": ("crypto.gcm_invocations", "1")},
    ),
    # ---- robot: humanoid kinematics / actuation / onboard-compute sizing screens ----
    CheckRecipe(
        name="arm reach (2R workspace)", validator="reach", trigger="arm.target_x",
        inputs={
            "l1": ("arm.link1_length", "m"),
            "l2": ("arm.link2_length", "m"),
            "x": ("arm.target_x", "m"),
            "y": ("arm.target_y", "m"),
        },
    ),
    CheckRecipe(
        name="balance (ZMP in support polygon)", validator="zmp_balance", trigger="balance.com_x",
        inputs={
            "com_x": ("balance.com_x", "m"),
            "com_z": ("balance.com_height", "m"),
            "support_min_x": ("balance.support_min_x", "m"),
            "support_max_x": ("balance.support_max_x", "m"),
        },
    ),
    CheckRecipe(
        name="electric joint actuator (torque-speed)", validator="electric_actuator",
        trigger="actuator.joint_torque",
        inputs={
            "joint_torque": ("actuator.joint_torque", "N*m"),
            "joint_speed": ("actuator.joint_speed", "rad/s"),
            "motor_stall_torque": ("motor.stall_torque", "N*m"),
            "motor_noload_speed": ("motor.noload_speed", "rad/s"),
            "gear_ratio": ("drivetrain.gear_ratio", "1"),
            "efficiency": ("drivetrain.efficiency", "1"),
        },
    ),
    CheckRecipe(
        name="hydraulic cylinder force", validator="hydraulic_cylinder",
        trigger="hydraulic.pressure",
        inputs={
            "pressure": ("hydraulic.pressure", "Pa"),
            "bore_area": ("hydraulic.bore_area", "m^2"),
            "required_force": ("hydraulic.required_force", "N"),
        },
    ),
    CheckRecipe(
        name="hydraulic flow", validator="hydraulic_flow", trigger="hydraulic.piston_velocity",
        inputs={
            "bore_area": ("hydraulic.bore_area", "m^2"),
            "piston_velocity": ("hydraulic.piston_velocity", "m/s"),
            "pump_flow": ("hydraulic.pump_flow", "m^3/s"),
        },
    ),
    CheckRecipe(
        name="compute throughput budget", validator="compute_budget",
        trigger="compute.workload_tops",
        inputs={
            "workload_tops": ("compute.workload_tops", "1"),
            "chip_tops": ("compute.chip_tops", "1"),
            "utilisation_max": ("compute.utilisation", "1"),
        },
    ),
    CheckRecipe(
        name="inference power", validator="inference_power",
        trigger="compute.efficiency_tops_per_w",
        inputs={
            "workload_tops": ("compute.workload_tops", "1"),
            "efficiency_tops_per_w": ("compute.efficiency_tops_per_w", "1"),
            "power_budget_w": ("compute.power_budget", "W"),
        },
    ),
    CheckRecipe(
        name="inference latency (control loop)", validator="inference_latency",
        trigger="compute.inference_ops",
        inputs={
            "inference_ops": ("compute.inference_ops", "1"),
            "throughput_ops_per_s": ("compute.throughput_ops_per_s", "1"),
            "control_period_s": ("control.period", "s"),
        },
    ),
    CheckRecipe(
        name="data bus bandwidth", validator="bus_bandwidth", trigger="bus.sample_rate",
        inputs={
            "n_devices": ("bus.n_devices", "1"),
            "bytes_per_sample": ("bus.bytes_per_sample", "1"),
            "sample_rate_hz": ("bus.sample_rate", "1/s"),
            "bus_bitrate_bps": ("bus.bitrate", "1/s"),
        },
    ),
    CheckRecipe(
        name="data bus poll-cycle latency", validator="bus_latency", trigger="bus.bitrate",
        inputs={
            "n_devices": ("bus.n_devices", "1"),
            "bytes_per_sample": ("bus.bytes_per_sample", "1"),
            "bus_bitrate_bps": ("bus.bitrate", "1/s"),
            "control_period_s": ("control.period", "s"),
        },
    ),
    # ---- robot dynamics: balance + actuation OVER a gait cycle, not one static pose ----
    CheckRecipe(
        name="swing resonance (natural leg cadence)", validator="swing_resonance",
        trigger="limb.inertia",
        inputs={
            "inertia": ("limb.inertia", "kg*m^2"),
            "mass": ("limb.mass", "kg"),
            "com_distance": ("limb.com_distance", "m"),
            "step_frequency": ("gait.step_frequency", "Hz"),
        },
    ),
    CheckRecipe(
        name="dynamic balance (ZMP over the gait cycle)", validator="zmp_dynamic",
        trigger="gait.step_frequency",
        inputs={
            "com_height": ("balance.com_height", "m"),
            "com_amplitude": ("gait.com_amplitude", "m"),
            "step_frequency": ("gait.step_frequency", "Hz"),
            "support_min_x": ("balance.support_min_x", "m"),
            "support_max_x": ("balance.support_max_x", "m"),
            "com_offset": ("balance.com_x", "m"),
        },
    ),
    CheckRecipe(
        name="swing joint torque (inverse dynamics over the swing)", validator="joint_swing_torque",
        trigger="swing.amplitude",
        inputs={
            "inertia": ("limb.inertia", "kg*m^2"),
            "mass": ("limb.mass", "kg"),
            "com_distance": ("limb.com_distance", "m"),
            "amplitude_rad": ("swing.amplitude", "rad"),
            "step_frequency": ("gait.step_frequency", "Hz"),
            "available_torque": ("actuator.available_torque", "N*m"),
        },
    ),
    # ---- space multi-physics (vacuum radiation dominant, for habitats/radiators/TPS) ----
    CheckRecipe(
        name="vacuum radiation balance (space thermal)", validator="vacuum_radiation_balance",
        trigger="thermal.radiation_absorbed",
        inputs={
            "absorbed_solar_w": ("thermal.radiation_absorbed", "W"),
            "epsilon": ("material.emissivity", "1"),
            "area_m2": ("surface.area", "m^2"),
            "t_k": ("thermal.temperature", "K"),
        },
        extra={
            "designed_as_sink_or_source": False,  # explicit design flag for non-equilibrium (eclipse sinks etc.)
        },
        optional_inputs={
            # dose mapped from spec when present → real (non-echo) in validator + limit check
            "radiation_dose_sv": ("radiation.total_ionizing_dose", "Sv"),
        },
    ),
]


def _measurand_map(spec: Specification) -> dict[str, Quantity]:
    """Index a spec's quantities by their declared measurand (first wins; GATE γ C-17
    guarantees same-measurand quantities agree, so the choice is immaterial)."""
    out: dict[str, Quantity] = {}
    for q in spec.quantities:
        if q.measurand and q.measurand not in out:
            out[q.measurand] = q
    return out


def _resolve(by_measurand: dict[str, Quantity], measurand: str, unit: str):
    """Return (value_in_`unit`, None) or (None, reason). Converts soundly via units.py;
    refuses (reason) on a missing quantity, a dimension mismatch, or an opaque unit."""
    q = by_measurand.get(measurand)
    if q is None:
        return None, f"keine Größe mit measurand {measurand!r}"
    try:
        if parse_unit(q.unit) != parse_unit(unit):
            return None, f"{measurand}: Einheit {q.unit!r} ist nicht dimensionsgleich zu {unit!r}"
        scale_from, scale_to = unit_scale(q.unit), unit_scale(unit)
    except UnitError as exc:
        return None, f"{measurand}: {exc}"
    if scale_from is None or scale_to is None:
        return None, f"{measurand}: opake Einheit {q.unit!r} — Umrechnung verweigert"
    return q.value * scale_from / scale_to, None


def select_physics_checks(spec: Specification) -> tuple[list[PhysicsCheck], list[str]]:
    """Build the applicable physics checks from a Specification's measurand-tagged
    quantities.

    Returns ``(checks, gaps)``: `checks` are ready ``PhysicsCheck``s (inputs resolved and
    unit-converted); `gaps` describe physics that is INDICATED (trigger present) but cannot
    be run (a missing/incompatible/opaque input), so an unrunnable check is surfaced rather
    than dropped. A recipe whose trigger is absent contributes neither. Deterministic.

    optional_inputs on CheckRecipe are resolved when present (enables real mapping e.g.
    radiation_dose_sv from "radiation.total_ionizing_dose" measurand without forcing gaps).
    """
    by_measurand = _measurand_map(spec)
    checks: list[PhysicsCheck] = []
    gaps: list[str] = []
    for recipe in RECIPES:
        if recipe.trigger not in by_measurand:
            continue                                # this physics is simply not present
        inputs = dict(recipe.extra)
        problems: list[str] = []
        for arg, (measurand, unit) in recipe.inputs.items():
            value, reason = _resolve(by_measurand, measurand, unit)
            if reason is not None:
                problems.append(reason)
            else:
                inputs[arg] = value
        # optional_inputs: map if present (for dose etc.); default 0.0 if absent (no gap)
        for arg, (measurand, unit) in recipe.optional_inputs.items():
            value, reason = _resolve(by_measurand, measurand, unit)
            if reason is None:
                inputs[arg] = value
            else:
                inputs[arg] = 0.0
        if problems:
            gaps.append(
                f"{recipe.name} ({recipe.validator}) ist durch {recipe.trigger!r} "
                f"indiziert, kann aber nicht laufen: {'; '.join(problems)}"
            )
        else:
            checks.append(PhysicsCheck(recipe.name, recipe.validator, inputs))
    return checks, gaps


def evaluate_spec_physics(spec: Specification) -> dict:
    """Full spec→verdict flow: select the applicable checks, run GATE δ-physics on them,
    and return ``{"gate": GateResult, "checks": [...], "gaps": [...]}``. The gate verdict
    reflects only the checks that could be assembled; `gaps` lists indicated-but-unrunnable
    physics (which a caller may treat as a soft fail / a reason to enrich the spec)."""
    checks, gaps = select_physics_checks(spec)
    gate: GateResult = gate_delta_physics(checks)
    return {"gate": gate, "checks": checks, "gaps": gaps}
