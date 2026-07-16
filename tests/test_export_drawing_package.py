"""G4+H1 tests: real dimensioned DXF section views in the realization package.

Contract:
  * fragments whose CAD artifact carries CSG geometry get REAL top/front/right DXF
    section files with overall envelope linear dimensions; drawing_gap flips to False.
  * fragments without geometry keep drawing_gap=True with the honest gap text.
  * never an empty .dxf file; full GD&T / isometric remain explicit gaps.
  * dimension sidecars (``.dxf.dims.txt``) land next to each view when annotated.
"""

from __future__ import annotations

import pytest

from gen.export.drawing import drawing_available
from gen.pipelines.architekt import map_to_system_concept
from gen.pipelines.ingenieur import map_to_ingenieur_spec
from gen.pipelines.integrator import build_realization_fragment
from gen.pipelines.realization_package import (
    build_drawings_section,
    write_drawings_section,
)

try:
    import ezdxf  # noqa: F401

    _HAVE_EZDXF = True
except Exception:  # pragma: no cover
    _HAVE_EZDXF = False


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
    # reserved keys must not leak into the serialized json
    raw = (tmp_path / "drawings.json").read_text()
    assert "_view_texts" not in raw
    assert "_dim_sidecars" not in raw


@pytest.mark.skipif(not drawing_available(), reason="build123d drawing venv missing")
def test_fragment_with_geometry_gets_real_dxf_views(tmp_path):
    frag = _real_fragment("h1-real")
    section = build_drawings_section([frag], _FakeAsm(), run_id="h1-real")
    assert section["drawing_gap"] is False
    assert section["dimensions_annotated"] is True
    part = section["parts"][0]
    # H1: top + front + right (YZ)
    assert set(part["views_generated"]) == {"front", "top", "right"}
    assert part["dimensions_annotated"] is True

    write_drawings_section(tmp_path, section)
    for view in ("top", "front", "right"):
        f = tmp_path / f"part_0_{view}.dxf"
        assert f.is_file() and f.stat().st_size > 0
        assert "SECTION" in f.read_text(errors="replace")[:200]
        sc = tmp_path / f"part_0_{view}.dxf.dims.txt"
        assert sc.is_file()
        assert "overall dimensions" in sc.read_text()
        assert "GD&T" in sc.read_text() or "gaps:" in sc.read_text()
    # Full GD&T + isometric honesty stays; overall dims are no longer the gap
    assert any("GD&T" in g or "tolerance frames" in g for g in section["gaps"])
    assert any("isometric" in g for g in section["gaps"])
    assert not any(
        "dimension annotations not generated" in g for g in section["gaps"]
    )


@pytest.mark.skipif(not drawing_available(), reason="build123d drawing venv missing")
@pytest.mark.skipif(not _HAVE_EZDXF, reason="ezdxf required to inspect DIMENSION entities")
def test_package_dxf_contains_linear_dimensions(tmp_path):
    """H1: package DXF reloads via ezdxf and carries overall DIMENSION entities."""
    import ezdxf

    frag = _real_fragment("h1-dims")
    section = build_drawings_section([frag], _FakeAsm(), run_id="h1-dims")
    write_drawings_section(tmp_path, section)
    path = tmp_path / "part_0_top.dxf"
    assert path.is_file()
    doc = ezdxf.readfile(path)
    kinds = {e.dxftype() for e in doc.modelspace()}
    assert "DIMENSION" in kinds, kinds
    n_dim = sum(1 for e in doc.modelspace() if e.dxftype() == "DIMENSION")
    assert n_dim >= 2, f"expected overall width+height dimensions, got {n_dim}"
