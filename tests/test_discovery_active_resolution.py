"""Active Resolution of Uncertainty — the active next move after an ``unentschieden`` verdict.

The decisive test is the FLIP: a narrow-range sample where a transcendental and a power-of-a-group
fit equally well (``unentschieden``); the operator proposes the bounded measurement that would break
the tie; feeding true data at that spec flips the verdict to ``bestaetigt`` — a data-driven
resolution with no human intuition. Plus the honest gate: when no bounded measurement discriminates,
the operator says so instead of inventing one.
"""

import numpy as np
import pytest

from gen.discovery import (
    Constant, DiscoveryProblem, Variable,
    DecisionSpec, discover_rivals, discover_transcendental, propose_resolution,
)

TAU, X0 = 5.0, 10.0


def _decay_problem(t: np.ndarray) -> DiscoveryProblem:
    """Exponential decay x = X0·exp(−t/τ) sampled at the given times."""
    return DiscoveryProblem(
        idea="Zerfall", target=Variable("x", "m", tuple(X0 * np.exp(-t / TAU))),
        inputs=(Variable("t", "s", tuple(t)),), constants=(Constant("tau", TAU, "s"),))


_T_NARROW = np.array([1.0, 1.5, 2.0, 2.5, 3.0])   # t/τ ∈ [0.2, 0.6]: exp ≈ a power law here


def test_narrow_range_is_genuinely_undecided():
    """On the narrow range a power-of-a-group fits the exponential as well as the exponential
    itself — both clear the bar, so the verdict is honestly ``unentschieden`` (the setup the
    operator exists to resolve)."""
    law = discover_transcendental(_decay_problem(_T_NARROW))
    assert law.verdict == "unentschieden"
    assert law.r_squared >= 0.999 and law.powerlaw_r2 >= 0.999


def test_proposes_a_discriminating_measurement():
    """propose_resolution finds a bounded region where the two rivals diverge far above the noise
    floor, and returns a spread of points in the UNOBSERVED region with differing signatures."""
    problem = _decay_problem(_T_NARROW)
    trans, powerlaw = discover_rivals(problem)
    assert trans is not None and powerlaw is not None
    spec = propose_resolution(trans, powerlaw, problem)
    assert isinstance(spec, DecisionSpec)
    assert spec.discriminating
    assert spec.discrimination_ratio > 5.0
    assert spec.variable == "t"
    assert len(spec.measure_at) >= 2
    # at least one suggested point lies outside the observed range (new data is actually needed)
    lo, hi = spec.observed_range
    assert any(p < lo or p > hi for p in spec.measure_at)
    # the rivals' expected signatures genuinely differ at the suggested points
    assert max(abs(a - b) for a, b in zip(spec.expected_a, spec.expected_b)) > 1e-3


def test_resolution_flips_the_undecided_verdict():
    """THE acceptance test: feed true data at the proposed spec and re-judge — ``unentschieden``
    becomes ``bestaetigt`` for the real (exponential) form, and the power-of-a-group rival drops
    below the bar. The tie is broken by the proposed measurement, deterministically."""
    problem = _decay_problem(_T_NARROW)
    assert discover_transcendental(problem).verdict == "unentschieden"

    trans, powerlaw = discover_rivals(problem)
    spec = propose_resolution(trans, powerlaw, problem)
    assert spec.discriminating

    augmented_t = np.sort(np.concatenate([_T_NARROW, np.array(spec.measure_at)]))
    resolved = discover_transcendental(_decay_problem(augmented_t))
    assert resolved.verdict == "bestaetigt"
    assert resolved.form_name == "exp"
    assert resolved.powerlaw_r2 < 0.999          # the rival now clearly loses


def test_bounded_extrapolation_gate_blocks_artefacts():
    """The honest failure mode is extrapolation: with only a tiny look-past-the-data budget the
    rivals barely diverge, so the operator reports ``discriminating = False`` ("no power in the
    allowed regime") instead of inventing a meaningless far-extrapolation experiment."""
    problem = _decay_problem(_T_NARROW)
    trans, powerlaw = discover_rivals(problem)
    spec = propose_resolution(trans, powerlaw, problem, max_extrapolation=1.02)
    assert not spec.discriminating
    assert spec.discrimination_ratio < 5.0
    assert "Unterscheidungskraft" in spec.reason or "discrimin" in spec.reason.lower()


def test_rejects_multiple_varying_inputs():
    """MVP scope is a single varying input — more than one is an explicit ValueError, not a
    silently-wrong proposal."""
    problem = DiscoveryProblem(
        idea="multi", target=Variable("x", "m", (10.0, 20.0, 30.0, 40.0)),
        inputs=(Variable("t", "s", (1.0, 2.0, 3.0, 4.0)), Variable("u", "s", (1.0, 2.0, 3.0, 4.0))),
        constants=(Constant("tau", 5.0, "s"),))
    trans, powerlaw = discover_rivals(problem)
    a = trans or powerlaw
    if a is not None:
        with pytest.raises(ValueError):
            propose_resolution(a, a, problem)


def test_rejects_extrapolation_factor_below_one():
    """A max_extrapolation < 1 would search INSIDE the data only — meaningless; hard ValueError."""
    problem = _decay_problem(_T_NARROW)
    trans, powerlaw = discover_rivals(problem)
    with pytest.raises(ValueError):
        propose_resolution(trans, powerlaw, problem, max_extrapolation=0.5)


def test_rejects_a_none_rival():
    """A None rival (discover_rivals found no dimensionless argument) is a clear ValueError, not an
    AttributeError deep in evaluation — there is nothing to resolve."""
    problem = _decay_problem(_T_NARROW)
    trans, _ = discover_rivals(problem)
    with pytest.raises(ValueError):
        propose_resolution(trans, None, problem)
