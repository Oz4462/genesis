"""Depth-audit / characterization tests for the Cosmic Insight Engine (build doc 4.1).

These tests are FACADE DETECTORS: they fail if ``cosmic_insight`` is a hollow stub that
returns canned analogies regardless of its input. Each test proves the headline claim — that
the engine finds CROSS-DOMAIN structural analogies by ABSTRACTING AWAY variable names and
units — REALLY holds, by asserting that

  (a) the output changes meaningfully when a driving input changes (the graph's confirmed
      laws / their domains are genuinely consumed, not a constant), and
  (b) the documented fail-loud path raises ValueError on empty/bad target data.

The confirmed graph nodes are built through the REAL ``discover_new_formulas`` →
``add_result`` path (so a node only counts if it actually passed the discovery gate), and the
problems are built through the real engine constructors — no node is hand-forged into the
``bestaetigt`` bucket.
"""

import dataclasses
import math

import numpy as np
import pytest
from hypothesis import given, strategies as st

from gen.discovery import (
    Constant,
    DiscoveryGraph,
    DiscoveryProblem,
    Variable,
    cross_domain_hypotheses,
    discover_new_formulas,
    find_analogies,
    structural_signature,
)
from gen.discovery.benchmark import newton_gravity_case

# Coulomb's constant carries the same shape as Newton's G in the dimensional solve.
COULOMB_K = 8.99e9
MU_SUN = 1.32712440018e20


def _coulomb_problem(idea: str = "Elektrostatik") -> DiscoveryProblem:
    """An inverse-square electrostatics law ``Fe = k·q1·q2·r^(-2)`` — the canonical
    cross-domain twin of Newton's gravitation, with DIFFERENT variable names and units."""
    q1 = np.array([1.0, 2.0, 3.0, 1.0, 2.0])
    q2 = np.array([2.0, 1.0, 1.0, 3.0, 2.0])
    r = np.array([1.0, 2.0, 1.0, 0.5, 1.5])
    fe = COULOMB_K * q1 * q2 / r ** 2
    return DiscoveryProblem(
        idea=idea,
        target=Variable("Fe", "N", tuple(fe)),
        inputs=(Variable("q1", "Ah", tuple(q1)), Variable("q2", "Ah", tuple(q2)),
                Variable("r", "m", tuple(r))),
        constants=(Constant("k", COULOMB_K, "N*m^2/Ah/Ah"),))


def _kepler_problem(idea: str = "Himmelsmechanik") -> DiscoveryProblem:
    """Kepler's third law ``T = 2π·a^(3/2)·mu^(-1/2)`` — shape (-0.5, 1.5), a DIFFERENT
    structural shape from the inverse-square family."""
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11])
    period = 2.0 * math.pi * a ** 1.5 / math.sqrt(MU_SUN)
    return DiscoveryProblem(
        idea=idea,
        target=Variable("T", "s", tuple(period)),
        inputs=(Variable("a", "m", tuple(a)),),
        constants=(Constant("mu", MU_SUN, "m^3/s^2"),))


def _newton_problem(idea: str | None = None) -> DiscoveryProblem:
    """Newton's gravitation from the benchmark; optionally re-tagged with a different idea so
    we can place two distinct-shaped laws under the SAME domain in one graph."""
    problem = newton_gravity_case().problem
    if idea is not None:
        problem = dataclasses.replace(problem, idea=idea)
    return problem


def _graph(*problems: DiscoveryProblem) -> DiscoveryGraph:
    """Build a graph by running REAL discovery on each problem and recording every verdict —
    only laws that genuinely pass the gate land in ``confirmed()``."""
    graph = DiscoveryGraph()
    for problem in problems:
        graph.add_result(discover_new_formulas(problem), target_name=problem.target.name)
    return graph


# --------------------------------------------------------------------------------------------
# (1) structural_signature: the shape abstracts names + units
# --------------------------------------------------------------------------------------------

