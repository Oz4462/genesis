"""Tests for `scholar` — quote-checked fact extraction. No network, no real LLM."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.agents.scholar import Scholar, claim_id  # noqa: E402
from gen.core.state import (  # noqa: E402
    ClaimStatus,
    Question,
    RunState,
    SourceCandidate,
)
from gen.ledger.store import InMemoryLedgerStore  # noqa: E402
from gen.llm.base import ScriptedLLM  # noqa: E402
from gen.tools.fetch import WebFetchTool  # noqa: E402
from gen.tools.http import HttpResponse  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def http_serving(content_by_url: dict[str, str], *, status=200):
    async def _get(url: str) -> HttpResponse:
        return HttpResponse(status=status, body=content_by_url.get(url, ""), final_url=url)
    return _get


def http_failing():
    async def _get(url: str) -> HttpResponse:
        raise ConnectionError("down")
    return _get


def _state(urls):
    st = RunState(question=Question(raw="What kernel does build123d use?", run_id="r1"))
    st.candidates = [
        SourceCandidate(url_or_id=u, title=None, backend="b", relevance_note="r") for u in urls
    ]
    return st


def test_extracts_claim_with_real_quote():
    url = "https://docs.example/build123d"
    content = "build123d is built on the Open Cascade (OCCT) kernel for B-rep geometry."
    fetch = WebFetchTool(http_serving({url: content}))
    llm = ScriptedLLM(
        "claude-opus-4-8",
        json.dumps([{"text": "build123d uses the Open Cascade kernel.",
                     "quote": "built on the Open Cascade"}]),
    )
    ledger = InMemoryLedgerStore()
    st = run(Scholar(fetch, llm, ledger).run(_state([url])))

    assert len(st.claims) == 1
    c = st.claims[0]
    assert c.status is ClaimStatus.UNVERIFIED
    assert c.sources[0].url_or_id == url
    assert c.sources[0].retrieved is True
    assert c.model == "claude-opus-4-8"
    # persisted with provenance
    assert run(ledger.get_claims("r1"))[0].id == c.id


def test_drops_claim_with_hallucinated_quote():
    url = "https://docs.example/page"
    content = "This page is about apples and oranges. Nothing about kernels."
    fetch = WebFetchTool(http_serving({url: content}))
    llm = ScriptedLLM(
        "claude-opus-4-8",
        json.dumps([{"text": "build123d uses the Open Cascade kernel.",
                     "quote": "built on the Open Cascade kernel"}]),  # NOT in content
    )
    st = run(Scholar(fetch, llm, InMemoryLedgerStore()).run(_state([url])))
    assert st.claims == []  # hallucinated quote -> no claim
    assert any("hallucinated quote" in line for line in st.log)


def test_no_claim_from_failed_fetch():
    url = "https://down.example"
    fetch = WebFetchTool(http_failing())
    llm = ScriptedLLM("claude-opus-4-8", json.dumps([{"text": "x", "quote": "x"}]))
    st = run(Scholar(fetch, llm, InMemoryLedgerStore()).run(_state([url])))
    assert st.claims == []
    assert any("fetch not ok" in line for line in st.log)


def test_unparseable_llm_output_yields_no_claim_no_crash():
    url = "https://docs.example/x"
    fetch = WebFetchTool(http_serving({url: "some real content here"}))
    llm = ScriptedLLM("claude-opus-4-8", "I cannot return JSON today, sorry.")
    st = run(Scholar(fetch, llm, InMemoryLedgerStore()).run(_state([url])))
    assert st.claims == []
    assert any("unparseable LLM" in line for line in st.log)


def test_too_short_quote_is_rejected():
    url = "https://docs.example/x"
    content = "aaa bbb ccc relevant content"
    fetch = WebFetchTool(http_serving({url: content}))
    llm = ScriptedLLM("claude-opus-4-8", json.dumps([{"text": "claim", "quote": "aa"}]))
    st = run(Scholar(fetch, llm, InMemoryLedgerStore(), min_quote_len=4).run(_state([url])))
    assert st.claims == []


def test_rerun_does_not_duplicate_claims():
    url = "https://docs.example/build123d"
    content = "build123d is built on the Open Cascade kernel."
    fetch = WebFetchTool(http_serving({url: content}))
    llm = ScriptedLLM(
        "claude-opus-4-8",
        json.dumps([{"text": "build123d uses the Open Cascade kernel.",
                     "quote": "built on the Open Cascade kernel"}]),
    )
    ledger = InMemoryLedgerStore()
    scholar = Scholar(fetch, llm, ledger)
    st = _state([url])
    run(scholar.run(st))
    run(scholar.run(st))  # second pass: same id -> skipped
    assert len(st.claims) == 1
    assert len(run(ledger.get_claims("r1"))) == 1
