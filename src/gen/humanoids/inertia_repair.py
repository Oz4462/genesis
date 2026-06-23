"""inertia_repair — derive proper <inertial> blocks for inertia-less URDF links from mesh geometry.

Motivation (AGILOped, the NimbRo-OP ``nimbro_new`` lineage URDF that ships in the repo): of its 45
links only 13 carry an authored ``<inertial>``. The other 32 are loaded by PyBullet with the importer
fallback ``mass=1, inertia=diag(1,1,1)`` (it prints a ``No inertial data for link`` warning for each).
That fabricates ~32 kg of phantom mass, inflating the floating-base total to ~42.4 kg against the
paper's 14.5 kg headline (and the 10.43 kg actually carried by the authored inertials). A robot with
32 unit-mass phantom links cannot be used for any honest dynamics.

This module repairs that by *deriving* each missing inertial from the link's own mesh geometry via
``trimesh`` (volume × material density → mass; the unit-density moment-of-inertia tensor scaled by
density → the inertia tensor; the mesh centroid → the inertial origin), and emitting a repaired URDF.

Two honesty boundaries are enforced, not hidden:
  * **Meshless coordinate frames.** 24 of the 32 links carry NO ``<visual>``/``<collision>`` mesh at
    all — they are pure kinematic frames (feet, foot-contact planes, the whole arm chain, neck, head,
    cameras, the "back" parallel rods). There is no geometry to integrate, so a mass CANNOT be derived
    from this model; assigning one would be invention. They are given a TINY nominal point inertial
    (default 1e-4 kg) purely so the engine stops faking 1 kg. The consequence — that the arms/head of
    this particular URDF lineage carry no modelled mass — is reported, not papered over.
  * **Hollow printed parts are not solid.** Most of the leg/trunk STLs are non-watertight thin shells;
    ``trimesh`` then falls back to the convex hull, which *fills the shell solid* and overestimates
    volume badly (e.g. the trunk's authored 5.20 kg vs a solid-hull-at-PLA 12.8 kg). We therefore do
    NOT re-derive masses for links that already have an authored inertial (we trust the authored value),
    and for the 8 parallel-linkage rods — whose ``<visual>`` reuses a full *leg* mesh purely for
    drawing — we substitute the real slender rod mesh (``parallel_rod_link.STL``, which IS watertight),
    because that is what the part physically is; using the leg mesh would double-count a whole leg.
    Every such substitution and every convex-hull fallback is recorded in the returned report.

Output is a NEW URDF file (the input is never mutated). Fail-loud: a missing mesh, an unreadable mesh,
a non-positive density, or a link that cannot be resolved raises — no silent skips, no guessed values.

Source: trimesh mass-properties (``Trimesh.volume``, ``Trimesh.center_mass``, ``Trimesh.moment_inertia``
are computed at unit density; mass/inertia scale linearly with density). URDF inertial conventions per
the ROS URDF spec (``<inertial>`` = mass + COM origin + symmetric 3×3 inertia about the COM).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

#: Default material density [kg/m^3]. AGILOped is a 3D-printed prototype; PLA is ~1240 kg/m^3.
#: Stated explicitly and overridable — never a hidden constant.
PLA_DENSITY_KG_M3 = 1240.0

#: Mass [kg] given to a link that has NO mesh to integrate (a pure coordinate frame). Tiny on purpose:
#: it exists only to stop the engine inventing 1 kg; it is NOT a claim about the real part's mass.
NOMINAL_FRAME_MASS_KG = 1.0e-4

#: The real slender linkage-rod mesh basename. The parallel-rod links reference a full leg mesh in
#: their <visual> (for drawing only); physically they are this thin rod, so we integrate this instead.
_PARALLEL_ROD_MESH = "parallel_rod_link.STL"

#: Substring of a link name marking it as a parallel-linkage rod (gets the rod-mesh substitution).
_PARALLEL_PREFIX = "parallel_"


@dataclass(frozen=True)
class LinkInertial:
    """The inertial derived (or substituted/nominal) for one previously inertia-less link."""
    link: str
    mass_kg: float
    com_xyz: tuple[float, float, float]          #: inertial origin = mesh centroid in the link frame
    inertia: tuple[float, float, float, float, float, float]  #: (ixx, ixy, ixz, iyy, iyz, izz) about COM
    source: str                                  #: "mesh:<file>" | "mesh(convex_hull):<file>" |
    #                                              "rod-substitution:<file>" | "rod-substitution(convex_hull):<file>"
    #                                              | "nominal-frame(no geometry)"
    used_convex_hull: bool                       #: True if the mesh was non-watertight → hull fallback


@dataclass(frozen=True)
class RepairReport:
    """Outcome of a URDF inertial repair: what was added, the resulting mass, and the honesty caveats."""
    urdf_in: str
    urdf_out: str
    density_kg_m3: float
    links_total: int
    links_already_inertial: int
    links_repaired: int                          #: previously inertia-less links now given an inertial
    mass_already_inertial_kg: float              #: Σ of the authored inertials (trusted, not re-derived)
    mass_added_kg: float                         #: Σ of the inertials this repair injected
    derived: tuple[LinkInertial, ...] = field(default_factory=tuple)
    convex_hull_links: tuple[str, ...] = field(default_factory=tuple)
    nominal_frame_links: tuple[str, ...] = field(default_factory=tuple)
    rod_substituted_links: tuple[str, ...] = field(default_factory=tuple)

    @property
    def total_mass_kg(self) -> float:
        """Σ of authored + injected inertial mass — the model's total once repaired."""
        return self.mass_already_inertial_kg + self.mass_added_kg

    def summary(self) -> dict:
        return {
            "urdf_out": self.urdf_out,
            "density_kg_m3": self.density_kg_m3,
            "links_total": self.links_total,
            "links_already_inertial": self.links_already_inertial,
            "links_repaired": self.links_repaired,
            "mass_already_inertial_kg": round(self.mass_already_inertial_kg, 4),
            "mass_added_kg": round(self.mass_added_kg, 4),
            "total_mass_kg": round(self.total_mass_kg, 4),
            "convex_hull_links": len(self.convex_hull_links),
            "nominal_frame_links": len(self.nominal_frame_links),
            "rod_substituted_links": len(self.rod_substituted_links),
        }


