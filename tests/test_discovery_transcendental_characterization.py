"""Characterization + depth audit of ``discovery.transcendental`` (T02).

This file is the FACADE DETECTOR for transcendental discovery over dimensionless π-groups.
The pre-existing ``test_discovery_transcendental.py`` pins recovery of specific cases; this file
proves the *headline honesty contract* genuinely holds on constructed data:

  * a true transcendental of a π-group is only ``bestaetigt`` when it is essentially exact (R²≥bar)
    AND the power-of-the-group rival is NOT — the power law does not explain the data equally well.
  * when the target IS a power/quadratic of the same π-group, both clear the bar and the verdict is
    the honest ``unentschieden`` (never a transcendental over-claim).
  * when inputs admit no dimensionless group at all, the verdict is ``widerlegt``.
  * the rival API (discover_rivals / evaluate_rival / refit_rival) is exercised and input-driven.
  * every documented fail-loud guard (non-positive magnitudes) raises with the exact message.

All inputs are built via the real engine constructors (DiscoveryProblem/Variable/Constant).
Property-based tests (Hypothesis) assert the scaling and recovery invariants that must hold for
arbitrary positive parameters of an exact transcendental generator.
"""

import math

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from gen.discovery import (
    Constant, DiscoveryProblem, Variable,
    TranscendentalLaw, discover_transcendental, dimensionless_groups,
    discover_rivals, evaluate_rival, refit_rival, RivalForm,
)
# NOTE: refit_rival now exercised via public package surface (gen.discovery) per facade-killer
# and review finding (was direct submodule import, which hid the __init__ lazy export)


# --------------------------------------------------------------------------------------------
# builders — exact laws via real engine constructors (positive magnitudes only)
# --------------------------------------------------------------------------------------------

def _exp_decay_trans(c: float = 10.0, alpha: float = -1.0, n: int = 10) -> DiscoveryProblem:
    """Genuine transcendental: y = C * exp(α * (t/τ)) with α<0, exact fit, power law cannot match."""
    t = np.linspace(1.0, 10.0, n)
    tau = 5.0
    y = c * np.exp(alpha * (t / tau))
    return DiscoveryProblem(
        idea="Zerfall transzendental",
        target=Variable("y", "m", tuple(y)),
        inputs=(Variable("t", "s", tuple(t)),),
        constants=(Constant("tau", tau, "s"),),
    )


def _sine_trans() -> DiscoveryProblem:
    """Oscillation y = 3*sin(2*(t/τ)) + 5 — non-monotonic, power law cannot fit."""
    t = np.linspace(0.1, 3.0, 16)
    tau = 1.0
    y = 3.0 * np.sin(2.0 * (t / tau)) + 5.0
    return DiscoveryProblem(
        idea="Schwingung transzendental",
        target=Variable("y", "m", tuple(y)),
        inputs=(Variable("t", "s", tuple(t)),),
        constants=(Constant("tau", tau, "s"),),
    )


def _quadratic_power_of_group() -> DiscoveryProblem:
    """Target IS a power law of the group: y = 7*(t/τ)². Transcendental can approx but power clears
    the bar exactly → honest unentschieden."""
    t = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    tau = 2.0
    y = 7.0 * (t / tau) ** 2
    return DiscoveryProblem(
        idea="Potenz des Gruppen-Arguments",
        target=Variable("y", "m", tuple(y)),
        inputs=(Variable("t", "s", tuple(t)),),
        constants=(Constant("tau", tau, "s"),),
    )


def _kepler_no_dimless() -> DiscoveryProblem:
    """Pure power law (Kepler) with NO dimensionless π-group among sources → widerlegt."""
    MU = 1.32712440018e20
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11, 1.434e12])
    T = 2.0 * math.pi * a**1.5 / math.sqrt(MU)
    return DiscoveryProblem(
        idea="Kepler (kein dim-loses Argument)",
        target=Variable("T", "s", tuple(T)),
        inputs=(Variable("a", "m", tuple(a)),),
        constants=(Constant("mu", MU, "m^3/s^2"),),
    )


# --------------------------------------------------------------------------------------------
# (a) true transcendental of a π-group → bestaetigt (and power rival does not clear)
# --------------------------------------------------------------------------------------------

def test_true_transcendental_of_pi_group_yields_bestaetigt():
    """Headline (a): exact transcendental over dimensionless group is gated bestaetigt because
    the fitted R² clears the strict bar AND the best power-of-group rival does NOT."""
    prob = _exp_decay_trans()
    law = discover_transcendental(prob)
    assert isinstance(law, TranscendentalLaw)
    assert law.verdict == "bestaetigt"
    assert law.form_name == "exp"
    assert law.r_squared >= 0.999
    assert law.powerlaw_r2 < 0.999, "power-of-group must not clear for genuine transcendental"
    # alpha recovered near -1, C near generating value
    assert abs(law.params.get("alpha", 0.0) + 1.0) < 0.02
    assert abs(law.params.get("C", 0.0) - 10.0) < 0.2


