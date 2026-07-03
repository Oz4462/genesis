"""srbench_hygiene — the SRBench evaluation-hygiene gate against Schein-Entdeckung.

The honest benchmark lesson (FORSCHUNG_AUTONOMES_ERFINDEN §A2/P2, SRBench arXiv:2107.14351): a high R² is
NOT a discovery — R² rewards the wrong equation, and a fit on data it was only fitted on proves nothing.
So a discovered law must clear hygiene checks before it is trusted:

  * DUMMY-VARIABLE test — plant an IRRELEVANT variable (a different physical dimension, random values). A
    sound discovery must give it a ~zero exponent. GENESIS' dimensional engine forces an alien-dimension
    variable to exponent 0 by construction (it cannot help form the target dimension), so a non-zero dummy
    exponent would signal a broken engine — the test pins that soundness.
  * OUT-OF-SAMPLE generalisation — reuse ``validation.out_of_sample_validate``: a real law (Kepler from
    half the planets) predicts the other half; a spurious fit on noise does not (its held-out R² collapses).
  * NOISE SWEEP — add multiplicative noise at rising levels and report the held-out R². A real law degrades
    gracefully; pure noise never generalises. (Reported for transparency; the gate decision is dummy ∧ OOS.)

Honest note: because GENESIS' dimensional constraint FIXES the exponents from the units (one free
coefficient), the engine is structurally hard to overfit — so the discriminating power here is the
out-of-sample collapse on non-power-law / noise targets and the alien-dummy soundness, not exponent
wobble. Seed fixed AND varied where it matters; never best-of-N (that is p-hacking). Offline, deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .engine import DiscoveryProblem, Variable, symbolic_regress
from .validation import out_of_sample_validate

#: A dimension absent from typical mechanical/orbital targets — an alien-dimension dummy is forced to
#: exponent 0 by the dimensional solve. Override for a problem whose target genuinely involves mass.
DEFAULT_DUMMY_UNIT = "kg"
#: |exponent| at/below which the planted dummy counts as excluded.
DUMMY_TOLERANCE = 1e-3


@dataclass(frozen=True)
class HygieneReport:
    """Outcome of the hygiene gate. ``passed`` requires the planted dummy excluded AND out-of-sample
    generalisation — the two checks that actually discriminate a real law from a fit on noise."""

    dummy_excluded: bool
    dummy_exponent: float
    oos_test_r2: float
    generalises: bool
    noise_sweep: tuple[tuple[float, float], ...]
    passed: bool


def dummy_variable_test(problem: DiscoveryProblem, *, dummy_unit: str = DEFAULT_DUMMY_UNIT,
                        seed: int = 0, tol: float = DUMMY_TOLERANCE) -> tuple[bool, float]:
    """Plant an alien-dimension dummy input (random positive values) and discover again; the dummy's
    fitted exponent must be ~0. Returns ``(excluded, |exponent|)``."""
    n = len(problem.target.values)
    rng = np.random.default_rng(seed)
    dummy = Variable("hygiene_dummy", dummy_unit, tuple(rng.uniform(1.0, 5.0, size=n)))
    augmented = DiscoveryProblem(idea=problem.idea, target=problem.target,
                                 inputs=problem.inputs + (dummy,), constants=problem.constants,
                                 run_id=problem.run_id)
    candidate = symbolic_regress(augmented)[0]
    exponent = abs(float(candidate.exponents.get("hygiene_dummy", 0.0)))
    return exponent <= tol, exponent


def _noisy_target(problem: DiscoveryProblem, level: float, seed: int) -> DiscoveryProblem:
    rng = np.random.default_rng(seed)
    y = np.asarray(problem.target.values, dtype=float)
    noisy = np.abs(y * (1.0 + level * rng.standard_normal(y.shape)))
    noisy = np.maximum(noisy, np.abs(y) * 1e-3)            # keep strictly positive (engine requirement)
    return DiscoveryProblem(idea=problem.idea,
                            target=Variable(problem.target.name, problem.target.unit, tuple(noisy)),
                            inputs=problem.inputs, constants=problem.constants, run_id=problem.run_id)


def noise_sweep(problem: DiscoveryProblem, *, levels=(0.0, 0.01, 0.05, 0.1),
                seed: int = 0) -> tuple[tuple[float, float], ...]:
    """Held-out R² at rising multiplicative-noise levels — graceful degradation for a real law. Best-effort:
    a level whose split cannot be fit reports ``nan`` rather than crashing."""
    out: list[tuple[float, float]] = []
    for level in levels:
        prob = problem if level == 0.0 else _noisy_target(problem, level, seed)
        try:
            out.append((float(level), float(out_of_sample_validate(prob).test_r2)))
        except (ValueError, ZeroDivisionError):
            out.append((float(level), float("nan")))
    return tuple(out)


def hygiene_gate(problem: DiscoveryProblem, *, dummy_unit: str = DEFAULT_DUMMY_UNIT,
                 levels=(0.0, 0.01, 0.05, 0.1), seed: int = 0) -> HygieneReport:
    """Run the full hygiene gate. ``passed`` iff the planted dummy is excluded AND the law generalises
    out-of-sample — a fit on noise (or a non-power-law target) fails the OOS check. Deterministic."""
    excluded, exponent = dummy_variable_test(problem, dummy_unit=dummy_unit, seed=seed)
    oos = out_of_sample_validate(problem)
    sweep = noise_sweep(problem, levels=levels, seed=seed)
    return HygieneReport(dummy_excluded=excluded, dummy_exponent=exponent,
                         oos_test_r2=oos.test_r2, generalises=oos.generalises,
                         noise_sweep=sweep, passed=excluded and oos.generalises)