def _resolve_mesh_path(filename: str, mesh_search_root: Path) -> Path:
    """Resolve a URDF ``<mesh filename=...>`` to a local file.

    Handles the ``package://<pkg>/...`` ROS scheme (strip the scheme + package name and join the
    remainder under ``mesh_search_root``'s package root) and the xacro ``${display_variant}`` token
    that the AGILOped URDF leaves in some paths (it resolves to the ``nimbro_new`` mesh variant). Falls
    back to a basename search under the root. Raises FileNotFoundError if nothing matches (no silent
    empty mesh)."""
    fn = filename.replace("${display_variant}", "nimbro_new")
    if fn.startswith("package://"):
        rel = fn[len("package://"):]
        # rel = "<pkg>/<...path...>"; mesh_search_root is the dir that CONTAINS <pkg>
        parts = rel.split("/", 1)
        if len(parts) == 2:
            candidate = mesh_search_root / parts[1]
            if candidate.is_file():
                return candidate
    # basename fallback (covers odd path roots): find the unique file by name under the root
    base = Path(fn).name
    matches = list(mesh_search_root.rglob(base))
    if matches:
        return matches[0]
    raise FileNotFoundError(f"could not resolve mesh {filename!r} under {mesh_search_root}")


def _mesh_inertial(mesh_path: Path, density_kg_m3: float
                   ) -> tuple[float, tuple[float, float, float],
                              tuple[float, float, float, float, float, float], bool]:
    """Compute (mass, com_xyz, (ixx,ixy,ixz,iyy,iyz,izz) about COM, used_convex_hull) for a mesh.

    trimesh computes ``volume``/``center_mass``/``moment_inertia`` at UNIT density, so mass = volume·ρ
    and the inertia tensor scales linearly with ρ. Non-watertight meshes have no well-defined enclosed
    volume; trimesh's robust fallback is the convex hull (flagged in the return so the caller can report
    it). Raises ValueError on a degenerate (non-positive-volume) mesh — never returns a zero-mass body
    silently."""
    import trimesh
    mesh = trimesh.load(str(mesh_path), force="mesh")
    if mesh.is_watertight:
        solid = mesh
        used_hull = False
    else:
        solid = mesh.convex_hull
        used_hull = True
    volume = float(solid.volume)
    if not (volume > 0.0):
        raise ValueError(f"mesh {mesh_path} has non-positive volume ({volume}); cannot derive inertia")
    mass = volume * density_kg_m3
    com = solid.center_mass
    inertia = solid.moment_inertia * density_kg_m3   # unit-density tensor → physical tensor
    return (
        mass,
        (float(com[0]), float(com[1]), float(com[2])),
        (float(inertia[0, 0]), float(inertia[0, 1]), float(inertia[0, 2]),
         float(inertia[1, 1]), float(inertia[1, 2]), float(inertia[2, 2])),
        used_hull,
    )


