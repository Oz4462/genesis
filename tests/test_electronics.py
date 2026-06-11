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
    assert "Bill of materials (mechanical):" in out
    assert "Bill of materials (electronics):" in out
    # the Pi appears under electronics, the screw under mechanical
    mech_idx = out.index("(mechanical)")
    elec_idx = out.index("(electronics)")
    assert out.index("M4 screw") < elec_idx
    assert out.index("Raspberry Pi 4") > elec_idx
    assert mech_idx < elec_idx
