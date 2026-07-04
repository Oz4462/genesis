"""Additive π-arguments inside one transcendental (Frontier 6.8) — ``y = C·f(α·π1 + β·π2) + D``
(e.g. an Arrhenius-like rate with TWO dimensionless contributions in one exponent). Pins the
honest method: the two-contribution Arrhenius law is rediscovered exactly; ``f = exp`` with an
additive argument is recognised as THE canonical representation of the ``exp·exp`` product that
6.7 deliberately excluded (equivalence documented, never a double claim); ``β = 0`` collapses
onto the 6.3 single form via the Occam ladder; proportional π-pairs are an affine parameter
ridge and are never promoted to a two-group claim; noise is never promoted; a narrow-band tie
is ``unentschieden`` and flips via the 6.4 discriminating measurement.
"""

import math

import numpy as np
import pytest

from gen.discovery import (
    AdditiveArgumentLaw, Constant, DiscoveryProblem, Variable,
    additive_argument_out_of_sample_validate, discover_additive_argument,
    discover_additive_argument_rivals, discover_blind_product, evaluate_additive_rival,
    propose_resolution,
)

#: Irregular sampling (as in 6.6/6.7): on an evenly spaced grid a sinusoidal argument is
#: identified only up to aliasing; irregular points pin the coefficients uniquely.
_T_IRREG = np.array([0.2, 0.5, 0.9, 1.3, 1.8, 2.2, 2.7, 3.1, 3.6, 4.0, 4.3, 4.9, 5.3, 5.8, 6.1])

#: Reduced π-lattice (as in the 6.6/6.7 tests): with τ = 1 s the groups (t/τ)^{±0.5, ±1} fully
#: contain the true laws' arguments (t/τ and √(t/τ)), so nothing about the claim weakens — only
#: the pair count and with it the curve_fit budget shrinks.
_FAST = {"max_abs_exp": 1.0}

_ALPHA, _BETA, _AMP = -1.2, 2.0, 3.0


def _two_scale_exp(t: np.ndarray) -> np.ndarray:
    """y = 3·exp(−1.2·x + 2·√x), x = t/τ — ONE exponential of an ADDITIVE two-π argument."""
    return _AMP * np.exp(_ALPHA * t + _BETA * np.sqrt(t))


_CHIRP_ALPHA, _CHIRP_BETA, _CHIRP_PHI = 1.5, 0.8, 0.4


def _chirp(t: np.ndarray) -> np.ndarray:
    """y = 3·sin(1.5·x + 0.8·√x + 0.4) — a CHIRP: one sinusoid whose additive two-π argument
    drifts in frequency. No single-π sinusoid and no π-pair product can follow it globally."""
    return 3.0 * np.sin(_CHIRP_ALPHA * t + _CHIRP_BETA * np.sqrt(t) + _CHIRP_PHI)


def _arrhenius_problem() -> DiscoveryProblem:
    """k = 2·exp(−θ/T − 0.5·P/p0) over a WIDE two-sided regime (θ/T ∈ [0.33, 4], P/p0 ∈
    [0.1, 5]). The width is what makes the claim honest: on a narrow band (θ/T ≈ 0.8–1.2,
    measured while building) a saturating tanh / single-hump sine imitates the exponential to
    R² > 0.999 and the honest verdict is unentschieden — widening the regime is the 6.4 lesson
    applied at design time."""
    temp = np.array([75.0, 90.0, 110.0, 140.0, 170.0, 210.0, 260.0, 320.0, 400.0, 500.0, 700.0, 900.0])
    press = np.array([0.1e5, 3.2e5, 0.6e5, 1.8e5, 5.0e5, 0.9e5, 2.6e5, 0.25e5, 4.1e5, 0.45e5, 1.3e5, 3.6e5])
    theta, p0 = 300.0, 1.0e5
    k = 2.0 * np.exp(-(theta / temp) - 0.5 * (press / p0))
    return DiscoveryProblem(
        idea="Arrhenius mit zwei Beiträgen", target=Variable("k", "1/s", tuple(k)),
        inputs=(Variable("T", "K", tuple(temp)), Variable("P", "Pa", tuple(press))),
        constants=(Constant("theta", theta, "K"), Constant("p0", p0, "Pa")))


def _pi_values(group: dict[str, float], problem: DiscoveryProblem) -> np.ndarray:
    """π-group values recomputed independently from the problem's inputs/constants."""
    n = len(problem.target.values)
    sources = {v.name: np.asarray(v.values, dtype=float) for v in problem.inputs}
    sources.update({c.name: np.full(n, float(c.value)) for c in problem.constants})
    pi = np.ones(n)
    for name, exponent in group.items():
        if abs(exponent) > 1e-12:
            pi = pi * sources[name] ** exponent
    return pi


