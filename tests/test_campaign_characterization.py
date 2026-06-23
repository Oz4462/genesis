"""Characterization / depth-audit tests for discovery/campaign.py.

These tests are facade-detectors: they fail if ``run_campaign`` only *claims* to compose the
learned concept-utility prior, the MAP-Elites archive and the SciAgents cross-domain proposer,
but actually fakes them. They prove the headline claims REALLY hold by asserting outputs change
with driving inputs and that the honest-abstention paths produce empty results, not fabrications.

Three pinned claims (mirroring campaign.py's docstring):
  1. The learned ``ConceptUtility`` prior genuinely ACCUMULATES across problems from the gate
     ledger — a campaign whose ledger holds both passing AND failing verdicts yields a NON-neutral
     prior, while a passing-only campaign yields the neutral (empty) prior. validated_count +
     archive.coverage reflect the real confirmed laws.
  2. ``cross_domain_hypotheses`` is populated ONLY when ``cross_domain_target`` is given, and every
     proposed grouping is dimensionally FEASIBLE toward that target (the impossible are disposed).
     It stays the empty tuple when ``cross_domain_target`` is None.
  3. Honest abstention: an empty problems sequence yields an empty archive / empty hypotheses, and a
     target dimension nothing can reach yields empty hypotheses — never a fabricated result.

All inputs are built via the real engine constructors with small, deterministic, recoverable laws.
Offline, deterministic.
"""

from __future__ import annotations

import math

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from gen.discovery.campaign import CampaignReport, run_campaign
from gen.discovery.concept_utility import ConceptUtility
from gen.discovery.engine import (
    Constant,
    DiscoveryProblem,
    Variable,
    dimensional_power_law,
    DIMENSION_TOLERANCE,
)
from gen.verification.units import parse_unit


# --- small, known, recoverable laws (built via the real engine constructors) -------------

def _pendulum_problem() -> DiscoveryProblem:
    """T = 2π·√(L/g) → recovers T = C·L^(1/2)·g^(-1/2). A clean PASS (complexity 2, vars {L,g})."""
    g = 9.80665
    L = np.array([0.25, 0.5, 1.0, 1.5, 2.0, 0.75])
    T = 2.0 * math.pi * np.sqrt(L / g)
    return DiscoveryProblem(
        idea="Schwingungsdauer eines Fadenpendels.",
        target=Variable("T", "s", tuple(T)),
        inputs=(Variable("L", "m", tuple(L)),),
        constants=(Constant("g", g, "m/s^2"),),
    )


def _area_problem() -> DiscoveryProblem:
    """A = π·r² → recovers A = C·r^2. A clean PASS in a DIFFERENT cell (complexity 1, vars {r})."""
    r = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    A = math.pi * r ** 2
    return DiscoveryProblem(
        idea="Kreisfläche aus dem Radius.",
        target=Variable("A", "m^2", tuple(A)),
        inputs=(Variable("r", "m", tuple(r)),),
    )


def _offset_failure_problem() -> DiscoveryProblem:
    """v = g·t + v0 — dimensionally valid but the additive offset blocks a pure power law, so the fit
    gate keeps it 'unentschieden' (passed=False). It contributes the FAILING records the contrastive
    prior needs to become non-neutral; it is NOT archived (only confirmed laws are)."""
    g = 9.80665
    t = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    v = g * t + 40.0
    return DiscoveryProblem(
        idea="Geschwindigkeit im freien Fall mit Anfangsgeschwindigkeit.",
        target=Variable("v", "m/s", tuple(v)),
        inputs=(Variable("t", "s", tuple(t)),),
        constants=(Constant("g", g, "m/s^2"),),
    )


def _mixed_campaign_problems() -> list[DiscoveryProblem]:
    """Two passing laws (distinct cells) + one failing case → a ledger with both verdict signs."""
    return [_pendulum_problem(), _area_problem(), _offset_failure_problem()]


def _unit_of_every_variable(problems: list[DiscoveryProblem]) -> dict[str, str]:
    """Name → unit for every target/input/constant in the campaign (units are consistent across laws)."""
    units: dict[str, str] = {}
    for p in problems:
        units[p.target.name] = p.target.unit
        for v in p.inputs:
            units[v.name] = v.unit
        for c in p.constants:
            units[c.name] = c.unit
    return units


def _group_is_dimensionally_feasible(group: tuple[str, ...], target_unit: str,
                                     units: dict[str, str]) -> bool:
    """Independently re-derive whether ``group``'s dimensions can form ``target_unit`` (residual ≈ 0).
    This is the SAME disposer the KG uses, recomputed here so the test does not trust the module."""
    dims = [parse_unit(units[name]) for name in group]
    _, residual = dimensional_power_law(parse_unit(target_unit), list(group), dims)
    return residual < DIMENSION_TOLERANCE


# --- Claim 1: the learned prior genuinely accumulates from the gate ledger ----------------

def test_passing_only_campaign_yields_the_neutral_prior():
    """No failing verdicts in the ledger → nothing to contrast → the prior is the empty/neutral one.

    This is the BASELINE the accumulation claim is measured against: if even a passing-only campaign
    returned a non-empty utility, the 'learned' prior would be fabricated rather than contrastive.
    """
    report = run_campaign([_pendulum_problem(), _area_problem()])
    assert isinstance(report.prior, ConceptUtility)
    # A contrastive utility needs BOTH a pass and a fail side; with passes only it is empty (all-zero).
    assert report.prior.utility("var:L") == 0.0
    best = report.archive.best()
    assert best is not None
    assert report.prior.score(best) == 0.0  # neutral on every candidate


