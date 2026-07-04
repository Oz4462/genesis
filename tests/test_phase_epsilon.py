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
from gen.seams import build_seam_certificate, domains_present, gate_epsilon, required_seam_pairs, _looks_isru, _looks_life_support  # noqa: E402


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


# --- Radiation optional domain tests (linear filtered chain for co-design seams) ---

def _spec_radiation(*, with_elec: bool = True) -> Specification:
    """Space spec with RADIATION + THERMAL (optionally + ELECTRICAL) to test insertion."""
    qs = [
        _q("q_heat", 80.0, "W", measurand="thermal.heat_power"),
        _q("q_absorbed", 100.0, "W", measurand="thermal.radiation_absorbed"),
        _q("q_dose", 2.5, "Sv", measurand="radiation.total_ionizing_dose"),
        _q("q_emiss", 0.8, "1", measurand="material.emissivity"),
        _q("q_area", 0.5, "m^2", measurand="surface.area"),
        _q("q_t", 300.0, "K", measurand="thermal.temperature"),
    ]
    if with_elec:
        qs.append(_q("q_elec_p", 20.0, "W", measurand="electronics.dissipated_power"))
    return Specification(
        run_id="r-rad",
        idea="space radiator with vacuum radiation balance",
        quantities=qs,
        components=[Component(id="c_rad", name="radiator panel")],
        bom=[BomItem(id="b_e", name="rad controller", role=BomRole.PART, count=1, domain=BomDomain.ELECTRONIC)] if with_elec else [],
    )


def _rad_thermal_seam() -> DomainSeam:
    return DomainSeam(
        id="s_rad_thermal",
        left_domain=SeamDomain.THERMAL,
        right_domain=SeamDomain.RADIATION,
        relation=SeamRelation.EQ,
        left_expr="q_heat",
        right_expr="q_absorbed",  # simplified; real would use net expressions (see vacuum_radiation_balance_check)
        rationale="vacuum radiation is the thermal rejection mechanism (Stefan-Boltzmann dominant)",
    )


def _rad_elec_seam() -> DomainSeam:
    return DomainSeam(
        id="s_rad_elec",
        left_domain=SeamDomain.RADIATION,
        right_domain=SeamDomain.ELECTRICAL,
        relation=SeamRelation.LE,
        left_expr="q_dose",
        right_expr="q_elec_p",  # placeholder; real: dose <= elec_tid_budget
        rationale="radiation dose on electronics (future TID derating, SEE); links to rad-elec co-design",
    )


def test_filtered_chain_restores_therm_elec_for_non_radiation():
    """Repro case: inserting RADIATION into _CHAIN must not drop THERMAL-ELECTRICAL
    adjacency for terrestrial specs (power dissipation always sources heat).
    """
    spec = _spec()  # the original electro-thermal-fw without radiation
    present = domains_present(spec)
    assert SeamDomain.RADIATION not in present
    req = required_seam_pairs(spec)
    # Must include THERMAL <-> ELECTRICAL (in either order)
    assert any(set(p) == {SeamDomain.THERMAL, SeamDomain.ELECTRICAL} for p in req), req
    # MECH-THERM and ELEC-FW still present
    assert any(set(p) == {SeamDomain.MECHANICAL, SeamDomain.THERMAL} for p in req)
    assert any(set(p) == {SeamDomain.ELECTRICAL, SeamDomain.FIRMWARE} for p in req)


def test_radiation_domain_inserts_correct_adjacencies():
    """When RADIATION present (space), explicit adjacencies (per decision against auto RAD-ELEC)
    require THERM-RAD (additive) + preserve core THERM-ELEC (power-heat always coupled).
    No auto RAD-ELEC (dose effects require explicit justification + test).
    """
    spec = _spec_radiation(with_elec=True)
    present = domains_present(spec)
    assert {SeamDomain.THERMAL, SeamDomain.RADIATION, SeamDomain.ELECTRICAL} <= present
    req = required_seam_pairs(spec)
    assert any(set(p) == {SeamDomain.THERMAL, SeamDomain.RADIATION} for p in req)
    # Decision: no auto RAD-ELEC
    assert not any(set(p) == {SeamDomain.RADIATION, SeamDomain.ELECTRICAL} for p in req)
    # Core THERM-ELEC still required even with RAD (explicit list preserves it)
    assert any(set(p) == {SeamDomain.THERMAL, SeamDomain.ELECTRICAL} for p in req)


