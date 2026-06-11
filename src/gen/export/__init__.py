"""GENESIS exporters — turn a verified Specification into a concrete artifact.

Exporters are deterministic, framework-free output adapters. They assume a
GATE-γ-validated specification and never invent a value: a node they cannot
faithfully render raises ``ExportError`` rather than emitting a guessed number.

  openscad — the parametric CSG geometry as OpenSCAD source (every dimension
             carries the originating quantity id as a comment, so the export is
             traceable back to the ledger / decision sheet).
"""

from __future__ import annotations

from .openscad import component_to_openscad, specification_to_openscad

__all__ = ["specification_to_openscad", "component_to_openscad"]
