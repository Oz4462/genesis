"""Depth audit of discovery/engine.py — does the dimensional-SR claim REALLY hold?

This is not a smoke test. Each test attacks the engine's headline anti-hallucination claim
(CLAUDE.md §1/§4, build doc Anhang B) and would FAIL if the claim were a facade:

  * The power-law EXPONENTS come from the Buckingham-π linear DIMENSIONAL solve ALONE — not
    from fitting the data. Proof: the exponents are invariant under arbitrary rescaling of the
    target data (only the constant C absorbs the scale). A fit-driven engine could not have
    this invariance.
  * The fitted constant C is the ONLY free parameter, and for Kepler it is 2π — recovered, not
    assumed.
  * The three verdicts are genuinely computed, not hardcoded: a dimensionally unreachable
    target is ``widerlegt``; a clean power law clearing the δ-raised bar is ``bestaetigt``; a
    dimension-ok but additively-contaminated fit is ``unentschieden``.
  * gate_c6 RECOMPUTE re-evaluates the fitted formula per data point (it FAILS on the
    additive case and PASSES on the clean one — it is not a constant True).
  * The FIT gate threshold RISES with candidate complexity (δ-asymmetry) and FALLS when an
    expected known law is supplied (a lower evidence bar) — both directions, exposed in the
    gate detail.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gen.discovery.engine import (
    DEFAULT_R2_THRESHOLD,
    DIMENSION_TOLERANCE,
    Constant,
    DiscoveryProblem,
    Variable,
    dimensional_power_law,
    discover_new_formulas,
    symbolic_regress,
)
from gen.verification.units import parse_unit

MU_SUN = 1.32712440018e20  # m^3/s^2, the Sun's gravitational parameter G*M_sun

# Mercury..Jupiter semi-major axes (m); exact Kepler periods follow the closed form below.
_KEPLER_A = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11, 1.434e12])


def _kepler_problem(constant: float = 2.0 * math.pi) -> DiscoveryProblem:
    """Kepler III with a tunable leading constant so we can prove the exponents do NOT
    depend on the data's magnitude (only ``C`` does). ``constant=2π`` is the real law."""
    T = constant * _KEPLER_A ** 1.5 / math.sqrt(MU_SUN)
    return DiscoveryProblem(
        idea="Umlaufzeit vs. Bahngröße (Kepler).",
        target=Variable("T", "s", tuple(T)),
        inputs=(Variable("a", "m", tuple(_KEPLER_A)),),
        constants=(Constant("mu", MU_SUN, "m^3/s^2"),),
        run_id="kepler-audit",
    )


def _ideal_gas_problem() -> DiscoveryProblem:
    """Ideal gas P = R·n·T·V^-1 — a complexity-4 power law (vs Kepler's 2) for the δ-asymmetry."""
    R = 8.314462618
    n = np.array([1.0, 2.0, 1.0, 3.0, 2.0, 1.5])
    temp = np.array([273.0, 300.0, 350.0, 280.0, 320.0, 310.0])
    vol = np.array([0.0224, 0.05, 0.03, 0.08, 0.04, 0.06])
    P = R * n * temp / vol
    return DiscoveryProblem(
        idea="Druck eines idealen Gases.",
        target=Variable("P", "Pa", tuple(P)),
        inputs=(Variable("n", "mol", tuple(n)),
                Variable("temp", "K", tuple(temp)),
                Variable("V", "m^3", tuple(vol))),
        constants=(Constant("R", R, "J/mol/K"),),
        run_id="gas-audit",
    )


# --------------------------------------------------------------------------------------
# Claim 1: the dimensional (Buckingham-π) constraint ALONE fixes the exponents.
# --------------------------------------------------------------------------------------

def test_dimensional_solve_fixes_exponents_without_any_data():
    """``dimensional_power_law`` takes ONLY dimensions — no samples — yet pins a^(3/2)·mu^(-1/2).

    This is the structural proof: the function signature cannot see the data, so the
    exponents are a property of the dimensions, full stop. Residual ≈ 0 means the target
    dimension is exactly reachable."""
    exps, residual = dimensional_power_law(
        parse_unit("s"), ["a", "mu"], [parse_unit("m"), parse_unit("m^3/s^2")])
    assert residual < DIMENSION_TOLERANCE
    assert exps["a"] == pytest.approx(1.5, abs=1e-9)
    assert exps["mu"] == pytest.approx(-0.5, abs=1e-9)


