"""Depth-audit characterization tests for reality_fork (Reality Fork Simulator, build 4.2).

These tests are the authoritative facade-detector for ``src/gen/discovery/reality_fork.py``.
They prove the headline claim REALLY holds:

  (a) the spatial-dimension and constant forks COMPUTE their laws from Gauss's law / power-law
      scaling — the output changes meaningfully when a driving input changes, so the strings are
      derived, never canned; and
  (b) the honesty invariants hold — base D=3 → ``counterfactual=False``, every other fork
      ``counterfactual=True``, and NO fork carries the real-data gate's ``bestaetigt`` authority;
      and the documented fail-loud / abstention guards fire (non-integer dimension raises,
      non-positive / non-finite magnitude is flagged inconsistent rather than silently explored).

The pre-existing tests/test_discovery_reality_fork.py covers the canonical happy path; this file
deliberately attacks the "is it real?" question and adds property-based invariants.
"""

import math

import pytest
from hypothesis import given, strategies as st

from gen.discovery import (
    CounterfactualWorld,
    fork_spatial_dimension,
    fork_constant,
    gauss_force_exponent,
)


# --------------------------------------------------------------------------------------------
# (a) NOT CANNED: the law is computed from the input, so varying the input varies the output.
# --------------------------------------------------------------------------------------------

def test_force_law_is_computed_from_dimension_not_a_constant_string():
    """Different spatial dimensions must yield different force exponents AND different law
    strings via Gauss's law ``F ∝ r^(-(D-1))`` — a canned facade would return one fixed law."""
    worlds = {d: fork_spatial_dimension(d) for d in (2, 3, 4, 5, 6)}
    exponents = {d: w.change["force_exponent"] for d, w in worlds.items()}
    # Each exponent equals the closed-form Gauss value -(D-1); all five are distinct.
    assert exponents == {2: -1, 3: -2, 4: -3, 5: -4, 6: -5}
    assert len(set(exponents.values())) == 5
    # The forked_law string actually carries the computed exponent, not a fixed template.
    for d, w in worlds.items():
        assert f"r^{-(d - 1)}" in w.forked_law
    # Sanity: the five law strings are genuinely different from one another.
    assert len({w.forked_law for w in worlds.values()}) == 5


def test_force_law_tracks_the_quantity_label():
    """The quantity symbol is threaded into the law string — proof it is built, not hardcoded."""
    assert fork_spatial_dimension(4, quantity="E").forked_law.startswith("E ∝")
    assert fork_spatial_dimension(4, quantity="F").forked_law.startswith("F ∝")


def test_constant_fork_scale_factor_is_computed_from_the_inputs():
    """The target scale factor must equal ``(new/base)^exponent`` exactly and change as the
    inputs change — a canned value would not move with base_value / new_value / exponent."""
    base = fork_constant("T", "mu", base_value=1.0, new_value=2.0, scaling_exponent=-0.5)
    assert math.isclose(base.change["target_scale_factor"], 2.0 ** -0.5, rel_tol=1e-12)

    # Change the new value → factor must change accordingly.
    bigger = fork_constant("T", "mu", base_value=1.0, new_value=4.0, scaling_exponent=-0.5)
    assert math.isclose(bigger.change["target_scale_factor"], 4.0 ** -0.5, rel_tol=1e-12)
    assert bigger.change["target_scale_factor"] != base.change["target_scale_factor"]

    # Flip the exponent sign → factor inverts.
    inverted = fork_constant("T", "mu", base_value=1.0, new_value=2.0, scaling_exponent=0.5)
    assert math.isclose(
        inverted.change["target_scale_factor"] * base.change["target_scale_factor"], 1.0,
        rel_tol=1e-12,
    )
    # The law string carries the computed factor, not a placeholder.
    assert f"{base.change['target_scale_factor']:.6g}" in base.forked_law


# --------------------------------------------------------------------------------------------
# (b) HONESTY INVARIANTS: counterfactual labelling and the no-'bestaetigt' guarantee.
# --------------------------------------------------------------------------------------------

def test_only_base_dimension_three_is_marked_non_counterfactual():
    """The single base case D=3 reproduces our world (``counterfactual=False``); every other
    spatial fork is a genuine counterfactual."""
    real = fork_spatial_dimension(3)
    assert real.counterfactual is False
    assert real.internally_consistent
    for d in (1, 2, 4, 5, 7):
        w = fork_spatial_dimension(d)
        assert w.counterfactual is True, f"D={d} must be a counterfactual"


def test_custom_base_dimension_relabels_the_real_world():
    """The base/real label tracks ``base_dimension`` — fork D=4 against base 4 is the 'real'
    one there, and the base-self-check warns if the base does not give the real r^-2."""
    w = fork_spatial_dimension(4, base_dimension=4)
    assert w.counterfactual is False  # equal to its own base → not a what-if
    # A base dimension that does NOT reproduce r^-2 trips the documented self-check warning.
    warned = fork_spatial_dimension(5, base_dimension=4)
    assert any("does not give the real r^-2" in n for n in warned.notes)


