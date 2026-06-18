"""benchmark — the Rediscovery benchmark + Red-Team (build doc Phase 4).

The honest capability proof. Two questions, both from the doc:

  * REDISCOVERY — can the engine recover KNOWN laws from data alone? (Kepler's third law,
    the ideal gas law, Newton's inverse-square gravitation.) This is the methodology AI
    Feynman was validated with: if it cannot re-find the laws we already know, no claim
    about new ones is credible.
  * RED-TEAM — fed "tempting but false" ideas, do the gates reject them? A dimensionally
    impossible target must be ``widerlegt``; data that only LOOKS like a power law but
    carries an extra additive term must fail the fit gate and come back ``unentschieden``
    (an honest "I don't know"), never a false ``bestaetigt``. A high rejection rate for the
    false cases is the success criterion.

``rediscovery_benchmark`` runs a set of cases and reports the rediscovery rate and the
red-team catch rate. Offline, deterministic, numpy-only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .engine import (
    Constant,
    DiscoveryProblem,
    Variable,
    discover_new_formulas,
)

#: How close a rediscovered exponent must be to the textbook value to count as recovered.
EXPONENT_MATCH_TOLERANCE = 0.05


@dataclass(frozen=True)
class BenchmarkCase:
    """One benchmark task. `expected_exponents` is the textbook signature for a real law
    (None for a red-team case); `is_redteam=True` means SUCCESS is the engine REJECTING it."""

    name: str
    problem: DiscoveryProblem
    expected_exponents: dict[str, float] | None
    is_redteam: bool = False
    known_laws: dict[str, dict[str, float]] | None = None


@dataclass(frozen=True)
class CaseResult:
    name: str
    success: bool
    verdict: str
    detail: str


@dataclass(frozen=True)
class BenchmarkReport:
    results: tuple[CaseResult, ...]
    n_pass: int
    n_total: int
    rediscovery_rate: float
    redteam_catch_rate: float


# --- the textbook cases ------------------------------------------------------------------

def kepler_case() -> BenchmarkCase:
    """Kepler III: T = 2π·a^(3/2)·mu^(-1/2)."""
    mu = 1.32712440018e20
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11, 1.434e12])
    T = 2.0 * math.pi * a ** 1.5 / math.sqrt(mu)
    problem = DiscoveryProblem(
        idea="Umlaufzeit vs. Bahngröße (Kepler).",
        target=Variable("T", "s", tuple(T)),
        inputs=(Variable("a", "m", tuple(a)),),
        constants=(Constant("mu", mu, "m^3/s^2"),))
    return BenchmarkCase("Kepler III", problem, {"a": 1.5, "mu": -0.5})


def ideal_gas_case() -> BenchmarkCase:
    """Ideal gas law: P = R·n·T·V^(-1)."""
    R = 8.314462618
    n = np.array([1.0, 2.0, 1.0, 3.0, 2.0, 1.5])
    Temp = np.array([273.0, 300.0, 350.0, 280.0, 320.0, 310.0])
    V = np.array([0.0224, 0.05, 0.03, 0.08, 0.04, 0.06])
    P = R * n * Temp / V
    problem = DiscoveryProblem(
        idea="Druck eines idealen Gases.",
        target=Variable("P", "Pa", tuple(P)),
        inputs=(Variable("n", "mol", tuple(n)),
                Variable("Temp", "K", tuple(Temp)),
                Variable("V", "m^3", tuple(V))),
        constants=(Constant("R", R, "J/mol/K"),))
    return BenchmarkCase("Ideal gas law", problem, {"R": 1.0, "n": 1.0, "Temp": 1.0, "V": -1.0})


def newton_gravity_case() -> BenchmarkCase:
    """Newton's gravitation: F = G·m1·m2·r^(-2)."""
    G = 6.674e-11
    m1 = np.array([1.0, 2.0, 3.0, 1.0, 2.0, 4.0])
    m2 = np.array([2.0, 1.0, 1.0, 3.0, 2.0, 1.0])
    r = np.array([1.0, 2.0, 1.0, 0.5, 1.5, 2.0])
    F = G * m1 * m2 / r ** 2
    problem = DiscoveryProblem(
        idea="Gravitationskraft zwischen zwei Massen.",
        target=Variable("F", "N", tuple(F)),
        inputs=(Variable("m1", "g", tuple(m1)),
                Variable("m2", "g", tuple(m2)),
                Variable("r", "m", tuple(r))),
        constants=(Constant("G", G, "m^3/g/s^2"),))
    return BenchmarkCase("Newton gravitation", problem, {"m1": 1.0, "m2": 1.0, "r": -2.0, "G": 1.0})


