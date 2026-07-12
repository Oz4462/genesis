"""catalog — the verified, source-cited reference record for each real open-source humanoid.

This is the GROUND TRUTH that GENESIS's physics axes are checked against. Every number carries the
source it was confirmed from (a primary repo file, the project's own paper, or the official spec page),
following the project rule: no factual value without a source. Where a spec could not be confirmed it
is ``None`` (an honest gap), never a guess.

Two kinds of fact live here, kept distinct:
  * ``RobotSpec`` — the PUBLISHED design figures (height, mass, total DOF, actuator model + ratings,
    compute, battery) with per-field sources. These drive the actuation/compute/mass axes and are the
    "truth" the agreement table compares GENESIS against.
  * ``AssetRef`` — the LOCAL files actually downloaded (path, format, license) and whether a
    machine-readable model (URDF/MJCF) is present for the structural parser. ``None`` model_path means
    spec-only (no mesh/URDF obtainable in this environment) — also an honest state, not a failure.

Offline, deterministic, no I/O at import. Asset paths point OUTSIDE the repo
(/home/genesis/humanoid_assets/) to stay clear of the running crew campaign's git operations.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

ASSET_ROOT = "/home/genesis/humanoid_assets"
#: The curated MuJoCo-Menagerie shallow clone + MANIFEST live here (the §A library).
REF_ROOT = f"{ASSET_ROOT}/references"
#: The robot_descriptions on-demand cache (the §B library) — clones the upstream repo per model.
#: ``expanduser`` is pure string work (no filesystem I/O), so the "no I/O at import" rule holds.
RD_ROOT = os.path.expanduser("~/.cache/robot_descriptions")


@dataclass(frozen=True)
class Cited:
    """A single value with the source it was verified from."""
    value: float | int | str | None
    source: str

    def __repr__(self) -> str:  # compact for tables
        return f"{self.value!r}⟨{self.source}⟩"


@dataclass(frozen=True)
class ActuatorSpec:
    """One joint actuator's published ratings — the input to ``actuation.electric_actuator_check``."""
    model: str
    peak_torque_nm: Cited
    rated_torque_nm: Cited | None = None
    gear_ratio: Cited | None = None
    source: str = ""


@dataclass(frozen=True)
class RobotSpec:
    """Published design figures for one humanoid, each field sourced. ``None`` = unconfirmed gap."""
    key: str
    name: str
    maker: str
    height_m: Cited
    mass_kg: Cited
    total_dof: Cited
    legs: Cited
    arms: Cited
    primary_source: str
    actuators: tuple[ActuatorSpec, ...] = ()
    peak_joint_torque_nm: Cited | None = None
    compute_tops: Cited | None = None
    compute_power_w: Cited | None = None
    battery_wh: Cited | None = None
    notes: str = ""


@dataclass(frozen=True)
class AssetRef:
    """What was actually downloaded locally for a robot."""
    key: str
    repo_url: str
    license: str
    license_note: str
    local_dir: str
    model_path: str | None        #: the URDF/MJCF the parser can read; None = spec-only
    model_format: str | None      #: "urdf" | "mjcf" | None
    extra_formats: tuple[str, ...] = field(default_factory=tuple)  #: STEP/STL/DAE present on disk
    status_note: str = ""


# ── Published specs (each value sourced) ──────────────────────────────────────────────────────────

