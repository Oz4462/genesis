"""Capstone (Phase γ-depth §6): a real idea -> a COMPLETE specification, through
all gates α/β/γ/δ, with mechanics + electronics + sourcing + assembly + site.

The end-to-end proof of the durable sourced-or-gap invariant: every factual detail
(load, screw, drill, prices, voltages, currents, supplier, part number) is a
VERIFIED claim or a declared/recomputed quantity — nothing invented. The spec is
the same one the CLI capstone demo renders (gen.demo), so what is demonstrated is
exactly what is verified. Real data comes from live α-research later, no code change.

Run:  pytest tests/test_capstone.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.state import ClaimStatus  # noqa: E402
from gen.demo import capstone_claims, capstone_spec, capstone_state  # noqa: E402
from gen.verification.gates import gate_delta, gate_gamma  # noqa: E402
from gen.verification.geometry import mass_of, volume_of  # noqa: E402


# --- α: every referenced claim is VERIFIED ------------------------------------

def test_alpha_all_claims_verified():
    assert all(c.status is ClaimStatus.VERIFIED and c.confidence >= 0.7 for c in capstone_claims())


# --- β: the spec is anchored in a grounded approach ---------------------------

def test_beta_anchored():
    st = capstone_state()
    anchor = next(a for a in st.approaches if a.id == st.specification.approach_id)
    assert anchor.grounding == ["c_anchor"]


# --- γ: the complete spec passes GATE γ ---------------------------------------

def test_gamma_complete_spec_passes():
    result = gate_gamma(capstone_state())
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]


# --- δ: geometry sound, fits the site, volume & mass exact --------------------

def test_delta_geometry_and_site_and_properties():
    st = capstone_state()
    result = gate_delta(st)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]

    bracket = st.specification.components[0]
    quantities = {q.id: q for q in st.specification.quantities}
    vol = volume_of(bracket.geometry, quantities)
    assert vol.exact and vol.value > 0
    m = mass_of(bracket, quantities)
    assert m.value is not None and m.exact and m.value > 0   # ~35.6 g


# --- end-to-end: the rendered spec contains every depth section ---------------

def test_rendered_spec_has_all_depth_sections():
    from gen.cli import format_specification
    out = format_specification(capstone_spec())
    assert "Bill of materials (mechanical):" in out
    assert "Bill of materials (electronics):" in out and "12 V LED strip" in out
    assert "McMaster-Carr #91290A115" in out and "0.42 EUR/pc" in out
    assert "tool:  4 mm hex key" in out and "torque: 2.5 N*m" in out
    assert "Site & environment" in out and "available space: 200 mm x 200 mm x 200 mm" in out
    assert "volume:" in out and "mass:" in out
    assert "no provably broken geometry" in out
    # cost roll-up: honest partial (only the screw is priced)
    assert "Estimated cost: 0.84 EUR (partial" in out


# --- the invariant: drop one claim -> the dependent detail fails ---------------

def test_removing_a_claim_breaks_the_dependent_detail():
    st = capstone_state()
    st.claims = [c for c in st.claims if c.id != "c_price"]   # remove the price claim
    assert {f.code for f in gate_gamma(st).failures}          # no invented price survives
