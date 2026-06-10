"""Tests for `skeptic` — the verifier. No network, no real LLM (judgments mocked)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.agents.skeptic import Skeptic  # noqa: E402
from gen.core.errors import ModelConflictError, SearchBackendError  # noqa: E402
from gen.core.state import (  # noqa: E402
    Claim,
    ClaimStatus,
    Question,
    RunState,
    SourceCandidate,
    SourceRef,
    SourceSupport,
)
from gen.ledger.store import InMemoryLedgerStore  # noqa: E402
from gen.llm.base import ScriptedLLM  # noqa: E402
from gen.tools.fetch import WebFetchTool  # noqa: E402
from gen.tools.http import HttpResponse  # noqa: E402


def run(coro):
    return asyncio.run(coro)


class FakeBackend:
    def __init__(self, name, urls, fail=False):
        self.name = name
        self._urls = urls
        self._fail = fail

    async def search(self, query, limit):
        if self._fail:
            raise SearchBackendError(self.name, "boom")
        return [
            SourceCandidate(url_or_id=u, title=None, backend=self.name, relevance_note="r")
            for u in self._urls
        ][:limit]


def http_serving(content_by_url, status=200):
    async def _get(url):
        return HttpResponse(status=status, body=content_by_url.get(url, ""), final_url=url)
    return _get


def verifier_by_marker(model="gpt-4o"):
    """Verdict depends on a marker in the source content (passed in the user msg)."""
    def responder(system, user):
        if "CONTRADICT" in user:
            return json.dumps({"relation": "contradicts", "confidence": 0.9})
        if "SUPPORT" in user:
            return json.dumps({"relation": "supports", "confidence": 0.8})
        return json.dumps({"relation": "irrelevant", "confidence": 0.0})
    return ScriptedLLM(model, responder)


def _state_with_claim(ledger, *, model="claude-opus-4-8", scholar_url="https://scholar.src"):
    st = RunState(question=Question(raw="is X true?", run_id="r1"))
    c = Claim(
        id="c1",
        text="X is true",
        sources=[SourceRef(scholar_url, retrieved=True, support=SourceSupport.SUPPORTS)],
        status=ClaimStatus.UNVERIFIED,
        model=model,
        produced_by="scholar",
    )
    run(ledger.add_claims("r1", [c]))
    st.claims = [c]
    return st, c


def test_verified_with_two_independent_supports():
    ledger = InMemoryLedgerStore()
    st, c = _state_with_claim(ledger)
    backend = FakeBackend("b", ["https://i1", "https://i2"])
    fetch = WebFetchTool(http_serving({
        "https://i1": "SUPPORT: X is indeed true per study A.",
        "https://i2": "SUPPORT: independent confirmation of X.",
    }))
    sk = Skeptic([backend], fetch, verifier_by_marker(), ledger, min_sources_for_verified=2)
    run(sk.run(st))
    assert c.status is ClaimStatus.VERIFIED
    assert c.confidence == pytest.approx(0.96)  # corroborated(0.8, 0.8)
    assert {r.url_or_id for r in c.verification} == {"https://i1", "https://i2"}
    assert ledger.non_independent_verifications("r1") == []  # all independent


def test_refuted_when_source_contradicts():
    ledger = InMemoryLedgerStore()
    st, c = _state_with_claim(ledger)
    backend = FakeBackend("b", ["https://i1"])
    fetch = WebFetchTool(http_serving({"https://i1": "CONTRADICT: X is actually false."}))
    sk = Skeptic([backend], fetch, verifier_by_marker(), ledger)
    run(sk.run(st))
    assert c.status is ClaimStatus.REFUTED
    assert any(r.support is SourceSupport.CONTRADICTS for r in c.verification)


def test_unsupported_when_no_independent_source_found():
    """Only the scholar's own URL comes back -> excluded -> nothing to verify."""
    ledger = InMemoryLedgerStore()
    st, c = _state_with_claim(ledger, scholar_url="https://scholar.src")
    backend = FakeBackend("b", ["https://scholar.src"])  # same as scholar's source
    fetch = WebFetchTool(http_serving({"https://scholar.src": "SUPPORT: anything"}))
    sk = Skeptic([backend], fetch, verifier_by_marker(), ledger)
    run(sk.run(st))
    assert c.status is ClaimStatus.UNSUPPORTED
    assert c.confidence == 0.0
    assert c.verification == []


def test_unsupported_when_single_support_below_min():
    ledger = InMemoryLedgerStore()
    st, c = _state_with_claim(ledger)
    backend = FakeBackend("b", ["https://i1"])
    fetch = WebFetchTool(http_serving({"https://i1": "SUPPORT: one source only."}))
    sk = Skeptic([backend], fetch, verifier_by_marker(), ledger, min_sources_for_verified=2)
    run(sk.run(st))
    assert c.status is ClaimStatus.UNSUPPORTED  # not enough corroboration -> never VERIFIED


def test_independence_scholar_source_excluded():
    ledger = InMemoryLedgerStore()
    st, c = _state_with_claim(ledger, scholar_url="https://shared")
    backend = FakeBackend("b", ["https://shared", "https://new1", "https://new2"])
    fetch = WebFetchTool(http_serving({
        "https://shared": "SUPPORT: reused source (must be ignored)",
        "https://new1": "SUPPORT: independent 1",
        "https://new2": "SUPPORT: independent 2",
    }))
    sk = Skeptic([backend], fetch, verifier_by_marker(), ledger, min_sources_for_verified=2)
    run(sk.run(st))
    urls = {r.url_or_id for r in c.verification}
    assert "https://shared" not in urls  # scholar's source never counts
    assert urls == {"https://new1", "https://new2"}
    assert ledger.non_independent_verifications("r1") == []


