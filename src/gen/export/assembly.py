"""export/assembly — render the FINISHED, ASSEMBLED product, not just the flat parts tray.

The parts-tray OpenSCAD shows every printed part laid out side by side (good for printing); this module
shows what the owner asked for: how the robot LOOKS when fully assembled. When a spec's components carry
an ``assembly_pose`` (position + rotation in the body frame), this emits:

  * ``assembly_scad(spec)``      — an OpenSCAD ASSEMBLY view: every part placed at its pose
    (``translate([...]) rotate([...]) part();``) so OpenSCAD renders the whole standing robot.
  * ``render_assembly_png(spec, path)`` — a 3D IMAGE of the assembled robot (each part drawn as its
    bounding-box solid at its pose) via matplotlib, saved as PNG — a picture of the finished product.

Honest boundary: the 3D image draws each part as its BOUNDING-BOX block at the declared pose — a faithful
massing/silhouette of the assembled robot (legs, torso, arms, head in place), not a photorealistic render
of the filleted CSG. matplotlib is optional: ``render_assembly_png`` returns False (never a fake image) if
it is absent or the spec declares no assembly poses. Deterministic.
"""

from __future__ import annotations

import math
from pathlib import Path

from ..core.state import Component, GeometryNode, Quantity, Specification
from ._text import single_line as _single_line
from .numfmt import fmt_number as _fmt
from .openscad import _emit, _module_name


def _bbox_dims(geometry: GeometryNode | None, quantities: dict[str, Quantity]) -> tuple[float, float, float] | None:
    """(size_x, size_y, size_z) of a part's outer primitive envelope, walking to the first
    primitive: a ``box`` gives its sizes, a ``cylinder`` (2r, 2r, h), a ``sphere`` (2r, 2r, 2r).
    None if no primitive is reachable or a param is unresolvable — the caller REPORTS such
    parts (image title) instead of dropping them silently."""
    node = geometry
    while node is not None and node.kind not in ("box", "cylinder", "sphere"):
        node = node.children[0] if node.children else None
    if node is None:
        return None
    try:
        if node.kind == "box":
            return (float(quantities[node.params["size_x"]].value),
                    float(quantities[node.params["size_y"]].value),
                    float(quantities[node.params["size_z"]].value))
        r = float(quantities[node.params["radius"]].value)
        if node.kind == "cylinder":
            return (2.0 * r, 2.0 * r, float(quantities[node.params["height"]].value))
        return (2.0 * r, 2.0 * r, 2.0 * r)   # sphere
    except (KeyError, AttributeError, TypeError, ValueError):
        return None


def _placements(spec: Specification) -> list[tuple[Component, tuple[float, float, float, float, float, float]]]:
    """Resolve ``spec.assembly`` to (component, pose) pairs — a fabricated component may appear several
    times (two legs, two arms). Placements referencing an unknown or geometry-less part are skipped."""
    by_id = {c.id: c for c in spec.components}
    out: list[tuple[Component, tuple[float, float, float, float, float, float]]] = []
    for cid, x, y, z, rx, ry, rz in spec.assembly:
        comp = by_id.get(cid)
        if comp is not None and comp.geometry is not None:
            out.append((comp, (x, y, z, rx, ry, rz)))
    return out


def assembly_scad(spec: Specification) -> str | None:
    """An OpenSCAD ASSEMBLY view of the finished product, or None if the spec declares no assembly."""
    placements = _placements(spec)
    if not placements:
        return None
    quantities = {q.id: q for q in spec.quantities}
    lines = [
        "// GENESIS — ASSEMBLED view (the finished product, parts in place)",
        f"// idea: {_single_line(spec.idea)}",
        f"// run_id: {spec.run_id}",
        "",
    ]
    for comp in {c.id: c for c, _ in placements}.values():   # one module def per unique part
        geom = comp.geometry
        assert geom is not None
        lines.append("\n".join([f"module {_module_name(comp.id)}() {{", *_emit(geom, quantities, 1), "}"]))
    lines.append("\n// ---- ASSEMBLY: each part instance placed at its body-frame pose ----")
    for comp, (x, y, z, rx, ry, rz) in placements:
        lines.append(
            f"translate([{_fmt(x)}, {_fmt(y)}, {_fmt(z)}]) rotate([{_fmt(rx)}, {_fmt(ry)}, {_fmt(rz)}]) "
            f"{_module_name(comp.id)}();  // {_single_line(comp.name)}")
    return "\n".join(lines) + "\n"


