"""campaign cross-domain hypotheses: SciAgents KG breadth + GENESIS's dimensional-type disposer.

Pins the opt-in knowledge_graph wiring in run_campaign: a knowledge graph is built over the campaign's
CONFIRMED laws, and cross-domain source groupings (variables drawn from across DIFFERENT laws) are
proposed toward a target dimension — but only those that PASS the deterministic dimensional-type filter
survive. The KG suggests breadth; the dimensional types dispose the impossible BEFORE any gate work; the
groupings are hypotheses (gate inputs / open questions), never confirmed findings.

The campaign confirms Kepler (T from a, mu) and the pendulum (T from L, g). Toward a time target, a
length-only pair like (a, L) can never form a time and is filtered out, while a genuinely cross-domain
pair like (a, g) — Kepler's axis with the pendulum's gravity — is dimensionally feasible and surfaces.
Offline, deterministic.
"""

from gen.discovery.benchmark import kepler_case, pendulum_case
from gen.discovery.campaign import run_campaign
from gen.discovery.knowledge_graph import DiscoveryGraph as KnowledgeGraph
from gen.verification.units import parse_unit


def _campaign(**kw):
    return run_campaign([kepler_case().problem, pendulum_case().problem], **kw)


def _kg_over_the_confirmed_laws():
    kg = KnowledgeGraph()
    for case in (kepler_case(), pendulum_case()):
        p = case.problem
        kg.add_law(target_name=p.target.name, target_unit=p.target.unit,
                   source_units={v.name: v.unit for v in p.inputs}
                   | {c.name: c.unit for c in p.constants})
    return kg


def test_no_target_means_no_cross_domain_hypotheses():
    assert _campaign().cross_domain_hypotheses == ()         # opt-in: default leaves the report unchanged


def test_every_hypothesis_is_dimensionally_feasible_toward_the_target():
    rep = _campaign(cross_domain_target="s")
    assert rep.cross_domain_hypotheses
    kg, time = _kg_over_the_confirmed_laws(), parse_unit("s")
    for group in rep.cross_domain_hypotheses:                # soundness: the disposer admitted only feasible ones
        assert kg.dimensional_type_filter(list(group), time)


def test_dimensionally_impossible_grouping_is_filtered_out():
    rep = _campaign(cross_domain_target="s")
    # a and L are both lengths — no power product of two lengths is a time, so the disposer must reject it.
    assert ("a", "L") not in rep.cross_domain_hypotheses
    assert ("L", "a") not in rep.cross_domain_hypotheses


def test_a_genuinely_cross_domain_feasible_pair_survives():
    rep = _campaign(cross_domain_target="s")
    # Kepler's semi-major axis a + the pendulum's gravity g form a time dimensionally, though no single
    # confirmed law combined them — SciAgents breadth, dimensionally disposed, surfaced as a hypothesis.
    assert ("a", "g") in rep.cross_domain_hypotheses


def test_cross_domain_proposal_is_deterministic():
    assert _campaign(cross_domain_target="s").cross_domain_hypotheses == \
        _campaign(cross_domain_target="s").cross_domain_hypotheses
