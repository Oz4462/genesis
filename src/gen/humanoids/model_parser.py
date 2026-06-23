"""model_parser — structural parsing of real-robot URDF / MuJoCo-MJCF descriptions (stdlib only).

This module is the HONEST, in-environment validation that the imported open-source humanoid models
are real and well-formed. The Genesis venv has no pybullet/mujoco/trimesh (see the agent's env note),
so we cannot load the models into a physics engine here. What we CAN do — and what a physics engine
itself does first when it ingests a model — is parse the XML kinematic tree and read off the ground
truth the file actually carries:

  * link / body count, joint count split by TYPE (revolute/prismatic/continuous = actuated DOF vs the
    fixed joints that only weld frames), so the reported DOF is the real articulated count, not a
    grep of ``<joint``;
  * the total mass = Σ link masses, and whether every moving link carries an inertial (a model with
    zero-mass moving links explodes in any engine — a real defect this surfaces);
  * the mesh files each link references and whether they exist on disk at the resolved path (a URDF
    that points at meshes that were not downloaded is broken, however well-formed the XML);
  * a units sanity read: a humanoid's summed link COM spread and mesh-referenced extents should be on
    the order of ~1-2 m. A model authored in millimetres (values ~1000) or with a scale bug is the
    single most common import failure, so we flag it rather than trust it.

Everything here is deterministic, offline, and uses only ``xml.etree.ElementTree`` + ``struct`` (for
the binary-STL triangle/bbox read). It parses; it does not repair. URDF (``<robot>``) and MJCF
(``<mujoco>``) are both supported because the imported set uses both (TienKung/Berkeley = URDF,
Asimov = MJCF).

Errors are loud (per the project convention): a missing file, an unparseable XML, or a model with no
links raises rather than returning a guessed-empty result.
"""

from __future__ import annotations

import math
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

#: URDF joint types that contribute an actuated degree of freedom (everything else is a fixed weld or
#: a non-driven mobility we do not count as a controllable DOF here). ``floating``/``planar`` are
#: multi-DOF mobilities a humanoid base could use, but they are not actuator DOF, so they are reported
#: separately and never folded into ``actuated_dof``.
_URDF_ACTUATED = frozenset({"revolute", "continuous", "prismatic"})
#: MJCF joint types: ``hinge`` ≈ revolute, ``slide`` ≈ prismatic. ``free`` is a 6-DOF floating base
#: (the trunk), ``ball`` is 3-DOF — both reported separately, not counted as actuator DOF.
_MJCF_ACTUATED = frozenset({"hinge", "slide"})


@dataclass(frozen=True)
class LinkInfo:
    """One rigid body in the tree, with the mass/inertia the file actually declares."""
    name: str
    mass: float | None                 #: kg; None when the link declares no inertial
    com: tuple[float, float, float] | None  #: inertial origin in the link frame (m)
    has_inertia: bool                  #: a full (non-zero) inertia tensor was given
    mesh_files: tuple[str, ...] = ()   #: mesh filenames this link references (visual + collision)


