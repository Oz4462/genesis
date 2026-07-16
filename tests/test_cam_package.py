"""H2 tests: verified CAM G-code section in the realization package.

Contract:
  * fragments with bbox get real .nc files that pass verify_gcode
  * multi_axis.supported is False (honest)
  * cam_gap is False when at least one verified program exists
  * never empty .nc; reserved _program_texts stripped from cam.json
"""

from __future__ import annotations

from gen.cad.gcode import verify_gcode
from gen.pipelines.realization_package import build_cam_section, write_cam_section


class _Spec:
    name = "Plate"
    bounding_box_hint_mm = (60.0, 40.0, 8.0)
    min_wall_thickness_mm = 2.0


class _Qty:
    def __init__(self, value: float) -> None:
        self.value = value


class _Cad:
    spec = _Spec()
    geometry_quantities = {"hr": _Qty(3.0)}  # Ø6 mm centre hole


class _Frag:
    cad_artifact = _Cad()


def test_cam_section_writes_verified_nc(tmp_path):
    section = build_cam_section([_Frag()], run_id="h2-cam", pkg_name="pkg")
    assert section["cam_gap"] is False
    assert section["multi_axis"]["supported"] is False
    assert "helical_bore" in section["multi_axis"]["ops_available"]
    part = section["parts"][0]
    ops = {o["operation"] for o in part["operations"]}
    assert "outside_profile" in ops
    assert "face_mill" in ops
    assert "helical_bore" in ops
    assert all(o["verified"] for o in part["operations"])

    write_cam_section(tmp_path, section)
    assert (tmp_path / "cam.json").is_file()
    assert (tmp_path / "CAM.md").is_file()
    raw = (tmp_path / "cam.json").read_text()
    assert "_program_texts" not in raw

    for op in ("outside_profile", "face_mill", "helical_bore"):
        nc = tmp_path / f"part_0_{op}.nc"
        assert nc.is_file() and nc.stat().st_size > 0
        text = nc.read_text()
        assert "G21" in text and "M30" in text
        chk = verify_gcode(text)
        assert chk.ok, (op, chk.issues)


def test_cam_section_without_hole_skips_helical():
    class _NoHoleCad:
        spec = _Spec()
        geometry_quantities: dict = {}

    class _F:
        cad_artifact = _NoHoleCad()

    section = build_cam_section([_F()], run_id="h2-nohole")
    assert section["cam_gap"] is False
    ops = {o["operation"] for o in section["parts"][0]["operations"]}
    assert "outside_profile" in ops
    assert "helical_bore" not in ops
    assert any("helical_bore skipped" in n for n in section["notes"])
