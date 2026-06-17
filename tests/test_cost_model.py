"""Cost model — a sourced, ranged FDM cost estimate (Teil 2, Stein 4).

A cost is a MEASUREMENT with assumptions, not a single fabricated number. The
estimate must be a range derived from sourced material prices / densities /
print throughput / machine rates, expose its assumptions and honest gaps (exact
slicing time, supports, finishing, labour), grow with volume, resolve the
material from the spec hint, and fail loud on a degenerate volume. Offline.

Run:  pytest tests/test_cost_model.py
"""

from __future__ import annotations

import pytest

from gen.cad.cost_model import CostEstimate, estimate_fdm_cost


def test_fdm_cost_is_a_sourced_range_not_a_single_fabricated_number():
    """Tracer: the estimate is a RANGE with explicit assumptions + honest gaps and a
    source — never one fabricated number like the old '8-25 EUR' stub."""
    est = estimate_fdm_cost(50.0, material="PLA")
    assert isinstance(est, CostEstimate)
    assert 0 < est.low_eur < est.high_eur          # a real range, not one number
    assert est.assumptions and est.gaps            # explicit assumptions + honest gaps
    assert est.source
    # the breakdown carries the three modelled components
    assert {"material", "machine_time", "setup"} <= set(est.breakdown)


def test_fdm_cost_fails_loud_on_degenerate_volume():
    """A non-positive or non-finite volume yields no honest cost — refuse, never guess
    (a NaN/inf must not propagate into a NaN cost)."""
    for bad in [0.0, -5.0, float("nan"), float("inf")]:
        with pytest.raises(ValueError):
            estimate_fdm_cost(bad)


def test_fdm_cost_grows_with_volume_and_setup_is_a_band():
    """More material → more cost; setup is itself a band (0 self-run … nominal), so it
    widens the estimate rather than being a fixed offset."""
    small = estimate_fdm_cost(10.0, "PLA")
    big = estimate_fdm_cost(200.0, "PLA")
    assert big.low_eur > small.low_eur and big.high_eur > small.high_eur
    setup_low, setup_high = small.breakdown["setup"]
    assert setup_low == 0.0 and setup_high > 0.0            # setup adds uncertainty, not a fixed offset


def test_fdm_cost_resolves_material_from_hint_and_states_it():
    """The free-text spec hint resolves to a known material, and the chosen material
    is surfaced as an assumption (never silently decisive). Denser PETG → more mass."""
    from gen.cad.cost_model import resolve_fdm_material

    assert resolve_fdm_material("PLA oder PETG für erste Prints") == "PLA"   # first match
    assert resolve_fdm_material("nur PETG, bitte") == "PETG"
    assert resolve_fdm_material("unbekannt") == "PLA"                        # default
    est = estimate_fdm_cost(50.0, "PLA oder PETG für erste Prints")
    assert any("material PLA" in a for a in est.assumptions)                 # stated
    # PETG is denser than PLA -> a touch more material mass/cost at the high end
    assert estimate_fdm_cost(50.0, "PETG").high_eur >= estimate_fdm_cost(50.0, "PLA").high_eur


def test_fdm_cost_surfaces_its_honest_limits_as_gaps():
    """The model's real limitations are declared, not hidden: an unresolved material
    defaults but says so; the flat-infill multiplier's shell/near-solid blind spot
    and commercial-bureau pricing are explicit gaps (not folded into the band)."""
    est = estimate_fdm_cost(50.0, "carbon-fibre wonderstuff")
    assert any("did not resolve" in g for g in est.gaps)         # default flagged
    assert any("shell-dominated" in g or "near-solid" in g for g in est.gaps)
    assert any("commercial" in g.lower() for g in est.gaps)      # bureau pricing not folded in