def test_exponents_are_invariant_under_target_rescaling_only_constant_moves():
    """The facade-killer for "exponents come from the fit": rescale the target data by ×1000
    and the exponents MUST be byte-identical while the constant C scales by exactly 1000.

    A fit that derived exponents from the data could not satisfy this — the dimensional solve
    can, because it never looks at the values."""
    base = symbolic_regress(_kepler_problem(constant=2.0 * math.pi))[0]
    scaled = symbolic_regress(_kepler_problem(constant=2000.0 * math.pi))[0]  # C×1000

    assert base.exponents["a"] == pytest.approx(scaled.exponents["a"], abs=1e-12)
    assert base.exponents["mu"] == pytest.approx(scaled.exponents["mu"], abs=1e-12)
    # only the constant absorbs the rescaling, proportionally
    assert scaled.coefficient == pytest.approx(base.coefficient * 1000.0, rel=1e-9)
    # the fit quality is unchanged — same shape, different constant
    assert scaled.r_squared == pytest.approx(base.r_squared, abs=1e-12)


def test_fitted_constant_is_two_pi_recovered_not_assumed():
    """For the real Kepler data the single free parameter C is 2π — and the exponents are the
    exact half-integers the dimensions demand."""
    best = symbolic_regress(_kepler_problem())[0]
    assert best.exponents["a"] == pytest.approx(1.5, abs=1e-9)
    assert best.exponents["mu"] == pytest.approx(-0.5, abs=1e-9)
    assert best.coefficient == pytest.approx(2.0 * math.pi, rel=1e-9)
    assert best.r_squared == pytest.approx(1.0, abs=1e-9)
    assert best.dimension_ok is True


@settings(max_examples=40, deadline=None)
@given(scale=st.floats(min_value=1e-6, max_value=1e6, allow_nan=False, allow_infinity=False))
def test_property_rescaling_invariance(scale: float):
    """PROPERTY (invariant): for ANY positive scale, the dimensionally-fixed exponents are
    unchanged and the constant tracks the scale linearly. Explores the input space the two
    hand-picked examples above only sample."""
    base = symbolic_regress(_kepler_problem(constant=2.0 * math.pi))[0]
    scaled = symbolic_regress(_kepler_problem(constant=2.0 * math.pi * scale))[0]
    assert scaled.exponents["a"] == pytest.approx(base.exponents["a"], abs=1e-9)
    assert scaled.exponents["mu"] == pytest.approx(base.exponents["mu"], abs=1e-9)
    assert scaled.coefficient == pytest.approx(base.coefficient * scale, rel=1e-6)


# --------------------------------------------------------------------------------------
# Claim 2: the three honest verdicts are REAL, not hardcoded.
# --------------------------------------------------------------------------------------

def test_bestaetigt_for_clean_power_law():
    """A dimension-ok candidate clearing the δ-raised R² bar → ``bestaetigt`` (and it passed
    every gate)."""
    result = discover_new_formulas(_kepler_problem())
    assert result.validated, "clean Kepler must produce at least one validated verdict"
    best = result.validated[0]
    assert best.verdict == "bestaetigt"
    assert best.passed is True
    assert best.gates["dimensional_check"]["passed"] is True
    assert best.gates["fit"]["passed"] is True
    assert best.gates["gate_c6_recompute"]["passed"] is True


def test_widerlegt_for_dimensionally_impossible_target():
    """A temperature target that NO product of a length and a time can form → ``widerlegt``.

    This is the red-team negative: the dimensional residual is non-zero, so the engine refuses
    rather than fabricate a fit."""
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    problem = DiscoveryProblem(
        idea="Temperatur aus Länge und Zeit — dimensional unmöglich.",
        target=Variable("Theta", "K", tuple(2.0 * x)),
        inputs=(Variable("a", "m", tuple(x)), Variable("t", "s", tuple(x))),
        run_id="impossible-audit",
    )
    result = discover_new_formulas(problem)
    assert not result.validated  # nothing may pass
    record = result.all_records[0]
    assert record.verdict == "widerlegt"
    assert record.candidate.dimension_ok is False
    assert record.candidate.dimension_residual > DIMENSION_TOLERANCE
    assert record.gates["dimensional_check"]["passed"] is False


