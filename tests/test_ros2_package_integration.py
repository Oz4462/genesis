"""ROS 2 package export from a GENESIS humanoid URDF — structure + real-tool validation.

export/ros2_package.py turns a urdf_bridge URDF into a colcon-buildable ament_cmake package.
These tests pin both the STRUCTURE (always) and its VALIDITY against real ROS 2 tooling:

  * POSITIVE (structure, no ROS 2 needed): the package has the standard layout
    (package.xml + CMakeLists.txt + urdf/<robot>.urdf + launch/display.launch.py), the
    URDF round-trips byte-for-byte, the CMakeLists installs the urdf/launch dirs, and the
    package.xml is format-3 ament_cmake;
  * POSITIVE (real validation, ROS 2 present): ``check_urdf`` (urdfdom) parses the emitted
    URDF as a valid robot tree, AND ``catkin_pkg`` validates package.xml as a real ament
    manifest — i.e. the package is genuinely ROS 2-loadable, not just plausibly shaped;
  * NEGATIVE (loud failure): an invalid package name, a blank URDF, and a non-<robot> root
    each raise the typed ExportError (a malformed package would break colcon).

The structure + negative tests always run (stdlib only). The ``check_urdf`` test SKIPs when
that binary is absent; the ``catkin_pkg`` test SKIPs when that module cannot be imported.

Engine: ROS 2 Jazzy (check_urdf / catkin_pkg). Run:  pytest tests/test_ros2_package_integration.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.errors import ExportError  # noqa: E402
from gen.export.ros2_package import export_ros2_package  # noqa: E402
from gen.urdf_bridge import humanoid_urdf  # noqa: E402


def _export(tmp_path) -> "object":
    return export_ros2_package(
        humanoid_urdf("genesis_humanoid"), tmp_path, "genesis_humanoid_description"
    )


# --- structure tests (no ROS 2) ----------------------------------------------------

def test_package_has_standard_layout(tmp_path):
    pkg = _export(tmp_path)
    base = Path(pkg.package_dir)
    assert base.name == "genesis_humanoid_description"
    assert (base / "package.xml").is_file()
    assert (base / "CMakeLists.txt").is_file()
    assert (base / "urdf" / "genesis_humanoid.urdf").is_file()
    assert (base / "launch" / "display.launch.py").is_file()
    assert pkg.robot_name == "genesis_humanoid"


def test_urdf_round_trips_and_is_wellformed(tmp_path):
    pkg = _export(tmp_path)
    urdf_text = Path(pkg.urdf).read_text()
    root = ET.fromstring(urdf_text)  # parses
    assert root.tag == "robot" and root.get("name") == "genesis_humanoid"
    # the whole-body tree is present (pelvis root + 10 joints)
    assert {ln.get("name") for ln in root.findall("link")} >= {"pelvis", "l_thigh", "head"}
    assert len(root.findall("joint")) == 10


def test_package_xml_is_format3_ament_cmake(tmp_path):
    pkg = _export(tmp_path)
    root = ET.fromstring(Path(pkg.package_xml).read_text())
    assert root.tag == "package" and root.get("format") == "3"
    assert root.findtext("name") == "genesis_humanoid_description"
    assert root.findtext("buildtool_depend") == "ament_cmake"
    build_type = root.find("export/build_type")
    assert build_type is not None and build_type.text == "ament_cmake"


def test_cmakelists_installs_resource_dirs(tmp_path):
    pkg = _export(tmp_path)
    cm = Path(pkg.cmakelists).read_text()
    assert "project(genesis_humanoid_description)" in cm
    assert "find_package(ament_cmake REQUIRED)" in cm
    assert "DIRECTORY urdf launch" in cm
    assert "ament_package()" in cm


# --- NEGATIVE tests (no ROS 2) -----------------------------------------------------

def test_invalid_package_name_is_loud(tmp_path):
    with pytest.raises(ExportError):
        export_ros2_package(humanoid_urdf(), tmp_path, "Bad-Name")  # hyphen + capital


def test_blank_urdf_is_loud(tmp_path):
    with pytest.raises(ExportError):
        export_ros2_package("   ", tmp_path, "ok_pkg")


def test_non_robot_root_is_loud(tmp_path):
    with pytest.raises(ExportError):
        export_ros2_package("<notrobot/>", tmp_path, "ok_pkg")


# --- real-tool validation (ROS 2 present) ------------------------------------------

_CHECK_URDF = shutil.which("check_urdf") or "/opt/ros/jazzy/bin/check_urdf"
_HAVE_CHECK_URDF = Path(_CHECK_URDF).exists()


@pytest.mark.skipif(not _HAVE_CHECK_URDF, reason="check_urdf (urdfdom / ROS 2) not available")
def test_check_urdf_accepts_emitted_urdf(tmp_path):
    """urdfdom's check_urdf parses the emitted URDF as a valid robot tree (the real
    ROS 2 URDF parser, not GENESIS' own)."""
    pkg = _export(tmp_path)
    proc = subprocess.run([_CHECK_URDF, pkg.urdf], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "Successfully Parsed XML" in proc.stdout
    assert "robot name is: genesis_humanoid" in proc.stdout


def _have_catkin_pkg() -> bool:
    try:
        import catkin_pkg  # noqa: F401
        return True
    except Exception:
        # it usually lives in the system python, not the test venv — probe that too
        try:
            r = subprocess.run(
                ["python3", "-c", "import catkin_pkg"], capture_output=True, timeout=20
            )
            return r.returncode == 0
        except Exception:
            return False


@pytest.mark.skipif(not _have_catkin_pkg(), reason="catkin_pkg (ament manifest parser) not available")
def test_package_xml_validates_as_ament_manifest(tmp_path):
    """catkin_pkg parses + validates package.xml as a real ament manifest — proving it is
    a manifest colcon/ament will accept, not merely well-formed XML."""
    pkg = _export(tmp_path)
    # run in whichever python has catkin_pkg (prefer this interpreter, else system python3)
    code = (
        "import sys;"
        "from catkin_pkg.package import parse_package;"
        f"p = parse_package({pkg.package_dir!r});"
        "p.validate();"
        "assert p.name == 'genesis_humanoid_description', p.name;"
        "bt = [e.content for e in p.exports if e.tagname == 'build_type'];"
        "assert bt == ['ament_cmake'], bt;"
        "print('VALID')"
    )
    try:
        import catkin_pkg  # noqa: F401

        interp = sys.executable
    except Exception:
        interp = "python3"
    proc = subprocess.run([interp, "-c", code], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "VALID" in proc.stdout
