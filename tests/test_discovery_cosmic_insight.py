"""Cosmic Insight Engine — cross-domain structural analogies over the Discovery Graph (4.1)."""

import math

import numpy as np

from gen.discovery import (
    Variable, Constant, DiscoveryProblem, discover_new_formulas, DiscoveryGraph,
    structural_signature, find_analogies, cross_domain_hypotheses,
)
from gen.discovery.benchmark import newton_gravity_case

MU_SUN = 1.32712440018e20


def _coulomb_problem():
    q1 = np.array([1.0, 2.0, 3.0, 1.0, 2.0])
    q2 = np.array([2.0, 1.0, 1.0, 3.0, 2.0])
    r = np.array([1.0, 2.0, 1.0, 0.5, 1.5])
    k = 8.99e9
    Fe = k * q1 * q2 / r ** 2
    return DiscoveryProblem(idea="Elektrostatik", target=Variable("Fe", "N", tuple(Fe)),
                            inputs=(Variable("q1", "Ah", tuple(q1)), Variable("q2", "Ah", tuple(q2)),
                                    Variable("r", "m", tuple(r))),
                            constants=(Constant("k", k, "N*m^2/Ah/Ah"),))


def _kepler_problem():
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11])
    T = 2.0 * math.pi * a ** 1.5 / math.sqrt(MU_SUN)
    return DiscoveryProblem(idea="Himmelsmechanik", target=Variable("T", "s", tuple(T)),
                            inputs=(Variable("a", "m", tuple(a)),),
                            constants=(Constant("mu", MU_SUN, "m^3/s^2"),))


def _graph(*problems):
    g = DiscoveryGraph()
    for p in problems:
        g.add_result(discover_new_formulas(p), target_name=p.target.name)
    return g


def test_structural_signature_abstracts_names_and_units():
    """The shape is the multiset of exponents — names/units don't matter."""
    assert structural_signature({"m1": 1, "m2": 1, "r": -2, "G": 1}) == (-2.0, 1.0, 1.0, 1.0)
    assert structural_signature({"a": 1, "b": 1, "c": -2, "d": 1}) == (-2.0, 1.0, 1.0, 1.0)
    assert structural_signature({"a": 1.5, "mu": -0.5}) == (-0.5, 1.5)   # Kepler shape differs


def test_finds_inverse_square_analogy_across_domains():
    """Newton's gravity and the Coulomb force share the inverse-square shape (-2,1,1,1) — the
    engine reports them as a cross-domain structural analogy."""
    g = _graph(newton_gravity_case().problem, _coulomb_problem())
    analogies = find_analogies(g)
    assert len(analogies) == 1
    a = analogies[0]
    assert a.signature == (-2.0, 1.0, 1.0, 1.0)
    assert "Gravitationskraft zwischen zwei Massen." in a.domains[0] or any("Gravit" in d for d in a.domains)
    assert any("Elektrostatik" in d for d in a.domains)            # spans both domains


def test_no_false_analogy_for_different_shapes():
    """Newton (shape -2,1,1,1) and Kepler (shape -0.5,1.5) are NOT analogous — no false bridge."""
    g = _graph(newton_gravity_case().problem, _kepler_problem())
    assert find_analogies(g) == []


def test_cross_domain_hypothesis_surfaces_a_known_analog():
    """A new inverse-square relation gets a hypothesis pointing at the known law in another
    domain — a proposal for the loop, not a confirmation."""
    g = _graph(newton_gravity_case().problem)                      # graph knows gravity
    hyps = cross_domain_hypotheses(g, _coulomb_problem())          # a new electrostatics relation
    assert hyps
    h = hyps[0]
    assert h.shared_signature == (-2.0, 1.0, 1.0, 1.0)
    assert "Gravit" in h.source_domain and h.target_idea == "Elektrostatik"
    assert h.proposed_expression.startswith("Fe =")


def test_analogies_only_use_confirmed_laws():
    """A graph with only a single domain yields no analogy (need >=2 distinct domains)."""
    g = _graph(newton_gravity_case().problem)
    assert find_analogies(g) == []
