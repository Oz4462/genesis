"""2-D manufacturing-drawing export: a dimensioned DXF/SVG SECTION from a 3-D part.

GENESIS exports 3-D geometry (OpenSCAD source, build123d source, STL, STEP). A shop floor
also needs a 2-D drawing — a planar SECTION through the part with the cut profile (outline
+ holes) and overall dimensions. This module produces exactly that: it takes a GATE-γ
GeometryNode CSG tree, cuts it with a named plane, and writes a real DXF (the CAD/CAM
interchange) or SVG (a viewable drawing), with the section's bounding-box dimensions
annotated as a sidecar.

build123d (the OCCT-backed parametric library that provides ``section`` + ``ExportDXF`` /
``ExportSVG``) is kept OUT of the main ``.venv`` for the same reason as cadquery — its
OpenCASCADE/numpy stack conflicts with the main one. So this is a SUBPROCESS bridge,
exactly like ``cad/cadquery_bridge``: it serialises the CSG to JSON, runs
``export/drawing_worker.py`` under the build123d-venv interpreter, and parses back only
the DXF/SVG text + section metrics. No build123d / OCCT object enters the main process.

Configuration (env, with a default):
  * ``GENESIS_B123D_PYTHON`` — path to a Python interpreter that has build123d installed
    (default ``/home/genesis/.venv-b123d/bin/python``).

Failure is LOUD and typed (CLAUDE.md: no silent defaults / no fabricated geometry):
  * interpreter missing                  -> ExportError
  * subprocess crash / non-zero exit     -> ExportError (stderr included)
  * worker reports a typed error         -> ExportError (re-raised faithfully)
  * empty section (plane misses solid)   -> ExportError (never a blank drawing)
  * unparseable output                   -> ExportError
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..core.errors import ExportError
from ..core.state import Component, GeometryNode, Quantity, Specification

#: The worker script (shipped here; executed by the build123d-venv interpreter).
_WORKER = Path(__file__).resolve().parent / "drawing_worker.py"

#: Default build123d-venv interpreter; override with GENESIS_B123D_PYTHON.
_DEFAULT_B123D_PYTHON = "/home/genesis/.venv-b123d/bin/python"

#: Generous default timeout (s): OCCT section + DXF export on a cold import.
_DEFAULT_TIMEOUT = 120.0

#: The planes the worker understands.
_PLANES = ("XY", "XZ", "YZ")


def b123d_python() -> str:
    """Resolve the build123d-venv interpreter path (env override, else default)."""
    return os.environ.get("GENESIS_B123D_PYTHON", _DEFAULT_B123D_PYTHON)


def drawing_available() -> bool:
    """True iff the build123d interpreter and the worker script both exist.

    Mirrors ``cad_available``: a True does NOT prove build123d imports — only the first
    real call does — but a False is a definitive 'no build123d interpreter', so tests can
    skip-guard cleanly.
    """
    return Path(b123d_python()).exists() and _WORKER.is_file()


def _serialize(node: GeometryNode) -> dict:
    return {
        "kind": node.kind,
        "params": dict(node.params),
        "children": [_serialize(c) for c in node.children],
    }


def _resolved_values(quantities: dict[str, Quantity]) -> dict[str, float]:
    return {qid: float(q.value) for qid, q in quantities.items()}


def _run(request: dict, *, timeout: float = _DEFAULT_TIMEOUT):
    """Run the worker once with ``request`` (JSON on stdin); return its result.

    Raises ExportError on any failure mode — loud, never a guessed drawing.
    """
    py = b123d_python()
    if not Path(py).exists():
        raise ExportError(
            f"the 2-D drawing exporter needs a Python interpreter with build123d at "
            f"{py!r} (set GENESIS_B123D_PYTHON). build123d is intentionally NOT in the "
            f"main .venv — its OCCT/numpy stack conflicts with it, like cadquery."
        )
    if not _WORKER.is_file():
        raise ExportError(f"drawing worker script missing at {_WORKER}")
    try:
        proc = subprocess.run(
            [py, str(_WORKER)],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise ExportError(
            f"drawing worker timed out after {timeout}s for op {request.get('op')!r}"
        ) from exc
    if proc.returncode != 0:
        raise ExportError(
            f"drawing worker exited {proc.returncode} for op {request.get('op')!r}: "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ExportError(
            f"drawing worker returned unparseable output for op "
            f"{request.get('op')!r}: {proc.stdout[:500]!r} (stderr: "
            f"{proc.stderr[:300]!r})"
        ) from exc
    if not payload.get("ok", False):
        raise ExportError(
            f"drawing worker (op {request.get('op')!r}) failed: "
            f"{payload.get('error', 'unknown error')}"
        )
    return payload["result"]


def _check_plane(plane: str) -> None:
    if plane not in _PLANES:
        raise ExportError(f"plane must be one of {_PLANES}, got {plane!r}")


# --- low-level CSG API -------------------------------------------------------------

def section_dxf(
    node: GeometryNode, quantities: dict[str, Quantity], *,
    plane: str = "XY", offset: float = 0.0,
) -> str:
    """DXF text of the planar section of the CSG through ``plane`` (offset along normal).

    The section is the real cut profile (outer outline + any holes the plane crosses),
    produced by the OCCT kernel. Raises ExportError on an empty section (the plane misses
    the solid) — never a blank drawing.
    """
    _check_plane(plane)
    return str(_run({"op": "section_dxf", "node": _serialize(node),
                     "values": _resolved_values(quantities), "plane": plane,
                     "offset": float(offset)}))


def section_svg(
    node: GeometryNode, quantities: dict[str, Quantity], *,
    plane: str = "XY", offset: float = 0.0,
) -> str:
    """SVG text of the planar section of the CSG (a viewable 2-D drawing)."""
    _check_plane(plane)
    return str(_run({"op": "section_svg", "node": _serialize(node),
                     "values": _resolved_values(quantities), "plane": plane,
                     "offset": float(offset)}))


@dataclass(frozen=True)
class SectionInfo:
    """Metrics of a planar section (read from the OCCT section sketch)."""

    n_faces: int
    n_edges: int
    bbox_min: tuple[float, float, float]
    bbox_max: tuple[float, float, float]

    @property
    def dimensions(self) -> tuple[float, float, float]:
        """Overall (dx, dy, dz) extent of the section — the drawing's outer dimensions."""
        return (
            self.bbox_max[0] - self.bbox_min[0],
            self.bbox_max[1] - self.bbox_min[1],
            self.bbox_max[2] - self.bbox_min[2],
        )


