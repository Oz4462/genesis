"""Characterization test: the Rediscovery benchmark is HONEST, not rigged.

Audit target — ``gen.discovery.benchmark.rediscovery_benchmark`` claims ~100% rediscovery of
textbook laws. This file proves that headline is earned, not a facade, by pinning four
falsifiable properties of the dimensional symbolic-regression engine:

  1. THE ANSWER IS NEVER HANDED IN. Each textbook ``BenchmarkCase`` carries ``known_laws=None``,
     so ``_run_case`` feeds NOTHING about the expected exponents into ``discover_new_formulas``.
     ``expected_exponents`` is consumed ONLY by the post-hoc ``_exponents_match`` check. We spy on
     the real ``discover_new_formulas`` call and assert the expected signature is never an argument.
  2. RECOVERY IS DATA-SAMPLE-INVARIANT (held-out / perturbed data). The same physical law,
     reconstructed from a DIFFERENT set of points — and from a NOISIER sample — still yields the
     textbook exponents within tolerance. Because the exponents come from the Buckingham-π
     dimensional solve (not from memorising the six demo points), they are robust to which points
     you sample and to measurement noise. (cf. AI-Feynman: dimensional analysis fixes the form.)
  3. THE SUCCESS CHECK IS NOT TRIVIALLY SATISFIABLE (negative control). Data that is dimensionally
     valid but does NOT obey the law (T ∝ a^1.8 instead of a^1.5) is NOT rediscovered: the fit gate
     keeps the verdict ``unentschieden`` even though the dimensional exponents still read 1.5/-0.5.
     Matching exponents alone is therefore insufficient — a real fit gate must also pass.
  4. THE IMPOSSIBLE RED-TEAM IS REJECTED. A target whose dimension cannot be formed from the inputs
     is ``widerlegt`` (a definite negative), never silently confirmed.

AUDIT VERDICT: REAL. The answer is not leaked and success requires a validated ``bestaetigt`` whose
exponents match — so ``benchmark.py`` needs NO source change. These tests are the standing proof.
Deterministic: fixed numpy seeds and Hypothesis ``derandomize=True``.
"""

from __future__ import annotations

import math

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from gen.discovery import benchmark as bench
from gen.discovery.benchmark import (
    EXPONENT_MATCH_TOLERANCE,
    ideal_gas_case,
    kepler_case,
    newton_gravity_case,
    redteam_impossible_case,
    rediscovery_benchmark,
)
from gen.discovery.engine import (
    Constant,
    DiscoveryProblem,
    Variable,
    discover_new_formulas,
)

#: Standard gravitational parameter of the Sun [m^3/s^2] — the Kepler constant used everywhere here.
MU_SUN = 1.32712440018e20

#: A semi-major-axis sample DISJOINT from the demo planets in ``kepler_case`` — proves recovery is
#: not tied to the six built-in points.
HELD_OUT_A = (4.0e10, 8.0e10, 2.0e11, 5.0e11, 9.0e11, 1.6e12, 3.0e12)


def _kepler_problem(a_values, *, noise: float = 0.0, seed: int = 0) -> DiscoveryProblem:
    """A fresh Kepler problem T = 2π·a^(3/2)·mu^(-1/2) over the given semi-major axes.

    ``noise`` adds deterministic multiplicative Gaussian scatter to the target (a noisier sample);
    the inputs/constants keep their textbook units so the dimensional solve is identical regardless
    of the data — that invariance is exactly what these tests probe.
    """
    a = np.asarray(a_values, dtype=float)
    target = 2.0 * math.pi * a ** 1.5 / math.sqrt(MU_SUN)
    if noise:
        rng = np.random.default_rng(seed)
        target = target * (1.0 + noise * rng.standard_normal(target.shape[0]))
    return DiscoveryProblem(
        idea="Kepler III (held-out sample).",
        target=Variable("T", "s", tuple(target)),
        inputs=(Variable("a", "m", tuple(a)),),
        constants=(Constant("mu", MU_SUN, "m^3/s^2"),),
    )


KEPLER_EXPONENTS = {"a": 1.5, "mu": -0.5}


# --- Property 1: the answer is never handed into discovery --------------------------------------

def test_textbook_cases_carry_no_known_laws():
    """Each real BenchmarkCase keeps ``known_laws=None`` — the only place the textbook signature
    lives is ``expected_exponents`` (the post-hoc match check), never an input to discovery."""
    for case in (kepler_case(), ideal_gas_case(), newton_gravity_case()):
        assert case.known_laws is None, case.name
        assert case.expected_exponents, case.name  # the answer exists, but only for scoring


def test_discovery_is_never_told_the_expected_exponents(monkeypatch):
    """Spy on the real ``discover_new_formulas`` while the benchmark runs: prove the expected
    exponent signature is NEVER passed in (neither as ``known_laws`` nor positionally). If the
    benchmark leaked the answer, this is where it would show up."""
    seen_known_laws: list[object] = []
    real = bench.discover_new_formulas

    def spy(problem, *args, **kwargs):
        seen_known_laws.append(kwargs.get("known_laws"))
        # No expected-exponent dict may ride in on any other argument.
        assert KEPLER_EXPONENTS not in args and KEPLER_EXPONENTS not in kwargs.values()
        return real(problem, *args, **kwargs)

    monkeypatch.setattr(bench, "discover_new_formulas", spy)

    cases = [kepler_case(), ideal_gas_case(), newton_gravity_case()]
    report = rediscovery_benchmark(cases)

    assert report.rediscovery_rate == 1.0  # still rediscovered — without ever seeing the answer
    assert len(seen_known_laws) == len(cases)
    assert all(kl is None for kl in seen_known_laws)