def _problem(t: np.ndarray, y: np.ndarray, idea: str = "Zwei-Skalen-Exponential") -> DiscoveryProblem:
    return DiscoveryProblem(
        idea=idea, target=Variable("x", "m", tuple(y)),
        inputs=(Variable("t", "s", tuple(t)),),
        constants=(Constant("tau", 1.0, "s"),))


def _coefficient_of(law: AdditiveArgumentLaw, group: dict[str, float]) -> float:
    """The fitted coefficient attached to `group` (α for group_f, β for group_g) — pair order
    inside the law is enumeration order, so the test maps by group content."""
    def matches(g: dict[str, float]) -> bool:
        keys = set(g) | set(group)
        return all(abs(g.get(k, 0.0) - group.get(k, 0.0)) < 1e-9 for k in keys)
    if matches(law.group_f):
        return law.params["alpha"]
    assert matches(law.group_g), f"group {group} not in law ({law.group_f}, {law.group_g})"
    return law.params["beta"]


def test_arrhenius_with_two_contributions_is_rediscovered():
    """DER Akzeptanztest: k = 2·exp(−θ/T − 0.5·P/p0) — an Arrhenius-like rate with TWO
    dimensionless contributions in ONE exponent — is rediscovered exactly: C = 2, the θ/T group
    carries −1, the P/p0 group carries −0.5, D = 0. All four Occam-ladder rivals (power law with
    offset, 6.3 single form, 6.6 product, 6.7 blind pair) stay below the bar and the
    train-refitted winner transfers out-of-sample — verdict bestätigt."""
    law = discover_additive_argument(_arrhenius_problem(), max_abs_exp=1.0, step=1.0)
    assert isinstance(law, AdditiveArgumentLaw)
    assert law.verdict == "bestaetigt"
    assert law.form_name == "exp"
    assert law.r_squared > 0.999
    assert law.powerlaw_r2 < 0.999
    assert law.single_r2 < 0.999
    assert law.product_power_r2 < 0.999
    assert law.blind_r2 < 0.999
    assert law.oos_confirm_r2 > 0.99
    assert abs(law.params["C"] - 2.0) < 1e-6
    assert abs(law.params["D"]) < 1e-6
    assert abs(_coefficient_of(law, {"T": -1.0, "theta": 1.0}) + 1.0) < 1e-6
    assert abs(_coefficient_of(law, {"P": 1.0, "p0": -1.0}) + 0.5) < 1e-6


def test_exp_additive_is_the_canonical_product_representation():
    """Äquivalenz-Wächter: exp(α·π1 + β·π2) IS exp(α·π1)·exp(β·π2) — the very form 6.7
    deliberately excluded from its pair library (guard (a): a single exponential of an additive
    argument). 6.8 is its canonical home: the law names the product equivalence, the two
    representations agree machine-exactly, and 6.7 on the same data never issues a rival
    two-transcendental claim — one law, one canonical form, no double claim."""
    problem = _arrhenius_problem()
    law = discover_additive_argument(problem, max_abs_exp=1.0, step=1.0)
    assert law.verdict == "bestaetigt"
    assert law.form_name == "exp"
    assert "exp" in law.product_equivalent and law.product_equivalent.count("exp(") == 2
    # numeric equivalence of the two representations on the observed data
    pi1 = _pi_values(law.group_f, problem)
    pi2 = _pi_values(law.group_g, problem)
    additive = evaluate_additive_rival(law, problem)
    product = (law.params["C"] * np.exp(law.params["alpha"] * pi1)
               * np.exp(law.params["beta"] * pi2))
    assert np.allclose(additive - law.params["D"], product, rtol=1e-9, atol=1e-12)
    # 6.7 never claims this data as a two-transcendental product (its guard (a) dispatches here)
    blind = discover_blind_product(problem, max_abs_exp=1.0, step=1.0)
    assert blind.verdict != "bestaetigt"


def test_single_input_two_scale_exponential_is_honestly_undecided():
    """δ-Asymmetrie in Reinform: y = 3·exp(−1.2·x + 2·√x) (x = t/τ) is fitted EXACTLY in-family
    (R² = 1), yet on a single input this one-hump shape is imitable by a 6.7 pair
    (exp·sin ≥ 0.999, measured while building) — so the honest verdict is unentschieden with the
    tie NAMED, never a claim the data cannot separate. The active 6.4 move, not a bigger claim,
    is the designed way out."""
    law = discover_additive_argument(_problem(_T_IRREG, _two_scale_exp(_T_IRREG)), **_FAST)
    assert law.r_squared > 0.999                    # the family DOES contain the truth
    assert law.verdict == "unentschieden"           # ...but the data cannot separate it
    assert law.occam_winner == "blind_produkt"
    assert law.blind_r2 > 0.999


