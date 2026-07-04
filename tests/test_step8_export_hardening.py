"""Schritt-8-Härtungen (Review 2026-07-04): src/gen/export/ — Injection, Tabellen, Präzision.

Findings aus dem Paket-Review:
  F1 Kommentar-/Heading-Injection: mehrzeilige spec.idea / comp.name brechen aus
     ``//``/``#``-Kommentaren aus → nicht-öffnendes .scad / nicht kompilierendes .py.
  F2 Markdown-Korruption: ``|`` und Newlines in name/rationale/reason sprengen Tabellen.
  F3 Single-Source + Byte-Genauigkeit: markdown.py umging fmt_number (inline ``:g``);
     fmt_number rundete auf 6 signifikante Stellen → Backends divergierten sichtbar.
     Fix: alles über fmt_number, Präzision ``.12g`` (Display-Rundung dokumentiert;
     stl.py %.9g bleibt bewusste Mesh-Format-Ausnahme; Zitate C-4 bleiben byte-genau).
  F4 Overlap-Overclaim: der PARTS-TRAY ignorierte interne translate/rotate — Teile
     konnten real überlappen, obwohl der Docstring Disjunktheit behauptete.
     Fix: Footprint aus der analytischen AABB (verification.geometry.aabb_of) +
     Zentrums-Kompensation bei der Platzierung → beweisbar disjunkte AABBs.
  F5 Stille PNG-Lücke: Nicht-Box-Teile fielen still aus dem Assembly-Render.
     Fix: cylinder/sphere-Bbox (d=2r) abgeleitet; nicht darstellbare Teile werden
     im Bild-Titel gemeldet, nie still verschluckt.
  F6 Skip-Konflation: specification_to_stl verschluckte JEDEN ExportError als
     Boolean-Skip. Fix: CsgBooleanRefusal (erwartete Kernel-Verweigerung) getrennt
     von echtem ExportError; specification_to_stl_report liefert (stl, skipped).
  F7 Degenerierte Facetten: der Primitiv-Mesher emittierte Nullflächen-Facetten
     (brep_stl filtert sie); der CLI-Fallback war ungegated. Fix: gleicher Filter
     in _triangles_to_stl + stl_integrity_check-Gate im CLI-Fallback.

Deterministisch, offline, kein LLM.

Run:  pytest tests/test_step8_export_hardening.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

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


# --- F4: PARTS-TRAY mit beweisbar disjunkten AABBs -------------------------------

def _tray_positions(scad: str) -> dict[str, tuple[float, float]]:
    """module-name → (x, y) of its tray placement, parsed from the layout lines."""
    out: dict[str, tuple[float, float]] = {}
    for ln in scad.splitlines():
        s = ln.strip()
        if s.startswith("translate([") and "();" in s:
            coords = s.split("translate([")[1].split("])")[0].split(",")
            module = s.split("])")[1].split("();")[0].strip()
            out[module] = (float(coords[0]), float(coords[1]))
    return out


def test_parts_tray_aabbs_are_disjoint_despite_inner_translate():
    """Pre-fix: _footprint walked to the root primitive and IGNORED an inner
    translate — a part offset by exactly the pitch landed on its neighbour."""
    from gen.verification.geometry import aabb_of
    qs = [_q("s6", 6.0), _q("d66", 66.0), _q("z0", 0.0)]
    inner = GeometryNode(
        kind="translate", params={"x": "d66", "y": "z0", "z": "z0"},
        children=[GeometryNode(kind="box", params={"size_x": "s6", "size_y": "s6", "size_z": "s6"})],
    )
    plain = GeometryNode(kind="box", params={"size_x": "s6", "size_y": "s6", "size_z": "s6"})
    spec = Specification(
        run_id="r", idea="i", quantities=qs,
        components=[Component(id="c_off", name="off", geometry=inner),
                    Component(id="c_plain", name="plain", geometry=plain)],
    )
    scad = specification_to_openscad(spec)
    pos = _tray_positions(scad)
    assert set(pos) == {"c_off", "c_plain"}
    qmap = {q.id: q for q in qs}
    boxes = {}
    for comp in spec.components:
        bb = aabb_of(comp.geometry, qmap)
        tx, ty = pos[comp.id]
        boxes[comp.id] = ((bb.min_x + tx, bb.max_x + tx), (bb.min_y + ty, bb.max_y + ty))
    (ax_, aX), (ay, aY) = boxes["c_off"]
    (bx, bX), (by, bY) = boxes["c_plain"]
    x_disjoint = aX <= bx or bX <= ax_
    y_disjoint = aY <= by or bY <= ay
    assert x_disjoint or y_disjoint, f"tray parts overlap: {boxes}"


# --- F5: Assembly-Render — cylinder/sphere-Bbox statt stillem Auslassen ----------

def test_bbox_dims_derives_cylinder_and_sphere_envelopes():
    from gen.export.assembly import _bbox_dims
    qs = {q.id: q for q in (_q("r", 5.0), _q("h", 4.0), _q("rs", 3.0))}
    cyl = GeometryNode(kind="cylinder", params={"radius": "r", "height": "h"})
    sph = GeometryNode(kind="sphere", params={"radius": "rs"})
    assert _bbox_dims(cyl, qs) == (10.0, 10.0, 4.0)
    assert _bbox_dims(sph, qs) == (6.0, 6.0, 6.0)
    # through an operation wrapper (first primitive found)
    wrapped = GeometryNode(kind="union", children=[cyl])
    assert _bbox_dims(wrapped, qs) == (10.0, 10.0, 4.0)


def test_bbox_dims_unresolvable_is_none_not_a_guess():
    from gen.export.assembly import _bbox_dims
    ghost = GeometryNode(kind="cylinder", params={"radius": "nope", "height": "nope"})
    assert _bbox_dims(ghost, {}) is None


# --- F6: Boolean-Skip getrennt von echtem ExportError ----------------------------

def _bool_geom() -> GeometryNode:
    return GeometryNode(kind="difference", children=[
        _box(), GeometryNode(kind="cylinder", params={"radius": "s", "height": "s"}),
    ])


def test_boolean_refusal_is_a_distinct_exportable_class():
    from gen.core.errors import ExportError
    from gen.export.stl import CsgBooleanRefusal, component_to_stl
    assert issubclass(CsgBooleanRefusal, ExportError)
    with pytest.raises(CsgBooleanRefusal):
        component_to_stl(Component(id="d", name="d", geometry=_bool_geom()),
                         {"s": _q("s", 10.0)})


def test_stl_report_names_boolean_skips():
    from gen.export.stl import specification_to_stl_report
    spec = Specification(
        run_id="r", idea="i", quantities=[_q("s", 10.0)],
        components=[Component(id="plate", name="plate", geometry=_box()),
                    Component(id="bored", name="bored", geometry=_bool_geom())],
    )
    stl, skipped = specification_to_stl_report(spec)
    assert "solid plate" in stl
    assert set(skipped) == {"bored"} and "kernel" in skipped["bored"].lower()


def test_stl_report_propagates_real_errors_instead_of_skipping():
    from gen.core.errors import ExportError
    from gen.export.stl import specification_to_stl, specification_to_stl_report
    spec = Specification(
        run_id="r", idea="i", quantities=[_q("s", 10.0)],
        components=[Component(id="plate", name="plate", geometry=_box()),
                    Component(id="bad", name="bad",
                              geometry=GeometryNode(kind="torus", params={}))],
    )
    with pytest.raises(ExportError):        # pre-fix: silently skipped, partial "success"
        specification_to_stl_report(spec)
    with pytest.raises(ExportError):
        specification_to_stl(spec)


# --- F7: Nullflächen-Filter + gegateter CLI-Fallback ------------------------------

def test_triangles_to_stl_drops_zero_area_facets():
    from gen.export.stl import _triangles_to_stl
    degenerate = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0))   # collinear
    good = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    out = _triangles_to_stl("t", [degenerate, good])
    assert out.count("facet normal") == 1


def test_triangles_to_stl_all_degenerate_raises():
    from gen.core.errors import ExportError
    from gen.export.stl import _triangles_to_stl
    degenerate = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0))
    with pytest.raises(ExportError):
        _triangles_to_stl("t", [degenerate])


def _no_kernel(monkeypatch):
    """Force the CLI stl path onto the primitive fallback (as if cadquery were absent)."""
    import gen.export.brep_stl as brep_stl
    from gen.core.errors import GeometryError

    def _raise(spec, **kw):
        raise GeometryError("kein Kernel (Test)")

    monkeypatch.setattr(brep_stl, "specification_to_brep_stl", _raise)


def test_cli_stl_fallback_emits_integrity_checked_mesh(monkeypatch):
    from gen.cli import render_spec
    _no_kernel(monkeypatch)
    spec = Specification(run_id="r", idea="i", quantities=[_q("s", 10.0)],
                         components=[Component(id="plate", name="plate", geometry=_box())])
    out = render_spec(spec, "stl")
    assert out.startswith("solid ")          # a real, gated mesh


def test_cli_stl_fallback_refuses_partial_export(monkeypatch):
    from gen.cli import render_spec
    _no_kernel(monkeypatch)
    spec = Specification(
        run_id="r", idea="i", quantities=[_q("s", 10.0)],
        components=[Component(id="plate", name="plate", geometry=_box()),
                    Component(id="bored", name="bored", geometry=_bool_geom())],
    )
    out = render_spec(spec, "stl")
    assert out.startswith("#") and "verweigert" in out and "bored" in out


def test_cli_stl_fallback_refuses_on_failed_integrity(monkeypatch):
    import gen.mesh_integrity as mesh_integrity
    from gen.cli import render_spec
    _no_kernel(monkeypatch)
    monkeypatch.setattr(mesh_integrity, "stl_integrity_check",
                        lambda stl: {"ok": False, "issues": ["kaputt (Test)"]})
    spec = Specification(run_id="r", idea="i", quantities=[_q("s", 10.0)],
                         components=[Component(id="plate", name="plate", geometry=_box())])
    out = render_spec(spec, "stl")
    assert out.startswith("#") and "verweigert" in out and "kaputt (Test)" in out
