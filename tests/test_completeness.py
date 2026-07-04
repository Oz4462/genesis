"""Tests for the completeness critic — soft, deterministic, orthogonal to soundness.

The critic warns (never fails) when a valid spec is probably under-specified: an
orphan quantity, an unused tool, a component with no BOM line, or a build that
never reaches a final artifact. The capstone (a complete spec) yields zero
warnings.

Run:  pytest tests/test_completeness.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.completeness import completeness_warnings  # noqa: E402
from gen.core.state import (  # noqa: E402
    BomItem,
    BomRole,
    Component,
    GeometryNode,
    Quantity,
    Specification,
    Step,
    ValueOrigin,
)
from gen.demo import capstone_spec  # noqa: E402


def _q(qid: str, value: float = 1.0) -> Quantity:
    return Quantity(id=qid, name=qid, value=value, unit="mm",
                    origin=ValueOrigin.DECISION, rationale="t")


def test_capstone_is_complete():
    assert completeness_warnings(capstone_spec()) == []


def test_orphan_quantity_warned():
    spec = Specification(run_id="r", idea="i", quantities=[_q("q_used"), _q("q_orphan")],
                         constraints=[])
    # q_used referenced by a constraint, q_orphan by nothing
    from gen.core.state import Constraint
    spec.constraints = [Constraint(id="k", kind="gt", left="q_used", right="0", reason="x")]
    warns = completeness_warnings(spec)
    assert any("q_orphan" in w for w in warns)
    assert not any("q_used" in w for w in warns)


def test_unused_tool_warned():
    spec = Specification(
        run_id="r", idea="i",
        bom=[BomItem(id="b_tool", name="hex key", role=BomRole.TOOL),
             BomItem(id="b_used", name="driver", role=BomRole.TOOL)],
        steps=[Step(id="s1", index=1, action="use the driver", check="ok", uses=["b_used"])],
    )
    warns = completeness_warnings(spec)
    assert any("b_tool" in w for w in warns)
    assert not any("b_used" in w for w in warns)


def test_component_without_bom_line_warned():
    geom = GeometryNode(kind="box", params={"size_x": "q", "size_y": "q", "size_z": "q"})
    spec = Specification(run_id="r", idea="i", quantities=[_q("q")],
                         components=[Component(id="c1", name="widget", geometry=geom)])
    warns = completeness_warnings(spec)
    assert any("c1" in w and "keine Stücklisten-Position" in w for w in warns)


def test_no_final_artifact_warned():
    # s1 makes a1, s2 consumes a1 and makes nothing new that survives
    spec = Specification(
        run_id="r", idea="i",
        steps=[
            Step(id="s1", index=1, action="make a1", check="ok", outputs=["a1"]),
            Step(id="s2", index=2, action="consume a1", check="ok", inputs=["a1"]),
        ],
    )
    assert any("kein finales Artefakt" in w for w in completeness_warnings(spec))


def test_complete_build_has_final_artifact():
    spec = Specification(
        run_id="r", idea="i",
        steps=[
            Step(id="s1", index=1, action="make a1", check="ok", outputs=["a1"]),
            Step(id="s2", index=2, action="finish into a2", check="ok",
                 inputs=["a1"], outputs=["a2"]),
        ],
    )
    assert not any("kein finales Artefakt" in w for w in completeness_warnings(spec))


# --- K-1: positive floors — an EMPTY spec must not read as "complete" -------------


def test_empty_spec_is_not_silently_complete():
    """The critic was purely negative: an empty spec produced [] and therefore read as
    'complete'. The positive floors warn — a plan with no steps, no BOM and no artifact
    is under-specified, surfaced softly, never blocked."""
    warns = completeness_warnings(Specification(run_id="r", idea="i"))
    assert any("keine Schritte" in w for w in warns)
    assert any("keine Stückliste" in w for w in warns)
    assert any("erzeugt kein Artefakt" in w for w in warns)


def test_positive_floors_stay_quiet_on_a_populated_spec():
    """A spec with steps, a BOM line and a step output triggers none of the floors."""
    spec = Specification(
        run_id="r", idea="i",
        bom=[BomItem(id="b", name="x", role=BomRole.PART)],
        steps=[Step(id="s1", index=1, action="build", check="ok", outputs=["a1"])],
    )
    warns = completeness_warnings(spec)
    assert not any("keine Schritte" in w for w in warns)
    assert not any("keine Stückliste" in w for w in warns)
    assert not any("erzeugt kein Artefakt" in w for w in warns)


def test_components_count_as_artifact_even_without_step_outputs():
    geom = GeometryNode(kind="box", params={"size_x": "q", "size_y": "q", "size_z": "q"})
    spec = Specification(
        run_id="r", idea="i", quantities=[_q("q")],
        components=[Component(id="c1", name="widget", geometry=geom)],
        bom=[BomItem(id="b1", name="widget", role=BomRole.PART, component_id="c1")],
        steps=[Step(id="s1", index=1, action="print", check="ok")],
    )
    assert not any("erzeugt kein Artefakt" in w for w in completeness_warnings(spec))


# --- K-2: measurand-consumed quantities are not orphans ---------------------------


def test_filament_price_quantity_is_not_an_orphan():
    """costing.bom_cost consumes the filament price BY MEASURAND, not by id — the
    orphan check must know that channel, or every priced print plan gets a false warning."""
    from gen.core.state import ValueOrigin as VO
    q_fil = Quantity(id="q_fil", name="Filament-Preis", value=0.05, unit="EUR/g",
                     origin=VO.GROUNDED, grounding=["c"],
                     measurand="material.filament_price")
    spec = Specification(run_id="r", idea="i", quantities=[q_fil],
                         bom=[BomItem(id="b", name="x", role=BomRole.PART)],
                         steps=[Step(id="s1", index=1, action="a", check="ok", outputs=["o"])])
    assert not any("q_fil" in w for w in completeness_warnings(spec))


# --- K-3: drift guard — the reference walker must track core/state.py -------------


def test_reference_walker_tracks_the_id_carrying_fields_of_state():
    """Regression guard: the set of quantity-id-carrying field names in core/state.py is
    pinned here. If a new field appears (e.g. ``foo_quantity_id``), this test fails and
    forces _referenced_quantity_ids (and this pin) to be updated — no silent orphan drift."""
    import re
    from pathlib import Path

    import gen.core.state as state

    source = Path(state.__file__).read_text(encoding="utf-8")
    found = set(re.findall(r"^\s+(\w*quantity\w*):", source, flags=re.M))
    assert found == {
        "quantity_ids",       # Component — walked
        "price_quantity_id",  # Sourcing — walked
        "quantity_refs",      # Step — walked
        "torque_quantity_id", # Step — walked
        "quantity_id",        # DesignObjective (γ+ goal) — NOT part of Specification
    }


def test_every_reference_channel_suppresses_the_orphan_warning():
    """Functional drift guard: one spec that uses EVERY id-carrying channel — derivation
    inputs, component quantity_ids/material_density/geometry params, constraint expression,
    step refs/torque, sourcing price, site available_space — yields zero orphan warnings."""
    from gen.core.state import (
        Constraint, Derivation, SiteRequirements, Sourcing, ValueOrigin as VO,
    )
    qs = [_q(f"q_{n}") for n in
          ("deriv_in", "comp", "rho", "geo", "constr", "stepref", "torque", "sx", "sy", "sz")]
    qs.append(Quantity(id="q_price", name="q_price", value=1.0, unit="EUR",
                       origin=VO.GROUNDED, grounding=["c"]))
    qs.append(Quantity(id="q_derived", name="q_derived", value=1.0, unit="mm",
                       origin=VO.DERIVED, derivation=Derivation(formula="q_deriv_in",
                                                                inputs=("q_deriv_in",))))
    geom = GeometryNode(kind="box", params={"size_x": "q_geo", "size_y": "q_geo",
                                            "size_z": "q_geo"})
    spec = Specification(
        run_id="r", idea="i", quantities=qs,
        components=[Component(id="c1", name="w", geometry=geom, quantity_ids=["q_comp"],
                              material_density="q_rho")],
        constraints=[Constraint(id="k", kind="gt", left="q_constr", right="0", reason="x")],
        steps=[Step(id="s1", index=1, action="a", check="ok", outputs=["o"],
                    quantity_refs=["q_stepref"], torque_quantity_id="q_torque")],
        bom=[BomItem(id="b1", name="w", role=BomRole.PART, component_id="c1",
                     sourcing=Sourcing(supplier="S", part_number="P",
                                       price_quantity_id="q_price", grounding=["c"]))],
        site=SiteRequirements(available_space=("q_sx", "q_sy", "q_sz")),
    )
    # q_derived itself is referenced by nothing — every OTHER quantity must be covered
    warns = [w for w in completeness_warnings(spec) if "deklariert" in w]
    assert [w for w in warns if "q_derived" not in w] == []


# --- K-4: constraint parsing tolerates exactly the parser's own failure ------------


def test_malformed_constraint_does_not_crash_the_critic():
    """A malformed constraint expression is a γ failure, not ours — the critic must
    neither crash nor mark anything referenced from it (FormulaError is tolerated)."""
    from gen.core.state import Constraint
    spec = Specification(run_id="r", idea="i", quantities=[_q("q_orphan")],
                         constraints=[Constraint(id="k", kind="gt", left="1 +",
                                                 right="import os", reason="x")])
    warns = completeness_warnings(spec)          # must not raise
    assert any("q_orphan" in w for w in warns)
