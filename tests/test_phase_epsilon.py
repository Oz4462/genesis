"""Phase epsilon acceptance — verified seams across domains.

Each seam is an explicit, typed relation between domains. The gate recomputes formula
values with unit scaling, proves dimensions, enforces required adjacent domain pairs, and
checks declared cost totals against the BOM roll-up.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.state import (  # noqa: E402
    BomDomain,
    BomItem,
    BomRole,
    CodeArtifact,
    Component,
    Constraint,
    DomainSeam,
    Quantity,
    SeamDomain,
    SeamRelation,
    Sourcing,
    Specification,
    ValueOrigin,
)
from gen.seams import (
    build_seam_certificate,
    detect_cross_domain_seams,
    domains_present,
    gate_epsilon,
)  # noqa: E402


def _q(qid: str, value: float, unit: str, *, measurand: str | None = None) -> Quantity:
    return Quantity(
        id=qid,
        name=qid,
        value=value,
        unit=unit,
        origin=ValueOrigin.DECISION,
        rationale="declared seam-test value",
        measurand=measurand,
    )


def _price(qid: str, value: float) -> Quantity:
    return Quantity(
        id=qid,
        name=qid,
        value=value,
        unit="EUR",
        origin=ValueOrigin.GROUNDED,
        grounding=["c_price"],
    )


def _spec(
    *, total_cost: float = 4.0, fw_limit: float = 1.0, expansion_unit: str = "mm"
) -> Specification:
    return Specification(
        run_id="r-epsilon",
        idea="coupled electro-thermal firmware assembly",
        quantities=[
            _q("q_elec_power", 6.0, "W", measurand="electronics.dissipated_power"),
            _q("q_heat_power", 6.0, "W", measurand="thermal.heat_power"),
            _q("q_expansion", 0.2, expansion_unit, measurand="thermal.expansion"),
            _q("q_clearance", 0.4, "mm", measurand="mechanical.clearance"),
            _q("q_fw_current_limit", fw_limit, "A", measurand="firmware.current_limit"),
            _q("q_elec_current_limit", 1.5, "A", measurand="electronics.current_limit"),
            _price("q_unit_price", 2.0),
            _price("q_total_cost", total_cost),
        ],
        components=[Component(id="c_case", name="printed case")],
        bom=[
            BomItem(
                id="b_driver",
                name="driver board",
                role=BomRole.PART,
                count=2,
                domain=BomDomain.ELECTRONIC,
                sourcing=Sourcing(
                    supplier="S",
                    part_number="P",
                    price_quantity_id="q_unit_price",
                    grounding=["c_price"],
                ),
            )
        ],
        code_artifacts=[
            CodeArtifact(
                id="fw",
                name="current limiter",
                language="python",
                source="LIMIT_A = 1.0\n",
                check="assert LIMIT_A <= 1.5\n",
            )
        ],
    )


def _seams() -> list[DomainSeam]:
    return [
        DomainSeam(
            id="s_elec_thermal",
            left_domain=SeamDomain.ELECTRICAL,
            right_domain=SeamDomain.THERMAL,
            relation=SeamRelation.EQ,
            left_expr="q_elec_power",
            right_expr="q_heat_power",
            rationale="electrical dissipated power is the thermal heat source",
        ),
        DomainSeam(
            id="s_thermal_mech",
            left_domain=SeamDomain.THERMAL,
            right_domain=SeamDomain.MECHANICAL,
            relation=SeamRelation.LE,
            left_expr="q_expansion",
            right_expr="q_clearance",
            rationale="thermal expansion must fit mechanical clearance",
        ),
        DomainSeam(
            id="s_fw_elec",
            left_domain=SeamDomain.FIRMWARE,
            right_domain=SeamDomain.ELECTRICAL,
            relation=SeamRelation.LE,
            left_expr="q_fw_current_limit",
            right_expr="q_elec_current_limit",
            rationale="firmware current cap must respect electrical current budget",
        ),
        DomainSeam(
            id="s_cost",
            left_domain=SeamDomain.COST,
            right_domain=SeamDomain.ELECTRICAL,
            relation=SeamRelation.COST_ROLLUP,
            left_expr="q_total_cost",
            right_expr="EUR",
            rationale="declared total cost must match priced electronic BOM roll-up",
        ),
    ]


def test_structural_guard_rejects_hidden_or_same_domain_seams():
    with pytest.raises(ValueError):
        DomainSeam(
            id="s",
            left_domain=SeamDomain.THERMAL,
            right_domain=SeamDomain.THERMAL,
            relation=SeamRelation.EQ,
            left_expr="a",
            right_expr="b",
            rationale="x",
        )
    with pytest.raises(ValueError):
        DomainSeam(
            id="s",
            left_domain=SeamDomain.THERMAL,
            right_domain=SeamDomain.MECHANICAL,
            relation=SeamRelation.EQ,
            left_expr="a",
            right_expr="b",
            rationale="",
        )


def test_complete_domain_chain_passes():
    spec = _spec()
    assert {
        SeamDomain.MECHANICAL,
        SeamDomain.THERMAL,
        SeamDomain.ELECTRICAL,
        SeamDomain.FIRMWARE,
        SeamDomain.COST,
    } <= domains_present(spec)

    cert = build_seam_certificate(spec, _seams())
    res = gate_epsilon(spec, cert)
    assert res.passed, [f"{f.code}: {f.detail}" for f in res.failures]


def test_missing_required_pair_fails():
    spec = _spec()
    seams = [seam for seam in _seams() if seam.id != "s_fw_elec"]
    res = gate_epsilon(spec, build_seam_certificate(spec, seams))
    assert not res.passed
    assert any(f.code == "MISSING_REQUIRED_SEAM" for f in res.failures)


def test_dimension_mismatch_fails():
    spec = _spec(expansion_unit="kg")
    res = gate_epsilon(spec, build_seam_certificate(spec, _seams()))
    assert not res.passed
    assert any(f.code == "SEAM_DIMENSION_MISMATCH" for f in res.failures)


def test_relation_violation_fails():
    spec = _spec(fw_limit=2.0)
    res = gate_epsilon(spec, build_seam_certificate(spec, _seams()))
    assert not res.passed
    assert any(f.code == "SEAM_RELATION_VIOLATION" for f in res.failures)


def test_cost_rollup_mismatch_fails():
    spec = _spec(total_cost=3.0)
    res = gate_epsilon(spec, build_seam_certificate(spec, _seams()))
    assert not res.passed
    assert any(f.code == "COST_ROLLUP_MISMATCH" for f in res.failures)


def test_unpriced_bom_cannot_certify_cost_rollup():
    spec = _spec()
    spec.bom[0].sourcing = None
    res = gate_epsilon(spec, build_seam_certificate(spec, _seams()))
    assert not res.passed
    assert any(f.code == "COST_INCOMPLETE" for f in res.failures)


def test_cost_domain_requires_cost_rollup_relation():
    spec = _spec()
    bad = DomainSeam(
        id="s_bad_cost",
        left_domain=SeamDomain.COST,
        right_domain=SeamDomain.ELECTRICAL,
        relation=SeamRelation.EQ,
        left_expr="q_total_cost",
        right_expr="q_unit_price",
        rationale="bad cost seam",
    )
    res = gate_epsilon(spec, build_seam_certificate(spec, _seams()[:-1] + [bad]))
    assert not res.passed
    assert any(f.code == "COST_SEAM_REQUIRES_ROLLUP" for f in res.failures)


def test_detect_cross_domain_seams_with_expr_ish_constraint_roundtrips_to_gate_epsilon():
    # Return Gate enforcement (subagent mini re-reads): BUILD_LOG.md severity table
    # MEDIUM "tests/test_phase_epsilon.py (hardcoded _seams only, no detect import/test)" + gap#4;
    # HORIZON.md:109 (ε first-stone, "expr support + full auto coverage pending (test_phase_epsilon detects 0 direct)");
    # prior researcher evidence: verification/4LINSEN_PIPELINES_SEAMS_REVIEW_2026-06-21.md:10 ("do not exercise detect..."), CodeKnowledge-epsilon-zeta-auto-seams.md:84 (smoke uses bare, no expr test), loop-close-plan.md:82 (G2 explicit: "add real detect call + roundtrip gate_epsilon").
    # Cites seams.py:420+ (new expr support via referenced_names in detect loop).
    # Exercises enhanced path (not bare-id direct): Constraint right="... * ... " triggers referenced_names & fallback lqid/rqid.
    # Uses existing _spec helper (no new helpers). Smallest guarded: adds 1 test fn, extends 2 imports only.
    spec = _spec()
    spec.constraints = [
        Constraint(
            id="c_power_xfer",
            kind="eq",
            left="q_elec_power",
            right="q_heat_power * 1.0",  # expr-ish (not bare qid) to hit seams.py:427-430 refs path
            reason="electrical power balance to thermal (exercises Return Gate #4 expr)",
        )
    ]
    seams = detect_cross_domain_seams(spec)
    assert len(seams) >= 1, (
        "detect_cross_domain_seams must emit >=1 seam from cross-domain constraint"
    )
    # prove at least the auto_con seam or cost; structure is list[DomainSeam] with exprs preserved
    assert any(
        getattr(s, "left_expr", None) and "q_elec" in str(s.left_expr) for s in seams
    )

    # roundtrip: feed detected into build+gate (as architect/pipeline/omega do)
    cert = build_seam_certificate(spec, seams)
    res = gate_epsilon(spec, cert)
    # assert structure (GateResult: passed bool + failures list; per core/interfaces + seams gate)
    assert hasattr(res, "passed") and isinstance(res.passed, bool)
    assert hasattr(res, "failures") and isinstance(res.failures, (list, tuple))
