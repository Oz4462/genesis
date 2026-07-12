"""coacd_feet — convex-decompose a humanoid's foot meshes into simulation-stable collision geometry.

WHY this exists: the bundled humanoid URDFs (e.g. Tien Kung) use the FULL, non-watertight foot mesh as
the ``<collision>`` geometry. PyBullet cannot use a concave triangle soup as a stable dynamic collider —
it falls back to the single convex hull of the mesh, which rounds off the flat sole and makes SPARSE,
noisy ground contact. Measured consequence (see :mod:`gen.humanoids.balance_env`): the live contact is
too sparse to use as a control signal, and any ankle motion momentarily breaks the marginal contact, so
ankle-strategy balance does worse than a passive hold. The standard fix is to replace the one concave
collision mesh with a set of CONVEX pieces (a convex decomposition) that PyBullet contacts robustly.

This module wraps CoACD (``import coacd``) to do exactly that, then rewrites the URDF so the foot link's
``<collision>`` becomes one ``<collision>`` per convex part (the ``<visual>`` keeps the original mesh, so
the robot still looks right). Two decomposition modes are offered, both honest about their trade-off:

  * ``mode="sole"`` (default, recommended for a flat-footed biped): isolate the BOTTOM slab of the foot
    mesh (the part within ``sole_thickness`` of the lowest point) and convex-decompose only that. This
    spends every convex hull on the actual contact surface, giving a dense, near-flat sole pad — which is
    what matters for stable standing. The non-contact upper bracket is not collided (it never touches the
    floor while standing), which is fine and much cheaper to simulate.
  * ``mode="full"``: convex-decompose the WHOLE foot mesh (capped to ``max_convex_hull`` pieces). More
    physically complete (the whole foot can collide), but most hulls land on the non-contact bracket and
    only 1-2 reach the sole — denser contact than the single hull, but not as flat-sole-focused as
    ``"sole"`` and slower.

Everything is deterministic (CoACD ``seed=0``), writes OUTSIDE the repo (next to the source meshes under
a ``coacd_feet/`` sibling dir), and is fail-loud (raises if CoACD is missing or a mesh/foot is absent) —
no silent fallback to the broken mesh collision (CLAUDE.md: no silent defaults for factual things).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


def coacd_available() -> bool:
    """True iff the ``coacd`` convex-decomposition package can be imported (optional dependency)."""
    try:
        import coacd  # noqa: F401
        return True
    except Exception:
        return False


#: TienKung lite URDF: the two sole-bearing links and the foot meshes they reference (in the URDF dir).
TIENKUNG_FEET = ("ankle_roll_l_link", "ankle_roll_r_link")


@dataclass(frozen=True)
class FootDecomp:
    """The convex decomposition of one foot link's collision mesh."""

    link: str                       #: URDF link whose <collision> was replaced
    mesh_rel: str                   #: original collision mesh filename (as referenced in the URDF)
    parts: tuple[str, ...]          #: written convex-part mesh paths (absolute), one <collision> each
    n_parts: int
    sole_z: float                   #: lowest z of the source mesh [m] (the sole plane, link frame)
    n_sole_parts: int               #: how many parts reach within 5 mm of the sole (the contact patch)


@dataclass(frozen=True)
class CoacdFeetResult:
    """Outcome of building a convex-foot URDF variant: the new URDF + per-foot decomposition records."""

    src_urdf: str
    out_urdf: str
    mode: str
    feet: tuple[FootDecomp, ...]
    parts_dir: str

    def summary(self) -> dict:
        return {
            "out_urdf": self.out_urdf, "mode": self.mode,
            "feet": {fd.link: {"parts": fd.n_parts, "sole_parts": fd.n_sole_parts} for fd in self.feet},
            "parts_dir": self.parts_dir,
        }


def _load_trimesh(path: Path):
    import trimesh
    m = trimesh.load(str(path), force="mesh")
    if m.is_empty or len(m.vertices) == 0:
        raise ValueError(f"mesh has no geometry: {path}")
    return m


