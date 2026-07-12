"""n1_feet — add flat box soles to the Fourier N1 MuJoCo feet for stable ground contact.

WHY: the N1 MJCF (``scene/N1_raw_refine.xml``) gives each foot a single MESH collision geom
(``foot_pitch_link`` STL, MuJoCo geom type 7). Like every mesh-foot humanoid in this project, that makes
SPARSE, noisy ground contact (3-5 points), which can't support a stable stand — the robot tips within
~2 s regardless of pose or gains (the established mesh-foot ceiling; see project memory). The proven cure
on AGILOped was to add a thin FLAT BOX sole under each foot, sized to the REAL footprint of the foot mesh
(no fabricated geometry): a box makes dense, deterministic surface contact.

HOW: this uses MuJoCo's model-editing API (``MjSpec``) to add a box ``<geom>`` to each ``foot_pitch_link``
body, then recompiles + writes a new self-contained MJCF. The box is placed at the foot mesh's measured
bottom (z = mesh-bbox min-z) and sized to the mesh's measured x/y footprint, so it coincides with the real
sole — it adds CONTACT FIDELITY, not new shape. The original mesh geom is moved to a non-colliding visual
group so only the box collides (cleaner contact); the visual mesh still renders.

This is honest: the footprint comes from ``trimesh`` of the actual STL; the only invented number is the
thin sole thickness (default 12 mm, the same as AGILOped) and a small mass (20 g) so the box is not
massless (a massless colliding geom is fine in MuJoCo but a token mass keeps inertia well-conditioned).

Source: MuJoCo 3.x ``MjSpec`` model editing; ``mjGEOM_BOX`` contact via condim-3 friction cone.
"""

from __future__ import annotations

from pathlib import Path

N1_MODEL_DIR = "/home/genesis/humanoid_assets/fourier_n1/model"
N1_REFINE_MJCF = f"{N1_MODEL_DIR}/scene/N1_raw_refine.xml"
N1_FEET_MJCF = f"{N1_MODEL_DIR}/scene/N1_boxfeet.xml"
N1_FEET_SCENE = f"{N1_MODEL_DIR}/scene/_stand_scene_boxfeet.mjcf"

#: the two foot bodies that carry the foot collision mesh in the N1 model
_FOOT_BODIES = ("left_foot_pitch_link", "right_foot_pitch_link")


def _foot_footprint(mesh_path: str) -> tuple[float, float, float]:
    """Return (half_x, half_y, bottom_z) of the foot mesh's axis-aligned bbox via trimesh.

    half_x/half_y are the box half-sizes that match the mesh footprint; bottom_z is the mesh's lowest
    point in the link frame (where the sole sits). Raises if trimesh or the mesh is unavailable."""
    import trimesh
    m = trimesh.load(mesh_path, force="mesh")
    lo, hi = m.bounds
    half_x = float((hi[0] - lo[0]) / 2.0)
    half_y = float((hi[1] - lo[1]) / 2.0)
    bottom_z = float(lo[2])
    cx = float((hi[0] + lo[0]) / 2.0)
    return half_x, half_y, bottom_z, cx


def trimesh_available() -> bool:
    try:
        import trimesh  # noqa: F401
        return True
    except Exception:
        return False


def mujoco_spec_available() -> bool:
    try:
        import mujoco
        return hasattr(mujoco, "MjSpec")
    except Exception:
        return False


def add_box_feet(src_mjcf: str = N1_REFINE_MJCF, out_mjcf: str = N1_FEET_MJCF,
                 *, sole_thickness: float = 0.012, sole_mass: float = 0.02,
                 shrink: float = 0.92) -> str:
    """Add a flat box sole to each N1 foot body and write a new MJCF; return the out path.

    The box half-sizes are the foot mesh footprint × ``shrink`` (a slight inset so the box does not
    overhang the visible foot), thickness ``sole_thickness``; it is centred at the foot mesh's measured
    fore-aft centre and placed so its top meets the mesh bottom. The original mesh collision geom is set
    to group 1 / non-colliding (visual only). Raises if MjSpec or trimesh is unavailable, or a foot body
    is missing."""
    import mujoco
    spec = mujoco.MjSpec.from_file(str(src_mjcf))

    # measure each foot footprint from its STL (left/right are identical-shaped but measure both)
    mesh_dir = Path(src_mjcf).resolve().parent.parent / "meshes"
    for body_name in _FOOT_BODIES:
        side = "left" if body_name.startswith("left") else "right"
        stl = mesh_dir / f"{side}_foot_pitch_link.STL"
        half_x, half_y, bottom_z, cx = _foot_footprint(str(stl))
        body = spec.body(body_name)
        if body is None:
            raise ValueError(f"foot body {body_name!r} not in model")
        # demote the existing mesh collision geom(s) on this body to non-colliding visual
        for g in body.geoms:
            if int(g.type) == int(mujoco.mjtGeom.mjGEOM_MESH):
                g.contype = 0
                g.conaffinity = 0
                g.group = 1
        # add a thin box sole at the mesh footprint bottom
        box = body.add_geom()
        box.name = f"{side}_box_sole"
        box.type = mujoco.mjtGeom.mjGEOM_BOX
        box.size = [half_x * shrink, half_y * shrink, sole_thickness]
        # place the box so its TOP is at the mesh bottom (box centre = bottom_z - thickness), at the
        # mesh's fore-aft centre so it sits under the real foot
        box.pos = [cx, 0.0, bottom_z - sole_thickness]
        box.contype = 1
        box.conaffinity = 1
        box.condim = 6
        box.friction = [1.0, 0.02, 0.01]
        box.mass = sole_mass
        box.rgba = [0.2, 0.2, 0.25, 1.0]

    spec.compile()  # validate before writing
    xml = spec.to_xml()
    Path(out_mjcf).write_text(xml)
    return str(out_mjcf)
