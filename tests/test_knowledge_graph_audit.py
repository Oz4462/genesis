"""Characterization audit for knowledge_graph.py (T05).

Pins the headline claim: the dimensional-type filter is a deterministic disposer
that LLM-only KG systems lack. A cross-domain variable grouping whose dimensions
CANNOT form the target dimension (via power-law monomial) is rejected by
dimensional_type_filter BEFORE any data or gate work.

- Build DiscoveryGraph from a couple of confirmed laws (Kepler + pendulum via
  real benchmark cases).
- Prove filter True on groupings that CAN form target (incl. genuine cross-domain),
  False on spurious/ill-typed (NEGATIVE case) and unknowns.
- Prove propose_cross_domain(seed) is deterministic and emits ONLY subsets for
  which filter returns True; ill-typed subsets never appear.
- Property-based tests (Hypothesis) over seeds for the "only feasible" and
  reproducibility invariants.
- New test file is the authoritative signal (legacy test_knowledge_graph.py
  untouched). Edits to source ONLY on genuine defect (pre-audit: none found).
- Uses stdlib + declared deps only (hypothesis already in dev; no new imports).

If filter accepts ill-typed or propose leaks them -> fix would be required.
Current impl upholds the contract for power-law dimensional feasibility.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gen.discovery.benchmark import kepler_case, pendulum_case
from gen.discovery.knowledge_graph import DiscoveryGraph
from gen.verification.units import parse_unit


def _kg_from_two_confirmed_laws() -> DiscoveryGraph:
    """Populate a knowledge-graph over two confirmed textbook laws.

    In the real campaign flow only *validated* (bestaetigt) results are added;
    here we drive add_law directly from the benchmark problems (the same
    structures that define the "confirmed" cases for rediscovery).
    """
    kg = DiscoveryGraph()
    for case in (kepler_case(), pendulum_case()):
        p = case.problem
        source_units = {v.name: v.unit for v in p.inputs} | {
            c.name: c.unit for c in p.constants
        }
        kg.add_law(
            target_name=p.target.name,
            target_unit=p.target.unit,
            source_units=source_units,
        )
    return kg


_TIME = parse_unit("s")


def test_dimensional_type_filter_true_for_feasible_including_cross_domain():
    kg = _kg_from_two_confirmed_laws()
    # Kepler pair forms time
    assert kg.dimensional_type_filter(["a", "mu"], _TIME) is True
    # pendulum pair forms time
    assert kg.dimensional_type_filter(["L", "g"], _TIME) is True
    # genuine cross-domain: a (Kepler length) + g (pendulum accel) combine to time
    # (sqrt(a/g)), even though no *single* confirmed law ever grouped them.
    assert kg.dimensional_type_filter(["a", "g"], _TIME) is True


def test_dimensional_type_filter_false_for_spurious_negative_case():
    """NEGATIVE / spurious case: dimensions that cannot form the target are rejected.

    This is the core "disposer" behaviour. Two pure lengths cannot synthesize a time
    under any real exponents; unknown names are rejected early.
    """
    kg = _kg_from_two_confirmed_laws()
    # two lengths: L * L^? cannot cancel to T^1
    assert kg.dimensional_type_filter(["a", "L"], _TIME) is False
    # unknown variable never reaches solver
    assert kg.dimensional_type_filter(["a", "no_such_var"], _TIME) is False
    # single mismatched dim
    assert kg.dimensional_type_filter(["a"], _TIME) is False
    # empty
    assert kg.dimensional_type_filter([], _TIME) is False


def test_propose_cross_domain_returns_only_filter_passing_subsets():
    kg = _kg_from_two_confirmed_laws()
    proposals = kg.propose_cross_domain(_TIME, size=2, n=8, seed=0)
    assert proposals, "expected at least some dimensionally feasible proposals"
    for subset in proposals:
        assert kg.dimensional_type_filter(subset, _TIME) is True, (
            f"propose emitted ill-typed subset that filter rejects: {subset}"
        )
    # proposals contain distinct sets (internal seen dedup)
    seen = set(tuple(s) for s in proposals)
    assert len(seen) == len(proposals)


def test_propose_cross_domain_is_deterministic_for_fixed_seed():
    kg = _kg_from_two_confirmed_laws()
    a = kg.propose_cross_domain(_TIME, size=2, n=8, seed=42)
    b = kg.propose_cross_domain(_TIME, size=2, n=8, seed=42)
    assert a == b
    # also for size=1
    c = kg.propose_cross_domain(_TIME, size=1, n=3, seed=7)
    d = kg.propose_cross_domain(_TIME, size=1, n=3, seed=7)
    assert c == d


# --- property-based tests (invariants over sampling) -------------------------

@given(st.integers(min_value=0, max_value=2**31 - 1))
@settings(max_examples=30, deadline=2000)
def test_propose_never_emits_ill_typed_subsets(seed: int):
    """Property-based: across random seeds, every emitted proposal passes the filter.

    This directly verifies the disposer contract: propose_cross_domain is a
    filtered sampler; ill-typed groupings are never returned to the caller.
    """
    kg = _kg_from_two_confirmed_laws()
    for subset in kg.propose_cross_domain(_TIME, size=2, n=5, seed=seed):
        assert kg.dimensional_type_filter(subset, _TIME) is True


@given(st.integers(min_value=0, max_value=1000))
@settings(max_examples=30, deadline=2000)
def test_propose_deterministic_for_any_seed(seed: int):
    """Reproducibility (A5): identical seed => identical proposal sequence.

    Two independent calls on identical graph must match exactly.
    """
    kg = _kg_from_two_confirmed_laws()
    a = kg.propose_cross_domain(_TIME, size=2, n=4, seed=seed)
    b = kg.propose_cross_domain(_TIME, size=2, n=4, seed=seed)
    assert a == b


def test_propose_for_impossible_target_yields_only_feasible_or_empty():
    """When the target dimension cannot be formed from any combination in the graph,
    propose must return the empty list (or only feasibles, of which there are none).
    """
    kg = _kg_from_two_confirmed_laws()
    _K = parse_unit("K")  # temperature; none of L/T/M combos reach it
    props = kg.propose_cross_domain(_K, size=2, n=10, seed=0)
    assert all(kg.dimensional_type_filter(s, _K) for s in props)
    # In this particular graph we expect none
    assert props == []


def test_filter_uses_exact_tolerance_boundary_consistently():
    """The filter decision is exactly the residual < DIMENSION_TOLERANCE test
    (delegated to engine.dimensional_power_law) once membership is satisfied.
    We only assert observable contract, not internal tolerance value.
    """
    kg = _kg_from_two_confirmed_laws()
    # a known zero-residual case
    assert kg.dimensional_type_filter(["a", "mu"], _TIME) is True
    # a known positive-residual case
    assert kg.dimensional_type_filter(["a", "L"], _TIME) is False
