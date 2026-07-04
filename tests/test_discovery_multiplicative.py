"""Multiplicative-coupling discovery (Frontier 6.6) — product laws ``y = C·π1^a·f(α·π2)`` gated
against the pure power-law rival, and the multiplicative minimal-correction ``y ≈ y_base·m(π)``
under the 6.5 gates (ratio_explained ∧ ΔR² ∧ Leave-One-Out). Pins the honest method: dimensionless
π-pairs only, log path refused on sign-free targets (no silent abs), noise never promoted to a
coupling, ties resolved actively via the 6.4 seam (Flip-Test).
"""

import numpy as np
import pytest

from gen.discovery import (
    Constant, DiscoveryProblem, Variable,
    MultiplicativeCorrection, ProductLaw,
    discover_multiplicative_correction, discover_product_law, discover_product_rivals,
    product_out_of_sample_validate, propose_resolution,
)


def _wien_values(t: np.ndarray, tau: float = 1.0, c: float = 2.0) -> np.ndarray:
    """The Wien / Planck-tail product shape u = C·x³·e^(−x) with x = t/τ — a KNOWN physical
    product law (power × exponential) the module must rediscover exactly."""
    x = t / tau
    return c * x**3 * np.exp(-x)


def _wien_problem(t: np.ndarray, y: np.ndarray, idea: str = "Wien-Produktform") -> DiscoveryProblem:
    return DiscoveryProblem(
        idea=idea, target=Variable("u", "W", tuple(y)),
        inputs=(Variable("t", "s", tuple(t)),),
        constants=(Constant("tau", 1.0, "s"),))


_T_WIDE = np.linspace(0.3, 6.0, 14)          # wide range: the e^(−x) turnover is in the data

#: Reduced π-lattice for the runtime-heavy secondary tests: the groups (t/τ)^{±0.5, ±1} fully
#: contain the true law's arguments, so nothing about the claim weakens — only the pair count
#: (and with it the curve_fit budget) shrinks. The primary acceptance test runs on the DEFAULT
#: lattice.
_FAST = {"max_abs_exp": 1.0}


def test_rediscovers_wien_product_law_exactly():
    """u = 2·x³·e^(−x) is recovered as exp-product with verdict bestätigt: the product form is
    exact (R²≈1) while the pure power-law rival C·π1^p·π2^q+D cannot follow the turnover. The
    EFFECTIVE exponents are pinned: a·(base t-exponent) = 3, α·(mod t-exponent) = −1, C = 2 —
    the exact known law, independent of which lattice orientation the fit picked."""
    law = discover_product_law(_wien_problem(_T_WIDE, _wien_values(_T_WIDE)))
    assert isinstance(law, ProductLaw)
    assert law.verdict == "bestaetigt"
    assert law.form_name == "exp"
    assert law.r_squared > 0.999
    assert law.powerlaw_r2 < 0.999           # the power rival does NOT explain the turnover
    a_eff = law.params["a"] * law.base_group["t"]
    alpha_eff = law.params["alpha"] * law.mod_group["t"]
    assert abs(a_eff - 3.0) < 1e-6
    assert abs(alpha_eff + 1.0) < 1e-6
    assert abs(law.params["C"] - 2.0) < 1e-6
    assert law.log_path_applied              # strictly positive target → exact log path ran


def test_log_path_is_refused_for_sign_free_target_but_direct_fit_still_works():
    """A negative-valued target refuses the log path (log|y| would silently change the model —
    never a silent abs), yet the direct scipy path still recovers the law with C = −2."""
    law = discover_product_law(_wien_problem(_T_WIDE, -_wien_values(_T_WIDE)), **_FAST)
    assert not law.log_path_applied
    assert law.verdict == "bestaetigt"
    assert law.form_name == "exp"
    assert abs(law.params["C"] + 2.0) < 1e-6


def test_pure_power_law_is_never_claimed_as_product_coupling():
    """The decisive red-team: y = 4·x² IS a power law. The product family fits it too (exp with
    α→0 degenerates to a power), so the honest gate relies on the power rival ALSO being exact —
    verdict unentschieden, never a multiplicative over-claim for a plain power law."""
    y = 4.0 * (_T_WIDE / 1.0) ** 2
    law = discover_product_law(_wien_problem(_T_WIDE, y, "Potenz"), **_FAST)
    assert law.verdict == "unentschieden"
    assert law.powerlaw_r2 > 0.999


def test_noise_is_never_promoted_to_a_product_law():
    """Pure noise clears no 0.999 bar in the product family — verdict widerlegt (anti-
    hallucination, δ-asymmetry): out of noise, NO coupling is ever 'discovered'."""
    rng = np.random.default_rng(7)
    t = np.linspace(0.5, 4.0, 12)
    y = rng.uniform(0.5, 1.5, size=12)
    law = discover_product_law(_wien_problem(t, y, "Rauschen"), **_FAST)
    assert law.verdict == "widerlegt"
    assert law.r_squared < 0.999


