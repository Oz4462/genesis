"""uncertainty — bootstrap confidence bands over a discovered law (the integrity layer GENESIS lacked).

FORSCHUNG_AUTONOMES_ERFINDEN §A2/P2: a scientist reports a DISTRIBUTION over laws with uncertainty bands,
not one scheinsichere Formel. This is the bootstrap realisation: resample the data points with replacement
many times, rediscover the law on each resample, and report each parameter's mean + a percentile band.

The honest behaviour falls straight out of GENESIS' design: on EXACT data (a clean Kepler) every resample
gives the identical perfect fit, so the band is DEGENERATE (zero width) — correctly saying "no uncertainty,
this law fits exactly". As noise enters the data the band WIDENS, quantifying how much the data actually
pins each parameter. Because the dimensional constraint fixes the exponents from the units (one free
coefficient), the coefficient band is usually the informative one; for an under-determined free-π law the
exponent bands move too. A wide band is an honest "the data does not strongly determine this", never hidden
behind a single number. Pure numpy (percentiles over reseeded resamples); offline, deterministic.

(Distinct from top-level ``gen.uncertainty`` — that is GUM standard-uncertainty propagation for a spec;
this is empirical bootstrap over a discovered law.)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .engine import DiscoveryProblem, Variable, symbolic_regress


@dataclass(frozen=True)
class ParameterBand:
    """A bootstrap band for one parameter: ``mean`` and a ``[lo, hi]`` percentile interval (default 95 %),
    plus ``std``. ``contains(v)`` tells whether the truth ``v`` lies inside the band."""

    name: str
    mean: float
    lo: float
    hi: float
    std: float

    def contains(self, value: float) -> bool:
        return self.lo <= value <= self.hi

    @property
    def width(self) -> float:
        return self.hi - self.lo


@dataclass(frozen=True)
class BootstrapResult:
    """Bootstrap distribution over the discovered law: one ``ParameterBand`` per source exponent and one for
    the fitted ``coefficient``, plus the mean R² across resamples and the resample count."""

    bands: dict[str, ParameterBand]
    n_resamples: int
    r2_mean: float


def _resample(problem: DiscoveryProblem, idx: np.ndarray) -> DiscoveryProblem:
    y = np.asarray(problem.target.values, dtype=float)
    return DiscoveryProblem(
        idea=problem.idea,
        target=Variable(problem.target.name, problem.target.unit, tuple(y[idx])),
        inputs=tuple(Variable(v.name, v.unit, tuple(np.asarray(v.values, dtype=float)[idx]))
                     for v in problem.inputs),
        constants=problem.constants, run_id=problem.run_id)


def _band(name: str, values: list[float], ci: tuple[float, float]) -> ParameterBand:
    arr = np.asarray(values, dtype=float)
    return ParameterBand(name=name, mean=float(np.mean(arr)),
                         lo=float(np.percentile(arr, ci[0])), hi=float(np.percentile(arr, ci[1])),
                         std=float(np.std(arr)))


def bootstrap_law(
    problem: DiscoveryProblem,
    *,
    n_resamples: int = 400,
    seed: int = 0,
    ci: tuple[float, float] = (2.5, 97.5),
) -> BootstrapResult:
    """Resample the data ``n_resamples`` times with replacement, rediscover the best power law on each, and
    report a percentile band per exponent + the coefficient. Deterministic for a fixed ``seed``. Raises
    ValueError on too few points (via the engine) — bootstrap needs a few real samples."""
    y = np.asarray(problem.target.values, dtype=float)
    n = y.shape[0]
    if n < 3:
        raise ValueError("need at least 3 data points to bootstrap")
    rng = np.random.default_rng(seed)
    exp_names = [v.name for v in problem.inputs] + [c.name for c in problem.constants]
    exp_samples: dict[str, list[float]] = {name: [] for name in exp_names}
    coeffs: list[float] = []
    r2s: list[float] = []
    for _ in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        candidate = symbolic_regress(_resample(problem, idx))[0]
        for name in exp_names:
            exp_samples[name].append(float(candidate.exponents.get(name, 0.0)))
        coeffs.append(float(candidate.coefficient))
        r2s.append(float(candidate.r_squared))

    bands = {name: _band(name, exp_samples[name], ci) for name in exp_names}
    bands["coefficient"] = _band("coefficient", coeffs, ci)
    return BootstrapResult(bands=bands, n_resamples=n_resamples, r2_mean=float(np.mean(r2s)))
