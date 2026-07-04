"""blind_product — blind discovery of two-transcendental products (Frontier 6.7).

The law family is ``y = C · f(α·π1) · g(β·π2 [+ φ])`` — e.g. the damped oscillation
``A·e^(−ζt)·cos(ωt)`` — discovered BLIND, with no declared baseline. This closes the boundary
6.6 left open explicitly: `multiplicative` recovers the damped oscillation only as a
declared-baseline ratio correction (baseline ``A·e^(−ζt)`` → modulation ``cos(ωt)``); here the
product of two transcendentals is a first-class candidate law. Both arguments are dimensionless
π-groups from the null space of the source dimensional matrix (``A·p = 0``, the same bounded
lattice as the whole frontier); ``C`` alone carries the target's dimension (a fitted model
parameter, never a sourced fact). The fit machinery is REUSED from 6.6 (`ProductForm`,
deterministic `curve_fit` starts, the same hybrid LM/TRF fitter) — the blind forms carry NO
fitted power exponent, so the ±MAX_FIT_EXPONENT cap of 6.6 applies only to the rivals, which
inherit it through the reused fitters.

Identifiability guards (the design core — a two-transcendental claim is the highest-novelty
claim of the frontier so far, and the family is full of degeneracies):

  (a) ``exp·exp`` is EXCLUDED from the pair library: ``exp(u)·exp(v) = exp(u+v)`` is structurally
      ONE exponential. On a shared π-argument only ``α+β`` is identifiable (a parameter ridge,
      not a law); on distinct π-arguments the product is a single exponential of an additive
      argument — outside the two-factor family either way. Data that IS a pure exponential
      collapses honestly onto the single-transcendental rival (``occam_winner``), never onto a
      two-factor double-claim.
  (b) Product formulas (``sin·cos = ½[sin(a+b)+sin(a−b)]`` etc.) and flat factors (``exp`` with
      α≈0, saturated ``tanh``) reduce a "product" to what ONE transcendental already represents.
      The Occam gate handles this structurally: the single-transcendental rival library is the
      6.6 modulation library — WITH phase in ``sin`` and an offset ``D`` the blind form does not
      get — so anything one transcendental can express (a pure cosine included) makes that rival
      essentially exact → verdict ``unentschieden`` with the collapse named in ``occam_winner``,
      never a 6.7 over-claim.
  (c) Sign/phase ambiguity is canonicalised: ``−cos = cos(·+π)``, ``sin(−βx+φ) = sin(βx+π−φ)``,
      ``tanh(−x) = −tanh(x)``. Canonical form: ``C > 0`` where a phase can absorb the sign, sine
      frequencies ``β > 0``, ``tanh`` frequency ``> 0`` (sign moved into ``C``), phases wrapped
      to ``[0, 2π)`` — exactly one parameterisation per law, no ambiguous duplicate claims.

Honest gates (the 6.6 duties, tightened): THREE rivals over the same π-groups/pairs — the pure
power law WITH offset ``C·π1^p·π2^q + D`` (at least as flexible as the blind form: bias toward
``unentschieden``, never toward an over-claim), the single-transcendental family (6.3 forms +
phase + offset), and the 6.6 power×transcendental product. ``bestaetigt`` requires the blind
form essentially exact (R² ≥ the 6.3 bar) AND every rival NOT — and additionally an
OUT-OF-SAMPLE confirmation: the winning form is re-fitted on a deterministic train split and
must transfer to the held-out points at ≥ `DEFAULT_GENERALISES_R2` (its in-sample win alone is
not enough; without the OOS edge the verdict stays ``unentschieden``). Ties feed the 6.4 seam:
:func:`discover_blind_rivals` hands a :class:`BlindRival` plus the power-law rival to
`active_resolution.propose_resolution` for the discriminating measurement. Noise is never
promoted: nothing in noise clears the 0.999 bar, and the OOS confirmation rejects what grazes it.

Honest data caveat (as in 6.6): on an EVENLY spaced input grid a sinusoidal factor is identified
only up to aliasing — a property of the data, not of the fit; irregular sampling pins the
frequency uniquely (the acceptance tests sample irregularly).

Honest boundary: compositions of transcendentals INSIDE one another (``f(g(·))``), additive
π-combinations inside an argument (``exp(α·π1 + β·π2)`` — one transcendental of a non-monomial
argument, see guard (a)), and the full GP search over open form spaces remain the open frontier.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

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

#: Deterministic split for the out-of-sample confirmation inside the verdict: the winning blind
#: form is re-fitted on this fraction of the points and must transfer to the held-out rest.
#: Same fraction/seed convention as the 6.2/6.6 validators — reproducible, no peeking.
DEFAULT_OOS_TRAIN_FRACTION = 0.6
DEFAULT_OOS_SEED = 0

_TWO_PI = 2.0 * math.pi

#: The Occam ladder: the simplest rival family that is essentially exact wins over the blind
#: two-transcendental form. Order = increasing structural complexity (pure power law → one
#: transcendental → power×transcendental product → two transcendentals).
_OCCAM_FAMILIES = ("pow2", "einzel_transzendent", "produkt_potenz")


# ---------------------------------------------------------------------------
# The blind two-transcendental pair library
# ---------------------------------------------------------------------------

def _blind_forms() -> tuple[ProductForm, ...]:
    """The two-transcendental pair library. ``exp·exp`` is deliberately ABSENT (guard (a):
    structurally one exponential, a parameter ridge on a shared argument). The sine factors
    carry a phase (``cos = sin(·+π/2)`` — without it the flagship damped oscillation would be
    unrepresentable). No fitted power exponents by design — a power×transcendental product is
    the 6.6 family and serves as a RIVAL here, not as a candidate."""

    def exp_sin(pi1, pi2, c, alpha, beta, phi):
        return c * np.exp(alpha * pi1) * np.sin(beta * pi2 + phi)

    def exp_tanh(pi1, pi2, c, alpha, beta):
        return c * np.exp(alpha * pi1) * np.tanh(beta * pi2)

    def sin_sin(pi1, pi2, c, alpha, phi, beta, psi):
        return c * np.sin(alpha * pi1 + phi) * np.sin(beta * pi2 + psi)

    return (
        ProductForm("exp_sin", exp_sin, ("C", "alpha", "beta", "phi"),
                    ((1.0, -1.0, 1.0, 0.0), (1.0, -1.0, 2.0, 1.5708), (1.0, 1.0, 2.0, 1.5708),
                     (1.0, -1.0, 3.0, 1.5708), (1.0, -0.5, 1.0, 0.0))),
        ProductForm("exp_tanh", exp_tanh, ("C", "alpha", "beta"),
                    ((1.0, -1.0, 1.0), (1.0, 1.0, 1.0), (1.0, -1.0, 5.0))),
        ProductForm("sin_sin", sin_sin, ("C", "alpha", "phi", "beta", "psi"),
                    ((1.0, 1.0, 0.0, 2.0, 0.0), (1.0, 1.0, 1.5708, 3.0, 1.5708))),
    )


def _wrap_phase(phi: float) -> float:
    return float(phi % _TWO_PI)


def _canonicalise(pair_name: str, params: dict[str, float]) -> dict[str, float]:
    """Guard (c): one canonical parameterisation per law. Sine identities used:
    ``sin(−βx+φ) = sin(βx + (π−φ))`` (frequency sign flip, no scale flip) and
    ``−sin(u) = sin(u+π)`` (scale sign absorbed into the phase); ``tanh(−x) = −tanh(x)``
    (frequency sign moved into ``C``). Phases wrapped to ``[0, 2π)``."""
    p = dict(params)
    if pair_name == "exp_sin":
        if p["beta"] < 0.0:
            p["beta"] = -p["beta"]
            p["phi"] = math.pi - p["phi"]
        if p["C"] < 0.0:
            p["C"] = -p["C"]
            p["phi"] = p["phi"] + math.pi
        p["phi"] = _wrap_phase(p["phi"])
    elif pair_name == "exp_tanh":
        if p["beta"] < 0.0:
            p["beta"] = -p["beta"]
            p["C"] = -p["C"]
    elif pair_name == "sin_sin":
        for freq, phase in (("alpha", "phi"), ("beta", "psi")):
            if p[freq] < 0.0:
                p[freq] = -p[freq]
                p[phase] = math.pi - p[phase]
        if p["C"] < 0.0:
            p["C"] = -p["C"]
            p["phi"] = p["phi"] + math.pi
        p["phi"] = _wrap_phase(p["phi"])
        p["psi"] = _wrap_phase(p["psi"])
    return p


def _apply_blind(pair_name: str, params: dict[str, float],
                 pi1: np.ndarray, pi2: np.ndarray) -> np.ndarray:
    """Evaluate a fitted blind pair form on π-pair values. Raises ValueError on an unknown pair."""
    c = params["C"]
    if pair_name == "exp_sin":
        return c * np.exp(params["alpha"] * pi1) * np.sin(params["beta"] * pi2 + params["phi"])
    if pair_name == "exp_tanh":
        return c * np.exp(params["alpha"] * pi1) * np.tanh(params["beta"] * pi2)
    if pair_name == "sin_sin":
        return (c * np.sin(params["alpha"] * pi1 + params["phi"])
                * np.sin(params["beta"] * pi2 + params["psi"]))
    raise ValueError(f"unknown blind pair form {pair_name!r}")


def _format_blind(target: str, pair_name: str, group_f: dict[str, float],
                  group_g: dict[str, float], params: dict[str, float]) -> str:
    c = params.get("C", 1.0)
    pi1, pi2 = _pi_expr(group_f), _pi_expr(group_g)
    if pair_name == "exp_sin":
        body = (f"exp({params['alpha']:.4g} * ({pi1})) * "
                f"sin({params['beta']:.4g} * ({pi2}) + {params['phi']:.4g})")
    elif pair_name == "exp_tanh":
        body = (f"exp({params['alpha']:.4g} * ({pi1})) * "
                f"tanh({params['beta']:.4g} * ({pi2}))")
    elif pair_name == "sin_sin":
        body = (f"sin({params['alpha']:.4g} * ({pi1}) + {params['phi']:.4g}) * "
                f"sin({params['beta']:.4g} * ({pi2}) + {params['psi']:.4g})")
    else:
        body = pair_name
    return f"{target} = {c:.4g} * {body}"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BlindProductLaw:
    """A blindly discovered two-transcendental product law and its honest verdict.

    `verdict`: ``bestaetigt`` (blind form essentially exact, ALL three rivals are not, and the
    out-of-sample confirmation passed), ``unentschieden`` (a simpler rival family — named in
    ``occam_winner`` — explains the data just as well, OR the blind win did not transfer
    out-of-sample; resolve actively via :func:`discover_blind_rivals` + 6.4), or ``widerlegt``
    (no dimensionless argument, or nothing fits). ``oos_confirm_r2`` is the held-out R² of the
    train-refitted winner (NaN when the confirmation step never ran). Parameters are canonical
    (guard (c))."""

    pair_name: str
    group_f: dict[str, float]
    group_g: dict[str, float]
    params: dict[str, float]
    r_squared: float
    powerlaw_r2: float
    single_r2: float
    product_power_r2: float
    oos_confirm_r2: float
    occam_winner: str
    verdict: str
    expression: str


@dataclass(frozen=True)
class BlindRival:
    """A fitted blind two-transcendental rival that can be EVALUATED on new data — what an
    ``unentschieden`` blind verdict leaves on the table. `active_resolution` accepts this next
    to ``RivalForm`` (6.3) and ``ProductRival`` (6.6) and computes the discriminating
    measurement."""

    pair_name: str
    group_f: dict[str, float]
    group_g: dict[str, float]
    params: dict[str, float]
    r_squared: float

    @property
    def form_name(self) -> str:
        """Alias for `active_resolution`'s human-readable spec strings — the 6.3/6.6 rival
        types call this field ``form_name``."""
        return self.pair_name


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def _occam_winner(powerlaw_r2: float, single_r2: float, product_power_r2: float,
                  threshold: float) -> str:
    """The SIMPLEST rival family that is essentially exact (guard (b) — the Occam ladder), or
    ``""`` if none is. A tie with any of these collapses the two-transcendental claim."""
    scores = dict(zip(_OCCAM_FAMILIES, (powerlaw_r2, single_r2, product_power_r2)))
    for family in _OCCAM_FAMILIES:
        if scores[family] >= threshold:
            return family
    return ""


def _oos_confirm(form: ProductForm, group_f: dict[str, float], group_g: dict[str, float],
                 popt: tuple[float, ...], problem: DiscoveryProblem,
                 train_fraction: float, seed: int) -> float:
    """Held-out R² of the winning blind form: re-fit its parameters on a deterministic train
    split (seeded at the full-fit optimum), score UNCHANGED on the held-out points. Returns
    ``-inf`` (conservative — blocks ``bestaetigt``) when there are too few points to split or
    the train re-fit fails."""
    n = len(problem.target.values)
    if n < 4:
        return -math.inf
    train_idx, test_idx = _split_indices(n, train_fraction, seed)
    train, test = _subproblem(problem, train_idx), _subproblem(problem, test_idx)

    names_tr, arrs_tr = _source_arrays(train)
    fit = _fit_product(form,
                       _group_values(group_f, names_tr, arrs_tr),
                       _group_values(group_g, names_tr, arrs_tr),
                       np.asarray(train.target.values, dtype=float),
                       extra_p0=(popt,))
    if fit is None:
        return -math.inf
    _, p_train = fit

    names_te, arrs_te = _source_arrays(test)
    pred = form.model(_group_values(group_f, names_te, arrs_te),
                      _group_values(group_g, names_te, arrs_te), *p_train)
    if not np.all(np.isfinite(pred)):
        return -math.inf
    return _r2(np.asarray(test.target.values, dtype=float), np.asarray(pred, dtype=float))


def _no_law(target: str, note: str, *, powerlaw_r2: float = -math.inf,
            single_r2: float = -math.inf, product_power_r2: float = -math.inf,
            occam: str = "") -> BlindProductLaw:
    return BlindProductLaw(
        pair_name="none", group_f={}, group_g={}, params={}, r_squared=-math.inf,
        powerlaw_r2=powerlaw_r2, single_r2=single_r2, product_power_r2=product_power_r2,
        oos_confirm_r2=math.nan, occam_winner=occam, verdict="widerlegt",
        expression=f"{target} = ({note})")


def discover_blind_product(
    problem: DiscoveryProblem,
    *,
    r2_threshold: float = DEFAULT_R2_THRESHOLD,
    max_abs_exp: float = DEFAULT_MAX_ABS_EXP,
    step: float = DEFAULT_STEP,
    oos_bar: float = DEFAULT_GENERALISES_R2,
    train_fraction: float = DEFAULT_OOS_TRAIN_FRACTION,
    seed: int = DEFAULT_OOS_SEED,
) -> BlindProductLaw:
    """Blindly discover a two-transcendental product law ``y = C·f(α·π1)·g(β·π2 [+φ])`` over
    dimensionless π-pairs — no declared baseline — honestly gated against THREE rivals and an
    out-of-sample confirmation.

    Enumerates the π-groups (null space ``A·p = 0``), fits the blind pair library against every
    ordered pair (deterministic `curve_fit` starts, 6.6 fitter), and fits the rivals over the
    SAME groups/pairs: the pure power law with offset, the single-transcendental family
    (with phase + offset), and the 6.6 power×transcendental product. Verdict: ``bestaetigt``
    only if the blind form clears `r2_threshold`, NO rival does (Occam ladder, guard (b)), AND
    the train-refitted winner transfers to the held-out split at ≥ `oos_bar`; a simpler-family
    tie or a failed OOS confirmation → ``unentschieden``; otherwise ``widerlegt``. Parameters
    are canonicalised (guard (c)). Raises ValueError on non-positive source magnitudes, an
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
    occam = _occam_winner(powerlaw_r2, single_r2, product_power_r2, r2_threshold)

    best = _best_product(_blind_forms(), groups, pi_cache, y, use_log_seed=False)
    if best is None:
        return _no_law(problem.target.name, "keine Form passt", powerlaw_r2=powerlaw_r2,
                       single_r2=single_r2, product_power_r2=product_power_r2, occam=occam)

    r2, form, group_f, group_g, popt = best
    params = _canonicalise(form.name, {n: float(v) for n, v in zip(form.param_names, popt)})

    oos_confirm_r2 = math.nan
    if r2 < r2_threshold:
        verdict = "widerlegt"
    elif occam:
        verdict = "unentschieden"       # a simpler family explains it as well — collapse, no claim
    else:
        oos_confirm_r2 = _oos_confirm(form, group_f, group_g, popt, problem,
                                      train_fraction, seed)
        verdict = "bestaetigt" if oos_confirm_r2 >= oos_bar else "unentschieden"

    return BlindProductLaw(
        pair_name=form.name, group_f=dict(group_f), group_g=dict(group_g), params=params,
        r_squared=r2, powerlaw_r2=powerlaw_r2, single_r2=single_r2,
        product_power_r2=product_power_r2, oos_confirm_r2=oos_confirm_r2,
        occam_winner=occam, verdict=verdict,
        expression=_format_blind(problem.target.name, form.name, group_f, group_g, params))


