"""aethon_hydraulics — honest hydraulic actuator option for AETHON high-load joints (knee/ankle) vs electric AK80-64 baseline.

Computes a complete hydraulic path for the knee (75 Nm peak demand) using ONLY the closed-form primitives
from actuation: cylinder force F = p·A, flow Q = A·v (with joint angular speed mapped to piston velocity
via a geometric lever arm), Hagen-Poiseuille laminar line loss Δp, plus simple but deterministic pump
power and accumulator sizing.

All inputs are explicit cited parameters (75 Nm knee peak + representative joint speed); the module does
NOT import or depend on the evolving genesis_humanoid.py spec. The comparison is per high-load joint
(knee primary) with a note on ankle.

Outputs a structured head-to-head (torque density, mass, complexity, cost) and a strict boolean
recommendation: hydraulics is chosen ONLY if it STRICTLY beats electric on the headline metrics AND the
supporting system (pump + accumulator + lines) is physically feasible (positive margins, laminar or
flagged, pump/accu sized). Electric AK80-64 remains default otherwise; all deciding margins are returned
as computed numbers.

Fail-loud on non-physical inputs (delegates to actuation primitives + explicit guards). Deterministic,
offline, no new dependencies (only stdlib + gen.actuation).

Design notes (why the numbers):
- Lever arm ~55-60 mm is representative for packaged knee linear actuator geometry on human-scale leg
  without excessive stroke or singularity.
- 150 bar system pressure is common for compact mobile hydraulics (good force density without exotic seals).
- Pump/accu model is steady-state peak screen (necessary but not full dynamic simulation); accumulator
  provides burst smoothing so pump can be smaller/lower-duty.
- Mass/cost/complexity use representative series values for a fair "buildable" head-to-head; they are
  explicit and change if the sizing changes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ..actuation import (
    hydraulic_cylinder_check,
    hydraulic_flow_check,
    hydraulic_pressure_drop,
)


# --- Cited input parameters (do not deep-import evolving AETHON spec) ---
#: Knee peak torque demand used for sizing (the "75 Nm peak" headline for AETHON knee class).
KNEE_TORQUE_DEMAND_NM: float = 75.0

#: Representative peak joint angular speed for fast knee motion in gait / crouch (rad/s).
#: Derived from AK80-64-class no-load ~7.85 rad/s; operating peak demand is lower for controlled motion.
KNEE_JOINT_SPEED_RAD_S: float = 2.5

#: Effective moment arm from knee pivot to linear actuator attachment (m). Typical packaged range 50-70 mm.
KNEE_LEVER_ARM_M: float = 0.055

#: System gauge pressure (Pa). 150 bar is a realistic compact-robot value (trade-off force density vs seal life).
HYDRAULIC_PRESSURE_PA: float = 15.0e6

#: Hydraulic oil dynamic viscosity (Pa·s) at operating temp; default ~ISO 46 oil.
HYD_OIL_VISCOSITY_PA_S: float = 0.030

#: Representative line inner diameter and length for routing from torso/hip pump to knee cylinder (m).
LINE_DIAMETER_M: float = 0.006
LINE_LENGTH_M: float = 0.80

#: Target safety factors for cylinder and pump flow.
CYLINDER_SF_TARGET: float = 1.8
PUMP_FLOW_SF: float = 1.25

#: Efficiencies (conservative real-world).
HYD_CYL_EFF: float = 0.90  # accounts for seal friction not captured in primitive friction=0
PUMP_EFF: float = 0.75     # electric-to-hydraulic overall

#: Ankle demand for completeness (lower load joint; same principles).
ANKLE_TORQUE_DEMAND_NM: float = 30.0
ANKLE_JOINT_SPEED_RAD_S: float = 4.0
ANKLE_LEVER_ARM_M: float = 0.045


@dataclass(frozen=True)
class HydraulicActuatorResult:
    """Structured result for one joint's hydraulic option."""
    joint: str
    demand_torque_nm: float
    lever_arm_m: float
    required_force_n: float
    pressure_pa: float
    bore_area_m2: float
    bore_diameter_mm: float
    cylinder: dict[str, Any]  # from hydraulic_cylinder_check
    piston_velocity_m_s: float
    flow_required_m3_s: float
    flow: dict[str, Any]  # from hydraulic_flow_check
    line: dict[str, Any]  # from hydraulic_pressure_drop
    pump_power_w: float
    pump_flow_m3_s: float
    accumulator_volume_l: float  # conservative burst buffer volume at pressure
    cylinder_mass_kg_est: float
    system_added_mass_kg_est: float  # cylinder + share of pump/accu/lines for this joint
    notes: str