@dataclass(frozen=True)
class ModelStructure:
    """The parsed kinematic structure + the checks a physics engine would run at load time."""
    name: str
    fmt: str                           #: "urdf" or "mjcf"
    source_path: str
    links: tuple[LinkInfo, ...]
    actuated_dof: int                  #: revolute+prismatic+continuous (URDF) / hinge+slide (MJCF)
    fixed_joints: int
    free_or_ball_dof: int              #: DOF from floating/planar (URDF) or free/ball (MJCF) mobilities
    joint_type_counts: dict[str, int]
    total_mass: float                  #: Σ declared link masses (kg)
    links_without_inertia: tuple[str, ...]
    mesh_refs: tuple[str, ...]
    meshes_found: int
    meshes_missing: tuple[str, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def link_count(self) -> int:
        return len(self.links)

    def summary(self) -> dict:
        """A flat dict of the load-bearing numbers, for the validation report / catalog."""
        return {
            "name": self.name, "format": self.fmt, "links": self.link_count,
            "actuated_dof": self.actuated_dof, "fixed_joints": self.fixed_joints,
            "free_or_ball_dof": self.free_or_ball_dof, "total_mass_kg": round(self.total_mass, 4),
            "links_without_inertia": len(self.links_without_inertia),
            "mesh_refs": len(self.mesh_refs), "meshes_found": self.meshes_found,
            "meshes_missing": len(self.meshes_missing), "warnings": list(self.warnings),
        }


def _f(x: str | None) -> float:
    """Parse a float attribute, raising on a missing/garbage value (no silent 0.0 default — a missing
    mass is a fact to surface, not to invent)."""
    if x is None:
        raise ValueError("expected a numeric attribute, got none")
    return float(x)


def _vec3(s: str | None) -> tuple[float, float, float]:
    parts = (s or "0 0 0").split()
    if len(parts) != 3:
        raise ValueError(f"expected 3 components, got {s!r}")
    return (float(parts[0]), float(parts[1]), float(parts[2]))


def parse_urdf(path: str | Path) -> ModelStructure:
    """Parse a URDF file into a :class:`ModelStructure`.

    Reads every ``<link>`` (mass, inertial origin, whether a non-zero inertia tensor is present, and
    the visual/collision mesh filenames) and classifies every ``<joint type=...>``. Resolves each
    mesh reference relative to the URDF's directory (stripping a leading ``package://`` segment) and
    checks it exists on disk. Raises ValueError if the file is not a ``<robot>`` or has no links;
    FileNotFoundError if the path does not exist."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"URDF not found: {p}")
    root = ET.parse(p).getroot()
    if root.tag != "robot":
        raise ValueError(f"not a URDF (root <{root.tag}>, expected <robot>): {p}")

    links: list[LinkInfo] = []
    all_mesh_refs: list[str] = []
    for link in root.findall("link"):
        name = link.get("name", "<unnamed>")
        inertial = link.find("inertial")
        mass: float | None = None
        com: tuple[float, float, float] | None = None
        has_inertia = False
        if inertial is not None:
            m = inertial.find("mass")
            if m is not None and m.get("value") is not None:
                mass = _f(m.get("value"))
            o = inertial.find("origin")
            if o is not None:
                com = _vec3(o.get("xyz"))
            it = inertial.find("inertia")
            if it is not None:
                diag = [abs(_f(it.get(k))) for k in ("ixx", "iyy", "izz")]
                has_inertia = any(d > 0.0 for d in diag)
        meshes: list[str] = []
        for tag in ("visual", "collision"):
            for vc in link.findall(tag):
                for mesh in vc.iter("mesh"):
                    fn = mesh.get("filename")
                    if fn:
                        meshes.append(fn)
                        all_mesh_refs.append(fn)
        links.append(LinkInfo(name=name, mass=mass, com=com, has_inertia=has_inertia,
                              mesh_files=tuple(meshes)))
    if not links:
        raise ValueError(f"URDF has no <link> elements: {p}")

    type_counts: dict[str, int] = {}
    for joint in root.findall("joint"):
        jt = joint.get("type", "unknown")
        type_counts[jt] = type_counts.get(jt, 0) + 1
    actuated = sum(type_counts.get(t, 0) for t in _URDF_ACTUATED)
    fixed = type_counts.get("fixed", 0)
    extra = 6 * type_counts.get("floating", 0) + 2 * type_counts.get("planar", 0)

    return _finalize(name=root.get("name", p.stem), fmt="urdf", source=p, base_dir=p.parent,
                     links=links, mesh_refs=all_mesh_refs, type_counts=type_counts,
                     actuated=actuated, fixed=fixed, extra_dof=extra)


def parse_mjcf(path: str | Path) -> ModelStructure:
    """Parse a MuJoCo MJCF file into a :class:`ModelStructure`.

    MJCF nests bodies; mass/inertia live on optional ``<inertial>`` under each ``<body>`` (MuJoCo
    otherwise infers them from geoms — which this static read cannot do, so such a body is reported as
    inertia-less, an honest 'declared mass unknown' rather than a fabricated value). Joints are
    classified by ``type`` (default ``hinge`` when omitted, per the MJCF spec). Mesh assets are read
    from ``<asset><mesh file=...>`` and resolved against the model dir and an optional ``<compiler
    meshdir=...>``. Raises ValueError if not a ``<mujoco>`` model or it has no bodies."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"MJCF not found: {p}")
    root = ET.parse(p).getroot()
    if root.tag != "mujoco":
        raise ValueError(f"not an MJCF (root <{root.tag}>, expected <mujoco>): {p}")

    compiler = root.find("compiler")
    meshdir = compiler.get("meshdir", "") if compiler is not None else ""
    base_dir = (p.parent / meshdir) if meshdir else p.parent

    asset_meshes: list[str] = []
    asset = root.find("asset")
    if asset is not None:
        for mesh in asset.findall("mesh"):
            fn = mesh.get("file")
            if fn:
                asset_meshes.append(fn)

    links: list[LinkInfo] = []
    worldbody = root.find("worldbody")
    bodies = list(worldbody.iter("body")) if worldbody is not None else []
    for body in bodies:
        name = body.get("name", "<unnamed>")
        inertial = body.find("inertial")
        mass: float | None = None
        com: tuple[float, float, float] | None = None
        has_inertia = False
        if inertial is not None:
            if inertial.get("mass") is not None:
                mass = _f(inertial.get("mass"))
            com = _vec3(inertial.get("pos"))
            diag = inertial.get("diaginertia")
            full = inertial.get("fullinertia")
            if diag:
                has_inertia = any(abs(float(v)) > 0.0 for v in diag.split())
            elif full:
                has_inertia = any(abs(float(v)) > 0.0 for v in full.split()[:3])
        # mesh geoms referenced directly on this body (by asset mesh name, resolved below globally)
        meshes = [g.get("mesh") for g in body.findall("geom") if g.get("mesh")]
        links.append(LinkInfo(name=name, mass=mass, com=com, has_inertia=has_inertia,
                              mesh_files=tuple(m for m in meshes if m)))
    if not links:
        raise ValueError(f"MJCF has no <body> elements: {p}")

    type_counts: dict[str, int] = {}
    for body in bodies:
        # an MJCF free base may be written either as <freejoint/> or <joint type="free"/>;
        # normalise both to the "free" key so it is tallied exactly once below.
        if body.find("freejoint") is not None:
            type_counts["free"] = type_counts.get("free", 0) + 1
        for joint in body.findall("joint"):
            jt = joint.get("type", "hinge")  # MJCF default is hinge
            type_counts[jt] = type_counts.get(jt, 0) + 1
    actuated = sum(type_counts.get(t, 0) for t in _MJCF_ACTUATED)
    free_dof = 6 * type_counts.get("free", 0) + 3 * type_counts.get("ball", 0)

    return _finalize(name=root.get("model", p.stem), fmt="mjcf", source=p, base_dir=base_dir,
                     links=links, mesh_refs=asset_meshes, type_counts=type_counts,
                     actuated=actuated, fixed=0, extra_dof=free_dof)


def _resolve_mesh(ref: str, base_dir: Path) -> Path:
    """Resolve a mesh reference to a filesystem path, stripping a ``package://<pkg>/`` or ``file://``
    prefix and treating the rest as relative to ``base_dir`` (the model file's directory).

    Two real conventions are handled: a proper ``package://<pkgname>/sub/x.stl`` (drop the package-name
    segment, since ``base_dir`` is the package), and the Onshape-exporter form
    ``package://../meshes/x.stl`` where the segment after ``package://`` is already a relative path
    (``..``/``.``) — there is no package name to drop, so the remainder is kept verbatim. Mishandling
    the second form is exactly why Berkeley Humanoid Lite's meshes first appeared 'missing'."""
    r = ref
    for pre in ("package://", "file://"):
        if r.startswith(pre):
            r = r[len(pre):]
            head = r.split("/", 1)[0]
            if head not in ("", ".", ".."):
                # a real package name → drop it (base_dir is the package root)
                r = r.split("/", 1)[1] if "/" in r else r
            break
    return base_dir / r


def _stl_extent(path: Path) -> float | None:
    """Largest bounding-box edge (in the STL's own units) of a BINARY STL, by reading the 80-byte
    header + uint32 triangle count + the vertex floats. Returns None if the file is ASCII STL or
    cannot be read as binary. Used only for a units sanity read, so a None (skip) is fine."""
    try:
        with open(path, "rb") as fh:
            header = fh.read(80)
            if header[:5].lstrip().lower().startswith(b"solid"):
                return None  # likely ASCII STL; skip (binary path only)
            (ntri,) = struct.unpack("<I", fh.read(4))
            if ntri == 0 or ntri > 5_000_000:
                return None
            lo = [math.inf] * 3
            hi = [-math.inf] * 3
            for _ in range(ntri):
                rec = fh.read(50)  # 12 floats (normal+3 verts) + 2-byte attr
                if len(rec) < 50:
                    break
                vals = struct.unpack("<12f", rec[:48])
                for vi in range(3):
                    for c in range(3):
                        v = vals[3 + vi * 3 + c]
                        lo[c] = min(lo[c], v)
                        hi[c] = max(hi[c], v)
            edges = [hi[c] - lo[c] for c in range(3) if math.isfinite(hi[c]) and math.isfinite(lo[c])]
            return max(edges) if edges else None
    except (OSError, struct.error):
        return None


def _finalize(*, name: str, fmt: str, source: Path, base_dir: Path, links: list[LinkInfo],
              mesh_refs: list[str], type_counts: dict[str, int], actuated: int, fixed: int,
              extra_dof: int) -> ModelStructure:
    """Shared tail: total mass, inertia-less moving links, mesh existence, and the units sanity read."""
    total_mass = sum(li.mass for li in links if li.mass is not None)
    no_inertia = tuple(li.name for li in links if (li.mass is None or not li.has_inertia))

    # resolve + existence-check meshes (URDF refs are filenames; MJCF refs are asset names that may
    # omit the extension — we only existence-check when the ref looks like a path with an extension)
    found = 0
    missing: list[str] = []
    sample_extent: float | None = None
    checked_extent = False
    for ref in mesh_refs:
        if "." not in Path(ref).name:  # MJCF asset name without extension — cannot existence-check
            continue
        rp = _resolve_mesh(ref, base_dir)
        if rp.is_file():
            found += 1
            if not checked_extent and rp.suffix.lower() == ".stl":
                sample_extent = _stl_extent(rp)
                checked_extent = sample_extent is not None
        else:
            missing.append(ref)

    warnings: list[str] = []
    if no_inertia:
        warnings.append(f"{len(no_inertia)} link(s) without a declared (non-zero) inertia")
    if missing:
        warnings.append(f"{len(missing)} mesh file(s) referenced but not found on disk")
    # units sanity: a human-scale link COM should be < ~3 m from its frame origin; >100 ⇒ millimetres
    com_max = max((max(abs(c) for c in li.com) for li in links if li.com), default=0.0)
    if com_max > 100.0:
        warnings.append(f"inertial COM up to {com_max:.0f} — likely MILLIMETRES, not metres (scale bug)")
    if sample_extent is not None and sample_extent > 50.0:
        warnings.append(f"sample mesh bbox edge {sample_extent:.0f} units — meshes likely in millimetres")
    if total_mass <= 0.0:
        warnings.append("total declared mass is 0 — no link masses present (engine would need geom inference)")

    return ModelStructure(
        name=name, fmt=fmt, source_path=str(source), links=tuple(links),
        actuated_dof=actuated, fixed_joints=fixed, free_or_ball_dof=extra_dof,
        joint_type_counts=dict(type_counts), total_mass=total_mass,
        links_without_inertia=no_inertia, mesh_refs=tuple(mesh_refs),
        meshes_found=found, meshes_missing=tuple(missing), warnings=tuple(warnings),
    )


def parse_model(path: str | Path) -> ModelStructure:
    """Parse a robot description, dispatching on the XML root (``<robot>`` → URDF, ``<mujoco>`` →
    MJCF). Raises ValueError for any other root element."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"model not found: {p}")
    root_tag = ET.parse(p).getroot().tag
    if root_tag == "robot":
        return parse_urdf(p)
    if root_tag == "mujoco":
        return parse_mjcf(p)
    raise ValueError(f"unsupported model root <{root_tag}> (expected <robot> or <mujoco>): {p}")
