"""Tests for the Wikipedia search backend — no real network (HttpGet faked).

Wikipedia is GENESIS's keyless, non-rate-limited discovery workhorse (the free
Semantic Scholar API 429s without a key). Like every backend it does DISCOVERY
only: it returns candidate URLs (the REST *summary* endpoint, whose body is clean
prose the scholar can quote-check verbatim) and never asserts a fact. A transport
failure raises ``SearchBackendError`` — loud, never a silent empty list that would
hide an outage.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.errors import SearchBackendError  # noqa: E402
from gen.core.interfaces import SearchBackend  # noqa: E402
from gen.tools.http import HttpResponse  # noqa: E402
from gen.tools.search import WikipediaBackend, to_keywords  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def http_returning(status: int, body: str, calls: list | None = None):
    async def _get(url: str) -> HttpResponse:
        if calls is not None:
            calls.append(url)
        return HttpResponse(status=status, body=body, final_url=url)

    return _get


def search_body(*titles: str) -> str:
    return json.dumps(
        {"query": {"search": [{"title": t, "pageid": i} for i, t in enumerate(titles, 1)]}}
    )


# --- tracer bullet: real result shape -> candidates ---------------------------

def test_search_maps_titles_to_summary_url_candidates():
    calls: list = []
    be = WikipediaBackend(http_returning(200, search_body("Solid modeling", "FreeCAD"), calls))
    cands = run(be.search("CAD kernel", 5))
    assert [c.title for c in cands] == ["Solid modeling", "FreeCAD"]
    # Candidate URL is the REST summary endpoint (clean prose for quote-checking),
    # title path-encoded (space -> underscore, then percent-encoding).
    assert cands[0].url_or_id == (
        "https://en.wikipedia.org/api/rest_v1/page/summary/Solid_modeling"
    )
    assert all(c.backend == "wikipedia" for c in cands)
    assert all(c.fetched_ok is False for c in cands)  # discovery only
    # the search query was sent to the MediaWiki API endpoint
    assert calls and "list=search" in calls[0]


def test_satisfies_search_backend_protocol():
    be = WikipediaBackend(http_returning(200, search_body("X")))
    assert isinstance(be, SearchBackend)


# --- failure modes are loud; missing data is never invented -------------------

def http_raising(exc: Exception):
    async def _get(url: str) -> HttpResponse:
        raise exc

    return _get


def test_http_error_raises_search_backend_error():
    be = WikipediaBackend(http_returning(503, "service down"))
    with pytest.raises(SearchBackendError):
        run(be.search("q", 5))


def test_transport_exception_raises_search_backend_error():
    be = WikipediaBackend(http_raising(ConnectionError("dns boom")))
    with pytest.raises(SearchBackendError) as exc_info:
        run(be.search("q", 5))
    assert "dns boom" in str(exc_info.value)


def test_bad_json_raises_search_backend_error():
    be = WikipediaBackend(http_returning(200, "<html>not json</html>"))
    with pytest.raises(SearchBackendError):
        run(be.search("q", 5))


def test_no_results_yields_empty_list_not_fabrication():
    be = WikipediaBackend(http_returning(200, json.dumps({"query": {"search": []}})))
    assert run(be.search("nonexistent topic xyzzy", 5)) == []


def test_result_without_title_is_skipped_never_invented():
    body = json.dumps({"query": {"search": [{"pageid": 1}, {"title": "Real"}]}})
    be = WikipediaBackend(http_returning(200, body))
    cands = run(be.search("q", 5))
    assert [c.title for c in cands] == ["Real"]  # the title-less hit is dropped


def test_special_characters_in_title_are_path_encoded():
    be = WikipediaBackend(http_returning(200, search_body("C++ (programming language)")))
    (cand,) = run(be.search("q", 5))
    # space -> underscore, then '+', '(', ')' percent-encoded -> a safe, real URL
    assert cand.url_or_id == (
        "https://en.wikipedia.org/api/rest_v1/page/summary/"
        "C%2B%2B_%28programming_language%29"
    )


# --- query normalization: Wikipedia full-text search wants keywords, not questions

def test_to_keywords_strips_question_framing_and_punctuation():
    # Wikipedia search matches a question poorly (stop words + '?' pollute it);
    # the content keywords are what surface the right article.
    assert to_keywords("What is a geometric modeling kernel?") == "geometric modeling kernel"
    assert to_keywords("How does the Open Cascade Technology work?") == "Open Cascade Technology work"
    assert to_keywords("geometric modeling kernel") == "geometric modeling kernel"  # already keywords
    assert to_keywords("What are the main features of OCCT?") == "main features of OCCT"


def test_search_sends_normalized_keywords_not_the_raw_question():
    calls: list = []
    be = WikipediaBackend(http_returning(200, search_body("Geometric modeling kernel"), calls))
    run(be.search("What is a geometric modeling kernel?", 5))
    # the keyword form (URL-encoded) is what hit the API, not the raw question
    assert "srsearch=geometric+modeling+kernel" in calls[0]
    assert "What" not in calls[0] and "%3F" not in calls[0]  # no question word, no '?'
