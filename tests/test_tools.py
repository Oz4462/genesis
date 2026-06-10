"""Tests for tool adapters — no real network (HttpGet is faked).

Covers Aufgabe 3 of CLAUDE_CODE_AUFTRAG_001, with the failure path tested
explicitly per the requirement: a fetch that fails must NEVER become a usable
source, and every attempt is recorded in the ledger.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.errors import FetchFailedError, SearchBackendError  # noqa: E402
from gen.ledger.store import InMemoryLedgerStore  # noqa: E402
from gen.tools.http import HttpResponse  # noqa: E402
from gen.tools.fetch import WebFetchTool, require_ok  # noqa: E402
from gen.tools.search import SemanticScholarBackend, WebSearchBackend  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def http_returning(status: int, body: str):
    async def _get(url: str) -> HttpResponse:
        return HttpResponse(status=status, body=body, final_url=url)
    return _get


def http_raising(exc: Exception):
    async def _get(url: str) -> HttpResponse:
        raise exc
    return _get


# --- WebFetchTool: success ----------------------------------------------------

def test_fetch_success_sets_ok_content_and_hash():
    tool = WebFetchTool(http_returning(200, "hello world"))
    res = run(tool(url="https://ok.example"))
    assert res.ok is True
    assert res.content == "hello world"
    assert res.content_hash and len(res.content_hash) == 64  # sha256 hex
    ref = res.to_source_ref()
    assert ref.retrieved is True
    assert ref.content_hash == res.content_hash


# --- WebFetchTool: every failure mode -> ok False, never content -------------

def test_fetch_non_2xx_is_not_ok():
    tool = WebFetchTool(http_returning(404, "nope"))
    res = run(tool(url="https://missing.example"))
    assert res.ok is False
    assert res.content is None
    assert "404" in res.reason
    assert res.to_source_ref().retrieved is False  # gate will flag DEAD_CITATION


def test_fetch_empty_body_is_not_ok():
    tool = WebFetchTool(http_returning(200, "   \n  "))
    res = run(tool(url="https://blank.example"))
    assert res.ok is False
    assert res.content is None
    assert res.reason == "empty body"


def test_fetch_transport_exception_is_not_ok():
    tool = WebFetchTool(http_raising(ConnectionError("dns boom")))
    res = run(tool(url="https://down.example"))
    assert res.ok is False
    assert res.content is None
    assert "dns boom" in res.reason  # honest failure, no fabricated success


# --- WebFetchTool: ledger recording of attempts ------------------------------

def test_fetch_records_success_and_failure_in_ledger():
    ledger = InMemoryLedgerStore()
    ok_tool = WebFetchTool(http_returning(200, "data"), ledger=ledger, run_id="r1")
    bad_tool = WebFetchTool(http_returning(500, ""), ledger=ledger, run_id="r1")
    run(ok_tool(url="https://ok.example"))
    run(bad_tool(url="https://err.example"))
    ok_rec = run(ledger.get_fetch("r1", "https://ok.example"))
    bad_rec = run(ledger.get_fetch("r1", "https://err.example"))
    assert ok_rec.ok is True and ok_rec.content_hash
    assert bad_rec.ok is False and bad_rec.content_hash is None


# --- require_ok ---------------------------------------------------------------

def test_require_ok_returns_content_or_raises():
    tool = WebFetchTool(http_returning(200, "payload"))
    good = run(tool(url="https://ok.example"))
    assert require_ok(good) == "payload"

    bad_tool = WebFetchTool(http_returning(403, ""))
    bad = run(bad_tool(url="https://forbidden.example"))
    with pytest.raises(FetchFailedError):
        require_ok(bad)


# --- SemanticScholarBackend ---------------------------------------------------

_SS_BODY = json.dumps({
    "data": [
        {"title": "DOI paper", "externalIds": {"DOI": "10.1/abc"}, "year": 2021,
         "abstract": "An abstract about kernels."},
        {"title": "arXiv paper", "externalIds": {"ArXiv": "2101.00001"}, "year": 2020},
        {"title": "URL only", "url": "https://example.org/p", "externalIds": {}},
        {"title": "No id at all", "externalIds": {}},  # must be skipped
    ]
})


def test_semantic_scholar_maps_and_prefers_stable_ids():
    backend = SemanticScholarBackend(http_returning(200, _SS_BODY))
    cands = run(backend.search("cad kernel", limit=10))
    ids = [c.url_or_id for c in cands]
    assert ids == [
        "https://doi.org/10.1/abc",
        "https://arxiv.org/abs/2101.00001",
        "https://example.org/p",
    ]  # the id-less paper was skipped, not invented
    assert all(c.backend == "semantic_scholar" for c in cands)
    assert all(c.fetched_ok is False for c in cands)  # discovery != retrieval
    assert "year 2021" in cands[0].relevance_note


def test_semantic_scholar_http_error_raises():
    backend = SemanticScholarBackend(http_returning(503, "down"))
    with pytest.raises(SearchBackendError):
        run(backend.search("q", limit=5))


def test_semantic_scholar_bad_json_raises():
    backend = SemanticScholarBackend(http_returning(200, "not json"))
    with pytest.raises(SearchBackendError):
        run(backend.search("q", limit=5))


def test_semantic_scholar_transport_error_raises():
    backend = SemanticScholarBackend(http_raising(TimeoutError("slow")))
    with pytest.raises(SearchBackendError):
        run(backend.search("q", limit=5))


# --- WebSearchBackend (generic) ----------------------------------------------

def _parse_demo(data) -> list[tuple[str, str | None, str]]:
    return [(h["link"], h.get("title"), h.get("snippet", "")) for h in data["results"]]


def test_web_search_backend_parses_injected_provider():
    body = json.dumps({"results": [
        {"link": "https://a.example", "title": "A", "snippet": "first"},
        {"link": "https://b.example", "title": "B", "snippet": "second"},
    ]})
    backend = WebSearchBackend(
        http_returning(200, body),
        endpoint_template="https://serp.example/s?q={query}&n={limit}",
        parse=_parse_demo,
        name="web",
    )
    cands = run(backend.search("hello world", limit=10))
    assert [c.url_or_id for c in cands] == ["https://a.example", "https://b.example"]
    assert cands[0].backend == "web"


def test_web_search_backend_http_error_raises():
    backend = WebSearchBackend(
        http_returning(500, ""),
        endpoint_template="https://serp.example/s?q={query}&n={limit}",
        parse=_parse_demo,
    )
    with pytest.raises(SearchBackendError):
        run(backend.search("q", limit=5))
