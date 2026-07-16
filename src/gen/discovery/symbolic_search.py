"""symbolic_search — an open-form genetic-programming symbolic-regression engine (Roadmap B0).

GENESIS' dimensional engine (``engine.py``) discovers ONLY power-law / Π-group relations: it fixes the
exponents from the units and fits a single coefficient. That is sound but NARROW — it cannot represent an
additive law (``v = g·t + v0``), a transcendental one (``y = A·sin(x) + C``), or anything outside one
power-law product. This module is the general, field-INDEPENDENT proposer the roadmap calls for: a real,
self-contained, SEEDED genetic-programming search over expression trees with the operators

    +  −  ×  ÷  pow   sin  cos  exp  log  sqrt  neg

plus constant optimisation (an exact closed-form affine refit ``a·f(x)+b`` on top of evolved internal
constants) and a PARSIMONY penalty against overfitting.

It is a PROPOSER, never a verdict. A discovered expression earns nothing on fit alone; ``gp_discover``
runs every candidate through the same honesty discipline as the rest of the arm:

  * FIT gate — R² over the data, with the δ-asymmetry RAISING the bar as the expression grows.
  * HYGIENE gate — the SRBench discipline (``srbench_hygiene``) adapted to open expressions:
      (a) a planted IRRELEVANT variable must not be used (dummy exclusion), and
      (b) the law must generalise OUT-OF-SAMPLE — the structure's affine constants are refit on a TRAIN
          split and scored on a HELD-OUT split it never saw. A fit on noise passes neither.

So the engine WIDENS the candidate space; the gate stays the sole authority — exactly the symbiosis
discipline (``symbiosis.py``), with a deterministic search in place of an LLM as the breadth source.

Determinism: every random draw comes from a single ``numpy.random.default_rng(seed)`` consumed in a fixed
order; selection, elitism and tie-breaks sort on ``(-score, complexity, canonical-string)``. Same seed +
same data → byte-identical expression. Offline, numpy-only.

Honest boundary: a SMALL GP finds LOW-complexity closed forms (depth a few); it is not a global optimiser,
constants buried inside transcendental functions are found by search (not gradient), and a hard target may
come back ``unentschieden`` — an honest "I don't know", never a fabricated law.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .engine import DiscoveryProblem

# --- operator set -------------------------------------------------------------------------

BINARY_OPS: tuple[str, ...] = ("+", "-", "*", "/", "pow")
UNARY_OPS: tuple[str, ...] = ("sin", "cos", "exp", "log", "sqrt", "neg")

#: clip the argument of exp into a finite range so a deep tree cannot overflow to inf.
_EXP_CLIP = 50.0


@dataclass(frozen=True)
class Node:
    """An expression-tree node. ``kind`` ∈ {var, const, unary, binary}. A var carries ``name``; a const
    carries ``value``; a unary carries ``op`` + ``a``; a binary carries ``op`` + ``a`` + ``b``."""

    kind: str
    name: Optional[str] = None
    value: Optional[float] = None
    op: Optional[str] = None
    a: Optional["Node"] = None
    b: Optional["Node"] = None


def mk_var(name: str) -> Node:
    return Node("var", name=name)


def mk_const(value: float) -> Node:
    return Node("const", value=float(value))


def mk_unary(op: str, a: Node) -> Node:
    return Node("unary", op=op, a=a)


def mk_binary(op: str, a: Node, b: Node) -> Node:
    return Node("binary", op=op, a=a, b=b)


# --- evaluation, size, rendering ----------------------------------------------------------

def evaluate(node: Node, env: dict[str, np.ndarray], n: int) -> np.ndarray:
    """Evaluate ``node`` over column arrays ``env`` (length ``n``). Domain violations (÷0, log≤0, √<0,
    overflow) yield non-finite values that the caller treats as an invalid individual — never a crash."""
    with np.errstate(all="ignore"):
        if node.kind == "const":
            return np.full(n, float(node.value))
        if node.kind == "var":
            return env[node.name]
        if node.kind == "unary":
            x = evaluate(node.a, env, n)
            op = node.op
            if op == "sin":
                return np.sin(x)
            if op == "cos":
                return np.cos(x)
            if op == "exp":
                return np.exp(np.clip(x, -_EXP_CLIP, _EXP_CLIP))
            if op == "log":
                return np.where(x > 0.0, np.log(np.abs(x)), np.nan)
            if op == "sqrt":
                return np.where(x >= 0.0, np.sqrt(np.abs(x)), np.nan)
            if op == "neg":
                return -x
            raise ValueError(f"unknown unary op {op!r}")
        # binary
        x = evaluate(node.a, env, n)
        y = evaluate(node.b, env, n)
        op = node.op
        if op == "+":
            return x + y
        if op == "-":
            return x - y
        if op == "*":
            return x * y
        if op == "/":
            return np.where(np.abs(y) > 1e-12, x / np.where(np.abs(y) > 1e-12, y, 1.0), np.nan)
        if op == "pow":
            return np.power(np.abs(x) + 1e-12, np.clip(y, -6.0, 6.0)) * np.sign(np.where(x == 0.0, 1.0, x)) ** 0
        raise ValueError(f"unknown binary op {op!r}")


def complexity(node: Node) -> int:
    """Node count — the parsimony measure."""
    if node.kind in ("var", "const"):
        return 1
    if node.kind == "unary":
        return 1 + complexity(node.a)
    return 1 + complexity(node.a) + complexity(node.b)


def vars_used(node: Node) -> frozenset[str]:
    if node.kind == "var":
        return frozenset({node.name})
    if node.kind == "const":
        return frozenset()
    if node.kind == "unary":
        return vars_used(node.a)
    return vars_used(node.a) | vars_used(node.b)


def to_str(node: Node) -> str:
    """Canonical, deterministic rendering (constants at 6 significant figures)."""
    if node.kind == "const":
        return f"{node.value:.6g}"
    if node.kind == "var":
        return node.name
    if node.kind == "unary":
        return f"{node.op}({to_str(node.a)})"
    return f"({to_str(node.a)} {node.op} {to_str(node.b)})"


def _preorder(node: Node) -> list[Node]:
    if node.kind in ("var", "const"):
        return [node]
    if node.kind == "unary":
        return [node, *_preorder(node.a)]
    return [node, *_preorder(node.a), *_preorder(node.b)]


def _replace_at(tree: Node, k: int, repl: Node) -> Node:
    """Return a copy of ``tree`` with the pre-order k-th node replaced by ``repl`` (counts every node)."""
    counter = [0]

    def rec(n: Node) -> Node:
        cur = counter[0]
        counter[0] += 1
        if n.kind in ("var", "const"):
            return repl if cur == k else n
        if n.kind == "unary":
            child = rec(n.a)
            return repl if cur == k else mk_unary(n.op, child)
        left = rec(n.a)
        right = rec(n.b)
        return repl if cur == k else mk_binary(n.op, left, right)

    return rec(tree)


# --- random generation --------------------------------------------------------------------

def _rand_terminal(rng: np.random.Generator, var_names: tuple[str, ...]) -> Node:
    # ~75% a variable, ~25% an ephemeral constant — variables carry the signal, constants tune it.
    if len(var_names) > 0 and rng.random() < 0.75:
        return mk_var(var_names[int(rng.integers(len(var_names)))])
    return mk_const(round(float(rng.uniform(-3.0, 3.0)), 4))


def _rand_tree(rng: np.random.Generator, depth: int, var_names: tuple[str, ...], *, full: bool) -> Node:
    if depth <= 0:
        return _rand_terminal(rng, var_names)
    # 'grow' allows early terminals; 'full' always branches until the depth limit.
    if not full and rng.random() < 0.30:
        return _rand_terminal(rng, var_names)
    if rng.random() < 0.55:
        op = UNARY_OPS[int(rng.integers(len(UNARY_OPS)))]
        return mk_unary(op, _rand_tree(rng, depth - 1, var_names, full=full))
    op = BINARY_OPS[int(rng.integers(len(BINARY_OPS)))]
    return mk_binary(op, _rand_tree(rng, depth - 1, var_names, full=full),
                     _rand_tree(rng, depth - 1, var_names, full=full))


# --- fitness ------------------------------------------------------------------------------

def _affine_fit(f: np.ndarray, y: np.ndarray) -> tuple[float, float, np.ndarray]:
    """Exact least-squares ``a·f + b`` (the closed-form optimal linear constants). Degenerate f → (0, ȳ)."""
    n = f.shape[0]
    sf = float(np.sum(f))
    sff = float(np.sum(f * f))
    sy = float(np.sum(y))
    sfy = float(np.sum(f * y))
    det = n * sff - sf * sf
    if abs(det) < 1e-12:
        b = sy / n
        return 0.0, b, np.full(n, b)
    a = (n * sfy - sf * sy) / det
    b = (sy - a * sf) / n
    return a, b, a * f + b


def _r2(y: np.ndarray, y_hat: np.ndarray) -> float:
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
    if ss_tot <= 0.0:
        return 1.0 if np.allclose(y, y_hat) else 0.0
    return 1.0 - ss_res / ss_tot


@dataclass(frozen=True)
class SymbolicModel:
    """A discovered open-form law ``y ≈ a·f(x) + b``. ``tree`` is the evolved structure f; ``a``/``b`` are
    the affine constants; ``r_squared`` and ``complexity`` are the fit and parsimony; ``expression`` renders
    the full law. ``predict`` evaluates it on a fresh column dict."""

    tree: Node
    a: float
    b: float
    r_squared: float
    complexity: int
    expression: str

    def predict(self, env: dict[str, np.ndarray]) -> np.ndarray:
        n = len(next(iter(env.values())))
        return self.a * evaluate(self.tree, env, n) + self.b


def _evaluate_tree(tree: Node, env: dict[str, np.ndarray], y: np.ndarray, n: int) -> tuple[float, float, float]:
    """Return ``(r2, a, b)`` for ``tree``; an invalid (non-finite) evaluation scores r2 = -inf."""
    f = evaluate(tree, env, n)
    if f.shape != y.shape or not np.all(np.isfinite(f)):
        return -math.inf, 0.0, 0.0
    a, b, y_hat = _affine_fit(f, y)
    return _r2(y, y_hat), a, b


def _render(tree: Node, a: float, b: float, target_name: str) -> str:
    return f"{target_name} = {a:.6g} * [{to_str(tree)}] + {b:.6g}"


# --- the genetic-programming search -------------------------------------------------------

@dataclass(frozen=True)
class GPConfig:
    """Search hyper-parameters. Defaults are deterministic and modest; tests pass smaller values."""

    population: int = 240
    generations: int = 60
    max_depth: int = 4
    tournament: int = 5
    crossover_rate: float = 0.7
    mutation_rate: float = 0.25
    elitism: int = 3
    parsimony: float = 2e-3
    max_nodes: int = 28


def _score(r2: float, size: int, cfg: GPConfig) -> float:
    # higher is better; parsimony shrinks the score with size so a true simpler law wins ties.
    return r2 - cfg.parsimony * size


def gp_fit(target: np.ndarray, columns: dict[str, np.ndarray], *, seed: int = 0,
           cfg: GPConfig | None = None) -> SymbolicModel:
    """Evolve an open-form law ``y ≈ a·f(x)+b`` for ``target`` over the input ``columns``. Deterministic in
    ``seed``: identical seed + data → identical model. Raises ValueError on empty/mismatched data."""
    if cfg is None:
        cfg = GPConfig()
    y = np.asarray(target, dtype=float)
    n = y.shape[0]
    if n == 0:
        raise ValueError("target has no samples")
    var_names = tuple(sorted(columns))
    env = {k: np.asarray(columns[k], dtype=float) for k in var_names}
    for k, arr in env.items():
        if arr.shape[0] != n:
            raise ValueError(f"column {k!r} has {arr.shape[0]} samples, target has {n}")
    if not var_names:
        raise ValueError("need at least one input column")
    rng = np.random.default_rng(seed)

    def make_individual() -> Node:
        depth = 1 + int(rng.integers(cfg.max_depth))
        return _rand_tree(rng, depth, var_names, full=bool(rng.integers(2)))

    population = [make_individual() for _ in range(cfg.population)]

    def scored(pop: list[Node]) -> list[tuple[float, int, str, Node, float, float]]:
        rows = []
        for tree in pop:
            size = complexity(tree)
            r2, a, b = _evaluate_tree(tree, env, y, n)
            rows.append((_score(r2, size, cfg), size, to_str(tree), tree, r2, a))
        # deterministic order: best score, then parsimony, then canonical string
        rows.sort(key=lambda r: (-r[0], r[1], r[2]))
        return rows

    def tournament_pick(rows: list) -> Node:
        best_idx = min(int(rng.integers(len(rows))) for _ in range(cfg.tournament))
        return rows[best_idx][3]  # rows are sorted best-first, so the smallest index wins

    def mutate(tree: Node) -> Node:
        nodes = _preorder(tree)
        k = int(rng.integers(len(nodes)))
        target_node = nodes[k]
        if target_node.kind == "const" and rng.random() < 0.5:
            repl = mk_const(round(float(target_node.value) + float(rng.normal(0.0, 1.0)), 4))
        else:
            repl = _rand_tree(rng, 1 + int(rng.integers(cfg.max_depth)), var_names, full=False)
        out = _replace_at(tree, k, repl)
        return out if complexity(out) <= cfg.max_nodes else tree

    def crossover(p1: Node, p2: Node) -> Node:
        donors = _preorder(p2)
        donor = donors[int(rng.integers(len(donors)))]
        k = int(rng.integers(complexity(p1)))
        out = _replace_at(p1, k, donor)
        return out if complexity(out) <= cfg.max_nodes else p1

    best_row = None
    for _ in range(cfg.generations):
        rows = scored(population)
        if best_row is None or rows[0][0] > best_row[0]:
            best_row = rows[0]
        # honest early stop: a (near-)exact, parsimonious fit cannot be beaten
        if best_row[4] >= 1.0 - 1e-12:
            break
        nxt: list[Node] = [rows[i][3] for i in range(min(cfg.elitism, len(rows)))]
        while len(nxt) < cfg.population:
            if rng.random() < cfg.crossover_rate:
                child = crossover(tournament_pick(rows), tournament_pick(rows))
            else:
                child = tournament_pick(rows)
            if rng.random() < cfg.mutation_rate:
                child = mutate(child)
            nxt.append(child)
        population = nxt

    # final sweep includes the last generation
    rows = scored(population)
    if best_row is None or rows[0][0] > best_row[0]:
        best_row = rows[0]

    tree = best_row[3]
    size = best_row[1]
    r2, a, b = _evaluate_tree(tree, env, y, n)
    return SymbolicModel(tree=tree, a=a, b=b, r_squared=r2, complexity=size,
                         expression=_render(tree, a, b, "y"))


# --- the gated proposer (behind the existing honesty discipline) --------------------------

@dataclass(frozen=True)
class GPVerdict:
    """The honest judgement of an open-form discovery: the model, the three-way verdict, and per-gate
    detail. ``verdict`` ∈ {bestaetigt, unentschieden, widerlegt}; ``passed`` requires fit AND hygiene."""

    model: SymbolicModel
    verdict: str
    passed: bool
    fit_ok: bool
    dummy_excluded: bool
    generalises: bool
    test_r2: float
    gates: dict


def _columns(problem: DiscoveryProblem) -> tuple[dict[str, np.ndarray], int]:
    n = len(problem.target.values)
    cols: dict[str, np.ndarray] = {v.name: np.asarray(v.values, float) for v in problem.inputs}
    for c in problem.constants:
        cols[c.name] = np.full(n, float(c.value))
    return cols, n


def _split(n: int, train_fraction: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    k = max(2, min(n - 1, int(round(n * train_fraction))))
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n)
    return np.sort(perm[:k]), np.sort(perm[k:])


#: default fit bar for a confirmed open-form law (R² ≥ this, δ-raised by complexity).
DEFAULT_GP_R2_THRESHOLD = 0.999
#: held-out R² at/above which the law is judged to generalise.
DEFAULT_GP_OOS_R2 = 0.99
#: dimension absent from typical targets — an alien-dimension dummy must not be used by a sound law.
DUMMY_UNIT = "kg"


def gp_discover(problem: DiscoveryProblem, *, seed: int = 0, cfg: GPConfig | None = None,
                r2_threshold: float = DEFAULT_GP_R2_THRESHOLD,
                oos_r2: float = DEFAULT_GP_OOS_R2) -> GPVerdict:
    """Discover an open-form law for ``problem`` and JUDGE it through the same honesty gates as the rest of
    the arm — never accepting it on fit alone.

    1. FIT — evolve ``a·f(x)+b``; require R² ≥ a δ-raised threshold (a more complex claim must fit better).
    2. DUMMY EXCLUSION — plant an irrelevant alien-dimension variable; the re-evolved law must not use it.
    3. OUT-OF-SAMPLE — refit only the affine constants of the discovered structure on a TRAIN split and
       score on a HELD-OUT split (no peeking). A fit on noise collapses here.

    Verdict: ``bestaetigt`` (fit ∧ hygiene), ``widerlegt`` (anti-correlated, R² < 0), else
    ``unentschieden`` (an honest "I don't know"). Deterministic in ``seed``."""
    if cfg is None:
        cfg = GPConfig()
    cols, n = _columns(problem)
    y = np.asarray(problem.target.values, float)
    model = gp_fit(y, cols, seed=seed, cfg=cfg)

    # δ-asymmetry: a more complex (more novel) claim must clear a stricter bar.
    delta = min(1.0, model.complexity / 10.0)
    effective_threshold = r2_threshold + (1.0 - r2_threshold) * delta
    fit_ok = model.r_squared >= effective_threshold

    # (2) dummy exclusion — re-evolve with an alien-dimension irrelevant column planted.
    rng = np.random.default_rng(seed + 1)
    dummy_cols = dict(cols)
    dummy_cols["gp_dummy"] = rng.uniform(1.0, 5.0, size=n)
    dummy_model = gp_fit(y, dummy_cols, seed=seed, cfg=cfg)
    dummy_excluded = "gp_dummy" not in vars_used(dummy_model.tree)

    # (3) out-of-sample — refit ONLY the affine constants of the discovered structure on train, score test.
    generalises = False
    test_r2 = float("nan")
    if n >= 4:
        train_idx, test_idx = _split(n, 0.6, seed)
        env_train = {k: v[train_idx] for k, v in cols.items()}
        env_test = {k: v[test_idx] for k, v in cols.items()}
        f_train = evaluate(model.tree, env_train, train_idx.shape[0])
        f_test = evaluate(model.tree, env_test, test_idx.shape[0])
        if np.all(np.isfinite(f_train)) and np.all(np.isfinite(f_test)):
            a, b, _ = _affine_fit(f_train, y[train_idx])
            test_r2 = _r2(y[test_idx], a * f_test + b)
            generalises = test_r2 >= oos_r2
    else:
        generalises = fit_ok  # too few points to split — fall back to the in-sample verdict honestly

    hygiene_ok = dummy_excluded and generalises
    passed = fit_ok and hygiene_ok
    if model.r_squared < 0.0:
        verdict = "widerlegt"
    elif passed:
        verdict = "bestaetigt"
    else:
        verdict = "unentschieden"

    gates = {
        "fit": {"passed": fit_ok, "r_squared": model.r_squared, "threshold": effective_threshold,
                "complexity": model.complexity},
        "dummy_exclusion": {"passed": dummy_excluded, "vars": sorted(vars_used(dummy_model.tree))},
        "out_of_sample": {"passed": generalises, "test_r2": test_r2, "threshold": oos_r2},
    }
    return GPVerdict(model=model, verdict=verdict, passed=passed, fit_ok=fit_ok,
                     dummy_excluded=dummy_excluded, generalises=generalises, test_r2=test_r2, gates=gates)


__all__ = [
    "Node", "mk_var", "mk_const", "mk_unary", "mk_binary",
    "evaluate", "complexity", "vars_used", "to_str",
    "SymbolicModel", "GPConfig", "gp_fit",
    "GPVerdict", "gp_discover",
    "BINARY_OPS", "UNARY_OPS",
    "DEFAULT_GP_R2_THRESHOLD", "DEFAULT_GP_OOS_R2",
]
