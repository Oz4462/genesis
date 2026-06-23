"""2-D manufacturing-drawing export (build123d section -> DXF/SVG) — real-tool integration.

export/drawing.py is a SUBPROCESS bridge (like cad/cadquery_bridge) that takes a GENESIS
CSG tree, cuts it with a named plane via build123d's OCCT-backed ``section``, and writes a
real DXF/SVG drawing. build123d lives in a separate venv (its OCCT/numpy stack conflicts
with the main one), so these tests SKIP when that interpreter is absent.

  * POSITIVE: a holed plate sectioned on its mid-plane yields a DXF that RELOADS via ezdxf
    and contains the expected entities — a CIRCLE for the hole and LINEs for the outline —
    proving the section is the real cut profile, not an empty or fabricated file;
  * POSITIVE: the section's reported overall dimensions equal the part's box footprint
    (60 x 40 mm), and a dimension sidecar is written next to the DXF;
  * POSITIVE: SVG export also produces a non-trivial drawing;
  * NEGATIVE (empty section): a plane offset far outside the solid produces no section and
    raises ExportError — never a blank drawing passed off as valid;
  * NEGATIVE (bad plane): an unknown plane name raises ExportError;
  * NEGATIVE (no geometry): sectioning a component with no geometry raises ExportError.

Two FAST unit tests (no build123d) always run: the availability probe is a bool, and a
missing interpreter is a loud ExportError.

Engines: build123d (section + ExportDXF/ExportSVG, in its own venv) + ezdxf (reload, main
venv). Run:  pytest tests/test_drawing_integration.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.errors import ExportError  # noqa: E402
from gen.core.state import Component, GeometryNode, Quantity, ValueOrigin  # noqa: E402
from gen.export.drawing import (  # noqa: E402
    b123d_python,
    component_section_dxf,
    drawing_available,
    section_dxf,
    section_info,
    section_svg,
    write_section_dxf,
)

_HAVE = drawing_available()
_skip = pytest.mark.skipif(
    not _HAVE, reason=f"the 2-D drawing exporter needs a build123d venv at {b123d_python()!r}"
)
_HAVE_EZDXF = True
try:
    import ezdxf  # noqa: F401
except Exception:
    _HAVE_EZDXF = False


def _q(qid: str, value: float) -> Quantity:
    return Quantity(id=qid, name=qid, value=value, unit="mm",
                    origin=ValueOrigin.DECISION, rationale="test")


def _holed_plate_quantities() -> dict[str, Quantity]:
    return {q.id: q for q in (_q("w", 60.0), _q("d", 40.0), _q("t", 8.0), _q("hr", 6.0))}


def _holed_plate_geometry() -> GeometryNode:
    return GeometryNode(
        kind="difference",
        children=[
            GeometryNode(kind="box", params={"size_x": "w", "size_y": "d", "size_z": "t"}),
            GeometryNode(kind="cylinder", params={"radius": "hr", "height": "t"}),
        ],
    )


# --- FAST unit tests (no build123d) ------------------------------------------------

def test_availability_probe_is_bool():
    assert isinstance(drawing_available(), bool)


def test_missing_interpreter_is_loud(monkeypatch):
    """If the build123d interpreter path does not exist, the exporter raises ExportError
    — it never returns a fabricated drawing (exercised even where build123d IS present by
    pointing the env var at a nonexistent interpreter)."""
    monkeypatch.setenv("GENESIS_B123D_PYTHON", "/nonexistent/python")
    with pytest.raises(ExportError):
        section_dxf(_holed_plate_geometry(), _holed_plate_quantities(), plane="XY")


# --- integration tests (need the build123d venv) -----------------------------------

@_skip
def test_section_info_reports_part_footprint():
    info = section_info(_holed_plate_geometry(), _holed_plate_quantities(), plane="XY")
    dx, dy, dz = info.dimensions
    assert dx == pytest.approx(60.0, abs=1e-6)
    assert dy == pytest.approx(40.0, abs=1e-6)
    assert dz == pytest.approx(0.0, abs=1e-6)  # a planar section is flat
    assert info.n_faces == 1
    assert info.n_edges >= 5  # 4 outline edges + at least the hole circle


@_skip
@pytest.mark.skipif(not _HAVE_EZDXF, reason="needs ezdxf to reload the DXF")
def test_dxf_reloads_with_expected_entities(tmp_path):
    """The exported DXF is real geometry: ezdxf reloads it and finds the hole CIRCLE and
    the outline LINEs — the cut profile of the holed plate."""
    import ezdxf

    comp = Component(id="c_plate", name="holed plate", geometry=_holed_plate_geometry())
    out = write_section_dxf(comp, _holed_plate_quantities(), tmp_path / "plate.dxf", plane="XY")
    assert Path(out).is_file()
    doc = ezdxf.readfile(out)
    entities = list(doc.modelspace())
    kinds = {e.dxftype() for e in entities}
    assert "CIRCLE" in kinds, kinds          # the hole
    assert "LINE" in kinds, kinds            # the plate outline
    # the dimension sidecar was written alongside
    sidecar = Path(out + ".dims.txt")
    assert sidecar.is_file()
    assert "60.000 x 40.000" in sidecar.read_text()


@_skip
def test_svg_export_is_nontrivial():
    svg = section_svg(_holed_plate_geometry(), _holed_plate_quantities(), plane="XY")
    assert svg.lstrip().startswith("<?xml") or "<svg" in svg
    assert len(svg) > 100


@_skip
def test_empty_section_is_loud():
    """A plane offset far outside the solid produces no section — ExportError, never a
    blank drawing."""
    with pytest.raises(ExportError):
        section_dxf(_holed_plate_geometry(), _holed_plate_quantities(),
                    plane="XY", offset=100.0)


@_skip
def test_bad_plane_is_loud():
    with pytest.raises(ExportError):
        section_dxf(_holed_plate_geometry(), _holed_plate_quantities(), plane="QQ")


def test_component_without_geometry_is_loud():
    """Sectioning a component that has no geometry is a loud ExportError (no silent empty
    output) — checked before any subprocess, so it runs without build123d."""
    comp = Component(id="c_empty", name="bought part", geometry=None)
    with pytest.raises(ExportError):
        component_section_dxf(comp, _holed_plate_quantities(), plane="XY")