def test_different_transcendental_inputs_produce_meaningfully_different_output():
    """Facade detector (L4): driving input change must change headline output — proves consumption."""
    p_exp = _exp_decay_trans(c=10.0, alpha=-1.0)
    p_sine = _sine_trans()
    law_exp = discover_transcendental(p_exp)
    law_sine = discover_transcendental(p_sine)
    # different form or very different verdict/params
    assert law_exp.form_name != law_sine.form_name or law_exp.verdict != law_sine.verdict
    # r2 high for both but the expressions differ
    assert law_exp.expression != law_sine.expression


# --------------------------------------------------------------------------------------------
# (b) target is power/quadratic of the π-group → unentschieden (power rival clears bar too)
# --------------------------------------------------------------------------------------------

def test_power_law_of_same_group_yields_unentschieden():
    """Headline (b): when target really is a power law of the group, the power rival also clears
    the bar and the verdict is unentschieden — the honest refusal to over-claim transcendental."""
    prob = _quadratic_power_of_group()
    law = discover_transcendental(prob)
    assert law.verdict == "unentschieden"
    assert law.r_squared >= 0.999, "transcendental fit must reach the bar (approx)"
    assert law.powerlaw_r2 >= 0.999, "the power-of-group rival must clear the bar exactly"
    # the power rival is decisive: its r2 is essentially 1
    assert abs(law.powerlaw_r2 - 1.0) < 1e-5


def test_rivals_api_exposes_distinguishable_forms_for_unentschieden_case():
    """Exercise discover_rivals + evaluate + refit (as required by spec) and prove they are driven
    by input: both rivals exist, evaluate reproduces data on the power case, refit on identical
    data yields equivalent quality."""
    prob = _quadratic_power_of_group()
    t_rival, p_rival = discover_rivals(prob)
    assert t_rival is not None
    assert p_rival is not None
    assert isinstance(t_rival, RivalForm)
    assert isinstance(p_rival, RivalForm)
    # power rival evaluates to nearly exact match on its own data
    yhat = evaluate_rival(p_rival, prob)
    y = np.asarray(prob.target.values)
    r2_eval = 1.0 - np.sum((y - yhat)**2) / np.sum((y - y.mean())**2) if np.var(y) > 0 else 1.0
    assert r2_eval > 0.999
    # refit on identical data must not degrade
    refit = refit_rival(p_rival, prob)
    assert refit is not None
    assert refit.r_squared >= 0.999


# --------------------------------------------------------------------------------------------
# (c) no dimensionless argument → widerlegt
# --------------------------------------------------------------------------------------------

def test_no_dimensionless_group_yields_widerlegt():
    """Headline (c): Kepler-style case (no null-space group) produces widerlegt and empty groups.
    The discovery never fabricates a transcendental when no dimensionless argument exists."""
    prob = _kepler_no_dimless()
    assert dimensionless_groups(prob) == []
    law = discover_transcendental(prob)
    assert law.verdict == "widerlegt"
    assert "kein dimensionsloses" in law.expression or "keine Form" in law.expression


def test_verdict_changes_with_presence_of_dimensionless_group():
    """Facade detector: same-style numeric shape but presence/absence of π-group flips verdict
    from bestaetigt to widerlegt — proves the group enumeration is consumed, not ignored."""
    # construct a pure-power but WITH a dimensionless group by adding a matching constant
    # (reuse exp data but treat as power target to force different verdict path)
    p_with_group = _quadratic_power_of_group()
    p_no_group = _kepler_no_dimless()
    v_with = discover_transcendental(p_with_group).verdict
    v_no = discover_transcendental(p_no_group).verdict
    assert v_with != v_no
    assert v_with == "unentschieden"
    assert v_no == "widerlegt"


# --------------------------------------------------------------------------------------------
# negative test for documented guard (exact message for regression safety)
# --------------------------------------------------------------------------------------------

def test_non_positive_magnitudes_raises_documented_valueerror():
    """Negative test (required): non-positive input/constant must raise ValueError with the
    documented message. Zero and negative are both rejected (π-groups require positive magnitudes)."""
    bad_input = DiscoveryProblem(
        idea="bad",
        target=Variable("x", "m", (1.0, 2.0, 3.0)),
        inputs=(Variable("t", "s", (1.0, -1.0, 3.0)),),
        constants=(Constant("tau", 5.0, "s"),),
    )
    with pytest.raises(ValueError, match="non-positive values; a π-group needs positive magnitudes"):
        discover_transcendental(bad_input)

    bad_const = DiscoveryProblem(
        idea="badc",
        target=Variable("x", "m", (1.0, 2.0, 3.0)),
        inputs=(Variable("t", "s", (1.0, 2.0, 3.0)),),
        constants=(Constant("tau", 0.0, "s"),),
    )
    with pytest.raises(ValueError, match="must be positive"):
        discover_transcendental(bad_const)


