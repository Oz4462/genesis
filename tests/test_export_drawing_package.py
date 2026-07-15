"""G4 (P1-3) tests: real DXF section views in the realization package.

Contract:
  * fragments whose CAD artifact carries CSG geometry get REAL top/front DXF
    section files in the package; drawing_gap flips to False then.
  * fragments without geometry keep drawing_gap=True with the honest gap text.
  * never an empty .dxf file; remaining GD&T gaps stay explicitly listed.
"""

from __future__ import annotations

import os

import pytest

from gen.export.drawing import drawing_available
from gen.pipelines.architekt import map_to_system_concept
from gen.pipelines.ingenieur import map_to_ingenieur_spec
from gen.pipelines.integrator import build_realization_fragment
from gen.pipelines.realization_package import (
    build_drawings_section,
    write_drawings_section,
)


class _FakeAsm:
    combined_stl = None
    part_files: list[str] = []


def _real_fragment(run_id: str):
    concept = map_to_system_concept(
        "Ein modularer Vertikal-Garten mit Bewässerung", run_id=run_id
    )
    ingenieur = map_to_ingenieur_spec(concept, run_id=run_id)
    return build_realization_fragment(concept, ingenieur, run_id=run_id)


def test_fragment_without_geometry_keeps_honest_gap(tmp_path):
    class _NoGeoCad:
        class spec:
            name = "No Geo"
            description = "artifact without CSG"
            bounding_box_hint_mm = (10, 10, 2)
            min_wall_thickness_mm = 2.0

        volume_estimate_cm3 = None
        geometry = None
        geometry_quantities: dict = {}

    class _Frag:
        cad_artifact = _NoGeoCad()

    section = build_drawings_section([_Frag()], _FakeAsm(), run_id="g4-nogeo")
    assert section["drawing_gap"] is True
    assert any("not generated" in g for g in section["gaps"])
    write_drawings_section(tmp_path, section)
    assert list(tmp_path.glob("*.dxf")) == []
    # reserved key must not leak into the serialized json
    assert "_view_texts" not in (tmp_path / "drawings.json").read_text()


@pytest.mark.skipif(not drawing_available(), reason="build123d drawing venv missing")
def test_fragment_with_geometry_gets_real_dxf_views(tmp_path):
    frag = _real_fragment("g4-real")
    section = build_drawings_section([frag], _FakeAsm(), run_id="g4-real")
    assert section["drawing_gap"] is False
    part = section["parts"][0]
    assert set(part["views_generated"]) == {"front", "top"}

    write_drawings_section(tmp_path, section)
    for view in ("top", "front"):
        f = tmp_path / f"part_0_{view}.dxf"
        assert f.is_file() and f.stat().st_size > 0
        assert "SECTION" in f.read_text(errors="replace")[:200]
    # GD&T honesty stays
    assert any("GD&T" in g or "dimension annotations" in g for g in section["gaps"])
