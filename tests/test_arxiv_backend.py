"""Tests for the arXiv discovery backend (Tier-3).

Offline: a scripted HttpGet returns a minimal arXiv Atom feed. Asserts candidates are
discovery-only (stable /abs/ ids, titles, evidence-grounded notes, unfetched) and that
transport/parse failures raise SearchBackendError (loud, never a silent empty list).
"""

from __future__ import annotations

import asyncio

import pytest

from gen.core.errors import SearchBackendError
from gen.tools.arxiv_backend import ArxivBackend
from gen.tools.http import HttpResponse

_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <title>A Study of Conformal Prediction</title>
    <summary>We present a finite-sample method for distribution-free uncertainty.</summary>
    <published>2024-01-02T00:00:00Z</published>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2402.12345v2</id>
    <title>Drift Detection in Streams</title>
    <summary>A streaming meta-test with per-window false-alarm control.</summary>
    <published>2024-02-15T00:00:00Z</published>
  </entry>
</feed>"""


def _http(status=200, body=_FEED):
    async def _get(url):
        return HttpResponse(status=status, body=body, final_url=url)
    return _get


def test_parses_entries_to_candidates():
    be = ArxivBackend(_http())
    cands = asyncio.run(be.search("conformal prediction uncertainty", limit=5))
    assert [c.url_or_id for c in cands] == [
        "https://arxiv.org/abs/2401.00001v1",
        "https://arxiv.org/abs/2402.12345v2",
    ]
    assert cands[0].title == "A Study of Conformal Prediction"
    assert cands[0].backend == "arxiv"
    assert "published 2024-01-02" in cands[0].relevance_note
    assert all(c.fetched_ok is False for c in cands)  # discovery only


def test_limit_truncates():
    be = ArxivBackend(_http())
    assert len(asyncio.run(be.search("x", limit=1))) == 1


def test_http_error_raises():
    be = ArxivBackend(_http(status=503))
    with pytest.raises(SearchBackendError):
        asyncio.run(be.search("x", limit=5))


def test_bad_xml_raises():
    be = ArxivBackend(_http(body="<not-xml"))
    with pytest.raises(SearchBackendError):
        asyncio.run(be.search("x", limit=5))