def test_cross_model_violation_raises():
    """KEY: verifier on the SAME family as the generator is a config error."""
    ledger = InMemoryLedgerStore()
    st, c = _state_with_claim(ledger, model="claude-opus-4-8")
    backend = FakeBackend("b", ["https://i1"])
    fetch = WebFetchTool(http_serving({"https://i1": "SUPPORT"}))
    same_family = verifier_by_marker(model="claude-3-5-haiku")  # also 'claude'
    sk = Skeptic([backend], fetch, same_family, ledger)
    with pytest.raises(ModelConflictError):
        run(sk.run(st))


def test_cross_model_ok_with_different_families():
    ledger = InMemoryLedgerStore()
    st, c = _state_with_claim(ledger, model="claude-opus-4-8")
    backend = FakeBackend("b", ["https://i1", "https://i2"])
    fetch = WebFetchTool(http_serving({
        "https://i1": "SUPPORT a", "https://i2": "SUPPORT b",
    }))
    sk = Skeptic([backend], fetch, verifier_by_marker("gpt-4o"), ledger, min_sources_for_verified=2)
    run(sk.run(st))  # no raise
    assert c.status is ClaimStatus.VERIFIED


def test_failed_fetch_does_not_fabricate_support():
    ledger = InMemoryLedgerStore()
    st, c = _state_with_claim(ledger)
    backend = FakeBackend("b", ["https://dead"])
    fetch = WebFetchTool(http_serving({"https://dead": ""}, status=500))  # fetch not ok
    sk = Skeptic([backend], fetch, verifier_by_marker(), ledger)
    run(sk.run(st))
    assert c.status is ClaimStatus.UNSUPPORTED
    assert c.verification == []
    assert any("fetch not ok" in line for line in st.log)


def test_verifier_parse_error_is_treated_as_irrelevant():
    ledger = InMemoryLedgerStore()
    st, c = _state_with_claim(ledger)
    backend = FakeBackend("b", ["https://i1", "https://i2"])
    fetch = WebFetchTool(http_serving({"https://i1": "anything", "https://i2": "anything"}))
    broken = ScriptedLLM("gpt-4o", "definitely not json")
    sk = Skeptic([backend], fetch, broken, ledger)
    run(sk.run(st))
    assert c.status is ClaimStatus.UNSUPPORTED  # no fabricated support on parse failure
    assert c.verification == []


def test_status_update_is_persisted_to_ledger():
    ledger = InMemoryLedgerStore()
    st, c = _state_with_claim(ledger)
    backend = FakeBackend("b", ["https://i1", "https://i2"])
    fetch = WebFetchTool(http_serving({"https://i1": "SUPPORT", "https://i2": "SUPPORT"}))
    sk = Skeptic([backend], fetch, verifier_by_marker(), ledger, min_sources_for_verified=2)
    run(sk.run(st))
    [persisted] = run(ledger.get_claims("r1"))
    assert persisted.status is ClaimStatus.VERIFIED
    assert persisted.confidence == pytest.approx(0.96)


def test_second_judge_is_really_called_and_can_downgrade():
    """A genuine second opinion: if the second model finds the same sources
    irrelevant while the verifier supports, the disagreement forces abstention.
    (If the second judge were a relabel of the first, this would stay VERIFIED.)"""
    ledger = InMemoryLedgerStore()
    st, c = _state_with_claim(ledger, model="claude-opus-4-8")
    backend = FakeBackend("b", ["https://i1", "https://i2"])
    fetch = WebFetchTool(http_serving({"https://i1": "SUPPORT", "https://i2": "SUPPORT"}))
    verifier = verifier_by_marker("gpt-4o")                      # -> supports x2 -> VERIFIED
    second = ScriptedLLM(                                        # -> always irrelevant
        "llama3.1:70b",
        json.dumps({"relation": "irrelevant", "confidence": 0.0}),
    )
    sk = Skeptic([backend], fetch, verifier, ledger,
                 second_judge=second, min_sources_for_verified=2)
    run(sk.run(st))
    assert c.status is ClaimStatus.UNSUPPORTED   # second judge genuinely changed the outcome
    assert c.confidence == pytest.approx(0.0)


def test_second_judge_agreement_keeps_verified():
    ledger = InMemoryLedgerStore()
    st, c = _state_with_claim(ledger, model="claude-opus-4-8")
    backend = FakeBackend("b", ["https://i1", "https://i2"])
    fetch = WebFetchTool(http_serving({"https://i1": "SUPPORT", "https://i2": "SUPPORT"}))
    verifier = verifier_by_marker("gpt-4o")
    second = verifier_by_marker("llama3.1:70b")  # different family, also supports
    sk = Skeptic([backend], fetch, verifier, ledger,
                 second_judge=second, min_sources_for_verified=2)
    run(sk.run(st))
    assert c.status is ClaimStatus.VERIFIED       # both agree -> verified, corroborated
    assert c.confidence > 0.9


def test_second_judge_same_family_as_generator_raises():
    ledger = InMemoryLedgerStore()
    st, c = _state_with_claim(ledger, model="claude-opus-4-8")
    backend = FakeBackend("b", ["https://i1"])
    fetch = WebFetchTool(http_serving({"https://i1": "SUPPORT"}))
    verifier = verifier_by_marker("gpt-4o")
    bad_second = verifier_by_marker("claude-3-5-haiku")  # same family as generator
    sk = Skeptic([backend], fetch, verifier, ledger, second_judge=bad_second)
    with pytest.raises(ModelConflictError):
        run(sk.run(st))