def _link_mesh_filename(link: ET.Element) -> str | None:
    """The first mesh filename referenced by a link's <visual> or <collision>, or None if it has none."""
    for tag in ("collision", "visual"):
        el = link.find(tag)
        if el is not None:
            mesh = el.find(".//mesh")
            if mesh is not None and mesh.get("filename"):
                return mesh.get("filename")
    return None


def _make_inertial_element(li: LinkInertial) -> ET.Element:
    """Build a URDF ``<inertial>`` element from a derived LinkInertial (mass + COM origin + tensor)."""
    inertial = ET.Element("inertial")
    origin = ET.SubElement(inertial, "origin")
    origin.set("rpy", "0 0 0")
    origin.set("xyz", f"{li.com_xyz[0]:.8g} {li.com_xyz[1]:.8g} {li.com_xyz[2]:.8g}")
    mass = ET.SubElement(inertial, "mass")
    mass.set("value", f"{li.mass_kg:.8g}")
    ixx, ixy, ixz, iyy, iyz, izz = li.inertia
    inertia = ET.SubElement(inertial, "inertia")
    inertia.set("ixx", f"{ixx:.8g}"); inertia.set("ixy", f"{ixy:.8g}"); inertia.set("ixz", f"{ixz:.8g}")
    inertia.set("iyy", f"{iyy:.8g}"); inertia.set("iyz", f"{iyz:.8g}"); inertia.set("izz", f"{izz:.8g}")
    return inertial