def _rot_matrix(rx: float, ry: float, rz: float) -> list[list[float]]:
    """OpenSCAD rotate([rx,ry,rz]) convention: R = Rz·Ry·Rx (apply X, then Y, then Z)."""
    ax, ay, az = math.radians(rx), math.radians(ry), math.radians(rz)
    cx, sx = math.cos(ax), math.sin(ax)
    cy, sy = math.cos(ay), math.sin(ay)
    cz, sz = math.cos(az), math.sin(az)
    rxm = [[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]]
    rym = [[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]]
    rzm = [[cz, -sz, 0.0], [sz, cz, 0.0], [0.0, 0.0, 1.0]]

    def mul(a, b):
        return [[sum((a[i][k] * b[k][j] for k in range(3)), 0.0) for j in range(3)] for i in range(3)]

    return mul(rzm, mul(rym, rxm))


def _box_faces(size: tuple[float, float, float], pose: tuple[float, ...]):
    """The 6 quad faces of a box of `size`, rotated+translated by `pose` — for a 3D solid render."""
    sx, sy, sz = size
    x, y, z, rx, ry, rz = pose
    r = _rot_matrix(rx, ry, rz)
    hx, hy, hz = sx / 2.0, sy / 2.0, sz / 2.0
    corners = [(dx * hx, dy * hy, dz * hz) for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)]
    placed = []
    for cx, cy, cz in corners:
        wx = r[0][0] * cx + r[0][1] * cy + r[0][2] * cz + x
        wy = r[1][0] * cx + r[1][1] * cy + r[1][2] * cz + y
        wz = r[2][0] * cx + r[2][1] * cy + r[2][2] * cz + z
        placed.append((wx, wy, wz))
    # corner index = bit(dx)<<2 | bit(dy)<<1 | bit(dz), dx/dy/dz in {-1->0, 1->1}
    idx = {(dx, dy, dz): (dx << 2) | (dy << 1) | dz for dx in (0, 1) for dy in (0, 1) for dz in (0, 1)}
    faces_def = [
        [(0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)],  # x-
        [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)],  # x+
        [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)],  # y-
        [(0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)],  # y+
        [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)],  # z-
        [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)],  # z+
    ]
    return [[placed[idx[c]] for c in face] for face in faces_def]


def _part_color(name: str) -> str:
    n = name.lower()
    if "bein" in n or "schenkel" in n or "fuß" in n or "fuss" in n:
        return "#2C5586"   # legs — blue
    if "arm" in n or "hand" in n:
        return "#D9B36A"   # arms/hands — gold
    if "kopf" in n:
        return "#B5651D"   # head
    if "rumpf" in n:
        return "#557A46"   # torso — green
    return "#6E6E6E"        # pelvis/other — grey


def render_assembly_png(spec: Specification, path: str | Path) -> bool:
    """Render the ASSEMBLED robot to a PNG (each part its bounding-box solid at its pose —
    box/cylinder/sphere envelopes, see ``_bbox_dims``). Returns True on success; False (no fake
    image) if matplotlib is absent or the spec declares no assembly poses. A part whose envelope
    cannot be derived is NOT silently dropped: it is named in the image title as un-renderable."""
    placements = _placements(spec)
    if not placements:
        return False
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    except Exception:
        return False

    quantities = {q.id: q for q in spec.quantities}
    fig = plt.figure(figsize=(6, 9))
    ax = fig.add_subplot(111, projection="3d")
    all_pts: list[tuple[float, float, float]] = []
    skipped: list[str] = []
    for comp, pose in placements:
        dims = _bbox_dims(comp.geometry, quantities)
        if dims is None:
            skipped.append(_single_line(comp.name))
            continue
        faces = _box_faces(dims, pose)
        for f in faces:
            all_pts.extend(f)
        ax.add_collection3d(Poly3DCollection(faces, facecolor=_part_color(comp.name),
                                             edgecolor="#222222", linewidths=0.3, alpha=0.95))
    if not all_pts:
        plt.close(fig)
        return False
    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    zs = [p[2] for p in all_pts]
    # equal aspect so the robot is not distorted
    rng = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) / 2.0 or 1.0
    cx, cy, cz = (sum(v) / len(v) for v in (xs, ys, zs))
    ax.set_xlim(cx - rng, cx + rng)
    ax.set_ylim(cy - rng, cy + rng)
    ax.set_zlim(cz - rng, cz + rng)
    ax.view_init(elev=12, azim=-70)
    ax.set_axis_off()
    title = f"GENESIS — montierter Roboter\n{spec.run_id}"
    if skipped:
        # honest gap in the picture, not a silent omission
        title += f"\nnicht darstellbar (keine Primitiv-Hülle): {', '.join(sorted(set(skipped)))}"
    ax.set_title(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(str(path), dpi=130)
    plt.close(fig)
    return True
