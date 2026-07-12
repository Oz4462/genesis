"""asimov_actuators — add position (PD-servo) actuators to the Asimov v1 MJCF so it can be balance-driven.

The shipped Asimov MuJoCo model (``sim-model/xmls/asimov.xml``) loads clean in MuJoCo 3.10 but defines
ZERO ``<actuator>`` elements (``nu == 0``): every joint is passive, so the model can be dropped but not
HELD in a pose or balanced. (The repo's RL stack presumably injects actuators at load time / drives
``qfrc_applied`` directly; the static XML has none.) This module writes a variant XML that adds a
``<position>`` actuator (an implicit PD position servo, MuJoCo's stable analogue of PyBullet's
POSITION_CONTROL) for the lower-body joints needed to stand: both legs' hip pitch/roll/yaw, knee, and
ankle pitch/roll, plus the waist yaw — 13 actuators. The toe joints (passive return springs) and the arms
(the model's deliberate ``passive_upper`` damped springs) are left passive, matching the design intent.

Gains: ``kp`` is the position gain (N·m per rad of error) and ``kv`` the damping (N·m per rad/s), applied
via ``<position kp=… kv=…>``; ``forcerange`` caps the torque. These are chosen to give a stiff but stable
hold (verified the model holds a pose and can be commanded). This is an ADDITIVE actuation-model change
(no geometry/inertia altered), needed because the brief asks for Asimov to be balance-driven and the
in-engine ``insim_mujoco`` statics/drop path explicitly does not add actuators.

Output: ``…/xmls/asimov_actuated.xml`` (writes next to the source so its relative ``meshdir`` still
resolves). Whether the actuated model then STANDS is reported honestly by a drop/hold test, never assumed.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

ASIMOV_XML = "/home/genesis/humanoid_assets/asimov/sim-model/xmls/asimov.xml"
ASIMOV_ACTUATED_XML = "/home/genesis/humanoid_assets/asimov/sim-model/xmls/asimov_actuated.xml"

#: Lower-body joints to actuate (the standing/balance set) with a per-joint torque cap [N·m]. Caps are
#: sized roughly to the joint's role (hips/knees strong, ankles/waist moderate) — generous enough to hold
#: a stance, not a precise vendor spec (Asimov's actuator torques are not all published per joint).
ASIMOV_ACTUATED_JOINTS: dict[str, float] = {
    "left_hip_pitch_joint": 120.0, "left_hip_roll_joint": 120.0, "left_hip_yaw_joint": 80.0,
    "left_knee_joint": 120.0, "left_ankle_pitch_joint": 60.0, "left_ankle_roll_joint": 40.0,
    "right_hip_pitch_joint": 120.0, "right_hip_roll_joint": 120.0, "right_hip_yaw_joint": 80.0,
    "right_knee_joint": 120.0, "right_ankle_pitch_joint": 60.0, "right_ankle_roll_joint": 40.0,
    "waist_yaw_joint": 80.0,
}


def add_position_actuators(xml_in: str = ASIMOV_XML, xml_out: str = ASIMOV_ACTUATED_XML,
                           joints: dict[str, float] | None = None,
                           kp: float = 150.0, kv: float = 8.0) -> str:
    """Write a copy of the Asimov MJCF with a ``<position>`` PD actuator per joint in ``joints``.

    ``joints`` maps joint name → torque cap [N·m] (default :data:`ASIMOV_ACTUATED_JOINTS`). ``kp``/``kv``
    are the position/velocity gains shared by all actuators. Validates that every named joint exists in the
    model (fail-loud) and that the source has no existing ``<actuator>`` for them (so this is purely
    additive). Returns ``xml_out``."""
    if joints is None:
        joints = ASIMOV_ACTUATED_JOINTS
    src = Path(xml_in)
    if not src.is_file():
        raise FileNotFoundError(f"Asimov MJCF not found: {xml_in}")
    tree = ET.parse(src)
    root = tree.getroot()

    have = {j.get("name") for j in root.iter("joint")}
    missing = [j for j in joints if j not in have]
    if missing:
        raise ValueError(f"joints not in Asimov MJCF: {missing}")
    existing_act = root.find("actuator")
    if existing_act is not None and len(existing_act):
        raise ValueError("Asimov MJCF already has <actuator> elements — refusing to double-add")

    act = existing_act if existing_act is not None else ET.SubElement(root, "actuator")
    for jname, fmax in joints.items():
        ET.SubElement(act, "position", {
            "name": f"{jname}_act", "joint": jname,
            "kp": f"{kp}", "kv": f"{kv}",
            "forcerange": f"{-fmax} {fmax}",
        })

    out = Path(xml_out)
    tree.write(out, encoding="utf-8", xml_declaration=True)
    return str(out)


if __name__ == "__main__":
    print(add_position_actuators())
