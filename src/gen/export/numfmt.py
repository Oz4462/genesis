"""Shared deterministic number formatting for all exporters.

One source of truth so every exporter renders 60 (not 60.0), 4.5, 2.25 the same
way — no drift between the OpenSCAD and build123d back-ends.
"""

from __future__ import annotations


def fmt_number(value: float) -> str:
    """Clean, deterministic rendering: integral values lose the trailing .0."""
    return f"{float(value):g}"