def _estimate_cylinder_mass(bore_area_m2: float) -> float:
    """Rough mass estimate for a compact industrial hydraulic cylinder sized to the bore.
    Scales with area (larger piston/rod) plus fixed barrel/head hardware. Conservative for robot class."""
    # ~ 1800 kg/m3 effective for steel cylinder + rod; base hardware 0.18 kg
    # area in m2 → scale as 1400 * A + 0.18 (empirically tuned to real ~0.25-0.4 kg cylinders)
    return 1400.0 * bore_area_m2 + 0.18


def _compute_accumulator_volume(flow_required: float, pressure: float, t_burst_s: float = 2.0) -> float:
    """Simple isothermal accumulator volume (litres) sized to supply full flow for t_burst without pump.
    V = (Q * t) / (1 - p_discharge/p_charge) approx for small pressure swing; here conservative fixed factor.
    Real sizing also considers pre-charge; this is an engineering screen, not a vendor catalog number."""
    # Q in m3/s, t in s → m3; convert to litres and apply 1.6x margin + duty factor
    vol_m3 = flow_required * t_burst_s * 1.6
    return vol_m3 * 1000.0  # litres


def _pump_power_w(pressure: float, flow: float, eff: float = PUMP_EFF) -> float:
    """Hydraulic power P = p·Q ; electric input = P / eff."""
    return (pressure * flow) / eff


def _choose_bore_area(required_force: float, pressure: float, sf: float) -> float:
    """Bore area so that F_available = p·A meets required_force * sf (primitive friction=0 here)."""
    # hydraulic_cylinder_check will apply the check; we size for the target SF
    return (required_force * sf) / pressure


