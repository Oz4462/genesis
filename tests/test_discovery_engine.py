"""Discovery engine — dimensional symbolic regression + discover_new_formulas (Phase 1 DoD).

The headline test is the honest capability proof from the build doc (Phase 4): can the
engine REDISCOVER Kepler's third law T = 2π·a^(3/2)·mu^(-1/2) from data alone? Plus the
red-team (a dimensionally impossible target must be 'widerlegt') and fail-loud inputs.
"""

import math

import numpy as np
import pytest

from gen.discovery import (
    Variable, Constant, DiscoveryProblem,
    symbolic_regress, discover_new_formulas, dimensional_power_law,
)
from gen.verification.units import parse_unit

MU_SUN = 1.32712440018e20  # m^3/s^2, G*M_sun


def _kepler_problem():
    # semi-major axes (m), Mercury..Jupiter, and the exact Kepler period for each
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11, 1.434e12])
    T = 2.0 * math.pi * a ** 1.5 / math.sqrt(MU_SUN)
    return DiscoveryProblem(
        idea="Wie hängt die Umlaufzeit eines Planeten von seiner Bahngröße ab?",
        target=Variable(name="T", unit="s", values=tuple(T)),
        inputs=(Variable(name="a", unit="m", values=tuple(a)),),
        constants=(Constant(name="mu", value=MU_SUN, unit="m^3/s^2"),),
        run_id="kepler-001",
    )


def test_dimensional_power_law_nails_keplers_exponents():
    """Tracer: the Buckingham-π solve alone fixes a^(3/2)·mu^(-1/2) — before any fitting."""
    exps, residual = dimensional_power_law(
        parse_unit("s"), ["a", "mu"], [parse_unit("m"), parse_unit("m^3/s^2")])
    assert residual < 1e-9
    assert abs(exps["a"] - 1.5) < 1e-6
    assert abs(exps["mu"] + 0.5) < 1e-6


def test_rediscovers_keplers_third_law_end_to_end():
    """The full loop recovers the law AND the constant 2π, and judges it 'bestaetigt'."""
    result = discover_new_formulas(_kepler_problem())
    assert result.validated, "Kepler should be rediscovered and validated"
    best = result.validated[0]
    assert best.verdict == "bestaetigt" and best.passed
    assert abs(best.candidate.exponents["a"] - 1.5) < 1e-3
    assert abs(best.candidate.exponents["mu"] + 0.5) < 1e-3
    assert abs(best.candidate.coefficient - 2.0 * math.pi) / (2.0 * math.pi) < 1e-3
    assert best.candidate.r_squared > 0.9999
    assert best.gates["dimensional_check"]["passed"]
    assert best.gates["gate_c6_recompute"]["passed"]


def test_red_team_dimensionally_impossible_target_is_widerlegt():
    """A target dimension that CANNOT be formed from the inputs must be rejected by the
    dimensional gate — not fitted into a fake discovery (hohe Verwerfungsrate = Erfolg)."""
    a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    problem = DiscoveryProblem(
        idea="Erfinde eine Temperatur aus einer Länge und einer Zeit (unmöglich).",
        target=Variable(name="Temp", unit="K", values=tuple(2.0 * a)),
        inputs=(Variable(name="a", unit="m", values=tuple(a)),
                Variable(name="t", unit="s", values=tuple(a))),
        run_id="redteam-001",
    )
    result = discover_new_formulas(problem)
    assert result.validated == ()                         # nothing passes
    assert all(r.verdict == "widerlegt" for r in result.all_records)
    assert all(not r.candidate.dimension_ok for r in result.all_records)


def test_every_candidate_kept_and_rejected_is_recorded():
    """Rejection is information: all_records carries every candidate for the Discovery Graph."""
    result = discover_new_formulas(_kepler_problem())
    assert len(result.all_records) >= 1
    assert result.problem_idea.startswith("Wie hängt")


def test_fails_loud_on_nonpositive_and_mismatched_data():
    """No fabricated candidate on bad data: non-positive magnitudes and length mismatch raise."""
    with pytest.raises(ValueError):
        symbolic_regress(DiscoveryProblem(
            idea="x", target=Variable("y", "s", (1.0, -2.0, 3.0)),
            inputs=(Variable("a", "m", (1.0, 2.0, 3.0)),)))
    with pytest.raises(ValueError):
        symbolic_regress(DiscoveryProblem(
            idea="x", target=Variable("y", "s", (1.0, 2.0, 3.0)),
            inputs=(Variable("a", "m", (1.0, 2.0)),)))


def test_discovery_is_deterministic():
    """Identical inputs give an identical verdict (reproducibility, Kernprinzip 5)."""
    a = discover_new_formulas(_kepler_problem()).validated[0]
    b = discover_new_formulas(_kepler_problem()).validated[0]
    assert a.candidate.expression == b.candidate.expression
    assert a.candidate.coefficient == b.candidate.coefficient
