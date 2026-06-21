"""feynman — GENESIS's discovery arm scored on the Feynman Symbolic Regression Database.

The honest external-benchmark number. The Feynman SRDB (Udrescu & Tegmark, *AI Feynman*, Science
Advances 2020; space.mit.edu/home/tegmark/aifeynman.html) is the standard equation-discovery yardstick.
GENESIS's discovery core finds POWER-LAW / Buckingham-π relations of positive magnitudes — so it does
NOT, and must not pretend to, recover transcendental or additive Feynman equations. This benchmark
therefore measures TWO things, and honesty lives in the second:

  * RECOVERY on the power-law family — equations whose dimensional structure GENESIS can solve
    (gravitation, ideal gas, flux, kinetic energy, pendulum). Success = a gate-passed candidate whose
    exponents match the textbook signature.
  * HONEST ABSTENTION on the non-power-law family — Gaussian, Euclidean distance, the thin-lens/parallel
    combination. Success = GENESIS does NOT confirm a power law (no ``bestaetigt`` candidate). An LLM-SR
    system that "recovers" these by reciting a memorised form scores a false positive here; GENESIS's
    deterministic fit gate must return "I don't know".

The headline number is reported with both rates separately, never blended into a single inflated
"accuracy" — the LLM-SRBench lesson that a Feynman score dominated by recitation is not a discovery
score. Deterministic (seeded sampling), offline, numpy-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from .benchmark import (
    EXPONENT_MATCH_TOLERANCE,
    BenchmarkCase,
    CaseResult,
    ideal_gas_case,
    newton_gravity_case,
    pendulum_case,
)
from .engine import Constant, DiscoveryProblem, Variable, discover_new_formulas


@dataclass(frozen=True)
class FeynmanEq:
    """One Feynman SRDB equation as a generator spec. ``expected_exponents`` is the textbook power-law
    signature when GENESIS should recover it, or ``None`` when the equation is NOT a power law and the
    honest outcome is abstention."""

    number: str
    name: str
    target_unit: str
    inputs: tuple[tuple[str, str, float, float], ...]      # (name, unit, lo, hi)
    formula: Callable[[dict[str, np.ndarray]], np.ndarray]
    expected_exponents: dict[str, float] | None
    constants: tuple[tuple[str, float, str], ...] = ()      # (name, value, unit)


def _to_case(eq: FeynmanEq, *, n: int, seed: int) -> BenchmarkCase:
    """Sample synthetic data for a Feynman equation over its ranges (seeded) and build a case."""
    rng = np.random.default_rng(seed)
    env: dict[str, np.ndarray] = {}
    inputs: list[Variable] = []
    for name, unit, lo, hi in eq.inputs:
        vals = rng.uniform(lo, hi, n)
        env[name] = vals
        inputs.append(Variable(name, unit, tuple(float(v) for v in vals)))
    consts: list[Constant] = []
    for name, value, unit in eq.constants:
        env[name] = np.full(n, float(value))
        consts.append(Constant(name, float(value), unit))
    y = np.asarray(eq.formula(env), dtype=float)
    target = Variable("y", eq.target_unit, tuple(float(v) for v in y))
    problem = DiscoveryProblem(
        idea=f"Feynman {eq.number}: {eq.name}", target=target,
        inputs=tuple(inputs), constants=tuple(consts),
    )
    return BenchmarkCase(
        name=f"Feynman {eq.number}", problem=problem,
        expected_exponents=eq.expected_exponents, is_redteam=eq.expected_exponents is None,
    )


# --- a curated, attributed subset of the Feynman SRDB ------------------------------------------
# Power-law family (GENESIS-recoverable): the dimensional solve fixes the exponents, the fit the const.
_FLUX = FeynmanEq(
    "II.3.24", "radiated power flux  I = P/(4π r²)", "W/m^2",
    (("P", "W", 1.0, 10.0), ("r", "m", 1.0, 5.0)),
    lambda e: e["P"] / (4.0 * np.pi * e["r"] ** 2),
    {"P": 1.0, "r": -2.0},
)
_KINETIC = FeynmanEq(
    "I.13.4", "kinetic energy  E = ½ m v²", "J",
    (("m", "g", 1.0, 5.0), ("v", "m/s", 1.0, 10.0)),
    lambda e: 0.5 * e["m"] * e["v"] ** 2,
    {"m": 1.0, "v": 2.0},
)

# Non-power-law family (GENESIS must ABSTAIN — these are NOT monomials of their inputs):
_GAUSSIAN = FeynmanEq(
    "I.6.20", "Gaussian  f = exp(−θ²/2)/√(2π)", "1",
    (("theta", "1", 0.3, 2.0),),
    lambda e: np.exp(-(e["theta"] ** 2) / 2.0) / np.sqrt(2.0 * np.pi),
    None,
)
_DISTANCE = FeynmanEq(
    "I.8.14", "Euclidean distance  d = √(a²+b²)", "m",
    (("a", "m", 1.0, 5.0), ("b", "m", 1.0, 5.0)),
    lambda e: np.sqrt(e["a"] ** 2 + e["b"] ** 2),
    None,
)
_LENS = FeynmanEq(
    "I.27.6", "thin-lens / parallel combination  f = a·b/(a+b)", "m",
    (("a", "m", 1.0, 5.0), ("b", "m", 1.0, 5.0)),
    lambda e: (e["a"] * e["b"]) / (e["a"] + e["b"]),
    None,
)


def feynman_cases(*, n: int = 64, seed: int = 0) -> list[BenchmarkCase]:
    """The curated Feynman SRDB subset as benchmark cases (power-law + non-power-law families).

    The three textbook power laws GENESIS already rediscovers (gravitation I.9.18, ideal gas I.39.22,
    pendulum) are reused from ``benchmark.py``; the rest are sampled fresh from their Feynman ranges.
    """
    sampled = [
        _to_case(_FLUX, n=n, seed=seed + 1),
        _to_case(_KINETIC, n=n, seed=seed + 2),
        _to_case(_GAUSSIAN, n=n, seed=seed + 3),
        _to_case(_DISTANCE, n=n, seed=seed + 4),
        _to_case(_LENS, n=n, seed=seed + 5),
    ]
    reused = [newton_gravity_case(), ideal_gas_case(), pendulum_case()]
    return reused + sampled


@dataclass(frozen=True)
class FeynmanReport:
    """The honest two-rate score. ``recovery_rate`` is over the power-law family; ``abstention_rate``
    is over the non-power-law family (the share GENESIS correctly refused to confirm)."""

    results: tuple[CaseResult, ...]
    recoverable_total: int
    recoverable_recovered: int
    nonrecoverable_total: int
    nonrecoverable_abstained: int

    @property
    def recovery_rate(self) -> float:
        return self.recoverable_recovered / self.recoverable_total if self.recoverable_total else 0.0

    @property
    def abstention_rate(self) -> float:
        return self.nonrecoverable_abstained / self.nonrecoverable_total if self.nonrecoverable_total else 0.0


def _matches(candidate, expected: dict[str, float]) -> bool:
    return all(abs(candidate.exponents.get(k, 0.0) - v) <= EXPONENT_MATCH_TOLERANCE for k, v in expected.items())


def feynman_benchmark(*, n: int = 64, seed: int = 0) -> FeynmanReport:
    """Run GENESIS discovery over the Feynman subset and report recovery + honest-abstention rates."""
    results: list[CaseResult] = []
    rec_total = rec_ok = non_total = non_ok = 0
    for case in feynman_cases(n=n, seed=seed):
        outcome = discover_new_formulas(case.problem)
        best = outcome.validated[0].candidate if outcome.validated else None
        if case.expected_exponents is not None:           # power-law family: must recover
            rec_total += 1
            recovered = best is not None and _matches(best, case.expected_exponents)
            rec_ok += int(recovered)
            results.append(CaseResult(
                case.name, recovered, "bestaetigt" if best is not None else "unentschieden",
                "recovered" if recovered else "not recovered",
            ))
        else:                                             # non-power-law: success = honest abstention
            non_total += 1
            abstained = best is None                       # nothing passed the gate -> did not hallucinate
            non_ok += int(abstained)
            results.append(CaseResult(
                case.name, abstained, "unentschieden" if abstained else "bestaetigt",
                "abstained (honest)" if abstained else "FALSE-CONFIRMED a non-power-law",
            ))
    return FeynmanReport(tuple(results), rec_total, rec_ok, non_total, non_ok)
