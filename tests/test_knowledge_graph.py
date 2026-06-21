"""Tests for the discovery KG + dimensional-type filter (discovery/knowledge_graph.py).

Pins the deterministic anti-hallucination disposer: the dimensional-type filter accepts groupings whose
dimensions CAN form the target (incl. a genuine cross-domain one), rejects those that cannot and any
with an unknown variable, and propose_cross_domain returns only filter-passing subsets, deterministically.
Offline.
"""

from gen.discovery.knowledge_graph import DiscoveryGraph
from gen.verification.units import parse_unit


def _graph() -> DiscoveryGraph:
    g = DiscoveryGraph()
    g.add_law(target_name="T", target_unit="s", source_units={"a": "m", "mu": "m^3/s^2"})   # Kepler
    g.add_law(target_name="T", target_unit="s", source_units={"L": "m", "g": "m/s^2"})       # pendulum
    return g


_TIME = parse_unit("s")


def test_registers_variables_and_cooccurrence_edges():
    g = _graph()
    assert {"a", "mu", "L", "g"} <= g.variables
    assert g.neighbours("a") == frozenset({"mu"}) and g.neighbours("L") == frozenset({"g"})


def test_dimensional_filter_accepts_feasible_groupings():
    g = _graph()
    assert g.dimensional_type_filter(["a", "mu"], _TIME) is True     # Kepler forms a time
    assert g.dimensional_type_filter(["L", "g"], _TIME) is True      # pendulum forms a time
    # genuine CROSS-DOMAIN feasibility: a (length) and g (accel) form sqrt(L/accel) = time.
    assert g.dimensional_type_filter(["a", "g"], _TIME) is True


def test_dimensional_filter_rejects_infeasible_and_unknown():
    g = _graph()
    assert g.dimensional_type_filter(["a", "L"], _TIME) is False     # two lengths cannot make a time
    assert g.dimensional_type_filter(["a", "nope"], _TIME) is False  # unknown variable -> reject


def test_propose_returns_only_filter_passing_subsets():
    g = _graph()
    proposals = g.propose_cross_domain(_TIME, size=2, n=8, seed=0)
    assert proposals                                                  # at least one feasible grouping
    for subset in proposals:
        assert g.dimensional_type_filter(subset, _TIME) is True       # every proposal is dimensionally feasible


def test_propose_is_deterministic():
    a = _graph().propose_cross_domain(_TIME, size=2, n=8, seed=0)
    b = _graph().propose_cross_domain(_TIME, size=2, n=8, seed=0)
    assert a == b