def _sole_slab(mesh, sole_thickness: float):
    """Return a sub-mesh of the faces whose centroid is within ``sole_thickness`` of the lowest z.

    This isolates the bottom contact plate of the foot. Falls back to the whole mesh if the slab is empty
    (degenerate mesh) so the caller still gets a (single-hull) collider rather than nothing."""
    import trimesh
    zmin = float(mesh.bounds[0][2])
    tri_z = mesh.triangles[:, :, 2].mean(axis=1)  # per-face mean z
    keep = tri_z <= zmin + sole_thickness
    if not keep.any():
        return mesh
    faces = mesh.faces[keep]
    sub = trimesh.Trimesh(vertices=mesh.vertices, faces=faces, process=True)
    sub.remove_unreferenced_vertices()
    if len(sub.vertices) < 4:
        return mesh
    return sub


def _decompose(mesh, *, max_convex_hull: int, threshold: float, resolution: int, mcts_iterations: int):
    """Run CoACD on ``mesh`` and return a list of (vertices, faces) convex parts. Deterministic (seed 0)."""
    import coacd
    try:
        coacd.set_log_level("error")
    except Exception:
        pass
    cmesh = coacd.Mesh(mesh.vertices, mesh.faces)
    parts = coacd.run_coacd(
        cmesh, threshold=threshold, max_convex_hull=max_convex_hull,
        preprocess_mode="auto", preprocess_resolution=resolution,
        mcts_iterations=mcts_iterations, merge=True, seed=0,
    )
    return parts


