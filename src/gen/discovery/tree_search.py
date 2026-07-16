"""tree_search — best-first tree search with the GATE as the node-scoring oracle.

The AI-Scientist-v2 adoption (best-first tree search over an experiment tree), with the one change
that makes it honest for GENESIS: the node-scoring oracle is the DETERMINISTIC gate, never an LLM
judge. Every one of those systems that let an LLM decide "promote this node" was fooled by its own
fabricated results (the documented 42% failure / hallucinated-ablation landscape); here a node is
promoted/pruned purely on what the gate says, so a node can never score itself past the gate.

``best_first_search`` is a general primitive: ``score(state) -> (quality, passed)`` is the gate, and
``expand(state) -> child states`` grows the tree. It expands the highest-quality unexpanded node first,
dedups by ``key(state)``, and is bounded by ``max_nodes`` / ``max_depth``. Deterministic given a
deterministic score/expand (ties break by insertion order). The discovery consumer ``directed_search``
shows it finding a confirmed law from a wrong start, scored only by ``judge_candidate``.

Offline, numpy-free for the primitive.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Callable, Generic, Hashable, Iterable, TypeVar

S = TypeVar("S")


@dataclass(frozen=True)
class SearchNode(Generic[S]):
    """A visited state: its gate quality, whether it PASSED the gate, and its tree depth."""

    state: S
    quality: float
    passed: bool
    depth: int


@dataclass(frozen=True)
class SearchResult(Generic[S]):
    """The outcome: the best node (highest-quality gate-PASSING node, else highest-quality seen),
    how many nodes were expanded, and every gate-passing node found (best first)."""

    best: SearchNode[S] | None
    nodes_expanded: int
    passing: tuple[SearchNode[S], ...]


def best_first_search(
    roots: Iterable[S],
    score: Callable[[S], tuple[float, bool]],
    expand: Callable[[S], Iterable[S]],
    *,
    key: Callable[[S], Hashable] | None = None,
    max_nodes: int = 128,
    max_depth: int = 16,
) -> SearchResult[S]:
    """Best-first search. ``score`` is the gate (returns ``(quality, passed)``); ``expand`` grows the
    tree. Expands the highest-quality unexpanded node first, deduping by ``key`` (default identity),
    bounded by ``max_nodes`` expansions and ``max_depth``. The gate alone decides ``passed`` — no model
    promotes a node."""
    if max_nodes < 1:
        raise ValueError("max_nodes must be >= 1")
    identity = key or (lambda s: s)
    heap: list[tuple[float, int, SearchNode[S]]] = []
    counter = 0
    seen: set[Hashable] = set()

    def _push(state: S, depth: int) -> None:
        nonlocal counter
        quality, passed = score(state)
        heapq.heappush(heap, (-quality, counter, SearchNode(state, quality, passed, depth)))
        counter += 1

    for root in roots:
        _push(root, 0)

    expanded = 0
    passing: list[SearchNode[S]] = []
    best_any: SearchNode[S] | None = None
    while heap and expanded < max_nodes:
        _, _, node = heapq.heappop(heap)
        node_key = identity(node.state)
        if node_key in seen:
            continue
        seen.add(node_key)
        expanded += 1
        if best_any is None or node.quality > best_any.quality:
            best_any = node
        if node.passed:
            passing.append(node)
        if node.depth < max_depth:
            for child in expand(node.state):
                if identity(child) not in seen:
                    _push(child, node.depth + 1)

    passing.sort(key=lambda n: -n.quality)
    best = passing[0] if passing else best_any
    return SearchResult(best=best, nodes_expanded=expanded, passing=tuple(passing))


# --- discovery consumer: directed exponent search, scored ONLY by the gate ---------------------

def directed_search(problem, start_exponents: dict[str, float], *, step: float = 0.5, max_nodes: int = 64):
    """Best-first search over power-law exponent vectors, scored by ``judge_candidate`` (the gate).

    From a (possibly wrong) start, expand by perturbing each exponent by ±``step`` and let the gate
    score every neighbour; best-first walks toward a confirmed law. The gate is the sole oracle — a
    neighbour is ``passed`` only if it clears the dimensional + fit gates. Returns a ``SearchResult``
    whose ``best`` is the highest-R² confirmed law found (or the best seen if none passed).
    """
    from .engine import candidate_from_exponents, judge_candidate

    names = tuple(start_exponents)

    def _key(exps: tuple[float, ...]) -> Hashable:
        return tuple(round(e, 6) for e in exps)

    def _score(exps: tuple[float, ...]) -> tuple[float, bool]:
        mapping = {n: float(e) for n, e in zip(names, exps, strict=True)}
        verdict = judge_candidate(problem, candidate_from_exponents(problem, mapping))
        return (verdict.candidate.r_squared, verdict.passed)

    def _expand(exps: tuple[float, ...]) -> Iterable[tuple[float, ...]]:
        # bound exponents to a physically sane range: real power-law exponents are small rationals, and
        # wandering to extreme values only overflows the fit (a candidate no gate would ever confirm).
        for i in range(len(exps)):
            for delta in (step, -step):
                value = exps[i] + delta
                if abs(value) > 4.0:
                    continue
                neighbour = list(exps)
                neighbour[i] = value
                yield tuple(neighbour)

    root = tuple(float(start_exponents[n]) for n in names)
    return best_first_search([root], _score, _expand, key=_key, max_nodes=max_nodes)
