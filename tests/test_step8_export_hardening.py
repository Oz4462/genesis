"""Schritt-8-Härtungen (Review 2026-07-04): src/gen/export/ — Injection, Tabellen, Präzision.

Findings aus dem Paket-Review:
  F1 Kommentar-/Heading-Injection: mehrzeilige spec.idea / comp.name brechen aus
     ``//``/``#``-Kommentaren aus → nicht-öffnendes .scad / nicht kompilierendes .py.
  F2 Markdown-Korruption: ``|`` und Newlines in name/rationale/reason sprengen Tabellen.
  F3 Single-Source + Byte-Genauigkeit: markdown.py umging fmt_number (inline ``:g``);
     fmt_number rundete auf 6 signifikante Stellen → Backends divergierten sichtbar.
     Fix: alles über fmt_number, Präzision ``.12g`` (Display-Rundung dokumentiert;
     stl.py %.9g bleibt bewusste Mesh-Format-Ausnahme; Zitate C-4 bleiben byte-genau).

Deterministisch, offline, kein LLM.

Run:  pytest tests/test_step8_export_hardening.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.state import (  # noqa: E402
    Component,
    GeometryNode,
    Quantity,
    Specification,
    ValueOrigin,
)
from gen.export._text import md_cell, single_line  # noqa: E402
from gen.export.build123d import specification_to_build123d  # noqa: E402
from gen.export.markdown import specification_to_markdown  # noqa: E402
from gen.export.numfmt import fmt_number  # noqa: E402
from gen.export.openscad import specification_to_openscad  # noqa: E402


def _q(qid: str, value: float, unit: str = "mm") -> Quantity:
    return Quantity(id=qid, name=qid, value=value, unit=unit,
                    origin=ValueOrigin.DECISION, rationale="test")


def _box(s: str = "s") -> GeometryNode:
    return GeometryNode(kind="box", params={"size_x": s, "size_y": s, "size_z": s})


EVIL_IDEA = 'ein Halter\nmit 45° Winkel + "Quotes"!'
EVIL_NAME = 'böses "Teil"\nzweite Zeile!'


def _evil_spec() -> Specification:
    return Specification(
        run_id="r-evil", idea=EVIL_IDEA,
        quantities=[_q("s", 10.0)],
        components=[
            Component(id="c_a", name=EVIL_NAME, geometry=_box()),
            Component(id="c_buy", name=EVIL_NAME, geometry=None),  # purchased comment path
        ],
    )


# --- F1: Kommentar-/Heading-Injection -------------------------------------------

def _assert_fragments_commented(text: str, marker: str) -> None:
    """Every free-text fragment must sit AFTER a comment marker on its own line
    (a heading/trailing comment is fine; a bare continuation line is the bug)."""
    for line in text.splitlines():
        for frag in ("Winkel", "zweite Zeile"):
            if frag in line:
                assert marker in line[: line.index(frag)], f"escaped from comment: {line!r}"
    assert "Winkel" in text and "zweite Zeile" in text   # nothing silently dropped


def test_single_line_collapses_all_newline_flavours():
    assert single_line("a\nb") == "a b"
    assert single_line("a\r\nb\rc") == "a b c"
    assert single_line("plain") == "plain"


def test_openscad_multiline_idea_and_name_stay_commented():
    _assert_fragments_commented(specification_to_openscad(_evil_spec()), "//")


def test_build123d_multiline_idea_and_name_still_compile():
    src = specification_to_build123d(_evil_spec())
    compile(src, "<b123d-export>", "exec")   # would raise SyntaxError pre-fix
    _assert_fragments_commented(src, "#")


def test_assembly_scad_multiline_idea_and_name_stay_commented():
    from gen.export.assembly import assembly_scad
    spec = _evil_spec()
    spec.assembly = [("c_a", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)]
    out = assembly_scad(spec)
    assert out is not None
    _assert_fragments_commented(out, "//")


def test_markdown_multiline_idea_and_component_name_stay_one_heading():
    md = specification_to_markdown(_evil_spec())
    heads = [ln for ln in md.splitlines() if ln.startswith("# Bauanleitung:")]
    assert len(heads) == 1 and "Winkel" in heads[0]      # idea collapsed into the H1
    comp_heads = [ln for ln in md.splitlines() if ln.startswith("### ")]
    assert comp_heads and all("zweite Zeile" in h for h in comp_heads if "c_a" in h)


# --- F2: Markdown-Tabellenzellen -------------------------------------------------

def _pipes(line: str) -> int:
    """Unescaped pipes = raw '|' minus escaped '\\|' (cell separators only)."""
    return line.count("|") - line.count("\\|")


def test_markdown_pipe_and_newline_in_quantity_cells_keep_table_shape():
    q = Quantity(id="q_x", name="a|b\nc", value=1.0, unit="mm",
                 origin=ValueOrigin.DECISION, rationale="r|s\nt")
    spec = Specification(run_id="r", idea="i", quantities=[q], components=[])
    md = specification_to_markdown(spec)
    rows = [ln for ln in md.splitlines() if "`q_x`" in ln]
    assert len(rows) == 1                                   # one row, one line
    assert _pipes(rows[0]) == 6                             # 5 columns → 6 separators
    assert "a\\|b c" in rows[0] and "r\\|s t" in rows[0]    # content kept, escaped


def test_markdown_pipe_in_bom_name_keeps_table_shape():
    from gen.core.state import BomItem, BomRole
    spec = Specification(
        run_id="r", idea="i", quantities=[],
        components=[], bom=[BomItem(id="b1", name="M4|Schraube\nlang", role=BomRole.PART, count=2)],
    )
    md = specification_to_markdown(spec)
    rows = [ln for ln in md.splitlines() if "M4" in ln]
    assert len(rows) == 1
    assert _pipes(rows[0]) == 6
    assert "M4\\|Schraube lang" in rows[0]


def test_markdown_multiline_step_and_decision_stay_single_line():
    from gen.core.state import Decision, Step
    spec = Specification(
        run_id="r", idea="i", quantities=[], components=[],
        steps=[Step(id="s1", index=1, action="bohren\nund senken", check="Sitz\nprüfen")],
        decisions=[Decision(id="d1", title="Farbe\nwahl", choice="rot\nmatt",
                            rationale="weil\nschön")],
    )
    md = specification_to_markdown(spec)
    assert "1. bohren und senken" in md
    assert "Prüfung: Sitz prüfen" in md
    assert "**Farbe wahl:** rot matt — weil schön" in md


# --- F3: Single-Source-Formatierung + .12g-Präzision -----------------------------

def test_fmt_number_keeps_clean_integers_and_fractions():
    assert fmt_number(60.0) == "60"
    assert fmt_number(4.5) == "4.5"
    assert fmt_number(2.25) == "2.25"


def test_fmt_number_carries_twelve_significant_digits():
    # pre-fix :g collapsed this to "1" — a visible 1e-9 loss between backends
    assert fmt_number(1.000000001) == "1.000000001"
    assert fmt_number(0.1234567890123) == "0.123456789012"


def test_markdown_routes_values_through_fmt_number():
    q = Quantity(id="q_fine", name="fein", value=1.000000001, unit="mm",
                 origin=ValueOrigin.DECISION, rationale="r")
    spec = Specification(run_id="r", idea="i", quantities=[q], components=[])
    md = specification_to_markdown(spec)
    assert "| 1.000000001 |" in md      # pre-fix: "| 1 |" via inline :g


def test_openscad_and_markdown_render_the_same_value_identically():
    val = 1.000000001
    q = Quantity(id="s", name="s", value=val, unit="mm",
                 origin=ValueOrigin.DECISION, rationale="r")
    spec = Specification(run_id="r", idea="i", quantities=[q],
                         components=[Component(id="c", name="c", geometry=_box())])
    scad = specification_to_openscad(spec)
    md = specification_to_markdown(spec)
    assert fmt_number(val) in scad and fmt_number(val) in md


def test_md_cell_escapes_pipes_and_collapses_newlines():
    assert md_cell("a|b") == "a\\|b"
    assert md_cell("a\nb|c") == "a b\\|c"
