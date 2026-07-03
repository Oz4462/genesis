"""Discovery Graph — the deduped, Ledger-aligned long-term memory (build doc 4.6 / Anhang C)."""

import json
import math

import numpy as np
import pytest

from gen.discovery import Variable, Constant, DiscoveryProblem, discover_new_formulas
from gen.discovery import DiscoveryGraph

MU_SUN = 1.32712440018e20


def _kepler_result():
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11])
    T = 2.0 * math.pi * a ** 1.5 / math.sqrt(MU_SUN)
    return discover_new_formulas(DiscoveryProblem(
        idea="Kepler", target=Variable("T", "s", tuple(T)),
        inputs=(Variable("a", "m", tuple(a)),),
        constants=(Constant("mu", MU_SUN, "m^3/s^2"),), run_id="g-001"))


def test_records_every_candidate_with_anhang_c_schema():
    g = DiscoveryGraph()
    nodes = g.add_result(_kepler_result(), target_name="T", provenance=("mensch", "forge"),
                         timestamp="2026-06-18T00:00:00Z")
    assert nodes and len(g) == len(nodes)
    rec = nodes[0].to_record()
    for key in ("id", "timestamp", "input_idea", "candidate", "delta_to_consensus",
                "gates", "verdict", "provenance", "parent_ids", "graph_edges"):
        assert key in rec
    assert rec["provenance"] == ["mensch", "forge"]


def test_dedup_collapses_a_rediscovery_onto_one_node():
    """The whole point of the graph: the SAME law discovered twice does not duplicate — it
    increments the encounter count and merges provenance (verhindert doppelte Neu-Entdeckung)."""
    g = DiscoveryGraph()
    g.add_result(_kepler_result(), target_name="T", provenance=("run-1",))
    n_after_first = len(g)
    g.add_result(_kepler_result(), target_name="T", provenance=("run-2",))
    assert len(g) == n_after_first                     # no new nodes — it is already known
    confirmed = g.confirmed()
    assert confirmed and confirmed[0].encounters >= 2
    assert "run-1" in confirmed[0].provenance and "run-2" in confirmed[0].provenance


def test_is_known_guards_rediscovery():
    g = DiscoveryGraph()
    g.add_result(_kepler_result(), target_name="T")
    assert g.is_known("T", {"a": 1.5, "mu": -0.5})     # exact signature is recognised
    assert not g.is_known("T", {"a": 2.0, "mu": -0.5})  # a different law is not


def test_confirmed_discovery_present_and_edges_link():
    g = DiscoveryGraph()
    g.add_result(_kepler_result(), target_name="T")
    confirmed = g.confirmed()
    assert confirmed and confirmed[0].verdict == "bestaetigt"
    # a second (toy) node to link to
    a = np.array([1.0, 2.0, 3.0, 4.0])
    other = discover_new_formulas(DiscoveryProblem(
        idea="toy", target=Variable("F", "N", tuple(2.0 * a)),
        inputs=(Variable("m", "g", tuple(a)), Variable("acc", "m/s^2", tuple(2.0 * np.ones(4)))),))
    g.add_result(other, target_name="F")
    src = confirmed[0].id
    dst = g.nodes()[-1].id
    g.link(src, dst, "analog_zu")
    assert any("analog_zu" in e for e in g.get(src).graph_edges)
    with pytest.raises(KeyError):
        g.link(src, "deadbeef", "analog_zu")


def test_to_json_round_trips():
    g = DiscoveryGraph()
    g.add_result(_kepler_result(), target_name="T", timestamp="2026-06-18T00:00:00Z")
    parsed = json.loads(g.to_json())
    assert isinstance(parsed, list) and parsed
    assert all("verdict" in r and "id" in r for r in parsed)


def test_discover_facade_runs_and_records_in_one_call():
    """The one-call entry (Anhang B): run discovery AND deposit every candidate in a graph;
    a second run on a long-lived graph dedups onto the same confirmed node."""
    from gen.discovery import discover
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11])
    T = 2.0 * math.pi * a ** 1.5 / math.sqrt(MU_SUN)
    problem = DiscoveryProblem(
        idea="Kepler", target=Variable("T", "s", tuple(T)),
        inputs=(Variable("a", "m", tuple(a)),),
        constants=(Constant("mu", MU_SUN, "m^3/s^2"),))
    result, graph = discover(problem, provenance=("mensch", "grok"))
    assert result.validated and result.validated[0].verdict == "bestaetigt"
    assert graph.confirmed()
    # accumulate: a second run on the SAME graph does not duplicate the discovery
    n_before = len(graph)
    discover(problem, graph=graph)
    assert len(graph) == n_before
