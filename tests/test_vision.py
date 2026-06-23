"""OpenCV vision adapter — deterministic feature detection + measurement.

external/vision.py is an import-guarded capability: detect the distinct shapes in an image
and measure each (bbox, area, centroid, optionally in mm). These tests pin it on a
SYNTHESISED image with known shapes, so the expected measurements are exact:

  * POSITIVE: two rectangles of known size are detected, sorted largest-first, with the
    right bounding boxes and areas; a mm/px scale converts pixel sizes to mm correctly
    (area scales by the square of the linear scale); detection works from an ndarray AND
    from a written-then-read PNG path; and a sub-min-area speck is filtered out;
  * NEGATIVE (loud failure): a missing file, a non-positive mm/px scale, and an
    unsupported array shape each raise the typed GenesisError — never a fabricated
    measurement.

One FAST unit test always runs (the availability probe is a bool). The cv2-dependent tests
SKIP when OpenCV is absent.

Engine: OpenCV (cv2). Deterministic (fixed threshold, external contours). Run:
  pytest tests/test_vision.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.errors import GenesisError  # noqa: E402
from gen.external.vision import (  # noqa: E402
    count_features,
    detect_features,
    opencv_available,
)

_HAVE_CV2 = opencv_available()
_skip_no_cv2 = pytest.mark.skipif(not _HAVE_CV2, reason="the vision adapter needs the optional cv2 package")


def _two_rectangles():
    """A 200x300 light image with a 60x60 and a 100x70 dark rectangle."""
    import cv2
    import numpy as np

    img = np.full((200, 300), 255, np.uint8)
    cv2.rectangle(img, (20, 30), (80, 90), 0, -1)      # ~60x60
    cv2.rectangle(img, (150, 100), (250, 170), 0, -1)  # ~100x70
    return img


# --- FAST unit test (no cv2) -------------------------------------------------------

def test_availability_probe_is_bool():
    assert isinstance(opencv_available(), bool)


# --- cv2-dependent tests -----------------------------------------------------------

@_skip_no_cv2
def test_detects_two_rectangles_sorted_by_area():
    feats = detect_features(_two_rectangles())
    assert len(feats) == 2
    # largest first: the 100x70 rectangle
    big, small = feats
    assert big.area_px > small.area_px
    # OpenCV bounding rects are inclusive-edge (≈ nominal+1 px)
    assert big.bbox[2] == pytest.approx(101, abs=2)
    assert big.bbox[3] == pytest.approx(71, abs=2)
    assert small.bbox[2] == pytest.approx(61, abs=2)
    # centroid of the big rect is near its geometric center (~200, ~135)
    assert big.centroid[0] == pytest.approx(200, abs=3)
    assert big.centroid[1] == pytest.approx(135, abs=3)


@_skip_no_cv2
def test_scale_to_mm_is_correct():
    """A 0.5 mm/px scale halves linear sizes and quarters areas."""
    feats = detect_features(_two_rectangles(), mm_per_px=0.5)
    big = feats[0]
    assert big.width_mm == pytest.approx(big.bbox[2] * 0.5)
    assert big.height_mm == pytest.approx(big.bbox[3] * 0.5)
    assert big.area_mm2 == pytest.approx(big.area_px * 0.25)


@_skip_no_cv2
def test_detects_from_written_png_path(tmp_path):
    import cv2

    p = tmp_path / "shapes.png"
    cv2.imwrite(str(p), _two_rectangles())
    assert count_features(str(p)) == 2


@_skip_no_cv2
def test_min_area_filters_small_specks():
    import cv2
    import numpy as np

    img = np.full((100, 100), 255, np.uint8)
    cv2.rectangle(img, (10, 10), (60, 60), 0, -1)   # big
    img[80, 80] = 0                                  # a 1-px speck
    # with a generous min area only the big rectangle survives
    assert count_features(img, min_area_px=10.0) == 1


@_skip_no_cv2
def test_missing_file_is_loud():
    with pytest.raises(GenesisError):
        detect_features("/no/such/image_file.png")


@_skip_no_cv2
def test_bad_scale_is_loud():
    with pytest.raises(GenesisError):
        detect_features(_two_rectangles(), mm_per_px=-1.0)


@_skip_no_cv2
def test_unsupported_array_shape_is_loud():
    import numpy as np

    with pytest.raises(GenesisError):
        detect_features(np.zeros((4, 4, 7)))  # 7-channel is not an image
