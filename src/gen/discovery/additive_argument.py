"""additive_argument — one transcendental of an ADDITIVE two-π argument (Frontier 6.8 (A)).

The law family is ``y = C · f(α·π1 + β·π2) + D`` — ONE transcendental whose argument is an
additive combination of TWO dimensionless π-groups (e.g. an Arrhenius-like rate with two
contributions in one exponent, ``k = A·exp(−E1/T − c·P)``). This closes the boundary 6.7 left
open explicitly ("additive π-combinations inside an argument"). Both π-groups come from the null
space of the source dimensional matrix (``A·p = 0``, the same bounded lattice as the whole
frontier); ``C`` alone carries the target's dimension (a fitted model parameter, never a sourced
fact). The fit machinery is REUSED from 6.6/6.7 (`ProductForm`, deterministic `curve_fit`
starts, the same hybrid LM/TRF fitter); for ``f = exp`` with a strictly positive target the
exact log-linear path ``log y = log C + α·π1 + β·π2`` seeds the direct fit (D seeded at 0 — an
offset makes the log path unsound in general, so it is only ever a SEED, never the verdict; any
``y ≤ 0`` refuses the seed, no silent ``abs()``).

Identifiability guards (the design core):

  (a) CANONICAL HOME of ``exp·exp``: ``exp(α·π1 + β·π2) = exp(α·π1)·exp(β·π2)`` — exactly the
      pair 6.7 EXCLUDED from its blind library ("a single exponential of an additive argument —
      outside the two-factor family"). 6.8 is where that law lives: the discovered exp law names
      its product equivalence in ``product_equivalent`` (one law, one canonical representation),
      and 6.7 never issues a rival two-transcendental claim on the same data — no double claim.
  (b) AFFINE RIDGE pairs are skipped: when ``π2`` is (numerically) an affine function of ``π1``
      (pointwise proportional groups from same-unit constants, ``π1 == π2`` itself, a
      constants-only group), the argument ``α·π1 + β·π2`` has fewer identifiable directions than
      parameters — the affine analogue of 6.7's ``exp·exp`` parameter ridge. Such a pair is
      never fitted (`AFFINE_RIDGE_TOL`); data explained by one direction collapses honestly onto
      the single-transcendental rival via the Occam ladder.
  (c) ``β = 0`` collapses on 6.3: a one-contribution law makes the single-transcendental rival
      (phase + offset) essentially exact, so the Occam ladder returns ``unentschieden`` with the
      collapse named — never a two-group over-claim.
  (d) Sign/phase ambiguity is canonicalised: ``sin(−α·π1 − β·π2 + φ) = sin(α·π1 + β·π2 + (π−φ))``
      and ``−sin(u) = sin(u+π)``; ``tanh(−u) = −tanh(u)``. Canonical form: leading coefficient
      ``α > 0`` (sign flip absorbed in phase / in ``C``), ``C > 0`` where a phase can carry the
      sign, phases wrapped to ``[0, 2π)``. ``exp`` has no such ambiguity (all parameters
      identifiable on a non-ridge pair). Pair order is fixed by enumeration (unordered pairs,
      ``i < j``) — no swapped duplicate parameterisation.

Honest gates (the 6.7 duties, extended by one rung): FOUR rivals over the same groups/pairs —
the Occam ladder in increasing structural complexity: pure power law WITH offset
``C·π1^p·π2^q + D`` (at least as flexible in its family: bias toward ``unentschieden``), the
single-transcendental family (6.3 forms + phase + offset), the 6.6 power×transcendental product,
and the 6.7 blind two-transcendental pair. ``bestaetigt`` requires the additive-argument form
essentially exact (R² ≥ the 6.3 bar), EVERY rival NOT, and the 6.7 out-of-sample confirmation:
the winner re-fitted on a deterministic train split must transfer to the held-out points at
≥ `DEFAULT_GENERALISES_R2` — without that OOS edge the verdict stays ``unentschieden``. Ties
feed the 6.4 seam: :func:`discover_additive_argument_rivals` hands an
:class:`AdditiveArgumentRival` plus the strongest simpler evaluable rival to
`active_resolution.propose_resolution`. Noise is never promoted: nothing in noise clears the
0.999 bar, and the OOS confirmation rejects what grazes it.

Honest boundary — (B) true composition ``y = C·f(β·g(α·π)) + D`` was ANALYSED AND REJECTED for
this tour (Ehrlichkeit vor Feature-Zahl); it remains the open frontier, for three concrete,
checked reasons:

  1. DATA-DEPENDENT parameter ridge: wherever the inner ``g`` is exercised only in its (locally)
     linear regime, ``f(β·g(α·π)) ≈ f(β·g'(0)·α·π)`` — only the PRODUCT ``α·β·g'(0)`` is
     identifiable. Unlike 6.7's ``exp·exp`` (a structural ridge, excludable once, up front),
     this ridge depends on the DATA BAND: an honest implementation would need a per-fit proof
     that the inner nonlinearity is actually activated, which no fixed guard provides.
  2. COLLAPSE AMBIGUITY: wherever the outer ``f`` is exercised only in its linear regime,
     ``C·f(β·g(α·π)) + D ≈ C·f(0) + C·f'(0)·β·g(α·π) + D`` — exactly the 6.3 single form. Between
     ridges (1) and collapses (2), almost every finite data band ends ``unentschieden``; the
     family has no honestly winnable case without an active 6.4 measurement placed in a
     precisely calibrated regime.
  3. NO GENERAL CANONICAL FORM: the same law has multiple exact in-family representations —
     e.g. ``exp(−k·sin²θ) = e^(−k/2)·exp((k/2)·cos 2θ)`` (two different ``(f, g, α, β)``
     decompositions of one function). 6.7's canonicalisation rested on a finite list of sine
     identities; for mixed ``f∘g`` no such finite list exists, so "exactly one parameterisation
     per law" — the frontier's anti-double-claim invariant — cannot be guaranteed.

Also open: the full GP search over open form spaces.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .blind_product import (
    DEFAULT_OOS_SEED,
    DEFAULT_OOS_TRAIN_FRACTION,
    _blind_forms,
    _oos_confirm,
)
from .engine import DiscoveryProblem
from .multiterm import DEFAULT_GENERALISES_R2, _split_indices, _subproblem
from .multiplicative import (
    ProductForm,
    ProductRival,
    ProductValidation,
    _best_product,
    _fit_product,
    _modulation_library,
    _pair_guard,
    _pi_expr,
    _pow_rival,
    _product_forms,
    _to_product_rival,
)
from .transcendental import (
    DEFAULT_MAX_ABS_EXP,
    DEFAULT_R2_THRESHOLD,
    DEFAULT_STEP,
    _best_over_groups,
    _group_values,
    _r2,
    _source_arrays,
    dimensionless_groups,
)

#: A π-pair is an AFFINE RIDGE (guard (b)) when the relative residual of the best affine map
#: ``π2 ≈ a·π1 + b`` falls below this: the argument ``α·π1 + β·π2`` then has fewer identifiable
#: directions than parameters. Deliberately tight (float-noise scale): only true degeneracy
#: (proportional groups from same-unit constants, constants-only groups) trips it — a narrow but
#: genuinely curved band does NOT, that case is handled honestly by the Occam ladder instead.
AFFINE_RIDGE_TOL = 1e-8

#: |D| below this fraction of max(1, |C|) counts as "no offset" for naming the exp↔product
#: equivalence (guard (a)): only ``C·exp(α·π1 + β·π2)`` WITHOUT an offset is exactly the product
#: ``C·exp(α·π1)·exp(β·π2)``.
_NEGLIGIBLE_OFFSET_REL = 1e-9

#: A group whose values have relative spread below this is numerically CONSTANT — it belongs in
#: the offset ``D``, never in the argument (its "coefficient" would ride on D, a ridge).
_CONST_GROUP_TOL = 1e-12

_TWO_PI = 2.0 * math.pi

#: The Occam ladder (order = increasing structural complexity): the SIMPLEST rival family that
#: is essentially exact wins over the additive-argument claim. One rung longer than 6.7 — the
#: 6.7 blind two-transcendental product is itself a rival here.
_OCCAM_FAMILIES = ("pow2", "einzel_transzendent", "produkt_potenz", "blind_produkt")


# ---------------------------------------------------------------------------
# The additive-argument form library
# ---------------------------------------------------------------------------

def _additive_forms() -> tuple[ProductForm, ...]:
    """One transcendental of an additive two-π argument. ``f ∈ {exp, sin, tanh}``; ``log`` is
    deliberately ABSENT (``log(α·π1 + β·π2)`` needs a positivity proof of a SIGNED fitted
    combination at every point — not provable up front, so not offered; the honest route for
    log-like data is 6.3/6.6). `sin` carries a phase (``cos = sin(·+π/2)``); all forms carry the
    offset ``D`` exactly like 6.3. No fitted power exponents — the ±MAX_FIT_EXPONENT cap of 6.6
    applies only to the rivals, inherited through the reused fitters."""

    def exp_add(pi1, pi2, c, alpha, beta, d):
        return c * np.exp(alpha * pi1 + beta * pi2) + d

    def sin_add(pi1, pi2, c, alpha, beta, phi, d):
        return c * np.sin(alpha * pi1 + beta * pi2 + phi) + d

    def tanh_add(pi1, pi2, c, alpha, beta, d):
        return c * np.tanh(alpha * pi1 + beta * pi2) + d

    return (
        ProductForm("exp", exp_add, ("C", "alpha", "beta", "D"),
                    ((1.0, 1.0, 1.0, 0.0), (1.0, -1.0, -1.0, 0.0), (1.0, -1.0, 1.0, 0.0),
                     (1.0, 1.0, -1.0, 0.0), (1.0, -0.5, -0.5, 0.0))),
        ProductForm("sin", sin_add, ("C", "alpha", "beta", "phi", "D"),
                    ((1.0, 1.0, 1.0, 0.0, 0.0), (1.0, 2.0, 1.0, 0.0, 0.0),
                     (1.0, 1.0, 0.5, 0.0, 0.0), (1.0, 2.0, 0.5, 1.5708, 0.0))),
        ProductForm("tanh", tanh_add, ("C", "alpha", "beta", "D"),
                    ((1.0, 1.0, 1.0, 0.0), (1.0, -1.0, 1.0, 0.0), (1.0, 1.0, -1.0, 0.0))),
    )


def _is_affine_ridge(pi1: np.ndarray, pi2: np.ndarray) -> bool:
    """Guard (b): True when the pair spans fewer identifiable directions than parameters —
    either group numerically constant, or ``π2`` an affine function of ``π1``."""
    for p in (pi1, pi2):
        if float(np.std(p)) <= _CONST_GROUP_TOL * max(1.0, abs(float(np.mean(p)))):
            return True
    m = np.column_stack([np.ones_like(pi1), pi1])
    coef, *_ = np.linalg.lstsq(m, pi2, rcond=None)
    resid = float(np.linalg.norm(pi2 - m @ coef))
    denom = float(np.linalg.norm(pi2 - float(np.mean(pi2))))
    return resid <= AFFINE_RIDGE_TOL * max(denom, 1e-30)


def _log_seed(pi1: np.ndarray, pi2: np.ndarray, y: np.ndarray) -> tuple[float, float, float, float] | None:
    """Exact linear estimate of (C, α, β) for the exp form at D = 0 on a strictly positive
    target: ``log y = log C + α·π1 + β·π2``. Returns None (seed REFUSED, no silent ``abs()``)
    when the target has any non-positive value. Only ever a SEED for the direct fit — with a
    true offset the log model is wrong, and the direct fit decides."""
    if np.any(y <= 0.0):
        return None
    x = np.column_stack([np.ones_like(y), pi1, pi2])
    try:
        coef, *_ = np.linalg.lstsq(x, np.log(y), rcond=None)
    except np.linalg.LinAlgError:
        return None
    if not np.all(np.isfinite(coef)) or abs(coef[0]) > 700.0:      # exp() would overflow
        return None
    return (float(math.exp(coef[0])), float(coef[1]), float(coef[2]), 0.0)


def _wrap_phase(phi: float) -> float:
    return float(phi % _TWO_PI)


def _canonicalise(form_name: str, params: dict[str, float]) -> dict[str, float]:
    """Guard (d): one canonical parameterisation per law. ``sin``: a global sign flip of the
    argument is absorbed in the phase (``sin(−u+φ) = sin(u+(π−φ))``), a sign of ``C`` in the
    phase (``−sin(u) = sin(u+π)``); ``tanh``: an argument sign flip moves into ``C``
    (``tanh(−u) = −tanh(u)``); ``exp`` needs none. Canonical: leading coefficient α > 0 (or
    β > 0 when α = 0), C > 0 for ``sin``, phases in [0, 2π)."""
    p = dict(params)
    flip = p["alpha"] < 0.0 or (p["alpha"] == 0.0 and p["beta"] < 0.0)
    if form_name == "sin":
        if flip:
            p["alpha"], p["beta"] = -p["alpha"], -p["beta"]
            p["phi"] = math.pi - p["phi"]
        if p["C"] < 0.0:
            p["C"] = -p["C"]
            p["phi"] = p["phi"] + math.pi
        p["phi"] = _wrap_phase(p["phi"])
    elif form_name == "tanh":
        if flip:
            p["alpha"], p["beta"] = -p["alpha"], -p["beta"]
            p["C"] = -p["C"]
    return p


def _apply_additive(form_name: str, params: dict[str, float],
                    pi1: np.ndarray, pi2: np.ndarray) -> np.ndarray:
    """Evaluate a fitted additive-argument form on π-pair values. Raises ValueError on an
    unknown form."""
    c, d = params["C"], params.get("D", 0.0)
    arg = params["alpha"] * pi1 + params["beta"] * pi2
    if form_name == "exp":
        return c * np.exp(arg) + d
    if form_name == "sin":
        return c * np.sin(arg + params.get("phi", 0.0)) + d
    if form_name == "tanh":
        return c * np.tanh(arg) + d
    raise ValueError(f"unknown additive-argument form {form_name!r}")


def _format_additive(target: str, form_name: str, group_f: dict[str, float],
                     group_g: dict[str, float], params: dict[str, float]) -> str:
    c, d = params.get("C", 1.0), params.get("D", 0.0)
    inner = (f"{params['alpha']:.4g} * ({_pi_expr(group_f)}) + "
             f"{params['beta']:.4g} * ({_pi_expr(group_g)})")
    if "phi" in params and abs(params["phi"]) > 1e-9:
        inner += f" + {params['phi']:.4g}"
    body = f"{c:.4g} * {form_name}({inner})"
    if abs(d) > 1e-9:
        body += f" + {d:.4g}"
    return f"{target} = {body}"


def _product_equivalent(group_f: dict[str, float], group_g: dict[str, float],
                        params: dict[str, float]) -> str:
    """Guard (a): the exp law's equivalent product spelling ``C·exp(α·π1)·exp(β·π2)`` — named
    only when the offset is negligible (with D ≠ 0 the identity does not hold)."""
    if abs(params.get("D", 0.0)) > _NEGLIGIBLE_OFFSET_REL * max(1.0, abs(params["C"])):
        return ""
    return (f"{params['C']:.4g} * exp({params['alpha']:.4g} * ({_pi_expr(group_f)})) * "
            f"exp({params['beta']:.4g} * ({_pi_expr(group_g)}))")


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AdditiveArgumentLaw:
    """A discovered additive-argument law and its honest verdict.

    `verdict`: ``bestaetigt`` (additive form essentially exact, ALL four rivals are not, and the
    out-of-sample confirmation passed), ``unentschieden`` (a simpler rival family — named in
    ``occam_winner`` — explains the data just as well, OR the win did not transfer out-of-sample;
    resolve actively via :func:`discover_additive_argument_rivals` + 6.4), or ``widerlegt`` (no
    dimensionless argument, no non-ridge pair, or nothing fits). ``oos_confirm_r2`` is the
    held-out R² of the train-refitted winner (NaN when the confirmation never ran).
    ``product_equivalent`` names the ``exp·exp`` product spelling for an offset-free exp law
    (guard (a)) and is empty otherwise. Parameters are canonical (guard (d))."""

    form_name: str
    group_f: dict[str, float]
    group_g: dict[str, float]
    params: dict[str, float]
    r_squared: float
    powerlaw_r2: float
    single_r2: float
    product_power_r2: float
    blind_r2: float
    oos_confirm_r2: float
    occam_winner: str
    verdict: str
    expression: str
    product_equivalent: str


@dataclass(frozen=True)
class AdditiveArgumentRival:
    """A fitted additive-argument rival that can be EVALUATED on new data — what an
    ``unentschieden`` verdict leaves on the table. `active_resolution` accepts this next to
    ``RivalForm`` (6.3), ``ProductRival`` (6.6) and ``BlindRival`` (6.7) and computes the
    discriminating measurement."""

    form_name: str
    group_f: dict[str, float]
    group_g: dict[str, float]
    params: dict[str, float]
    r_squared: float


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def _best_additive(
    groups: list[dict[str, float]],
    pi_cache: dict[int, np.ndarray],
    y: np.ndarray,
) -> tuple[float, ProductForm, dict[str, float], dict[str, float], tuple[float, ...]] | None:
    """Best (R², form, group_f, group_g, params) over every UNORDERED non-ridge π-pair
    (``i < j`` — the additive argument is symmetric under a pair swap with α↔β, so one
    enumeration order IS the canonicalisation; guard (b) skips ridge pairs)."""
    best: tuple[float, ProductForm, dict[str, float], dict[str, float], tuple[float, ...]] | None = None
    forms = _additive_forms()
    log_seed_ok = bool(np.all(y > 0.0))
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            pi1, pi2 = pi_cache[i], pi_cache[j]
            if _is_affine_ridge(pi1, pi2):
                continue
            for form in forms:
                extra: tuple[tuple[float, ...], ...] = ()
                if form.name == "exp" and log_seed_ok:
                    seed = _log_seed(pi1, pi2, y)
                    if seed is not None:
                        extra = (seed,)
                fit = _fit_product(form, pi1, pi2, y, extra_p0=extra)
                if fit is None:
                    continue
                r2, popt = fit
                if best is None or r2 > best[0]:
                    best = (r2, form, groups[i], groups[j], popt)
    return best


def _occam_winner(powerlaw_r2: float, single_r2: float, product_power_r2: float,
                  blind_r2: float, threshold: float) -> str:
    """The SIMPLEST rival family that is essentially exact (the Occam ladder), or ``""`` if
    none is. A tie with any of these collapses the additive-argument claim."""
    scores = dict(zip(_OCCAM_FAMILIES, (powerlaw_r2, single_r2, product_power_r2, blind_r2), strict=True))
    for family in _OCCAM_FAMILIES:
        if scores[family] >= threshold:
            return family
    return ""


def _no_law(target: str, note: str, *, powerlaw_r2: float = -math.inf,
            single_r2: float = -math.inf, product_power_r2: float = -math.inf,
            blind_r2: float = -math.inf, occam: str = "") -> AdditiveArgumentLaw:
    return AdditiveArgumentLaw(
        form_name="none", group_f={}, group_g={}, params={}, r_squared=-math.inf,
        powerlaw_r2=powerlaw_r2, single_r2=single_r2, product_power_r2=product_power_r2,
        blind_r2=blind_r2, oos_confirm_r2=math.nan, occam_winner=occam, verdict="widerlegt",
        expression=f"{target} = ({note})", product_equivalent="")


def discover_additive_argument(
    problem: DiscoveryProblem,
    *,
    r2_threshold: float = DEFAULT_R2_THRESHOLD,
    max_abs_exp: float = DEFAULT_MAX_ABS_EXP,
    step: float = DEFAULT_STEP,
    oos_bar: float = DEFAULT_GENERALISES_R2,
    train_fraction: float = DEFAULT_OOS_TRAIN_FRACTION,
    seed: int = DEFAULT_OOS_SEED,
) -> AdditiveArgumentLaw:
    """Discover an additive-argument law ``y = C·f(α·π1 + β·π2) + D`` over unordered non-ridge
    dimensionless π-pairs — honestly gated against FOUR rivals and an out-of-sample confirmation.

    Enumerates the π-groups (null space ``A·p = 0``), fits the additive form library against
    every unordered non-ridge pair (deterministic `curve_fit` starts, 6.6 fitter; exact
    log-linear seed for exp on a strictly positive target), and fits the rivals over the SAME
    groups/pairs: the pure power law with offset, the single-transcendental family (phase +
    offset), the 6.6 power×transcendental product and the 6.7 blind two-transcendental pair.
    Verdict: ``bestaetigt`` only if the additive form clears `r2_threshold`, NO rival does
    (Occam ladder), AND the train-refitted winner transfers to the held-out split at ≥
    `oos_bar`; a simpler-family tie or a failed OOS confirmation → ``unentschieden``; otherwise
    ``widerlegt``. Parameters are canonicalised (guard (d)); an offset-free exp law names its
    product equivalence (guard (a)). Raises ValueError on non-positive source magnitudes, an
    over-large lattice, or an over-large pair space."""
    y = np.asarray(problem.target.values, dtype=float)
    names, arrs = _source_arrays(problem)
    groups = dimensionless_groups(problem, max_abs_exp=max_abs_exp, step=step)

    if not groups:
        return _no_law(problem.target.name, "kein dimensionsloses Argument")
    _pair_guard(groups)
    pi_cache = {i: _group_values(g, names, arrs) for i, g in enumerate(groups)}

    powerlaw = _best_product((_pow_rival(),), groups, pi_cache, y, use_log_seed=False)
    powerlaw_r2 = powerlaw[0] if powerlaw is not None else -math.inf
    single = _best_over_groups(_modulation_library(), groups, pi_cache, y)
    single_r2 = single[0] if single is not None else -math.inf
    product_power = _best_product(_product_forms(), groups, pi_cache, y,
                                  use_log_seed=bool(np.all(y > 0.0)))
    product_power_r2 = product_power[0] if product_power is not None else -math.inf
    blind = _best_product(_blind_forms(), groups, pi_cache, y, use_log_seed=False)
    blind_r2 = blind[0] if blind is not None else -math.inf
    occam = _occam_winner(powerlaw_r2, single_r2, product_power_r2, blind_r2, r2_threshold)

    best = _best_additive(groups, pi_cache, y)
    if best is None:
        return _no_law(problem.target.name, "keine Form passt (oder nur Ridge-Paare)",
                       powerlaw_r2=powerlaw_r2, single_r2=single_r2,
                       product_power_r2=product_power_r2, blind_r2=blind_r2, occam=occam)

    r2, form, group_f, group_g, popt = best
    params = _canonicalise(form.name, {n: float(v) for n, v in zip(form.param_names, popt, strict=True)})

    oos_confirm_r2 = math.nan
    if r2 < r2_threshold:
        verdict = "widerlegt"
    elif occam:
        verdict = "unentschieden"       # a simpler family explains it as well — collapse, no claim
    else:
        oos_confirm_r2 = _oos_confirm(form, group_f, group_g, popt, problem,
                                      train_fraction, seed)
        verdict = "bestaetigt" if oos_confirm_r2 >= oos_bar else "unentschieden"

    equivalent = _product_equivalent(group_f, group_g, params) if form.name == "exp" else ""
    return AdditiveArgumentLaw(
        form_name=form.name, group_f=dict(group_f), group_g=dict(group_g), params=params,
        r_squared=r2, powerlaw_r2=powerlaw_r2, single_r2=single_r2,
        product_power_r2=product_power_r2, blind_r2=blind_r2, oos_confirm_r2=oos_confirm_r2,
        occam_winner=occam, verdict=verdict,
        expression=_format_additive(problem.target.name, form.name, group_f, group_g, params),
        product_equivalent=equivalent)


# ---------------------------------------------------------------------------
# Rivals for the active-resolution follow-up (6.4 seam)
# ---------------------------------------------------------------------------

def discover_additive_argument_rivals(
    problem: DiscoveryProblem,
    *,
    max_abs_exp: float = DEFAULT_MAX_ABS_EXP,
    step: float = DEFAULT_STEP,
) -> tuple[AdditiveArgumentRival | None, ProductRival | None]:
    """Fit the best additive-argument rival AND the strongest SIMPLER-family rival over the
    same π-groups. Returns ``(additive, simpler)`` — the pair an ``unentschieden`` verdict
    cannot separate; feed them to `active_resolution.propose_resolution` for the discriminating
    measurement. The simpler rival is the best of the pure power law with offset (``pow2``) and
    the 6.6 power×transcendental product — both evaluable/refittable `ProductRival`s; the 6.6
    ``sin`` form at ``a≈0`` subsumes the single-sinusoid-with-phase family up to its offset, so
    the strongest tie the Occam ladder can name is represented. Either is None if nothing fits
    or no dimensionless argument exists."""
    y = np.asarray(problem.target.values, dtype=float)
    names, arrs = _source_arrays(problem)
    groups = dimensionless_groups(problem, max_abs_exp=max_abs_exp, step=step)
    if not groups:
        return None, None
    _pair_guard(groups)
    pi_cache = {i: _group_values(g, names, arrs) for i, g in enumerate(groups)}
    additive = _best_additive(groups, pi_cache, y)
    powerlaw = _best_product((_pow_rival(),), groups, pi_cache, y, use_log_seed=False)
    product_power = _best_product(_product_forms(), groups, pi_cache, y,
                                  use_log_seed=bool(np.all(y > 0.0)))
    simpler = powerlaw
    if product_power is not None and (simpler is None or product_power[0] > simpler[0]):
        simpler = product_power
    additive_rival: AdditiveArgumentRival | None = None
    if additive is not None:
        r2, form, group_f, group_g, popt = additive
        additive_rival = AdditiveArgumentRival(
            form_name=form.name, group_f=dict(group_f), group_g=dict(group_g),
            params=_canonicalise(form.name, {n: float(v) for n, v in zip(form.param_names, popt, strict=True)}),
            r_squared=r2)
    return additive_rival, _to_product_rival(simpler)


def evaluate_additive_rival(rival: AdditiveArgumentRival | AdditiveArgumentLaw,
                            problem: DiscoveryProblem) -> np.ndarray:
    """Evaluate a fitted additive-argument rival (or a discovered :class:`AdditiveArgumentLaw`)
    on a problem's data — both π-groups recomputed from the inputs/constants, then the form
    applied. No refit. Raises ValueError on non-positive magnitudes or an unfitted law
    (``form_name == 'none'``)."""
    if rival.form_name == "none":
        raise ValueError("cannot evaluate an unfitted additive-argument law (form 'none')")
    names, arrs = _source_arrays(problem)
    pi1 = _group_values(rival.group_f, names, arrs)
    pi2 = _group_values(rival.group_g, names, arrs)
    return _apply_additive(rival.form_name, rival.params, pi1, pi2)


def refit_additive_rival(rival: AdditiveArgumentRival,
                         problem: DiscoveryProblem) -> AdditiveArgumentRival | None:
    """RE-FIT an additive-argument rival's form on its SAME π-pair to a (possibly augmented)
    problem's data — the T-optimality move behind `active_resolution.propose_resolution_robust`.
    Returns a freshly fitted (canonicalised) :class:`AdditiveArgumentRival` or None if it cannot
    fit."""
    names, arrs = _source_arrays(problem)
    pi1 = _group_values(rival.group_f, names, arrs)
    pi2 = _group_values(rival.group_g, names, arrs)
    y = np.asarray(problem.target.values, dtype=float)
    forms = {f.name: f for f in _additive_forms()}
    form = forms.get(rival.form_name)
    if form is None:
        return None
    current = tuple(rival.params[n] for n in form.param_names)
    fit = _fit_product(form, pi1, pi2, y, extra_p0=(current,))
    if fit is None:
        return None
    r2, popt = fit
    return AdditiveArgumentRival(
        form_name=rival.form_name, group_f=dict(rival.group_f), group_g=dict(rival.group_g),
        params=_canonicalise(form.name, {n: float(v) for n, v in zip(form.param_names, popt, strict=True)}),
        r_squared=r2)


# ---------------------------------------------------------------------------
# Out-of-sample validation (6.2 seam)
# ---------------------------------------------------------------------------

def additive_argument_out_of_sample_validate(
    problem: DiscoveryProblem,
    *,
    train_fraction: float = DEFAULT_OOS_TRAIN_FRACTION,
    r2_threshold: float = DEFAULT_GENERALISES_R2,
    seed: int = DEFAULT_OOS_SEED,
    **discover_kwargs,
) -> ProductValidation:
    """Out-of-sample validation for an additive-argument law: discover it — form, π-pair AND
    parameters — on a TRAIN split only, then score it UNCHANGED on the HELD-OUT split (no refit,
    no peeking; the 6.2 pattern). A real law transfers; a fit to noise collapses. The train law
    is validated regardless of its verdict — the validator measures generalisation of the best
    fit, the verdict gates the claim. Raises ValueError on too few points or if nothing fits on
    the train split. ``discover_kwargs`` are forwarded to :func:`discover_additive_argument`."""
    n = len(problem.target.values)
    if n < 4:
        raise ValueError("need at least 4 data points to split train/held-out")
    train_idx, test_idx = _split_indices(n, train_fraction, seed)
    train_law = discover_additive_argument(_subproblem(problem, train_idx), **discover_kwargs)
    if train_law.form_name == "none":
        raise ValueError("no additive-argument form could be fitted on the train split")
    test_problem = _subproblem(problem, test_idx)
    y_test = np.asarray(test_problem.target.values, dtype=float)
    pred = evaluate_additive_rival(train_law, test_problem)
    test_r2 = _r2(y_test, pred)
    return ProductValidation(
        law=train_law.expression, train_r2=train_law.r_squared, test_r2=test_r2,
        overfit_gap=train_law.r_squared - test_r2, generalises=test_r2 >= r2_threshold,
        n_train=int(train_idx.shape[0]), n_test=int(test_idx.shape[0]))
