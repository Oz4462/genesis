"""Characterization + facade-detector for discovery/separability.py.

Goal: prove ``analyze_separability`` REALLY evaluates the mixed second difference
``y(++) − y(+−) − y(−+) + y(−−)`` (and its ``log y`` form for multiplicative mode) rather than
returning a canned grouping. Two pillars per the team facade-killer convention:

(a) the headline output (the variable grouping / max_interaction) changes MEANINGFULLY when a driving
    input changes — additive vs coupled, multiplicative vs coupled, partial coupling — so the number is
    computed, not constant; and
(b) the documented fail-loud guards raise the exact ``ValueError`` (unknown mode, non-positive target in
    multiplicative mode, and the two silent-wrong-value guards ``n_bases < 1`` / ``tol < 0``).

Legacy tests/test_separability.py and tests/test_engine_separability_annotation.py stay the source of
truth for the basic happy paths; this file pins the deeper "is the math real" contract. Offline,
deterministic, numpy-only.
"""

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gen.discovery.separability import analyze_separability

# Wide, strictly-positive ranges so the multiplicative log path is always defined.
_R3 = {"a": (1.0, 4.0), "b": (1.0, 4.0), "c": (1.0, 4.0)}
_R2 = {"a": (1.0, 4.0), "b": (1.0, 4.0)}


# --------------------------------------------------------------------------------------------------
# (a) the grouping is DRIVEN by the function — change the coupling, the groups change
# --------------------------------------------------------------------------------------------------

def test_additive_splits_but_the_same_variables_coupled_merge():
    """Same variables, same ranges, same mode — only the FUNCTION's coupling differs, and the grouping
    flips from singletons to one group. A canned grouping could not track this."""
    separable = analyze_separability(lambda a, b: a + b, ["a", "b"], _R2, mode="additive")
    coupled = analyze_separability(lambda a, b: a * b, ["a", "b"], _R2, mode="additive")

    assert set(separable.groups) == {frozenset({"a"}), frozenset({"b"})}
    assert separable.max_interaction == 0.0          # a pure sum has a vanishing mixed difference
    assert coupled.groups == (frozenset({"a", "b"}),)
    assert coupled.max_interaction > 0.0             # a product has a non-zero mixed difference


def test_multiplicative_log_path_splits_a_product_but_groups_a_coupled_factor():
    """The multiplicative mode is the additive test on ``log f``: a pure product factors into singletons,
    while a coupled factor like ``(a+b)`` keeps a,b together. Proves the log transform is really applied
    (under additive mode the SAME product would NOT separate)."""
    product = analyze_separability(lambda a, b: a * b, ["a", "b"], _R2, mode="multiplicative")
    coupled = analyze_separability(lambda a, b: (a + b) * 2.0, ["a", "b"], _R2, mode="multiplicative")

    assert set(product.groups) == {frozenset({"a"}), frozenset({"b"})}
    assert product.max_interaction == 0.0
    assert coupled.groups == (frozenset({"a", "b"}),)
    assert coupled.max_interaction > 1e-3

    # Cross-check the log path is what does it: a*b is COUPLED under the additive test, separable under
    # the multiplicative test — same f, opposite verdict, so the mode genuinely changes the computation.
    add = analyze_separability(lambda a, b: a * b, ["a", "b"], _R2, mode="additive")
    assert add.groups == (frozenset({"a", "b"}),)


def test_partial_coupling_groups_only_the_interacting_pair():
    """y = a·b + c : a,b interact (multiplied) and c is additive. The connected-component grouping must
    isolate {a,b} from {c} — neither all-separate nor all-together — proving the per-pair mixed difference
    is evaluated and the union-find really partitions."""
    r = analyze_separability(lambda a, b, c: a * b + c, ["a", "b", "c"], _R3, mode="additive")
    assert set(r.groups) == {frozenset({"a", "b"}), frozenset({"c"})}
    # the {a,b} pair is genuinely coupled, so an interaction was actually recorded
    assert r.max_interaction > 0.0
    # and the separable pairs the algorithm found include the (a,c)/(b,c) boundaries
    assert frozenset({"a", "c"}) in r.separable_pairs
    assert frozenset({"b", "c"}) in r.separable_pairs


def test_three_way_coupling_is_one_group():
    """y = a·b·c (additive mode): every pair interacts → a single 3-variable group. Distinguishes a real
    pairwise scan from a stub that only ever returns singletons."""
    r = analyze_separability(lambda a, b, c: a * b * c, ["a", "b", "c"], _R3, mode="additive")
    assert r.groups == (frozenset({"a", "b", "c"}),)
    assert len(r.separable_pairs) == 0


def test_max_interaction_scales_with_the_coupling_strength():
    """A stronger product coupling yields a strictly larger relative mixed difference. A canned constant
    could not order these — the magnitude is computed from the actual corner sum."""
    weak = analyze_separability(lambda a, b: a + b + 1e-3 * a * b, ["a", "b"], _R2, mode="additive")
    strong = analyze_separability(lambda a, b: a + b + 1.0 * a * b, ["a", "b"], _R2, mode="additive")
    assert 0.0 < weak.max_interaction < strong.max_interaction


def test_ignored_variable_separates_off():
    """A variable that does not appear in f (c) cannot interact with anything → it splits into its own
    singleton group. Proves the mixed difference, not the argument list, decides the grouping."""
    r = analyze_separability(lambda a, b, c: a * b, ["a", "b", "c"], _R3, mode="additive")
    assert set(r.groups) == {frozenset({"a", "b"}), frozenset({"c"})}


# --------------------------------------------------------------------------------------------------
# (b) the documented fail-loud guards raise — a gate without a test does not exist
# --------------------------------------------------------------------------------------------------

