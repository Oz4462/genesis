"""GENESIS exporters — turn a verified Specification into a concrete artifact.

Exporters are deterministic, framework-free output adapters. They assume a
GATE-γ-validated specification and never invent a value: a node they cannot
faithfully render raises ``ExportError`` rather than emitting a guessed number.

  openscad  — the parametric CSG geometry as OpenSCAD source (every dimension
              carries the originating quantity id as a comment).
  build123d — the same geometry as build123d (algebra-mode) Python on the OCCT
              kernel; per-component traceability comment.
  stl       — an ASCII STL triangle mesh of the MESHABLE primitives (box exact;
              cylinder/sphere tessellated); CSG booleans are not mesh-evaluated
              (raises, pointing to openscad/build123d) — never a wrong mesh.
  drawing   — a 2-D MANUFACTURING DRAWING: a planar DXF/SVG SECTION through a 3-D part
              (the real cut profile + overall dimensions), produced via build123d's OCCT
              ``section`` in an isolated subprocess (like cad/cadquery_bridge). Imported
              lazily so the package never hard-depends on a build123d interpreter.

The text back-ends resolve numbers from the same source (numfmt) so they never
drift.
"""

from __future__ import annotations

from .build123d import component_to_build123d, specification_to_build123d
from .brep_stl import component_to_brep_stl, specification_to_brep_stl
from .markdown import specification_to_markdown
from .openscad import component_to_openscad, specification_to_openscad
from .stl import component_to_stl, specification_to_stl

__all__ = [
    "specification_to_openscad",
    "component_to_openscad",
    "specification_to_build123d",
    "component_to_build123d",
    "specification_to_stl",
    "component_to_stl",
    "specification_to_brep_stl",
    "component_to_brep_stl",
    "specification_to_markdown",
    # drawing (2-D DXF/SVG section) — lazy (needs a build123d-venv interpreter)
    "drawing_available",
    "section_dxf",
    "section_svg",
    "section_info",
    "write_section_dxf",
    "specification_section_dxfs",
]


def __getattr__(name: str):
    # Lazy: the drawing exporter is a subprocess bridge; only import on demand.
    if name in (
        "drawing_available", "section_dxf", "section_svg", "section_info",
        "write_section_dxf", "specification_section_dxfs", "component_section_dxf",
        "SectionInfo",
    ):
        from . import drawing
        return getattr(drawing, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
