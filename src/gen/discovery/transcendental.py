"""transcendental — discovery of transcendental laws (exp / log / sin / tanh of a π-group).

The frontier past the power-law/π-group family. A transcendental function is the Taylor series
of a PURE NUMBER, so — by Buckingham-π — it can only take a DIMENSIONLESS argument. That single
physical fact is the whole honest method here:

  1. Build the dimensionless π-groups of the inputs: exponent vectors ``p`` in the NULL SPACE of
     the source dimensional matrix (``A·p = 0``), enumerated over the same bounded lattice as the
     power-law search. ``t/τ`` for a decay, ``L·g/v²`` for a projectile — each is a pure number.
  2. Model the target as ``y = C·f(α·π) + D`` where ``f`` is a dimensionless transcendental,
     ``C`` carries the target's dimension (a fitted scale, a model parameter — never a sourced
     fact), ``α`` scales the argument and ``D`` is an offset. Unlike the power law, this is
     NONLINEAR in ``α`` (it sits inside ``f``), so the fit uses ``scipy.optimize.curve_fit`` from
     fixed, deterministic initial guesses (offline, reproducible).
  3. Gate honestly. A transcendental claim is HIGH novelty, so the δ-asymmetry bites hardest. The
     rival is a power law of a dimensionless group, ``C·π^β + D`` (the SAME family of fits, just a
     power instead of a transcendental). The verdict is ``bestaetigt`` only if the best
     transcendental is essentially exact (R² ≥ the strict bar) AND the best power-of-a-group fit
     over ALL groups is NOT — i.e. no power law of any dimensionless group explains the data that
     well. If a power-of-a-group is also essentially exact, the verdict is ``unentschieden`` (the
     two are indistinguishable on this data) — never a transcendental over-claim for what a power
     law explains just as well.

Honest boundary: this covers ``y = C·f(α·π) + D`` for a single dimensionless group and the form
library {exp, log, sin, tanh}. Products/compositions of transcendentals, and a full symbolic /
genetic search, remain the open frontier.
"""

from __future__ import annotations

import itertools
import math
import warnings
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from scipy.optimize import OptimizeWarning, curve_fit

from .engine import DiscoveryProblem, dimensional_system

#: Lattice for enumerating dimensionless π-groups (null space of the source dimensional matrix).
DEFAULT_MAX_ABS_EXP = 2.0
DEFAULT_STEP = 0.5

#: Strict R² a fit must clear to count as "essentially exact" (high-novelty claim → high bar,
#: δ-asymmetry). A transcendental is ``bestaetigt`` only if it clears this AND the best power law
#: OF THE SAME π-GROUP does NOT — i.e. the transcendental is essentially exact and the simpler
#: power-of-the-group rival is not. If both clear it, the verdict is ``unentschieden`` (a power law
#: explains the data just as well, so no transcendental over-claim).
DEFAULT_R2_THRESHOLD = 0.999

#: ``A·p`` below this norm counts as dimensionless.
_DIM_TOL = 1e-9


@dataclass(frozen=True)
class TranscendentalForm:
    """One dimensionless transcendental ``f`` and its parametric model ``C·f(α·π) + D``.
    `model(pi, *params)` returns the prediction; `p0_list` is the set of deterministic initial
    guesses tried (handles sign ambiguity without randomness)."""

    name: str
    model: Callable[..., np.ndarray]
    param_names: tuple[str, ...]
    p0_list: tuple[tuple[float, ...], ...]
    needs_positive_pi: bool = False


def _form_library() -> tuple[TranscendentalForm, ...]:
    def exp_model(pi, c, alpha, d):
        return c * np.exp(alpha * pi) + d

    def sin_model(pi, c, alpha, d):
        return c * np.sin(alpha * pi) + d

    def tanh_model(pi, c, alpha, d):
        return c * np.tanh(alpha * pi) + d

    def log_model(pi, c, d):
        return c * np.log(pi) + d

    return (
        TranscendentalForm("exp", exp_model, ("C", "alpha", "D"),
                           ((1.0, 1.0, 0.0), (1.0, -1.0, 0.0))),
        TranscendentalForm("sin", sin_model, ("C", "alpha", "D"),
                           ((1.0, 1.0, 0.0), (1.0, 2.0, 0.0))),
        TranscendentalForm("tanh", tanh_model, ("C", "alpha", "D"),
                           ((1.0, 1.0, 0.0), (1.0, -1.0, 0.0))),
        TranscendentalForm("log", log_model, ("C", "D"),
                           ((1.0, 0.0),), needs_positive_pi=True),
    )


