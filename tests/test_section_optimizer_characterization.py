"""Characterization / facade-detector for section_optimizer.py (T04 depth audit).

This file is the authoritative facade-detector. It proves three things the headline claim rests on,
without re-using the optimiser's own arithmetic as its oracle:

  1. CLOSED-FORM CROSS-CHECK — the proposed section's stress equals an INDEPENDENTLY recomputed
     ``σ = 6·F·L/(b·h²)`` and sits within the allowable. The optimiser is not graded by its own number.
  2. INPUT IS CONSUMED (not canned) — a larger allowable yields a strictly smaller volume, and a larger
     load yields a heavier section. A constant stub could not do this.
  3. PROPOSER/GATE SPLIT IS REAL — ``propose_and_verify``'s ``gate_passed`` is reproduced bit-for-bit by
     calling the SEPARATE ``cantilever_yield_check`` gate ourselves, and that same gate genuinely REJECTS
     a deliberately under-sized section (so it is a real check, not a rubber stamp).

Plus the mandatory NEGATIVE battery (every documented fail-loud path fires) and the honest-abstention
path made reachable by the ``max_wall`` build bound (an over-constrained load → ``feasible=False``).

Offline, deterministic; uses REAL material names from gen.materials. Property-based invariant via
Hypothesis. Per CLAUDE.md §1 (no fact without a check), §2 (verification is a gate) and §4 (abstention).
"""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gen.materials import MATERIALS, get_material
from gen.section_optimizer import (
    SectionDesign,
    VerifiedSection,
    optimize_cantilever_section,
    propose_and_verify,
)
from gen.verification.cegis import cantilever_yield_check

_F, _L, _SA = 120.0, 45.0, 600.0


def _closed_form_stress(force: float, arm: float, breadth: float, depth: float) -> float:
    """Independent reference implementation of the bending stress σ = 6·F·L/(b·h²)."""
    return 6.0 * force * arm / (breadth * depth * depth)


# --- 1. closed-form cross-check -----------------------------------------------------------------

def test_proposed_stress_matches_independent_closed_form_and_clears_allowable():
    d = optimize_cantilever_section(force=_F, arm=_L, sigma_allow=_SA, min_wall=2.0, max_aspect=4.0)
    assert d.feasible
    # the optimiser's reported stress is the genuine closed form, not a decorative number
    assert d.stress == pytest.approx(_closed_form_stress(_F, _L, d.breadth, d.depth), rel=1e-12)
    assert d.stress <= _SA + 1e-9
    # safety_factor is exactly sigma_allow / stress, and >= 1 for a section that meets the bound
    assert d.safety_factor == pytest.approx(_SA / d.stress, rel=1e-12)
    assert d.safety_factor >= 1.0


def test_design_respects_the_geometry_bounds_it_claims():
    d = optimize_cantilever_section(force=_F, arm=_L, sigma_allow=_SA, min_wall=2.0, max_aspect=4.0)
    assert d.breadth >= 2.0 - 1e-9
    assert d.depth >= 2.0 - 1e-9
    assert d.depth / d.breadth <= 4.0 + 1e-6
    # volume is genuinely b·h·L, not a placeholder
    assert d.volume == pytest.approx(d.breadth * d.depth * _L, rel=1e-12)


# --- 2. the driving inputs are actually consumed ------------------------------------------------

def test_larger_allowable_yields_strictly_smaller_volume():
    # A weaker stress limit needs less material — a canned constant could never react to this.
    lean = optimize_cantilever_section(force=_F, arm=_L, sigma_allow=_SA * 4.0)
    heavy = optimize_cantilever_section(force=_F, arm=_L, sigma_allow=_SA)
    assert lean.feasible and heavy.feasible
    assert lean.volume < heavy.volume


def test_larger_load_yields_a_heavier_section():
    light = optimize_cantilever_section(force=_F, arm=_L, sigma_allow=_SA)
    big = optimize_cantilever_section(force=_F * 5.0, arm=_L, sigma_allow=_SA)
    assert big.volume > light.volume


# --- 3. proposer/gate split is REAL -------------------------------------------------------------

def test_gate_passed_is_reproduced_by_the_independent_gate_for_every_material():
    # gate_passed must equal an INDEPENDENT call to cantilever_yield_check — proving the verdict comes
    # from the separate gate, not from the optimiser trusting its own feasible flag.
    for name in MATERIALS:
        vs = propose_and_verify(material_name=name, force=_F, arm=_L, safety_factor=2.0)
        assert isinstance(vs, VerifiedSection)
        independent = cantilever_yield_check(
            {"F": _F, "L": _L, "b": vs.design.breadth, "h": vs.design.depth}, vs.sigma_allow
        )
        assert vs.gate_passed == (independent is None), f"{name}: gate verdict disagrees — {vs.detail}"
        assert vs.gate_passed, f"{name}: proposal failed the independent gate — {vs.detail}"


def test_the_gate_actually_rejects_an_undersized_section():
    # Guard against a rubber-stamp gate: a deliberately too-thin section MUST be flagged. If this passed,
    # gate_passed in the test above would be meaningless.
    ce = cantilever_yield_check({"F": _F, "L": _L, "b": 1.0, "h": 1.0}, sigma_allow=1.0)
    assert ce is not None
    assert ce.quantity == "bending_stress"
    assert ce.value > ce.bound