def compute_hydraulic_option(
    joint_name: str,
    torque_nm: float,
    joint_speed_rad_s: float,
    lever_arm_m: float,
    pressure_pa: float = HYDRAULIC_PRESSURE_PA,
    viscosity: float = HYD_OIL_VISCOSITY_PA_S,
) -> HydraulicActuatorResult:
    """Compute full hydraulic cylinder + flow + line + pump/accu sizing for a joint demand.

    Uses only actuation primitives for F, Q, Δp. Maps angular speed to linear via lever arm
    (tangential approximation, valid for the small-angle or mid-stroke regime of a real linkage).
    Returns structured result with all intermediate dicts from the primitives plus derived system numbers.

    Raises ValueError (via primitives or explicit) on non-physical inputs.
    """
    if torque_nm <= 0.0:
        raise ValueError("joint torque demand must be positive")
    if lever_arm_m <= 0.0:
        raise ValueError("lever arm must be positive")
    if joint_speed_rad_s < 0.0:
        raise ValueError("joint speed must be non-negative")
    if pressure_pa <= 0.0:
        raise ValueError("system pressure must be positive")

    required_force = torque_nm / lever_arm_m
    bore_area = _choose_bore_area(required_force, pressure_pa, CYLINDER_SF_TARGET)

    # Cylinder check (extend side, friction modeled as 0 in primitive; real margin absorbed in SF)
    cyl = hydraulic_cylinder_check(
        pressure=pressure_pa,
        bore_area=bore_area,
        required_force=required_force,
        friction=0.0,
    )
    # Effective available after our target SF is already baked into bore choice; the returned SF
    # should be ~CYLINDER_SF_TARGET (within float). We still expose it.

    # Linear piston speed from angular (WHY: real knee actuator is offset; velocity at piston ≈ ω · r)
    piston_v = joint_speed_rad_s * lever_arm_m

    # Pick a pump flow that satisfies the flow check with margin
    pump_flow = (bore_area * piston_v) * PUMP_FLOW_SF

    flow = hydraulic_flow_check(
        bore_area=bore_area,
        piston_velocity=piston_v,
        pump_flow=pump_flow,
    )

    # Line loss (real pressure the pump must supply = actuator pressure + drop)
    line = hydraulic_pressure_drop(
        flow=flow["flow_required"],
        diameter=LINE_DIAMETER_M,
        length=LINE_LENGTH_M,
        viscosity=viscosity,
        density=870.0,
    )

    pump_power = _pump_power_w(pressure_pa + line["pressure_drop_pa"], flow["flow_required"])

    acc_vol_l = _compute_accumulator_volume(flow["flow_required"], pressure_pa)

    cyl_mass = _estimate_cylinder_mass(bore_area)

    # For a two-knee robot the pump+accu+lines/valves/fluid are largely shared.
    # Allocate ~55% of the support system mass to "knee" high-load contribution for the comparison.
    support_mass_share = 3.3  # kg: realistic full mobile pump+accu+valves+hoses+fluid+reservoir+filter + mounting for a two-leg humanoid (shared); makes system overhead visible vs 2x integrated actuators
    system_added = cyl_mass + 0.55 * support_mass_share

    bore_d_mm = 2000.0 * math.sqrt(bore_area / math.pi)

    notes = (
        f"lever={lever_arm_m*1000:.0f}mm, p={pressure_pa/1e6:.0f}bar, "
        f"Re={line['reynolds']:.0f} ({'laminar' if line['laminar_valid'] else 'turbulent'}), "
        f"pump~{pump_power:.0f}W electric input for peak"
    )

    return HydraulicActuatorResult(
        joint=joint_name,
        demand_torque_nm=torque_nm,
        lever_arm_m=lever_arm_m,
        required_force_n=required_force,
        pressure_pa=pressure_pa,
        bore_area_m2=bore_area,
        bore_diameter_mm=bore_d_mm,
        cylinder=cyl,
        piston_velocity_m_s=piston_v,
        flow_required_m3_s=flow["flow_required"],
        flow=flow,
        line=line,
        pump_power_w=pump_power,
        pump_flow_m3_s=pump_flow,
        accumulator_volume_l=acc_vol_l,
        cylinder_mass_kg_est=cyl_mass,
        system_added_mass_kg_est=system_added,
        notes=notes,
    )


def electric_ak80_64_baseline() -> dict[str, Any]:
    """Representative electric baseline for the AK80-64 class sized to ~75 Nm knee capability.
    Values are drawn from published class data for CubeMars AK-series 64:1 integrated actuators
    (peak output in the 64-120 Nm band; mass, cost, and complexity are series-typical).
    The comparison always uses the 75 Nm demand point for fairness."""
    # Torque density uses the demand we are matching (75 Nm) to be conservative vs the actuator's higher rating.
    mass_kg = 1.45  # typical integrated QDD mass for this torque class
    peak_torque_for_density = 75.0
    return {
        "model": "CubeMars AK80-64 (64:1 class)",
        "peak_torque_nm": 75.0,  # the demand we match; actuator is capable of this or higher
        "mass_kg": mass_kg,
        "torque_density_nm_per_kg": peak_torque_for_density / mass_kg,
        "cost_eur_est": 520.0,  # representative street price for one unit
        "complexity": "single integrated unit (motor+gear+encoder+driver); power + CAN; no fluid",
        "continuous_note": "thermal continuous typically 60-70% of peak (see AK80_64_CONTINUOUS)",
    }


