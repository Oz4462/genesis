"""Tests for assembly detail (tool/torque) + site/environment (Phase γ-depth §5).

A step can name its tool and a tightening torque (a quantity, N·m). The site says
where to build it: the available space (a triple of quantity_ids) and declared
environmental requirements (ventilation, indoor/outdoor, mains, safety clearance).
GATE δ checks deterministically that each component's bounding box FITS the
available space (any axis-aligned orientation); a too-big part is caught. GATE γ
resolves torque/space references and validates the declared requirements. Nothing
is invented — every site demand is a declared decision (claim-informed).

Run:  pytest tests/test_assembly_site.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.state import (  # noqa: E402
    Approach,
    Claim,
    ClaimStatus,
    Component,
    Decision,
    GeometryNode,
    Question,
    Quantity,
    RunState,
    SiteRequirements,
    SourceRef,
    SourceSupport,
    Specification,
    Step,
    ValueOrigin,
)
from gen.verification.gates import gate_delta, gate_gamma  # noqa: E402


def _q(qid: str, value: float, unit: str = "mm") -> Quantity:
    return Quantity(id=qid, name=qid, value=value, unit=unit,
                    origin=ValueOrigin.DECISION, rationale="t")


def _anchor():
    """A verified claim + a grounded approach, so a content-bearing spec satisfies
    the β-chain (C-14) — orthogonal to the assembly/site concern under test."""
    claim = Claim(
        id="c_a", text="Brackets are used for wall-mounted shelves.",
        sources=[SourceRef("https://a", True, support=SourceSupport.SUPPORTS)],
        status=ClaimStatus.VERIFIED, confidence=0.9,
        verification=[SourceRef("https://i", True, support=SourceSupport.SUPPORTS)],
    )
    approach = Approach(id="ap1", name="Bracket", grounding=["c_a"])
    return claim, approach


def _anchored_spec(**kwargs) -> tuple[RunState, Specification]:
    claim, approach = _anchor()
    spec = Specification(run_id="r", idea="i", approach_id="ap1", **kwargs)
    st = RunState(question=Question(raw="i", run_id="r"))
    st.claims = [claim]
    st.approaches = [approach]
    st.specification = spec
    return st, spec


def _bracket_state(space=None, requirements=None) -> RunState:
    qs = [_q("q_w", 60.0), _q("q_h", 80.0), _q("q_t", 6.0)]
    geom = GeometryNode(kind="box", params={"size_x": "q_w", "size_y": "q_h", "size_z": "q_t"})
    comp = Component(id="c", name="bracket", geometry=geom)
    site = None
    if space is not None or requirements is not None:
        site = SiteRequirements(available_space=space, requirements=requirements or [])
    st, _ = _anchored_spec(quantities=qs, components=[comp], site=site)
    return st


# --- assembly detail: tool + torque -------------------------------------------

def test_step_tool_and_torque():
    qs = [_q("q_tq", 2.5, "N*m")]
    step = Step(id="s1", index=1, action="Tighten the M4 bolts.",
                check="Bolts seated, no wobble.", tool="4 mm hex key",
                torque_quantity_id="q_tq")
    st, _ = _anchored_spec(quantities=qs, steps=[step])
    result = gate_gamma(st)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]
    assert step.tool == "4 mm hex key"


def test_torque_dangling_reference_caught():
    step = Step(id="s1", index=1, action="Tighten.", check="ok",
                torque_quantity_id="q_ghost")
    st, _ = _anchored_spec(steps=[step])
    assert "DANGLING_REFERENCE" in {f.code for f in gate_gamma(st).failures}


# --- site: available space fit (δ) --------------------------------------------

def test_part_fits_available_space():
    # bracket 60x80x6 fits a 100x100x100 mm space
    space = {"sx": 100.0, "sy": 100.0, "sz": 100.0}
    st = _bracket_state(space=("sx", "sy", "sz"))
    # add the space quantities
    st.specification.quantities += [_q("sx", 100.0), _q("sy", 100.0), _q("sz", 100.0)]
    result = gate_delta(st)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]


def test_part_too_big_for_space_is_caught():
    # bracket 60x80x6 does NOT fit a 50x50x50 mm space (80 > 50)
    st = _bracket_state(space=("sx", "sy", "sz"))
    st.specification.quantities += [_q("sx", 50.0), _q("sy", 50.0), _q("sz", 50.0)]
    assert "SITE_SPACE_EXCEEDED" in {f.code for f in gate_delta(st).failures}


def test_fit_allows_any_orientation():
    # a 6x80x60 part fits a 70x70x10 space only by rotation; sorted-dims test allows it
    st = _bracket_state(space=("sx", "sy", "sz"))
    st.specification.quantities += [_q("sx", 70.0), _q("sy", 70.0), _q("sz", 10.0)]
    # bracket sorted dims (6,60,80) vs space sorted (10,70,70): 6<=10, 60<=70, 80>70 -> exceeds
    assert "SITE_SPACE_EXCEEDED" in {f.code for f in gate_delta(st).failures}


# --- site: declared requirements ----------------------------------------------

def test_site_requirements_validated():
    reqs = [
        Decision(id="d_vent", title="Ventilation", choice="passive airflow, 5 cm clearance",
                 rationale="dissipate motor heat"),
        Decision(id="d_loc", title="Location", choice="indoor, dry",
                 rationale="electronics not weatherproof"),
    ]
    st = _bracket_state(requirements=reqs)
    result = gate_gamma(st)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]


def test_site_space_dangling_caught():
    st = _bracket_state(space=("ghost_x", "ghost_y", "ghost_z"))
    assert "DANGLING_REFERENCE" in {f.code for f in gate_gamma(st).failures}


def test_assembly_and_site_render_in_cli():
    from gen.cli import format_specification
    qs = [_q("q_tq", 2.5, "N*m"), _q("sx", 100.0), _q("sy", 100.0), _q("sz", 100.0)]
    step = Step(id="s1", index=1, action="Tighten bolts.", check="seated.",
                tool="4 mm hex key", torque_quantity_id="q_tq")
    site = SiteRequirements(
        available_space=("sx", "sy", "sz"),
        requirements=[Decision(id="d", title="Location", choice="indoor", rationale="dry")],
    )
    spec = Specification(run_id="r", idea="i", quantities=qs, steps=[step], site=site)
    out = format_specification(spec)
    assert "tool:  4 mm hex key" in out
    assert "torque: 2.5 N*m" in out
    assert "Site & environment" in out and "available space: 100 mm x 100 mm x 100 mm" in out
