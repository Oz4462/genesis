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
    # the deliverable document is GERMAN (owner directive 2026-06-12): every
    # human-facing label/heading German, ids/units/values untouched
    assert md.startswith("# Bauanleitung: Ein wandmontierter LED-Regalhalter")
    assert "## Größen" in md
    assert "| `q_load` | belegte Regallast | 12 | kg | belegt durch c_load |" in md
    assert "## Stückliste (Mechanik)" in md
    assert "## Stückliste (Elektronik)" in md
    assert "| Werkzeug |" in md                  # BOM roles rendered as German labels
    assert "McMaster-Carr #91290A115" in md and "0.42 EUR" in md
    assert "**Geschätzte Kosten:** 0.84 EUR (unvollständig" in md
    assert ("## Bauschritte" in md and "Anzugsmoment: 2.5 N*m" in md
            and "Werkzeug: 4-mm-Innensechskantschlüssel" in md)
    assert "## Geprüfte Anforderungen" in md
    assert "## Entscheidungsblatt" in md
    assert "## Ort & Umgebung" in md and "verfügbarer Platz: 200 mm × 200 mm × 200 mm" in md
    assert "## Geometrische Validierung" in md
    assert "Volumen: 57409.1 mm³ (exakt)" in md
    assert "Masse: 71.1873 g (exakt)" in md
    assert "## Quellen" in md and "- `c_price`" in md


def test_markdown_is_deterministic():
    a = specification_to_markdown(capstone_spec())
    b = specification_to_markdown(capstone_spec())
    assert a == b


def test_quantities_table_header_present():
    md = specification_to_markdown(capstone_spec())
    assert "| id | Name | Wert | Einheit | Herkunft |" in md
    assert "|----|------|------|---------|----------|" in md