# ---------------------------------------------------------------------------
# Rivals for the active-resolution follow-up (6.4 seam)
# ---------------------------------------------------------------------------

def discover_blind_rivals(
    problem: DiscoveryProblem,
    *,
    max_abs_exp: float = DEFAULT_MAX_ABS_EXP,
    step: float = DEFAULT_STEP,
) -> tuple[BlindRival | None, ProductRival | None]:
    """Fit the best blind two-transcendental rival AND the strongest SIMPLER-family rival over
    the same π-pairs. Returns ``(blind, simpler)`` — the pair an ``unentschieden`` blind verdict
    cannot separate; feed them to `active_resolution.propose_resolution` for the discriminating
    measurement. The simpler rival is the better of the pure power law with offset (``pow2``)
    and the 6.6 power×transcendental product — both evaluable/refittable `ProductRival`s; the
    6.6 ``sin`` form at ``a≈0`` subsumes the single-sinusoid-with-phase family up to its offset,
    so the strongest tie the Occam ladder can name is represented. Either is None if nothing
    fits or no dimensionless argument exists."""
    y = np.asarray(problem.target.values, dtype=float)
    names, arrs = _source_arrays(problem)
    groups = dimensionless_groups(problem, max_abs_exp=max_abs_exp, step=step)
    if not groups:
        return None, None
    _pair_guard(groups)
    pi_cache = {i: _group_values(g, names, arrs) for i, g in enumerate(groups)}
    blind = _best_product(_blind_forms(), groups, pi_cache, y, use_log_seed=False)
    powerlaw = _best_product((_pow_rival(),), groups, pi_cache, y, use_log_seed=False)
    product_power = _best_product(_product_forms(), groups, pi_cache, y,
                                  use_log_seed=bool(np.all(y > 0.0)))
    simpler = powerlaw
    if product_power is not None and (simpler is None or product_power[0] > simpler[0]):
        simpler = product_power
    blind_rival: BlindRival | None = None
    if blind is not None:
        r2, form, group_f, group_g, popt = blind
        blind_rival = BlindRival(
            pair_name=form.name, group_f=dict(group_f), group_g=dict(group_g),
            params=_canonicalise(form.name, {n: float(v) for n, v in zip(form.param_names, popt)}),
            r_squared=r2)
    return blind_rival, _to_product_rival(simpler)