def test_signature_abstracts_names_and_units_to_one_shape():
    """Newton ``{m1,m2,r,G}`` and Coulomb ``{q1,q2,r,k}`` — different names/units — collapse to
    the identical inverse-square shape ``(-2, 1, 1, 1)``."""
    newton = structural_signature({"m1": 1, "m2": 1, "r": -2, "G": 1})
    coulomb = structural_signature({"q1": 1, "q2": 1, "r": -2, "k": 1})
    assert newton == (-2.0, 1.0, 1.0, 1.0)
    assert coulomb == newton  # names + units abstracted away -> same shape


def test_signature_distinguishes_a_different_shape():
    """A law with a different exponent multiset (Kepler's (-0.5, 1.5)) yields a DIFFERENT
    tuple — the signature is not a constant, it tracks the actual exponents."""
    kepler = structural_signature({"a": 1.5, "mu": -0.5})
    assert kepler == (-0.5, 1.5)
    assert kepler != structural_signature({"m1": 1, "m2": 1, "r": -2, "G": 1})


def test_signature_drops_near_zero_exponents():
    """Exponents that are effectively zero are not part of the shape (an absent variable does
    not change a law's structure)."""
    assert structural_signature({"a": 1.0, "b": 0.0, "c": 1e-12}) == (1.0,)


@given(st.lists(st.floats(min_value=-9.0, max_value=9.0, allow_nan=False, allow_infinity=False),
                min_size=0, max_size=8))
def test_signature_is_rename_invariant_and_sorted(values):
    """INVARIANT: the signature depends ONLY on the multiset of (rounded, non-near-zero)
    exponent VALUES — never on the variable names or their insertion order — and is sorted.
    This is the property the whole engine rests on (analogy by shape, not by name)."""
    exps_named_x = {f"x{i}": v for i, v in enumerate(values)}
    exps_named_y = {f"y{i}": v for i, v in enumerate(values)}  # same values, different names
    sig_x = structural_signature(exps_named_x)
    sig_y = structural_signature(exps_named_y)

    assert sig_x == sig_y                                   # names abstracted away
    assert list(sig_x) == sorted(sig_x)                     # sorted multiset
    expected = tuple(sorted(round(v, 6) for v in values if abs(v) >= 1e-9))
    assert sig_x == expected                                # exactly the non-zero shape


# --------------------------------------------------------------------------------------------
# (2) find_analogies: a shared shape is an analogy ONLY across >=2 distinct domains
# --------------------------------------------------------------------------------------------

def test_finds_inverse_square_bridge_across_two_domains():
    """Newton (gravity) + Coulomb (electrostatics) share shape (-2,1,1,1) from DIFFERENT ideas
    -> exactly one analogy spanning both domains. The headline cross-domain claim."""
    graph = _graph(_newton_problem(), _coulomb_problem())
    analogies = find_analogies(graph)
    assert len(analogies) == 1
    analogy = analogies[0]
    assert analogy.signature == (-2.0, 1.0, 1.0, 1.0)
    assert len(analogy.domains) == 2
    assert any("Gravit" in d for d in analogy.domains)
    assert any("Elektro" in d for d in analogy.domains)


def test_no_analogy_for_two_laws_in_the_SAME_domain():
    """FACADE KILLER for the honest cross-domain requirement: two laws that share the
    inverse-square shape but come from the SAME idea are NOT an analogy. If the engine ignored
    the domain split (and only counted members), this would falsely report a bridge."""
    same = "Vereinheitlichte Feldtheorie"
    # Two structurally-identical (-2,1,1,1) laws, distinct variable names (so distinct nodes),
    # both tagged with the SAME idea.
    graph = _graph(_newton_problem(idea=same), _coulomb_problem(idea=same))
    # Sanity: both really confirmed and share the shape -> 2 nodes, 1 domain.
    confirmed = graph.confirmed()
    assert len(confirmed) == 2
    assert len({structural_signature(n.exponent_signature) for n in confirmed}) == 1
    assert {n.input_idea for n in confirmed} == {same}
    # ... yet NO analogy, because a single domain is not a cross-domain bridge.
    assert find_analogies(graph) == []