# --------------------------------------------------------------------------------------------
# zero-sample guard tests (covers all functions sharing the validation path + dimensionless_groups)
# exact message to catch regressions; per 'a gate without a test does not exist'
# --------------------------------------------------------------------------------------------

def _empty_problem() -> DiscoveryProblem:
    """Zero-sample target (and matching empty inputs) — must fail loud before any fit or group work."""
    return DiscoveryProblem(
        idea="empty",
        target=Variable("y", "m", ()),
        inputs=(Variable("t", "s", ()),),
        constants=(Constant("tau", 5.0, "s"),),
    )


def test_zero_sample_target_raises_documented_valueerror_for_all_entry_points():
    """All public entry points through _source_arrays (and dimensionless_groups) must raise
    the exact 'target has no samples' (matching engine.symbolic_regress) on n==0.
    Previously only discover_transcendental was covered by non-positive test."""
    empty = _empty_problem()
    # discover_transcendental
    with pytest.raises(ValueError, match="target has no samples"):
        discover_transcendental(empty)
    # discover_rivals
    with pytest.raises(ValueError, match="target has no samples"):
        discover_rivals(empty)
    # evaluate_rival (needs a dummy rival; guard fires first in _source_arrays)
    dummy_rival = RivalForm(form_name="pow", group={"t": 1.0, "tau": -1.0}, params={"C": 1.0, "beta": 1.0, "D": 0.0}, r_squared=0.0)
    with pytest.raises(ValueError, match="target has no samples"):
        evaluate_rival(dummy_rival, empty)
    # refit_rival
    with pytest.raises(ValueError, match="target has no samples"):
        refit_rival(dummy_rival, empty)
    # dimensionless_groups (now guarded explicitly for consistency)
    with pytest.raises(ValueError, match="target has no samples"):
        dimensionless_groups(empty)


# --------------------------------------------------------------------------------------------
# determinism (A5 contract) and output consumption
# --------------------------------------------------------------------------------------------

def test_same_problem_yields_identical_law_deterministic():
    """Reproducibility: identical DiscoveryProblem yields bit-identical TranscendentalLaw."""
    prob = _exp_decay_trans()
    l1 = discover_transcendental(prob)
    l2 = discover_transcendental(prob)
    assert l1 == l2


# --------------------------------------------------------------------------------------------
# property-based invariants (Hypothesis) — must hold for all generated positive parameters
# --------------------------------------------------------------------------------------------

@settings(deadline=None, max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    c=st.floats(min_value=0.5, max_value=50.0),
    alpha=st.floats(min_value=-8.0, max_value=-0.9),
)
def test_property_exact_trans_recovers_parameters_and_clears_bestaetigt(c: float, alpha: float):
    """For positive C and sufficiently negative alpha (strong curvature over the sampled range),
    an exact exp(α·π) law is recovered with R²=1 and bestaetigt (the power rival cannot reach
    the bar within tolerance). Shallow alphas allow power approx to clear 0.999 → correctly
    unentschieden; the bound ensures the honest distinction is exercised."""
    prob = _exp_decay_trans(c=c, alpha=alpha)
    law = discover_transcendental(prob)
    assert law.verdict == "bestaetigt"
    assert law.r_squared == pytest.approx(1.0, abs=1e-9)
    assert abs(law.params["C"] - c) < 0.1
    assert abs(law.params["alpha"] - alpha) < 0.1
    assert law.powerlaw_r2 < 0.999


@settings(deadline=None, max_examples=20)
@given(k=st.floats(min_value=0.1, max_value=10.0))
def test_property_target_scaling_scales_C_only_preserves_r2_and_verdict(k: float):
    """Scaling the target values by k>0 must scale only the C parameter (and D if present) while
    leaving R² and verdict unchanged — the transcendental shape is scale-invariant in this model.
    Proves the fit, R², and verdict decision are genuinely computed from the supplied y, not canned."""
    prob0 = _exp_decay_trans(c=8.0, alpha=-1.5)
    law0 = discover_transcendental(prob0)
    y0 = np.asarray(prob0.target.values)
    prob1 = DiscoveryProblem(
        prob0.idea,
        Variable(prob0.target.name, prob0.target.unit, tuple(y0 * k)),
        prob0.inputs,
        prob0.constants,
    )
    law1 = discover_transcendental(prob1)
    # verdict and r2 preserved
    assert law1.verdict == law0.verdict == "bestaetigt"
    assert law1.r_squared == pytest.approx(law0.r_squared, abs=1e-9)
    # C scales (within numeric tolerance of the nonlinear fit)
    c0 = law0.params.get("C", 0.0)
    c1 = law1.params.get("C", 0.0)
    assert abs(c1 - c0 * k) < 0.2 or abs(c1 - c0 * k) / max(abs(c0 * k), 1e-9) < 0.05


