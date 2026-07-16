"""H7: structured montage steps with torque + image placeholders."""

from __future__ import annotations

import pytest

from gen.pipelines.realization_package import (
    DEFAULT_TORQUE_NM,
    build_montage_section,
    write_montage_section,
)


class _Spec:
    name = "Anchor Plate"


class _Cad:
    spec = _Spec()


class _Frag:
    cad_artifact = _Cad()


def test_montage_has_ordered_steps_and_torque(tmp_path):
    sec = build_montage_section([_Frag()], run_id="h7", pkg_name="pkg")
    assert sec["schema"] == "genesis-montage-v1"
    assert sec["n_steps"] >= 3
    assert sec["default_torque_nm"] == DEFAULT_TORQUE_NM["M3"]
    mount = next(s for s in sec["steps"] if s.get("part_name") == "Anchor Plate")
    assert mount["torque_nm"] == DEFAULT_TORQUE_NM["M3"]
    assert mount["image"] is None
    assert mount["image_placeholder"].startswith("images/")
    assert any("photos not generated" in g for g in sec["gaps"])

    write_montage_section(tmp_path, sec)
    md = (tmp_path / "MONTAGEANLEITUNG.md").read_text()
    assert "Torque" in md or "torque" in md.lower()
    assert "Anchor Plate" in md
    assert (tmp_path / "montage.json").is_file()


def test_montage_unknown_fastener_is_loud():
    with pytest.raises(ValueError, match="fastener"):
        build_montage_section([], fastener="M99")
