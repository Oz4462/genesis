"""Tests for the Markdown build-manual exporter — deterministic, offline.

The exporter renders a complete γ spec as a shareable Markdown document. These
tests assert the document carries every depth section (quantities table, both
BOMs, cost, steps with tool/torque, constraints, decisions, site, δ validation
with volume/mass, and a Sources appendix of the ledger claim_ids) — built from
the SAME capstone spec the gates verify.

Run:  pytest tests/test_markdown.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.demo import capstone_spec  # noqa: E402
from gen.export.markdown import specification_to_markdown  # noqa: E402


def test_markdown_has_all_sections():
    md = specification_to_markdown(capstone_spec())
    assert md.startswith("# Build manual: A wall-mounted LED shelf bracket")
    assert "## Quantities" in md
    assert "| `q_load` | verified shelf load | 12 | kg | grounded in c_load |" in md
    assert "## Bill of materials (mechanical)" in md
    assert "## Bill of materials (electronics)" in md
    assert "McMaster-Carr #91290A115" in md and "0.42 EUR" in md
    assert "**Estimated cost:** 0.84 EUR (partial" in md
    assert "## Build steps" in md and "torque: 2.5 N*m" in md and "tool: 4 mm hex key" in md
    assert "## Checked constraints" in md
    assert "## Decision sheet" in md
    assert "## Site & environment" in md and "available space: 200 mm × 200 mm × 200 mm" in md
    assert "## Geometric validation" in md
    assert "volume: 28704.6 mm³ (exact)" in md
    assert "mass: 35.5937 g (exact)" in md
    assert "## Sources" in md and "- `c_price`" in md


def test_markdown_is_deterministic():
    a = specification_to_markdown(capstone_spec())
    b = specification_to_markdown(capstone_spec())
    assert a == b


def test_quantities_table_header_present():
    md = specification_to_markdown(capstone_spec())
    assert "| id | name | value | unit | provenance |" in md
    assert "|----|------|-------|------|------------|" in md
