"""Characterization + honesty tests for ``discovery/benchmark.py``.

The headline claim is ~100 % rediscovery plus a high red-team catch rate. The team honesty
rule (2026-06-23) demands we PROVE that headline is earned by recovering laws *from data*,
not leaked or echoed from the canned answer arrays. Concretely this file proves:

  1. ``known_laws`` is NEVER fed to the engine for the real cases (``case.known_laws is None``)
     and ``expected_exponents`` is used ONLY in the post-hoc ``_exponents_match`` check — so the
     engine cannot see the textbook signature while searching.
  2. HELD-OUT / PERTURBED DATA — a Kepler case rebuilt from a *different* (and a *noisier*) sample
     of the same law is still rediscovered. Recovery survives changing the data, so it comes from
     the data, not from the exact arrays baked into ``kepler_case``.
  3. NEGATIVE CONTROL — a case whose target data is scrambled relative to its ``expected_exponents``
     is NOT reported as rediscovered. Success therefore cannot come from echoing ``expected_exponents``.

All problems are built through the real ``engine.py`` constructors. Offline, deterministic.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.gen.discovery.benchmark import (
    BenchmarkCase,
    _exponents_match,
    _run_case,
    default_cases,
    kepler_case,
    rediscovery_benchmark,
)
from src.gen.discovery.engine import (
    Constant,
    DiscoveryProblem,
    Variable,
    discover_new_formulas,
)

#: Gravitational parameter of the Sun (m^3/s^2) — the constant Kepler's third law is built on.
MU_SUN = 1.32712440018e20
#: The textbook exponent signature of Kepler III: T = 2π · a^(3/2) · mu^(-1/2).
KEPLER_SIGNATURE = {"a": 1.5, "mu": -0.5}


def _kepler_problem(a_values, *, target_values=None, idea: str = "Kepler held-out") -> DiscoveryProblem:
    """A Kepler III discovery problem over arbitrary semi-major axes ``a`` (built via the REAL
    engine constructors). ``target_values=None`` synthesises the exact law T = 2π·a^1.5·mu^-0.5;
    passing ``target_values`` injects a perturbed/scrambled target for the honesty controls."""
    a = np.asarray(a_values, dtype=float)
    if target_values is None:
        target = 2.0 * math.pi * a ** 1.5 / math.sqrt(MU_SUN)
    else:
        target = np.asarray(target_values, dtype=float)
    return DiscoveryProblem(
        idea=idea,
        target=Variable("T", "s", tuple(target)),
        inputs=(Variable("a", "m", tuple(a)),),
        constants=(Constant("mu", MU_SUN, "m^3/s^2"),),
    )


# --- (1) the full benchmark: real laws rediscovered, red-team caught ----------------------

def test_full_benchmark_rates_at_documented_level():
    """Real-law cases are rediscovered and red-team cases caught — the documented headline."""
    report = rediscovery_benchmark()
    # All four textbook laws recovered from data alone.
    assert report.rediscovery_rate == 1.0
    # All false ideas rejected (none falsely validated).
    assert report.redteam_catch_rate == 1.0
    assert report.n_pass == report.n_total


def test_redteam_verdicts_are_honest():
    """The impossible-dimension case is a hard ``widerlegt``; the hidden-additive case must NOT
    be a false ``bestaetigt`` (it lands on the honest ``unentschieden``)."""
    results = {r.name: r for r in rediscovery_benchmark().results}

    impossible = results["Red-team: impossible dimension"]
    assert impossible.verdict == "widerlegt"  # no length+time product forms a temperature
    assert impossible.success  # success for a red-team == correctly rejected

    additive = results["Red-team: hidden additive term"]
    assert additive.verdict != "bestaetigt"  # a pure power law cannot swallow the additive v0
    assert additive.verdict == "unentschieden"
    assert additive.success


# --- the leak guard: the engine never sees the answer signature ---------------------------

def test_known_laws_is_never_fed_to_the_engine():
    """Every real case passes ``known_laws=None`` to ``discover_new_formulas`` — the textbook
    signature lives only in ``expected_exponents``, used post-hoc. This is the structural
    no-leak guarantee."""
    for case in default_cases():
        if not case.is_redteam:
            assert case.known_laws is None
            assert case.expected_exponents is not None


def test_engine_recovers_signature_without_being_told_it():
    """Calling the engine directly with ``known_laws=None`` (exactly as the benchmark does) still
    yields a validated candidate whose exponents match the textbook signature — recovery is the
    engine's own dimensional solve, not a fed answer."""
    case = kepler_case()
    result = discover_new_formulas(case.problem, known_laws=None)
    assert result.validated, "engine validated nothing on exact Kepler data"
    top = result.validated[0]
    assert top.verdict == "bestaetigt"
    assert _exponents_match(top.candidate.exponents, KEPLER_SIGNATURE)


