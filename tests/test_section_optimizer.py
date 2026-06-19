"""Tests for the minimum-material section optimizer (section_optimizer.py).

Pins: the proposed section is re-verified by the structural yield formula (proposer/gate split holds),
it is lighter than a naive square section meeting the same load, it respects the manufacturability
bounds, and invalid inputs are rejected. Offline, deterministic.
"""

import pytest

from gen.section_optimizer import optimize_cantilever_section
from gen.verification.smt import cantilever_stress

_F, _L, _SA = 100.0, 50.0, 600.0


def test_proposed_section_passes_the_structural_yield_gate():
    d = optimize_cantilever_section(force=_F, arm=_L, sigma_allow=_SA, min_wall=2.0, max_aspect=4.0)
    assert d.feasible and d.stress <= _SA
    # independent re-verification with the gate's own formula (the proposal is a candidate, not trusted)
    assert cantilever_stress(_F, _L, d.breadth, d.depth) <= _SA + 1e-6
    assert d.safety_factor >= 1.0


def test_optimized_section_is_lighter_than_a_naive_square():
    d = optimize_cantilever_section(force=_F, arm=_L, sigma_allow=_SA, min_wall=2.0, max_aspect=4.0)
    required_bh2 = 6.0 * _F * _L / _SA
    h_square = required_bh2 ** (1.0 / 3.0)          # square section b=h that just meets the stress limit
    square_volume = h_square * h_square * _L
    assert d.volume < square_volume                  # auto-sizing beats the hand-drawn square


def test_respects_manufacturability_bounds():
    d = optimize_cantilever_section(force=_F, arm=_L, sigma_allow=_SA, min_wall=2.0, max_aspect=4.0)
    assert d.breadth >= 2.0 - 1e-9 and d.depth >= 2.0 - 1e-9
    assert d.depth / d.breadth <= 4.0 + 1e-6


def test_invalid_inputs_rejected():
    with pytest.raises(ValueError):
        optimize_cantilever_section(force=0.0, arm=_L, sigma_allow=_SA)


def test_is_deterministic():
    a = optimize_cantilever_section(force=_F, arm=_L, sigma_allow=_SA)
    b = optimize_cantilever_section(force=_F, arm=_L, sigma_allow=_SA)
    assert (a.breadth, a.depth, a.volume) == (b.breadth, b.depth, b.volume)
