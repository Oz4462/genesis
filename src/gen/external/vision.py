"""OpenCV vision adapter — an import-guarded feature-measurement capability.

GENESIS produces and consumes images: rendered CAD parts, 2-D drawings, plots. A small
vision capability lets it INSPECT such an image deterministically — detect the distinct
shapes/parts in it and MEASURE each (bounding box, area, centroid) — which is directly
useful for, e.g., counting the parts laid out in a render, checking a drawing has the
expected number of features, or measuring a feature's size in real units given a known
scale. It is the analogue of the other ``external`` adapters: a focused, honest capability
behind an availability guard, not a general computer-vision claim.

OpenCV (``cv2``) is an OPTIONAL dependency (lazy import). Failure is LOUD and typed
(``GenesisError``): a missing package, an unreadable image, or a non-positive scale all
surface — never a fabricated measurement. Determinism: the same image + parameters always
yield the same features (a fixed threshold and external-contour retrieval, no randomness).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.errors import GenesisError


def opencv_available() -> bool:
    """True iff the optional ``cv2`` (OpenCV) package can be imported.

    Mirrors the other adapters' ``*_available`` probes so callers/tests can skip-guard
    cleanly. A False is a definitive 'no OpenCV'.
    """
    try:
        import cv2
        return True
    except Exception:
        return False


@dataclass(frozen=True)
class Feature:
    """One detected feature (connected shape) and its measurements.

    Pixel measurements are always present; the ``*_mm`` fields are populated only when a
    ``mm_per_px`` scale is supplied (area in mm² scales by the square of the linear scale).
    """

    bbox: tuple[int, int, int, int]   #: (x, y, w, h) in pixels
    area_px: float                    #: contour area in pixels²
    centroid: tuple[float, float]     #: (cx, cy) in pixels
    width_mm: float | None = None     #: bbox width in mm (if a scale was given)
    height_mm: float | None = None    #: bbox height in mm (if a scale was given)
    area_mm2: float | None = None     #: contour area in mm² (if a scale was given)


def _require_cv2():
    try:
        import cv2  # type: ignore
        return cv2
    except ImportError as exc:  # pragma: no cover - only without cv2
        raise GenesisError(
            "the vision adapter needs the optional 'opencv-python' (cv2) package; install "
            "it with `pip install opencv-python`."
        ) from exc


def _load_gray(image, cv2):
    """Coerce ``image`` (a path, or an already-loaded HxW / HxWxC ndarray) to grayscale."""
    import numpy as np

    if isinstance(image, str):
        from pathlib import Path

        if not Path(image).is_file():
            raise GenesisError(f"image file not found: {image}")
        gray = cv2.imread(image, cv2.IMREAD_GRAYSCALE)
        if gray is None:
            raise GenesisError(f"OpenCV could not decode the image: {image}")
        return gray
    arr = np.asarray(image)
    if arr.ndim == 2:
        return arr.astype("uint8") if arr.dtype != np.uint8 else arr
    if arr.ndim == 3 and arr.shape[2] in (3, 4):
        code = cv2.COLOR_BGRA2GRAY if arr.shape[2] == 4 else cv2.COLOR_BGR2GRAY
        return cv2.cvtColor(arr.astype("uint8"), code)
    raise GenesisError(f"unsupported image array shape {arr.shape}; expected HxW or HxWxC")


def detect_features(
    image,
    *,
    threshold: int = 127,
    invert: bool = True,
    min_area_px: float = 1.0,
    mm_per_px: float | None = None,
) -> list[Feature]:
    """Detect distinct shapes in ``image`` and measure each (deterministic).

    ``image`` is a file path or a grayscale/BGR(A) ndarray. The image is thresholded at
    ``threshold`` (with ``invert`` so DARK shapes on a LIGHT background are foreground —
    the common case for renders/drawings; set ``invert=False`` for light-on-dark), and the
    EXTERNAL contours above ``min_area_px`` are returned as :class:`Feature` objects sorted
    by descending area. With ``mm_per_px`` (> 0), each feature also carries its size in mm.

    Raises:
        GenesisError: cv2 unavailable, the image cannot be read, or ``mm_per_px`` ≤ 0
            (a non-positive scale would silently corrupt every real measurement).
    """
    if mm_per_px is not None and mm_per_px <= 0.0:
        raise GenesisError("mm_per_px must be > 0 (it is a length per pixel)")
    cv2 = _require_cv2()
    gray = _load_gray(image, cv2)
    flag = cv2.THRESH_BINARY_INV if invert else cv2.THRESH_BINARY
    _, binary = cv2.threshold(gray, int(threshold), 255, flag)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    feats: list[Feature] = []
    for c in contours:
        area = float(cv2.contourArea(c))
        if area < min_area_px:
            continue
        x, y, w, h = (int(v) for v in cv2.boundingRect(c))
        m = cv2.moments(c)
        if m["m00"] != 0.0:
            cx, cy = m["m10"] / m["m00"], m["m01"] / m["m00"]
        else:  # degenerate (zero-area) contour — fall back to bbox center
            cx, cy = x + w / 2.0, y + h / 2.0
        if mm_per_px is not None:
            feats.append(Feature(
                bbox=(x, y, w, h), area_px=area, centroid=(cx, cy),
                width_mm=w * mm_per_px, height_mm=h * mm_per_px,
                area_mm2=area * mm_per_px * mm_per_px,
            ))
        else:
            feats.append(Feature(bbox=(x, y, w, h), area_px=area, centroid=(cx, cy)))
    feats.sort(key=lambda f: f.area_px, reverse=True)
    return feats


def count_features(image, *, threshold: int = 127, invert: bool = True,
                   min_area_px: float = 1.0) -> int:
    """How many distinct shapes are in ``image`` (above ``min_area_px``) — a quick check,
    e.g. 'does this parts-tray render show the expected number of parts?'."""
    return len(detect_features(image, threshold=threshold, invert=invert,
                               min_area_px=min_area_px))


__all__ = [
    "opencv_available",
    "Feature",
    "detect_features",
    "count_features",
]
