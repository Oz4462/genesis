"""Blind two-transcendental product discovery (Frontier 6.7) — ``y = C·f(α·π1)·g(β·π2 [+φ])``
with NO declared baseline (the boundary 6.6 left open: it recovered the damped oscillation only
as a declared-baseline ratio correction). Pins the honest method: the damped oscillation
``4·e^(−0.3t)·cos(2t)`` is rediscovered BLIND to tight tolerance and generalises out-of-sample;
degeneracies collapse honestly (``exp·exp`` → one exponential, a pure cosine → the 6.3-family
single form — never a two-transcendental double-claim); sign/phase ambiguity is canonicalised
(``−cos = cos(·+π)``); noise is never promoted; a narrow-band tie is ``unentschieden`` and flips
via the 6.4 discriminating measurement.
"""

import math

import numpy as np
import pytest

from gen.discovery import (
    BlindProductLaw, Constant, DiscoveryProblem, Variable,
    blind_product_out_of_sample_validate, discover_blind_product, discover_blind_rivals,
    evaluate_blind_rival, propose_resolution,
)

#: Irregular sampling — on an evenly spaced grid a sinusoidal factor is identified only up to
#: aliasing (documented data caveat, as in 6.6); irregular points pin the frequency uniquely.
_T_IRREG = np.array([0.2, 0.5, 0.9, 1.3, 1.8, 2.2, 2.7, 3.1, 3.6, 4.0, 4.3, 4.9, 5.3, 5.8, 6.1])
_ZETA, _OMEGA, _AMP = 0.3, 2.0, 4.0

#: Reduced π-lattice (as in the 6.6 tests): the groups (t/τ)^{±0.5, ±1} fully contain the true
#: law's arguments (both are t/τ), so nothing about the claim weakens — only the pair count and
#: with it the curve_fit budget shrinks. A full default-lattice run reproduces the identical law
#: (measured while building; it merely triples the runtime of an already-exact rediscovery).
_FAST = {"max_abs_exp": 1.0}


def _damped(t: np.ndarray) -> np.ndarray:
    """x(t) = A·e^(−ζt)·cos(ωt) — the classic product of two transcendentals, blind here."""
    return _AMP * np.exp(-_ZETA * t) * np.cos(_OMEGA * t)


def _problem(t: np.ndarray, y: np.ndarray, idea: str = "Gedämpfte Schwingung") -> DiscoveryProblem:
    return DiscoveryProblem(
        idea=idea, target=Variable("x", "m", tuple(y)),
        inputs=(Variable("t", "s", tuple(t)),),
        constants=(Constant("tau", 1.0, "s"),))


def test_damped_oscillation_is_rediscovered_blind():
    """DER Akzeptanztest: x = 4·e^(−0.3t)·cos(2t) is discovered BLIND — no baseline declared —
    as the exp_sin pair with the exact parameters: C = 4, ζ = 0.3, ω = 2, φ = π/2 (canonical:
    cos = sin(·+π/2)). All three rivals (power law with offset, single transcendental with
    phase+offset, 6.6 power×transcendental) stay below the bar, and the train-refitted winner
    transfers out-of-sample — verdict bestätigt."""
    law = discover_blind_product(_problem(_T_IRREG, _damped(_T_IRREG)), **_FAST)
    assert isinstance(law, BlindProductLaw)
    assert law.verdict == "bestaetigt"
    assert law.pair_name == "exp_sin"
    assert law.r_squared > 0.999
    assert law.powerlaw_r2 < 0.999
    assert law.single_r2 < 0.999
    assert law.product_power_r2 < 0.999
    assert law.oos_confirm_r2 > 0.99          # the in-sample win transferred to held-out points
    # exact parameter recovery (τ = 1 s, so both π-groups must be t/τ to the first power)
    assert abs(law.group_f.get("t", 0.0) - 1.0) < 1e-9
    assert abs(law.group_g.get("t", 0.0) - 1.0) < 1e-9
    assert abs(law.params["C"] - _AMP) < 1e-6
    assert abs(law.params["alpha"] + _ZETA) < 1e-6
    assert abs(law.params["beta"] - _OMEGA) < 1e-6
    assert abs(law.params["phi"] - math.pi / 2.0) < 1e-6


def test_sign_ambiguity_is_canonicalised():
    """Guard (c): −cos = cos(·+π). The negated target −4·e^(−0.3t)·cos(2t) is recovered with a
    POSITIVE canonical amplitude and the sign absorbed into the phase (φ = 3π/2), frequency
    positive, phase wrapped to [0, 2π) — one parameterisation per law, no duplicate claims."""
    law = discover_blind_product(_problem(_T_IRREG, -_damped(_T_IRREG)), **_FAST)
    assert law.verdict == "bestaetigt"
    assert law.pair_name == "exp_sin"
    assert law.params["C"] > 0.0
    assert abs(law.params["C"] - _AMP) < 1e-6
    assert law.params["beta"] > 0.0
    assert 0.0 <= law.params["phi"] < 2.0 * math.pi
    assert abs(law.params["phi"] - 3.0 * math.pi / 2.0) < 1e-6


