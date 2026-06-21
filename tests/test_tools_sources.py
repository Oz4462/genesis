"""Free-API discovery connectors behind the SearchBackend seam (tools/sources/{openalex,patents}.py).

Pins the interface-first integration: each connector turns a free, openly-licensed API into SourceCandidates
through the injected HttpGet — offline-fixture-deterministic, and live-probeable through the SAME seam. Each
candidate carries a REAL stable id (OpenAlex work id / Google-Patents URL); rows without an id are skipped,
never invented; a non-2xx is a loud SearchBackendError (honest BLOCKED), never a fabricated miss. The live
OpenAlex probe (CC0, no key) runs only under GENESIS_ALLOW_LIVE so the offline suite stays deterministic.
"""

import asyncio
import json
import os

import pytest

from gen.core.errors import SearchBackendError
from gen.core.interfaces import SearchBackend
from gen.core.state import SourceCandidate
from gen.tools.http import HttpResponse, default_http_get
from gen.tools.sources import OpenAlexBackend, PatentsViewBackend


def run(coro):
    return asyncio.run(coro)


def _fake(status: int, body: str):
    async def _get(url: str) -> HttpResponse:
        return HttpResponse(status=status, body=body, final_url=url)
    return _get


def _raising(exc: Exception):
    async def _get(url: str) -> HttpResponse:
        raise exc
    return _get


_OPENALEX_BODY = json.dumps({"meta": {"count": 2}, "results": [
    {"id": "https://openalex.org/W123", "title": "Sparse Identification of Nonlinear Dynamics",
     "doi": "https://doi.org/10.1/x", "publication_year": 2016, "cited_by_count": 4200},
    {"id": "https://openalex.org/W456", "title": "  Symbolic   Regression  ",
     "doi": None, "publication_year": 2009, "cited_by_count": None},
    {"id": "", "title": "no stable id"},
]})

_PATENTS_BODY = json.dumps({"error": False, "count": 2, "patents": [
    {"patent_id": "10000000", "patent_title": "Robotic actuator", "patent_date": "2018-06-19"},
    {"patent_id": "9999999", "patent_title": "Pendulum damper", "patent_date": "2015-01-01"},
    {"patent_id": "", "patent_title": "no id row"},
]})


def test_both_connectors_satisfy_the_searchbackend_protocol():
    assert isinstance(OpenAlexBackend(_fake(200, "{}")), SearchBackend)
    assert isinstance(PatentsViewBackend(_fake(200, "{}")), SearchBackend)


def test_openalex_parses_works_with_stable_ids_and_cc0_provenance():
    cands = run(OpenAlexBackend(_fake(200, _OPENALEX_BODY)).search("sindy", 5))
    assert all(isinstance(c, SourceCandidate) for c in cands)
    assert [c.url_or_id for c in cands] == ["https://openalex.org/W123", "https://openalex.org/W456"]
    assert cands[0].title == "Sparse Identification of Nonlinear Dynamics"
    assert cands[1].title == "Symbolic Regression"                 # whitespace normalized
    assert all(c.backend == "openalex" and not c.fetched_ok for c in cands)
    assert "CC0" in cands[0].relevance_note and "2016" in cands[0].relevance_note


def test_patentsview_parses_patents_into_resolvable_provenance():
    cands = run(PatentsViewBackend(_fake(200, _PATENTS_BODY)).search("robot actuator", 5))
    assert [c.url_or_id for c in cands] == [
        "https://patents.google.com/patent/US10000000", "https://patents.google.com/patent/US9999999"]
    assert cands[0].title == "Robotic actuator"
    assert all(c.backend == "patents" and not c.fetched_ok for c in cands)
    assert "public domain" in cands[0].relevance_note


def test_limit_is_respected():
    assert len(run(OpenAlexBackend(_fake(200, _OPENALEX_BODY)).search("x", 1))) == 1
    assert len(run(PatentsViewBackend(_fake(200, _PATENTS_BODY)).search("x", 1))) == 1


def test_non_2xx_raises_searchbackenderror_not_a_fake_miss():
    # e.g. PatentsView 403 without an X-Api-Key — an honest BLOCKED, never an empty "no results"
    with pytest.raises(SearchBackendError):
        run(PatentsViewBackend(_fake(403, "")).search("x", 5))
    with pytest.raises(SearchBackendError):
        run(OpenAlexBackend(_fake(500, "")).search("x", 5))


def test_transport_failure_and_bad_json_raise():
    with pytest.raises(SearchBackendError):
        run(OpenAlexBackend(_raising(ConnectionError("dns"))).search("x", 5))
    with pytest.raises(SearchBackendError):
        run(OpenAlexBackend(_fake(200, "not-json")).search("x", 5))


@pytest.mark.skipif(not os.environ.get("GENESIS_ALLOW_LIVE"),
                    reason="live OpenAlex probe gated behind GENESIS_ALLOW_LIVE (honest-skip)")
def test_openalex_live_probe_returns_real_candidates():
    cands = run(OpenAlexBackend(default_http_get, mailto="genesis@example.org").search("symbolic regression", 2))
    assert cands and all(c.url_or_id.startswith("https://openalex.org/") for c in cands)