def test_sigma_allow_is_grounded_in_the_material_yield_not_an_anonymous_constant():
    vs = propose_and_verify(material_name="petg", force=_F, arm=_L, safety_factor=2.0)
    material = get_material("PETG")
    assert vs.sigma_allow == pytest.approx(material.yield_strength_mpa / 2.0)
    assert vs.material.source  # the property carries provenance (no anonymous literal)
    assert _closed_form_stress(_F, _L, vs.design.breadth, vs.design.depth) <= vs.sigma_allow + 1e-6


def test_machine_proof_is_honest_about_z3_availability():
    vs = propose_and_verify(material_name="PLA", force=_F, arm=_L)
    assert vs.machine_proved or "z3 unavailable" in vs.detail
    if vs.machine_proved:
        assert vs.gate_passed  # a machine proof implies the closed-form gate passes


# --- 4. NEGATIVE battery: every documented fail-loud path fires ----------------------------------

@pytest.mark.parametrize(
    "kwargs",
    [
        {"force": 0.0, "arm": _L, "sigma_allow": _SA},
        {"force": -1.0, "arm": _L, "sigma_allow": _SA},
        {"force": _F, "arm": 0.0, "sigma_allow": _SA},
        {"force": _F, "arm": -1.0, "sigma_allow": _SA},
        {"force": _F, "arm": _L, "sigma_allow": 0.0},
        {"force": _F, "arm": _L, "sigma_allow": -1.0},
    ],
)
def test_optimize_rejects_nonpositive_inputs(kwargs):
    with pytest.raises(ValueError):
        optimize_cantilever_section(**kwargs)


def test_propose_rejects_nonpositive_safety_factor():
    with pytest.raises(ValueError):
        propose_and_verify(material_name="PLA", force=_F, arm=_L, safety_factor=0.0)
    with pytest.raises(ValueError):
        propose_and_verify(material_name="PLA", force=_F, arm=_L, safety_factor=-1.0)


def test_propose_rejects_unknown_material():
    with pytest.raises(ValueError):
        propose_and_verify(material_name="unobtanium", force=_F, arm=_L)


def test_propose_rejects_nonpositive_load_via_optimizer():
    with pytest.raises(ValueError):
        propose_and_verify(material_name="PLA", force=0.0, arm=_L)


# --- 5. honest abstention: an over-constrained load returns feasible=False -----------------------

def test_over_constrained_load_returns_honest_infeasible_not_a_fabricated_section():
    # With a finite build bound, a crushing load that cannot be met within [min_wall, max_wall] must
    # ABSTAIN rather than fabricate a section. This path is the whole point of the feasible flag.
    d = optimize_cantilever_section(
        force=1.0e6, arm=1000.0, sigma_allow=1.0, min_wall=1.0, max_wall=5.0, max_aspect=4.0,
    )
    assert d.feasible is False
    assert math.isinf(d.stress)


def test_propose_and_verify_reports_infeasible_without_certifying_anything():
    vs = propose_and_verify(
        material_name="PLA", force=1.0e6, arm=1000.0, max_wall=5.0,
    )
    assert vs.design.feasible is False
    assert vs.gate_passed is False
    assert vs.machine_proved is False
    assert "no section" in vs.detail


def test_finite_max_wall_does_not_change_an_already_buildable_design():
    # Regression: a generous max_wall must leave the unbounded optimum untouched (input consumed only
    # when it actually binds), so existing callers see identical geometry.
    unbounded = optimize_cantilever_section(force=_F, arm=_L, sigma_allow=_SA)
    bounded = optimize_cantilever_section(force=_F, arm=_L, sigma_allow=_SA, max_wall=1.0e6)
    assert (bounded.breadth, bounded.depth, bounded.volume) == (
        unbounded.breadth, unbounded.depth, unbounded.volume,
    )


# --- 6. determinism + property-based invariant --------------------------------------------------

def test_optimizer_is_deterministic():
    a = optimize_cantilever_section(force=_F, arm=_L, sigma_allow=_SA)
    b = optimize_cantilever_section(force=_F, arm=_L, sigma_allow=_SA)
    assert (a.breadth, a.depth, a.volume) == (b.breadth, b.depth, b.volume)


@settings(max_examples=60, deadline=None)
@given(
    force=st.floats(min_value=1.0, max_value=5.0e3),
    arm=st.floats(min_value=1.0, max_value=5.0e2),
    material_name=st.sampled_from(sorted(MATERIALS)),
    safety_factor=st.floats(min_value=1.0, max_value=4.0),
)
def test_invariant_every_proposal_clears_its_own_independent_gate(
    force, arm, material_name, safety_factor,
):
    # The core anti-hallucination property: for ANY valid load and grounded material, the optimiser's
    # proposal satisfies the closed-form bound AND the independent gate confirms it (unbounded => always
    # feasible). Proposer and gate never disagree.
    vs = propose_and_verify(
        material_name=material_name, force=force, arm=arm, safety_factor=safety_factor,
    )
    assert vs.design.feasible
    sigma = _closed_form_stress(force, arm, vs.design.breadth, vs.design.depth)
    assert sigma <= vs.sigma_allow + 1e-6
    assert vs.gate_passed
    assert isinstance(vs.design, SectionDesign)