def test_wrong_expected_exponents_blocks_success_proving_posthoc_check():
    """``expected_exponents`` is a genuine post-hoc filter, not an input: feed exact Kepler data
    but a WRONG signature and the case is reported NOT rediscovered, even though the engine itself
    confirmed the (correct) law. Proves the answer array does not drive the search."""
    wrong = BenchmarkCase("Kepler wrong-key", kepler_case().problem, {"a": 2.0, "mu": 1.0})
    res = _run_case(wrong)
    assert res.success is False  # the engine's true a^1.5·mu^-0.5 does not match the wrong signature


# --- (2) held-out / perturbed data: recovery is from data, not the canned arrays -----------

#: A semi-major-axis sample DISJOINT from ``kepler_case``'s baked-in array.
_HELD_OUT_AXES = [4.0e10, 9.0e10, 2.0e11, 5.0e11, 9.0e11, 2.0e12, 3.5e12]


def test_kepler_recovered_from_held_out_sample():
    """Rebuild Kepler from a DIFFERENT set of orbital radii (exact law) — still rediscovered."""
    case = BenchmarkCase("Kepler held-out", _kepler_problem(_HELD_OUT_AXES), KEPLER_SIGNATURE)
    res = _run_case(case)
    assert res.success
    assert res.verdict == "bestaetigt"
    # The recovered candidate carries the textbook exponents, derived from this fresh sample.
    result = discover_new_formulas(case.problem, known_laws=None)
    assert _exponents_match(result.validated[0].candidate.exponents, KEPLER_SIGNATURE)


def test_kepler_recovered_from_noisier_sample():
    """Add small deterministic multiplicative noise to the held-out Kepler target; the law is
    still recovered. Noise that does not follow the law cannot be 'echoed' from an array — only
    a genuine data fit clears the gates."""
    rng = np.random.default_rng(7)  # fixed seed → deterministic noise (research-reproducibility)
    a = np.asarray(_HELD_OUT_AXES, dtype=float)
    exact = 2.0 * math.pi * a ** 1.5 / math.sqrt(MU_SUN)
    # ~5e-5 relative scatter stays inside the recompute gate's 1e-3 relative tolerance.
    noisy = exact * (1.0 + rng.normal(0.0, 5e-5, size=a.shape))
    case = BenchmarkCase("Kepler noisy", _kepler_problem(a, target_values=noisy), KEPLER_SIGNATURE)
    res = _run_case(case)
    assert res.success
    assert res.verdict == "bestaetigt"


# --- (3) negative control: scrambled data must NOT be reported as rediscovered ------------

def test_negative_control_scrambled_target_not_rediscovered():
    """Pair the Kepler inputs with a REVERSED (scrambled) target so the (a, T) relation is broken,
    while keeping the correct ``expected_exponents``. The dimensional exponents the engine derives
    still equal the textbook signature (dimensions are units-determined), so if success came from
    echoing ``expected_exponents`` this would PASS. It must FAIL: only the data fit decides."""
    a = np.asarray(_HELD_OUT_AXES, dtype=float)
    exact = 2.0 * math.pi * a ** 1.5 / math.sqrt(MU_SUN)
    scrambled = exact[::-1]  # deterministic shuffle: monotone law -> anti-monotone data
    case = BenchmarkCase("Kepler scrambled", _kepler_problem(a, target_values=scrambled), KEPLER_SIGNATURE)
    res = _run_case(case)
    assert res.success is False
    assert res.verdict != "bestaetigt"


def test_negative_control_engine_does_not_validate_scrambled_data():
    """The honesty result one layer deeper: the engine itself refuses the scrambled fit (low R²),
    so no validated 'bestaetigt' candidate exists for the harness to count."""
    a = np.asarray(_HELD_OUT_AXES, dtype=float)
    exact = 2.0 * math.pi * a ** 1.5 / math.sqrt(MU_SUN)
    scrambled = exact[::-1]
    result = discover_new_formulas(_kepler_problem(a, target_values=scrambled), known_laws=None)
    assert all(v.verdict != "bestaetigt" for v in result.validated)


# --- property: Kepler is rediscovered from ANY valid exact sample -------------------------

@settings(max_examples=40, deadline=None)
@given(
    st.lists(
        st.floats(min_value=1.0e10, max_value=5.0e12, allow_nan=False, allow_infinity=False),
        min_size=4,
        max_size=8,
        unique=True,
    )
)
def test_property_kepler_recovered_from_any_exact_sample(axes):
    """For ANY set of distinct positive semi-major axes, the exact Kepler law is rediscovered.
    The invariant 'exact data of a known power law → rediscovered' must hold over the input space,
    not just for the one hand-picked array — proving the headline is a property of the method."""
    case = BenchmarkCase("Kepler prop", _kepler_problem(sorted(axes)), KEPLER_SIGNATURE)
    res = _run_case(case)
    assert res.success
    assert _exponents_match(
        discover_new_formulas(case.problem, known_laws=None).validated[0].candidate.exponents,
        KEPLER_SIGNATURE,
    )


if __name__ == "__main__":  # pragma: no cover - convenience runner
    raise SystemExit(pytest.main([__file__, "-q"]))