def test_beta_zero_collapses_to_the_single_transcendental_family():
    """Occam: y = 2·exp(−0.8·t/τ) needs only ONE π-contribution. The additive form fits it too
    (β = 0), but the 6.3 single family is equally exact → unentschieden with the collapse named —
    never a two-group over-claim for what one group explains."""
    law = discover_additive_argument(
        _problem(_T_IRREG, 2.0 * np.exp(-0.8 * _T_IRREG), "ein Beitrag"), **_FAST)
    assert law.verdict == "unentschieden"
    assert law.occam_winner == "einzel_transzendent"
    assert law.single_r2 > 0.999


def test_proportional_pi_groups_are_an_affine_ridge_not_a_law():
    """Ridge-Wächter: with two same-unit constants τ1, τ2 the groups t/τ1 and t/τ2 are pointwise
    proportional — α·(t/τ1) + β·(t/τ2) has only ONE identifiable direction (a parameter ridge,
    exactly the 6.7 exp·exp degeneracy in affine form). The data 2·exp(−0.8·t/τ1 − 0.2·t/τ2) IS a
    single exponential, and the verdict says so: collapse onto the single family, no two-group
    claim built on a ridge pair."""
    t = _T_IRREG
    y = 2.0 * np.exp(-0.8 * t / 1.0 - 0.2 * t / 2.0)
    problem = DiscoveryProblem(
        idea="Ridge", target=Variable("x", "m", tuple(y)),
        inputs=(Variable("t", "s", tuple(t)),),
        constants=(Constant("tau1", 1.0, "s"), Constant("tau2", 2.0, "s")))
    law = discover_additive_argument(problem, **_FAST)
    assert law.verdict == "unentschieden"
    assert law.occam_winner == "einzel_transzendent"


def test_sign_ambiguity_of_the_sine_argument_is_canonicalised():
    """Wächter (c)-Analogon: −C·sin(−α·π1 − β·π2 + φ) has a canonical twin. The negated
    two-scale chirp −3·sin(1.5·x + 0.8·√x + 0.4) comes back with C > 0, leading coefficient
    α > 0 and the sign absorbed into the wrapped phase — one parameterisation per law."""
    y = -_chirp(_T_IRREG)
    law = discover_additive_argument(_problem(_T_IRREG, y, "Chirp negiert"), **_FAST)
    assert law.form_name == "sin"
    assert law.r_squared > 0.999
    assert law.params["C"] > 0.0
    assert law.params["alpha"] > 0.0
    assert 0.0 <= law.params["phi"] < 2.0 * math.pi
    # the canonical parameters reproduce the data exactly (same law, one representation)
    x = _T_IRREG
    pi1 = x ** law.group_f["t"]
    pi2 = x ** law.group_g["t"]
    pred = (law.params["C"] * np.sin(law.params["alpha"] * pi1 + law.params["beta"] * pi2
                                     + law.params["phi"]) + law.params["D"])
    assert np.allclose(pred, y, atol=1e-6)


def test_noise_is_never_promoted_to_an_additive_argument_law():
    """Pure noise clears no 0.999 bar in the additive-argument family — verdict widerlegt
    (anti-hallucination, δ-asymmetry)."""
    rng = np.random.default_rng(11)
    t = np.array([0.5, 0.8, 1.2, 1.5, 1.9, 2.3, 2.6, 3.0, 3.3, 3.7, 3.9, 4.0])
    y = rng.uniform(0.5, 1.5, size=12)
    law = discover_additive_argument(_problem(t, y, "Rauschen"), **_FAST)
    assert law.verdict == "widerlegt"
    assert law.r_squared < 0.999


def test_additive_law_generalises_out_of_sample():
    """6.2 seam: the law discovered on a train split — form, π-pair AND parameters — transfers
    UNCHANGED (no refit) to the held-out split."""
    val = additive_argument_out_of_sample_validate(
        _problem(_T_IRREG, _two_scale_exp(_T_IRREG)), **_FAST)
    assert val.generalises
    assert val.test_r2 > 0.999
    assert abs(val.overfit_gap) < 1e-6


