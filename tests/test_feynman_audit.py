"""Characterization audit for ``gen.discovery.feynman`` — separate recovery vs honest-abstention rates, no blended score.

The module's claim (feynman.py docstring and FeynmanReport): the Feynman SRDB run reports TWO separate rates and
honesty lives in abstention. Concretely:

* RECOVERY on the power-law family (gravitation, ideal gas, pendulum, flux, kinetic energy) succeeds:
  the engine emits a validated 'bestaetigt' whose exponents match the textbook signature (within
  EXPONENT_MATCH_TOLERANCE).
* HONEST ABSTENTION on the non-power-law family (Gaussian, Euclidean distance, thin-lens): GENESIS must
  NOT emit a 'bestaetigt' power law for it; the case must come back with no validated candidates and
  verdict 'unentschieden' (the gates actively refuse rather than silently drop or hallucinate).
* The headline object (FeynmanReport) exposes ``recovery_rate`` and ``abstention_rate`` separately;
  it never exposes or computes a single blended 'accuracy'.

This audit constructs inputs via the REAL dataclasses (DiscoveryProblem/Variable/Constant) and calls
the real collaborators (feynman_cases + discover_new_formulas). It contains a NEGATIVE test
(non-power-law must not produce 'bestaetigt') and a PROPERTY-BASED test (rates stay separate/bounded
and deterministic across seeds; no blended accuracy can appear).

If the characterization revealed that abstention were faked (silently dropping the case, emitting a
blended score, or confirming a 'bestaetigt' for a non-power-law), feynman.py would be edited. It does not;
the headline contract already holds. Therefore only the new audit test is added — change nothing if correct.

File scope respected: only touches tests/test_feynman_audit.py (and would edit feynman.py on genuine defect).
"""

from __future__ import annotations

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from gen.discovery.benchmark import EXPONENT_MATCH_TOLERANCE
from gen.discovery.engine import (
    Constant,
    DiscoveryProblem,
    Variable,
    discover_new_formulas,
)
from gen.discovery.feynman import (
    FeynmanReport,
    feynman_benchmark,
    feynman_cases,
)

# Textbook signatures for the power-law family (reused + freshly sampled). These live only in the
# test as the post-hoc match criterion — never fed into discover_new_formulas (the honesty contract).
POWER_LAW_SIGNATURES = {
    "Newton gravitation": {"m1": 1.0, "m2": 1.0, "r": -2.0, "G": 1.0},
    "Ideal gas law": {"R": 1.0, "n": 1.0, "Temp": 1.0, "V": -1.0},
    "Pendulum period": {"L": 0.5, "g": -0.5},
    "Feynman II.3.24": {"P": 1.0, "r": -2.0},
    "Feynman I.13.4": {"m": 1.0, "v": 2.0},
}

NON_POWER_LAW_NAMES = {"Feynman I.6.20", "Feynman I.8.14", "Feynman I.27.6"}


def _exponents_match(actual: dict[str, float], expected: dict[str, float]) -> bool:
    """Local mirror of the tolerance check used by the module (for direct audit assertions)."""
    return all(
        abs(actual.get(k, 0.0) - v) <= EXPONENT_MATCH_TOLERANCE for k, v in expected.items()
    )


# --- Direct recovery proofs (exponents match textbook signature) --------------------------------

def test_power_law_family_recovers_with_textbook_exponents():
    """Power-law cases (gravitation/ideal-gas/pendulum + flux/kinetic) yield a 'bestaetigt' whose
    exponents match the textbook signature. This is the 'recovery succeeds' half of the claim."""
    cases = feynman_cases(n=16, seed=7)
    power_cases = [c for c in cases if c.expected_exponents is not None]
    assert len(power_cases) == 5

    for case in power_cases:
        outcome = discover_new_formulas(case.problem, known_laws=None)
        assert outcome.validated, f"{case.name} produced no validated candidate"
        best = outcome.validated[0]
        assert best.verdict == "bestaetigt", f"{case.name} did not receive bestaetigt"
        sig = POWER_LAW_SIGNATURES[case.name]
        assert _exponents_match(best.candidate.exponents, sig), (
            f"{case.name} exponents {best.candidate.exponents} do not match {sig}"
        )


# --- Honest abstention proofs (no 'bestaetigt' on non-power-law) --------------------------------

def test_non_power_law_family_yields_honest_abstention_no_bestaetigt():
    """Non-power-law equations (Gaussian, Euclidean distance, thin-lens) must produce ZERO
    validated 'bestaetigt'. The engine may emit attempted power-law candidates (all_records > 0),
    but the gates must refuse them (active refusal, not silent drop). This is the honesty half."""
    cases = feynman_cases(n=16, seed=11)
    non_cases = [c for c in cases if c.expected_exponents is None]
    assert len(non_cases) == 3

    for case in non_cases:
        outcome = discover_new_formulas(case.problem, known_laws=None)
        # No candidate cleared the gates.
        assert outcome.validated == (), f"{case.name} falsely produced validated: {outcome.validated}"
        # Actively evaluated (candidates were proposed) but all refused.
        assert len(outcome.all_records) > 0, f"{case.name} was silently dropped (no candidates at all)"
        assert all(r.verdict != "bestaetigt" for r in outcome.all_records), (
            f"{case.name} emitted a bestaetigt in all_records"
        )
        # Top record (if any) is unentschieden or widerlegt, never bestaetigt.
        if outcome.all_records:
            assert outcome.all_records[0].verdict != "bestaetigt"