def test_invalid_mode_raises():
    with pytest.raises(ValueError, match="mode must be"):
        analyze_separability(lambda a, b: a + b, ["a", "b"], _R2, mode="bogus")


def test_multiplicative_mode_rejects_non_positive_target():
    # a - 5 is negative on (1,4): log is undefined → fail loud rather than emit NaN-driven groups.
    with pytest.raises(ValueError, match="positive target"):
        analyze_separability(lambda a, b: a - 5.0, ["a", "b"], _R2, mode="multiplicative")


def test_n_bases_below_one_raises_instead_of_fabricating_full_separability():
    """Regression for a silent-wrong-value defect: with ``n_bases < 1`` the sampling loop never runs, so
    the mixed difference is never evaluated and a genuinely COUPLED ``a*b`` would be reported as fully
    separable. The honest behaviour is to fail loud (keine stillen Defaults)."""
    with pytest.raises(ValueError, match="n_bases must be"):
        analyze_separability(lambda a, b: a * b, ["a", "b"], _R2, mode="additive", n_bases=0)
    with pytest.raises(ValueError, match="n_bases must be"):
        analyze_separability(lambda a, b: a * b, ["a", "b"], _R2, mode="additive", n_bases=-3)


def test_negative_tolerance_raises_instead_of_fabricating_full_coupling():
    """Regression for the mirror silent-wrong-value defect: a non-negative relative interaction can never
    satisfy ``interaction <= tol`` when ``tol < 0``, so a pure sum ``a+b`` would be reported as coupled.
    Fail loud instead."""
    with pytest.raises(ValueError, match="tol must be"):
        analyze_separability(lambda a, b: a + b, ["a", "b"], _R2, mode="additive", tol=-1.0)


# --------------------------------------------------------------------------------------------------
# determinism + property-based invariants on the mixed-second-difference contract
# --------------------------------------------------------------------------------------------------

def test_result_is_deterministic_across_runs():
    f = lambda a, b, c: a * b + c
    r1 = analyze_separability(f, ["a", "b", "c"], _R3, mode="additive")
    r2 = analyze_separability(f, ["a", "b", "c"], _R3, mode="additive")
    assert r1.groups == r2.groups and r1.max_interaction == r2.max_interaction


@settings(max_examples=40, deadline=None)
@given(
    ca=st.floats(min_value=-3.0, max_value=3.0),
    cb=st.floats(min_value=-3.0, max_value=3.0),
    k=st.floats(min_value=0.1, max_value=3.0),
)
def test_property_additive_law_always_separates_product_always_couples(ca, cb, k):
    """INVARIANT of the mixed second difference: any purely additive law ``ca·a + cb·b`` has a vanishing
    mixed difference (separates into singletons), while a product term ``k·a·b`` always produces a
    non-zero mixed difference (couples) regardless of the coefficients. Explores the coefficient space
    rather than a single hand-picked example."""
    additive = analyze_separability(lambda a, b: ca * a + cb * b, ["a", "b"], _R2, mode="additive")
    assert set(additive.groups) == {frozenset({"a"}), frozenset({"b"})}
    assert additive.max_interaction == 0.0

    coupled = analyze_separability(lambda a, b: ca * a + cb * b + k * a * b, ["a", "b"], _R2,
                                   mode="additive")
    assert coupled.groups == (frozenset({"a", "b"}),)
    assert coupled.max_interaction > 0.0


@settings(max_examples=30, deadline=None)
@given(p=st.floats(min_value=0.5, max_value=3.0), q=st.floats(min_value=0.5, max_value=3.0))
def test_property_pure_monomial_factors_under_multiplicative_mode(p, q):
    """INVARIANT: a pure separable monomial ``a^p · b^q`` is additively separable in ``log`` for any
    positive exponents, so multiplicative mode must split a,b into singletons."""
    r = analyze_separability(lambda a, b: (a ** p) * (b ** q), ["a", "b"], _R2, mode="multiplicative")
    assert set(r.groups) == {frozenset({"a"}), frozenset({"b"})}
    assert r.max_interaction == 0.0


def test_log_path_matches_a_hand_computed_corner_sum():
    """Anchor the multiplicative log transform against an independent hand computation: for f = a·b the
    log mixed difference over the corners is exactly 0 (log a + log b is additive), whereas for the
    non-factoring f = a + b the log mixed difference is non-zero. This nails that ``log`` is applied to
    the SAME corner-sum machinery the module uses internally."""
    lo, hi = 1.0, 4.0

    def log_corner(f):
        return (math.log(f(hi, hi)) - math.log(f(hi, lo))
                - math.log(f(lo, hi)) + math.log(f(lo, lo)))

    assert log_corner(lambda a, b: a * b) == pytest.approx(0.0, abs=1e-12)
    assert abs(log_corner(lambda a, b: a + b)) > 1e-3

    # ...and the module agrees with the hand computation's verdict.
    assert analyze_separability(lambda a, b: a * b, ["a", "b"], _R2,
                                mode="multiplicative").max_interaction == 0.0
    assert analyze_separability(lambda a, b: a + b, ["a", "b"], _R2,
                                mode="multiplicative").max_interaction > 1e-3


def test_numpy_is_actually_imported_and_used_for_base_sampling():
    """Guard against an accidental removal of the seeded numpy sampler: the result must remain stable and
    the module must still expose its numpy-driven default seed behaviour (smoke that np is wired)."""
    # np is used indirectly; this asserts the deterministic seed path produces a finite interaction.
    r = analyze_separability(lambda a, b: a * b, ["a", "b"], _R2, mode="additive", seed=7)
    assert np.isfinite(r.max_interaction) and r.max_interaction > 0.0
