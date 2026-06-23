"""Characterization / facade-detector tests for the PURE rendering surface of
``src/gen/cli.py`` — ``format_report``, ``format_solution``,
``format_specification`` and ``render_spec``.

These are the deterministic, offline presentation functions (NOT the network /
pipeline ``--mode`` branches). The point of every test below is to prove the
renderers CONSUME their input rather than emit a canned template:

  * a Quantity's numeric value and unit appear verbatim in the rendered text,
    and changing the value changes the rendered string (input is consumed);
  * the verified/grounded path renders the bullet list while the empty path
    renders the explicit honest-abstention line (the negative case, per the
    "keine stillen Defaults" principle — abstention is a valid output);
  * ``render_spec`` dispatches by ``fmt`` and an unknown format falls through to
    the human-readable text renderer, while the real format selectors each
    return a distinct, non-empty string.

The spec under audit reads as REAL; no source defect was found, so cli.py is
left unchanged (per "change nothing if correct").
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gen.cli import (
    format_report,
    format_solution,
    format_specification,
    render_spec,
)
from gen.core.state import (
    Approach,
    Quantity,
    Report,
    SolutionReport,
    Specification,
    ValueOrigin,
)

# --- shared builders (components-free: keeps the non-text render paths free of
#     real CAD / network dependencies, as the task requires) -------------------


def _decision_quantity(value: float, *, qid: str = "q_load",
                       name: str = "Last", unit: str = "kg") -> Quantity:
    """A DECISION quantity (needs a rationale, no grounding/derivation)."""
    return Quantity(
        id=qid, name=name, value=value, unit=unit,
        origin=ValueOrigin.DECISION, rationale="konservative Annahme",
    )


def _spec(value: float = 47.5, *, unit: str = "kg") -> Specification:
    return Specification(
        run_id="run-cli-char",
        idea="Ein wandmontierter Regalhalter",
        approach_id="ap1",
        quantities=[_decision_quantity(value, unit=unit)],
    )


# --- format_specification: the value+unit must appear and must track input ----


def test_format_specification_renders_value_and_unit_verbatim():
    text = format_specification(_spec(47.5, unit="kg"))
    # {q.value:g} renders 47.5 -> "47.5"; the unit is appended verbatim.
    assert "47.5" in text
    assert "kg" in text
    # The provenance label proves the DECISION origin branch is taken.
    assert "ENTSCHEIDUNG" in text
    # The idea and approach anchoring are echoed from the input, not hardcoded.
    assert "Ein wandmontierter Regalhalter" in text
    assert "ap1" in text


def test_format_specification_value_change_changes_output():
    """Facade-killer: a different numeric value must produce a different string.
    A canned template would render identically regardless of input."""
    low = format_specification(_spec(12.0))
    high = format_specification(_spec(47.5))
    assert low != high
    assert "12" in low and "47.5" not in low
    assert "47.5" in high and "12 kg" not in high


def test_format_specification_unit_is_consumed():
    """Changing only the unit changes the rendered string (unit is consumed)."""
    kg = format_specification(_spec(5.0, unit="kg"))
    newton = format_specification(_spec(5.0, unit="N"))
    assert kg != newton
    assert "5 kg" in kg
    assert "5 N" in newton


def test_format_specification_empty_spec_renders_abstention():
    """A spec asserting nothing (no components, no steps) must print the explicit
    honest-abstention line, not a fabricated build plan (the negative case)."""
    empty = Specification(run_id="r0", idea="Noch ungeklärte Idee")
    text = format_specification(empty)
    assert "keine behauptet — nichts konnte belegt werden" in text


@settings(max_examples=50)
@given(value=st.floats(min_value=1.0, max_value=1.0e6,
                       allow_nan=False, allow_infinity=False))
def test_format_specification_value_always_appears(value: float):
    """Property: for any finite, in-range value the renderer echoes the exact
    `:g`-formatted number — proving the value is always consumed, never canned."""
    text = format_specification(_spec(value))
    assert f"{value:g}" in text


# --- format_report: verified findings vs the explicit abstention line ---------


def test_format_report_renders_verified_findings():
    report = Report(
        run_id="r1",
        question="Welchen CAD-Kernel nutzt build123d?",
        body="build123d basiert auf dem OCCT-Kernel.",
        statement_to_claim={"build123d basiert auf dem OCCT-Kernel.": "c1"},
        sources_used=["https://build123d.readthedocs.io/"],
    )
    text = format_report(report)
    # The question and the verified body sentence are echoed as a bullet.
    assert "Welchen CAD-Kernel nutzt build123d?" in text
    assert "• build123d basiert auf dem OCCT-Kernel." in text
    assert "Verifizierte Befunde (jede Zeile" in text
    assert "https://build123d.readthedocs.io/" in text


def test_format_report_no_claims_renders_abstention_line():
    """Negative case: with no statement_to_claim, the report must render the
    explicit 'nichts konnte unabhängig verifiziert werden' abstention line."""
    report = Report(
        run_id="r2",
        question="Eine unbeantwortbare Frage?",
        body="",
        statement_to_claim={},
    )
    text = format_report(report)
    assert "keine — nichts konnte unabhängig verifiziert werden" in text
    assert "• " not in text  # no findings bullets when nothing is verified


def test_format_report_flips_between_findings_and_abstention():
    verified = Report(
        run_id="r3", question="Q", body="Ein belegter Befund.",
        statement_to_claim={"Ein belegter Befund.": "c1"},
    )
    empty = Report(run_id="r3", question="Q", body="", statement_to_claim={})
    assert format_report(verified) != format_report(empty)


# --- format_solution: grounded approaches vs the abstention line --------------


def test_format_solution_renders_grounded_approaches():
    sr = SolutionReport(
        run_id="b1",
        problem="Rate-Limiting für eine API.",
        approaches=[
            Approach(id="a1", name="Token-Bucket", grounding=["c1"],
                     tradeoffs=["c2"]),
        ],
    )
    text = format_solution(sr)
    assert "Rate-Limiting für eine API." in text
    assert "• Token-Bucket" in text
    assert "Beleg: c1" in text
    assert "Abwägungen: c2" in text


def test_format_solution_no_approaches_renders_abstention_line():
    """Negative case: no grounded approaches -> the explicit abstention line."""
    sr = SolutionReport(run_id="b2", problem="Ungelöstes Problem.")
    text = format_solution(sr)
    assert "keine — nichts konnte verankert werden" in text
    assert "• " not in text


def test_format_solution_flips_between_approaches_and_abstention():
    grounded = SolutionReport(
        run_id="b3", problem="P",
        approaches=[Approach(id="a1", name="Ansatz A", grounding=["c1"])],
    )
    empty = SolutionReport(run_id="b3", problem="P")
    assert format_solution(grounded) != format_solution(empty)


# --- render_spec: dispatch by fmt + unknown falls through to text -------------


def test_render_spec_text_routes_to_format_specification():
    spec = _spec()
    assert render_spec(spec, "text") == format_specification(spec)


def test_render_spec_unknown_fmt_falls_through_to_text():
    """An unrecognized format must fall through to the human-readable text
    renderer (the documented default), not raise or emit something else."""
    spec = _spec()
    assert render_spec(spec, "totally-unknown") == format_specification(spec)


def test_render_spec_formats_are_distinct_and_nonempty():
    """Each real format selector returns a distinct, non-empty string — proving
    the dispatch actually routes to different exporters, not one template."""
    spec = _spec()
    rendered = {fmt: render_spec(spec, fmt) for fmt in ("text", "md", "scad", "b123d")}
    for fmt, out in rendered.items():
        assert out.strip(), f"{fmt} rendered empty"
    # All four outputs are pairwise distinct.
    assert len(set(rendered.values())) == 4
    # Spot-check each exporter's signature header so we know the routing is real.
    assert rendered["md"].startswith("# Bauanleitung")
    assert "OpenSCAD" in rendered["scad"]
    assert "build123d" in rendered["b123d"]


def test_render_spec_consumes_value_in_quantity_table_formats():
    """The changed numeric value must propagate through the formats that render
    the quantity table (text + Markdown manual) — a canned exporter would ignore
    it. (scad/b123d render only the CSG *geometry*; a loose quantity not bound to
    any component geometry correctly does not appear there, so they are excluded.)"""
    for fmt in ("text", "md"):
        low = render_spec(_spec(12.0), fmt)
        high = render_spec(_spec(47.5), fmt)
        assert low != high, f"format {fmt} ignored the value change"
        assert "47.5" in high and "47.5" not in low