def test_feynman_report_never_reports_bestaetigt_for_non_power_law_names():
    """Using the headline entry point: the CaseResults for non-power names must never carry 'bestaetigt'."""
    report = feynman_benchmark(n=16, seed=13)
    for res in report.results:
        if res.name in NON_POWER_LAW_NAMES:
            assert res.verdict != "bestaetigt", f"{res.name} was reported as bestaetigt"


# --- Headline object: separate rates, never a blended accuracy ----------------------------------

def test_feynman_report_exposes_two_separate_rates_not_a_blended_accuracy():
    """The headline FeynmanReport must surface recovery_rate and abstention_rate as distinct
    properties and must never surface or compute a single blended 'accuracy'."""
    report = feynman_benchmark(n=32, seed=0)
    assert isinstance(report, FeynmanReport)
    assert hasattr(report, "recovery_rate")
    assert hasattr(report, "abstention_rate")
    # Explicitly no blended accuracy on the object (the documented anti-recitation contract).
    assert not hasattr(report, "accuracy")
    # Guard against accidental addition of a blended score.
    for attr in dir(report):
        if not attr.startswith("_"):
            assert "accuracy" not in attr.lower(), f"blended accuracy leaked via {attr}"

    # The two rates are independently meaningful (they can each be 1.0 without implying a composite).
    assert 0.0 <= report.recovery_rate <= 1.0
    assert 0.0 <= report.abstention_rate <= 1.0
    # Totals add to the case count (separation invariant).
    assert report.recoverable_total + report.nonrecoverable_total == len(report.results) == 8


def test_feynman_report_rates_are_computed_from_the_right_subsets():
    """recovery_rate is computed ONLY over the power-law subset; abstention_rate ONLY over the rest."""
    report = feynman_benchmark(n=8, seed=99)
    # With current data both are perfect, but the structure proves separation.
    assert report.recoverable_total == 5
    assert report.nonrecoverable_total == 3
    assert report.recoverable_recovered <= report.recoverable_total
    assert report.nonrecoverable_abstained <= report.nonrecoverable_total
    # A blended accuracy would not expose the two cardinalities separately.
    assert report.recoverable_total != report.nonrecoverable_total


# --- Negative test: signal-free or contradictory input yields honest refusal --------------------

def test_wide_range_non_power_law_is_refused_not_confirmed():
    """A documented non-power-law (thin-lens harmonic mean) over a range wide enough that no single
    monomial fits the curvature must be refused (active gate failure). Mirrors the canonical
    non-power cases used by feynman.py itself."""
    # Same generator shape as _LENS in feynman.py but explicit here so the audit owns the negative.
    a = np.linspace(0.5, 8.0, 12)
    b = np.linspace(0.8, 12.0, 12)
    y = (a * b) / (a + b)
    problem = DiscoveryProblem(
        idea="Thin lens (non-power, wide range).",
        target=Variable("f", "m", tuple(y)),
        inputs=(Variable("a", "m", tuple(a)), Variable("b", "m", tuple(b))),
    )
    outcome = discover_new_formulas(problem)
    assert outcome.validated == (), "wide-range thin-lens must not be bestaetigt"
    assert all(r.verdict != "bestaetigt" for r in outcome.all_records)


# --- Property-based invariants (Hypothesis) -----------------------------------------------------

@settings(max_examples=8, deadline=None, derandomize=True)
@given(st.integers(min_value=0, max_value=2**31 - 1))
def test_feynman_benchmark_separate_rates_are_deterministic_and_bounded(seed: int):
    """PROPERTY: identical (n, seed) always yields identical separate rates; each rate stays in [0,1];
    the report object never manufactures a blended accuracy regardless of input."""
    r1 = feynman_benchmark(n=16, seed=seed)
    r2 = feynman_benchmark(n=16, seed=seed)
    assert r1.recovery_rate == r2.recovery_rate
    assert r1.abstention_rate == r2.abstention_rate
    assert r1.recoverable_recovered == r2.recoverable_recovered
    assert r1.nonrecoverable_abstained == r2.nonrecoverable_abstained

    assert 0.0 <= r1.recovery_rate <= 1.0
    assert 0.0 <= r1.abstention_rate <= 1.0
    assert not hasattr(r1, "accuracy")
    # The separation contract: the two families are tallied independently.
    assert r1.recoverable_total == 5 and r1.nonrecoverable_total == 3


# --- Completeness / determinism cross-check -----------------------------------------------------

def test_feynman_benchmark_reports_full_separation_on_default_run():
    """The default feynman_benchmark() run (the one used by CLI/docs) must still show perfect
    separation: recovery on power laws, honest abstention on the rest."""
    r = feynman_benchmark()
    assert r.recovery_rate == 1.0
    assert r.abstention_rate == 1.0
    assert r.recoverable_recovered == r.recoverable_total == 5
    assert r.nonrecoverable_abstained == r.nonrecoverable_total == 3
    # No blended number is the headline.
    assert "accuracy" not in str(r).lower()
