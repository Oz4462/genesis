"""Symbiosis Protocol — Grok proposes breadth, GENESIS gates every proposal (build doc 4.4).

All offline + deterministic: the Grok proposer sits behind the mockable LLMClient seam
(ScriptedLLM), so no live grok call is needed in the suite. The hard law — Grok = proposal,
never truth — is what the tests pin.
"""

import asyncio
import math

import numpy as np
import pytest

from gen.discovery import Variable, Constant, DiscoveryProblem
from gen.discovery import symbiosis_discover, GrokProposer, Proposal
from gen.llm.base import ScriptedLLM
from gen.verification.cross_model import assert_different_families

MU_SUN = 1.32712440018e20


def _kepler():
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11, 1.434e12])
    T = 2.0 * math.pi * a ** 1.5 / math.sqrt(MU_SUN)
    return DiscoveryProblem(idea="Kepler", target=Variable("T", "s", tuple(T)),
                            inputs=(Variable("a", "m", tuple(a)),),
                            constants=(Constant("mu", MU_SUN, "m^3/s^2"),))


def test_every_proposal_is_gated_and_a_wrong_one_is_rejected():
    """A correct AND a dimensionally-impossible proposal are BOTH gated; only the correct one
    is validated — a Grok hypothesis is never accepted on Grok's say-so."""
    proposals = [
        Proposal(exponents={"a": 1.5, "mu": -0.5}, rationale="Kepler", source="grok-build"),
        Proposal(exponents={"a": 1.0, "mu": 1.0}, rationale="raten", source="grok-build"),
    ]
    res = symbiosis_discover(_kepler(), proposals=proposals)
    assert len(res.judged_proposals) == 2
    verdicts = {tuple(sorted(j.proposal.exponents.items())): j.verdict.verdict for j in res.judged_proposals}
    assert verdicts[(("a", 1.5), ("mu", -0.5))] == "bestaetigt"
    assert verdicts[(("a", 1.0), ("mu", 1.0))] == "widerlegt"          # dimensionally impossible
    assert any(v.candidate.expression.startswith("T =") and abs(v.candidate.exponents["a"] - 1.5) < 1e-6
               for v in res.validated)


def test_runs_without_grok_fallback():
    """No proposer → GENESIS still rediscovers Kepler on its own (never depends on Grok)."""
    res = symbiosis_discover(_kepler())
    assert res.used_proposer is False
    assert res.own.validated and res.own.validated[0].verdict == "bestaetigt"
    assert res.validated and abs(res.validated[0].candidate.exponents["a"] - 1.5) < 1e-3


def test_grok_proposer_parses_hypotheses_via_mock_client():
    """The Grok path parses JSON hypotheses into Proposals — tested with a scripted client
    (the same LLMClient seam GrokCLI implements), so no live grok is needed."""
    canned = ('Hier die Hypothesen:\n[{"exponents": {"a": 1.5, "mu": -0.5}, "rationale": "Kepler"},'
              ' {"exponents": {"a": 2.0}, "rationale": "raten"}]')
    proposer = GrokProposer(ScriptedLLM("grok-build", lambda system, user: canned))
    props = asyncio.run(proposer.propose(_kepler(), n=2))
    assert len(props) == 2
    assert props[0].exponents == {"a": 1.5, "mu": -0.5}
    assert all(p.source == "grok-build" for p in props)


def test_proposer_is_xai_family_and_cross_model_split_holds():
    """The proposer is the xAI family; the deterministic gate is the verifier (stronger than an
    LLM split). The family helper still enforces a real split when two models are paired."""
    proposer = GrokProposer(ScriptedLLM("grok-build", lambda system, user: "[]"))
    assert proposer.family == "xai"
    assert_different_families("grok-build", "claude-opus-4-8")          # ok: different families
    with pytest.raises(Exception):
        assert_different_families("grok-build", "grok-build")           # same family rejected


def test_symbiosis_end_to_end_with_mock_proposer():
    """The full loop with a (mock) Grok proposer: the proposal is fetched, gated, and the valid
    one is rediscovered — used_proposer is True."""
    canned = '[{"exponents": {"a": 1.5, "mu": -0.5}, "rationale": "Kepler III"}]'
    proposer = GrokProposer(ScriptedLLM("grok-build", lambda system, user: canned))
    res = symbiosis_discover(_kepler(), proposer=proposer)
    assert res.used_proposer is True
    assert any(j.verdict.verdict == "bestaetigt" for j in res.judged_proposals)