def test_unentschieden_for_dimension_ok_but_additively_contaminated_fit():
    """v = g·t + v0: the dimension IS reachable (g·t is m/s) but the additive v0 is something
    a pure power law cannot represent, so the FIT/recompute gates fail → ``unentschieden`` —
    an honest "I don't know", never a false ``bestaetigt``."""
    g = 9.80665
    t = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    v = g * t + 40.0  # large additive offset, dimensionally invisible
    problem = DiscoveryProblem(
        idea="Geschwindigkeit im freien Fall mit Anfangsgeschwindigkeit.",
        target=Variable("v", "m/s", tuple(v)),
        inputs=(Variable("t", "s", tuple(t)),),
        constants=(Constant("g", g, "m/s^2"),),
        run_id="offset-audit",
    )
    result = discover_new_formulas(problem)
    assert not result.validated
    record = result.all_records[0]
    assert record.verdict == "unentschieden"
    assert record.candidate.dimension_ok is True          # dimension is fine...
    assert record.gates["fit"]["passed"] is False          # ...but the fit is not


# --------------------------------------------------------------------------------------
# Claim 3: gate_c6 RECOMPUTE independently re-evaluates the fitted formula per point.
# --------------------------------------------------------------------------------------

def test_gate_c6_recompute_is_real_not_constant_true():
    """The recompute gate must DISCRIMINATE: pass (≈0 per-point error) on the exact Kepler
    formula, fail (large per-point error) on the additive-offset data. A hardcoded ``True``
    would pass both — this asserts it does not."""
    clean = discover_new_formulas(_kepler_problem()).all_records[0]
    assert clean.gates["gate_c6_recompute"]["passed"] is True
    assert clean.gates["gate_c6_recompute"]["max_rel_err"] < 1e-6

    g = 9.80665
    t = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    contaminated = DiscoveryProblem(
        idea="freier Fall mit Offset.",
        target=Variable("v", "m/s", tuple(g * t + 40.0)),
        inputs=(Variable("t", "s", tuple(t)),),
        constants=(Constant("g", g, "m/s^2"),),
    )
    rec = discover_new_formulas(contaminated).all_records[0]
    assert rec.gates["gate_c6_recompute"]["passed"] is False
    # the offset induces a genuinely large per-point relative error the recompute catches
    assert rec.gates["gate_c6_recompute"]["max_rel_err"] > 1e-3


# --------------------------------------------------------------------------------------
# Claim 4: the FIT gate threshold rises with complexity (δ-asymmetry), falls with priors.
# --------------------------------------------------------------------------------------

def test_fit_threshold_rises_with_candidate_complexity():
    """δ-asymmetry: a more complex (higher-δ) law must clear a STRICTER R² bar. The ideal-gas
    law (complexity 4) must therefore carry a higher fit threshold than Kepler (complexity 2)."""
    kepler = discover_new_formulas(_kepler_problem()).all_records[0]
    gas = discover_new_formulas(_ideal_gas_problem()).all_records[0]

    assert gas.candidate.complexity > kepler.candidate.complexity
    assert gas.gates["fit"]["threshold"] > kepler.gates["fit"]["threshold"]
    # both thresholds are at or above the base bar (the δ term only ever RAISES it)
    assert kepler.gates["fit"]["threshold"] >= DEFAULT_R2_THRESHOLD


def test_known_law_prior_lowers_the_evidence_bar():
    """The other arm of the δ-asymmetry: supplying the EXPECTED Kepler signature drives δ→0,
    so the fit threshold drops to the base bar — an expected rediscovery is judged less
    harshly than a novel claim of the same complexity."""
    novel = discover_new_formulas(_kepler_problem()).all_records[0]
    expected = discover_new_formulas(
        _kepler_problem(), known_laws={"kepler": {"a": 1.5, "mu": -0.5}}).all_records[0]

    assert expected.gates["fit"]["threshold"] == pytest.approx(DEFAULT_R2_THRESHOLD, abs=1e-12)
    assert novel.gates["fit"]["threshold"] > expected.gates["fit"]["threshold"]
    assert expected.delta_to_consensus == pytest.approx(0.0, abs=1e-12)


# --------------------------------------------------------------------------------------
# Negative PROPERTY: a target carrying a base dimension absent from the inputs is unreachable.
# --------------------------------------------------------------------------------------

@settings(max_examples=25, deadline=None)
@given(foreign=st.sampled_from(["K", "A", "mol", "cd", "s*K", "m*A"]))
def test_property_foreign_base_dimension_is_unreachable(foreign: str):
    """PROPERTY (negative): if the target's dimension introduces a base symbol that the inputs
    (a:m, mu:m^3/s^2) cannot supply, the Buckingham-π residual MUST exceed tolerance — the
    engine cannot, and must not, fabricate exponents for it."""
    _, residual = dimensional_power_law(
        parse_unit(foreign), ["a", "mu"], [parse_unit("m"), parse_unit("m^3/s^2")])
    assert residual > DIMENSION_TOLERANCE
