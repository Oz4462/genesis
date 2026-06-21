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
