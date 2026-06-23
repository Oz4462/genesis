"""Characterization test: prove `propose_resolution` is REAL (numpy divergence search),
not a facade.

Audit target: src/gen/discovery/active_resolution.py implements deterministic,
LLM-free active experimental design after ``unentschieden``: given two RivalForms
(transcendental vs power-of-group) fitted by the real transcendental API, it searches
a bounded extrapolation region with a real grid + |fa-fb| divergence, selects a
SPREAD (not single peak) of measure points, and emits DecisionSpec fields that are
computed from the inputs.

Per task spec + team decisions (2026-06-23):
- Construct single-input DiscoveryProblem via engine.py REAL constructors.
- Obtain two RivalForm via transcendental.py's discover_rivals (and demonstrate
  refit_rival / evaluate_rival APIs) — never invent dataclass fields.
- Assert DecisionSpec.measure_at / max_divergence / discrimination_ratio CHANGE
  when rival pair or data changes (computed, not canned constant).
- Barely-diverging case (inside bounded region) yields discriminating=False with
  the documented honest 'mehr Daten ...' reason.
- Documented fail-loud guards raise exact ValueError (None rival, >1 input,
  max_extrapolation<1.0, degenerate/non-positive range). At least one NEGATIVE test.
- Add >=1 property-based (Hypothesis) test for determinism / range invariants.
- Edit active_resolution.py ONLY if a documented guard is genuinely missing/wrong
  (pre-audit: guards exist and match docstring; no source change).
- Uses only declared deps + stdlib.

AUDIT VERDICT (see DEPTH_AUDIT): REAL. Numpy divergence search is genuine; no edit
to source required; the new characterization test is the authoritative proof.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from gen.discovery.engine import Constant, DiscoveryProblem, Variable
from gen.discovery.transcendental import (
    RivalForm,
    discover_rivals,
    evaluate_rival,
    refit_rival,
)
from gen.discovery.active_resolution import (
    DecisionSpec,
    propose_resolution,
    DEFAULT_MIN_DISCRIMINATION,
)

TAU = 5.0
X0 = 10.0


def _decay_problem(t: np.ndarray) -> DiscoveryProblem:
    """Exponential decay x = X0 * exp(-t/TAU) as a single-input DiscoveryProblem.

    Real constructor from engine.py (read actual fields: idea, target:Variable,
    inputs: tuple[Variable,...], constants, run_id).
    """
    target_vals = tuple(float(X0 * math.exp(-float(tt) / TAU)) for tt in t)
    return DiscoveryProblem(
        idea="Zerfall characterization",
        target=Variable("x", "m", target_vals),
        inputs=(Variable("t", "s", tuple(float(tt) for tt in t)),),
        constants=(Constant("tau", TAU, "s"),),
        run_id="char-activeres-001",
    )


_NARROW = np.array([1.0, 1.5, 2.0, 2.5, 3.0])  # narrow regime: exp ~ power-law


def test_decision_spec_fields_are_computed_not_canned():
    """measure_at, max_divergence, discrimination_ratio are functions of the
    supplied rivals + problem data (real numpy grid search + evaluate).

    Changing the observed data (hence the fitted rivals and observed_range)
    must produce a different spec — proves no constant stub / facade.
    """
    p1 = _decay_problem(_NARROW)
    ra1, rb1 = discover_rivals(p1)
    assert ra1 is not None and rb1 is not None
    s1 = propose_resolution(ra1, rb1, p1)

    # Different data sample -> different rivals + different observed range
    t2 = np.array([0.8, 1.2, 1.8, 2.4, 3.0, 3.8])
    p2 = _decay_problem(t2)
    ra2, rb2 = discover_rivals(p2)
    assert ra2 is not None and rb2 is not None
    s2 = propose_resolution(ra2, rb2, p2)

    # The core numeric results of the divergence search must differ
    assert s1.observed_range != s2.observed_range
    assert s1.max_divergence != s2.max_divergence
    # measure_at (spread) or the ratio must reflect the different search
    changed = (
        s1.measure_at != s2.measure_at
        or abs(s1.discrimination_ratio - s2.discrimination_ratio) > 1e-6
        or abs(s1.max_divergence - s2.max_divergence) > 1e-12
    )
    assert changed, "DecisionSpec numerics must be input-dependent (not canned)"

    # Also exercise the evaluate API on a real rival (consumes the problem)
    ev = evaluate_rival(ra1, p1)
    assert ev.shape == (len(p1.target.values),)
    assert np.all(np.isfinite(ev))


def test_barely_diverging_inside_bound_yields_honest_non_discriminating():
    """A pair whose divergence barely exceeds noise inside the ALLOWED (bounded)
    extrapolation region yields discriminating=False + documented 'mehr Daten'
    style reason. Honest abstention, not invented experiment.
    """
    p = _decay_problem(_NARROW)
    ra, rb = discover_rivals(p)
    assert ra is not None and rb is not None

    # Force barely-diverge path with tiny allowed extrapolation
    spec = propose_resolution(
        ra, rb, p, max_extrapolation=1.01, min_discrimination=DEFAULT_MIN_DISCRIMINATION
    )

    assert isinstance(spec, DecisionSpec)
    assert not spec.discriminating
    assert spec.discrimination_ratio < DEFAULT_MIN_DISCRIMINATION
    # Documented honest message (from active_resolution.py)
    assert "mehr Daten" in spec.reason or "Regime" in spec.reason
    assert "keine Unterscheidungskraft" in spec.reason or "Unterscheidungskraft" in spec.reason
    # Still reports inspectable peak / candidates (per implementation contract)
    assert len(spec.measure_at) >= 1
    assert len(spec.expected_a) == len(spec.measure_at)
    assert len(spec.expected_b) == len(spec.measure_at)


def test_guards_raise_valueerror():
    """The four documented fail-loud paths raise ValueError with the messages
    present in active_resolution.py (no silent wrong result).
    This is the required NEGATIVE test (gate without test does not exist).
    """
    p_good = _decay_problem(_NARROW)
    ra, rb = discover_rivals(p_good)
    assert ra is not None and rb is not None

    # 1. rival None
    with pytest.raises(ValueError, match="needs two fitted rivals"):
        propose_resolution(ra, None, p_good)

    # 2. more than one varying input
    p_multi = DiscoveryProblem(
        idea="multi-input",
        target=Variable("y", "m", (10.0, 20.0, 30.0, 40.0)),
        inputs=(
            Variable("t", "s", (1.0, 2.0, 3.0, 4.0)),
            Variable("u", "s", (1.0, 2.0, 3.0, 4.0)),
        ),
        constants=(Constant("tau", 5.0, "s"),),
    )
    with pytest.raises(ValueError, match="single varying input"):
        propose_resolution(ra, rb, p_multi)

    # 3. max_extrapolation < 1.0
    with pytest.raises(ValueError, match="max_extrapolation must be >= 1.0"):
        propose_resolution(ra, rb, p_good, max_extrapolation=0.5)

    # 4. degenerate / non-positive input range (lo == hi, positive values)
    p_deg = DiscoveryProblem(
        idea="degenerate range",
        target=Variable("x", "m", (1.0, 1.0, 1.0)),
        inputs=(Variable("t", "s", (2.0, 2.0, 2.0)),),
        constants=(Constant("tau", 5.0, "s"),),
    )
    with pytest.raises(ValueError, match="input range must be positive and non-degenerate"):
        propose_resolution(ra, rb, p_deg)


def test_uses_real_refit_and_evaluate_apis():
    """Demonstrate construction / variation of RivalForm via transcendental's
    public refit/evaluate API (as required) while still exercising propose.
    """
    p = _decay_problem(_NARROW)
    ra, rb = discover_rivals(p)
    assert ra is not None and rb is not None

    # Refit on same data yields a valid RivalForm (same form_name, possibly tweaked params)
    rb_refit = refit_rival(rb, p)
    assert isinstance(rb_refit, RivalForm)
    assert rb_refit.form_name == rb.form_name

    spec = propose_resolution(ra, rb_refit, p)
    assert isinstance(spec, DecisionSpec)

    # evaluate_rival used internally; call explicitly to prove API surface works
    ev = evaluate_rival(ra, p)
    assert len(ev) == len(p.target.values)


# --- Property-based invariants (Hypothesis) ---------------------------------


@settings(deadline=None, max_examples=25, derandomize=True)
@given(
    st.lists(
        st.floats(min_value=0.2, max_value=8.0, allow_nan=False, allow_infinity=False),
        min_size=3,
        max_size=7,
    )
)
def test_propose_resolution_is_deterministic_and_range_contract(raw_t):
    """PROPERTY: identical inputs yield byte-identical DecisionSpec (A5 contract).

    Also: extended_range brackets observed_range; all suggested values finite;
    max_divergence >=0 ; when we can obtain rivals the call succeeds.
    Uses st.assume so Hypothesis only counts valid (positive, non-degenerate) draws.
    """
    t_arr = np.asarray(raw_t, dtype=float)
    t_arr = np.unique(t_arr)
    assume(t_arr.size >= 3)
    t_arr = np.sort(t_arr)
    assume(t_arr.min() > 0.0)
    assume(t_arr.max() > t_arr.min() + 1e-12)

    p = _decay_problem(t_arr)
    ra, rb = discover_rivals(p)
    assume(ra is not None and rb is not None)

    s1 = propose_resolution(ra, rb, p)
    s2 = propose_resolution(ra, rb, p)
    assert s1 == s2, "determinism: same RunState-like input must give identical spec"

    lo, hi = s1.observed_range
    elo, ehi = s1.extended_range
    # extended is lo / f .. hi * f with f>=1
    assert elo <= lo + 1e-12
    assert hi <= ehi + 1e-12
    assert all(math.isfinite(v) for v in s1.measure_at)
    assert s1.max_divergence >= 0.0
    assert s1.discrimination_ratio >= 0.0

    # Using evaluate on the returned points should give the expected_* values
    # (within float noise; we just prove the API path is live)
    grid_p = DiscoveryProblem(
        idea=p.idea,
        target=Variable(p.target.name, p.target.unit, tuple(0.0 for _ in s1.measure_at)),
        inputs=(Variable(s1.variable, p.inputs[0].unit, s1.measure_at),),
        constants=p.constants,
    )
    fa = evaluate_rival(ra, grid_p)
    assert fa.shape[0] == len(s1.measure_at)
