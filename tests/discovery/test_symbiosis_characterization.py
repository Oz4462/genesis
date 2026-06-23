"""Characterization test for discovery/symbiosis.py — the cross-model drift-check guarantee.

Headline claim under audit (CLAUDE.md §3 / build doc 4.4): a SECOND model, of a DIFFERENT
family than the model that produced a claimed law, INDEPENDENTLY verifies it; agreement is
accepted with no drift, while disagreement is surfaced as DRIFT and never silently passed off as
"verified". Single-model self-check is refused, and a verifier that cannot answer abstains
honestly rather than faking a pass.

If ``cross_model_drift_check`` were a hollow facade — always returning "verified", or accepting
the generator's claim on its own authority — these assertions fail. Everything runs offline via
``ScriptedLLM`` / a stub client (NO network, NO live CLI).
"""

import math

import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

from gen.discovery import Variable, Constant, DiscoveryProblem
from gen.discovery.symbiosis import (
    cross_model_drift_check, DriftReport, Proposal,
    DRIFT_CORROBORATED, DRIFT_DETECTED, DRIFT_ABSTAINED,
)
from gen.core.errors import ModelConflictError
from gen.llm.base import ScriptedLLM, LLMResponse

MU_SUN = 1.32712440018e20

# The generator (grok, xAI family) claims the true Kepler-III power law.
GENERATOR_MODEL = "grok-build"
CLAIM = Proposal(exponents={"a": 1.5, "mu": -0.5}, rationale="Kepler III", source=GENERATOR_MODEL)

# Verifier proposal payloads (what the SECOND model independently returns).
AGREE_JSON = '[{"exponents": {"a": 1.5, "mu": -0.5}, "rationale": "T=2pi sqrt(a^3/mu)"}]'
DISAGREE_JSON = ('[{"exponents": {"a": 1.0, "mu": 1.0}, "rationale": "linear, dimensional Unsinn"},'
                 ' {"exponents": {"a": 2.0}, "rationale": "ohne mu, falsch"}]')


def _kepler() -> DiscoveryProblem:
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11, 1.434e12])
    T = 2.0 * math.pi * a ** 1.5 / math.sqrt(MU_SUN)
    return DiscoveryProblem(idea="Kepler", target=Variable("T", "s", tuple(T)),
                            inputs=(Variable("a", "m", tuple(a)),),
                            constants=(Constant("mu", MU_SUN, "m^3/s^2"),))


class _ExplodingClient:
    """An ``LLMClient`` whose call always fails — models a verifier tool error / timeout."""

    def __init__(self, model: str) -> None:
        self.model = model

    async def complete(self, *, system: str, user: str) -> LLMResponse:
        raise TimeoutError("verifier CLI timed out")


# --- HAPPY PATH: second model agrees -> corroborated, no drift, verified ---------------------------

def test_agreeing_verifier_corroborates_with_no_drift():
    """A different-family verifier that independently re-derives the SAME gated law corroborates
    the claim: verified=True, drift=False."""
    verifier = ScriptedLLM("claude-opus-4-8", AGREE_JSON)  # claude family != xai
    report = cross_model_drift_check(_kepler(), CLAIM,
                                     generator_model=GENERATOR_MODEL, verifier=verifier)
    assert isinstance(report, DriftReport)
    assert report.status == DRIFT_CORROBORATED
    assert report.verified is True
    assert report.drift is False
    assert report.verifier_passed  # the verifier actually produced a gate-passed law
    assert any(abs(j.proposal.exponents["a"] - 1.5) < 1e-6 for j in report.verifier_passed)


# --- DRIFT: second model disagrees -> flagged as drift, NOT verified -------------------------------

def test_disagreeing_verifier_flags_drift_and_does_not_verify():
    """A verifier that proposes only contradictory / dimensionally-wrong laws fails to corroborate.
    The module must flag DRIFT and must NOT silently report the claim as verified."""
    verifier = ScriptedLLM("claude-opus-4-8", DISAGREE_JSON)
    report = cross_model_drift_check(_kepler(), CLAIM,
                                     generator_model=GENERATOR_MODEL, verifier=verifier)
    assert report.status == DRIFT_DETECTED
    assert report.drift is True
    assert report.verified is False  # the core anti-facade assertion: no silent pass


def test_empty_verifier_response_does_not_verify():
    """A verifier that returns nothing usable cannot corroborate — never a fake 'verified'."""
    verifier = ScriptedLLM("claude-opus-4-8", "ich weiss es nicht")  # no JSON -> no proposals
    report = cross_model_drift_check(_kepler(), CLAIM,
                                     generator_model=GENERATOR_MODEL, verifier=verifier)
    assert report.verified is False
    assert report.status == DRIFT_DETECTED  # ran but corroborated nothing


# --- NEGATIVE: same-family self-check is refused --------------------------------------------------

def test_same_family_self_check_is_refused():
    """A verifier in the SAME family as the generator is single-model self-checking — refused
    loudly with ModelConflictError, never run."""
    same_family = ScriptedLLM("grok-2", AGREE_JSON)  # grok-2 is also the xAI family
    with pytest.raises(ModelConflictError):
        cross_model_drift_check(_kepler(), CLAIM,
                                generator_model=GENERATOR_MODEL, verifier=same_family)


# --- NEGATIVE: verifier tool error / timeout -> honest abstention, not a fake pass ----------------

def test_verifier_error_yields_honest_abstention_not_fake_verified():
    """When the verifier errors (timeout / unreachable), there is no independent second opinion,
    so the result MUST be an honest abstention — verified=False, drift=False."""
    report = cross_model_drift_check(_kepler(), CLAIM, generator_model=GENERATOR_MODEL,
                                     verifier=_ExplodingClient("claude-opus-4-8"))
    assert report.status == DRIFT_ABSTAINED
    assert report.verified is False
    assert report.drift is False
    assert "abstain" in report.detail.lower()


# --- PROPERTY: a verifier that never proposes the true law can NEVER produce a false 'verified' ----

@settings(max_examples=40, deadline=None)
@given(
    a_exp=st.floats(min_value=-3.0, max_value=3.0).filter(lambda x: abs(x - 1.5) > 0.05),
    mu_exp=st.floats(min_value=-3.0, max_value=3.0).filter(lambda x: abs(x + 0.5) > 0.05),
)
def test_wrong_law_verifier_never_falsely_verifies(a_exp: float, mu_exp: float):
    """Anti-hallucination invariant: for ANY verifier that proposes a law other than the true
    Kepler exponents, the cross-model check must never return verified=True. A wrong second
    opinion cannot manufacture corroboration."""
    payload = f'[{{"exponents": {{"a": {a_exp}, "mu": {mu_exp}}}, "rationale": "zufall"}}]'
    verifier = ScriptedLLM("claude-opus-4-8", payload)
    report = cross_model_drift_check(_kepler(), CLAIM,
                                     generator_model=GENERATOR_MODEL, verifier=verifier)
    assert report.verified is False
    assert report.status in (DRIFT_DETECTED, DRIFT_ABSTAINED)
