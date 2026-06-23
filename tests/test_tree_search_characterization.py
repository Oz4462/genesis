"""Characterization / facade-detector for discovery/tree_search.py.

The headline claim under audit: best-first expansion is driven PURELY by the deterministic gate
score — a node's ``passed`` comes only from ``score(state)`` (no node can promote itself), the
search dedups by ``key``, is bounded by ``max_nodes``/``max_depth``, ties break by insertion order,
and ``directed_search`` walks from a deliberately WRONG exponent start to a gate-confirmed law that
is scored ONLY by ``judge_candidate``.

Every test here is a real facade-detector, not a smoke test: each asserts an observable behaviour
that would FAIL if the search secretly ignored its inputs, fabricated a "passing" node, or let
something other than the gate decide expansion order. Offline, deterministic.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gen.discovery.tree_search import best_first_search, directed_search


# --- (1) pure-primitive: best-first order, dedup, bounds, insertion-order tie-break -------------

def test_expansion_order_is_strictly_best_first():
    """Pop/expand order must be descending in gate quality — the highest-quality unexpanded node is
    always taken next. Recording the order in ``expand`` (called once per expanded node) exposes the
    real scheduling, so a search that secretly did BFS/DFS would fail this."""
    order: list[int] = []

    def score(x: int) -> tuple[float, bool]:
        return (float(x), False)  # quality == the integer itself

    def expand(x: int):
        order.append(x)
        return []  # roots only: isolate ordering from tree growth

    best_first_search([1, 5, 3, 2, 4], score, expand, max_nodes=10)
    assert order == [5, 4, 3, 2, 1]  # strictly by descending quality, not by insertion order


def test_ties_break_by_insertion_order():
    """When qualities tie, the earlier-inserted node must be expanded first. The heap carries a
    monotonic insertion counter as the tie-breaker, so equal-quality roots come out FIFO."""
    order: list[str] = []

    def score(_x: str) -> tuple[float, bool]:
        return (0.0, False)  # every node ties

    def expand(x: str):
        order.append(x)
        return []

    best_first_search(["a", "b", "c", "d"], score, expand, max_nodes=10)
    assert order == ["a", "b", "c", "d"]  # insertion order preserved under ties


def test_dedup_by_key_expands_each_key_once():
    """A cyclic/duplicating ``expand`` must not re-expand a key already seen — dedup by ``key`` is
    what makes the search terminate. Here every node keeps yielding the same child ``10``."""
    expanded: list[int] = []

    def score(x: int) -> tuple[float, bool]:
        return (-float(x), False)

    def expand(x: int):
        expanded.append(x)
        return [10, 10]  # always the same child, twice

    res = best_first_search([0], score, expand, key=lambda s: s, max_nodes=50, max_depth=8)
    assert expanded == [0, 10]              # 0 then 10, and 10 only once despite being yielded 4x
    assert res.nodes_expanded == 2


def test_custom_key_collapses_distinct_states():
    """``key`` is the dedup identity, not the state itself: two distinct states with the same key
    must collapse to a single expansion. Proves ``key`` is genuinely consulted."""
    expanded: list[int] = []

    def score(x: int) -> tuple[float, bool]:
        return (float(x), False)

    def expand(x: int):
        expanded.append(x)
        return []

    # 10 and 11 share key (//10 == 1); 25 has key 2. Higher quality (11) wins its key.
    res = best_first_search([10, 11, 25], score, expand, key=lambda s: s // 10, max_nodes=10)
    assert expanded == [25, 11]  # 11 expanded for key 1 (higher quality than 10), 10 deduped out
    assert res.nodes_expanded == 2


def test_max_nodes_caps_expansions():
    """The search must stop after exactly ``max_nodes`` expansions even in an unbounded space."""
    def score(x: int) -> tuple[float, bool]:
        return (-((x - 3) ** 2), x == 3)

    def expand(x: int):
        return [x - 1, x + 1]  # infinite space

    res = best_first_search([0], score, expand, max_nodes=4)
    assert res.nodes_expanded == 4


def test_max_depth_bounds_the_tree():
    """No node deeper than ``max_depth`` may grow children. A linear chain where state == depth makes
    the bound directly observable: with max_depth=2 only the depth-0 and depth-1 nodes have ``expand``
    invoked (so the deepest state ever created is 2), while the depth-2 node is still visited/counted."""
    order: list[int] = []

    def score(_x: int) -> tuple[float, bool]:
        return (0.0, False)

    def expand(x: int):
        order.append(x)
        return [x + 1]  # state value == its depth

    res = best_first_search([0], score, expand, max_nodes=100, max_depth=2)
    assert order == [0, 1]             # expand() invoked only on depth < max_depth nodes
    assert 3 not in order              # the depth-2 node never grows -> state 3 is never created
    assert res.nodes_expanded == 3     # but 0,1,2 are all visited (popped) and counted


def test_passed_comes_only_from_score_not_quality():
    """The crux of the honesty claim: a node cannot promote itself. ``best`` must be the highest-
    quality node the GATE marked ``passed`` — even when a strictly higher-quality node was NOT
    passed. So raw quality cannot smuggle a node past the gate."""
    def score(x: int) -> tuple[float, bool]:
        quality = {10: 100.0, 5: 50.0, 1: 10.0}[x]
        passed = (x == 5)  # the gate blesses ONLY the mid-quality node
        return (quality, passed)

    def expand(_x: int):
        return []

    res = best_first_search([10, 5, 1], score, expand, max_nodes=10)
    assert res.best is not None
    assert res.best.state == 5 and res.best.passed          # gate's verdict wins over raw quality
    assert [n.state for n in res.passing] == [5]            # passing set == exactly score's True nodes


def test_best_falls_back_to_highest_quality_when_nothing_passes():
    """With no passing node, ``best`` is the highest-quality node seen — and it must NOT claim to
    have passed (honest abstention rather than a fabricated success)."""
    def score(x: int) -> tuple[float, bool]:
        return (float(x), False)  # nothing ever passes

    def expand(_x: int):
        return []

    res = best_first_search([3, 7, 2], score, expand, max_nodes=10)
    assert res.best is not None and res.best.state == 7
    assert res.best.passed is False
    assert res.passing == ()


# --- (3) negative: max_nodes < 1 must fail loud, not silently no-op -----------------------------

@pytest.mark.parametrize("bad", [0, -1, -5])
def test_max_nodes_below_one_raises(bad: int):
    with pytest.raises(ValueError):
        best_first_search([0], lambda x: (0.0, False), lambda x: [], max_nodes=bad)


def test_directed_search_propagates_the_max_nodes_guard():
    """``directed_search`` forwards ``max_nodes`` to the primitive, so the guard must fire there too."""
    from gen.discovery.benchmark import kepler_case

    with pytest.raises(ValueError):
        directed_search(kepler_case().problem, {"a": 1.0, "mu": -0.5}, max_nodes=0)


# --- (2) directed_search: wrong start -> gate-confirmed law, scored only by judge_candidate -----

def test_directed_search_recovers_a_confirmed_law_from_a_wrong_start():
    """Starting from deliberately WRONG exponents, the gate-guided walk must reach a confirmed law
    with the true Kepler exponents (a=3/2, mu=-1/2). The ONLY thing that can mark a node passing is
    ``judge_candidate`` (the engine gate), so a confirmed result here proves the gate really drove
    the search to a dimensionally-and-fit-correct law from a bad seed."""
    from gen.discovery.benchmark import kepler_case

    problem = kepler_case().problem
    res = directed_search(problem, {"a": 1.0, "mu": -0.5}, step=0.5, max_nodes=64)

    assert res.best is not None and res.best.passed
    a_exp, mu_exp = res.best.state
    assert abs(a_exp - 1.5) < 1e-6 and abs(mu_exp + 0.5) < 1e-6
    # every node reported as passing must really carry the gate's blessing (no self-promotion)
    assert all(node.passed for node in res.passing)


def test_directed_search_does_not_fabricate_a_pass_on_an_impossible_target():
    """Honest abstention: a dimensionally impossible target (temperature from length+time) can never
    be confirmed by the gate, so the search must return a ``best`` with ``passed=False`` and an empty
    passing set — never a fabricated success."""
    from gen.discovery.benchmark import redteam_impossible_case

    problem = redteam_impossible_case().problem
    res = directed_search(problem, {"a": 1.0, "t": 1.0}, step=0.5, max_nodes=64)
    assert res.passing == ()
    assert res.best is None or res.best.passed is False


# --- (4) determinism across two runs -----------------------------------------------------------

def test_primitive_is_deterministic_across_two_runs():
    def score(x: int) -> tuple[float, bool]:
        return (-((x - 3) ** 2), x == 3)

    def expand(x: int):
        return [v for v in (x - 1, x + 1) if -10 <= v <= 10]

    a = best_first_search([0], score, expand, max_nodes=20)
    b = best_first_search([0], score, expand, max_nodes=20)
    assert a.best == b.best
    assert a.nodes_expanded == b.nodes_expanded
    assert a.passing == b.passing


def test_directed_search_is_deterministic_across_two_runs():
    from gen.discovery.benchmark import kepler_case

    problem = kepler_case().problem
    a = directed_search(problem, {"a": 1.0, "mu": -0.5}, step=0.5, max_nodes=64)
    b = directed_search(problem, {"a": 1.0, "mu": -0.5}, step=0.5, max_nodes=64)
    assert a.best == b.best
    assert a.nodes_expanded == b.nodes_expanded
    assert tuple(n.state for n in a.passing) == tuple(n.state for n in b.passing)


# --- property-based invariants: best-first order + bound + dedup hold for ALL inputs ------------

@settings(max_examples=200, deadline=None)
@given(
    roots=st.lists(st.integers(min_value=-50, max_value=50), min_size=1, max_size=30),
    max_nodes=st.integers(min_value=1, max_value=40),
)
def test_property_best_first_order_bound_and_dedup(roots: list[int], max_nodes: int):
    """For any root multiset and any max_nodes: expansion order is non-increasing in quality (best-
    first), expansions never exceed max_nodes, and with a non-growing ``expand`` exactly the unique
    roots (capped at max_nodes) are expanded — proving dedup-by-key holds for all inputs."""
    order: list[int] = []

    def score(x: int) -> tuple[float, bool]:
        return (float(x), False)

    def expand(x: int):
        order.append(x)
        return []  # no tree growth -> expanded set must equal the unique roots (capped)

    res = best_first_search(list(roots), score, expand, max_nodes=max_nodes)

    assert all(order[i] >= order[i + 1] for i in range(len(order) - 1))  # best-first
    assert res.nodes_expanded <= max_nodes                              # bounded
    assert res.nodes_expanded == min(len(set(roots)), max_nodes)        # dedup by key
    assert len(order) == res.nodes_expanded                            # one expand per expanded node