def section_info(
    node: GeometryNode, quantities: dict[str, Quantity], *,
    plane: str = "XY", offset: float = 0.0,
) -> SectionInfo:
    """Face/edge count and bounding box of the section — the dimensions to annotate."""
    _check_plane(plane)
    r = _run({"op": "section_info", "node": _serialize(node),
              "values": _resolved_values(quantities), "plane": plane, "offset": float(offset)})
    return SectionInfo(
        n_faces=int(r["n_faces"]),
        n_edges=int(r["n_edges"]),
        bbox_min=tuple(float(x) for x in r["bbox_min"]),  # type: ignore[arg-type]
        bbox_max=tuple(float(x) for x in r["bbox_max"]),  # type: ignore[arg-type]
    )


# --- component / spec convenience --------------------------------------------------

def component_section_dxf(
    component: Component, quantities: dict[str, Quantity], *,
    plane: str = "XY", offset: float = 0.0,
) -> str:
    """DXF section of one component's geometry. Raises ExportError if it has none."""
    if component.geometry is None:
        raise ExportError(f"component {component.id!r} has no geometry to section")
    return section_dxf(component.geometry, quantities, plane=plane, offset=offset)


def write_section_dxf(
    component: Component, quantities: dict[str, Quantity], out_path: str | Path, *,
    plane: str = "XY", offset: float = 0.0, write_dimension_sidecar: bool = True,
) -> str:
    """Write a component's DXF section to ``out_path``; return the path.

    With ``write_dimension_sidecar`` (default), also writes ``<out_path>.dims.txt`` with
    the section's overall dimensions and face/edge count — a human-readable dimension
    annotation alongside the geometric DXF (the "dimensioned" part of the drawing). The
    DXF itself is the exact section geometry, reloadable by any CAD/CAM tool (or ezdxf).
    """
    if component.geometry is None:
        raise ExportError(f"component {component.id!r} has no geometry to section")
    out_path = Path(out_path)
    dxf = section_dxf(component.geometry, quantities, plane=plane, offset=offset)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(dxf, encoding="utf-8")
    if write_dimension_sidecar:
        info = section_info(component.geometry, quantities, plane=plane, offset=offset)
        dx, dy, dz = info.dimensions
        sidecar = out_path.with_suffix(out_path.suffix + ".dims.txt")
        sidecar.write_text(
            f"GENESIS 2-D drawing — section of component {component.id!r} ({component.name})\n"
            f"plane: {plane}  offset: {offset:g} mm\n"
            f"overall dimensions (dx x dy x dz): {dx:.3f} x {dy:.3f} x {dz:.3f} mm\n"
            f"section profile: {info.n_faces} face(s), {info.n_edges} edge(s)\n",
            encoding="utf-8",
        )
    return str(out_path)


def specification_section_dxfs(
    spec: Specification, out_dir: str | Path, *, plane: str = "XY", offset: float = 0.0,
) -> list[str]:
    """Write a DXF section for every fabricated component of a spec; return the paths.

    Components without geometry are skipped (not an error — a spec can mix fabricated and
    bought parts). Raises ExportError only if a fabricated section genuinely fails.
    """
    quantities = {q.id: q for q in spec.quantities}
    out_dir = Path(out_dir)
    written: list[str] = []
    for comp in spec.components:
        if comp.geometry is None:
            continue
        path = out_dir / f"{comp.id}.dxf"
        written.append(
            write_section_dxf(comp, quantities, path, plane=plane, offset=offset)
        )
    return written


__all__ = [
    "b123d_python",
    "drawing_available",
    "section_dxf",
    "section_svg",
    "section_info",
    "SectionInfo",
    "component_section_dxf",
    "write_section_dxf",
    "specification_section_dxfs",
]
