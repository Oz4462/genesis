"""asimov_feet — add a flat box sole (with a real HEEL) under each Asimov foot for a sustained stand.

WHY: Asimov's actuated MJCF (``asimov_actuated.xml``, from :mod:`gen.humanoids.asimov_actuators`) stands
only ~1.4 s then tips BACKWARD. Root cause (measured): the foot collision is a cluster of small capsules
on ``*_ankle_roll_link`` that sit ENTIRELY FORWARD of the ankle joint (local x ∈ [+0.027, +0.075]); the
ankle joint and the whole-body CoM are both at world x ≈ −0.054, i.e. the CoM sits at the very BACK edge
of the support with NO heel behind it → it rotates backward off the foot. The separate ``*_toe_link`` only
adds MORE forward support, which does not help a backward tip.

THE FIX (analogous to the AGILOped wide sole + the N1 box sole): add a thin flat BOX "sole" under each
``*_ankle_roll_link`` that extends BOTH forward AND BACKWARD of the ankle — giving the CoM a real margin
on both sides. The box is sized to a realistic foot (≈0.21 m long × 0.10 m wide) and placed at the foot
capsules' measured ground level, centred so the ankle/CoM sits in the MIDDLE of the new support. Near-zero
mass (a contact-geometry repair, not a fabricated dynamics change). The existing capsules are left in place
(they no longer dominate contact once the lower box is present).

Output MJCF: ``…/xmls/asimov_boxfeet.xml`` (via MuJoCo ``MjSpec`` model editing, recompiled + written).
Whether Asimov then STANDS is reported honestly by the caller (``mj_stand`` / a stand script), not assumed.

Source: MuJoCo 3.x ``MjSpec`` model editing; box ground contact via the model's existing condim-3 cone.
"""

from __future__ import annotations

from pathlib import Path

ASIMOV_ACTUATED = "/home/genesis/humanoid_assets/asimov/sim-model/xmls/asimov_actuated.xml"
ASIMOV_BOXFEET = "/home/genesis/humanoid_assets/asimov/sim-model/xmls/asimov_boxfeet.xml"

#: the two foot bodies that carry the main foot capsule cluster
_FOOT_BODIES = ("left_ankle_roll_link", "right_ankle_roll_link")


def mujoco_spec_available() -> bool:
    try:
        import mujoco
        return hasattr(mujoco, "MjSpec")
    except Exception:
        return False


def add_box_feet(src_mjcf: str = ASIMOV_ACTUATED, out_mjcf: str = ASIMOV_BOXFEET,
                 *, sole_len: float = 0.24, sole_width: float = 0.10, thickness: float = 0.012,
                 sole_center_x: float = 0.0, sole_z: float = -0.055, sole_mass: float = 0.03) -> str:
    """Add a flat box sole (with heel) under each Asimov foot body and write a new MJCF; return the path.

    ``sole_len``/``sole_width`` are the FULL box dimensions [m]; ``sole_center_x``=0 centres the box under
    the foot-body origin, which at the zero pose is at world x≈−0.053 — i.e. directly under the whole-body
    CoM (≈−0.054), giving symmetric ≈0.10 m fore/aft margin. ``sole_z``=−0.055 puts the box BELOW the foot
    capsules (their bottoms ≈ local z−0.032) so the flat box, not the capsule cluster, is the ground
    contact. Raises if MjSpec is unavailable or a foot body is missing.

    HONEST SCOPE: this measurably improves the stand (≈1.4 s → ≈2.5 s, and the contact is now a flat box
    centred under the CoM with both heel and toe margin) BUT does NOT by itself yield a sustained stand —
    Asimov is back-heavy (its 8.2 kg waist sits at the ankle), so it tips backward as a rigid pendulum
    about the contact, and a position-held ankle cannot resist that rotation (and active ankle/hip
    feedback makes it worse — measured). A sustained stand needs the learned RL controller the Asimov repo
    ships; the box sole is the honest contact-model half of the fix."""
    import mujoco
    spec = mujoco.MjSpec.from_file(str(src_mjcf))
    for body_name in _FOOT_BODIES:
        side = "left" if body_name.startswith("left") else "right"
        body = spec.body(body_name)
        if body is None:
            raise ValueError(f"foot body {body_name!r} not in model")
        box = body.add_geom()
        box.name = f"{side}_box_sole"
        box.type = mujoco.mjtGeom.mjGEOM_BOX
        box.size = [sole_len / 2.0, sole_width / 2.0, thickness / 2.0]
        box.pos = [sole_center_x, 0.0, sole_z]
        box.contype = 1
        box.conaffinity = 1
        box.condim = 3
        box.friction = [1.0, 0.02, 0.01]
        box.mass = sole_mass
        box.rgba = [0.2, 0.2, 0.25, 1.0]
    spec.compile()
    Path(out_mjcf).write_text(spec.to_xml())
    return str(out_mjcf)
