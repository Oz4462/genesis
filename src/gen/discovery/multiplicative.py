"""multiplicative — discovery of multiplicative couplings (Frontier 6.6).

Two complementary capabilities, in the exact honest pattern of the frontier siblings
(`multiterm` 6.1/6.2, `transcendental` 6.3, `active_resolution` 6.4, `composition` 6.5):

  1. PRODUCT LAWS (:func:`discover_product_law`): ``y = C · π1^a · f(α·π2 [+ φ])`` — a power of
     one dimensionless π-group times a transcendental modulation of another (the Wien / Planck-
     tail shape ``x³·e^(−x)``, a Boltzmann-suppressed rate ``x^a·e^(−b·x)``, …). BOTH arguments
     are π-groups from the NULL SPACE of the source dimensional matrix (``A·p = 0``, same bounded
     lattice as the whole frontier), so the form is dimensionally forced: ``C`` alone carries the
     target's dimension (a fitted model parameter, never a sourced fact). Two fit paths:
       * LOG PATH (sound only where it is sound): for ``f = exp`` AND a strictly positive target,
         ``log y = log C + a·log π1 + α·π2`` is EXACTLY linear → deterministic lstsq, and the
         estimate also seeds the direct fit. The path is REFUSED (skipped — never a silent
         ``abs()``) when the target has any non-positive value: ``log|y|`` would silently change
         the model, so a sign-free target goes through the direct path only.
       * DIRECT PATH: `scipy.optimize.curve_fit` on the product model from fixed, deterministic
         initial guesses (offline, reproducible) — sign-free in ``y``, exactly like 6.3.
  2. MULTIPLICATIVE MINIMAL-CORRECTION (:func:`discover_multiplicative_correction`): the product
     counterpart of `composition.discover_correction`. Given a sourced baseline ``y_base``, the
     multiplicative residual is the RATIO ``r = y / y_base`` (dimensionless by construction) and
     the question is whether a dimensionless modulation ``m(π)`` with ``y ≈ y_base·m(π)`` is
     EARNED — under the SAME δ-asymmetric gates as the additive correction:
     ``ratio_explained ≥ 0.9`` AND ``ΔR² > 1e-3`` AND leave-one-out survival. The division is
     REFUSED (hard ValueError) unless ``|y_base| > ε`` at EVERY point — near a baseline zero the
     ratio blows up as ``1/y_base`` and any "modulation" found there is a division artefact, not
     physics (use the additive `composition` path instead). A constant ratio (pure rescaling) is
     never dressed up as a π-coupled modulation.

Honest gates (the core): the rival of a product form is a PURE POWER LAW over the same π-pairs,
``C·π1^p·π2^q + D`` — WITH an offset the product form does not get, so the rival is at least as
flexible (the conservative direction: bias toward ``unentschieden``, never toward a product
over-claim). ``bestaetigt`` only if the best product form is essentially exact (R² ≥ 0.999, the
6.3 bar) AND the best power-law rival is NOT; both exact → ``unentschieden`` — with the ACTIVE
follow-up: :func:`discover_product_rivals` hands the two fitted rivals to
`active_resolution.propose_resolution`, which computes the discriminating measurement (6.4) that
flips the tie. Otherwise ``widerlegt``. Noise is never promoted to a coupling: nothing in noise
clears the 0.999 bar (product law), and the ratio/ΔR²/LOO gates reject it (correction).

Honest boundary: products of TWO transcendentals as a BLIND law (``e^(−ζt)·cos(ωt)`` with no
declared baseline), compositions of transcendentals inside one another, and a full GP search
remain the open frontier. The damped oscillation IS recovered here — but only as a
declared-baseline correction (baseline ``A·e^(−ζt)`` → modulation ``cos(ωt)``), which is the
honest claim, not a blind two-transcendental product.
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from scipy.optimize import OptimizeWarning, curve_fit

from .composition import DEFAULT_LOO_BAR, DEFAULT_RESIDUAL_BAR, DEFAULT_SIGNIFICANCE
from .engine import DiscoveryProblem
from .multiterm import DEFAULT_GENERALISES_R2, _split_indices, _subproblem
from .transcendental import (
    DEFAULT_MAX_ABS_EXP,
    DEFAULT_R2_THRESHOLD,
    DEFAULT_STEP,
    TranscendentalForm,
    _baseline_form,
    _best_over_groups,
    _group_values,
    _r2,
    _source_arrays,
    dimensionless_groups,
)

#: |y_base| must exceed this fraction of the baseline's own peak magnitude at EVERY point before
#: the ratio y/y_base is formed. Near a baseline zero the multiplicative residual blows up as
#: 1/y_base and any "modulation" found there is a division artefact, not physics — so the module
#: REFUSES with a ValueError (Gate-Verweigerung) instead of silently masking or clipping points.
DEFAULT_MIN_BASE_REL = 1e-6

#: Hard cap on the number of ordered (π1, π2) pairs the product search enumerates. The pair space
#: is QUADRATIC in the group count; an unbounded search would have unbounded runtime and would not
#: be honest about its coverage. Exceeding it is a hard error: reduce max_abs_exp or raise step.
MAX_PRODUCT_PAIRS = 4096

#: Fitted EXPONENTS (the ``a`` of ``π1^a``, the ``p``/``q`` of the power rival) are bounded to
#: ±MAX_FIT_EXPONENT. The π-lattice itself only reaches ±2 per source; a fitted power far beyond
#: that is not a candidate physical law but a numerical step-function imitation — a degenerate
#: exact fit on narrow data whose extrapolation overflows float range (observed: a narrow-band
#: rival fit whose divergence search then returned NaN). Scale/argument parameters (C, α, φ, D)
#: stay unbounded.
MAX_FIT_EXPONENT = 8.0

#: A ratio whose relative spread is below this is a CONSTANT rescaling: std(r) ≤ tol·|mean(r)|.
#: A constant has no π-dependence, so promoting it to a "modulation of a π-group" would be a
#: structural over-claim (any form fits a constant via its offset). Float-noise scale, far below
#: any physical modulation.
_CONST_RATIO_TOL = 1e-9


# ---------------------------------------------------------------------------
# Part (a): product laws  y = C · π1^a · f(α·π2 [+ φ])
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProductForm:
    """One product model ``C·π1^a·f(…π2…)``: `model(pi1, pi2, *params)` returns the prediction;
    `p0_list` is the set of deterministic initial guesses (handles sign ambiguity of C and of the
    modulation argument without randomness)."""

    name: str
    model: Callable[..., np.ndarray]
    param_names: tuple[str, ...]
    p0_list: tuple[tuple[float, ...], ...]

    def bounds(self) -> tuple[list[float], list[float]]:
        """Fit bounds per parameter: exponents (``a``/``p``/``q``) are capped at
        ±MAX_FIT_EXPONENT (see the constant's rationale); everything else is free."""
        exponent_params = {"a", "p", "q"}
        lower = [-MAX_FIT_EXPONENT if n in exponent_params else -np.inf for n in self.param_names]
        upper = [MAX_FIT_EXPONENT if n in exponent_params else np.inf for n in self.param_names]
        return lower, upper


def _product_forms() -> tuple[ProductForm, ...]:
    """The modulation library of 6.3 (exp / sin / tanh / log), lifted to product form. `sin`
    carries a PHASE φ here: a multiplicative modulation of an oscillation is generically
    phase-shifted (``cos = sin(·+π/2)``), and without φ the library could not represent a cosine
    factor at all. π-groups are products of positive magnitudes, so ``π^a`` and ``log(π)`` are
    always well-defined."""

    def exp_model(pi1, pi2, c, a, alpha):
        return c * np.power(pi1, a) * np.exp(alpha * pi2)

    def sin_model(pi1, pi2, c, a, alpha, phi):
        return c * np.power(pi1, a) * np.sin(alpha * pi2 + phi)

    def tanh_model(pi1, pi2, c, a, alpha):
        return c * np.power(pi1, a) * np.tanh(alpha * pi2)

    def log_model(pi1, pi2, c, a):
        return c * np.power(pi1, a) * np.log(pi2)

    return (
        ProductForm("exp", exp_model, ("C", "a", "alpha"),
                    ((1.0, 1.0, -1.0), (1.0, 1.0, 1.0), (-1.0, 1.0, -1.0), (1.0, -1.0, 1.0))),
        ProductForm("sin", sin_model, ("C", "a", "alpha", "phi"),
                    ((1.0, 1.0, 1.0, 0.0), (1.0, 1.0, 2.0, 1.5708))),
        ProductForm("tanh", tanh_model, ("C", "a", "alpha"),
                    ((1.0, 1.0, 1.0), (1.0, 1.0, -1.0))),
        ProductForm("log", log_model, ("C", "a"),
                    ((1.0, 1.0), (-1.0, 1.0))),
    )


def _pow_rival() -> ProductForm:
    """The honest rival a product form must beat: a pure power law over the SAME π-pair,
    ``C·π1^p·π2^q + D``. It gets an offset the product form does not — at least as flexible, so
    the comparison can only err toward ``unentschieden``, never toward a product over-claim."""

    def pow2_model(pi1, pi2, c, p, q, d):
        return c * np.power(pi1, p) * np.power(pi2, q) + d

    return ProductForm("pow2", pow2_model, ("C", "p", "q", "D"),
                       ((1.0, 1.0, 1.0, 0.0), (1.0, 1.0, -1.0, 0.0),
                        (1.0, -1.0, 1.0, 0.0), (1.0, 2.0, 0.5, 0.0)))


def _log_linear_seed(pi1: np.ndarray, pi2: np.ndarray, y: np.ndarray) -> tuple[float, float, float] | None:
    """Exact linear estimate of (C, a, α) for the exp product on a strictly positive target:
    ``log y = log C + a·log π1 + α·π2``. Returns None (path REFUSED, no silent ``abs()``) if the
    target has any non-positive value — ``log|y|`` would silently change the model."""
    if np.any(y <= 0.0):
        return None
    x = np.column_stack([np.ones_like(y), np.log(pi1), pi2])
    try:
        coef, *_ = np.linalg.lstsq(x, np.log(y), rcond=None)
    except np.linalg.LinAlgError:
        return None
    if not np.all(np.isfinite(coef)) or abs(coef[0]) > 700.0:      # exp() would overflow
        return None
    return (float(math.exp(coef[0])), float(coef[1]), float(coef[2]))


def _fit_product(
    form: ProductForm,
    pi1: np.ndarray,
    pi2: np.ndarray,
    y: np.ndarray,
    extra_p0: Sequence[tuple[float, ...]] = (),
) -> tuple[float, tuple[float, ...]] | None:
    """Best (R², params) for one product form on one π-pair over all deterministic starts."""
    best: tuple[float, tuple[float, ...]] | None = None
    xdata = np.vstack([pi1, pi2])
    lower, upper = form.bounds()

    def wrapped(x, *params):
        return form.model(x[0], x[1], *params)

    def in_bounds(popt) -> bool:
        return all(lo <= v <= hi for v, lo, hi in zip(popt, lower, upper))

    for p0 in (*form.p0_list, *extra_p0):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", OptimizeWarning)
                warnings.simplefilter("ignore", RuntimeWarning)
                # Fast unbounded LM first; only a DEGENERATE solution (exponent outside
                # ±MAX_FIT_EXPONENT) triggers the slower bounded TRF refit from a clipped start.
                popt, _ = curve_fit(wrapped, xdata, y, p0=list(p0), maxfev=5000)
                if not in_bounds(popt):
                    clipped = [float(np.clip(v, lo, hi))
                               for v, lo, hi in zip(p0, lower, upper)]
                    popt, _ = curve_fit(wrapped, xdata, y, p0=clipped,
                                        bounds=(lower, upper), maxfev=5000)
            pred = form.model(pi1, pi2, *popt)
            if not np.all(np.isfinite(pred)) or not in_bounds(popt):
                continue
            r2 = _r2(y, pred)
            if best is None or r2 > best[0]:
                best = (r2, tuple(float(v) for v in popt))
        except (RuntimeError, ValueError, FloatingPointError):
            continue
    return best


def _best_product(
    forms: tuple[ProductForm, ...],
    groups: list[dict[str, float]],
    pi_cache: dict[int, np.ndarray],
    y: np.ndarray,
    *,
    use_log_seed: bool,
) -> tuple[float, ProductForm, dict[str, float], dict[str, float], tuple[float, ...]] | None:
    """Best (R², form, base_group, mod_group, params) over every ordered π-pair — including
    π1 == π2, which covers single-argument products like Wien's ``x³·e^(−x)``."""
    best: tuple[float, ProductForm, dict[str, float], dict[str, float], tuple[float, ...]] | None = None
    for i, g1 in enumerate(groups):
        for j, g2 in enumerate(groups):
            pi1, pi2 = pi_cache[i], pi_cache[j]
            for form in forms:
                extra: tuple[tuple[float, ...], ...] = ()
                if form.name == "exp" and use_log_seed:
                    seed = _log_linear_seed(pi1, pi2, y)
                    if seed is not None:
                        extra = (seed,)
                fit = _fit_product(form, pi1, pi2, y, extra_p0=extra)
                if fit is None:
                    continue
                r2, popt = fit
                if best is None or r2 > best[0]:
                    best = (r2, form, g1, g2, popt)
    return best


def _pi_expr(group: dict[str, float]) -> str:
    return " * ".join(n if abs(e - 1.0) < 1e-9 else f"{n}^{e:g}"
                      for n, e in group.items() if abs(e) > 1e-9) or "1"


def _format_product(target: str, form_name: str, base_group: dict[str, float],
                    mod_group: dict[str, float], params: dict[str, float]) -> str:
    c = params.get("C", 1.0)
    a = params.get("a", 0.0)
    base = f"({_pi_expr(base_group)})^{a:g}"
    if form_name == "log":
        mod = f"log({_pi_expr(mod_group)})"
    else:
        inner = f"{params.get('alpha', 1.0):.4g} * ({_pi_expr(mod_group)})"
        if "phi" in params and abs(params["phi"]) > 1e-9:
            inner += f" + {params['phi']:.4g}"
        mod = f"{form_name}({inner})"
    return f"{target} = {c:.4g} * {base} * {mod}"


@dataclass(frozen=True)
class ProductLaw:
    """A discovered multiplicative product law and its honest verdict.

    `verdict`: ``bestaetigt`` (product form essentially exact AND the power-law rival is not),
    ``unentschieden`` (both essentially exact — a pure power law explains the data just as well,
    no product over-claim; resolve actively via :func:`discover_product_rivals` + 6.4), or
    ``widerlegt`` (no dimensionless argument, or nothing fits). ``log_path_applied`` records
    whether the exact log-linear path was sound (strictly positive target) and therefore ran."""

    form_name: str
    base_group: dict[str, float]
    mod_group: dict[str, float]
    params: dict[str, float]
    r_squared: float
    powerlaw_r2: float
    log_path_applied: bool
    verdict: str
    expression: str


def _pair_guard(groups: list[dict[str, float]]) -> None:
    if len(groups) ** 2 > MAX_PRODUCT_PAIRS:
        raise ValueError(
            f"π-pair space too large ({len(groups)}² > {MAX_PRODUCT_PAIRS}); "
            "reduce max_abs_exp or raise step")


def discover_product_law(
    problem: DiscoveryProblem,
    *,
    r2_threshold: float = DEFAULT_R2_THRESHOLD,
    max_abs_exp: float = DEFAULT_MAX_ABS_EXP,
    step: float = DEFAULT_STEP,
) -> ProductLaw:
    """Discover a multiplicative product law ``y = C·π1^a·f(α·π2 [+ φ])`` over dimensionless
    π-pairs, honestly gated against the pure power-law rival ``C·π1^p·π2^q + D``.

    Enumerates the π-groups (null space ``A·p = 0``), fits every product form against every
    ordered pair (log-linear path for exp where the target is strictly positive, direct
    deterministic `curve_fit` always), and fits the power-law rival over the SAME pairs.
    Verdict: ``bestaetigt`` only if the product form clears `r2_threshold` and the rival does
    NOT; both clear → ``unentschieden``; otherwise ``widerlegt``. Raises ValueError on
    non-positive source magnitudes, an over-large lattice, or an over-large pair space."""
    y = np.asarray(problem.target.values, dtype=float)
    names, arrs = _source_arrays(problem)
    groups = dimensionless_groups(problem, max_abs_exp=max_abs_exp, step=step)

    if not groups:
        return ProductLaw(
            form_name="none", base_group={}, mod_group={}, params={},
            r_squared=-math.inf, powerlaw_r2=-math.inf, log_path_applied=False,
            verdict="widerlegt",
            expression=f"{problem.target.name} = (kein dimensionsloses Argument)")
    _pair_guard(groups)

    pi_cache = {i: _group_values(g, names, arrs) for i, g in enumerate(groups)}
    log_path_applied = bool(np.all(y > 0.0))

    rival = _best_product((_pow_rival(),), groups, pi_cache, y, use_log_seed=False)
    powerlaw_r2 = rival[0] if rival is not None else -math.inf

    best = _best_product(_product_forms(), groups, pi_cache, y, use_log_seed=log_path_applied)
    if best is None:
        return ProductLaw(
            form_name="none", base_group={}, mod_group={}, params={},
            r_squared=-math.inf, powerlaw_r2=powerlaw_r2, log_path_applied=log_path_applied,
            verdict="widerlegt",
            expression=f"{problem.target.name} = (keine Form passt)")

    r2, form, base_group, mod_group, popt = best
    params = {n: float(v) for n, v in zip(form.param_names, popt)}

    if r2 >= r2_threshold and powerlaw_r2 < r2_threshold:
        verdict = "bestaetigt"          # product essentially exact; the power-law rival is not
    elif r2 >= r2_threshold:
        verdict = "unentschieden"       # both essentially exact → a power law explains it as well
    else:
        verdict = "widerlegt"

    return ProductLaw(
        form_name=form.name, base_group=dict(base_group), mod_group=dict(mod_group),
        params=params, r_squared=r2, powerlaw_r2=powerlaw_r2,
        log_path_applied=log_path_applied, verdict=verdict,
        expression=_format_product(problem.target.name, form.name, base_group, mod_group, params))


# ---------------------------------------------------------------------------
# Rivals for the active-resolution follow-up (6.4 seam)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProductRival:
    """A fitted product-family rival that can be EVALUATED on new data — what an
    ``unentschieden`` product verdict leaves on the table. `active_resolution` accepts this next
    to the transcendental ``RivalForm`` and computes the discriminating measurement."""

    form_name: str
    base_group: dict[str, float]
    mod_group: dict[str, float]
    params: dict[str, float]
    r_squared: float


def _apply_product(form_name: str, params: dict[str, float],
                   pi1: np.ndarray, pi2: np.ndarray) -> np.ndarray:
    """Evaluate a fitted product form on π-pair values. Raises ValueError on an unknown form."""
    c = params.get("C", 1.0)
    if form_name == "exp":
        return c * np.power(pi1, params["a"]) * np.exp(params["alpha"] * pi2)
    if form_name == "sin":
        return c * np.power(pi1, params["a"]) * np.sin(params["alpha"] * pi2 + params.get("phi", 0.0))
    if form_name == "tanh":
        return c * np.power(pi1, params["a"]) * np.tanh(params["alpha"] * pi2)
    if form_name == "log":
        return c * np.power(pi1, params["a"]) * np.log(pi2)
    if form_name == "pow2":
        return c * np.power(pi1, params["p"]) * np.power(pi2, params["q"]) + params.get("D", 0.0)
    raise ValueError(f"unknown product form {form_name!r}")


def _to_product_rival(
    best: tuple[float, ProductForm, dict[str, float], dict[str, float], tuple[float, ...]] | None,
) -> ProductRival | None:
    if best is None:
        return None
    r2, form, g1, g2, popt = best
    return ProductRival(form_name=form.name, base_group=dict(g1), mod_group=dict(g2),
                        params={n: float(v) for n, v in zip(form.param_names, popt)}, r_squared=r2)


def discover_product_rivals(
    problem: DiscoveryProblem,
    *,
    max_abs_exp: float = DEFAULT_MAX_ABS_EXP,
    step: float = DEFAULT_STEP,
) -> tuple[ProductRival | None, ProductRival | None]:
    """Fit the best product-form rival AND the best pure-power-law rival over the same π-pairs.
    Returns ``(product, powerlaw)`` — the two forms an ``unentschieden`` product verdict cannot
    separate; feed them to `active_resolution.propose_resolution` for the discriminating
    measurement. Either is None if nothing fits or no dimensionless argument exists."""
    y = np.asarray(problem.target.values, dtype=float)
    names, arrs = _source_arrays(problem)
    groups = dimensionless_groups(problem, max_abs_exp=max_abs_exp, step=step)
    if not groups:
        return None, None
    _pair_guard(groups)
    pi_cache = {i: _group_values(g, names, arrs) for i, g in enumerate(groups)}
    log_seed = bool(np.all(y > 0.0))
    product = _best_product(_product_forms(), groups, pi_cache, y, use_log_seed=log_seed)
    powerlaw = _best_product((_pow_rival(),), groups, pi_cache, y, use_log_seed=False)
    return _to_product_rival(product), _to_product_rival(powerlaw)


def evaluate_product_rival(rival: ProductRival | ProductLaw, problem: DiscoveryProblem) -> np.ndarray:
    """Evaluate a fitted product rival (or a discovered :class:`ProductLaw`) on a problem's data —
    both π-groups recomputed from the inputs/constants, then the form applied. No refit. Raises
    ValueError on non-positive magnitudes or an unfitted law (``form_name == 'none'``)."""
    if rival.form_name == "none":
        raise ValueError("cannot evaluate an unfitted product law (form 'none')")
    names, arrs = _source_arrays(problem)
    pi1 = _group_values(rival.base_group, names, arrs)
    pi2 = _group_values(rival.mod_group, names, arrs)
    return _apply_product(rival.form_name, rival.params, pi1, pi2)


def refit_product_rival(rival: ProductRival, problem: DiscoveryProblem) -> ProductRival | None:
    """RE-FIT a product rival's form on its SAME π-pair to a (possibly augmented) problem's data
    — the T-optimality move behind `active_resolution.propose_resolution_robust`: a discriminating
    experiment must defeat the loser EVEN AFTER it re-fits optimally. Returns a freshly fitted
    :class:`ProductRival` or None if it cannot fit."""
    names, arrs = _source_arrays(problem)
    pi1 = _group_values(rival.base_group, names, arrs)
    pi2 = _group_values(rival.mod_group, names, arrs)
    y = np.asarray(problem.target.values, dtype=float)
    forms = {f.name: f for f in (*_product_forms(), _pow_rival())}
    form = forms.get(rival.form_name)
    if form is None:
        return None
    current = tuple(rival.params[n] for n in form.param_names)
    fit = _fit_product(form, pi1, pi2, y, extra_p0=(current,))
    if fit is None:
        return None
    r2, popt = fit
    return ProductRival(form_name=rival.form_name, base_group=dict(rival.base_group),
                        mod_group=dict(rival.mod_group),
                        params={n: float(v) for n, v in zip(form.param_names, popt)}, r_squared=r2)


# ---------------------------------------------------------------------------
# Out-of-sample validation for product laws (6.2 seam)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProductValidation:
    """Out-of-sample fit of a product law: `test_r2` is the law's R² on data it was NOT fitted on
    (the honest number); `generalises` is the verdict; `overfit_gap` = train − test."""

    law: str
    train_r2: float
    test_r2: float
    overfit_gap: float
    generalises: bool
    n_train: int
    n_test: int


def product_out_of_sample_validate(
    problem: DiscoveryProblem,
    *,
    train_fraction: float = 0.6,
    r2_threshold: float = DEFAULT_GENERALISES_R2,
    seed: int = 0,
    **discover_kwargs,
) -> ProductValidation:
    """Out-of-sample validation for a product law: discover it — form, π-pair AND parameters —
    on a TRAIN split only, then score it UNCHANGED on the HELD-OUT split (no refit, no peeking;
    the 6.2 pattern). A real product law transfers; a fit to noise collapses. The train law is
    validated regardless of its verdict — the validator measures generalisation of the best fit,
    the verdict gates the claim. Raises ValueError on too few points or if nothing fits on the
    train split. ``discover_kwargs`` are forwarded to :func:`discover_product_law`."""
    n = len(problem.target.values)
    if n < 4:
        raise ValueError("need at least 4 data points to split train/held-out")
    train_idx, test_idx = _split_indices(n, train_fraction, seed)
    train_law = discover_product_law(_subproblem(problem, train_idx), **discover_kwargs)
    if train_law.form_name == "none":
        raise ValueError("no product form could be fitted on the train split")
    test_problem = _subproblem(problem, test_idx)
    y_test = np.asarray(test_problem.target.values, dtype=float)
    pred = evaluate_product_rival(train_law, test_problem)
    test_r2 = _r2(y_test, pred)
    return ProductValidation(
        law=train_law.expression, train_r2=train_law.r_squared, test_r2=test_r2,
        overfit_gap=train_law.r_squared - test_r2, generalises=test_r2 >= r2_threshold,
        n_train=int(train_idx.shape[0]), n_test=int(test_idx.shape[0]))


# ---------------------------------------------------------------------------
# Part (b): multiplicative minimal-correction  y ≈ y_base · m(π)
# ---------------------------------------------------------------------------

def _modulation_library() -> tuple[TranscendentalForm, ...]:
    """The 6.3 form library for the RATIO fit ``m(π)``, with one deliberate extension: `sin`
    carries a PHASE φ, because the multiplicative residual of an oscillation is generically a
    shifted sinusoid (``cos(ωt) = sin(ωt + π/2)`` — the damped-oscillation case). Deterministic
    starts include φ = 0 and φ = π/2."""

    def exp_model(pi, c, alpha, d):
        return c * np.exp(alpha * pi) + d

    def sin_model(pi, c, alpha, phi, d):
        return c * np.sin(alpha * pi + phi) + d

    def tanh_model(pi, c, alpha, d):
        return c * np.tanh(alpha * pi) + d

    def log_model(pi, c, d):
        return c * np.log(pi) + d

    return (
        TranscendentalForm("exp", exp_model, ("C", "alpha", "D"),
                           ((1.0, 1.0, 0.0), (1.0, -1.0, 0.0))),
        TranscendentalForm("sin", sin_model, ("C", "alpha", "phi", "D"),
                           ((1.0, 1.0, 0.0, 0.0), (1.0, 1.0, 1.5708, 0.0), (1.0, 2.0, 0.0, 0.0))),
        TranscendentalForm("tanh", tanh_model, ("C", "alpha", "D"),
                           ((1.0, 1.0, 0.0), (1.0, -1.0, 0.0))),
        TranscendentalForm("log", log_model, ("C", "D"),
                           ((1.0, 0.0),), needs_positive_pi=True),
    )


def _loo_modulation_r2(form: TranscendentalForm, pi: np.ndarray, ratio: np.ndarray,
                       popt: tuple[float, ...]) -> float:
    """Leave-one-out cross-validated R² of the selected modulation STRUCTURE (form + π-group) on
    the ratio: refit the parameters on n−1 points (seeded deterministically at the full-fit
    optimum), predict the held-out point, accumulate. A real modulation generalises; a form bent
    onto noise collapses out-of-fold. Returns 0.0 (conservative — blocks the claim) when there
    are too few points or any refit fails."""
    n = ratio.shape[0]
    if n < 3:
        return 0.0
    idx = np.arange(n)
    loo = np.empty(n)
    for j in range(n):
        mask = idx != j
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", OptimizeWarning)
                warnings.simplefilter("ignore", RuntimeWarning)
                p, _ = curve_fit(form.model, pi[mask], ratio[mask], p0=list(popt), maxfev=5000)
            loo[j] = float(np.asarray(form.model(np.asarray([pi[j]]), *p))[0])
        except (RuntimeError, ValueError, FloatingPointError):
            return 0.0
    if not np.all(np.isfinite(loo)):
        return 0.0
    return _r2(ratio, loo)


def _format_modulation(form_name: str, group: dict[str, float], params: dict[str, float]) -> str:
    pi = _pi_expr(group)
    c, d = params.get("C", 1.0), params.get("D", 0.0)
    if form_name == "log":
        body = f"{c:.4g} * log({pi})"
    elif form_name == "pow":
        body = f"{c:.4g} * ({pi})^{params.get('beta', 1.0):.4g}"
    else:
        inner = f"{params.get('alpha', 1.0):.4g} * ({pi})"
        if "phi" in params and abs(params["phi"]) > 1e-9:
            inner += f" + {params['phi']:.4g}"
        body = f"{c:.4g} * {form_name}({inner})"
    if abs(d) > 1e-9:
        body += f" + {d:.4g}"
    return body


@dataclass(frozen=True)
class MultiplicativeCorrection:
    """How well a sourced baseline explains the data MULTIPLICATIVELY, and the minimal
    modulation it misses. ``ratio_explained`` is the R² of the fitted modulation on the ratio
    ``y/y_base``; ``powerlaw_ratio_r2`` is the power-modulation rival's R² on the same ratio (a
    transcendental modulation is never claimed when a power modulation is essentially exact);
    ``relative_modulation`` is RMS(m − 1) — how far the modulation departs from "no correction"."""

    baseline_r2: float
    corrected_r2: float
    ratio_explained: float
    loo_r2: float
    relative_modulation: float
    form_name: str
    group: dict[str, float]
    params: dict[str, float]
    powerlaw_ratio_r2: float
    verdict: str
    expression: str


def _no_correction(baseline_r2: float, powerlaw_ratio_r2: float, note: str,
                   ratio_explained: float = 0.0, loo_r2: float = 0.0) -> MultiplicativeCorrection:
    return MultiplicativeCorrection(
        baseline_r2=baseline_r2, corrected_r2=baseline_r2, ratio_explained=ratio_explained,
        loo_r2=loo_r2, relative_modulation=0.0, form_name="none", group={}, params={},
        powerlaw_ratio_r2=powerlaw_ratio_r2, verdict="vollstaendig",
        expression=f"Modulation = ({note})")


def discover_multiplicative_correction(
    problem: DiscoveryProblem,
    baseline_prediction,
    *,
    ratio_bar: float = DEFAULT_RESIDUAL_BAR,
    significance: float = DEFAULT_SIGNIFICANCE,
    loo_bar: float = DEFAULT_LOO_BAR,
    min_base_rel: float = DEFAULT_MIN_BASE_REL,
    r2_threshold: float = DEFAULT_R2_THRESHOLD,
    max_abs_exp: float = DEFAULT_MAX_ABS_EXP,
    step: float = DEFAULT_STEP,
) -> MultiplicativeCorrection:
    """Discover the minimal multiplicative modulation a composed/baseline prediction misses:
    ``y ≈ y_base · m(π)`` with ``m`` a dimensionless form of a π-group.

    Forms the RATIO ``r = y / y_base`` — REFUSED with a ValueError unless ``|y_base| >
    min_base_rel · max|y_base|`` at every point (division at a baseline zero is a numerical
    artefact; no silent masking) — and fits the modulation library plus the power-modulation
    rival ``C·π^β + D`` over all dimensionless groups. Occam guard: when the power modulation is
    essentially exact (≥ `r2_threshold`), it wins over any transcendental — a multiplicative
    correction never over-claims transcendence. A numerically constant ratio is reported as
    ``vollstaendig`` (a pure rescaling is a calibration question, not a π-coupling). Honest
    verdict under the 6.5 gates (δ-asymmetry — a modulation is a CLAIM): ``korrektur_noetig``
    only if ``ratio_explained ≥ ratio_bar`` AND the corrected R² improves by > `significance`
    AND the modulation survives leave-one-out at ≥ `loo_bar`; otherwise ``vollstaendig`` (no
    modulation asserted — within this modulation library). Raises ValueError on a length
    mismatch, a near-zero baseline point, or non-positive source magnitudes.

    Honest data caveat: on an EVENLY spaced input grid a sinusoidal modulation is identified
    only up to aliasing (a property of the data, not of the fit) — irregular sampling pins the
    frequency uniquely."""
    y = np.asarray(problem.target.values, dtype=float)
    y_base = np.asarray(baseline_prediction, dtype=float)
    if y_base.shape != y.shape:
        raise ValueError(f"baseline_prediction length {y_base.shape} != target length {y.shape}")

    peak = float(np.max(np.abs(y_base))) if y_base.size else 0.0
    eps = min_base_rel * peak
    if peak <= 0.0 or np.any(np.abs(y_base) <= eps):
        raise ValueError(
            "Gate-Verweigerung: |y_base| <= eps at some point — the multiplicative residual "
            "y/y_base is numerically meaningless at a baseline zero; use the additive "
            "composition.discover_correction there instead")

    ratio = y / y_base
    baseline_r2 = _r2(y, y_base)

    mean_r = float(np.mean(ratio))
    if float(np.std(ratio)) <= _CONST_RATIO_TOL * max(abs(mean_r), 1.0):
        # A constant ratio is a pure rescaling — it has no π-dependence, so promoting it to a
        # "modulation of a π-group" would be a structural over-claim (any form fits a constant
        # via its offset). Honest output: no coupling claim.
        return _no_correction(baseline_r2, -math.inf,
                              f"konstante Reskalierung ~{mean_r:.6g}, kein π-Kopplungs-Claim")

    groups = dimensionless_groups(problem, max_abs_exp=max_abs_exp, step=step)
    if not groups:
        return _no_correction(baseline_r2, -math.inf, "kein dimensionsloses Argument")

    names, arrs = _source_arrays(problem)
    pi_cache = {i: _group_values(g, names, arrs) for i, g in enumerate(groups)}

    best = _best_over_groups(_modulation_library(), groups, pi_cache, ratio)
    pow_best = _best_over_groups((_baseline_form(),), groups, pi_cache, ratio)
    powerlaw_ratio_r2 = pow_best[0] if pow_best is not None else -math.inf

    if best is None and pow_best is None:
        return _no_correction(baseline_r2, powerlaw_ratio_r2, "keine Form passt")
    # Occam guard: prefer the power modulation whenever it is essentially exact or simply better
    # — a transcendental modulation is only claimed when a power law cannot do the job as well.
    if best is None or (pow_best is not None
                        and (pow_best[0] >= r2_threshold or pow_best[0] > best[0])):
        winner = pow_best
    else:
        winner = best
    assert winner is not None      # one of the two branches above always yields a fit

    r2w, form, group, popt = winner
    pi = _group_values(group, names, arrs)
    m_pred = np.asarray(form.model(pi, *popt), dtype=float)
    ratio_explained = _r2(ratio, m_pred)
    corrected_r2 = _r2(y, y_base * m_pred)
    loo_r2 = _loo_modulation_r2(form, pi, ratio, popt)
    relative_modulation = float(np.sqrt(np.mean((m_pred - 1.0) ** 2)))

    # δ-asymmetry: a modulation is a CLAIM. It must (1) explain almost all of the ratio's
    # structure, (2) meaningfully improve the composed fit, AND (3) survive leave-one-out.
    significant = ((ratio_explained >= ratio_bar)
                   and (corrected_r2 - baseline_r2 > significance)
                   and (loo_r2 >= loo_bar))

    if significant:
        params = {n: float(v) for n, v in zip(form.param_names, popt)}
        expression = (f"{problem.target.name} = (y_base) * "
                      f"[{_format_modulation(form.name, group, params)}]")
        return MultiplicativeCorrection(
            baseline_r2=baseline_r2, corrected_r2=corrected_r2, ratio_explained=ratio_explained,
            loo_r2=loo_r2, relative_modulation=relative_modulation, form_name=form.name,
            group=dict(group), params=params, powerlaw_ratio_r2=powerlaw_ratio_r2,
            verdict="korrektur_noetig", expression=expression)

    return MultiplicativeCorrection(
        baseline_r2=baseline_r2, corrected_r2=baseline_r2, ratio_explained=ratio_explained,
        loo_r2=loo_r2, relative_modulation=0.0, form_name="none", group={}, params={},
        powerlaw_ratio_r2=powerlaw_ratio_r2, verdict="vollstaendig",
        expression="Modulation = (keine signifikante)")