def decompose_foot(mesh_path: str | Path, out_dir: str | Path, link: str, mesh_rel: str, *,
                   mode: str = "sole", sole_thickness: float = 0.02, max_convex_hull: int = 8,
                   threshold: float = 0.06, resolution: int = 40, mcts_iterations: int = 80) -> FootDecomp:
    """Convex-decompose one foot mesh and write the parts as OBJ files; return a :class:`FootDecomp`.

    ``mode`` is ``"sole"`` (decompose only the bottom slab — dense flat contact pad) or ``"full"``
    (decompose the whole foot, capped to ``max_convex_hull`` pieces). Parts are written as
    ``{out_dir}/{link}_part{i}.obj``. Raises if CoACD is unavailable or the mesh is missing/empty."""
    if not coacd_available():
        raise RuntimeError("coacd is not installed — convex foot decomposition needs it")
    import numpy as np
    import trimesh

    mesh_path = Path(mesh_path)
    if not mesh_path.is_file():
        raise FileNotFoundError(f"foot mesh not found: {mesh_path}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    full = _load_trimesh(mesh_path)
    sole_z = float(full.bounds[0][2])
    target = _sole_slab(full, sole_thickness) if mode == "sole" else full
    if mode not in ("sole", "full"):
        raise ValueError(f"mode must be 'sole' or 'full', got {mode!r}")

    parts = _decompose(target, max_convex_hull=max_convex_hull, threshold=threshold,
                       resolution=resolution, mcts_iterations=mcts_iterations)
    if not parts:
        raise RuntimeError(f"coacd produced no parts for {link} ({mesh_path.name})")

    written: list[str] = []
    n_sole = 0
    for i, (v, f) in enumerate(parts):
        hull = trimesh.Trimesh(vertices=np.asarray(v), faces=np.asarray(f), process=True)
        if hull.is_empty or len(hull.vertices) < 4:
            continue
        if float(hull.bounds[0][2]) <= sole_z + 0.005:
            n_sole += 1
        outp = out_dir / f"{link}_part{i}.obj"
        hull.export(str(outp))
        written.append(str(outp))
    if not written:
        raise RuntimeError(f"all coacd parts for {link} were degenerate")

    return FootDecomp(link=link, mesh_rel=mesh_rel, parts=tuple(written), n_parts=len(written),
                      sole_z=sole_z, n_sole_parts=n_sole)


def _rel_from_urdf(urdf_dir: Path, abs_part: str) -> str:
    """Filename a URDF in ``urdf_dir`` should use to reference ``abs_part`` (relative path with /)."""
    import os
    return os.path.relpath(abs_part, urdf_dir).replace("\\", "/")


def build_convex_feet_urdf(src_urdf: str | Path, out_urdf: str | Path, *,
                           foot_links: tuple[str, ...] = TIENKUNG_FEET, mode: str = "sole",
                           **decomp_kwargs) -> CoacdFeetResult:
    """Rewrite ``src_urdf`` so each ``foot_links`` link's ``<collision>`` is the convex decomposition.

    For each named foot link, the original (concave) collision mesh is convex-decomposed (see
    :func:`decompose_foot`) and the link's single ``<collision>`` is replaced by one ``<collision>`` per
    convex part (origin inherited from the original collision). The ``<visual>`` is left untouched so the
    rendered robot is unchanged. The result is written to ``out_urdf`` and the convex parts to a
    ``coacd_feet/`` dir next to it. Returns a :class:`CoacdFeetResult`. Fail-loud: raises if a named foot
    link, or its collision mesh, is absent (no silently-unchanged foot)."""
    src_urdf = Path(src_urdf)
    out_urdf = Path(out_urdf)
    if not src_urdf.is_file():
        raise FileNotFoundError(f"source URDF not found: {src_urdf}")
    urdf_dir = src_urdf.parent
    out_dir = out_urdf.parent
    parts_dir = out_dir / "coacd_feet"

    tree = ET.parse(str(src_urdf))
    root = tree.getroot()
    links = {ln.get("name"): ln for ln in root.findall("link")}

    feet: list[FootDecomp] = []
    for link_name in foot_links:
        link = links.get(link_name)
        if link is None:
            raise ValueError(f"foot link {link_name!r} not in URDF {src_urdf.name}; "
                             f"have {sorted(links)[:8]}…")
        coll = link.find("collision")
        if coll is None:
            raise ValueError(f"link {link_name!r} has no <collision> to replace")
        mesh_el = coll.find("geometry/mesh")
        if mesh_el is None or not mesh_el.get("filename"):
            raise ValueError(f"link {link_name!r} collision is not a <mesh> (cannot decompose a primitive)")
        mesh_rel = mesh_el.get("filename")
        mesh_abs = (urdf_dir / mesh_rel).resolve()
        origin_el = coll.find("origin")

        fd = decompose_foot(mesh_abs, parts_dir, link_name, mesh_rel, mode=mode, **decomp_kwargs)
        feet.append(fd)

        # remove the old collision, append one <collision> per convex part
        link.remove(coll)
        for part_abs in fd.parts:
            new_coll = ET.SubElement(link, "collision")
            if origin_el is not None:
                o = ET.SubElement(new_coll, "origin")
                o.set("xyz", origin_el.get("xyz", "0 0 0"))
                o.set("rpy", origin_el.get("rpy", "0 0 0"))
            geom = ET.SubElement(new_coll, "geometry")
            m = ET.SubElement(geom, "mesh")
            m.set("filename", _rel_from_urdf(out_dir, part_abs))

    out_dir.mkdir(parents=True, exist_ok=True)
    tree.write(str(out_urdf))
    return CoacdFeetResult(src_urdf=str(src_urdf), out_urdf=str(out_urdf), mode=mode,
                           feet=tuple(feet), parts_dir=str(parts_dir))


# Default output location for the TienKung convex-feet URDF (OUTSIDE the repo, next to the source).
TIENKUNG_SRC_URDF = (
    "/home/genesis/humanoid_assets/tienkung/lite_urdf_publish/urdf/humanoid_publish.urdf"
)
TIENKUNG_COACD_URDF = (
    "/home/genesis/humanoid_assets/tienkung/lite_urdf_publish/urdf/humanoid_publish_coacdfeet.urdf"
)


def build_tienkung_coacd_feet(mode: str = "sole", **kwargs) -> CoacdFeetResult:
    """Convenience: build the TienKung convex-feet URDF at :data:`TIENKUNG_COACD_URDF`."""
    return build_convex_feet_urdf(TIENKUNG_SRC_URDF, TIENKUNG_COACD_URDF,
                                  foot_links=TIENKUNG_FEET, mode=mode, **kwargs)