def test_exp_times_exp_collapses_to_a_single_exponential():
    """Guard (a): y = 5·e^(−0.3t)·e^(−0.4t) IS 5·e^(−0.7t) — one exponential. exp·exp is not in
    the pair library (exp(u)·exp(v) = exp(u+v), a parameter ridge, not a law), and the single-
    transcendental rival is exact → the Occam ladder collapses the claim: never bestätigt as a
    two-transcendental product."""
    t = _T_IRREG + 0.1
    law = discover_blind_product(_problem(t, 5.0 * np.exp(-0.7 * t), "exp*exp"), **_FAST)
    assert law.verdict != "bestaetigt"
    assert law.occam_winner == "einzel_transzendent"
    assert law.single_r2 > 0.999


def test_pure_cosine_collapses_to_the_single_transcendental_family():
    """Guard (b): y = 3·cos(2t) is ONE transcendental. The blind exp_sin pair fits it too (flat
    exponential factor), but the single rival — the 6.3 family with phase — is equally exact, so
    the verdict is unentschieden with the collapse named: a 6.3-form, not a 6.7 product claim."""
    law = discover_blind_product(_problem(_T_IRREG, 3.0 * np.cos(2.0 * _T_IRREG), "cos"), **_FAST)
    assert law.verdict == "unentschieden"
    assert law.occam_winner == "einzel_transzendent"
    assert law.single_r2 > 0.999


def test_noise_is_never_promoted_to_a_blind_product():
    """Pure noise clears no 0.999 bar in the blind pair family — verdict widerlegt (anti-
    hallucination, δ-asymmetry): out of noise, NO two-transcendental law is ever 'discovered'."""
    rng = np.random.default_rng(7)
    t = np.array([0.5, 0.8, 1.2, 1.5, 1.9, 2.3, 2.6, 3.0, 3.3, 3.7, 3.9, 4.0])
    y = rng.uniform(0.5, 1.5, size=12)
    law = discover_blind_product(_problem(t, y, "Rauschen"), **_FAST)
    assert law.verdict == "widerlegt"
    assert law.r_squared < 0.999


def test_blind_law_generalises_out_of_sample():
    """6.2 seam: the blind law discovered on a train split — pair form, π-pair AND parameters —
    transfers UNCHANGED (no refit) to the held-out split. A real two-transcendental law
    generalises."""
    val = blind_product_out_of_sample_validate(_problem(_T_IRREG, _damped(_T_IRREG)), **_FAST)
    assert val.generalises
    assert val.test_r2 > 0.999
    assert abs(val.overfit_gap) < 1e-6


def test_flip_narrow_band_tie_is_resolved_by_active_measurement():
    """6.4 seam (DER Flip-Test): on a narrow band (< one period, mild decay) the blind law and
    the simpler families are indistinguishable → unentschieden. discover_blind_rivals hands the
    blind fit plus the STRONGEST simpler evaluable rival to propose_resolution, which computes a
    discriminating spread; measuring the TRUE values there flips the verdict to bestätigt with
    the exact parameters — every simpler rival collapses on the new regime."""
    t_narrow = np.linspace(0.8, 2.0, 8)
    narrow = _problem(t_narrow, _damped(t_narrow))
    tied = discover_blind_product(narrow, **_FAST)
    assert tied.verdict == "unentschieden"
    assert tied.occam_winner != ""            # a simpler family ties on the narrow band

    blind_rival, simpler_rival = discover_blind_rivals(narrow, **_FAST)
    assert blind_rival is not None and simpler_rival is not None
    assert simpler_rival.r_squared > 0.999    # the hand-off rival really is tied
    spec = propose_resolution(blind_rival, simpler_rival, narrow)
    assert spec.discriminating
    assert all(m > 0.0 for m in spec.measure_at)

    t_aug = np.concatenate([t_narrow, np.asarray(spec.measure_at)])
    flipped = discover_blind_product(_problem(t_aug, _damped(t_aug)), **_FAST)
    assert flipped.verdict == "bestaetigt"
    assert flipped.powerlaw_r2 < 0.999
    assert flipped.single_r2 < 0.999
    assert flipped.product_power_r2 < 0.999
    assert abs(flipped.params["alpha"] + _ZETA) < 1e-6
    assert abs(flipped.params["beta"] - _OMEGA) < 1e-6


def test_kepler_has_no_dimensionless_pair_so_no_blind_claim():
    """(a, μ) admit no dimensionless group at all → no π-pair, honest widerlegt with the
    explicit diagnosis; the unfitted law refuses evaluation loudly."""
    mu = 1.32712440018e20
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11, 1.434e12])
    big_t = 2.0 * math.pi * a**1.5 / math.sqrt(mu)
    problem = DiscoveryProblem(
        idea="Kepler", target=Variable("T", "s", tuple(big_t)),
        inputs=(Variable("a", "m", tuple(a)),),
        constants=(Constant("mu", mu, "m^3/s^2"),))
    law = discover_blind_product(problem)
    assert law.verdict == "widerlegt"
    assert "kein dimensionsloses Argument" in law.expression
    with pytest.raises(ValueError):
        evaluate_blind_rival(law, problem)


def test_rejects_non_positive_source_magnitudes():
    """π-groups need positive magnitudes; a non-positive input is a hard ValueError."""
    bad = DiscoveryProblem(
        idea="kaputt", target=Variable("x", "m", (1.0, 2.0, 3.0, 4.0)),
        inputs=(Variable("t", "s", (1.0, -2.0, 3.0, 4.0)),),
        constants=(Constant("tau", 1.0, "s"),))
    with pytest.raises(ValueError):
        discover_blind_product(bad)