def evaluate_blind_rival(rival: BlindRival | BlindProductLaw,
                         problem: DiscoveryProblem) -> np.ndarray:
    """Evaluate a fitted blind rival (or a discovered :class:`BlindProductLaw`) on a problem's
    data — both π-groups recomputed from the inputs/constants, then the pair form applied. No
    refit. Raises ValueError on non-positive magnitudes or an unfitted law
    (``pair_name == 'none'``)."""
    if rival.pair_name == "none":
        raise ValueError("cannot evaluate an unfitted blind product law (pair 'none')")
    names, arrs = _source_arrays(problem)
    pi1 = _group_values(rival.group_f, names, arrs)
    pi2 = _group_values(rival.group_g, names, arrs)
    return _apply_blind(rival.pair_name, rival.params, pi1, pi2)


def refit_blind_rival(rival: BlindRival, problem: DiscoveryProblem) -> BlindRival | None:
    """RE-FIT a blind rival's pair form on its SAME π-pair to a (possibly augmented) problem's
    data — the T-optimality move behind `active_resolution.propose_resolution_robust`. Returns a
    freshly fitted (canonicalised) :class:`BlindRival` or None if it cannot fit."""
    names, arrs = _source_arrays(problem)
    pi1 = _group_values(rival.group_f, names, arrs)
    pi2 = _group_values(rival.group_g, names, arrs)
    y = np.asarray(problem.target.values, dtype=float)
    forms = {f.name: f for f in _blind_forms()}
    form = forms.get(rival.pair_name)
    if form is None:
        return None
    current = tuple(rival.params[n] for n in form.param_names)
    fit = _fit_product(form, pi1, pi2, y, extra_p0=(current,))
    if fit is None:
        return None
    r2, popt = fit
    return BlindRival(
        pair_name=rival.pair_name, group_f=dict(rival.group_f), group_g=dict(rival.group_g),
        params=_canonicalise(form.name, {n: float(v) for n, v in zip(form.param_names, popt)}),
        r_squared=r2)