def _baseline_form() -> TranscendentalForm:
    """The honest rival a transcendental must beat: a power law of a dimensionless π-group,
    ``C·π^β + D`` (β fitted). It carries the target's dimension in ``C`` exactly like the
    transcendental, so the comparison is like-for-like — a quadratic-in-π is fit perfectly by this,
    a true exponential is not. The discover step takes the best such fit over ALL groups (the
    strongest power-law rival on any dimensionless argument). (Named "pow"; π is a product of
    positive magnitudes, so any real exponent is well-defined.)"""

    def pow_model(pi, c, beta, d):
        return c * np.power(pi, beta) + d

    return TranscendentalForm("pow", pow_model, ("C", "beta", "D"),
                              ((1.0, 1.0, 0.0), (1.0, -1.0, 0.0), (1.0, 2.0, 0.0), (1.0, -2.0, 0.0)),
                              needs_positive_pi=True)


@dataclass(frozen=True)
class TranscendentalLaw:
    """A discovered transcendental law and its honest verdict.

    `verdict`: ``bestaetigt`` (clears the R² bar AND beats the power-law baseline by the margin),
    ``unentschieden`` (fits, but a power law explains it as well — no transcendental over-claim),
    or ``widerlegt`` (no dimensionless argument, or nothing fits)."""

    form_name: str
    group: dict[str, float]
    params: dict[str, float]
    r_squared: float
    powerlaw_r2: float
    verdict: str
    expression: str


def _r2(y: np.ndarray, y_hat: np.ndarray) -> float:
    # zero-variance target (all y identical) after length guard: constant target has no
    # explanatory variation from pi; return 1 only on exact match (via D/offset), else 0
    # (leads to widerlegt -- honest, no overclaim for constant). Guarded upstream now.
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
    if ss_tot <= 0.0:
        return 1.0 if np.allclose(y, y_hat) else 0.0
    return 1.0 - ss_res / ss_tot


def _source_arrays(problem: DiscoveryProblem) -> tuple[list[str], list[np.ndarray]]:
    n = len(problem.target.values)
    if n == 0:
        # match engine.symbolic_regress exactly for consistent loud failure across discovery paths;
        # prevents silent widerlegt or downstream curve_fit/ops on empty arrays
        raise ValueError("target has no samples")
    names: list[str] = []
    arrs: list[np.ndarray] = []
    for v in problem.inputs:
        a = np.asarray(v.values, dtype=float)
        if len(a) != n:
            # match engine length check for early structural error; prevents shape mismatch in pi/y
            # leading to surprising 0.0 R² or curve_fit failures (addresses degenerate + mismatch case)
            raise ValueError(f"input {v.name!r} has {len(a)} samples, target has {n}")
        if not np.all(np.isfinite(a)):
            # non-finite inputs bypass <=0 (nan <=0 is False); would produce nan pi / nan r2 / widerlegt
            # instead of loud error -- L4 correctness gap, 'fail loud on bad data'
            raise ValueError(f"input {v.name!r} has non-finite values; a π-group needs finite positive magnitudes")
        if np.any(a <= 0.0):
            raise ValueError(f"input {v.name!r} has non-positive values; a π-group needs positive magnitudes")
        names.append(v.name)
        arrs.append(a)
    for c in problem.constants:
        if not np.isfinite(c.value):
            raise ValueError(f"constant {c.name!r} has non-finite value; a π-group needs finite positive magnitudes")
        if c.value <= 0.0:
            raise ValueError(f"constant {c.name!r} must be positive for a π-group")
        names.append(c.name)
        arrs.append(np.full(n, float(c.value)))
    return names, arrs


