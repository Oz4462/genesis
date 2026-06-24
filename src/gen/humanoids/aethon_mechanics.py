"""aethon_mechanics — AETHON's mechanical truth, computed through the REAL Genesis δ-physics validators.

The flagship spec (``genesis_humanoid.py``) declares AETHON's geometry, actuators and load paths and
gates them. This module is the deep ENGINEERING analysis BEHIND that spec: it computes — not asserts —
the numbers the spec is built on, using the same closed-form/continuum validators the δ gate uses, so
every figure here is reproducible and falsifiable, and the spec's evolution is driven by these findings
rather than by intuition.

Four analyses, each through an existing validator (no new physics is invented here):

  (1) STRUCTURE — for every load-bearing part (thigh / hip-pelvis / spine-torso / knee-shank) the real
      continuum 3-D FEM (``fem3d.solve_elasticity`` via :func:`fem3d.prismatic_bar_axial_response`) is
      driven under the part's explicit stance load path to read out the axial (crush/compression)
      stress, AND the closed-form Euler-Bernoulli bending stress at the mounting hole (the SAME
      ``structural.cantilever_bending_stress_formula`` + Kirsch Kt the spec gates) is computed; the
      GOVERNING mode (the larger stress) sets the safety factor. The continuum FEM reproduces σ=F/A to
      machine precision, so the axial reserve is a genuine solver output, not a constant.
      Honest boundary — grounded in arXiv:cond-mat/0502303 (dimension- and interface-dependent
      mechanical-failure thresholds in thin films): a printed thin wall fails BELOW its bulk strength
      at the layer interfaces, so the in-plane strength used here is the effective (already-derated)
      print strength and the FEM/closed-form screen is NECESSARY, not sufficient — a real bonded-layer
      coupon test is the declared remaining gap.

  (2) KINEMATICS / DYNAMICS — the worst static pose (deep single-leg squat) knee torque
      (``kinematics.knee_squat_hold_torque``), the 2R arm reach margin (``kinematics.reach_check``),
      the static ZMP balance (``kinematics.zmp_balance_check``) AND a representative DYNAMIC load case
      (the same ZMP screen with the gait's peak horizontal CoM acceleration), plus the planar arm
      gravity-hold torques (``kinematics.static_joint_torques``).

  (3) DRIVETRAIN — every actuated body joint checked against its real off-the-shelf actuator
      (CubeMars AK80-64 knee / AK70-10 arm / MyActuator RMD hips+ankles, the BOM parts): the knee
      through the full reflected torque-speed envelope (``actuation.electric_actuator_check``), every
      other joint through its published peak, for BOTH the worst static hold and the dynamic
      (inertial J·α augmented) demand, flagging each joint OVER-designed / UNDER-designed / matched.

  (4) MASS / INERTIA + SCALING LAWS — the per-segment mass budget, the leg-swing inertia
      (``mechanics_formulas.rod_inertia_about_end``), and a comparison of AETHON's knee against the
      real-robot scaling law (``scaling_laws.check_knee``) flagging the design within / over / under
      the fleet band.

Deterministic, offline, numpy only (the continuum FEM is the pure-numpy ``fem3d`` path — NO gmsh /
CalculiX is required, so this runs everywhere the gate runs). All pure functions take explicit numeric
inputs; :func:`compute_aethon_mechanics` lazily pulls AETHON's config to feed them (no import cycle).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..actuation import electric_actuator_check
from ..fem3d import prismatic_bar_axial_response
from ..kinematics import (
    STANDARD_GRAVITY,
    knee_squat_hold_torque,
    reach_check,
    static_joint_torques,
    zmp_balance_check,
)
from ..mechanics_formulas import rod_inertia_about_end
from ..structural import STRESS_CONCENTRATION_CIRCULAR_HOLE

#: arXiv anchor for the honest thin-wall failure boundary (the in-plane print strength is already an
#: effective, interface-derated value — see the module docstring).
THIN_WALL_FAILURE_ANCHOR = "arXiv:cond-mat/0502303"

#: Minimum acceptable structural safety factor on the GOVERNING stress of a load-bearing part. 1.5 is
#: the conservative static margin GENESIS uses elsewhere; below it a part is UNDER-designed, far above
#: it (here ≥ 4) it is OVER-designed (heavier/costlier than the load needs).
STRUCT_SF_MIN = 1.5
STRUCT_SF_OVERBUILT = 4.0

#: Poisson's ratio of the CF-Nylon printed structure (typical for filled nylon; a DECISION input to the
#: elasticity matrix — it does not affect the uniaxial σ=F/A axial reserve but is required by the solver).
CF_NYLON_POISSON = 0.35


# ════════════════════════════════════════════════════════════════════════════════════════════════
# Finding dataclasses — the structured, honest output of each analysis.
# ════════════════════════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PartStructuralFinding:
    """One load-bearing part's structural verdict, with BOTH stress paths made explicit.

    ``fem_axial_stress_mpa`` is the continuum-FEM crush/compression stress (σ=F/A, a solver output);
    ``bending_stress_mpa`` is the closed-form peak bending stress at the mounting hole (Kt·6FL/bh²);
    ``governing_stress_mpa`` is the larger of the two and sets ``safety_factor`` = strength / governing.
    ``verdict`` is ``"under"`` (SF < STRUCT_SF_MIN), ``"overbuilt"`` (SF ≥ STRUCT_SF_OVERBUILT) or ``"ok"``.
    """
    name: str
    load_path: str
    load_n: float
    fem_axial_stress_mpa: float
    bending_stress_mpa: float
    governing_stress_mpa: float
    governing_mode: str          # "axial" | "bending"
    strength_mpa: float
    safety_factor: float
    verdict: str


@dataclass(frozen=True)
class JointDriveFinding:
    """One joint's drivetrain verdict against its real actuator, static and dynamic.

    ``static_sf`` / ``dynamic_sf`` are available-torque / demand for the worst static hold and the
    inertial (J·α-augmented) dynamic demand. ``verdict`` flags ``"under"`` (static_sf < 1.5),
    ``"overbuilt"`` (static_sf > 4) or ``"matched"``.
    """
    joint: str
    actuator: str
    static_demand_nm: float
    dynamic_demand_nm: float
    rated_peak_nm: float
    available_nm: float
    static_sf: float
    dynamic_sf: float
    verdict: str


@dataclass(frozen=True)
class KinematicsFinding:
    """The worst static pose + a representative dynamic case + the reach margin."""
    knee_worst_pose_torque_nm: float
    knee_worst_pose_angle_rad: float
    arm_reach_safety_factor: float
    arm_reachable: bool
    arm_max_gravity_hold_nm: float
    zmp_static_margin: float
    zmp_static_ok: bool
    zmp_dynamic_margin: float
    zmp_dynamic_ok: bool
    dynamic_accel_x: float


@dataclass(frozen=True)
class MassInertiaFinding:
    """The mass budget + leg-swing inertia + the scaling-law band verdict."""
    total_mass_kg: float
    per_segment_kg: dict
    leg_swing_inertia_kg_m2: float
    knee_law_predicted_nm: float
    knee_law_actual_nm: float
    knee_law_ratio: float
    knee_law_verdict: str         # "in_band" | "high" | "low"
    within_band: bool


@dataclass(frozen=True)
class MechanicsReport:
    """The complete deep-compute result for AETHON."""
    structural: list = field(default_factory=list)
    joints: list = field(default_factory=list)
    kinematics: KinematicsFinding | None = None
    mass_inertia: MassInertiaFinding | None = None


# ════════════════════════════════════════════════════════════════════════════════════════════════
# (1) STRUCTURE — continuum-FEM axial reserve + closed-form bending, governing SF.
# ════════════════════════════════════════════════════════════════════════════════════════════════

def fem_axial_stress_mpa(length_mm: float, width_mm: float, thick_mm: float,
                         force_n: float, e_mpa: float, nu: float = CF_NYLON_POISSON) -> float:
    """Continuum-FEM axial (compression) stress of a prismatic structural member [MPa].

    Drives the part through the REAL Genesis 3-D linear-elastic tet FEM
    (:func:`fem3d.prismatic_bar_axial_response`) under ``force_n`` along its long axis and reads the
    volume-mean σ_xx out of the solver — it is NOT a closed-form substitution. (The constant-strain
    tet reproduces the uniform axial field, so it equals F/A to machine precision; that is the point —
    a real solver that recovers the exact field, proving the number is computed, not canned.)

    Lengths in mm, ``force_n`` in N, ``e_mpa`` in MPa → stress in MPa (consistent N-mm-MPa system).
    Raises ValueError (from the solver) on a non-positive dimension/modulus.
    """
    return prismatic_bar_axial_response(length_mm, width_mm, thick_mm, e_mpa, nu, force_n).axial_stress


def closed_form_bending_peak_mpa(force_n: float, arm_mm: float, width_mm: float, thick_mm: float,
                                 kt: float = STRESS_CONCENTRATION_CIRCULAR_HOLE) -> float:
    """Closed-form peak bending stress at the mounting hole [MPa]: Kt·(6·F·L / (b·h²)).

    The SAME Euler-Bernoulli rectangular-section bending (``structural.cantilever_bending_stress_formula``)
    + Kirsch hole concentration the spec gates with — recomputed here independently. Raises ValueError on
    a non-positive section dimension.
    """
    if width_mm <= 0.0 or thick_mm <= 0.0:
        raise ValueError("section width and thickness must be positive")
    sigma_nom = 6.0 * force_n * arm_mm / (width_mm * thick_mm * thick_mm)
    return kt * sigma_nom


def part_structural_finding(name: str, *, load_path: str, force_n: float, bending_arm_mm: float,
                            width_mm: float, thick_mm: float, length_mm: float,
                            strength_mpa: float, e_mpa: float) -> PartStructuralFinding:
    """Full structural verdict for one load-bearing part: FEM axial reserve vs closed-form bending,
    governing SF, over/under/ok flag. Raises ValueError on a non-positive strength."""
    if strength_mpa <= 0.0:
        raise ValueError("material strength must be positive")
    axial = fem_axial_stress_mpa(length_mm, width_mm, thick_mm, force_n, e_mpa)
    bending = closed_form_bending_peak_mpa(force_n, bending_arm_mm, width_mm, thick_mm)
    if bending >= axial:
        governing, mode = bending, "bending"
    else:
        governing, mode = axial, "axial"
    sf = strength_mpa / governing if governing > 0.0 else float("inf")
    verdict = "under" if sf < STRUCT_SF_MIN else ("overbuilt" if sf >= STRUCT_SF_OVERBUILT else "ok")
    return PartStructuralFinding(
        name=name, load_path=load_path, load_n=force_n,
        fem_axial_stress_mpa=axial, bending_stress_mpa=bending,
        governing_stress_mpa=governing, governing_mode=mode,
        strength_mpa=strength_mpa, safety_factor=sf, verdict=verdict)


# ════════════════════════════════════════════════════════════════════════════════════════════════
# (3) DRIVETRAIN — every joint vs its real actuator, static + dynamic.
# ════════════════════════════════════════════════════════════════════════════════════════════════

def _swing_angular_accel(amplitude_rad: float, step_frequency_hz: float) -> float:
    """Peak angular acceleration of a sinusoidal swing θ(t)=A·sin(ωt): α_peak = A·ω², ω=2π·f.

    The honest representative dynamic case for a swinging limb — its inertial torque is J·α_peak."""
    omega = 2.0 * math.pi * step_frequency_hz
    return amplitude_rad * omega * omega


def joint_drive_finding(joint: str, actuator: str, static_demand_nm: float, rated_peak_nm: float,
                        *, dynamic_demand_nm: float | None = None,
                        envelope: dict | None = None) -> JointDriveFinding:
    """Verdict for one joint against its actuator's published peak (and, when given, its full reflected
    torque-speed ``envelope`` from :func:`actuation.electric_actuator_check`).

    ``available_nm`` is the envelope's available torque at the joint speed when an ``envelope`` is
    supplied (the honest motor curve), else the published ``rated_peak_nm`` (a peak-capability screen).
    Raises ValueError on a non-positive rated peak or negative static demand."""
    if rated_peak_nm <= 0.0:
        raise ValueError("rated peak torque must be positive")
    if static_demand_nm < 0.0:
        raise ValueError("static demand must be non-negative")
    available = float(envelope["available_torque"]) if envelope is not None else rated_peak_nm
    dyn = dynamic_demand_nm if dynamic_demand_nm is not None else static_demand_nm
    static_sf = available / static_demand_nm if static_demand_nm > 0.0 else float("inf")
    dynamic_sf = available / dyn if dyn > 0.0 else float("inf")
    verdict = ("under" if static_sf < STRUCT_SF_MIN
               else ("overbuilt" if static_sf > STRUCT_SF_OVERBUILT else "matched"))
    return JointDriveFinding(
        joint=joint, actuator=actuator, static_demand_nm=static_demand_nm,
        dynamic_demand_nm=dyn, rated_peak_nm=rated_peak_nm, available_nm=available,
        static_sf=static_sf, dynamic_sf=dynamic_sf, verdict=verdict)


# ════════════════════════════════════════════════════════════════════════════════════════════════
# The convenience driver — feed the real AETHON config to all four analyses.
# ════════════════════════════════════════════════════════════════════════════════════════════════

def compute_aethon_mechanics() -> MechanicsReport:
    """Run all four analyses on the live AETHON design and return a structured :class:`MechanicsReport`.

    Lazily imports the AETHON config / DOF map / URDF mass+dim tables from ``genesis_humanoid`` (so this
    module has no import cycle with the spec it informs). Deterministic, offline, numpy-only."""
    from . import genesis_humanoid as gh

    cfg = gh.AETHON
    g = STANDARD_GRAVITY
    sf = 2.0
    design_force_n = cfg.leg_load_kg * sf * g           # the spec's design load (load × safety factor)

    # ---- (1) structure: each load-bearing part under its stance load path ----
    structural: list[PartStructuralFinding] = []
    # thigh — the σ-gated bending member; arm = hip→knee bending lever
    structural.append(part_structural_finding(
        "Oberschenkel (thigh)", load_path="Einbein-Stand: Körperlast am Hüft-Pivot, Biegung am Knie-Loch",
        force_n=design_force_n, bending_arm_mm=70.0,
        width_mm=cfg.thigh_width_mm, thick_mm=cfg.thigh_thick_mm, length_mm=220.0,
        strength_mpa=cfg.material_strength_mpa, e_mpa=cfg.material_e_mpa))
    # pelvis/hip plate — carries the same body load across the hip bore (shorter bending arm)
    structural.append(part_structural_finding(
        "Becken/Hüfte (pelvis)", load_path="Hüftlager trägt die Körperlast; Biegung am Hüft-Loch",
        force_n=design_force_n, bending_arm_mm=65.0,
        width_mm=70.0, thick_mm=22.0, length_mm=170.0,
        strength_mpa=cfg.material_strength_mpa, e_mpa=cfg.material_e_mpa))
    # spine/torso plate — carries the upper-body share above the waist
    structural.append(part_structural_finding(
        "Spine/Rumpf (torso)", load_path="Spine trägt Oberkörper über dem Waist-Gelenk; Biegung am Spine-Loch",
        force_n=design_force_n, bending_arm_mm=85.0,
        width_mm=130.0, thick_mm=22.0, length_mm=210.0,
        strength_mpa=cfg.material_strength_mpa, e_mpa=cfg.material_e_mpa))
    # shank/knee member — the lower leg below the knee
    structural.append(part_structural_finding(
        "Unterschenkel (shank)", load_path="Knie→Knöchel-Glied unter Stand-Last; Biegung am Knie-Loch",
        force_n=design_force_n, bending_arm_mm=80.0,
        width_mm=38.0, thick_mm=14.0, length_mm=210.0,
        strength_mpa=cfg.material_strength_mpa, e_mpa=cfg.material_e_mpa))

    # ---- (2) kinematics / dynamics ----
    # worst static pose: a deep single-leg squat, thigh near-horizontal (θ ≈ 80° from vertical)
    worst_angle = math.radians(80.0)
    knee_worst = knee_squat_hold_torque(body_mass=gh.TARGET_MASS_KG, thigh_length=gh.SHANK_LEN_M,
                                        thigh_angle_from_vertical=worst_angle)
    rc = reach_check(cfg.reach_l1, cfg.reach_l2, cfg.reach_tx, cfg.reach_ty)
    # arm gravity hold: a 2R arm fully extended horizontally carrying a small payload share
    arm_tau = static_joint_torques(
        link_lengths=[cfg.reach_l1, cfg.reach_l2], joint_angles=[0.0, 0.0],
        link_masses=[gh._MASS["uarm"], gh._MASS["farm"]], payload_mass=1.0)
    # static ZMP: CoM centred over the 240 mm sole
    zmp_static = zmp_balance_check(com_x=0.0, com_z=gh.COM_HEIGHT_M, support_min_x=-0.11, support_max_x=0.13)
    # dynamic ZMP: peak horizontal CoM acceleration of the swaying gait (a = amplitude·ω²)
    accel_x = _swing_angular_accel(0.022, cfg.step_frequency_hz)   # reuse SHM peak: amp·(2πf)²
    zmp_dyn = zmp_balance_check(com_x=0.0, com_z=gh.COM_HEIGHT_M, support_min_x=-0.11,
                                support_max_x=0.13, accel_x=accel_x)
    kinematics = KinematicsFinding(
        knee_worst_pose_torque_nm=knee_worst["knee_torque"], knee_worst_pose_angle_rad=worst_angle,
        arm_reach_safety_factor=rc["safety_factor"], arm_reachable=rc["ok"],
        arm_max_gravity_hold_nm=arm_tau["max_torque"],
        zmp_static_margin=zmp_static["stability_margin"], zmp_static_ok=zmp_static["ok"],
        zmp_dynamic_margin=zmp_dyn["stability_margin"], zmp_dynamic_ok=zmp_dyn["ok"],
        dynamic_accel_x=accel_x)

    # ---- (3) drivetrain: every body joint vs its real actuator ----
    limb_inertia = rod_inertia_about_end(gh._MASS["thigh"] + gh._MASS["shank"],
                                         gh._DIM["thigh_len"] + gh._DIM["shank_len"])
    alpha = _swing_angular_accel(0.4, cfg.step_frequency_hz)        # leg swing amplitude 0.4 rad
    inertial_nm = limb_inertia * alpha
    joints: list[JointDriveFinding] = []
    for group, specs in gh.DOF_MAP.items():
        for j in specs:
            is_knee = j.name == "knee_pitch"
            env = None
            if is_knee:
                env = electric_actuator_check(
                    joint_torque=cfg.knee_demand_nm, joint_speed=cfg.joint_speed_rad_s,
                    motor_stall_torque=cfg.knee_peak_nm / (cfg.knee_gear * cfg.knee_eff),
                    motor_noload_speed=cfg.knee_noload_out_rad_s * cfg.knee_gear,
                    gear_ratio=cfg.knee_gear, efficiency=cfg.knee_eff)
            # dynamic demand: leg joints carry the swing inertial torque on top of the static hold
            dyn = j.demand_nm + (inertial_nm if group == "leg_each" else 0.0)
            joints.append(joint_drive_finding(j.name, j.actuator, j.demand_nm, j.peak_nm,
                                              dynamic_demand_nm=dyn, envelope=env))

    # ---- (4) mass / inertia + scaling laws ----
    counts = {"pelvis": 1, "torso": 1, "head": 1, "thigh": 2, "shank": 2, "foot": 2,
              "uarm": 2, "farm": 2, "palm": 2, "phalanx": 2 * gh.FINGERS_PER_HAND * gh.PHALANGES_PER_FINGER}
    per_segment = {k: gh._MASS[k] * n for k, n in counts.items()}
    total_mass = sum(per_segment.values())
    from .scaling_laws import check_knee
    dc = check_knee(mass_kg=float(cfg.leg_load_kg), height_m=gh.TARGET_HEIGHT_M,
                    knee_torque_nm=float(cfg.knee_peak_nm))
    mass_inertia = MassInertiaFinding(
        total_mass_kg=total_mass, per_segment_kg=per_segment,
        leg_swing_inertia_kg_m2=limb_inertia,
        knee_law_predicted_nm=dc.predicted, knee_law_actual_nm=dc.actual, knee_law_ratio=dc.ratio,
        knee_law_verdict=dc.verdict, within_band=dc.within_band)

    return MechanicsReport(structural=structural, joints=joints, kinematics=kinematics,
                           mass_inertia=mass_inertia)


def summarise() -> str:
    """A readable head-to-toe mechanical report (the audit deliverable text)."""
    r = compute_aethon_mechanics()
    out: list[str] = ["AETHON — Mechanik-Tiefenanalyse (über die echten δ-Physik-Validatoren)", ""]
    out.append("STRUKTUR (FEM-Axial-Reserve + Closed-Form-Biegung, maßgebend):")
    for f in r.structural:
        out.append(f"  [{f.verdict:9}] {f.name}: σ_axial(FEM)={f.fem_axial_stress_mpa:.2f} MPa, "
                   f"σ_bend={f.bending_stress_mpa:.1f} MPa → maßgebend {f.governing_mode} "
                   f"{f.governing_stress_mpa:.1f} MPa, SF={f.safety_factor:.2f} (σ_zul={f.strength_mpa:.0f} MPa)")
    k = r.kinematics
    out += ["", "KINEMATIK / DYNAMIK:",
            f"  Knie-Worst-Pose (tiefe Hocke {math.degrees(k.knee_worst_pose_angle_rad):.0f}°): "
            f"{k.knee_worst_pose_torque_nm:.1f} N·m",
            f"  Arm-Reichweite SF={k.arm_reach_safety_factor:.2f} (erreichbar={k.arm_reachable}), "
            f"Arm-Schwerkraft-Halt max {k.arm_max_gravity_hold_nm:.1f} N·m",
            f"  ZMP statisch: Marge {k.zmp_static_margin:.2f} (ok={k.zmp_static_ok}); "
            f"dynamisch (a_x={k.dynamic_accel_x:.3f} m/s²): Marge {k.zmp_dynamic_margin:.2f} (ok={k.zmp_dynamic_ok})"]
    out += ["", "ANTRIEB (je Gelenk vs. realer Aktuator, statisch/dynamisch):"]
    for j in r.joints:
        out.append(f"  [{j.verdict:9}] {j.joint}: Bedarf {j.static_demand_nm:.1f} N·m (dyn "
                   f"{j.dynamic_demand_nm:.1f}), verfügbar {j.available_nm:.1f} N·m → "
                   f"SF_stat {j.static_sf:.2f} / SF_dyn {j.dynamic_sf:.2f} [{j.actuator}]")
    m = r.mass_inertia
    out += ["", "MASSE / TRÄGHEIT + SKALIERUNGSGESETZE:",
            f"  Gesamtmasse {m.total_mass_kg:.1f} kg; Bein-Schwung-Trägheit {m.leg_swing_inertia_kg_m2:.3f} kg·m²",
            f"  Knie-Gesetz: vorhergesagt {m.knee_law_predicted_nm:.0f} N·m, AETHON {m.knee_law_actual_nm:.0f} "
            f"N·m ({m.knee_law_ratio:.2f}×) → {m.knee_law_verdict.upper()} (im Band={m.within_band})"]
    return "\n".join(out)
