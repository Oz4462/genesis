"""Recall tuning: the skeptic uses model-driven verification queries (Item 1).

Proves the value directly: a claim whose VERBATIM text finds no independent source,
but whose model-reformulated query does, becomes VERIFIED — whereas verbatim-only
search would leave it UNSUPPORTED. Offline (ScriptedLLM). Core-only.
"""

from __future__ import annotations

import asyncio
import json

from gen.agents.skeptic import Skeptic
from gen.core.state import (
    Claim,
    ClaimStatus,
    Question,
    RunState,
    SourceCandidate,
    SourceRef,
)
from gen.ledger.store import InMemoryLedgerStore
from gen.llm.base import ScriptedLLM
from gen.tools.fetch import WebFetchTool

CLAIM = "the speed of light in vacuum is 299792458 meters per second"
REFORMULATED = "speed of light vacuum physical constant value"
SUPPORT_URL = "https://i.example/sol"


class _Backend:
    """Only returns an independent supporting source for the REFORMULATED query,
    never for the verbatim claim — so verbatim-only search finds nothing."""

    name = "scripted"

    async def search(self, query, limit):
        if query.strip() == REFORMULATED:
            return [SourceCandidate(url_or_id=SUPPORT_URL, title=None,
                                    backend=self.name, relevance_note="x")]
        return []


def _http():
    from gen.tools.http import HttpResponse

    async def _get(url):
        return HttpResponse(status=200, body="SUPPORT independent corroboration", final_url=url)

    return _get


def _verifier(system, user):
    # query-generation call -> return the reformulated query as a JSON array
    if "generate search queries" in system.lower():
        return json.dumps([REFORMULATED])
    # judging call -> support
    if "SUPPORT" in user:
        return json.dumps({"relation": "supports", "confidence": 0.85})
    return json.dumps({"relation": "irrelevant", "confidence": 0.0})


def _run(extra_judges=()):
    ledger = InMemoryLedgerStore()
    claim = Claim(id="k1", text=CLAIM,
                  sources=[SourceRef(url_or_id="scholar://x", retrieved=True)],
                  status=ClaimStatus.UNVERIFIED, model="claude-opus-4-8")
    asyncio.run(ledger.add_claims("r", [claim]))
    state = RunState(question=Question(raw="q", run_id="r"))
    state.claims = [claim]
    skeptic = Skeptic(
        [_Backend()],
        WebFetchTool(_http(), ledger=ledger, run_id="r"),
        ScriptedLLM("gpt-4o", _verifier),
        ledger,
        generator_model="claude-opus-4-8",
        min_sources_for_verified=1,  # one independent corroboration is enough here
        extra_judges=extra_judges,
    )
    asyncio.run(skeptic.run(state))
    return claim


def test_reformulated_query_finds_corroboration():
    claim = _run()
    assert claim.status is ClaimStatus.VERIFIED
    assert claim.verification and claim.verification[0].url_or_id == SUPPORT_URL