def test_kepler_has_no_dimensionless_pair_so_no_product_claim():
    """(a, μ) admit no dimensionless group at all → no π-pair, honest widerlegt with the
    explicit 'kein dimensionsloses Argument' diagnosis (dimensional validity is enforced)."""
    import math
    mu = 1.32712440018e20
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11, 1.434e12])
    big_t = 2.0 * math.pi * a**1.5 / math.sqrt(mu)
    problem = DiscoveryProblem(
        idea="Kepler", target=Variable("T", "s", tuple(big_t)),
        inputs=(Variable("a", "m", tuple(a)),),
        constants=(Constant("mu", mu, "m^3/s^2"),))
    law = discover_product_law(problem)
    assert law.verdict == "widerlegt"
    assert "kein dimensionsloses Argument" in law.expression


def test_product_law_generalises_out_of_sample():
    """6.2 seam: the Wien product law discovered on a train split transfers UNCHANGED (no refit)
    to the held-out split — a real product law generalises."""
    val = product_out_of_sample_validate(_wien_problem(_T_WIDE, _wien_values(_T_WIDE)), **_FAST)
    assert val.generalises
    assert val.test_r2 > 0.999
    assert abs(val.overfit_gap) < 1e-6


def test_noise_product_fit_does_not_generalise_out_of_sample():
    """The train-split best fit on noise collapses on the held-out split — the OOS validator
    catches what an in-sample fit alone could hide."""
    rng = np.random.default_rng(7)
    t = np.linspace(0.5, 4.0, 12)
    y = rng.uniform(0.5, 1.5, size=12)
    val = product_out_of_sample_validate(_wien_problem(t, y, "Rauschen"), **_FAST)
    assert not val.generalises
    assert val.test_r2 < 0.99


def test_flip_narrow_band_tie_is_resolved_by_active_measurement():
    """DER Akzeptanztest (6.4 seam): on a narrow band the Wien law and a power law are
    indistinguishable (unentschieden). discover_product_rivals hands both fitted rivals to
    propose_resolution, which computes a discriminating spread; measuring the TRUE values there
    flips the verdict to bestätigt — the product frontier is actively resolvable."""
    t_narrow = np.linspace(2.0, 2.4, 8)
    narrow = _wien_problem(t_narrow, _wien_values(t_narrow))
    assert discover_product_law(narrow, **_FAST).verdict == "unentschieden"

    rival_prod, rival_pow = discover_product_rivals(narrow, **_FAST)
    assert rival_prod is not None and rival_pow is not None
    spec = propose_resolution(rival_prod, rival_pow, narrow)
    assert spec.discriminating
    assert all(m > 0.0 for m in spec.measure_at)

    t_aug = np.concatenate([t_narrow, np.asarray(spec.measure_at)])
    flipped = discover_product_law(_wien_problem(t_aug, _wien_values(t_aug)), **_FAST)
    assert flipped.verdict == "bestaetigt"
    assert flipped.powerlaw_r2 < 0.999       # the power rival collapsed on the new regime


def test_rejects_non_positive_source_magnitudes():
    """π-groups need positive magnitudes; a non-positive input is a hard ValueError."""
    bad = DiscoveryProblem(
        idea="kaputt", target=Variable("u", "W", (1.0, 2.0, 3.0, 4.0)),
        inputs=(Variable("t", "s", (1.0, -2.0, 3.0, 4.0)),),
        constants=(Constant("tau", 1.0, "s"),))
    with pytest.raises(ValueError):
        discover_product_law(bad)


# ---------------------------------------------------------------------------
# Part (b): multiplicative minimal-correction  y ≈ y_base · m(π)
# ---------------------------------------------------------------------------

#: Irregular sampling — on an evenly spaced grid a sinusoid is identified only up to aliasing
#: (documented data caveat); irregular points pin the frequency uniquely.
_T_DAMPED = np.array([0.2, 0.5, 0.9, 1.3, 1.8, 2.2, 2.7, 3.1, 3.6, 4.0, 4.3, 4.9, 5.3, 5.8, 6.1])
_ZETA, _OMEGA, _AMP = 0.3, 2.0, 4.0


def _damped_problem() -> tuple[DiscoveryProblem, np.ndarray]:
    """Damped oscillation x(t) = A·e^(−ζt)·cos(ωt) — the classic product of two transcendentals.
    The exponential envelope is the DECLARED baseline (a sourced law); the module must find the
    multiplicative modulation cos(ωt) on the ratio."""
    y_base = _AMP * np.exp(-_ZETA * _T_DAMPED)
    y = y_base * np.cos(_OMEGA * _T_DAMPED)
    problem = DiscoveryProblem(
        idea="Gedämpfte Schwingung", target=Variable("x", "m", tuple(y)),
        inputs=(Variable("t", "s", tuple(_T_DAMPED)),),
        constants=(Constant("zeta", _ZETA, "1/s"), Constant("omega", _OMEGA, "1/s")))
    return problem, y_base