def dimensionless_groups(
    problem: DiscoveryProblem,
    *,
    max_abs_exp: float = DEFAULT_MAX_ABS_EXP,
    step: float = DEFAULT_STEP,
) -> list[dict[str, float]]:
    """Enumerate the dimensionless π-groups of the inputs: every lattice exponent vector ``p``
    with ``A·p = 0`` (the null space of the source dimensional matrix), excluding the trivial
    all-zero vector. Both orientations of a group (``t/τ`` and ``τ/t``) are kept — they are
    different functions of the data and the fit decides which one a transcendental needs."""
    if len(problem.target.values) == 0:
        # zero-sample problems are invalid for discovery; loud error matches engine + _source_arrays
        # (prevents surprising empty results or downstream misuse)
        raise ValueError("target has no samples")
    # Call our _source_arrays (validates lengths, finite, positivity) to guarantee π-group error
    # messages instead of the divergent 'power-law discovery' messages from engine.dimensional_system
    # (which is called next). This keeps all error paths in transcendental consistent.
    _source_arrays(problem)
    a_matrix, _b, names = dimensional_system(problem)
    # arange + round(6) is known numeric-fragile for exact lattice inclusion at boundaries;
    # + small eps + round ensures ±max_abs_exp are present when they should be; tested below.
    eps = 1e-9
    grid = np.round(np.arange(-max_abs_exp, max_abs_exp + step / 2 + eps, step), 6)
    if len(grid) ** len(names) > 200_000:
        raise ValueError("π-group lattice too large; reduce max_abs_exp or raise step")
    groups: list[dict[str, float]] = []
    for combo in itertools.product(grid, repeat=len(names)):
        p = np.array(combo, dtype=float)
        if np.allclose(p, 0.0):
            continue
        if np.linalg.norm(a_matrix @ p) < _DIM_TOL:
            groups.append({n: float(e) for n, e in zip(names, combo)})
    return groups


def _group_values(group: dict[str, float], names: list[str], arrs: list[np.ndarray]) -> np.ndarray:
    pi = np.ones_like(arrs[0])
    for name, arr in zip(names, arrs):
        e = group.get(name, 0.0)
        if e != 0.0:
            pi = pi * np.power(arr, e)
    return pi


def _fit_form(form: TranscendentalForm, pi: np.ndarray, y: np.ndarray) -> tuple[float, tuple[float, ...]] | None:
    if form.needs_positive_pi and np.any(pi <= 0.0):
        return None
    best: tuple[float, tuple[float, ...]] | None = None
    for p0 in form.p0_list:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", OptimizeWarning)
                warnings.simplefilter("ignore", RuntimeWarning)
                popt, _ = curve_fit(form.model, pi, y, p0=list(p0), maxfev=5000)
            pred = form.model(pi, *popt)
            if not np.all(np.isfinite(pred)):
                continue
            r2 = _r2(y, pred)
            if best is None or r2 > best[0]:
                best = (r2, tuple(float(v) for v in popt))
        except (RuntimeError, ValueError, FloatingPointError):
            continue
    return best


def _best_over_groups(
    forms: tuple[TranscendentalForm, ...],
    groups: list[dict[str, float]],
    pi_cache: dict[int, np.ndarray],
    y: np.ndarray,
) -> tuple[float, TranscendentalForm, dict[str, float], tuple[float, ...]] | None:
    """Best (R², form, group, params) over every (group, form, initial-guess) combination."""
    best: tuple[float, TranscendentalForm, dict[str, float], tuple[float, ...]] | None = None
    for i, group in enumerate(groups):
        pi = pi_cache[i]
        for form in forms:
            fit = _fit_form(form, pi, y)
            if fit is None:
                continue
            r2, popt = fit
            if best is None or r2 > best[0]:
                best = (r2, form, group, popt)
    return best


