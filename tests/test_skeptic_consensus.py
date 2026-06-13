"""Phase 3 live wiring: the skeptic uses N-judge consensus when extra judges are set.

Drives the REAL Skeptic with a 3-judge panel (verifier + second + one extra), all
different families from the generator. Supports -> consensus VERIFIED; one extra judge
contradicting -> REFUTED veto. Offline (ScriptedLLM). Core-only (no extras needed).
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

SUBJECT = "standard gravity is 9.80665 meters per second squared"
INDEP = {
    "https://i.example/g1": "SUPPORT independent corroboration one",
    "https://i.example/g2": "SUPPORT independent corroboration two",
}


class _Backend:
    name = "scripted"

    async def search(self, query, limit):
        if query.strip() == SUBJECT:
            return [SourceCandidate(url_or_id=u, title=None, backend=self.name, relevance_note="x")
                    for u in INDEP][:limit]
        return []


def _http():
    from gen.tools.http import HttpResponse

    async def _get(url):
        return HttpResponse(status=200, body=INDEP.get(url, ""), final_url=url)

    return _get


def _supports(system, user):
    return json.dumps({"relation": "supports", "confidence": 0.85})


def _contradicts(system, user):
    return json.dumps({"relation": "contradicts", "confidence": 0.85})


def _run_panel(extra_responder):
    ledger = InMemoryLedgerStore()
    claim = Claim(
        id="k1", text=SUBJECT,
        sources=[SourceRef(url_or_id="scholar://x", retrieved=True)],
        status=ClaimStatus.UNVERIFIED, model="claude-opus-4-8",
    )
    asyncio.run(ledger.add_claims("r", [claim]))
    state = RunState(question=Question(raw="q", run_id="r"))
    state.claims = [claim]

    skeptic = Skeptic(
        [_Backend()],
        WebFetchTool(_http(), ledger=ledger, run_id="r"),
        ScriptedLLM("gpt-4o", _supports),               # verifier (openai)
        ledger,
        generator_model="claude-opus-4-8",              # generator (claude)
        second_judge=ScriptedLLM("gemini-1.5-pro", _supports),   # second (google)
        extra_judges=[ScriptedLLM("llama3:8b", extra_responder)],  # extra (llama)
    )
    asyncio.run(skeptic.run(state))
    return claim


def test_consensus_verified_when_panel_supports():
    claim = _run_panel(_supports)
    assert claim.status is ClaimStatus.VERIFIED
    assert claim.confidence > 0.7


def test_consensus_refuted_when_one_judge_contradicts():
    claim = _run_panel(_contradicts)
    assert claim.status is ClaimStatus.REFUTED
