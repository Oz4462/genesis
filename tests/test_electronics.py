"""Tests for the electronics domain (Phase γ-depth §4) — separate E-BOM + units.

Electronic components live in a separate electronics BOM (BomItem.domain =
ELECTRONIC), carry grounded spec quantities (voltage V, current A, power W,
resistance Ω, capacity Ah) backed by datasheet claims, and their compatibility is
checked by the same constraint mechanism. These tests pin the new electrical units
and that an electronics line passes GATE γ exactly like a mechanical one (sourcing
+ grounding rules apply identically).

Run:  pytest tests/test_electronics.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.state import (  # noqa: E402
    BomDomain,
    BomItem,
    BomRole,
    Claim,
    ClaimStatus,
    Question,
    Quantity,
    RunState,
    SourceRef,
    SourceSupport,
    Specification,
    ValueOrigin,
)
from gen.verification.gates import gate_gamma  # noqa: E402
from gen.verification.units import parse_unit, unit_scale  # noqa: E402


# --- the new electrical units --------------------------------------------------

def test_electrical_unit_dimensions():
    # V = W/A, ohm = V/A, Ah = A·s (charge), Wh = energy
    assert parse_unit("V") == parse_unit("W") / parse_unit("A")
    assert parse_unit("ohm") == parse_unit("V") / parse_unit("A")
    assert parse_unit("Ω") == parse_unit("ohm")
    assert parse_unit("Ah") == parse_unit("A") * parse_unit("s")
    assert parse_unit("Wh") == parse_unit("J")        # both energy


def test_electrical_prefixes_and_scale():
    assert parse_unit("mA") == parse_unit("A")        # milliamp is still current
    assert parse_unit("kohm") == parse_unit("ohm")
    assert unit_scale("mA") == pytest.approx(1e-3)
    assert unit_scale("Ah") == pytest.approx(3600.0)  # to coulombs
    assert unit_scale("mAh") == pytest.approx(3.6)


# --- a grounded electronic BOM line passes the gate ---------------------------

def _claim(cid: str, text: str) -> Claim:
    return Claim(
        id=cid, text=text,
        sources=[SourceRef(f"https://{cid}", True, support=SourceSupport.SUPPORTS)],
        status=ClaimStatus.VERIFIED, confidence=0.9,
        verification=[SourceRef(f"https://i/{cid}", True, support=SourceSupport.SUPPORTS)],
    )


def test_electronic_bom_line_with_grounded_spec_passes():
    dsheet = _claim("c_ds", "The Raspberry Pi 4 requires 5 V and draws up to 3 A.")
    qs = [
        Quantity(id="q_v", name="Pi voltage", value=5.0, unit="V",
                 origin=ValueOrigin.GROUNDED, grounding=["c_ds"]),
        Quantity(id="q_i", name="Pi current", value=3.0, unit="A",
                 origin=ValueOrigin.GROUNDED, grounding=["c_ds"]),
    ]
    pi = BomItem(id="b_pi", name="Raspberry Pi 4", role=BomRole.PART,
                 domain=BomDomain.ELECTRONIC, grounding=["c_ds"])
    st = RunState(question=Question(raw="i", run_id="r"))
    st.claims = [dsheet]
    st.specification = Specification(run_id="r", idea="i", quantities=qs, bom=[pi])
    result = gate_gamma(st)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]
    assert pi.domain is BomDomain.ELECTRONIC


def test_mechanical_and_electronic_split_render():
    from gen.cli import format_specification
    screw = BomItem(id="b_screw", name="M4 screw", role=BomRole.PART)
    pi = BomItem(id="b_pi", name="Raspberry Pi 4", role=BomRole.PART, domain=BomDomain.ELECTRONIC)
    spec = Specification(run_id="r", idea="i", bom=[screw, pi])
    out = format_specification(spec)
    assert "Stückliste (Mechanik):" in out
    assert "Stückliste (Elektronik):" in out
    # the Pi appears under electronics, the screw under mechanical
    mech_idx = out.index("(Mechanik)")
    elec_idx = out.index("(Elektronik)")
    assert out.index("M4 screw") < elec_idx
    assert out.index("Raspberry Pi 4") > elec_idx
    assert mech_idx < elec_idx


def test_internal_drc_uses_named_sourced_thresholds_and_is_non_vacuous():
    """The internal DRC must apply the NAMED, sourced DRC_* rules-of-thumb (not buried
    magic numbers) and actually CATCH a real violation — an undersized harness gauge and
    an over-dense board — while a clean, cool, well-separated board passes."""
    from gen.electronics import (
        run_internal_drc, Component, HarnessSpec, HarnessSegment, PlacementHint,
        DRC_MIN_CLEARANCE_MM, DRC_WIRE_CURRENT_DENSITY_A_PER_MM2,
        DRC_MAX_BOARD_POWER_DENSITY_W_PER_CM2,
    )
    from gen.core.state import Netlist

    def comp(cid, p=0.0):
        return Component(id=cid, name=cid, kind="mcu", v_nom=12.0, i_max=1.0,
                         p_max_dissip=p, footprint_mm=(10, 10, 2))

    comps = [comp("U1"), comp("U2")]
    placements = [PlacementHint(ref_des="U1", pos_mm=(10.0, 10.0, 0.0)),
                  PlacementHint(ref_des="U2", pos_mm=(60.0, 60.0, 0.0))]
    nl = Netlist(pins=[], nets=[])

    # 1) the DEFAULT rules ARE the named sourced constants (the fix's point)
    clean = run_internal_drc(nl, placements, None, comps)
    assert clean["rules_applied"]["min_clearance_mm"] == DRC_MIN_CLEARANCE_MM
    assert clean["rules_applied"]["trace_a_per_mm2"] == DRC_WIRE_CURRENT_DENSITY_A_PER_MM2
    assert clean["rules_applied"]["max_power_density_w_cm2"] == DRC_MAX_BOARD_POWER_DENSITY_W_PER_CM2
    assert clean["status"] == "pass"                       # separated, no harness, cool

    # 2) an undersized harness gauge is FLAGGED (non-vacuous): 24A on 0.5mm^2 needs ~2mm^2
    bad_harness = HarnessSpec(
        segments=[HarnessSegment(from_ref="U1", to_ref="U2", gauge_mm2=0.5,
                                 length_mm=100.0, signals=["PWR"], current_a=24.0, voltage_v=12.0)],
        total_mass_est_g=10.0, emc_measures=[])
    drc = run_internal_drc(nl, placements, bad_harness, comps)
    assert any(v["type"] == "trace_width" for v in drc["violations"])

    # 3) board_dims really drives the density screen (no silently hard-coded 150x100):
    #    24W on a tiny 20x20mm board (=4cm^2 -> 6 W/cm^2) is flagged...
    hot = [comp("U1", p=12.0), comp("U2", p=12.0)]
    dense = run_internal_drc(nl, placements, None, hot, board_dims=(20.0, 20.0))
    assert any(v["type"] == "power_density" for v in dense["violations"])
    #    ...the SAME parts on the big default board (150cm^2 -> 0.16 W/cm^2) are not
    big = run_internal_drc(nl, placements, None, hot)
    assert not any(v["type"] == "power_density" for v in big["violations"])