SPECS: dict[str, RobotSpec] = {
    "tienkung": RobotSpec(
        key="tienkung", name="Tien Kung (Lite)", maker="Open X-Humanoid (X-Humanoid / 北京人形)",
        height_m=Cited(1.69, "X-Humanoid Tien Kung 3.0 spec page (line height ~1.69 m)"),
        mass_kg=Cited(42.5, "PARSED from lite humanoid_publish.urdf: Σ link mass = 42.516 kg"),
        total_dof=Cited(20, "PARSED from lite humanoid_publish.urdf: 20 revolute joints"),
        legs=Cited(2, "URDF tree"), arms=Cited(2, "URDF tree"),
        primary_source="github.com/Open-X-Humanoid/TienKung_URDF (lite humanoid_publish.urdf)",
        peak_joint_torque_nm=Cited(360.0,
            "X-Humanoid Tien Kung line peak joint torque ~360-400 N·m (spec pages); used as the leg "
            "knee actuator capability class — NOT a per-joint URDF value"),
        notes="Lite variant = 20 DOF (12 leg + 8 arm). Pro/2.0/3.0 variants have more DOF & hands.",
    ),
    "berkeley_lite": RobotSpec(
        key="berkeley_lite", name="Berkeley Humanoid Lite", maker="UC Berkeley Hybrid Robotics",
        height_m=Cited(0.85, "arXiv 2504.17249 (sub-metre desktop-scale 3D-printed humanoid)"),
        mass_kg=Cited(16.33, "PARSED from berkeley_humanoid_lite.urdf: Σ link mass = 16.331 kg"),
        total_dof=Cited(22, "PARSED from berkeley_humanoid_lite.urdf: 22 revolute joints (full body)"),
        legs=Cited(2, "URDF tree"), arms=Cited(2, "URDF tree"),
        primary_source="github.com/HybridRobotics/Berkeley-Humanoid-Lite-Assets",
        notes="3D-printed incl. cycloidal-gear actuators. Biped-only sub-model = 12 DOF, 11.3 kg.",
    ),
    "asimov": RobotSpec(
        key="asimov", name="Asimov v1", maker="Menlo Research",
        height_m=Cited(1.2, "Menlo Research / Humanoids Daily launch (1.2 m biped)"),
        mass_kg=Cited(32.37, "PARSED from sim-model/xmls/asimov.xml: Σ body mass = 32.371 kg "
                              "(published figure ~35 kg incl. non-modelled parts)"),
        total_dof=Cited(27, "PARSED from asimov.xml: 27 hinge joints + 1 floating base "
                            "(published headline: 25 actuated DOF)"),
        legs=Cited(2, "MJCF tree"), arms=Cited(2, "MJCF tree"),
        primary_source="github.com/asimovinc/asimov-1 (sim-model/xmls/asimov.xml)",
        notes="MJF-printed + aluminum frame, chest 2MP cam. Published 25 DOF vs 27 hinges in MJCF — "
              "the 2-joint delta is unconfirmed (likely neck/end-effector); reported honestly.",
    ),
    "agiloped": RobotSpec(
        key="agiloped", name="AGILOped", maker="Univ. Bonn (NimbRo / AIS)",
        height_m=Cited(1.10, "arXiv 2509.09364 (110 cm)"),
        mass_kg=Cited(14.5, "arXiv 2509.09364 (14.5 kg)"),
        total_dof=Cited(10, "arXiv 2509.09364 (10 active DOF)"),
        legs=Cited(2, "arXiv 2509.09364"), arms=Cited(2, "arXiv 2509.09364 (1-DoF each)"),
        primary_source="nimbro.net/Humanoid/AGILOped + arXiv 2509.09364",
        actuators=(
            ActuatorSpec(model="MyActuator RMD-X6-40",
                         peak_torque_nm=Cited(40.0, "arXiv 2509.09364 hip flex 40 N·m peak"),
                         rated_torque_nm=Cited(18.0, "arXiv 2509.09364 hip flex 18 N·m rated"),
                         source="arXiv 2509.09364 Table (10× RMD-X6-40)"),
        ),
        peak_joint_torque_nm=Cited(80.0,
            "arXiv 2509.09364 knee flex 80 N·m peak (joint-configuration-dependent via parallel linkage)"),
        notes="Hybrid serial-parallel legs: 3 hip (yaw/roll/pitch) + 1 knee actuator/leg; passive "
              "ankles via parallelogram. CAD/URDF/MuJoCo on the NimbRo project page.",
    ),
    "fourier_n1": RobotSpec(
        key="fourier_n1", name="Fourier N1", maker="Fourier Intelligence",
        height_m=Cited(1.3, "Fourier N1 launch (1.3 m)"),
        mass_kg=Cited(38.0, "Fourier N1 launch (38 kg)"),
        total_dof=Cited(23, "CONFIRMED from Wiki-GRx-Deploy FourierN1 config_N1__developer.yaml "
                            "actuator map: 6 L-leg + 6 R-leg + 1 waist + 5 L-arm + 5 R-arm = 23"),
        legs=Cited(2, "config actuator map"), arms=Cited(2, "config actuator map"),
        primary_source="github.com/FFTAI/Wiki-GRx-Deploy@FourierN1 (config_N1__developer.yaml)",
        notes="Control period 0.0025 s (400 Hz) per config. URDF/mesh NOT in any accessible Fourier "
              "GitHub repo (lives in installed runtime resource ~/fourier-grx/resource/n1) → spec-only.",
    ),
    "kbot": RobotSpec(
        key="kbot", name="K-Bot", maker="K-Scale Labs",
        height_m=Cited(1.4, "K-Scale K-Bot launch (~4'7\" ≈ 1.4 m)"),
        mass_kg=Cited(34.0, "K-Scale K-Bot launch (~77 lb ≈ 34 kg)"),
        total_dof=Cited(20, "K-Scale K-Bot docs (20-DOF motor ID map)"),
        legs=Cited(2, "K-Scale docs"), arms=Cited(2, "K-Scale docs"),
        primary_source="github.com/kscalelabs/kbot",
        notes="Full aluminum modular skeleton. CAD is Onshape-only (publication link in repo); the "
              "MJCF is fetched at runtime from the kscale web API (kbot-v2-lw-feet) → not stored in "
              "repo → model-blocked offline.",
    ),
    "inmoov": RobotSpec(
        key="inmoov", name="InMoov", maker="Gael Langevin",
        height_m=Cited(None, "life-size upper body; full standing height not a single fixed spec"),
        mass_kg=Cited(None, "varies by build/servos — no single published mass"),
        total_dof=Cited(None, "configuration-dependent (per-finger servos, neck, arms); no single DOF"),
        legs=Cited(0, "InMoov is an upper-body humanoid (torso/arms/head); no legs"),
        arms=Cited(2, "InMoov design"),
        primary_source="inmoov.fr + github.com/inmoov-ros/inmoov_model",
        notes="100% home-3D-print, hobby servos + cable drives. CC-BY-NC (NonCommercial) — FLAG before "
              "any commercial use. STL-only (no inertial-bearing URDF in the canonical release).",
    ),

    # ── Ingested 2026-06-24 from MuJoCo Menagerie MJCFs (mass/DOF/knee parsed from the tuned model) ──
    # height_m = published vendor spec (the one fact the model does not carry); everything else PARSED.
    "unitree_g1": RobotSpec(
        key="unitree_g1", name="Unitree G1", maker="Unitree Robotics",
        height_m=Cited(1.27, "Unitree G1 spec (~1.27 m standing, 23-DOF base config)"),
        mass_kg=Cited(33.34, "PARSED menagerie/unitree_g1/g1.xml: Σ body mass = 33.341 kg"),
        total_dof=Cited(29, "PARSED g1.xml: 29 hinge joints (this Menagerie variant; 23-DOF & "
                            "with-hands variants exist) + free base"),
        legs=Cited(2, "MJCF tree"), arms=Cited(2, "MJCF tree"),
        primary_source="MuJoCo Menagerie unitree_g1/g1.xml (google-deepmind/mujoco_menagerie)",
        peak_joint_torque_nm=Cited(139.0, "PARSED g1.xml: left/right_knee_joint actuatorfrcrange = ±139 N·m"),
        notes="Knee 139 N·m, hip-pitch 88, ankle 50 N·m — all parsed from joint actuatorfrcrange.",
    ),
    "unitree_h1": RobotSpec(
        key="unitree_h1", name="Unitree H1", maker="Unitree Robotics",
        height_m=Cited(1.80, "Unitree H1 spec (~1.8 m full-size)"),
        mass_kg=Cited(51.44, "PARSED menagerie/unitree_h1/h1.xml: Σ body mass = 51.437 kg"),
        total_dof=Cited(19, "PARSED h1.xml: 19 hinge joints + free base"),
        legs=Cited(2, "MJCF tree"), arms=Cited(2, "MJCF tree"),
        primary_source="MuJoCo Menagerie unitree_h1/h1.xml",
        peak_joint_torque_nm=Cited(300.0, "PARSED h1.xml: left/right_knee motor ctrlrange = ±300 N·m"),
        notes="Knee 300 N·m, hip 200, ankle 40 N·m — parsed from <motor> ctrlrange (direct-drive, gear 1).",
    ),
    "booster_t1": RobotSpec(
        key="booster_t1", name="Booster T1", maker="Booster Robotics",
        height_m=Cited(1.18, "Booster T1 spec (~1.18 m)"),
        mass_kg=Cited(31.61, "PARSED menagerie/booster_t1/t1.xml: Σ body mass = 31.614 kg"),
        total_dof=Cited(23, "PARSED t1.xml: 23 hinge joints + free base"),
        legs=Cited(2, "MJCF tree"), arms=Cited(2, "MJCF tree"),
        primary_source="MuJoCo Menagerie booster_t1/t1.xml",
        peak_joint_torque_nm=Cited(60.0, "PARSED t1.xml: knee_pitch forcerange = ±60 N·m"),
        notes="Knee 60 N·m, hip-pitch 45 N·m — parsed from <position> forcerange.",
    ),
    "berkeley_humanoid": RobotSpec(
        key="berkeley_humanoid", name="Berkeley Humanoid", maker="UC Berkeley Hybrid Robotics",
        height_m=Cited(1.30, "Berkeley Humanoid (arXiv 2407.21781; ~1.3 m mid-scale, distinct from Lite)"),
        mass_kg=Cited(16.06, "PARSED menagerie/berkeley_humanoid/berkeley_humanoid.xml: Σ body mass = 16.057 kg"),
        total_dof=Cited(12, "PARSED berkeley_humanoid.xml: 12 hinge joints (legs only in this MJCF) + free base"),
        legs=Cited(2, "MJCF tree"), arms=Cited(0, "this Menagerie MJCF is the 12-DOF leg-only platform"),
        primary_source="MuJoCo Menagerie berkeley_humanoid/berkeley_humanoid.xml",
        peak_joint_torque_nm=Cited(None, "GAP: position actuators carry no forcerange in this MJCF — "
                                         "the torque cap is not declared in the model file"),
        notes="Torque limits not in the MJCF (position servos, no forcerange) → honest torque gap. "
              "12-DOF leg platform; distinct from the in-house 'berkeley_lite' 22-DOF desktop model.",
    ),
    "apptronik_apollo": RobotSpec(
        key="apptronik_apollo", name="Apptronik Apollo", maker="Apptronik",
        height_m=Cited(1.75, "Apptronik Apollo spec (~1.75 m, ~160 cm-class commercial humanoid)"),
        mass_kg=Cited(80.90, "PARSED menagerie/apptronik_apollo/apptronik_apollo.xml: Σ body mass = 80.898 kg"),
        total_dof=Cited(32, "PARSED apptronik_apollo.xml: 32 hinge joints + free base"),
        legs=Cited(2, "MJCF tree"), arms=Cited(2, "MJCF tree"),
        primary_source="MuJoCo Menagerie apptronik_apollo/apptronik_apollo.xml",
        peak_joint_torque_nm=Cited(336.0, "PARSED apptronik_apollo.xml: l/r_knee_fe forcerange = ±336 N·m "
                                          "(hip_aa is the strongest joint at ±494 N·m)"),
        notes="Knee 336 N·m parsed from <position> forcerange; hip ab/adduction 494 N·m is the max joint. "
              "1 link without declared inertia (a massless frame) — engine would infer from geoms.",
    ),
    "pal_talos": RobotSpec(
        key="pal_talos", name="PAL TALOS", maker="PAL Robotics",
        height_m=Cited(1.75, "PAL TALOS spec (1.75 m)"),
        mass_kg=Cited(94.00, "PARSED menagerie/pal_talos/talos.xml: Σ body mass = 94.003 kg "
                             "(published ~95 kg)"),
        total_dof=Cited(44, "PARSED talos.xml: 44 hinge joints + free base (legs 12 + torso 2 + arms 14 "
                            "+ head 2 + grippers)"),
        legs=Cited(2, "MJCF tree"), arms=Cited(2, "MJCF tree"),
        primary_source="MuJoCo Menagerie pal_talos/talos.xml",
        peak_joint_torque_nm=Cited(400.0, "PARSED talos.xml: leg_left/right_4_joint (knee) actuatorfrcrange "
                                          "= ±400 N·m"),
        notes="Knee = leg_X_4_joint, parsed ±400 N·m; hip-pitch (leg_X_3) ±160 N·m. TALOS uses numbered "
              "leg joints (1=hip-yaw … 4=knee … 6=ankle-roll).",
    ),
    "pndbotics_adam_lite": RobotSpec(
        key="pndbotics_adam_lite", name="PNDbotics Adam Lite", maker="PNDbotics",
        height_m=Cited(1.60, "PNDbotics Adam spec (~1.6 m full-size)"),
        mass_kg=Cited(58.19, "PARSED menagerie/pndbotics_adam_lite/adam_lite.xml: Σ body mass = 58.188 kg"),
        total_dof=Cited(25, "PARSED adam_lite.xml: 25 hinge joints + free base"),
        legs=Cited(2, "MJCF tree"), arms=Cited(2, "MJCF tree"),
        primary_source="MuJoCo Menagerie pndbotics_adam_lite/adam_lite.xml",
        peak_joint_torque_nm=Cited(230.0, "PARSED adam_lite.xml: kneePitch motor ctrlrange = ±230 N·m"),
        notes="Knee 230 N·m, hip-pitch 230 N·m — parsed from <motor> ctrlrange (direct, gear 1).",
    ),
    "robotis_op3": RobotSpec(
        key="robotis_op3", name="ROBOTIS OP3", maker="ROBOTIS",
        height_m=Cited(0.51, "ROBOTIS OP3 spec (51 cm desktop humanoid)"),
        mass_kg=Cited(3.15, "PARSED menagerie/robotis_op3/op3.xml: Σ body mass = 3.147 kg (spec ~3.5 kg)"),
        total_dof=Cited(20, "PARSED op3.xml: 20 hinge joints + free base (Dynamixel servos)"),
        legs=Cited(2, "MJCF tree"), arms=Cited(2, "MJCF tree"),
        primary_source="MuJoCo Menagerie robotis_op3/op3.xml",
        peak_joint_torque_nm=Cited(None, "GAP: Dynamixel position actuators carry no per-joint forcerange "
                                         "here (the one declared limit is a non-leg joint)"),
        notes="Small hobby-class humanoid (Dynamixel XM/MX servos ~4-6 N·m). Torque caps not in the MJCF "
              "→ honest gap. Mesh bbox read flags mm-authored visual meshes (geometry-only, not load-bearing).",
    ),
    "agility_cassie": RobotSpec(
        key="agility_cassie", name="Agility Cassie", maker="Agility Robotics (model port: DeepMind)",
        height_m=Cited(1.00, "Agility Cassie (~1.0 m to pelvis; biped, no torso/arms)"),
        mass_kg=Cited(33.31, "PARSED menagerie/agility_cassie/cassie.xml: Σ body mass = 33.312 kg "
                             "(published ~31 kg)"),
        total_dof=Cited(10, "PARSED cassie.xml: 10 ACTUATED hinges (the 20 tree hinges include 10 passive "
                            "spring/leaf joints; only 10 carry motors)"),
        legs=Cited(2, "MJCF tree"), arms=Cited(0, "Cassie is a biped, no arms"),
        primary_source="MuJoCo Menagerie agility_cassie/cassie.xml",
        peak_joint_torque_nm=Cited(195.2, "PARSED cassie.xml: knee <motor> gear=16 × ctrlrange ±12.2 "
                                          "= ±195.2 N·m at the joint"),
        notes="IMPORTANT: Cassie's <motor> declares the MOTOR command (±12.2) and a gear=16 reduction; the "
              "JOINT torque is 16×12.2 = 195.2 N·m. Reading ctrlrange alone (12.2) would understate it 16×. "
              "Parser counts only the 10 motorised joints as actuated DOF (matching Agility's 10-DOF spec).",
    ),
    "toddlerbot_2xc": RobotSpec(
        key="toddlerbot_2xc", name="ToddlerBot 2XC", maker="Stanford (Shi et al.)",
        height_m=Cited(0.56, "ToddlerBot (arXiv 2502.00893; ~0.56 m / 560 mm desktop bipedal)"),
        mass_kg=Cited(3.45, "PARSED menagerie/toddlerbot_2xc/toddlerbot_2xc.xml: Σ body mass = 3.454 kg"),
        total_dof=Cited(30, "PARSED toddlerbot_2xc.xml: 30 hinge joints (excl. the 1 free base of the 44 "
                            "joint slots; passive/coupled joints not motorised) + free base"),
        legs=Cited(2, "MJCF tree"), arms=Cited(2, "MJCF tree"),
        primary_source="MuJoCo Menagerie toddlerbot_2xc/toddlerbot_2xc.xml",
        peak_joint_torque_nm=Cited(None, "GAP: Dynamixel <motor>s with no per-joint torque cap in the MJCF"),
        notes="Smallest in the set (~3.5 kg, Dynamixel servos). Torque caps not declared → honest gap.",
    ),

    # ── Ingested 2026-06-24 from robot_descriptions cache (URDF/MJCF; mass/DOF/knee parsed) ─────────
    "atlas_v4": RobotSpec(
        key="atlas_v4", name="Boston Dynamics Atlas v4", maker="Boston Dynamics (model: roboschool/OpenAI)",
        height_m=Cited(1.50, "Atlas DRC/v4 spec (~1.5 m, hydraulic)"),
        mass_kg=Cited(182.42, "PARSED roboschool atlas_v4_with_multisense.urdf: Σ link mass = 182.4 kg "
                              "(this URDF's inertials; the real DRC Atlas is ~150-180 kg)"),
        total_dof=Cited(30, "PARSED atlas_v4 urdf: 30 revolute joints"),
        legs=Cited(2, "URDF tree"), arms=Cited(2, "URDF tree"),
        primary_source="robot_descriptions atlas_v4_description (roboschool atlas_v4_with_multisense.urdf)",
        peak_joint_torque_nm=Cited(890.0, "PARSED atlas_v4 urdf: l/r_leg_kny (knee) <limit effort> = 890 N·m "
                                          "(hydraulic — the strongest knee in the library)"),
        notes="HYDRAULIC: knee 890 N·m parsed from <limit effort> — an order above the electric fleet, the "
              "high-torque anchor. 29 mesh files referenced but absent in roboschool's tree (geometry not "
              "shipped) → meshes_missing, but the kinematic/inertial/torque data is intact.",
    ),
    "valkyrie": RobotSpec(
        key="valkyrie", name="NASA Valkyrie (R5)", maker="NASA JSC",
        height_m=Cited(1.83, "NASA Valkyrie R5 spec (1.83 m / 6 ft)"),
        mass_kg=Cited(135.9, "PARSED nasa valkyrie_sim.urdf: Σ link mass = 135.9 kg (published ~125-136 kg)"),
        total_dof=Cited(59, "PARSED valkyrie_sim.urdf: 59 revolute joints (incl. ~27 dexterous-hand finger "
                            "joints; the body/limb actuated count is ~32). Headline ~44 actuated."),
        legs=Cited(2, "URDF tree"), arms=Cited(2, "URDF tree"),
        primary_source="robot_descriptions valkyrie_description (nasa-urdf-robots valkyrie_sim.urdf)",
        peak_joint_torque_nm=Cited(350.0, "PARSED valkyrie_sim.urdf: left/rightKneePitch <limit effort> = 350 N·m"),
        notes="Knee 350 N·m parsed from <limit effort>. The 59 revolute count is finger-inflated (52 of 58 "
              "non-base revolute joints are hand fingers/thumbs); the load-bearing body DOF is ~32, headline "
              "~44 incl. hands. 2 links without declared inertia.",
    ),
    "gr1": RobotSpec(
        key="gr1", name="Fourier GR-1", maker="Fourier Intelligence",
        height_m=Cited(1.65, "Fourier GR-1 spec (~1.65 m)"),
        mass_kg=Cited(52.83, "PARSED Wiki-GRx GR1T1_nohand.urdf: Σ link mass = 52.827 kg (spec ~55 kg)"),
        total_dof=Cited(32, "PARSED GR1T1_nohand.urdf: 32 revolute joints (no-hand T1 variant)"),
        legs=Cited(2, "URDF tree"), arms=Cited(2, "URDF tree"),
        primary_source="robot_descriptions gr1_description (Wiki-GRx-Models GR1T1_nohand.urdf)",
        peak_joint_torque_nm=Cited(225.0, "PARSED GR1T1_nohand.urdf: knee_pitch <limit effort> = 225 N·m"),
        notes="Knee 225 N·m, hip-pitch 225 N·m parsed from <limit effort>. No-hand variant (32 DOF).",
    ),
    "h1_2": RobotSpec(
        key="h1_2", name="Unitree H1-2", maker="Unitree Robotics",
        height_m=Cited(1.80, "Unitree H1-2 spec (~1.8 m, refreshed H1)"),
        mass_kg=Cited(67.37, "PARSED unitree_ros h1_2.xml: Σ body mass = 67.368 kg"),
        total_dof=Cited(51, "PARSED h1_2.xml: 51 hinge joints (incl. dexterous wrists/hands) + free base"),
        legs=Cited(2, "MJCF tree"), arms=Cited(2, "MJCF tree"),
        primary_source="robot_descriptions h1_2_mj_description (unitree_ros h1_2.xml)",
        peak_joint_torque_nm=Cited(300.0, "PARSED h1_2.xml: knee actuatorfrcrange = ±300 N·m"),
        notes="Knee 300 N·m, hip-pitch 200 N·m parsed from joint actuatorfrcrange. 51 DOF incl. wrists/hands.",
    ),
    "jvrc1": RobotSpec(
        key="jvrc1", name="JVRC-1", maker="AIST (Japan Virtual Robotics Challenge)",
        height_m=Cited(1.40, "JVRC-1 spec (~1.4 m reference humanoid)"),
        mass_kg=Cited(62.40, "PARSED jvrc_mj_description jvrc1.xml: Σ body mass = 62.4 kg"),
        total_dof=Cited(44, "PARSED jvrc1.xml: 44 hinge joints + free base"),
        legs=Cited(2, "MJCF tree"), arms=Cited(2, "MJCF tree"),
        primary_source="robot_descriptions jvrc_mj_description (jvrc1.xml)",
        peak_joint_torque_nm=Cited(None, "GAP: motors declare no per-joint torque cap in this MJCF"),
        notes="Reference simulation humanoid. Torque caps not declared in the MJCF → honest gap.",
    ),
    "draco3": RobotSpec(
        key="draco3", name="Apptronik Draco3", maker="Apptronik / UT Austin HCRL",
        height_m=Cited(1.38, "Draco3 spec (~1.38 m research biped)"),
        mass_kg=Cited(36.52, "PARSED draco3_description draco3.urdf: Σ link mass = 36.522 kg"),
        total_dof=Cited(27, "PARSED draco3.urdf: 27 revolute joints (incl. proximal+distal split knee)"),
        legs=Cited(2, "URDF tree"), arms=Cited(2, "URDF tree"),
        primary_source="robot_descriptions draco3_description (draco3.urdf)",
        peak_joint_torque_nm=Cited(40.85, "PARSED draco3.urdf: knee_fe <limit effort> = 40.85 N·m PER segment "
                                          "(parallel proximal+distal knee → ~81.7 N·m effective)"),
        notes="LOW-OUTLIER knee: 40.85 N·m is per proximal/distal segment of a PARALLEL knee (jp+jd), so the "
              "effective knee torque is ~2×40.85 ≈ 81.7 N·m. The single-segment value flags as low for the mass.",
    ),
    "icub": RobotSpec(
        key="icub", name="iCub (IIT)", maker="Istituto Italiano di Tecnologia",
        height_m=Cited(1.04, "iCub spec (~104 cm child-size humanoid)"),
        mass_kg=Cited(33.06, "PARSED icub-models iCubGazeboV2_5/model.urdf: Σ link mass = 33.062 kg"),
        total_dof=Cited(32, "PARSED iCub model.urdf: 32 revolute joints"),
        legs=Cited(2, "URDF tree"), arms=Cited(2, "URDF tree"),
        primary_source="robot_descriptions icub_description (iCubGazeboV2_5/model.urdf)",
        peak_joint_torque_nm=Cited(37.0, "PARSED iCub urdf: l/r_knee <limit effort> = 37 N·m (the joints "
                                         "that carry a REAL effort; many iCub joints ship effort=50000 sentinels)"),
        notes="DATA-QUALITY NOTE: most iCub URDF joints declare effort=50000 (a placeholder sentinel the parser "
              "gates out as non-physical); only the legs carry real values (knee 37, hip-pitch 55.5 N·m). "
              "150 links without declared inertia (the model is geom-heavy) — honest gap.",
    ),
    "ergocub": RobotSpec(
        key="ergocub", name="ergoCub (IIT)", maker="Istituto Italiano di Tecnologia",
        height_m=Cited(1.27, "ergoCub spec (~127 cm, adult-leaning iCub successor)"),
        mass_kg=Cited(57.00, "PARSED ergocub-software ergoCubSN002/model.urdf: Σ link mass = 57.0 kg"),
        total_dof=Cited(57, "PARSED ergoCub model.urdf: 57 revolute joints (incl. hands)"),
        legs=Cited(2, "URDF tree"), arms=Cited(2, "URDF tree"),
        primary_source="robot_descriptions ergocub_description (ergoCubSN002/model.urdf)",
        peak_joint_torque_nm=Cited(None, "GAP: every ergoCub joint declares effort=1e9 (a placeholder "
                                         "sentinel, gated out as non-physical) — NO real torque limit in the URDF"),
        notes="DATA-QUALITY NOTE: all 57 joints ship effort=1e9 sentinels → the parser reports the torque as an "
              "honest gap rather than a 10^9 N·m fabrication. 138 links without declared inertia.",
    ),
}