# ---------------------------------------------------------------------------
# Out-of-sample validation (6.2 seam)
# ---------------------------------------------------------------------------

def blind_product_out_of_sample_validate(
    problem: DiscoveryProblem,
    *,
    train_fraction: float = DEFAULT_OOS_TRAIN_FRACTION,
    r2_threshold: float = DEFAULT_GENERALISES_R2,
    seed: int = DEFAULT_OOS_SEED,
    **discover_kwargs,
) -> ProductValidation:
    """Out-of-sample validation for a blind product law: discover it — pair form, π-pair AND
    parameters — on a TRAIN split only, then score it UNCHANGED on the HELD-OUT split (no refit,
    no peeking; the 6.2 pattern). A real two-transcendental law transfers; a fit to noise
    collapses. The train law is validated regardless of its verdict — the validator measures
    generalisation of the best fit, the verdict gates the claim. Raises ValueError on too few
    points or if nothing fits on the train split. ``discover_kwargs`` are forwarded to
    :func:`discover_blind_product`."""
    n = len(problem.target.values)
    if n < 4:
        raise ValueError("need at least 4 data points to split train/held-out")
    train_idx, test_idx = _split_indices(n, train_fraction, seed)
    train_law = discover_blind_product(_subproblem(problem, train_idx), **discover_kwargs)
    if train_law.pair_name == "none":
        raise ValueError("no blind product form could be fitted on the train split")
    test_problem = _subproblem(problem, test_idx)
    y_test = np.asarray(test_problem.target.values, dtype=float)
    pred = evaluate_blind_rival(train_law, test_problem)
    test_r2 = _r2(y_test, pred)
    return ProductValidation(
        law=train_law.expression, train_r2=train_law.r_squared, test_r2=test_r2,
        overfit_gap=train_law.r_squared - test_r2, generalises=test_r2 >= r2_threshold,
        n_train=int(train_idx.shape[0]), n_test=int(test_idx.shape[0]))
