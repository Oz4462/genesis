"""Monte-Carlo uncertainty propagation (GUM Supplement 1, JCGM 101).

The first-order GUM (uncertainty.py) propagates uncertainty by a linear Taylor
expansion — exact for sums/products, approximate otherwise. JCGM 101 (the GUM
Supplement) replaces the linearisation with a Monte-Carlo simulation: sample each
input from its distribution, push every sample through the model, and read the
output distribution directly. It captures non-linearity (including the mean shift
first-order misses) and non-Gaussian outputs.

GENESIS keeps it DETERMINISTIC: the sampler is seeded (a fixed default seed), so
the same inputs give the same interval — reproducibility is non-negotiable
(CLAUDE.md §5). Offline, no LLM. Inputs are taken as independent Gaussians
N(value, u) (an input with u = 0 is a constant).

Honest boundary: independent Gaussian inputs and a fixed sample count — the
coverage interval carries Monte-Carlo error ~ 1/sqrt(N). Correlated inputs or
non-Gaussian priors are a further extension under the same proof standard. Where
the model is linear this AGREES with the first-order GUM (the test pins that); its
value is the non-linear case, where it does not.
"""

from __future__ import annotations

import numpy as np

from .verification.derivation import evaluate_formula

DEFAULT_SAMPLES = 100_000
DEFAULT_SEED = 12345


def montecarlo_uncertainty(
    formula: str,
    values: dict[str, float],
    uncertainties: dict[str, float],
    *,
    n_samples: int = DEFAULT_SAMPLES,
    seed: int = DEFAULT_SEED,
    coverage: float = 0.95,
) -> dict[str, float]:
    """Propagate uncertainty through `formula` by Monte Carlo (JCGM 101).

    Returns ``{"mean", "std", "lo", "hi"}``: the output mean and standard
    uncertainty (sample std) and the symmetric `coverage` interval (e.g. the 2.5 %
    and 97.5 % quantiles for 95 %). Deterministic for fixed `seed`.
    """
    rng = np.random.default_rng(seed)
    names = list(values.keys())
    # draw an (n_samples x n_inputs) sample matrix; u = 0 -> a constant column
    columns = {}
    for name in names:
        u = float(uncertainties.get(name, 0.0))
        v = float(values[name])
        columns[name] = rng.normal(v, u, n_samples) if u > 0 else np.full(n_samples, v)

    # evaluate the formula vectorised: the safe evaluator's + - * / propagate over
    # numpy arrays unchanged. (min/max formulas fall back to per-sample.)
    try:
        out = evaluate_formula(formula, columns)
        out = np.asarray(out, dtype=float)
        if out.shape != (n_samples,):
            out = np.full(n_samples, float(out))
    except Exception:  # noqa: BLE001 - e.g. min/max over arrays: evaluate per sample
        out = np.array([
            evaluate_formula(formula, {k: columns[k][i] for k in names})
            for i in range(n_samples)
        ])

    lo_q = (1.0 - coverage) / 2.0
    return {
        "mean": float(np.mean(out)),
        "std": float(np.std(out, ddof=1)),
        "lo": float(np.quantile(out, lo_q)),
        "hi": float(np.quantile(out, 1.0 - lo_q)),
    }
