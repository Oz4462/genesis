"""agiloped_feet — give the AGILOped (NimbRo-OP ``nimbro_new`` lineage) model a real flat foot to stand on.

The shipped AGILOped URDF has no usable sole: the only collision geometry near the ground is the
``*_ankle_link`` STL, which is the ankle MOTOR BRACKET (a ~0.14 × 0.09 × 0.10 m 3-D chunk), not a flat
foot. The ``*_foot_link`` / ``*_foot_plane_link`` links that SHOULD be the soles are degenerate 2–3 mm
reference slabs with no real collision. As a result the model makes zero stable ground contact in a
neutral stance and topples — measured, rendered (a documented geometry blocker, not a harness bug; Berkeley
and Tien Kung stand in the identical env).

The real robot has rubber foot pads under the ankle brackets; they are simply absent from the printed-part
STL. This module adds them back: a thin flat collision+visual BOX "sole" rigidly fixed under each
``*_ankle_link``, sized to the bracket's measured footprint and placed at the bracket's lowest extent. This
is a collision-geometry REPAIR (the analogue of the CoACD convex-foot pass for Tien Kung), not a fabricated
dynamics change — the box has near-zero mass so it does not alter the (already inertia-repaired) mass model.

Output URDF: ``…/nimbro_new_repaired_noparallel_feet.urdf``. The added soles let the model be placed with
flat feet on the ground; whether it then STANDS is reported honestly by the balance env / drop test
(:mod:`gen.humanoids.balance_env`), never assumed here.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FlatFootSpec:
    """A flat box sole to fix under a link. Dimensions [m]; ``z_bottom`` is the sole's centre z in the
    parent link frame (place at the link's measured lowest extent + half the pad thickness).

    ``roll``/``pitch`` [rad] rotate the sole in the parent-link fixed joint. Default 0 keeps the original
    behaviour; they exist because the AGILOped ``ankle_link`` carries a baked ±29° roll (from the −44°
    hip-chain splay that the un-splay pose only partly cancels), so a sole attached with rpy=0 inherits
    that tilt and is NOT flat on the ground. Setting ``roll`` to the negative of the link's baked roll
    makes the sole truly flat, which is what gives a real (wide) support polygon."""

    parent_link: str
    size_x: float
    size_y: float
    thickness: float
    x: float
    y: float
    z_bottom: float
    mass: float = 0.02  #: near-zero so it does not perturb the inertia-repaired mass model
    roll: float = 0.0   #: sole roll [rad] in the fixed joint (counter the parent link's baked roll)
    pitch: float = 0.0  #: sole pitch [rad] in the fixed joint


#: Measured AGILOped sole specs (from the ``left_ankle_link`` STL footprint, used for both feet since the
#: right reuses the left mesh mirrored): footprint ~0.142 (fore/aft, +X) × 0.089 (lateral) at the bracket
#: bottom z ≈ −0.09 in the ankle-link frame, recentred on the footprint (x≈0.04, y≈0).
AGILOPED_FOOT_SPECS: tuple[FlatFootSpec, ...] = (
    FlatFootSpec("left_ankle_link",  size_x=0.135, size_y=0.085, thickness=0.012, x=0.040, y=0.0, z_bottom=-0.090),
    FlatFootSpec("right_ankle_link", size_x=0.135, size_y=0.085, thickness=0.012, x=0.040, y=0.0, z_bottom=-0.090),
)

#: The repaired-noparallel AGILOped URDF this module starts from, and the output it writes.
AGILOPED_NOPARALLEL_URDF = (
    "/home/genesis/humanoid_assets/agiloped/nimbro_op_model/robots/nimbro_new_repaired_noparallel.urdf")
AGILOPED_FEET_URDF = (
    "/home/genesis/humanoid_assets/agiloped/nimbro_op_model/robots/nimbro_new_repaired_noparallel_feet.urdf")


def _box_inertia(mass: float, sx: float, sy: float, sz: float) -> tuple[float, float, float]:
    ixx = mass * (sy * sy + sz * sz) / 12.0
    iyy = mass * (sx * sx + sz * sz) / 12.0
    izz = mass * (sx * sx + sy * sy) / 12.0
    return ixx, iyy, izz


def add_flat_feet(urdf_in: str = AGILOPED_NOPARALLEL_URDF, urdf_out: str = AGILOPED_FEET_URDF,
                  specs: tuple[FlatFootSpec, ...] = AGILOPED_FOOT_SPECS) -> str:
    """Write a copy of ``urdf_in`` with a flat box sole fixed under each spec's parent link.

    For each :class:`FlatFootSpec`, a new child link ``<parent>_sole`` (a thin box with collision + visual +
    a tiny inertial) is added and rigidly attached to the parent via a fixed joint at the spec's position.
    Returns ``urdf_out``. Raises if ``urdf_in`` is missing or a parent link is absent (fail-loud)."""
    src = Path(urdf_in)
    if not src.is_file():
        raise FileNotFoundError(f"AGILOped URDF not found: {urdf_in}")
    tree = ET.parse(src)
    root = tree.getroot()
    link_names = {ln.get("name") for ln in root.findall("link")}

    for spec in specs:
        if spec.parent_link not in link_names:
            raise ValueError(f"parent link {spec.parent_link!r} not in URDF; have {sorted(link_names)[:8]}…")
        sole_name = f"{spec.parent_link}_sole"
        cz = spec.z_bottom + spec.thickness / 2.0  # box centre = bottom + half thickness
        size = f"{spec.size_x} {spec.size_y} {spec.thickness}"
        ixx, iyy, izz = _box_inertia(spec.mass, spec.size_x, spec.size_y, spec.thickness)

        link = ET.SubElement(root, "link", {"name": sole_name})
        inertial = ET.SubElement(link, "inertial")
        ET.SubElement(inertial, "origin", {"xyz": "0 0 0", "rpy": "0 0 0"})
        ET.SubElement(inertial, "mass", {"value": f"{spec.mass}"})
        ET.SubElement(inertial, "inertia", {"ixx": f"{ixx:.8g}", "ixy": "0", "ixz": "0",
                                            "iyy": f"{iyy:.8g}", "iyz": "0", "izz": f"{izz:.8g}"})
        for tag in ("collision", "visual"):
            el = ET.SubElement(link, tag)
            ET.SubElement(el, "origin", {"xyz": "0 0 0", "rpy": "0 0 0"})
            geom = ET.SubElement(el, "geometry")
            ET.SubElement(geom, "box", {"size": size})
        joint = ET.SubElement(root, "joint", {"name": f"{sole_name}_fixed", "type": "fixed"})
        ET.SubElement(joint, "parent", {"link": spec.parent_link})
        ET.SubElement(joint, "child", {"link": sole_name})
        ET.SubElement(joint, "origin", {"xyz": f"{spec.x} {spec.y} {cz}",
                                        "rpy": f"{spec.roll} {spec.pitch} 0"})

    out = Path(urdf_out)
    tree.write(out, encoding="utf-8", xml_declaration=True)
    return str(out)


if __name__ == "__main__":
    print(add_flat_feet())