def test_no_fork_ever_carries_a_real_data_verdict():
    """Structural honesty: a CounterfactualWorld has no 'verdict'/'passed'/'bestaetigt' field,
    and the string 'bestaetigt' never leaks into any of its textual content. The real-data
    gate's authority must never be borrowed by a sandbox world."""
    samples = [
        fork_spatial_dimension(3),
        fork_spatial_dimension(4),
        fork_spatial_dimension(0),  # inconsistent fork still must not claim 'bestaetigt'
        fork_constant("T", "mu", 1.0, 2.0, -0.5),
        fork_constant("T", "mu", 1.0, -2.0, -0.5),  # inconsistent
    ]
    for w in samples:
        assert not hasattr(w, "verdict")
        assert not hasattr(w, "passed")
        assert not hasattr(w, "bestaetigt")
        haystack = " ".join((w.name, w.kind, w.forked_law, *w.notes)).lower()
        assert "bestaetigt" not in haystack and "bestätigt" not in haystack


# --------------------------------------------------------------------------------------------
# Fail-loud / honest-abstention guards (negative tests — "a gate without a test does not exist").
# --------------------------------------------------------------------------------------------

def test_non_integer_or_subunit_dimension_raises():
    """No Gauss surface exists for a fractional or sub-1 dimension → loud ValueError."""
    with pytest.raises(ValueError):
        gauss_force_exponent(0)
    with pytest.raises(ValueError):
        gauss_force_exponent(-3)
    with pytest.raises(ValueError):
        gauss_force_exponent(2.5)  # type: ignore[arg-type]


def test_inconsistent_dimension_is_flagged_not_faked():
    """A sub-1 dimension fork is returned flagged inconsistent (honest abstention), never a
    fabricated law."""
    for bad in (0, -1):
        w = fork_spatial_dimension(bad)
        assert w.internally_consistent is False
        assert w.forked_law == "(nicht wohlgeformt)"


def test_nonpositive_constant_is_flagged_inconsistent():
    """A non-positive forked constant cannot be a power-law magnitude → flagged, not explored."""
    for base, new in ((1.0, -2.0), (-1.0, 2.0), (1.0, 0.0), (0.0, 2.0)):
        w = fork_constant("T", "mu", base_value=base, new_value=new, scaling_exponent=-0.5)
        assert w.internally_consistent is False
        assert "target_scale_factor" not in w.change  # never emits a bogus factor


def test_nonfinite_constant_is_flagged_inconsistent():
    """REGRESSION: NaN/inf magnitudes slip past a plain ``<= 0.0`` check (NaN comparisons are
    False), so without an explicit finiteness guard the fork would stamp a non-finite scale
    factor ``internally_consistent=True`` — a silent non-finite 'fact'. The honest behaviour
    is to flag it inconsistent and emit no scale factor."""
    for base, new, exp in (
        (float("nan"), 2.0, 1.0),
        (1.0, float("inf"), 1.0),
        (1.0, 2.0, float("nan")),
        (1.0, 2.0, float("inf")),
    ):
        w = fork_constant("T", "mu", base_value=base, new_value=new, scaling_exponent=exp)
        assert w.internally_consistent is False
        assert "target_scale_factor" not in w.change


# --------------------------------------------------------------------------------------------
# Property-based invariants (math identities that must hold for ALL valid inputs).
# --------------------------------------------------------------------------------------------

@given(st.integers(min_value=1, max_value=200))
def test_gauss_exponent_is_exactly_minus_d_minus_one(dimension):
    """Invariant: the Gauss-law force exponent is ``-(D-1)`` for every integer D ≥ 1, and the
    spatial fork records exactly that value and labels D=3 as the (only) real world."""
    assert gauss_force_exponent(dimension) == -(dimension - 1)
    w = fork_spatial_dimension(dimension)
    assert w.internally_consistent is True
    assert w.change["force_exponent"] == -(dimension - 1)
    assert w.counterfactual is (dimension != 3)


@given(
    st.floats(min_value=1e-6, max_value=1e6),
    st.floats(min_value=1e-6, max_value=1e6),
    st.floats(min_value=-3.0, max_value=3.0),
)
def test_constant_fork_factor_matches_power_law_and_is_finite(base_value, new_value, exponent):
    """Invariant: for positive finite magnitudes the scale factor equals ``(new/base)^exp``
    exactly, is always finite, and the world is consistent + counterfactual."""
    w = fork_constant("T", "mu", base_value=base_value, new_value=new_value,
                      scaling_exponent=exponent)
    assert w.internally_consistent is True
    factor = w.change["target_scale_factor"]
    assert math.isfinite(factor)
    assert math.isclose(factor, (new_value / base_value) ** exponent, rel_tol=1e-9)
    assert w.counterfactual is True  # a constant fork is never the real-data verdict


@given(
    st.floats(min_value=1e-3, max_value=1e3),
    st.floats(min_value=1e-3, max_value=1e3),
    st.floats(min_value=-2.0, max_value=2.0).filter(lambda e: abs(e) > 1e-3),
)
def test_constant_fork_exponent_sign_round_trip(base_value, new_value, exponent):
    """Invariant: forking with +exp and −exp gives reciprocal scale factors (a power-law
    identity), proving the factor is genuinely computed from the exponent."""
    up = fork_constant("T", "mu", base_value, new_value, exponent).change["target_scale_factor"]
    down = fork_constant("T", "mu", base_value, new_value, -exponent).change["target_scale_factor"]
    assert math.isclose(up * down, 1.0, rel_tol=1e-6)


def test_counterfactualworld_is_importable_and_frozen():
    """The public dataclass is exported and immutable (honesty labels cannot be mutated away)."""
    w = fork_spatial_dimension(4)
    assert isinstance(w, CounterfactualWorld)
    with pytest.raises(Exception):  # frozen dataclass → FrozenInstanceError
        w.counterfactual = False  # type: ignore[misc]
