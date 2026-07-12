"""Export a GENESIS humanoid URDF as a ROS 2 (ament_cmake) robot-description package.

urdf_bridge emits a robot URDF; this turns it into a complete, colcon-buildable ROS 2
package so the design can be loaded by the ROS 2 ecosystem (robot_state_publisher, RViz,
Gazebo, MoveIt). A ROS 2 description package has a fixed shape, all of which is emitted here:

  <pkg>/
    package.xml          ament manifest (format 3): name, version, deps, build type
    CMakeLists.txt       ament_cmake: install the urdf/ and launch/ dirs
    urdf/<robot>.urdf    the robot description (from urdf_bridge)
    launch/display.launch.py   a robot_state_publisher launch file

The output is deterministic and dependency-free (stdlib only) — it just WRITES the package;
it does not require ROS 2 to be installed to generate it. Validity is a real, checkable
property (the test runs ``check_urdf`` and parses ``package.xml`` with ``catkin_pkg`` where
ROS 2 is present). Fail-loud: an empty/blank URString or a non-identifier package name is a
loud ``ExportError`` (a malformed package name would make ``colcon`` reject the package).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from ..core.errors import ExportError

#: A valid ROS 2 package name: lowercase, digits, underscores, starting with a letter
#: (REP-144 / ament naming). We enforce it so the generated package is colcon-valid.
_PKG_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _package_xml(name: str, version: str, description: str, maintainer: str,
                 maintainer_email: str, license_: str) -> str:
    """The ament ``package.xml`` (format 3) for an ament_cmake description package."""
    return (
        '<?xml version="1.0"?>\n'
        '<?xml-model href="http://download.ros.org/schema/package_format3.xsd" '
        'schematypens="http://www.w3.org/2001/XMLSchema"?>\n'
        '<package format="3">\n'
        f"  <name>{name}</name>\n"
        f"  <version>{version}</version>\n"
        f"  <description>{description}</description>\n"
        f'  <maintainer email="{maintainer_email}">{maintainer}</maintainer>\n'
        f"  <license>{license_}</license>\n\n"
        "  <buildtool_depend>ament_cmake</buildtool_depend>\n\n"
        "  <exec_depend>robot_state_publisher</exec_depend>\n"
        "  <exec_depend>joint_state_publisher</exec_depend>\n"
        "  <exec_depend>xacro</exec_depend>\n"
        "  <exec_depend>rviz2</exec_depend>\n\n"
        "  <export>\n"
        "    <build_type>ament_cmake</build_type>\n"
        "  </export>\n"
        "</package>\n"
    )


def _cmakelists(name: str) -> str:
    """An ament_cmake ``CMakeLists.txt`` that installs the urdf/ and launch/ dirs."""
    return (
        "cmake_minimum_required(VERSION 3.8)\n"
        f"project({name})\n\n"
        "find_package(ament_cmake REQUIRED)\n\n"
        "install(\n"
        "  DIRECTORY urdf launch\n"
        "  DESTINATION share/${PROJECT_NAME}\n"
        ")\n\n"
        "ament_package()\n"
    )


def _launch_py(name: str, urdf_filename: str) -> str:
    """A ``robot_state_publisher`` launch file that reads the installed URDF.

    Uses ament_index to locate the installed package share dir, so it works after
    ``colcon build`` + ``source install/setup.bash`` (the standard ROS 2 run path)."""
    return (
        "import os\n"
        "from ament_index_python.packages import get_package_share_directory\n"
        "from launch import LaunchDescription\n"
        "from launch_ros.actions import Node\n\n\n"
        "def generate_launch_description():\n"
        f"    pkg_share = get_package_share_directory('{name}')\n"
        f"    urdf_path = os.path.join(pkg_share, 'urdf', '{urdf_filename}')\n"
        "    with open(urdf_path, 'r') as f:\n"
        "        robot_description = f.read()\n"
        "    return LaunchDescription([\n"
        "        Node(\n"
        "            package='robot_state_publisher',\n"
        "            executable='robot_state_publisher',\n"
        "            output='screen',\n"
        "            parameters=[{'robot_description': robot_description}],\n"
        "        ),\n"
        "        Node(\n"
        "            package='joint_state_publisher',\n"
        "            executable='joint_state_publisher',\n"
        "            output='screen',\n"
        "        ),\n"
        "    ])\n"
    )


@dataclass(frozen=True)
class Ros2Package:
    """The files written for a ROS 2 description package (absolute paths)."""

    package_dir: str
    package_xml: str
    cmakelists: str
    urdf: str
    launch: str
    robot_name: str


def export_ros2_package(
    urdf_xml: str,
    out_dir: str | Path,
    package_name: str,
    *,
    version: str = "0.0.1",
    description: str = "GENESIS-generated robot description.",
    maintainer: str = "GENESIS",
    maintainer_email: str = "genesis@example.com",
    license_: str = "Apache-2.0",
    urdf_filename: str | None = None,
) -> Ros2Package:
    """Write ``urdf_xml`` as a colcon-buildable ament_cmake ROS 2 package; return the paths.

    ``package_name`` must be a valid ROS 2 package name (lowercase / digits / underscores,
    starting with a letter) — enforced, because colcon rejects an invalid name. The URDF is
    validated as well-formed XML (a ``<robot>`` root) before anything is written; a blank or
    malformed URDF is a loud ``ExportError`` (no half-written package).

    The package layout is the standard one (``package.xml`` + ``CMakeLists.txt`` + ``urdf/``
    + ``launch/``), so ``colcon build`` then ``ros2 launch <pkg> display.launch.py`` loads
    the robot into ``robot_state_publisher``.

    Raises:
        ExportError: an invalid package name, or a blank/malformed URDF.
    """
    if not _PKG_NAME_RE.match(package_name):
        raise ExportError(
            f"{package_name!r} is not a valid ROS 2 package name (must be lowercase "
            f"letters/digits/underscores, starting with a letter) — colcon would reject it"
        )
    if not urdf_xml or not urdf_xml.strip():
        raise ExportError("cannot export an empty URDF to a ROS 2 package")
    try:
        root = ET.fromstring(urdf_xml)
    except ET.ParseError as exc:
        raise ExportError(f"URDF is not well-formed XML: {exc}") from exc
    if root.tag != "robot":
        raise ExportError(f"URDF root must be <robot>, got <{root.tag}>")
    robot_name = root.get("name", package_name)

    urdf_filename = urdf_filename or f"{robot_name}.urdf"
    pkg_dir = Path(out_dir) / package_name
    urdf_dir = pkg_dir / "urdf"
    launch_dir = pkg_dir / "launch"
    urdf_dir.mkdir(parents=True, exist_ok=True)
    launch_dir.mkdir(parents=True, exist_ok=True)

    px = pkg_dir / "package.xml"
    cm = pkg_dir / "CMakeLists.txt"
    ud = urdf_dir / urdf_filename
    lp = launch_dir / "display.launch.py"

    px.write_text(_package_xml(package_name, version, description, maintainer,
                               maintainer_email, license_), encoding="utf-8")
    cm.write_text(_cmakelists(package_name), encoding="utf-8")
    ud.write_text(urdf_xml if urdf_xml.endswith("\n") else urdf_xml + "\n", encoding="utf-8")
    lp.write_text(_launch_py(package_name, urdf_filename), encoding="utf-8")

    return Ros2Package(
        package_dir=str(pkg_dir),
        package_xml=str(px),
        cmakelists=str(cm),
        urdf=str(ud),
        launch=str(lp),
        robot_name=robot_name,
    )


__all__ = [
    "export_ros2_package",
    "Ros2Package",
]