# --- Property 2: recovery is data-sample-invariant (held-out + noisy) ---------------------------

def _recovered_exponents(problem: DiscoveryProblem) -> dict[str, float]:
    """The exponents of the engine's best candidate for ``problem`` (known_laws explicitly None)."""
    result = discover_new_formulas(problem, known_laws=None)
    return result.all_records[0].candidate.exponents


def test_rediscovered_from_a_different_sample_of_points():
    """A held-out semi-major-axis sample (none of the six demo planets) is rediscovered: a validated
    'bestaetigt' whose exponents match the textbook law — recovery is not memorisation of the demo."""
    result = discover_new_formulas(_kepler_problem(HELD_OUT_A), known_laws=None)
    assert result.validated, "held-out Kepler not validated"
    best = result.validated[0]
    assert best.verdict == "bestaetigt"
    for name, exp in KEPLER_EXPONENTS.items():
        assert abs(best.candidate.exponents.get(name, 0.0) - exp) < EXPONENT_MATCH_TOLERANCE


def test_exponents_survive_a_noisier_sample():
    """Add deterministic measurement noise to the SAME law: the recovered exponents still match within
    tolerance because the dimensional solve is noise-independent. (The strict recompute/fit gate may
    legitimately downgrade the verdict to 'unentschieden' — that is the gate being honest about
    precision, NOT a relaxation of the success criterion; see the negative control below.)"""
    exps = _recovered_exponents(_kepler_problem(HELD_OUT_A, noise=0.002, seed=7))
    for name, exp in KEPLER_EXPONENTS.items():
        assert abs(exps.get(name, 0.0) - exp) < EXPONENT_MATCH_TOLERANCE, name


# --- Property 3: the success check is not trivially satisfiable (negative control) --------------

def test_data_inconsistent_with_the_law_is_not_rediscovered():
    """Dimensionally VALID but physically WRONG data (T ∝ a^1.8, not a^1.5) must NOT be rediscovered.
    The dimensional exponents still read 1.5/-0.5, yet the fit gate refuses 'bestaetigt' — proving
    matching exponents alone never wins; the data has to actually obey the law."""
    a = np.asarray(HELD_OUT_A, dtype=float)
    # Multiply the true target by a^0.3 to bend the real exponent to 1.8 while staying positive.
    bent = 2.0 * math.pi * a ** 1.5 / math.sqrt(MU_SUN) * (a / np.mean(a)) ** 0.3
    problem = DiscoveryProblem(
        idea="Kepler with a corrupted exponent (negative control).",
        target=Variable("T", "s", tuple(bent)),
        inputs=(Variable("a", "m", tuple(a)),),
        constants=(Constant("mu", MU_SUN, "m^3/s^2"),),
    )
    result = discover_new_formulas(problem, known_laws=None)
    assert result.validated == ()  # nothing confirmed
    best = result.all_records[0]
    assert best.verdict == "unentschieden"          # honest "I don't know", not 'bestaetigt'
    # The dimensional exponents are unchanged — so success cannot have come from exponents alone.
    for name, exp in KEPLER_EXPONENTS.items():
        assert abs(best.candidate.exponents.get(name, 0.0) - exp) < EXPONENT_MATCH_TOLERANCE


def test_impossible_red_team_is_rejected():
    """A target whose dimension no input product can form is 'widerlegt' — a definite negative."""
    result = discover_new_formulas(redteam_impossible_case().problem, known_laws=None)
    assert result.validated == ()
    assert all(r.verdict == "widerlegt" for r in result.all_records)


# --- Property 4 (invariant): dimensional recovery is independent of WHICH points you sample ------

@settings(deadline=None, max_examples=40, derandomize=True)
@given(
    st.lists(
        st.floats(min_value=1.0e9, max_value=1.0e13, allow_nan=False, allow_infinity=False),
        min_size=4,
        max_size=9,
    )
)
def test_kepler_exponents_invariant_to_arbitrary_positive_samples(a_values):
    """PROPERTY: for ANY positive sample of semi-major axes obeying Kepler's law, the engine recovers
    a=3/2, mu=-1/2 — without ever being told the answer. The exponents are a function of the UNITS,
    not of the data points, so no specific sample can be 'memorised'. This is the structural reason
    the ~100% headline is honest rather than overfit."""
    exps = _recovered_exponents(_kepler_problem(a_values))
    assert abs(exps.get("a", 0.0) - 1.5) < EXPONENT_MATCH_TOLERANCE
    assert abs(exps.get("mu", 0.0) + 0.5) < EXPONENT_MATCH_TOLERANCE


# --- determinism (A5 reproducibility) -----------------------------------------------------------

def test_rediscovery_benchmark_is_deterministic():
    """Same inputs → byte-identical report, run after run (no wall-clock / unseeded randomness)."""
    first = rediscovery_benchmark()
    second = rediscovery_benchmark()
    assert first == second
    assert first.rediscovery_rate == 1.0
    assert first.redteam_catch_rate == 1.0