# ── Local assets actually downloaded ──────────────────────────────────────────────────────────────

ASSETS: dict[str, AssetRef] = {
    "tienkung": AssetRef(
        key="tienkung", repo_url="github.com/Open-X-Humanoid/TienKung_URDF",
        license="OpenAtom Open Hardware License v1.0",
        license_note="permits copy/distribute/use of hardware-source incl. URDF/HDL — usable",
        local_dir=f"{ASSET_ROOT}/tienkung",
        model_path=f"{ASSET_ROOT}/tienkung/lite_urdf_publish/urdf/humanoid_publish.urdf",
        model_format="urdf", extra_formats=("STEP", "STL", "Webots .proto"),
        status_note="URDF-native, 597 STL meshes real (not LFS pointers), STEP assemblies present. "
                    "A convex-foot variant (humanoid_publish_coacdfeet.urdf, built by gen.humanoids."
                    "coacd_feet) replaces each foot's concave collision mesh with an 8-piece CoACD "
                    "decomposition of the sole slab → ~5x denser ground contact (mean 7.9→41 contacts "
                    "in the crouch hold). Helps the passive hold; does NOT make ankle-strategy control "
                    "beat the passive crouch (ankle tilt still lifts the sole) — see balance findings.",
    ),
    "berkeley_lite": AssetRef(
        key="berkeley_lite", repo_url="github.com/HybridRobotics/Berkeley-Humanoid-Lite-Assets",
        license="CC-BY-SA-4.0",
        license_note="share-alike; attribution required — usable for research",
        local_dir=f"{ASSET_ROOT}/berkeley_lite",
        model_path=f"{ASSET_ROOT}/berkeley_lite/data/robots/berkeley_humanoid/"
                   "berkeley_humanoid_lite/urdf/berkeley_humanoid_lite.urdf",
        model_format="urdf", extra_formats=("MJCF", "USD", "STL"),
        status_note="Full URDF: 26/26 meshes resolve. Biped sub-URDF refs a missing assets/merged/ "
                    "mesh dir (incomplete) → use the full model.",
    ),
    "asimov": AssetRef(
        key="asimov", repo_url="github.com/asimovinc/asimov-1",
        license="CERN-OHL-S 2.0 (hardware) + GPL-2.0 (software)",
        license_note="strongly-reciprocal open hardware + copyleft sw — usable, share-alike",
        local_dir=f"{ASSET_ROOT}/asimov",
        model_path=f"{ASSET_ROOT}/asimov/sim-model/xmls/asimov.xml",
        model_format="mjcf", extra_formats=("STEP/mechanical CAD", "electrical CAD", "STL"),
        status_note="MuJoCo-native, 28 STL meshes real. mechanical/ + electrical/ CAD dirs present.",
    ),
    "agiloped": AssetRef(
        key="agiloped",
        repo_url="github.com/gficht/AGILOped_model (linked from nimbro.net/Humanoid/AGILOped)",
        license="MIT",
        license_note="MIT (LICENSE in repo, © 2025 gficht) — permissive, usable incl. commercially",
        local_dir=f"{ASSET_ROOT}/agiloped",
        model_path=f"{ASSET_ROOT}/agiloped/nimbro_op_model/robots/nimbro_new.urdf",
        model_format="urdf", extra_formats=("STEP (104MB AGILOped.STEP)", "MuJoCo nimbro_new.xml",
                                            "STL (9 meshes)", "xacro"),
        status_note="ACQUIRED + URDF loads in PyBullet, BUT it is the NimbRo-OP 'nimbro_new' lineage "
                    "model the repo ships: 20 ACTUATED continuous joints (6/leg + 6 arm + neck/head) "
                    "PLUS 16 passive PARALLEL-LINKAGE joints — NOT the paper's reduced 10-active-DOF "
                    "AGILOped. 32/45 links carry NO inertial (the parallel rods) → PyBullet invents "
                    "mass=1 each, inflating total to 42.4 kg; the real Σ of declared inertials is "
                    "10.43 kg (paper headline 14.5 kg incl. non-modelled parts). Kinematically loadable "
                    "+ STEP/MuJoCo present; NOT clean-dynamics-ready (missing inertials) without repair.",
    ),
    "fourier_n1": AssetRef(
        key="fourier_n1", repo_url="github.com/FFTAI/Wiki-GRx-MJCF (models/N1) + Wiki-GRx-Deploy@FourierN1 (SDK)",
        license="GPL-3.0 (Wiki-GRx-MJCF model repo)",
        license_note="the N1 MJCF/URDF/meshes come from Wiki-GRx-MJCF (GPL-3.0); the deploy SDK is MIT",
        local_dir=f"{ASSET_ROOT}/fourier_n1",
        model_path=f"{ASSET_ROOT}/fourier_n1/model/scene/N1_raw_refine.xml",
        model_format="mjcf", extra_formats=("URDF (N1_raw.urdf, N1_rotor.urdf)", "29 STL meshes",
                                            "RL policy .pt", "joint config yaml"),
        status_note="ENGINE-VALIDATED + STANDS: MJCF loads in MuJoCo 3.10 — 23 hinge DOF + free base, "
                    "nu=23 actuators, total mass 39.73 kg (spec 38 kg, +4.5%), 29 real binary STL meshes. "
                    "Use scene/N1_raw_refine.xml (relative meshdir, actuated); the bare mjcf/N1_raw.xml "
                    "has hardcoded absolute mesh paths and will not compile here. STAND: with flat box "
                    "soles (gen.humanoids.n1_feet.add_box_feet -> scene/N1_boxfeet.xml) it holds the FULL "
                    "8s upright (max lean 5deg, position-servo PD) and survives lateral + forward pushes; "
                    "the raw mesh feet only stand ~2s (sparse contact). Render: _renders/n1_boxfeet_stand_*.png.",
    ),
    "kbot": AssetRef(
        key="kbot", repo_url="github.com/kscalelabs/kbot + kscalelabs/kscale-assets (kbot-v2-feet)",
        license="CERN-OHL-S (hardware) + GPL-3.0 (software)",
        license_note="strongly-reciprocal open hardware + copyleft sw",
        local_dir=f"{ASSET_ROOT}/kbot",
        model_path=f"{ASSET_ROOT}/kbot/model/robot.mjcf",
        model_format="mjcf", extra_formats=("URDF (robot.urdf)", "24 STL meshes (LFS-resolved)",
                                            "scene MJCFs", "metadata.json (actuator map)"),
        status_note="ENGINE-VALIDATED: MJCF loads in MuJoCo 3.10 — 20 hinge DOF + free base, nu=20 "
                    "actuators, total mass 35.65 kg (spec ~34 kg, +5%), 24 STL meshes. NOTE: meshes ship "
                    "as git-LFS POINTERS in the repo; resolved via the LFS batch API (git-lfs CLI absent). "
                    "robot.mjcf is the bare model; robot_scene.mjcf adds a floor.",
    ),
    "inmoov": AssetRef(
        key="inmoov", repo_url="inmoov.fr + github.com/inmoov-ros/inmoov_model",
        license="CC-BY-NC",
        license_note="NonCommercial — FLAG: forbids commercial use; research/personal OK with attribution",
        local_dir=f"{ASSET_ROOT}/inmoov",
        model_path=None, model_format=None, extra_formats=("STL",),
        status_note="SPEC-ONLY/STL: STL-only hobby model, no inertial-bearing URDF in canonical release; "
                    "no single published mass/DOF. Not pulled (large, NonCommercial-flagged).",
    ),

    # ── MuJoCo Menagerie locals (shallow clone @ 2026-06-24; per-model permissive licenses) ─────────
    "unitree_g1": AssetRef(
        key="unitree_g1", repo_url="github.com/google-deepmind/mujoco_menagerie (unitree_g1)",
        license="BSD-3-Clause", license_note="permissive — usable incl. commercially with attribution",
        local_dir=f"{REF_ROOT}/menagerie/unitree_g1",
        model_path=f"{REF_ROOT}/menagerie/unitree_g1/g1.xml", model_format="mjcf",
        extra_formats=("STL (visual+collision)", "render PNG", "scene.xml", "g1_with_hands.xml"),
        status_note="PARSED: 29 hinge DOF + free base, 33.34 kg, 29/29 joints carry actuatorfrcrange "
                    "(knee 139 N·m). Tuned MJCF, all inertials present.",
    ),
    "unitree_h1": AssetRef(
        key="unitree_h1", repo_url="github.com/google-deepmind/mujoco_menagerie (unitree_h1)",
        license="BSD-3-Clause", license_note="permissive",
        local_dir=f"{REF_ROOT}/menagerie/unitree_h1",
        model_path=f"{REF_ROOT}/menagerie/unitree_h1/h1.xml", model_format="mjcf",
        extra_formats=("STL", "render PNG", "scene.xml"),
        status_note="PARSED: 19 hinge DOF + free base, 51.44 kg, 19 <motor> ctrlrange torque caps "
                    "(knee 300 N·m, direct-drive gear 1).",
    ),
    "booster_t1": AssetRef(
        key="booster_t1", repo_url="github.com/google-deepmind/mujoco_menagerie (booster_t1)",
        license="Apache-2.0", license_note="permissive",
        local_dir=f"{REF_ROOT}/menagerie/booster_t1",
        model_path=f"{REF_ROOT}/menagerie/booster_t1/t1.xml", model_format="mjcf",
        extra_formats=("OBJ+MTL (textured)", "render PNG", "scene.xml"),
        status_note="PARSED: 23 hinge DOF + free base, 31.61 kg, 23 <position> forcerange caps (knee 60 N·m).",
    ),
    "berkeley_humanoid": AssetRef(
        key="berkeley_humanoid", repo_url="github.com/google-deepmind/mujoco_menagerie (berkeley_humanoid)",
        license="BSD-3-Clause", license_note="permissive",
        local_dir=f"{REF_ROOT}/menagerie/berkeley_humanoid",
        model_path=f"{REF_ROOT}/menagerie/berkeley_humanoid/berkeley_humanoid.xml", model_format="mjcf",
        extra_formats=("STL", "render PNG", "scene.xml"),
        status_note="PARSED: 12 hinge DOF (leg-only platform) + free base, 16.06 kg. Position actuators "
                    "carry NO forcerange → torque caps are an honest gap.",
    ),
    "apptronik_apollo": AssetRef(
        key="apptronik_apollo", repo_url="github.com/google-deepmind/mujoco_menagerie (apptronik_apollo)",
        license="Apache-2.0", license_note="permissive",
        local_dir=f"{REF_ROOT}/menagerie/apptronik_apollo",
        model_path=f"{REF_ROOT}/menagerie/apptronik_apollo/apptronik_apollo.xml", model_format="mjcf",
        extra_formats=("STL", "render PNG", "scene.xml"),
        status_note="PARSED: 32 hinge DOF + free base, 80.90 kg, 32 <position> forcerange caps (knee 336 N·m, "
                    "hip-aa 494 N·m). 1 link without declared inertia.",
    ),
    "pal_talos": AssetRef(
        key="pal_talos", repo_url="github.com/google-deepmind/mujoco_menagerie (pal_talos)",
        license="Apache-2.0", license_note="permissive",
        local_dir=f"{REF_ROOT}/menagerie/pal_talos",
        model_path=f"{REF_ROOT}/menagerie/pal_talos/talos.xml", model_format="mjcf",
        extra_formats=("STL", "render PNG", "scene_motor.xml", "scene_position.xml"),
        status_note="PARSED: 44 hinge DOF + free base, 94.00 kg, 30 joint actuatorfrcrange caps "
                    "(knee = leg_X_4_joint = 400 N·m).",
    ),
    "pndbotics_adam_lite": AssetRef(
        key="pndbotics_adam_lite", repo_url="github.com/google-deepmind/mujoco_menagerie (pndbotics_adam_lite)",
        license="MIT", license_note="permissive",
        local_dir=f"{REF_ROOT}/menagerie/pndbotics_adam_lite",
        model_path=f"{REF_ROOT}/menagerie/pndbotics_adam_lite/adam_lite.xml", model_format="mjcf",
        extra_formats=("OBJ+MTL (textured, 78 meshes)", "render PNG", "scene.xml"),
        status_note="PARSED: 25 hinge DOF + free base, 58.19 kg, 25 <motor> ctrlrange caps (knee 230 N·m).",
    ),
    "robotis_op3": AssetRef(
        key="robotis_op3", repo_url="github.com/google-deepmind/mujoco_menagerie (robotis_op3)",
        license="Apache-2.0", license_note="permissive",
        local_dir=f"{REF_ROOT}/menagerie/robotis_op3",
        model_path=f"{REF_ROOT}/menagerie/robotis_op3/op3.xml", model_format="mjcf",
        extra_formats=("STL", "render PNG", "scene.xml"),
        status_note="PARSED: 20 hinge DOF + free base, 3.15 kg (toy-scale). No per-joint torque caps in the "
                    "MJCF → honest gap. Visual meshes flagged mm-authored (geometry-only).",
    ),
    "agility_cassie": AssetRef(
        key="agility_cassie", repo_url="github.com/google-deepmind/mujoco_menagerie (agility_cassie)",
        license="MIT", license_note="model port MIT (the real robot is proprietary Agility hardware)",
        local_dir=f"{REF_ROOT}/menagerie/agility_cassie",
        model_path=f"{REF_ROOT}/menagerie/agility_cassie/cassie.xml", model_format="mjcf",
        extra_formats=("OBJ", "render PNG", "scene.xml"),
        status_note="PARSED: 10 ACTUATED hinges (of 20 tree hinges; 10 passive springs) + free base, 33.31 kg. "
                    "Knee torque = <motor> gear 16 × ctrl 12.2 = 195.2 N·m (gear math matters here).",
    ),
    "toddlerbot_2xc": AssetRef(
        key="toddlerbot_2xc", repo_url="github.com/google-deepmind/mujoco_menagerie (toddlerbot_2xc)",
        license="MIT", license_note="permissive",
        local_dir=f"{REF_ROOT}/menagerie/toddlerbot_2xc",
        model_path=f"{REF_ROOT}/menagerie/toddlerbot_2xc/toddlerbot_2xc.xml", model_format="mjcf",
        extra_formats=("STL", "render PNG", "scene.xml"),
        status_note="PARSED: 30 hinge DOF + free base, 3.45 kg (smallest in the set). No torque caps in MJCF "
                    "→ honest gap.",
    ),

    # ── robot_descriptions cache locals (~/.cache/robot_descriptions; per-upstream licenses) ────────
    "atlas_v4": AssetRef(
        key="atlas_v4", repo_url="roboschool (OpenAI) via robot_descriptions atlas_v4_description",
        license="BSD (roboschool)", license_note="permissive",
        local_dir=f"{RD_ROOT}/roboschool/roboschool/models_robot/atlas_description",
        model_path=f"{RD_ROOT}/roboschool/roboschool/models_robot/atlas_description/urdf/"
                   "atlas_v4_with_multisense.urdf",
        model_format="urdf", extra_formats=("URDF",),
        status_note="PARSED: 30 revolute DOF, 182.4 kg, 30 <limit effort> caps (HYDRAULIC knee 890 N·m — the "
                    "high-torque anchor). 29 mesh files referenced but not shipped in roboschool's tree.",
    ),
    "valkyrie": AssetRef(
        key="valkyrie", repo_url="nasa-urdf-robots via robot_descriptions valkyrie_description",
        license="NASA / BSD-style", license_note="permissive (NASA open release)",
        local_dir=f"{RD_ROOT}/nasa-urdf-robots/val_description",
        model_path=f"{RD_ROOT}/nasa-urdf-robots/val_description/model/robots/valkyrie_sim.urdf",
        model_format="urdf", extra_formats=("URDF", "meshes"),
        status_note="PARSED: 59 revolute DOF (finger-inflated; ~32 body), 135.9 kg, knee 350 N·m from "
                    "<limit effort>. 2 links without declared inertia.",
    ),
    "gr1": AssetRef(
        key="gr1", repo_url="Wiki-GRx-Models via robot_descriptions gr1_description",
        license="Apache-2.0", license_note="permissive",
        local_dir=f"{RD_ROOT}/Wiki-GRx-Models/GRX/GR1/GR1T1",
        model_path=f"{RD_ROOT}/Wiki-GRx-Models/GRX/GR1/GR1T1/urdf/GR1T1_nohand.urdf",
        model_format="urdf", extra_formats=("URDF", "meshes"),
        status_note="PARSED: 32 revolute DOF (no-hand variant), 52.83 kg, knee 225 N·m from <limit effort>.",
    ),
    "h1_2": AssetRef(
        key="h1_2", repo_url="unitree_ros via robot_descriptions h1_2_mj_description",
        license="BSD-3-Clause", license_note="permissive",
        local_dir=f"{RD_ROOT}/unitree_ros/robots/h1_2_description",
        model_path=f"{RD_ROOT}/unitree_ros/robots/h1_2_description/h1_2.xml",
        model_format="mjcf", extra_formats=("MJCF", "meshes"),
        status_note="PARSED: 51 hinge DOF + free base (incl. wrists/hands), 67.37 kg, knee 300 N·m from "
                    "actuatorfrcrange.",
    ),
    "jvrc1": AssetRef(
        key="jvrc1", repo_url="robot_descriptions jvrc_mj_description",
        license="BSD-2-Clause", license_note="permissive",
        local_dir=f"{RD_ROOT}/jvrc_mj_description",
        model_path=f"{RD_ROOT}/jvrc_mj_description/xml/jvrc1.xml",
        model_format="mjcf", extra_formats=("MJCF", "meshes"),
        status_note="PARSED: 44 hinge DOF + free base, 62.40 kg. No per-joint torque caps in the MJCF → gap.",
    ),
    "draco3": AssetRef(
        key="draco3", repo_url="apptronik via robot_descriptions draco3_description",
        license="BSD/Apache", license_note="permissive",
        local_dir=f"{RD_ROOT}/draco3_description",
        model_path=f"{RD_ROOT}/draco3_description/urdf/draco3.urdf",
        model_format="urdf", extra_formats=("URDF", "meshes"),
        status_note="PARSED: 27 revolute DOF, 36.52 kg, knee_fe 40.85 N·m PER segment (parallel jp+jd → "
                    "~81.7 N·m effective) from <limit effort>. 8 links without declared inertia.",
    ),
    "icub": AssetRef(
        key="icub", repo_url="icub-models via robot_descriptions icub_description",
        license="CC/GPL-style", license_note="copyleft-ish — reference/research safe",
        local_dir=f"{RD_ROOT}/icub-models/iCub/robots/iCubGazeboV2_5",
        model_path=f"{RD_ROOT}/icub-models/iCub/robots/iCubGazeboV2_5/model.urdf",
        model_format="urdf", extra_formats=("URDF", "meshes"),
        status_note="PARSED: 32 revolute DOF, 33.06 kg. DATA QUALITY: most joints ship effort=50000 sentinels "
                    "(parser gates them); only legs carry real caps (knee 37 N·m). 150 links w/o declared inertia.",
    ),
    "ergocub": AssetRef(
        key="ergocub", repo_url="ergocub-software via robot_descriptions ergocub_description",
        license="BSD-3-Clause", license_note="permissive",
        local_dir=f"{RD_ROOT}/ergocub-software/urdf/ergoCub/robots/ergoCubSN002",
        model_path=f"{RD_ROOT}/ergocub-software/urdf/ergoCub/robots/ergoCubSN002/model.urdf",
        model_format="urdf", extra_formats=("URDF", "meshes"),
        status_note="PARSED: 57 revolute DOF, 57.0 kg. DATA QUALITY: every joint ships effort=1e9 sentinels "
                    "(parser gates them → torque is an honest gap). 138 links w/o declared inertia.",
    ),
}


