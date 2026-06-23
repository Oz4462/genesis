"""Tests for gen.humanoids.inertia_repair — deriving URDF inertials from mesh geometry (AGILOped).

These exercise the real AGILOped asset when present (skipped cleanly otherwise), and the fail-loud
contract unconditionally. The motivating bug: the shipped nimbro_new URDF leaves 32/45 links without
an <inertial>, so PyBullet fakes mass=1 each (~42 kg total); the repair must remove every faked mass
and yield a realistic total, reported honestly.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from gen.humanoids import inertia_repair

_AGILOPED_URDF = Path(
    "/home/genesis/humanoid_assets/agiloped/nimbro_op_model/robots/nimbro_new.urdf")


def _trimesh_available() -> bool:
    try:
        import trimesh  # noqa: F401
        return True
    except Exception:
        return False


def _pybullet_available() -> bool:
    try:
        import pybullet  # noqa: F401
        return True
    except Exception:
        return False


requires_asset = pytest.mark.skipif(
    not _AGILOPED_URDF.is_file(), reason="AGILOped URDF asset not downloaded")
requires_trimesh = pytest.mark.skipif(not _trimesh_available(), reason="trimesh not installed")
requires_pybullet = pytest.mark.skipif(not _pybullet_available(), reason="pybullet not installed")


# ── fail-loud contract (no asset / deps needed) ───────────────────────────────────────────────────

def test_missing_input_urdf_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        inertia_repair.repair_urdf_inertials(
            str(tmp_path / "does_not_exist.urdf"), str(tmp_path / "out.urdf"))


@requires_asset
def test_nonpositive_density_raises(tmp_path):
    with pytest.raises(ValueError):
        inertia_repair.repair_urdf_inertials(
            str(_AGILOPED_URDF), str(tmp_path / "out.urdf"), density_kg_m3=0.0)


@requires_asset
def test_nonpositive_nominal_mass_raises(tmp_path):
    with pytest.raises(ValueError):
        inertia_repair.repair_urdf_inertials(
            str(_AGILOPED_URDF), str(tmp_path / "out.urdf"), nominal_frame_mass_kg=-1.0)


def test_unresolvable_mesh_raises(tmp_path):
    """A link whose mesh cannot be found under the search root raises (no silent empty mesh)."""
    urdf = tmp_path / "tiny.urdf"
    urdf.write_text(
        '<?xml version="1.0"?><robot name="t">'
        '<link name="a"><visual><geometry>'
        '<mesh filename="package://p/mesh/nimbro_new/nope.STL"/>'
        '</geometry></visual></link></robot>')
    (tmp_path / "mesh" / "nimbro_new").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        inertia_repair.repair_urdf_inertials(
            str(urdf), str(tmp_path / "out.urdf"), mesh_search_root=str(tmp_path))


def test_meshless_frame_gets_nominal_inertial(tmp_path):
    """A geometry-less link is given the tiny nominal point inertial, not a fabricated mass."""
    urdf = tmp_path / "frame.urdf"
    urdf.write_text(
        '<?xml version="1.0"?><robot name="t">'
        '<link name="cam_frame"/></robot>')
    rep = inertia_repair.repair_urdf_inertials(
        str(urdf), str(tmp_path / "out.urdf"), mesh_search_root=str(tmp_path),
        nominal_frame_mass_kg=1e-4)
    assert rep.links_repaired == 1
    assert rep.nominal_frame_links == ("cam_frame",)
    assert rep.derived[0].mass_kg == pytest.approx(1e-4)
    # and the written URDF link now carries an <inertial>
    out_root = ET.parse(str(tmp_path / "out.urdf")).getroot()
    link = out_root.find("link")
    assert link.find("inertial") is not None


# ── real AGILOped repair ──────────────────────────────────────────────────────────────────────────

@requires_asset
@requires_trimesh
def test_agiloped_repair_adds_inertial_to_every_link(tmp_path):
    out = tmp_path / "nimbro_new_repaired.urdf"
    rep = inertia_repair.repair_agiloped_inertials(urdf_out=str(out))

    assert out.is_file()
    # every link in the OUTPUT now has an <inertial>
    root = ET.parse(str(out)).getroot()
    links = root.findall("link")
    assert len(links) == rep.links_total
    missing = [lk.get("name") for lk in links if lk.find("inertial") is None]
    assert missing == [], f"links still without inertial: {missing}"

    # the repair touched the previously-missing links and trusted the authored ones
    assert rep.links_already_inertial + rep.links_repaired == rep.links_total
    assert rep.links_repaired == 32          # the 32 known inertia-less links
    # honesty bookkeeping: rods substituted + nominal frames account for all repaired links
    assert (len(rep.rod_substituted_links) + len(rep.nominal_frame_links)
            + sum(1 for d in rep.derived
                  if not d.link.startswith("parallel_")
                  and d.source.startswith("mesh"))) == rep.links_repaired


@requires_asset
@requires_trimesh
def test_agiloped_repair_mass_is_realistic_not_inflated(tmp_path):
    """Repaired total must be far below the ~42 kg phantom-mass figure and near the authored 10.43 kg."""
    out = tmp_path / "repaired.urdf"
    rep = inertia_repair.repair_agiloped_inertials(urdf_out=str(out))
    # authored inertials carry ~10.43 kg; the repair adds only small structural mass (rods + frames)
    assert rep.mass_already_inertial_kg == pytest.approx(10.4314, abs=0.05)
    assert rep.total_mass_kg < 12.0, "repaired total should not re-inflate toward 42 kg"
    assert rep.total_mass_kg > 10.0, "repaired total should retain the authored leg/trunk mass"
    # the added mass is dominated by the slender rods, each ~17 g → well under a kg total
    assert rep.mass_added_kg < 1.0


@requires_asset
@requires_trimesh
@requires_pybullet
def test_agiloped_repaired_loads_with_no_faked_masses():
    """PyBullet must load the repaired URDF with ZERO links at the fallback mass=1.0.

    The repaired URDF must sit beside the source so its ``package://`` mesh paths resolve (PyBullet
    resolves them relative to the URDF's own directory); we write it there, load it, then remove it so
    the test leaves no artifact behind."""
    import pybullet as p
    out = _AGILOPED_URDF.parent / "nimbro_new_repaired_pytest.urdf"
    rep = inertia_repair.repair_agiloped_inertials(urdf_out=str(out))
    try:
        c = p.connect(p.DIRECT)
        try:
            bid = p.loadURDF(str(out), useFixedBase=False,
                             flags=p.URDF_USE_INERTIA_FROM_FILE, physicsClientId=c)
            nj = p.getNumJoints(bid, physicsClientId=c)
            base_mass = p.getDynamicsInfo(bid, -1, physicsClientId=c)[0]
            faked = 0
            total = base_mass
            for j in range(nj):
                m = p.getDynamicsInfo(bid, j, physicsClientId=c)[0]
                total += m
                if abs(m - 1.0) < 1e-9:
                    faked += 1
        finally:
            p.disconnect(c)
    finally:
        out.unlink(missing_ok=True)

    assert faked == 0, f"{faked} links still at the fallback mass=1.0 after repair"
    # the engine's instantiated total matches the report's total (consistency, machine-ish precision)
    assert total == pytest.approx(rep.total_mass_kg, abs=1e-3)
