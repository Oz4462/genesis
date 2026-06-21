"""Tests for the composed discovery campaign (discovery/campaign.py).

Pins the live composition: a campaign over several problems collects each confirmed law into the
MAP-Elites archive (diversity) and learns a concept-utility prior from the accumulated ledger; the gate
stays the authority (only confirmed laws are archived). Offline, deterministic.
"""

from gen.discovery.benchmark import ideal_gas_case, kepler_case, pendulum_case
from gen.discovery.campaign import run_campaign
from gen.discovery.concept_utility import ConceptUtility


def _problems():
    return [kepler_case().problem, ideal_gas_case().problem, pendulum_case().problem]


def test_campaign_collects_diverse_confirmed_laws_and_learns_a_prior():
    report = run_campaign(_problems())
    assert report.coverage == 3                       # three structurally distinct confirmed laws
    assert report.validated_count >= 3
    assert isinstance(report.prior, ConceptUtility)
    assert report.archive.best() is not None and report.archive.best().r_squared > 0.99


def test_empty_campaign_is_empty():
    report = run_campaign([])
    assert report.coverage == 0 and report.validated_count == 0


def test_campaign_is_deterministic():
    a, b = run_campaign(_problems()), run_campaign(_problems())
    assert a.coverage == b.coverage and a.validated_count == b.validated_count
    assert [c.expression for c in a.archive.elites()] == [c.expression for c in b.archive.elites()]
