"""H3 tests: Ready-to-Build manufacturer ZIP from a realization package dir.

Contract:
  * ZIP is non-empty and contains BOM + manifest when present
  * nested .zip files are not re-packed into themselves
  * ready flag requires min handoff (manifest + payload)
  * empty/missing root is a loud ValueError
  * inventory + gaps are honest
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from gen.pipelines.realization_package import (
    build_cam_section,
    build_ready_to_build_zip,
    collect_ready_to_build_files,
    write_cam_section,
)


def _seed_package(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(
        json.dumps({"name": "test-pkg", "schema": "test"}), encoding="utf-8"
    )
    (root / "bom.json").write_text(
        json.dumps({"schema": "genesis-bom-v1", "mechanical": [{"id": "p0"}]}),
        encoding="utf-8",
    )
    (root / "BOM.md").write_text("# BOM\n", encoding="utf-8")
    (root / "part_0.stl").write_text(
        "solid test\nendsolid test\n", encoding="utf-8"
    )
    (root / "part_0_top.dxf").write_text("0\nSECTION\n", encoding="utf-8")
    (root / "harness_package.json").write_text("{}", encoding="utf-8")
    # CAM via real builder so .nc is verify-grade
    class _Spec:
        name = "Plate"
        bounding_box_hint_mm = (40.0, 30.0, 5.0)

    class _Cad:
        spec = _Spec()
        geometry_quantities: dict = {}

    class _Frag:
        cad_artifact = _Cad()

    sec = build_cam_section([_Frag()], run_id="h3", pkg_name="test")
    write_cam_section(root, sec)


def test_collect_skips_zip_and_dotfiles(tmp_path: Path):
    _seed_package(tmp_path)
    (tmp_path / ".hidden").write_text("x", encoding="utf-8")
    (tmp_path / "old.zip").write_bytes(b"PK\x03\x04")
    files = collect_ready_to_build_files(tmp_path)
    names = {p.name for p in files}
    assert "manifest.json" in names
    assert ".hidden" not in names
    assert "old.zip" not in names


def test_ready_to_build_zip_archives_manufacturer_set(tmp_path: Path):
    _seed_package(tmp_path)
    meta = build_ready_to_build_zip(tmp_path, run_id="h3-zip")
    assert meta["ready"] is True
    assert meta["size_bytes"] > 0
    assert meta["n_files_archived"] >= 5
    zip_path = tmp_path / meta["zip_file"]
    assert zip_path.is_file()
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
    assert "manifest.json" in names
    assert "bom.json" in names
    assert "part_0.stl" in names
    assert "part_0_top.dxf" in names
    assert any(n.endswith(".nc") for n in names)
    assert "ready_to_build.json" in names
    assert "READY_TO_BUILD_README.txt" in names
    # nested zip not included
    assert meta["zip_file"] not in names
    assert (tmp_path / "ready_to_build.json").is_file()
    assert (tmp_path / "READY_TO_BUILD.md").is_file()
    counts = meta["inventory_counts"]
    assert counts.get("bom", 0) >= 1
    assert counts.get("geometry", 0) >= 1
    assert any("factory sign-off" in g for g in meta["gaps"])


def test_ready_to_build_missing_root_is_loud(tmp_path: Path):
    with pytest.raises(ValueError, match="missing"):
        build_ready_to_build_zip(tmp_path / "nope")


def test_ready_false_without_payload(tmp_path: Path):
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    meta = build_ready_to_build_zip(tmp_path, run_id="emptyish")
    assert meta["ready"] is False
    assert any("BOM" in g or "geometry" in g or "CAM" in g for g in meta["gaps"])
