"""Shared deterministic number formatting for all exporters.

One source of truth so every exporter renders 60 (not 60.0), 4.5, 2.25 the same
way — no drift between the OpenSCAD, build123d and Markdown back-ends.

Precision contract: ``.12g`` — 12 significant digits render an IEEE-754 double
almost losslessly for engineering values, stay locale-free, and drop trailing
noise. This is DISPLAY rounding only: the ledger keeps the exact value; a value
with more than 12 significant digits is rounded for presentation, never in
storage. Deliberate exceptions to this single source:
  * ``export/stl.py`` writes vertices with ``%.9g`` — a mesh-format contract of
    its own (binary-near payload), intentionally not routed through here.
  * Quoted claim text (C-4) is byte-exact in its source notation and must never
    pass through this formatter.
"""

from __future__ import annotations


def fmt_number(value: float) -> str:
    """Clean, deterministic rendering: integral values lose the trailing .0.

    12 significant digits (see module docstring: display rounding, near-lossless
    for doubles). Raises TypeError/ValueError for non-numeric input — never a
    guessed string.
    """
    return f"{float(value):.12g}"