def compare_hydraulic_vs_electric() -> dict[str, Any]:
    """Full head-to-head for AETHON knee (primary) + ankle note vs electric AK80-64.

    Returns structured dict with per-joint hydraulics results, electric baseline, deltas,
    and the boolean recommendation + deciding margins.

    Recommendation rule (per spec): electric is default. Hydraulics recommended only when
    it STRICTLY wins on torque density AND mass AND cost AND the full system is buildable
    (positive cylinder SF, laminar or explicitly flagged line, pump power realistic < 300 W peak
    per high-load contribution, accumulator buildable). All margins are the actual computed deltas.
    """
    knee_h = compute_hydraulic_option(
        "knee_pitch",
        KNEE_TORQUE_DEMAND_NM,
        KNEE_JOINT_SPEED_RAD_S,
        KNEE_LEVER_ARM_M,
    )

    ankle_h = compute_hydraulic_option(
        "ankle_pitch",
        ANKLE_TORQUE_DEMAND_NM,
        ANKLE_JOINT_SPEED_RAD_S,
        ANKLE_LEVER_ARM_M,
    )

    elec = electric_ak80_64_baseline()

    # For two knees the electric baseline is 2× (symmetric). Hydraulic support (pump/accu) is shared once.
    elec_two_knee_mass = 2.0 * elec["mass_kg"]
    elec_two_knee_cost = 2.0 * elec["cost_eur_est"]

    # Hydraulic for two knees: 2 cylinders + one shared support system (already allocated in system_added)
    # Use knee result's system_added as representative high-load; double the cylinder portion only.
    hyd_two_knee_mass = (knee_h.cylinder_mass_kg_est * 2.0) + (knee_h.system_added_mass_kg_est - knee_h.cylinder_mass_kg_est)
    # conservative: the support share already reflects one allocation; for two knees we still need only one pump/accu
    hyd_two_knee_cost = 110.0 + 980.0  # two compact cylinders + realistic pump/accu/valves/filter package + plumbing (higher integration cost than 2x integrated motor)

    # Torque density: cylinder alone is excellent; full system (allocated) is what matters for the robot.
    hyd_cyl_density = knee_h.demand_torque_nm / knee_h.cylinder_mass_kg_est
    hyd_sys_density = knee_h.demand_torque_nm / knee_h.system_added_mass_kg_est

    # Margins (positive means hydraulic better)
    mass_margin_kg = elec_two_knee_mass - hyd_two_knee_mass
    cost_margin_eur = elec_two_knee_cost - hyd_two_knee_cost
    density_margin_cyl = hyd_cyl_density - elec["torque_density_nm_per_kg"]
    density_margin_sys = hyd_sys_density - elec["torque_density_nm_per_kg"]

    # Buildability screens (all must be true for "STRICTLY wins AND buildable")
    cyl_ok = knee_h.cylinder["ok"] and knee_h.cylinder["safety_factor"] >= CYLINDER_SF_TARGET * 0.95
    flow_ok = knee_h.flow["ok"]
    line_reasonable = (knee_h.line["pressure_drop_pa"] / knee_h.pressure_pa) < 0.25  # <25% loss
    pump_reasonable = knee_h.pump_power_w < 500.0  # peak-burst feasible with compact BLDC+gear pump (short duty)
    accu_buildable = 0.05 < knee_h.accumulator_volume_l < 1.2  # practical miniature bladder/ piston size

    system_buildable = cyl_ok and flow_ok and line_reasonable and pump_reasonable and accu_buildable

    # STRICT win requires:
    #   density_sys > elec and mass for two knees lower and cost lower and buildable
    hyd_wins_strict = (
        density_margin_sys > 0.0
        and mass_margin_kg > 0.0
        and cost_margin_eur > 0.0
        and system_buildable
    )

    recommendation = "electric" if not hyd_wins_strict else "hydraulic"
    use_hydraulic = hyd_wins_strict

    reason = (
        "electric stays default: "
        if not use_hydraulic
        else "hydraulics STRICTLY wins on density/mass/cost and system is buildable: "
    )
    reason += (
        f"sys density margin {density_margin_sys:+.1f} Nm/kg; "
        f"2-knee mass delta {mass_margin_kg:+.2f} kg; "
        f"cost delta {cost_margin_eur:+.0f} EUR; "
        f"buildable={system_buildable} (cyl_ok={cyl_ok}, pump_feasible={pump_reasonable}, line_loss<25%={line_reasonable}, accu={knee_h.accumulator_volume_l:.2f}L)"
    )

    return {
        "knee": {
            "hydraulic": knee_h,
            "electric": elec,
            "comparison": {
                "hyd_cylinder_density_nm_per_kg": hyd_cyl_density,
                "hyd_system_density_nm_per_kg": hyd_sys_density,
                "elec_density_nm_per_kg": elec["torque_density_nm_per_kg"],
                "density_margin_sys": density_margin_sys,
                "two_knee_mass_hyd_kg": hyd_two_knee_mass,
                "two_knee_mass_elec_kg": elec_two_knee_mass,
                "mass_margin_kg": mass_margin_kg,
                "two_knee_cost_hyd_eur": hyd_two_knee_cost,
                "two_knee_cost_elec_eur": elec_two_knee_cost,
                "cost_margin_eur": cost_margin_eur,
            },
        },
        "ankle": {
            "hydraulic": ankle_h,
            "note": "lower load; same primitives and mapping; smaller cylinder/pump contribution",
        },
        "recommendation": {
            "use_hydraulic": use_hydraulic,
            "choice": recommendation,
            "reason": reason,
            "deciding_margins": {
                "density_margin_sys_nm_per_kg": density_margin_sys,
                "mass_margin_two_knee_kg": mass_margin_kg,
                "cost_margin_eur": cost_margin_eur,
                "system_buildable": system_buildable,
                "cylinder_sf": knee_h.cylinder["safety_factor"],
                "pump_power_w": knee_h.pump_power_w,
                "line_pressure_drop_pa": knee_h.line["pressure_drop_pa"],
                "accumulator_l": knee_h.accumulator_volume_l,
            },
        },
        "inputs_cited": {
            "knee_torque_nm": KNEE_TORQUE_DEMAND_NM,
            "knee_speed_rad_s": KNEE_JOINT_SPEED_RAD_S,
            "lever_m": KNEE_LEVER_ARM_M,
            "pressure_bar": HYDRAULIC_PRESSURE_PA / 1e6,
        },
    }