def test_no_analogy_for_different_shapes_across_domains():
    """Two confirmed laws from different domains but DIFFERENT shapes (Newton vs Kepler) are
    not a bridge — the shape, not just the domain spread, must match."""
    graph = _graph(_newton_problem(), _kepler_problem())
    assert find_analogies(graph) == []


def test_single_domain_graph_yields_no_analogy():
    """Driving input check: one domain -> no analogy; the SAME graph plus a second domain of
    the same shape -> an analogy. Proves the domain set is genuinely consumed."""
    one_domain = _graph(_newton_problem())
    assert find_analogies(one_domain) == []
    two_domains = _graph(_newton_problem(), _coulomb_problem())
    assert len(find_analogies(two_domains)) == 1


def test_min_members_threshold_is_honoured():
    """The ``min_members`` knob is a real driving input: two confirmed laws span two domains
    and form a bridge at the default (2), but NOT when at least three members are demanded."""
    graph = _graph(_newton_problem(), _coulomb_problem())
    assert len(find_analogies(graph, min_members=2)) == 1
    assert find_analogies(graph, min_members=3) == []


# --------------------------------------------------------------------------------------------
# (3) cross_domain_hypotheses: only from a DIFFERENT domain; fail loud on bad target
# --------------------------------------------------------------------------------------------

def test_hypothesis_surfaces_known_analog_from_other_domain():
    """The graph knows gravity; a NEW electrostatics relation of the same shape gets a
    hypothesis pointing back at the known law in the OTHER domain — a proposal, not a
    confirmation."""
    graph = _graph(_newton_problem())                       # graph knows gravity only
    hyps = cross_domain_hypotheses(graph, _coulomb_problem())
    assert len(hyps) == 1
    hyp = hyps[0]
    assert hyp.shared_signature == (-2.0, 1.0, 1.0, 1.0)
    assert "Gravit" in hyp.source_domain                    # the analog is in the other domain
    assert hyp.target_idea == "Elektrostatik"
    assert hyp.proposed_expression.startswith("Fe =")


def test_no_hypothesis_from_the_same_domain():
    """FACADE KILLER for the cross-domain requirement: a known law and the target sharing the
    SAME idea must NOT produce a hypothesis (an analogy to oneself is not cross-domain). If the
    engine skipped the same-idea guard, this would wrongly surface a self-analogy."""
    same = "Elektrostatik"
    # The graph's only confirmed law is gravity-shaped but tagged with the target's own idea.
    graph = _graph(_newton_problem(idea=same))
    hyps = cross_domain_hypotheses(graph, _coulomb_problem(idea=same))
    assert hyps == []


def test_hypothesis_empty_when_no_shape_match():
    """A target whose shape matches nothing confirmed in another domain yields no hypothesis —
    the engine does not fabricate a bridge."""
    graph = _graph(_kepler_problem())                       # only the (-0.5, 1.5) shape known
    assert cross_domain_hypotheses(graph, _coulomb_problem()) == []


def test_cross_domain_hypotheses_raises_on_empty_target():
    """Documented fail-loud: empty target data raises ValueError (via the engine) rather than
    fabricating a candidate — 'keine stillen Defaults'."""
    graph = _graph(_newton_problem())
    empty_target = DiscoveryProblem(
        idea="Leer",
        target=Variable("Fe", "N", ()),
        inputs=(Variable("q1", "Ah", ()),),
        constants=(Constant("k", COULOMB_K, "N*m^2/Ah/Ah"),))
    with pytest.raises(ValueError):
        cross_domain_hypotheses(graph, empty_target)


def test_cross_domain_hypotheses_raises_on_nonpositive_target():
    """A non-positive target magnitude is dimensionally invalid for power-law discovery and
    raises ValueError — the engine refuses to guess instead of returning nan."""
    graph = _graph(_newton_problem())
    bad_target = DiscoveryProblem(
        idea="Negativ",
        target=Variable("Fe", "N", (1.0, -2.0, 3.0)),
        inputs=(Variable("q1", "Ah", (1.0, 2.0, 3.0)),),
        constants=(Constant("k", COULOMB_K, "N*m^2/Ah/Ah"),))
    with pytest.raises(ValueError):
        cross_domain_hypotheses(graph, bad_target)