#: The original in-house references (the "7"), URDF/MJCF-native first, spec-only last.
_INHOUSE = ["tienkung", "berkeley_lite", "asimov", "agiloped", "fourier_n1", "kbot", "inmoov"]
#: Robots ingested 2026-06-24 from the local MuJoCo-Menagerie clone (§A of the MANIFEST).
_MENAGERIE = ["unitree_g1", "unitree_h1", "booster_t1", "berkeley_humanoid", "apptronik_apollo",
              "pal_talos", "pndbotics_adam_lite", "robotis_op3", "agility_cassie", "toddlerbot_2xc"]
#: Robots ingested 2026-06-24 from the robot_descriptions cache (§B of the MANIFEST).
_ROBOT_DESCRIPTIONS = ["atlas_v4", "valkyrie", "gr1", "h1_2", "jvrc1", "draco3", "icub", "ergocub"]


def robots() -> list[str]:
    """Every catalogued robot key, in priority order (in-house first, then Menagerie, then
    robot_descriptions). 25 entries: the original 7 + 18 ingested 2026-06-24."""
    return [*_INHOUSE, *_MENAGERIE, *_ROBOT_DESCRIPTIONS]


def native_model_robots() -> list[str]:
    """Keys whose downloaded asset has a machine-readable URDF/MJCF the parser can validate."""
    return [k for k in robots() if ASSETS[k].model_path is not None]
