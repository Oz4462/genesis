"""model_parser — stdlib parse of the gym-pybullet-drones drone URDFs (the dynamics ground truth).

The gym-pybullet-drones URDFs (``cf2x.urdf``, ``cf2p.urdf``, ``racer.urdf``; MIT, utiasDSL) are not
ordinary geometric URDFs: they carry a ``<properties>`` element with the EMPIRICALLY-FITTED motor
constants the simulator's dynamics run on —

    T_motor = k_f · RPM²        (thrust per rotor, N)
    Q_motor = k_m · RPM²        (reaction torque per rotor, N·m)

plus the rest mass, arm length L, propeller radius, and the published thrust-to-weight ratio. From
these the simulator derives (BaseAviary.py, lines 117–128, verbatim):

    weight        = g · m
    HOVER_RPM     = sqrt(weight / (4·k_f))                 # 4 rotors share the weight at hover
    MAX_RPM       = sqrt(thrust2weight · weight / (4·k_f))
    MAX_THRUST    = 4·k_f·MAX_RPM²  (= thrust2weight · weight, by construction)

This module reproduces exactly that arithmetic from the parsed file, giving GENESIS a SECOND,
model-independent ground truth for the flight axes: the per-rotor hover thrust and the maximum total
thrust a real-dynamics drone produces, against which ``flight.rotor_hover_check`` (which sizes from a
declared ``max_total_thrust``) and the momentum-theory induced power can be cross-validated.

Pure stdlib (``xml.etree``), offline, deterministic. The repo is pre-cloned to
``/home/genesis/drone_data/gym-pybullet-drones``; ``DRONE_URDF_DIR`` points at its assets. A missing
file raises ``FileNotFoundError`` (loud) rather than returning a fabricated default — the no-silent-
defaults rule. The thrust-coefficient k_f and the standard gravity g=9.8 used by the simulator are
kept as the simulator uses them (the simulator hard-codes 9.8, not 9.80665; we mirror its value so
the cross-check is byte-faithful and document the 0.07 % difference from the CGPM constant).
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from xml.etree import ElementTree as ET

#: The gym-pybullet-drones assets dir (MIT, github.com/utiasDSL/gym-pybullet-drones), pre-cloned.
DRONE_URDF_DIR = "/home/genesis/drone_data/gym-pybullet-drones/gym_pybullet_drones/assets"

#: The gravitational constant the simulator hard-codes (BaseAviary.py:74 ``self.G = 9.8``). Kept at the
#: simulator's value so the parsed ground truth matches the simulator byte-for-byte; this is 0.07 %
#: below the CGPM standard 9.80665 used elsewhere in GENESIS (``flight.STANDARD_GRAVITY``), an
#: intentional, documented difference (the cross-check is against the SIMULATOR's numbers).
SIM_GRAVITY = 9.8

#: gym-pybullet-drones quadcopters always have 4 rotors (the four ``propN_link`` in every URDF).
N_ROTORS = 4


@dataclass(frozen=True)
class DroneModel:
    """The dynamics facts parsed from one gym-pybullet-drones URDF, plus the simulator's derived
    thrust/RPM figures recomputed from them (the ground truth the flight axes are checked against)."""
    name: str                       #: the URDF ``<robot name>``
    source_file: str                #: absolute path the values were parsed from
    mass_kg: float                  #: base_link <mass>
    arm_length_m: float             #: <properties arm=…> (motor-to-centre)
    prop_radius_m: float            #: <properties prop_radius=…>
    kf: float                       #: thrust coefficient (T = k_f·RPM²) [N/(rev/min)²]
    km: float                       #: torque coefficient (Q = k_m·RPM²) [N·m/(rev/min)²]
    thrust2weight: float            #: published max-thrust / weight ratio
    # ── derived, exactly as BaseAviary does it ──
    weight_n: float                 #: g·m
    hover_rpm: float                #: sqrt(weight/(4·k_f))
    max_rpm: float                  #: sqrt(t2w·weight/(4·k_f))
    hover_thrust_per_rotor_n: float #: k_f·HOVER_RPM²
    max_thrust_per_rotor_n: float   #: k_f·MAX_RPM²
    max_total_thrust_n: float       #: 4·k_f·MAX_RPM² (≡ t2w·weight)
    disk_area_m2: float             #: π·prop_radius² (one rotor)

    @property
    def prop_diameter_m(self) -> float:
        """Propeller diameter [m] = 2·prop_radius."""
        return 2.0 * self.prop_radius_m


def _require(props: dict[str, str], key: str, path: str) -> str:
    """Fetch a required ``<properties>`` attribute or fail loud (no silent default for a dynamics fact)."""
    if key not in props:
        raise ValueError(f"gym-pybullet-drones URDF {path!r} has no <properties {key}=…> — cannot "
                         f"derive the dynamics ground truth without it")
    return props[key]


def parse_drone_urdf(path: str) -> DroneModel:
    """Parse a gym-pybullet-drones URDF and recompute the simulator's derived thrust/RPM figures.

    Reads the base_link mass and the ``<properties>`` motor constants, then reproduces BaseAviary's
    ``HOVER_RPM``/``MAX_RPM``/``MAX_THRUST`` arithmetic verbatim. Raises ``FileNotFoundError`` if the
    file is absent (loud, not a fabricated default) and ``ValueError`` if a required dynamics attribute
    is missing or non-physical (non-positive mass / k_f / radius)."""
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"drone URDF not found: {path}. Clone gym-pybullet-drones into /home/genesis/drone_data/ "
            f"(MIT, github.com/utiasDSL/gym-pybullet-drones).")
    root = ET.parse(path).getroot()
    name = root.get("name", os.path.basename(path))

    props_el = root.find("properties")
    if props_el is None:
        raise ValueError(f"{path!r} has no <properties> element — not a gym-pybullet-drones dynamics URDF")
    props = dict(props_el.attrib)

    # base_link mass
    mass = None
    for link in root.findall("link"):
        if link.get("name") == "base_link":
            m_el = link.find("inertial/mass")
            if m_el is not None:
                mass = float(m_el.get("value"))
            break
    if mass is None or mass <= 0.0:
        raise ValueError(f"{path!r} base_link has no positive <mass>")

    arm = float(_require(props, "arm", path))
    prop_radius = float(_require(props, "prop_radius", path))
    kf = float(_require(props, "kf", path))
    km = float(_require(props, "km", path))
    t2w = float(_require(props, "thrust2weight", path))
    if kf <= 0.0 or prop_radius <= 0.0 or t2w <= 0.0:
        raise ValueError(f"{path!r} has a non-physical k_f / prop_radius / thrust2weight")

    weight = SIM_GRAVITY * mass
    hover_rpm = math.sqrt(weight / (N_ROTORS * kf))
    max_rpm = math.sqrt(t2w * weight / (N_ROTORS * kf))
    hover_thrust_per = kf * hover_rpm ** 2
    max_thrust_per = kf * max_rpm ** 2
    max_total_thrust = N_ROTORS * max_thrust_per
    disk_area = math.pi * prop_radius ** 2

    return DroneModel(
        name=name, source_file=path, mass_kg=mass, arm_length_m=arm, prop_radius_m=prop_radius,
        kf=kf, km=km, thrust2weight=t2w, weight_n=weight, hover_rpm=hover_rpm, max_rpm=max_rpm,
        hover_thrust_per_rotor_n=hover_thrust_per, max_thrust_per_rotor_n=max_thrust_per,
        max_total_thrust_n=max_total_thrust, disk_area_m2=disk_area,
    )


def parse_known() -> dict[str, DroneModel]:
    """Parse every gym-pybullet-drones URDF present in ``DRONE_URDF_DIR``.

    Returns a name→model map for the files that exist (``cf2x``, ``cf2p``, ``racer``); silently skips a
    missing file so the function works whether or not the optional clone is present, but a file that IS
    present and malformed still raises (a corrupt dynamics file is a real error, not a missing-asset)."""
    out: dict[str, DroneModel] = {}
    for fn in ("cf2x.urdf", "cf2p.urdf", "racer.urdf"):
        path = os.path.join(DRONE_URDF_DIR, fn)
        if os.path.isfile(path):
            m = parse_drone_urdf(path)
            out[fn[:-5]] = m
    return out