def repair_urdf_inertials(urdf_in: str, urdf_out: str, *, density_kg_m3: float = PLA_DENSITY_KG_M3,
                          mesh_search_root: str | None = None,
                          nominal_frame_mass_kg: float = NOMINAL_FRAME_MASS_KG,
                          parallel_rod_mesh: str = _PARALLEL_ROD_MESH) -> RepairReport:
    """Inject a derived ``<inertial>`` into every link of ``urdf_in`` that lacks one; write ``urdf_out``.

    For each inertia-less link:
      * if it references a mesh → derive (mass, COM, inertia) from that mesh at ``density_kg_m3``
        (parallel-linkage rods substitute the real slender ``parallel_rod_mesh`` for their drawn-only
        leg mesh — see the module docstring);
      * if it has no geometry → assign a tiny nominal point inertial (``nominal_frame_mass_kg``).
    Links that already have an inertial are left untouched (their authored values are trusted; this
    model's hollow shells make re-derivation inaccurate). Returns a :class:`RepairReport` with per-link
    detail and the resulting total mass.

    Raises FileNotFoundError if the input URDF or a referenced mesh is missing, and ValueError on a
    non-positive density / nominal mass or a degenerate mesh — fail-loud, no guessed values."""
    in_path = Path(urdf_in)
    if not in_path.is_file():
        raise FileNotFoundError(f"input URDF not found: {in_path}")
    if not (density_kg_m3 > 0.0):
        raise ValueError(f"density must be positive, got {density_kg_m3}")
    if not (nominal_frame_mass_kg > 0.0):
        raise ValueError(f"nominal frame mass must be positive, got {nominal_frame_mass_kg}")

    # The mesh package root: meshes live under <pkg>/mesh/...; the URDF sits in <pkg>/robots/.
    # package:// strips to "<pkg>/mesh/..."; resolving needs the dir that CONTAINS <pkg>.
    if mesh_search_root is not None:
        root_dir = Path(mesh_search_root)
    else:
        # urdf .../<pkg>/robots/nimbro_new.urdf  → contains-<pkg> dir = parents[2]
        root_dir = in_path.parent.parent.parent
    if not root_dir.is_dir():
        raise FileNotFoundError(f"mesh search root not found: {root_dir}")

    tree = ET.parse(str(in_path))
    robot = tree.getroot()
    links = robot.findall("link")

    derived: list[LinkInertial] = []
    convex_hull_links: list[str] = []
    nominal_links: list[str] = []
    rod_links: list[str] = []
    mass_already = 0.0
    n_already = 0

    for link in links:
        name = link.get("name", "")
        existing = link.find("inertial")
        if existing is not None:
            m = existing.find("mass")
            if m is not None and m.get("value") is not None:
                mass_already += float(m.get("value"))
            n_already += 1
            continue

        is_rod = name.startswith(_PARALLEL_PREFIX)
        mesh_fn = _link_mesh_filename(link)

        if is_rod:
            # parallel rod: integrate the REAL slender rod mesh, not the drawn leg mesh (avoid
            # double-counting a whole leg). Resolve the rod mesh relative to any leg mesh's dir.
            ref = mesh_fn if mesh_fn is not None else f"package://x/mesh/nimbro_new/{parallel_rod_mesh}"
            rod_path = _resolve_mesh_path(ref, root_dir)
            rod_path = rod_path.parent / parallel_rod_mesh
            mass, com, inertia, used_hull = _mesh_inertial(rod_path, density_kg_m3)
            tag = "rod-substitution(convex_hull)" if used_hull else "rod-substitution"
            li = LinkInertial(link=name, mass_kg=mass, com_xyz=com, inertia=inertia,
                              source=f"{tag}:{parallel_rod_mesh}", used_convex_hull=used_hull)
            rod_links.append(name)
            if used_hull:
                convex_hull_links.append(name)
        elif mesh_fn is not None:
            mesh_path = _resolve_mesh_path(mesh_fn, root_dir)
            mass, com, inertia, used_hull = _mesh_inertial(mesh_path, density_kg_m3)
            tag = "mesh(convex_hull)" if used_hull else "mesh"
            li = LinkInertial(link=name, mass_kg=mass, com_xyz=com, inertia=inertia,
                              source=f"{tag}:{mesh_path.name}", used_convex_hull=used_hull)
            if used_hull:
                convex_hull_links.append(name)
        else:
            # pure coordinate frame: no geometry to integrate → tiny nominal point inertial.
            li = LinkInertial(
                link=name, mass_kg=nominal_frame_mass_kg, com_xyz=(0.0, 0.0, 0.0),
                inertia=(1.0e-7, 0.0, 0.0, 1.0e-7, 0.0, 1.0e-7),
                source="nominal-frame(no geometry)", used_convex_hull=False)
            nominal_links.append(name)

        derived.append(li)
        # inject the inertial as the FIRST child of the link (URDF convention places it first)
        link.insert(0, _make_inertial_element(li))

    out_path = Path(urdf_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(out_path), encoding="utf-8", xml_declaration=True)

    return RepairReport(
        urdf_in=str(in_path), urdf_out=str(out_path), density_kg_m3=density_kg_m3,
        links_total=len(links), links_already_inertial=n_already, links_repaired=len(derived),
        mass_already_inertial_kg=mass_already,
        mass_added_kg=sum(li.mass_kg for li in derived),
        derived=tuple(derived), convex_hull_links=tuple(convex_hull_links),
        nominal_frame_links=tuple(nominal_links), rod_substituted_links=tuple(rod_links))


# Convenience wrapper for the AGILOped asset specifically (the motivating case).
def repair_agiloped_inertials(urdf_out: str | None = None,
                              density_kg_m3: float = PLA_DENSITY_KG_M3) -> RepairReport:
    """Repair the bundled AGILOped ``nimbro_new`` URDF. Output defaults next to the source URDF.

    Thin wrapper over :func:`repair_urdf_inertials` pointing at the downloaded AGILOped asset. Raises
    FileNotFoundError if the asset is not present (download it first)."""
    src = Path("/home/genesis/humanoid_assets/agiloped/nimbro_op_model/robots/nimbro_new.urdf")
    out = Path(urdf_out) if urdf_out is not None else src.parent / "nimbro_new_repaired.urdf"
    return repair_urdf_inertials(str(src), str(out), density_kg_m3=density_kg_m3)


if __name__ == "__main__":  # pragma: no cover - manual report
    rep = repair_agiloped_inertials()
    import json
    print(json.dumps(rep.summary(), indent=2))
    print(f"\nrepaired {rep.links_repaired} links; {len(rep.rod_substituted_links)} rod-substituted, "
          f"{len(rep.nominal_frame_links)} nominal frames, {len(rep.convex_hull_links)} convex-hull.")
    print(f"total mass = {rep.total_mass_kg:.3f} kg "
          f"(authored {rep.mass_already_inertial_kg:.3f} + added {rep.mass_added_kg:.3f})")
