"""First-order uncertainty propagation (GUM / JCGM 100) for γ derivations.

GENESIS otherwise treats every value as an exact point. But a real measured or
sourced input carries an uncertainty (a 12 kg shelf load is 12 ± something). For
"every value is backed" to stay rigorous under real inputs, that uncertainty must
PROPAGATE: a DERIVED value should carry — and independently recompute — its
combined standard uncertainty, exactly as the value itself is recomputed (C-6).

Method (researched, not invented): the GUM law of propagation of uncertainty for
UNCORRELATED inputs (JCGM 100:2008 / ISO GUM, eq. 10):

    u_c(y)^2 = Σ_i ( ∂f/∂x_i )^2 · u(x_i)^2 ,   y = f(x_1, …, x_n)

The partial derivatives ∂f/∂x_i are taken numerically (central differences) over
the same safe evaluator the values use, so any formula in the grammar
(+ - * /, min/max) is handled without symbolic differentiation. The expanded
uncertainty is U = k · u_c (JCGM 100 §6; k = 2 ≈ 95 % for a normal distribution).

Honest boundary: this is the FIRST-ORDER (linear Taylor) GUM, for uncorrelated
inputs. It is exact for sums/products of the inputs and a very good approximation
otherwise; strong non-linearity or correlated inputs need the Monte-Carlo method
(JCGM 101) — a later layer, under the same proof standard. It propagates
uncertainty; it does not invent an input uncertainty (an input with no declared
uncertainty contributes zero — it is treated as exact, which the caller declares).
"""

from __future__ import annotations

from .verification.derivation import evaluate_formula


def _central_partial(
    formula: str, values: dict[str, float], var: str, step: float
) -> float:
    """∂f/∂var by central difference: (f(var+h) - f(var-h)) / 2h. Exact for the
    linear/bilinear formulas in the grammar; deterministic given a fixed step."""
    up = dict(values)
    down = dict(values)
    up[var] = values[var] + step
    down[var] = values[var] - step
    return (evaluate_formula(formula, up) - evaluate_formula(formula, down)) / (2.0 * step)


def numeric_partials(formula: str, values: dict[str, float]) -> dict[str, float]:
    """∂f/∂x_i for every input, by central difference (deterministic)."""
    partials: dict[str, float] = {}
    for var, v in values.items():
        h = max(abs(v) * 1e-6, 1e-9)         # relative step, with an absolute floor
        partials[var] = _central_partial(formula, values, var, h)
    return partials


def combine_standard_uncertainty(
    formula: str,
    values: dict[str, float],
    uncertainties: dict[str, float],
) -> float:
    """Combined standard uncertainty u_c of ``y = formula(values)`` under the GUM
    law of propagation for uncorrelated inputs (JCGM 100 eq. 10).

    `uncertainties` gives the standard uncertainty u(x_i) of each input in the
    same unit as its value; an input absent from the mapping contributes zero
    (it is treated as exact). Returns u_c (a standard uncertainty, same unit as y).
    """
    partials = numeric_partials(formula, values)
    total = 0.0
    for var, dfdx in partials.items():
        u = float(uncertainties.get(var, 0.0))
        total += (dfdx * u) ** 2
    return total ** 0.5


def expanded_uncertainty(standard_uncertainty: float, k: float = 2.0) -> float:
    """Expanded uncertainty U = k · u_c (JCGM 100 §6; k = 2 ≈ 95 % coverage)."""
    return k * float(standard_uncertainty)
