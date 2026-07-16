"""H1 — overall linear dimension annotations on 2-D section drawings.

Contract:
  * ``section_dxf_with_info`` returns DXF + true OCCT envelope in one worker call
  * ``annotate_overall_dimensions`` injects ≥2 linear DIMENSION entities (width+height)
  * ``section_dxf_dimensioned`` is the composed path used by realization packages
  * NEGATIVE: degenerate envelope (zero dy) is a loud ExportError — never a fake dim
  * FAST unit: format_dimension_sidecar is pure text (no build123d)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gen.core.errors import ExportError
from gen.core.state import GeometryNode, Quantity, ValueOrigin
from gen.export.drawing import (
    SectionInfo,
    annotate_overall_dimensions,
    b123d_python,
    drawing_available,
    format_dimension_sidecar,
    section_dxf_dimensioned,
    section_dxf_with_info,
)

_HAVE = drawing_available()
_skip = pytest.mark.skipif(
    not _HAVE,
    reason=f"build123d drawing venv missing at {b123d_python()!r}",
)

try:
    import ezdxf  # noqa: F401

    _HAVE_EZDXF = True
except Exception:
    _HAVE_EZDXF = False


def _q(qid: str, value: float) -> Quantity:
    return Quantity(
        id=qid,
        name=qid,
        value=value,
        unit="mm",
        origin=ValueOrigin.DECISION,
        rationale="test",
    )


def _box_quantities() -> dict[str, Quantity]:
    return {q.id: q for q in (_q("w", 60.0), _q("d", 40.0), _q("t", 8.0))}


def _box_geometry() -> GeometryNode:
    return GeometryNode(
        kind="box",
        params={"size_x": "w", "size_y": "d", "size_z": "t"},
    )


def test_format_dimension_sidecar_is_pure_text():
    info = SectionInfo(
        n_faces=1,
        n_edges=4,
        bbox_min=(-30.0, -20.0, 0.0),
        bbox_max=(30.0, 20.0, 0.0),
    )
    text = format_dimension_sidecar(info, plane="XY", offset=0.0, label="unit")
    assert "60.000 x 40.000" in text
    assert "plane: XY" in text
    assert "GD&T" in text or "gaps:" in text


def test_annotate_rejects_degenerate_envelope():
    info = SectionInfo(
        n_faces=0,
        n_edges=0,
        bbox_min=(0.0, 0.0, 0.0),
        bbox_max=(0.0, 0.0, 0.0),
    )
    with pytest.raises(ExportError, match="positive"):
        annotate_overall_dimensions("0\nSECTION\n", info)


@_skip
def test_section_dxf_with_info_one_call():
    dxf, info = section_dxf_with_info(
        _box_geometry(), _box_quantities(), plane="XY"
    )
    assert "SECTION" in dxf[:200]
    dx, dy, dz = info.dimensions
    assert dx == pytest.approx(60.0, abs=1e-6)
    assert dy == pytest.approx(40.0, abs=1e-6)
    assert dz == pytest.approx(0.0, abs=1e-6)


@_skip
@pytest.mark.skipif(not _HAVE_EZDXF, reason="ezdxf required")
def test_section_dxf_dimensioned_has_two_linear_dims(tmp_path: Path):
    import ezdxf

    dxf, info = section_dxf_dimensioned(
        _box_geometry(), _box_quantities(), plane="XY"
    )
    out = tmp_path / "dim.dxf"
    out.write_text(dxf, encoding="utf-8")
    doc = ezdxf.readfile(out)
    n_dim = sum(1 for e in doc.modelspace() if e.dxftype() == "DIMENSION")
    assert n_dim >= 2
    assert info.dimensions[0] == pytest.approx(60.0, abs=1e-6)
    assert info.dimensions[1] == pytest.approx(40.0, abs=1e-6)


@_skip
@pytest.mark.skipif(not _HAVE_EZDXF, reason="ezdxf required")
def test_right_view_yz_is_dimensioned(tmp_path: Path):
    """H1 right view (YZ plane) is a real section with overall dims."""
    import ezdxf

    dxf, info = section_dxf_dimensioned(
        _box_geometry(), _box_quantities(), plane="YZ"
    )
    # YZ cut of a 60×40×8 box → envelope uses the Y and Z extents (40 × 8)
    dx, dy, _ = info.dimensions
    assert dx == pytest.approx(40.0, abs=1e-3) or dy == pytest.approx(40.0, abs=1e-3)
    assert max(dx, dy) >= 8.0 - 1e-3
    out = tmp_path / "right.dxf"
    out.write_text(dxf, encoding="utf-8")
    doc = ezdxf.readfile(out)
    n_dim = sum(1 for e in doc.modelspace() if e.dxftype() == "DIMENSION")
    assert n_dim >= 2
