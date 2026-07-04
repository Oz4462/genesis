"""Display-level text sanitisation for exporter output — comments, headings, cells.

Free text (``spec.idea``, component names, rationales, step actions) may contain
newlines or Markdown pipes. Interpolated raw into a ``//``/``#`` comment or a
table cell, that text BREAKS the surrounding syntax: a second line escapes the
comment (a .scad that does not open, a .py that does not compile), a ``|`` splits
the table row. These helpers keep the OUTPUT syntax intact.

Scope (honesty boundary): this is presentation only — stored data is never
altered, and quoted claim text (C-4) is byte-exact in its source notation and
must NEVER pass through these helpers.
"""

from __future__ import annotations


def single_line(text: str) -> str:
    """Collapse every line break (\\n, \\r\\n, \\r, …) to a single space.

    For text interpolated into a single-line context: a ``//``/``#`` comment, a
    Markdown heading or list item. Content is preserved, only line structure is
    flattened. Never raises; non-breaking input passes through unchanged.
    """
    return " ".join(str(text).splitlines())


def md_cell(text: str) -> str:
    """Make free text safe for one Markdown table cell.

    Line breaks collapse to spaces (a cell must be one line) and ``|`` is
    escaped to ``\\|`` so the column count of the row is preserved.
    """
    return single_line(text).replace("|", "\\|")