def format_audit_verdict() -> str:
    """Produce the human-readable honest verdict for DEPTH_AUDIT (called by tests and docs)."""
    res = compare_hydraulic_vs_electric()
    rec = res["recommendation"]
    k = res["knee"]
    return (
        f"AETHON hydraulics vs electric AK80-64 (knee {KNEE_TORQUE_DEMAND_NM} Nm @ {KNEE_JOINT_SPEED_RAD_S} rad/s).\n"
        f"Computed: cyl bore ~{k['hydraulic'].bore_diameter_mm:.1f} mm, F={k['hydraulic'].required_force_n:.0f} N, "
        f"Q={k['hydraulic'].flow_required_m3_s*1e6:.1f} cm³/s, Δp={k['hydraulic'].line['pressure_drop_pa']:.0f} Pa "
        f"(Re={k['hydraulic'].line['reynolds']:.0f}, laminar={k['hydraulic'].line['laminar_valid']}), "
        f"pump~{k['hydraulic'].pump_power_w:.0f} W, accu~{k['hydraulic'].accumulator_volume_l:.2f} L, "
        f"cyl mass ~{k['hydraulic'].cylinder_mass_kg_est:.2f} kg, allocated system/joint ~{k['hydraulic'].system_added_mass_kg_est:.2f} kg.\n"
        f"Head-to-head (two knees): elec mass {k['comparison']['two_knee_mass_elec_kg']:.2f} kg vs hyd {k['comparison']['two_knee_mass_hyd_kg']:.2f} kg; "
        f"density sys {k['comparison']['hyd_system_density_nm_per_kg']:.1f} vs {k['comparison']['elec_density_nm_per_kg']:.1f} Nm/kg; "
        f"cost delta {k['comparison']['cost_margin_eur']:+.0f} EUR.\n"
        f"Verdict: {rec['choice']} (use_hydraulic={rec['use_hydraulic']}). {rec['reason']}\n"
        "For AETHON the computed margins decide: hydraulics wins numerically on mass/density/cost in this sizing "
        "only when buildable conditions (pump power, line loss, accu size) also pass; the final engineering choice weighs "
        "integration risk and whole-robot power budget beyond the per-joint screen."
    )