def test_chirp_is_rediscovered_and_beats_every_rival():
    """The winnable single-input case: the chirp 3·sin(1.5·x + 0.8·√x + 0.4) — one sinusoid, a
    frequency-drifting additive argument. No rival family follows a global chirp (single-π sine:
    fixed frequency; π-pair products: beat notes, not one drifting tone) → bestätigt with the
    exact canonical coefficients and OOS confirmation."""
    law = discover_additive_argument(_problem(_T_IRREG, _chirp(_T_IRREG), "Chirp"), **_FAST)
    assert law.verdict == "bestaetigt"
    assert law.form_name == "sin"
    assert law.powerlaw_r2 < 0.999
    assert law.single_r2 < 0.999
    assert law.product_power_r2 < 0.999
    assert law.blind_r2 < 0.999
    assert law.oos_confirm_r2 > 0.99
    assert abs(law.params["C"] - 3.0) < 1e-6
    assert abs(law.params["D"]) < 1e-6
    assert abs(law.params["phi"] - _CHIRP_PHI) < 1e-6
    assert abs(_coefficient_of(law, {"t": 1.0, "tau": -1.0}) - _CHIRP_ALPHA) < 1e-6
    assert abs(_coefficient_of(law, {"t": 0.5, "tau": -0.5}) - _CHIRP_BETA) < 1e-6


def test_flip_narrow_band_tie_is_resolved_by_active_measurement():
    """6.4 seam (DER Flip-Test): on a narrow band (< one period) the chirp and a fixed-frequency
    sinusoid are indistinguishable → unentschieden. discover_additive_argument_rivals hands the
    additive fit plus the STRONGEST simpler evaluable rival to propose_resolution; measuring the
    TRUE values at the discriminating spread flips the verdict to bestätigt with the exact
    coefficients — every simpler rival collapses on the new regime."""
    t_narrow = np.linspace(0.8, 2.0, 8)
    narrow = _problem(t_narrow, _chirp(t_narrow), "Chirp schmal")
    tied = discover_additive_argument(narrow, **_FAST)
    assert tied.verdict == "unentschieden"
    assert tied.occam_winner != ""            # a simpler family ties on the narrow band

    additive_rival, simpler_rival = discover_additive_argument_rivals(narrow, **_FAST)
    assert additive_rival is not None and simpler_rival is not None
    assert simpler_rival.r_squared > 0.999    # the hand-off rival really is tied
    spec = propose_resolution(additive_rival, simpler_rival, narrow)
    assert spec.discriminating
    assert all(m > 0.0 for m in spec.measure_at)

    t_aug = np.concatenate([t_narrow, np.asarray(spec.measure_at)])
    flipped = discover_additive_argument(_problem(t_aug, _chirp(t_aug), "Chirp erweitert"), **_FAST)
    assert flipped.verdict == "bestaetigt"
    assert flipped.single_r2 < 0.999
    assert flipped.blind_r2 < 0.999
    assert abs(_coefficient_of(flipped, {"t": 1.0, "tau": -1.0}) - _CHIRP_ALPHA) < 1e-6
    assert abs(_coefficient_of(flipped, {"t": 0.5, "tau": -0.5}) - _CHIRP_BETA) < 1e-6


def test_kepler_has_no_dimensionless_pair_so_no_additive_claim():
    """(a, μ) admit no dimensionless group at all → no π-pair, honest widerlegt with the explicit
    diagnosis; the unfitted law refuses evaluation loudly."""
    mu = 1.32712440018e20
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11, 1.434e12])
    big_t = 2.0 * math.pi * a**1.5 / math.sqrt(mu)
    problem = DiscoveryProblem(
        idea="Kepler", target=Variable("T", "s", tuple(big_t)),
        inputs=(Variable("a", "m", tuple(a)),),
        constants=(Constant("mu", mu, "m^3/s^2"),))
    law = discover_additive_argument(problem)
    assert law.verdict == "widerlegt"
    assert "kein dimensionsloses Argument" in law.expression
    with pytest.raises(ValueError):
        evaluate_additive_rival(law, problem)


def test_rejects_non_positive_source_magnitudes():
    """π-groups need positive magnitudes; a non-positive input is a hard ValueError."""
    bad = DiscoveryProblem(
        idea="kaputt", target=Variable("x", "m", (1.0, 2.0, 3.0, 4.0)),
        inputs=(Variable("t", "s", (1.0, -2.0, 3.0, 4.0)),),
        constants=(Constant("tau", 1.0, "s"),))
    with pytest.raises(ValueError):
        discover_additive_argument(bad)