# --------------------------------------------------------------------------------------------
# additional coverage for review findings (bestaetigt rivals path, non-finite guards,
# length consistency, grid boundary, public import surface for refit_rival)
# --------------------------------------------------------------------------------------------

def test_discover_rivals_exercises_bestaetigt_path():
    """Rivals API must be exercised on bestaetigt case (transcendental rival exists and is
    distinguishable from power rival); previous coverage only hit unentschieden/quadratic.
    Use public surface import for refit_rival."""
    prob = _exp_decay_trans()
    t_rival, p_rival = discover_rivals(prob)
    assert t_rival is not None
    assert t_rival.form_name in ("exp", "sin", "tanh", "log")
    assert p_rival is not None
    assert p_rival.form_name == "pow"
    # trans rival should evaluate to near-exact on its data (for bestaetigt)
    yhat = evaluate_rival(t_rival, prob)
    y = np.asarray(prob.target.values)
    ss_res = np.sum((y - yhat)**2)
    ss_tot = np.sum((y - np.mean(y))**2)
    r2 = 1.0 if ss_tot <= 0 else 1.0 - ss_res / ss_tot
    assert r2 > 0.999
    # refit on same data via public symbol
    refit = refit_rival(t_rival, prob)
    assert refit is not None
    assert refit.r_squared > 0.999


def test_non_finite_data_raises_loud_valueerror():
    """Non-finite (nan/inf) in target or inputs must raise loud ValueError (not produce
    nan r2 -> silent widerlegt or curve_fit exception). Added per L4 review finding."""
    # bad target y
    prob = _exp_decay_trans()
    bad_y = list(prob.target.values)
    bad_y[0] = float("nan")
    bad_prob = DiscoveryProblem(
        prob.idea,
        Variable(prob.target.name, prob.target.unit, tuple(bad_y)),
        prob.inputs, prob.constants
    )
    with pytest.raises(ValueError, match="non-finite"):
        discover_transcendental(bad_prob)

    # bad input
    t = np.array([1.0, 2.0, 3.0])
    t[0] = float("inf")
    bad_in = DiscoveryProblem(
        "badinf",
        Variable("y", "m", (1.,2.,3.)),
        (Variable("t", "s", tuple(t)),),
        (Constant("tau", 1.0, "s"),)
    )
    with pytest.raises(ValueError, match="non-finite"):
        discover_transcendental(bad_in)
    with pytest.raises(ValueError, match="non-finite"):
        dimensionless_groups(bad_in)


@given(
    bad = st.floats(allow_nan=True, allow_infinity=True),
)
@settings(deadline=None, max_examples=10, suppress_health_check=[HealthCheck.filter_too_much])
def test_property_non_finite_raises(bad: float):
    """Property: any non-finite value in input array forces loud error (invariant for all such data)."""
    # only test when actually non-finite
    if not (np.isnan(bad) or np.isinf(bad)):
        return
    t = np.array([1.0, 2.0, 3.0])
    t[1] = bad
    p = DiscoveryProblem("p", Variable("y","m",(10.,20.,30.)), (Variable("t","s",tuple(t)),), ())
    with pytest.raises(ValueError, match="non-finite|no samples"):
        discover_transcendental(p)


def test_length_mismatch_raises_early_structural_error():
    """Length mismatch between target and inputs now caught early (like engine); prevents
    surprising r2=0.0 or shape errors in _group_values/_r2 for degenerate cases."""
    prob = DiscoveryProblem(
        "mismatch",
        Variable("y", "m", (1.0, 2.0, 3.0)),
        (Variable("t", "s", (1.0, 2.0)),),  # len 2 != 3
        (Constant("tau", 1.0, "s"),)
    )
    with pytest.raises(ValueError, match="samples, target has"):
        discover_transcendental(prob)


def test_dimensionless_groups_includes_exact_boundary_exponents():
    """Grid construction (arange + round + eps) must include exact ±max_abs_exp values;
    tests numeric boundary to protect against fp fragility in lattice enumeration."""
    # simple ratio setup
    prob = _exp_decay_trans(n=4)
    # step=1.0 makes ±2 easy to hit exactly
    groups = dimensionless_groups(prob, max_abs_exp=2.0, step=1.0)
    t_exps = sorted({abs(g.get("t", 0.0)) for g in groups if "t" in g})
    assert 2.0 in t_exps, f"expected boundary 2.0 in {t_exps}"
    # also for negative
    all_exps = [g.get("t", 0.0) for g in groups]
    assert 2.0 in all_exps and -2.0 in all_exps