def _format(form_name: str, group: dict[str, float], params: dict[str, float], target: str) -> str:
    pi = " * ".join(n if abs(e - 1.0) < 1e-9 else f"{n}^{e:g}"
                    for n, e in group.items() if abs(e) > 1e-9) or "1"
    c, d = params.get("C", 1.0), params.get("D", 0.0)
    inner = pi if "alpha" not in params else f"{params['alpha']:.4g} * ({pi})"
    body = f"{c:.4g} * {form_name}({inner})"
    if abs(d) > 1e-9:
        body += f" + {d:.4g}"
    return f"{target} = {body}"


def discover_transcendental(
    problem: DiscoveryProblem,
    *,
    r2_threshold: float = DEFAULT_R2_THRESHOLD,
    max_abs_exp: float = DEFAULT_MAX_ABS_EXP,
    step: float = DEFAULT_STEP,
) -> TranscendentalLaw:
    """Discover a transcendental law ``y = C·f(α·π) + D`` over a dimensionless π-group.

    Enumerates the dimensionless groups, fits every transcendental form against each (nonlinear,
    deterministic), and — over the SAME groups — fits the power-of-the-group rival ``C·π^β + D``.
    Honest verdict: ``bestaetigt`` only if the best transcendental is essentially exact
    (R² ≥ `r2_threshold`) AND the best power-of-the-group is NOT (so a power law does not explain
    the data equally well); ``unentschieden`` if both are essentially exact (indistinguishable on
    this data); ``widerlegt`` if no dimensionless argument exists or nothing fits. Raises ValueError
    on target with no samples, non-finite values, non-positive magnitudes or an over-large lattice."""
    y = np.asarray(problem.target.values, dtype=float)
    if not np.all(np.isfinite(y)):
        # non-finite y leads to nan in _r2 or curve_fit exceptions that become widerlegt/None
        # (silent wrong factual); fail loud per review finding
        raise ValueError("target contains non-finite values")
    names, arrs = _source_arrays(problem)
    groups = dimensionless_groups(problem, max_abs_exp=max_abs_exp, step=step)

    if not groups:
        return TranscendentalLaw(
            form_name="none", group={}, params={}, r_squared=-math.inf,
            powerlaw_r2=-math.inf, verdict="widerlegt",
            expression=f"{problem.target.name} = (kein dimensionsloses Argument)")

    pi_cache = {i: _group_values(g, names, arrs) for i, g in enumerate(groups)}
    baseline = _best_over_groups((_baseline_form(),), groups, pi_cache, y)
    powerlaw_r2 = baseline[0] if baseline is not None else -math.inf

    best = _best_over_groups(_form_library(), groups, pi_cache, y)
    if best is None:
        return TranscendentalLaw(
            form_name="none", group={}, params={}, r_squared=-math.inf,
            powerlaw_r2=powerlaw_r2, verdict="widerlegt",
            expression=f"{problem.target.name} = (keine Form passt)")

    r2, form, group, popt = best
    params = {name: float(v) for name, v in zip(form.param_names, popt)}

    if r2 >= r2_threshold and powerlaw_r2 < r2_threshold:
        verdict = "bestaetigt"          # transcendental essentially exact; the power-of-group rival is not
    elif r2 >= r2_threshold:
        verdict = "unentschieden"       # both essentially exact → a power law explains it just as well
    else:
        verdict = "widerlegt"

    return TranscendentalLaw(
        form_name=form.name, group=dict(group), params=params, r_squared=r2,
        powerlaw_r2=powerlaw_r2, verdict=verdict,
        expression=_format(form.name, group, params, problem.target.name))


@dataclass(frozen=True)
class RivalForm:
    """A single fitted rival — a transcendental (exp/sin/tanh/log) OR the power-of-a-group (pow)
    — that can be EVALUATED on new data. This is what an ``unentschieden`` verdict leaves on the
    table: two forms that fit the observed data equally well. ``active_resolution`` uses the pair
    to find where they disagree."""

    form_name: str
    group: dict[str, float]
    params: dict[str, float]
    r_squared: float


