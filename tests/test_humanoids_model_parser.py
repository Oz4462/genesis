"""Humanoid model parser — structural parse of real open-source URDF/MJCF (links, actuated DOF,
total mass, inertials, mesh existence, units sanity).

Exact checks, not vibes: a synthetic 2-link URDF reports exactly 1 actuated DOF (the revolute, not the
fixed weld) and 2.5 kg; the ``package://../meshes/`` Onshape-export form resolves and the mesh is
found (the quirk that first made Berkeley's meshes look 'missing'); a synthetic MJCF splits its
freejoint (6 DOF) from its one hinge (1 actuated DOF). Every nonsense input raises. When the large
asset downloads are present, the real TienKung URDF parses as a clean 20-DOF ~42 kg humanoid with all
inertials and all meshes, and the real Asimov MJCF as a floating-base full-body model.

Offline, stdlib only. Run:  pytest tests/test_humanoids_model_parser.py
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.humanoids.model_parser import (  # noqa: E402
    parse_mjcf,
    parse_model,
    parse_urdf,
)

_ASSETS = Path("/home/genesis/humanoid_assets")
_TIENKUNG = _ASSETS / "tienkung/lite_urdf_publish/urdf/humanoid_publish.urdf"
_ASIMOV = _ASSETS / "asimov/sim-model/xmls/asimov.xml"

_MINI_URDF = textwrap.dedent("""\
    <robot name="mini">
      <link name="base">
        <inertial>
          <origin xyz="0 0 0.1"/>
          <mass value="2.0"/>
          <inertia ixx="0.01" ixy="0" ixz="0" iyy="0.01" iyz="0" izz="0.01"/>
        </inertial>
        <visual><geometry><mesh filename="package://../meshes/base.stl"/></geometry></visual>
      </link>
      <link name="tip">
        <inertial><mass value="0.5"/>
          <inertia ixx="0.001" ixy="0" ixz="0" iyy="0.001" iyz="0" izz="0.001"/></inertial>
      </link>
      <joint name="j0" type="revolute"><parent link="base"/><child link="tip"/></joint>
      <joint name="weld" type="fixed"><parent link="base"/><child link="tip"/></joint>
    </robot>
""")

_MINI_MJCF = textwrap.dedent("""\
    <mujoco model="minimj">
      <worldbody>
        <body name="trunk">
          <freejoint/>
          <inertial pos="0 0 0" mass="3.0" diaginertia="0.1 0.1 0.1"/>
          <body name="thigh">
            <joint name="hip" type="hinge"/>
            <inertial pos="0 0 -0.2" mass="1.0" diaginertia="0.02 0.02 0.005"/>
          </body>
        </body>
      </worldbody>
    </mujoco>
""")


def test_synthetic_urdf_counts_dof_mass_and_resolves_relative_package_mesh(tmp_path):
    p = tmp_path / "urdf" / "mini.urdf"
    p.parent.mkdir()
    p.write_text(_MINI_URDF)
    (tmp_path / "meshes").mkdir()
    (tmp_path / "meshes" / "base.stl").write_bytes(b"\0" * 84)
    s = parse_urdf(p)
    assert s.link_count == 2
    assert s.actuated_dof == 1            # the revolute; the fixed weld is excluded
    assert s.fixed_joints == 1
    assert s.total_mass == pytest.approx(2.5)
    assert s.meshes_found == 1            # package://../meshes/ resolved (the Berkeley quirk)
    assert s.meshes_missing == ()


def test_synthetic_mjcf_splits_actuated_from_floating_base(tmp_path):
    p = tmp_path / "mini.xml"
    p.write_text(_MINI_MJCF)
    s = parse_mjcf(p)
    assert s.fmt == "mjcf"
    assert s.actuated_dof == 1            # the single hinge
    assert s.free_or_ball_dof == 6        # the freejoint trunk, NOT an actuator DOF
    assert s.total_mass == pytest.approx(4.0)


def test_units_warning_fires_on_a_millimetre_authored_urdf(tmp_path):
    """A model with a COM ~1000 from its frame origin is millimetres — the most common import bug.
    The parser must flag it, not trust it."""
    mm = _MINI_URDF.replace('xyz="0 0 0.1"', 'xyz="0 0 950.0"')
    p = tmp_path / "mm.urdf"
    p.write_text(mm)
    s = parse_urdf(p)
    assert any("MILLIMET" in w for w in s.warnings)


def test_parse_model_rejects_unknown_root(tmp_path):
    bad = tmp_path / "bad.xml"
    bad.write_text("<sdf><world/></sdf>")
    with pytest.raises(ValueError, match="unsupported model root"):
        parse_model(bad)


def test_parse_urdf_raises_on_missing_file():
    with pytest.raises(FileNotFoundError):
        parse_urdf("/no/such/robot.urdf")


def test_urdf_with_no_links_raises(tmp_path):
    p = tmp_path / "empty.urdf"
    p.write_text('<robot name="empty"></robot>')
    with pytest.raises(ValueError, match="no <link>"):
        parse_urdf(p)


@pytest.mark.skipif(not _TIENKUNG.is_file(), reason="TienKung assets not downloaded")
def test_real_tienkung_is_a_clean_20dof_humanoid():
    s = parse_model(_TIENKUNG)
    assert s.fmt == "urdf"
    assert s.actuated_dof == 20                  # 12 leg + 8 arm revolute joints
    assert 30.0 < s.total_mass < 60.0            # ~42.5 kg, human-scale
    assert s.links_without_inertia == ()         # every link carries an inertial
    assert s.meshes_missing == ()                # all referenced meshes present
    assert not any("MILLIMET" in w for w in s.warnings)


@pytest.mark.skipif(not _ASIMOV.is_file(), reason="Asimov assets not downloaded")
def test_real_asimov_mjcf_has_floating_base_and_clean_inertials():
    s = parse_model(_ASIMOV)
    assert s.fmt == "mjcf"
    assert s.free_or_ball_dof >= 6               # floating trunk
    assert s.actuated_dof >= 20                  # full-body hinges
    assert s.links_without_inertia == ()
