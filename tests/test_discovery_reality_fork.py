"""Reality Fork Simulator — counterfactual worlds, always labelled, internally checked (4.2)."""

import math

import numpy as np
import pytest

from gen.discovery import (
    fork_spatial_dimension, fork_constant, fork_from_discovery, gauss_force_exponent,
    discover_new_formulas, Variable, Constant, DiscoveryProblem,
)

MU_SUN = 1.32712440018e20


def test_gauss_law_reproduces_our_world_and_forks_dimensions():
    """3D reproduces the real inverse-square force; 4D and 2D are principled counterfactuals."""
    assert gauss_force_exponent(3) == -2          # our world
    assert gauss_force_exponent(4) == -3
    assert gauss_force_exponent(2) == -1
    real = fork_spatial_dimension(3)
    assert real.internally_consistent and real.counterfactual is False   # 3D IS the real world
    four = fork_spatial_dimension(4)
    assert four.counterfactual and four.internally_consistent
    assert four.change["force_exponent"] == -3
    assert any("Ehrenfest" in n for n in four.notes)                     # no stable orbits note


def test_inconsistent_dimension_is_flagged_not_explored():
    """A fractional or sub-1 dimension has no Gauss surface — flagged inconsistent, not faked."""
    for bad in (0, -1):
        w = fork_spatial_dimension(bad)
        assert not w.internally_consistent
    with pytest.raises(ValueError):
        gauss_force_exponent(0)


def test_constant_fork_scales_the_target_and_flags_nonpositive():
    """Doubling a constant whose target scales as c^(-1/2) scales the target by 2^(-1/2)."""
    w = fork_constant("T", "mu", base_value=1.0, new_value=2.0, scaling_exponent=-0.5)
    assert w.internally_consistent and w.counterfactual
    assert abs(w.change["target_scale_factor"] - 2.0 ** -0.5) < 1e-9
    bad = fork_constant("T", "mu", base_value=1.0, new_value=-2.0, scaling_exponent=-0.5)
    assert not bad.internally_consistent                                 # non-positive -> flagged


def test_fork_from_a_discovered_law_uses_its_own_exponent():
    """Forking a constant of a REAL discovered law reads the law's fitted exponent, so the
    counterfactual stays consistent with the relation — but never re-uses 'bestaetigt'."""
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11])
    T = 2.0 * math.pi * a ** 1.5 / math.sqrt(MU_SUN)
    verdict = discover_new_formulas(DiscoveryProblem(
        idea="Kepler", target=Variable("T", "s", tuple(T)),
        inputs=(Variable("a", "m", tuple(a)),),
        constants=(Constant("mu", MU_SUN, "m^3/s^2"),))).validated[0]
    world = fork_from_discovery(verdict, "mu", new_value=2 * MU_SUN, base_value=MU_SUN)
    assert world.counterfactual                                          # never claimed real
    assert abs(world.change["target_scale_factor"] - 2.0 ** -0.5) < 1e-6  # mu exponent is -1/2


def test_every_fork_is_marked_counterfactual_never_a_real_verdict():
    """Structural honesty: a fork carries a counterfactual flag and NO discovery verdict
    ('bestaetigt' lives only in the real-data gate, never in a sandbox world)."""
    w = fork_spatial_dimension(5)
    assert hasattr(w, "counterfactual") and w.counterfactual
    assert not hasattr(w, "verdict") and not hasattr(w, "passed")
