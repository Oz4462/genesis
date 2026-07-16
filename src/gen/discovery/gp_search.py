"""gp_search — the GENESIS-disciplined FULL GP search over open form spaces (Frontier 7).

``symbolic_search`` (Roadmap B0) is the raw open-form genetic-programming core: seeded evolution
over expression trees with fit/dummy/out-of-sample gates. It is honest but UNIT-BLIND — on a
dimensionful problem it would happily evolve ``sin(a)`` of a length. This module closes the last
declared frontier by putting the two GENESIS disciplines on top:

1. π-SCAFFOLD — dimensional typing at TREE level. The particular solution of ``A·p = b`` gives
   the target-dimension carrier ``base = Π sourceᵢ^pᵢ`` (a power-law product, exactly the
   engine's move); the null space of ``A`` gives the dimensionless π-groups (the same bounded
   lattice as the 6.x frontiers, preferring integer, positive, low-|p| groups; independent
   groups only). GP then evolves ONLY over the dimensionless columns ``π₁…πₖ`` against the
   scaled target ``ỹ = y / base``. Every genome — and every crossover/mutation product — is a
   function of pure numbers, so every tree is dimensionally consistent BY CONSTRUCTION: the
   ``tournament.py`` null-space move lifted from exponent vectors to expression trees. A
   determined system (Kepler) has an EMPTY open-form space beyond ``C·base`` — that is said
   honestly, never padded with a tree.

2. OCCAM RIVAL LADDER — GP is the most flexible (and therefore most overfit-prone) search mode,
   so it carries the HIGHEST evidence burden: before GP may claim anything, the simpler families
   run, simplest first — power law (the engine's own gate), power-of-a-π-group (the 6.3 baseline
   rival), additive multiterm (6.1, only with its 6.2 out-of-sample validation), transcendental
   (6.3), product (6.6), blind product (6.7), additive argument (6.8). If ANY simpler family is
   essentially exact (R² ≥ the shared 0.999 bar), the outcome COLLAPSES onto it: the collapse to
   the power law is gate-confirmed (``bestaetigt`` by ``judge_candidate``'s gates inside
   ``discover_new_formulas``); a collapse to any other family is ``unentschieden`` with the
   family named in ``occam_winner`` — the family's own discover_* is the place for its full
   claim. The ladder short-circuits (no GP budget is burned on a solved problem).

3. GP NEVER CONFIRMS — the surrogate principle (Phase 2). The evolved candidate goes through
   ``gp_discover``'s gates on the scaffolded problem: δ-raised fit bar (a bigger tree must fit
   better), planted-dummy exclusion and the out-of-sample split (the SRBench hygiene adapted to
   open forms). ``bestaetigt`` requires those gates AND an empty ladder — never fit alone.

Determinism (Prinzip 5): all randomness flows from ``numpy.random.default_rng(seed)`` inside the
GP core; the ladder is deterministic. Same seed + same data → byte-identical outcome.

Honest boundary: the reachable space is {rational/algebraic/transcendental closed forms of
lattice-representable π-groups within ``GPConfig``'s depth/size}; nested transcendental
composition ``f(g(·))`` stays REJECTED (the three 6.8(B) reasons apply unchanged — GP would only
add unidentifiable parametrisations of it); the reported R² of a GP law lives in the
dimensionless scaffold space (``ỹ`` vs its model), and a GP law has no exponent fingerprint, so
it is reported alongside — not inside — the exponent-keyed Discovery Graph.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

import numpy as np

from .engine import DiscoveryProblem, Variable, dimensional_system, discover_new_formulas
from .symbolic_search import GPConfig, GPVerdict, gp_discover, to_str

#: Shared Occam bar: a simpler family at/above this R² is EQUIVALENT (same as 6.3–6.8).
DEFAULT_R2_THRESHOLD = 0.999
#: Held-out R² the GP structure must reach out-of-sample (same as ``symbolic_search``).
DEFAULT_OOS_R2 = 0.99
#: ``‖A·p − b‖`` below which the target dimension is reachable from the sources.
_DIM_TOL = 1e-9
#: Lattice bounds for the π-group enumeration (the sibling frontiers' lattice).
DEFAULT_MAX_ABS_EXP = 2.0
DEFAULT_STEP = 0.5

#: The full Occam ladder, simplest family first. Every rung is an EXISTING gated discoverer.
DEFAULT_RUNGS: tuple[str, ...] = (
    "power_law", "power_of_pi", "multiterm", "transzendent",
    "produkt", "blind_produkt", "additives_argument",
)


# --- π-scaffold ----------------------------------------------------------------------------

@dataclass(frozen=True)
class PiScaffold:
    """The dimensional frame the GP evolves inside: ``base`` carries the target dimension
    (particular solution of ``A·p = b``), each π-group is dimensionless (null space, lattice).
    ``reachable=False`` means the target dimension cannot be formed at all (→ ``widerlegt``)."""

    base_exponents: dict[str, float]
    base_expression: str
    dimension_residual: float
    reachable: bool
    pi_groups: tuple[dict[str, float], ...]
    pi_names: tuple[str, ...]


def _fmt_exp(e: float) -> str:
    frac = Fraction(e).limit_denominator(24)
    return str(frac.numerator) if frac.denominator == 1 else f"{frac.numerator}/{frac.denominator}"


def _render_product(exponents: dict[str, float]) -> str:
    factors = [name if abs(e - 1.0) < 1e-9 else f"{name}^{_fmt_exp(e)}"
               for name, e in exponents.items() if abs(e) >= 1e-9]
    return " * ".join(factors) if factors else "1"


def _pi_basis(groups: list[dict[str, float]], names: list[str], nullity: int) -> tuple[dict[str, float], ...]:
    """A deterministic, INDEPENDENT π-basis from the enumerated lattice groups: prefer integer
    exponents, then small ‖p‖₁, then few negative exponents, then the canonical string; add a
    group only if it raises the rank (a redundant power of an already-chosen π adds nothing)."""
    def canon(g: dict[str, float]) -> str:
        return ";".join(f"{n}:{g.get(n, 0.0):g}" for n in names if abs(g.get(n, 0.0)) > 1e-12)

    def key(g: dict[str, float]):
        vals = [g.get(n, 0.0) for n in names]
        n_nonint = sum(1 for v in vals if abs(v - round(v)) > 1e-9)
        l1 = sum(abs(v) for v in vals)
        n_neg = sum(1 for v in vals if v < 0.0)
        first = next((v for v in vals if abs(v) > 1e-12), 0.0)
        return (n_nonint, l1, n_neg, 0 if first > 0.0 else 1, canon(g))

    chosen: list[dict[str, float]] = []
    vectors: list[np.ndarray] = []
    for g in sorted(groups, key=key):
        if len(chosen) >= nullity:
            break
        v = np.array([g.get(n, 0.0) for n in names], dtype=float)
        if np.linalg.matrix_rank(np.array([*vectors, v]), tol=1e-9) == len(vectors) + 1:
            chosen.append(g)
            vectors.append(v)
    return tuple(chosen)


def build_pi_scaffold(
    problem: DiscoveryProblem,
    *,
    max_abs_exp: float = DEFAULT_MAX_ABS_EXP,
    step: float = DEFAULT_STEP,
) -> PiScaffold:
    """Build the dimensional scaffold of `problem`: the target-dimension carrier ``base`` (the
    minimum-norm particular solution of ``A·p = b`` — deterministic) and an independent basis of
    dimensionless lattice π-groups. Honest boundary: a null-space direction that no bounded
    lattice group represents is not searched (the same lattice limit as the 6.x frontiers).
    Raises ValueError via the engine on non-positive magnitudes."""
    from .transcendental import dimensionless_groups

    a_matrix, b_vec, names = dimensional_system(problem)
    particular, *_ = np.linalg.lstsq(a_matrix, b_vec, rcond=None)
    residual = float(np.linalg.norm(a_matrix @ particular - b_vec))
    reachable = residual < _DIM_TOL
    base = {name: float(p) for name, p in zip(names, particular, strict=True)}

    groups: list[dict[str, float]] = dimensionless_groups(problem, max_abs_exp=max_abs_exp, step=step) if reachable else []
    nullity = len(names) - int(np.linalg.matrix_rank(a_matrix, tol=1e-9)) if reachable else 0
    basis = _pi_basis(groups, names, nullity) if nullity > 0 else ()
    return PiScaffold(
        base_exponents=base,
        base_expression=_render_product(base),
        dimension_residual=residual,
        reachable=reachable,
        pi_groups=basis,
        pi_names=tuple(f"pi{i + 1}" for i in range(len(basis))),
    )


def _pi_values(problem: DiscoveryProblem, exponents: dict[str, float]) -> np.ndarray:
    n = len(problem.target.values)
    out = np.ones(n, dtype=float)
    for v in problem.inputs:
        e = exponents.get(v.name, 0.0)
        if e != 0.0:
            out = out * np.power(np.asarray(v.values, dtype=float), e)
    for c in problem.constants:
        e = exponents.get(c.name, 0.0)
        if e != 0.0:
            out = out * float(c.value) ** e
    return out


# --- the Occam rival ladder ------------------------------------------------------------------

@dataclass(frozen=True)
class OccamRung:
    """One evaluated simpler family: its best in-sample R², its rendered law, and whether it is
    EQUIVALENT (essentially exact at the shared bar — for multiterm additionally out-of-sample
    validated, because an additive fit is not to be trusted in-sample alone, the 6.2 lesson)."""

    name: str
    r_squared: float
    expression: str
    equivalent: bool
    detail: str = ""


def _rung_power_law(problem: DiscoveryProblem, bar: float) -> OccamRung:
    result = discover_new_formulas(problem, r2_threshold=bar)
    if result.validated:
        best = result.validated[0]
        return OccamRung("power_law", best.candidate.r_squared, best.candidate.expression,
                         True, "gate: bestaetigt")
    best = max(result.all_records, key=lambda r: r.candidate.r_squared, default=None)
    if best is None:
        return OccamRung("power_law", -math.inf, "(kein Kandidat)", False)
    return OccamRung("power_law", best.candidate.r_squared, best.candidate.expression,
                     False, f"gate: {best.verdict}")


def _rung_power_of_pi(problem: DiscoveryProblem, bar: float) -> OccamRung:
    from .transcendental import discover_rivals

    _, rp = discover_rivals(problem)
    if rp is None:
        return OccamRung("power_of_pi", -math.inf, "(keine π-Gruppe)", False)
    pi = _render_product(rp.group)
    expr = (f"{problem.target.name} = {rp.params.get('C', 1.0):.6g}"
            f" * ({pi})^{rp.params.get('beta', 1.0):.6g} + {rp.params.get('D', 0.0):.6g}")
    return OccamRung("power_of_pi", rp.r_squared, expr, rp.r_squared >= bar)


def _rung_multiterm(problem: DiscoveryProblem, bar: float) -> OccamRung:
    from .multiterm import discover_multiterm, multiterm_out_of_sample_validate

    try:
        law = discover_multiterm(problem)
    except ValueError as exc:  # structural: empty term pool / over-large lattice
        return OccamRung("multiterm", -math.inf, "(kein Term-Pool)", False, str(exc))
    if law.r_squared < bar:
        return OccamRung("multiterm", law.r_squared, law.expression, False)
    try:
        oos = multiterm_out_of_sample_validate(problem)
    except ValueError as exc:  # too few points to split — an unvalidated additive fit never collapses GP
        return OccamRung("multiterm", law.r_squared, law.expression, False,
                         f"OOS nicht möglich: {exc}")
    return OccamRung("multiterm", law.r_squared, law.expression, bool(oos.generalises),
                     f"oos_test_r2={oos.test_r2:.6g}")


def _rung_transzendent(problem: DiscoveryProblem, bar: float) -> OccamRung:
    from .transcendental import discover_transcendental

    law = discover_transcendental(problem)
    return OccamRung("transzendent", law.r_squared, law.expression, law.r_squared >= bar)


def _rung_produkt(problem: DiscoveryProblem, bar: float) -> OccamRung:
    from .multiplicative import discover_product_law

    try:
        law = discover_product_law(problem)
    except ValueError as exc:
        return OccamRung("produkt", -math.inf, "(nicht anwendbar)", False, str(exc))
    return OccamRung("produkt", law.r_squared, law.expression, law.r_squared >= bar)


def _rung_blind_produkt(problem: DiscoveryProblem, bar: float) -> OccamRung:
    from .blind_product import discover_blind_product

    try:
        law = discover_blind_product(problem)
    except ValueError as exc:
        return OccamRung("blind_produkt", -math.inf, "(nicht anwendbar)", False, str(exc))
    return OccamRung("blind_produkt", law.r_squared, law.expression, law.r_squared >= bar)


def _rung_additives_argument(problem: DiscoveryProblem, bar: float) -> OccamRung:
    from .additive_argument import discover_additive_argument

    try:
        law = discover_additive_argument(problem)
    except ValueError as exc:
        return OccamRung("additives_argument", -math.inf, "(nicht anwendbar)", False, str(exc))
    return OccamRung("additives_argument", law.r_squared, law.expression, law.r_squared >= bar)


_RUNG_RUNNERS = {
    "power_law": _rung_power_law,
    "power_of_pi": _rung_power_of_pi,
    "multiterm": _rung_multiterm,
    "transzendent": _rung_transzendent,
    "produkt": _rung_produkt,
    "blind_produkt": _rung_blind_produkt,
    "additives_argument": _rung_additives_argument,
}


# --- the gated outcome -----------------------------------------------------------------------

@dataclass(frozen=True)
class GPSearchOutcome:
    """The honest outcome of the disciplined GP search.

    ``form``: the winning family — a ladder rung name on collapse, ``"gp"`` when the open-form
    search itself produced the best candidate, ``"keine"`` when there was nothing to search
    (dimensionally impossible target, or a determined system whose power law failed).
    ``verdict``: ``bestaetigt`` only for a gate-confirmed power-law collapse or a fully gated GP
    win; a collapse onto any other family is ``unentschieden`` with ``occam_winner`` naming it
    (its own discover_* carries the full claim); ``widerlegt`` for a dimensionally impossible
    target or an anti-correlated GP fit. ``r_squared`` of a GP law lives in the dimensionless
    scaffold space."""

    verdict: str
    form: str
    expression: str
    r_squared: float
    occam_winner: str | None
    rungs: tuple[OccamRung, ...]
    gp_verdict: GPVerdict | None
    scaffold: PiScaffold | None
    gates: dict


def _validate_problem(problem: DiscoveryProblem) -> None:
    """Fail loudly on unusable data (no silent defaults on factual things)."""
    y = np.asarray(problem.target.values, dtype=float)
    if y.shape[0] == 0:
        raise ValueError("target has no samples")
    if np.any(y <= 0.0):
        raise ValueError("target has non-positive values; the dimensional ladder needs positive magnitudes")
    for v in problem.inputs:
        arr = np.asarray(v.values, dtype=float)
        if arr.shape[0] != y.shape[0]:
            raise ValueError(f"input {v.name!r} has {arr.shape[0]} samples, target has {y.shape[0]}")
        if np.any(arr <= 0.0):
            raise ValueError(f"input {v.name!r} has non-positive values")
    for c in problem.constants:
        if c.value <= 0.0:
            raise ValueError(f"constant {c.name!r} must be positive")


def _gp_expression(problem: DiscoveryProblem, scaffold: PiScaffold, verdict: GPVerdict) -> str:
    rhs = f"{verdict.model.a:.6g} * [{to_str(verdict.model.tree)}] + {verdict.model.b:.6g}"
    if scaffold.base_expression == "1":
        expr = f"{problem.target.name} = {rhs}"
    else:
        expr = f"{problem.target.name} = ({scaffold.base_expression}) * ({rhs})"
    defs = "; ".join(f"{name} = {_render_product(group)}"
                     for name, group in zip(scaffold.pi_names, scaffold.pi_groups, strict=True))
    return f"{expr}  mit {defs}" if defs else expr


def gp_occam_discover(
    problem: DiscoveryProblem,
    *,
    seed: int = 0,
    cfg: GPConfig | None = None,
    r2_threshold: float = DEFAULT_R2_THRESHOLD,
    oos_r2: float = DEFAULT_OOS_R2,
    rungs: tuple[str, ...] = DEFAULT_RUNGS,
    max_abs_exp: float = DEFAULT_MAX_ABS_EXP,
    step: float = DEFAULT_STEP,
) -> GPSearchOutcome:
    """Run the FULL disciplined GP search: Occam ladder first, π-scaffolded GP only on what
    remains, verdicts only from the existing gates.

    The ladder rungs run simplest-first and SHORT-CIRCUIT: the first equivalent family collapses
    the outcome (``bestaetigt`` for the gate-confirmed power law, else ``unentschieden`` +
    ``occam_winner``) and no GP budget is spent. Only when every requested rung is below the bar
    does the GP evolve over the dimensionless π-columns of the scaffold; its candidate is judged
    by ``gp_discover``'s fit/dummy/out-of-sample gates — GP itself never confirms. Deterministic
    in ``seed``. Raises ValueError on unusable data or an unknown rung name."""
    if cfg is None:
        cfg = GPConfig()
    unknown = [r for r in rungs if r not in _RUNG_RUNNERS]
    if unknown:
        raise ValueError(f"unknown Occam rung(s) {unknown!r}; choose from {sorted(_RUNG_RUNNERS)}")
    _validate_problem(problem)

    evaluated: list[OccamRung] = []
    for name in rungs:
        rung = _RUNG_RUNNERS[name](problem, r2_threshold)
        evaluated.append(rung)
        if rung.equivalent:  # Occam collapse: the simplest equivalent family wins, GP never runs
            verdict = "bestaetigt" if name == "power_law" else "unentschieden"
            return GPSearchOutcome(
                verdict=verdict, form=name, expression=rung.expression,
                r_squared=rung.r_squared, occam_winner=name, rungs=tuple(evaluated),
                gp_verdict=None, scaffold=None,
                gates={"occam": {r.name: {"r_squared": r.r_squared, "equivalent": r.equivalent}
                                 for r in evaluated}})

    ladder_gates = {r.name: {"r_squared": r.r_squared, "equivalent": r.equivalent} for r in evaluated}
    best_rung_r2 = max((r.r_squared for r in evaluated), default=-math.inf)

    scaffold = build_pi_scaffold(problem, max_abs_exp=max_abs_exp, step=step)
    if not scaffold.reachable:
        return GPSearchOutcome(
            verdict="widerlegt", form="keine",
            expression=f"{problem.target.name} = (Ziel-Dimension aus den Quellen nicht bildbar)",
            r_squared=best_rung_r2, occam_winner=None, rungs=tuple(evaluated),
            gp_verdict=None, scaffold=scaffold,
            gates={"occam": ladder_gates,
                   "scaffold": {"reachable": False, "dimension_residual": scaffold.dimension_residual}})
    if not scaffold.pi_groups:
        # determined system, power law already failed: the open-form space beyond C·base is EMPTY
        return GPSearchOutcome(
            verdict="unentschieden", form="keine",
            expression=f"{problem.target.name} = (offener Formraum jenseits von C*{scaffold.base_expression} ist leer)",
            r_squared=best_rung_r2, occam_winner=None, rungs=tuple(evaluated),
            gp_verdict=None, scaffold=scaffold,
            gates={"occam": ladder_gates,
                   "scaffold": {"reachable": True, "pi_groups": 0}})

    # π-scaffolded GP: every genome is a function of pure numbers (dimensionless by construction)
    y = np.asarray(problem.target.values, dtype=float)
    base_values = _pi_values(problem, scaffold.base_exponents)
    y_scaled = y / base_values
    scaled_problem = DiscoveryProblem(
        idea=problem.idea,
        target=Variable(f"{problem.target.name}_pi", "1", tuple(y_scaled)),
        inputs=tuple(Variable(name, "1", tuple(_pi_values(problem, group)))
                     for name, group in zip(scaffold.pi_names, scaffold.pi_groups, strict=True)),
        run_id=problem.run_id,
    )
    gv = gp_discover(scaled_problem, seed=seed, cfg=cfg, r2_threshold=r2_threshold, oos_r2=oos_r2)

    return GPSearchOutcome(
        verdict=gv.verdict, form="gp",
        expression=_gp_expression(problem, scaffold, gv),
        r_squared=gv.model.r_squared, occam_winner=None, rungs=tuple(evaluated),
        gp_verdict=gv, scaffold=scaffold,
        gates={"occam": ladder_gates,
               "scaffold": {"reachable": True, "base": scaffold.base_expression,
                            "pi": {n: _render_product(g)
                                   for n, g in zip(scaffold.pi_names, scaffold.pi_groups, strict=True)}},
               "gp": gv.gates})


__all__ = [
    "PiScaffold", "build_pi_scaffold",
    "OccamRung", "GPSearchOutcome", "gp_occam_discover",
    "DEFAULT_RUNGS", "DEFAULT_R2_THRESHOLD", "DEFAULT_OOS_R2",
]