def test_multi_problem_prior_is_non_neutral_and_differs_from_the_empty_prior():
    """A campaign whose ledger holds both passing and failing verdicts learns a real, non-neutral prior.

    Concretely: ``var:L`` and the pendulum's exponents appear ONLY among passing candidates, so their
    contrastive utility is strictly positive — and the report's prior scores a confirmed law ABOVE the
    empty first-problem prior (which scores 0 for everything). This is the facade-killer: a faked prior
    would score 0 like the empty one.
    """
    report = run_campaign(_mixed_campaign_problems())
    empty_prior = ConceptUtility()  # the neutral prior the first problem starts from

    best = report.archive.best()
    assert best is not None
    # A concept seen only on the passing side must carry positive learned utility.
    assert report.prior.utility("var:L") > 0.0
    # The learned prior is genuinely different from the empty prior on a real confirmed candidate.
    assert report.prior.score(best) > 0.0
    assert empty_prior.score(best) == 0.0
    assert report.prior.score(best) != empty_prior.score(best)


def test_validated_count_and_coverage_reflect_the_real_confirmed_laws():
    """The two passing laws fill two distinct MAP-Elites cells; the failing case adds neither.

    Pins that the headline counters are computed from real gate verdicts, not hard-coded: coverage is the
    number of distinct confirmed structural cells (2) and validated_count counts confirmed verdicts (≥2),
    while the offset case — present in the input — contributes 0 to both because the gate rejects it.
    """
    report = run_campaign(_mixed_campaign_problems())
    assert report.coverage == 2                       # pendulum cell + area cell, distinct
    assert report.validated_count >= 2                # at least one confirmed verdict per passing law
    best = report.archive.best()
    assert best is not None and best.r_squared > 0.99  # archived laws are genuine fits
    # Every archived elite must have been a gate PASS (the archive's load-bearing invariant).
    assert len(report.archive.elites()) == report.coverage


def test_dropping_the_failing_case_collapses_the_prior_to_neutral():
    """The prior RESPONDS to the accumulated ledger: remove the only failing problem and the same two
    passing laws now yield the neutral prior — proving the utility is fit from real verdicts, not canned."""
    with_fail = run_campaign(_mixed_campaign_problems())
    without_fail = run_campaign([_pendulum_problem(), _area_problem()])
    assert with_fail.prior.utility("var:L") > 0.0
    assert without_fail.prior.utility("var:L") == 0.0


# --- Claim 2: cross-domain hypotheses are gated by the dimensional-type filter -------------

def test_cross_domain_hypotheses_only_when_target_given():
    """Default ``cross_domain_target=None`` leaves the report's hypotheses the empty tuple."""
    report = run_campaign(_mixed_campaign_problems())  # no cross_domain_target
    assert report.cross_domain_hypotheses == ()


def test_cross_domain_hypotheses_are_all_dimensionally_feasible():
    """With a reachable target, hypotheses are non-empty AND every grouping is independently feasible.

    The facade here would be groupings that do NOT actually form the target dimension (the SciAgents
    spurious-path failure mode). We recompute feasibility from scratch and reject any leak.
    """
    problems = _mixed_campaign_problems()
    report = run_campaign(problems, cross_domain_target="s")
    units = _unit_of_every_variable(problems)

    assert isinstance(report.cross_domain_hypotheses, tuple)
    assert len(report.cross_domain_hypotheses) > 0  # 's' is reachable from {L,g}, etc.
    for group in report.cross_domain_hypotheses:
        assert isinstance(group, tuple)
        assert _group_is_dimensionally_feasible(group, "s", units), \
            f"leaked dimensionally-impossible grouping: {group}"


@settings(max_examples=25, deadline=None)
@given(seed=st.integers(min_value=0, max_value=10_000))
def test_property_every_proposed_grouping_is_feasible_for_any_seed(seed: int):
    """INVARIANT: for ANY proposal seed, every grouping the campaign returns is dimensionally feasible
    toward the target. The dimensional-type filter must hold regardless of which random subsets are drawn.
    """
    problems = _mixed_campaign_problems()
    report = run_campaign(problems, cross_domain_target="s", cross_domain_seed=seed)
    units = _unit_of_every_variable(problems)
    for group in report.cross_domain_hypotheses:
        assert _group_is_dimensionally_feasible(group, "s", units)


# --- Claim 3: honest abstention (empty / unreachable) -------------------------------------

def test_empty_campaign_abstains_everywhere():
    """An empty problems sequence yields an empty archive, zero counts, a neutral prior and — even with a
    target requested — no hypotheses (the KG has no variables to draw from). No fabricated result."""
    report = run_campaign([], cross_domain_target="s")
    assert isinstance(report, CampaignReport)
    assert report.coverage == 0
    assert report.validated_count == 0
    assert report.archive.best() is None
    assert report.cross_domain_hypotheses == ()
    assert report.prior.score  # the prior exists and is the neutral one
    assert report.prior.utility("var:L") == 0.0


def test_unreachable_target_dimension_yields_no_hypotheses():
    """A target dimension nothing in the campaign can form ('mol' — no variable carries amount-of-
    substance) yields the empty tuple, NOT a fabricated cross-domain finding."""
    report = run_campaign(_mixed_campaign_problems(), cross_domain_target="mol")
    assert report.cross_domain_hypotheses == ()


def test_campaign_is_deterministic():
    """Same problems + same seed → byte-identical headline outputs (A5 reproducibility)."""
    a = run_campaign(_mixed_campaign_problems(), cross_domain_target="s", cross_domain_seed=7)
    b = run_campaign(_mixed_campaign_problems(), cross_domain_target="s", cross_domain_seed=7)
    assert a.coverage == b.coverage
    assert a.validated_count == b.validated_count
    assert a.cross_domain_hypotheses == b.cross_domain_hypotheses
    assert [c.expression for c in a.archive.elites()] == [c.expression for c in b.archive.elites()]