def test_radiation_seam_passes_gate_when_domains_present():
    """Example seam for radiation-thermal; gate accepts when declared and relation holds."""
    spec = _spec_radiation(with_elec=False)
    # Supply a seam that covers the required THERM-RAD (and MECH if present)
    # For minimal: also need MECH-THERM? our _spec_radiation has no clear mech quantities for seam expr, so provide only rad one + ensure minimal
    # To keep simple we build a minimal passing case using quantities we have.
    # Extend spec minimally for a mech-therm if needed, but test focuses on rad coupling.
    seams = [_rad_thermal_seam()]
    # Note: this may trigger MECH-THERM req if MECH detected via component; supply a trivial one if needed.
    # For this test we use a spec variant without forcing extra.
    cert = build_seam_certificate(spec, seams)
    res = gate_epsilon(spec, cert)
    # If MECH present (via component) we may have missing MECH-THERM; adjust by providing one using existing q if possible.
    # Simpler: check that rad-therm pair is covered, and any MISSING are only non-rad.
    missing_rad = any("RADIATION" in (f.detail or "") or "thermal" in (f.detail or "").lower() and "radiation" in (f.detail or "").lower() for f in res.failures)
    # The gate may fail on other reqs (MECH-THERM etc) but must not complain about missing rad-therm once provided.
    # We accept either pass or only non-rad failures.
    if not res.passed:
        rad_missing = [f for f in res.failures if "RADIATION" in str(f) or ("thermal" in str(f).lower() and "radiation" in str(f).lower())]
        assert not rad_missing, rad_missing
    # Provide fuller seams for clean pass in variant that also satisfies mech.
    # Rebuild a spec that triggers fewer domains for isolation + matching values for EQ seam.
    spec_min = Specification(
        run_id="r-rad-min",
        idea="pure rad-therm",
        quantities=[
            _q("q_heat", 100.0, "W", measurand="thermal.heat_power"),
            _q("q_absorbed", 100.0, "W", measurand="thermal.radiation_absorbed"),
            _q("q_dose", 2.5, "Sv", measurand="radiation.total_ionizing_dose"),
        ],
        components=[],
        bom=[],
    )
    seams_min = [_rad_thermal_seam()]
    res_min = gate_epsilon(spec_min, build_seam_certificate(spec_min, seams_min))
    # For pure THERM+RAD present, only that pair required → should pass with the seam.
    assert res_min.passed, [f"{f.code}: {f.detail}" for f in res_min.failures]


def test_missing_rad_seam_fails_when_radiation_present():
    spec = _spec_radiation(with_elec=False)
    # No seams at all → should fail on required (incl rad-therm)
    res = gate_epsilon(spec, build_seam_certificate(spec, []))
    assert not res.passed
    assert any(f.code == "MISSING_REQUIRED_SEAM" for f in res.failures)


def test_therm_elec_seam_triggered_for_quantity_only_t_e_spec():
    """Befund 1 amplification fix + domains_present improvement: T+E via measurands
    (no netlist, no ELECTRONIC bom, no components) must still set both domains so
    THERM-ELEC pair is required → needs_seams=True in assess (no skipped gate).
    """
    spec = Specification(
        run_id="r-te-qty",
        idea="elec power to heat only quantities",
        quantities=[
            _q("pwr", 10.0, "W", measurand="electronics.dissipated_power"),
            _q("heat", 10.0, "W", measurand="thermal.heat_power"),
            _q("cur", 2.0, "A", measurand="electronics.current"),
        ],
        components=[],
        bom=[],
        # deliberately no netlist, no bom domains, no code
    )
    present = domains_present(spec)
    assert SeamDomain.THERMAL in present
    assert SeamDomain.ELECTRICAL in present
    req = required_seam_pairs(spec)
    assert any(set(p) == {SeamDomain.THERMAL, SeamDomain.ELECTRICAL} for p in req)
    # gate would be triggered in assess (needs_seams)


# --- ISRU / LIFE_SUPPORT domain + seam pair tests (per auflage on 744bd2d; explicit for multi-planetary) ---
# Use _q helper for consistency with existing style. New domains must produce specific required pairs.
# These increase coverage on domains_present/required_seam_pairs + _looks_* and prevent Befund regressions.


def test_isru_domain_detection_and_required_pairs():
    """ISRU via measurand prefix + markers; asserts exact required pairs:
    (electrical, isru), (thermal, isru), (mechanical, isru), (isru, cost) when cost present.
    """
    spec = Specification(
        run_id="r-isru-test",
        idea="mars isru electrolysis plant",
        quantities=[
            _q("water", 100.0, "kg", measurand="isru.water_input_kg"),
            _q("o2", 25.0, "kg", measurand="isru.o2_yield"),
            _q("pwr", 5000.0, "W", measurand="electronics.dissipated_power"),  # triggers ELECTRICAL
            _q("heat", 4000.0, "W", measurand="thermal.heat_power"),  # THERMAL
        ],
        components=[Component(id="c_excav", name="regolith excavator")],  # MECHANICAL
        bom=[
            BomItem(id="b_reactor", name="isru reactor", role=BomRole.PART, count=1, domain=BomDomain.MECHANICAL),
            # PART → COST domain present
        ],
    )
    present = domains_present(spec)
    assert SeamDomain.ISRU in present
    assert SeamDomain.ELECTRICAL in present
    assert SeamDomain.THERMAL in present
    assert SeamDomain.MECHANICAL in present
    assert SeamDomain.COST in present

    req = required_seam_pairs(spec)
    assert any(set(p) == {SeamDomain.ELECTRICAL, SeamDomain.ISRU} for p in req), req
    assert any(set(p) == {SeamDomain.THERMAL, SeamDomain.ISRU} for p in req), req
    assert any(set(p) == {SeamDomain.MECHANICAL, SeamDomain.ISRU} for p in req), req
    assert any(set(p) == {SeamDomain.ISRU, SeamDomain.COST} for p in req), req
    # core pairs still required independently
    assert any(set(p) == {SeamDomain.THERMAL, SeamDomain.ELECTRICAL} for p in req)