def test_damped_oscillation_modulation_is_rediscovered_exactly():
    """x = A·e^(−ζt)·cos(ωt) with baseline A·e^(−ζt): the ratio is cos(ωt), recovered as the
    phase-shifted sin form with the EXACT angular frequency ω = 2 (checked as the effective
    frequency α·π/t, independent of which π-group orientation the fit picked), R²≈1 on ratio
    AND corrected target, LOO-survival — verdict korrektur_noetig."""
    problem, y_base = _damped_problem()
    res = discover_multiplicative_correction(problem, y_base)
    assert isinstance(res, MultiplicativeCorrection)
    assert res.verdict == "korrektur_noetig"
    assert res.form_name == "sin"
    assert res.ratio_explained > 1.0 - 1e-9
    assert res.corrected_r2 > 1.0 - 1e-9
    assert res.loo_r2 > 0.99
    # effective frequency: π = t·ζ^gz·ω^gw → dπ/dt = ζ^gz·ω^gw; |α·dπ/dt| must equal ω = 2.
    per_t = _ZETA ** res.group.get("zeta", 0.0) * _OMEGA ** res.group.get("omega", 0.0)
    assert abs(res.group.get("t", 0.0) - 1.0) < 1e-9
    freq = abs(res.params["alpha"]) * per_t
    assert abs(freq - _OMEGA) < 1e-3
    # the modulation swings a full ±1 around 1 → RMS(m−1) ≈ sqrt(1.5), far from "no correction"
    assert 1.0 < res.relative_modulation < 1.5


def test_exact_baseline_is_a_constant_rescaling_never_a_pi_coupling():
    """baseline == y → ratio ≡ 1 (a constant). A constant has no π-dependence, so no modulation
    is claimed (any form would 'fit' it via its offset) — verdict vollstaendig."""
    problem, _ = _damped_problem()
    y = np.asarray(problem.target.values, float)
    res = discover_multiplicative_correction(problem, y.copy())
    assert res.verdict == "vollstaendig"
    assert res.form_name == "none"
    assert "konstante Reskalierung" in res.expression


def test_noise_ratio_is_not_promoted_to_a_modulation():
    """A ratio that is pure noise does NOT become a 'coupling': the in-sample bar and above all
    the leave-one-out gate reject it (structured-noise defence, δ-asymmetry)."""
    problem, y_base = _damped_problem()
    rng = np.random.default_rng(3)
    y = y_base * (1.0 + 0.3 * rng.standard_normal(_T_DAMPED.shape))
    noisy = DiscoveryProblem(
        idea="Rauschen", target=Variable("x", "m", tuple(y)),
        inputs=problem.inputs, constants=problem.constants)
    res = discover_multiplicative_correction(noisy, y_base)
    assert res.verdict == "vollstaendig"
    assert res.form_name == "none"
    assert res.ratio_explained < 0.9 or res.loo_r2 < 0.5    # at least one gate rejected it


def test_power_modulation_is_preferred_over_transcendental_when_exact():
    """Occam guard: a ratio that IS a power of a group ((t/τ)²) is claimed as the pow modulation
    — never dressed up as a transcendental that merely fits as well."""
    t = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    y_base = 5.0 * t
    y = y_base * (t / 2.0) ** 2
    problem = DiscoveryProblem(
        idea="Potenz-Modulation", target=Variable("y", "m", tuple(y)),
        inputs=(Variable("t", "s", tuple(t)),),
        constants=(Constant("tau", 2.0, "s"),))
    res = discover_multiplicative_correction(problem, y_base)
    assert res.verdict == "korrektur_noetig"
    assert res.form_name == "pow"
    assert res.powerlaw_ratio_r2 > 0.999


def test_division_is_refused_at_a_baseline_zero():
    """Gate-Verweigerung: a baseline containing a (near-)zero makes the ratio meaningless there
    — hard ValueError, no silent masking or clipping of points."""
    problem, y_base = _damped_problem()
    y_base = y_base.copy()
    y_base[4] = 0.0
    with pytest.raises(ValueError, match="Gate-Verweigerung"):
        discover_multiplicative_correction(problem, y_base)


def test_rejects_a_baseline_of_the_wrong_length():
    problem, _ = _damped_problem()
    with pytest.raises(ValueError):
        discover_multiplicative_correction(problem, np.array([1.0, 2.0, 3.0]))


def test_no_dimensionless_group_means_no_modulation_claim():
    """Without any dimensionless argument there is nothing a modulation could depend on —
    honest vollstaendig (no claim), with the explicit diagnosis."""
    import math
    mu = 1.32712440018e20
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11, 1.434e12])
    big_t = 2.0 * math.pi * a**1.5 / math.sqrt(mu)
    problem = DiscoveryProblem(
        idea="Kepler", target=Variable("T", "s", tuple(big_t)),
        inputs=(Variable("a", "m", tuple(a)),),
        constants=(Constant("mu", mu, "m^3/s^2"),))
    res = discover_multiplicative_correction(problem, big_t * 1.1 + big_t**2 / np.max(big_t))
    assert res.verdict == "vollstaendig"
    assert "kein dimensionsloses Argument" in res.expression