def _apply_form(form_name: str, params: dict[str, float], pi: np.ndarray) -> np.ndarray:
    """Evaluate a fitted form on dimensionless-group values ``pi``. The argument scale is named
    ``alpha`` for the transcendentals and ``beta`` for the power; ``log`` has no scale."""
    c = params.get("C", 1.0)
    d = params.get("D", 0.0)
    a = params.get("alpha", params.get("beta", 1.0))
    if form_name == "exp":
        return c * np.exp(a * pi) + d
    if form_name == "sin":
        return c * np.sin(a * pi) + d
    if form_name == "tanh":
        return c * np.tanh(a * pi) + d
    if form_name == "log":
        return c * np.log(pi) + d
    if form_name == "pow":
        return c * np.power(pi, a) + d
    raise ValueError(f"unknown form {form_name!r}")


def _to_rival(best: tuple[float, TranscendentalForm, dict[str, float], tuple[float, ...]] | None) -> RivalForm | None:
    if best is None:
        return None
    r2, form, group, popt = best
    return RivalForm(form_name=form.name, group=dict(group),
                     params={n: float(v) for n, v in zip(form.param_names, popt)}, r_squared=r2)


def discover_rivals(
    problem: DiscoveryProblem,
    *,
    max_abs_exp: float = DEFAULT_MAX_ABS_EXP,
    step: float = DEFAULT_STEP,
) -> tuple[RivalForm | None, RivalForm | None]:
    """Fit the best transcendental rival AND the best power-of-a-group rival over the same
    dimensionless groups. Returns ``(transcendental, powerlaw)`` — the two forms an
    ``unentschieden`` verdict cannot separate. Either is ``None`` if nothing fits or there is no
    dimensionless argument. Raises ValueError on target with no samples or non-positive magnitudes."""
    y = np.asarray(problem.target.values, dtype=float)
    if not np.all(np.isfinite(y)):
        # non-finite y leads to nan in _r2 or curve_fit exceptions that become widerlegt/None
        # (silent wrong factual); fail loud per review finding
        raise ValueError("target contains non-finite values")
    names, arrs = _source_arrays(problem)
    groups = dimensionless_groups(problem, max_abs_exp=max_abs_exp, step=step)
    if not groups:
        return None, None
    pi_cache = {i: _group_values(g, names, arrs) for i, g in enumerate(groups)}
    transcendental = _best_over_groups(_form_library(), groups, pi_cache, y)
    powerlaw = _best_over_groups((_baseline_form(),), groups, pi_cache, y)
    return _to_rival(transcendental), _to_rival(powerlaw)


def evaluate_rival(rival: RivalForm, problem: DiscoveryProblem) -> np.ndarray:
    """Evaluate a fitted rival on a problem's data — its π-group recomputed from the inputs/
    constants, then the form applied. No refit. Raises ValueError on target with no samples or non-positive magnitudes."""
    names, arrs = _source_arrays(problem)
    pi = _group_values(rival.group, names, arrs)
    return _apply_form(rival.form_name, rival.params, pi)


def refit_rival(rival: RivalForm, problem: DiscoveryProblem) -> RivalForm | None:
    """RE-FIT a rival's form on its SAME π-group to a (possibly augmented) problem's data — letting the
    rival bend maximally to the new points. Returns a freshly-fitted ``RivalForm`` (new params + R²) or
    ``None`` if it cannot fit. This is the T-optimality move (FORSCHUNG §A4): a discriminating experiment
    must defeat the losing rival EVEN AFTER it re-fits optimally to the proposed data. Raises ValueError on
    target with no samples or non-positive magnitudes."""
    names, arrs = _source_arrays(problem)
    pi = _group_values(rival.group, names, arrs)
    y = np.asarray(problem.target.values, dtype=float)
    if not np.all(np.isfinite(y)):
        # non-finite y leads to nan in _r2 or curve_fit exceptions that become widerlegt/None
        # (silent wrong factual); fail loud per review finding
        raise ValueError("target contains non-finite values")
    forms = {f.name: f for f in (*_form_library(), _baseline_form())}
    form = forms.get(rival.form_name)
    if form is None:
        return None
    fit = _fit_form(form, pi, y)
    if fit is None:
        return None
    r2, popt = fit
    return RivalForm(form_name=rival.form_name, group=dict(rival.group),
                     params={n: float(v) for n, v in zip(form.param_names, popt)}, r_squared=r2)