def test_life_support_domain_and_required_pairs():
    """LIFE_SUPPORT detection + pairs: (thermal, life_support); with RADIATION also (radiation, life_support)."""
    qs = [
        _q("crew", 4.0, "1", measurand="life_support.crew"),
        _q("o2c", 0.84, "kg/day", measurand="life_support.o2_consumption_rate"),
        _q("close", 0.7, "1", measurand="life_support.o2_closure"),
        _q("heat", 200.0, "W", measurand="thermal.heat_power"),
    ]
    spec = Specification(
        run_id="r-life",
        idea="habitat eclss",
        quantities=qs,
        components=[Component(id="c_hab", name="habitat module")],
        bom=[],
    )
    present = domains_present(spec)
    assert SeamDomain.LIFE_SUPPORT in present
    assert SeamDomain.THERMAL in present
    req = required_seam_pairs(spec)
    assert any(set(p) == {SeamDomain.THERMAL, SeamDomain.LIFE_SUPPORT} for p in req), req

    # add radiation to trigger RAD + LIFE pair
    qs2 = list(qs) + [
        _q("dose", 1.0, "Sv", measurand="radiation.total_ionizing_dose"),
    ]
    spec_rad = Specification(
        run_id="r-life-rad",
        idea="space habitat with radiation",
        quantities=qs2,
        components=[Component(id="c_hab", name="habitat")],
        bom=[],
    )
    present_rad = domains_present(spec_rad)
    assert SeamDomain.RADIATION in present_rad
    assert SeamDomain.LIFE_SUPPORT in present_rad
    req_rad = required_seam_pairs(spec_rad)
    assert any(set(p) == {SeamDomain.RADIATION, SeamDomain.LIFE_SUPPORT} for p in req_rad), req_rad
    assert any(set(p) == {SeamDomain.THERMAL, SeamDomain.LIFE_SUPPORT} for p in req_rad)


def test_isru_false_positive_regression_german_and_substrings():
    """FP regression: German terms ("isrundes", "spannungskonzentrationsfaktor", "q_kt") + non-matching
    must return False for _looks_isru. Hardening (padded whole-word) must not regress to naive substring.
    """
    # German compound "isrundes"
    q_de = Quantity(
        id="q_desc",
        name="isrundes Bauteil",
        value=1.0,
        unit="1",
        origin=ValueOrigin.DECISION,
        rationale="FP regression test",
        measurand="material.desc",
    )
    assert not _looks_isru(q_de)

    # q_kt + German Kt factor name
    q_kt = Quantity(
        id="q_kt",
        name="Spannungskonzentrationsfaktor",
        value=2.5,
        unit="1",
        origin=ValueOrigin.DECISION,
        rationale="FP regression test",
        measurand="mechanical.kt",
    )
    assert not _looks_isru(q_kt)

    # unrelated that might contain letters
    q_other = _q("q_sp", 10.0, "MPa", measurand="structural.stress")
    assert not _looks_isru(q_other)

    # measurand not starting with isru. prefix and no isolated 'isru' token (e.g. compound without boundary)
    q_prefix = _q("bad", 1.0, "kg", measurand="foo.isrubaz")
    assert not _looks_isru(q_prefix)


def test_life_support_false_positive_regression():
    """Similar FP regression guard for _looks_life_support (German + substring traps e.g. 'lifetime')."""
    q_lifetime = Quantity(
        id="q_life",
        name="lifetime estimate",
        value=1000.0,
        unit="h",
        origin=ValueOrigin.DECISION,
        rationale="FP regression",
    )
    assert not _looks_life_support(q_lifetime)

    q_lebens = Quantity(
        id="q_leb",
        name="Lebensdauer und crew",
        value=5.0,
        unit="a",
        origin=ValueOrigin.DECISION,
        rationale="FP german",
        measurand="system.lebensdauer",
    )
    assert not _looks_life_support(q_lebens)

    # o2 without life_support. prefix
    q_o2 = _q("q_o2", 1.0, "kg", measurand="gas.o2_pure")
    assert not _looks_life_support(q_o2)

    # marker-like but not full
    q_partial = _q("q_atm", 101325, "Pa", measurand="atm.pressure")
    assert not _looks_life_support(q_partial)
