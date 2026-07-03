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
    DomainSeam,
    Quantity,
    SeamDomain,
    SeamRelation,
    Sourcing,
    Specification,
    ValueOrigin,
)
from gen.seams import build_seam_certificate, domains_present, gate_epsilon  # noqa: E402


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


def _spec(*, total_cost: float = 4.0, fw_limit: float = 1.0, expansion_unit: str = "mm") -> Specification:
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