def redteam_impossible_case() -> BenchmarkCase:
    """A temperature target that no length+time product can form — must be 'widerlegt'."""
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    problem = DiscoveryProblem(
        idea="Erfinde eine Temperatur aus Länge und Zeit (dimensional unmöglich).",
        target=Variable("Theta", "K", tuple(2.0 * x)),
        inputs=(Variable("a", "m", tuple(x)), Variable("t", "s", tuple(x))))
    return BenchmarkCase("Red-team: impossible dimension", problem, None, is_redteam=True)


def redteam_offset_case() -> BenchmarkCase:
    """Free fall WITH an initial velocity: v = g·t + v0. The dimensional power law v=C·g·t
    cannot capture the additive v0, so the fit gate must keep it 'unentschieden', not
    falsely 'bestaetigt' just because the dimension is right."""
    g = 9.80665
    t = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    v0 = 40.0  # a large additive offset a pure power law cannot represent
    v = g * t + v0
    problem = DiscoveryProblem(
        idea="Geschwindigkeit im freien Fall (mit Anfangsgeschwindigkeit).",
        target=Variable("v", "m/s", tuple(v)),
        inputs=(Variable("t", "s", tuple(t)),),
        constants=(Constant("g", g, "m/s^2"),))
    return BenchmarkCase("Red-team: hidden additive term", problem, None, is_redteam=True)


def default_cases() -> list[BenchmarkCase]:
    return [kepler_case(), ideal_gas_case(), newton_gravity_case(),
            redteam_impossible_case(), redteam_offset_case()]


# --- the harness -------------------------------------------------------------------------

def _exponents_match(actual: dict[str, float], expected: dict[str, float]) -> bool:
    return all(abs(actual.get(k, 0.0) - v) < EXPONENT_MATCH_TOLERANCE for k, v in expected.items())


def _run_case(case: BenchmarkCase) -> CaseResult:
    result = discover_new_formulas(case.problem, known_laws=case.known_laws)
    top_verdict = result.all_records[0].verdict if result.all_records else "kein Kandidat"
    if case.is_redteam:
        # success = the false idea is rejected (nothing validated)
        success = result.validated == ()
        detail = "korrekt verworfen" if success else f"FÄLSCHLICH validiert: {result.validated[0].candidate.expression}"
        return CaseResult(case.name, success, top_verdict, detail)
    # real law: success = a validated 'bestaetigt' whose exponents match the textbook law
    matches = [v for v in result.validated
               if v.verdict == "bestaetigt" and _exponents_match(v.candidate.exponents, case.expected_exponents or {})]
    success = bool(matches)
    detail = matches[0].candidate.expression if matches else f"nicht rediscovered (top={top_verdict})"
    return CaseResult(case.name, success, "bestaetigt" if success else top_verdict, detail)


def rediscovery_benchmark(cases: list[BenchmarkCase] | None = None) -> BenchmarkReport:
    """Run the Rediscovery + Red-Team benchmark and report the rediscovery rate (known laws
    recovered) and the red-team catch rate (false ideas rejected). Deterministic."""
    cases = cases if cases is not None else default_cases()
    results = tuple(_run_case(c) for c in cases)
    real = [r for r, c in zip(results, cases) if not c.is_redteam]
    red = [r for r, c in zip(results, cases) if c.is_redteam]
    n_pass = sum(1 for r in results if r.success)
    return BenchmarkReport(
        results=results,
        n_pass=n_pass,
        n_total=len(results),
        rediscovery_rate=(sum(1 for r in real if r.success) / len(real)) if real else 1.0,
        redteam_catch_rate=(sum(1 for r in red if r.success) / len(red)) if red else 1.0,
    )
