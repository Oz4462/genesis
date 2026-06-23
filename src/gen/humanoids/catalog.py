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

from dataclasses import dataclass, field

ASSET_ROOT = "/home/genesis/humanoid_assets"


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
}


def robots() -> list[str]:
    """The catalog keys, in priority order (URDF/MJCF-native first)."""
    return ["tienkung", "berkeley_lite", "asimov", "agiloped", "fourier_n1", "kbot", "inmoov"]


def native_model_robots() -> list[str]:
    """Keys whose downloaded asset has a machine-readable URDF/MJCF the parser can validate."""
    return [k for k in robots() if ASSETS[k].model_path is not None]
