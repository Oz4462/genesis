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
from gen.tools.http import HttpResponse, default_http_get  # noqa: E402
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


# --- WebFetchTool: SSRF — a non-http(s) candidate URL is refused, not fetched --

def http_spy():
    """An http_get that records whether it was called (it must NOT be for a bad scheme)."""
    calls: list[str] = []

    async def _get(url: str) -> HttpResponse:
        calls.append(url)
        return HttpResponse(status=200, body="should never be reached", final_url=url)

    return _get, calls


@pytest.mark.parametrize(
    "bad_url",
    ["file:///etc/passwd", "ftp://internal/secret", "data:text/plain,hi", "gopher://x", "no-scheme"],
)
def test_fetch_rejects_non_http_scheme_without_touching_transport(bad_url):
    get, calls = http_spy()
    res = run(WebFetchTool(get)(url=bad_url))
    assert res.ok is False
    assert res.content is None
    assert "unsupported URL scheme" in res.reason
    assert calls == []  # the malicious URL never reached urllib's file:// handler
    assert res.to_source_ref().retrieved is False  # gate will flag DEAD_CITATION


@pytest.mark.parametrize("good_url", ["https://ok.example", "http://ok.example", "HTTPS://Caps.example"])
def test_fetch_allows_http_and_https(good_url):
    res = run(WebFetchTool(http_returning(200, "body"))(url=good_url))
    assert res.ok is True and res.content == "body"


# --- SemanticScholar / Wikipedia: malformed envelope is loud, honest-empty is [] --

def test_semantic_scholar_missing_data_array_raises():
    # a 200 without the documented 'data' array is an error envelope, not "no
    # results" — must fail loud, never a silent empty list that masks an outage.
    backend = SemanticScholarBackend(http_returning(200, json.dumps({"error": "rate limited"})))
    with pytest.raises(SearchBackendError):
        run(backend.search("q", limit=5))


def test_semantic_scholar_empty_data_is_honest_no_results():
    backend = SemanticScholarBackend(http_returning(200, json.dumps({"data": []})))
    assert run(backend.search("q", limit=5)) == []


# --- default_http_get: the production transport caps an untrusted response body --

class _FakeUrlopen:
    """Minimal urlopen stand-in: a context manager yielding a readable response."""

    def __init__(self, payload: bytes, status: int = 200):
        self._payload = payload
        self.status = status

    def read(self, n: int = -1) -> bytes:
        return self._payload if n is None or n < 0 else self._payload[:n]

    def geturl(self) -> str:
        return "https://huge.example"

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_dns(monkeypatch, *addrs: str) -> None:
    """Make DNS resolution deterministic and offline for transport tests."""
    import socket

    infos = [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (a, 80)) for a in addrs
    ]

    def _getaddrinfo(host, port, *args, **kwargs):
        return infos

    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo)


def _fake_transport(monkeypatch, payload: bytes) -> None:
    import gen.tools.http as http_mod

    monkeypatch.setattr(
        http_mod,
        "_guarded_urlopen",
        lambda req, *, timeout, allow_private_hosts=False: _FakeUrlopen(payload),
    )


def test_default_http_get_refuses_oversize_body(monkeypatch):
    # 11 bytes available, cap at 10 -> read(11) sees > cap -> raise (never truncate).
    _fake_dns(monkeypatch, "93.184.216.34")
    _fake_transport(monkeypatch, b"x" * 11)
    with pytest.raises(ValueError):
        run(default_http_get("https://huge.example", max_bytes=10))


def test_default_http_get_accepts_body_at_or_under_cap(monkeypatch):
    _fake_dns(monkeypatch, "93.184.216.34")
    _fake_transport(monkeypatch, b"hello")
    res = run(default_http_get("https://ok.example", max_bytes=1000))
    assert res.status == 200 and res.body == "hello"


# --- D8: SSRF depth — the production transport refuses non-public targets ------
# The fetch target is attacker-influenced (search results / SERP parsers); a
# compromised source must not be able to steer GENESIS into loopback, RFC1918,
# link-local (cloud metadata 169.254.169.254) or ULA ranges.


def test_default_http_get_blocks_url_resolving_to_private(monkeypatch):
    _fake_dns(monkeypatch, "10.0.0.5")
    _fake_transport(monkeypatch, b"must never be reached")
    with pytest.raises(ValueError, match="non-public"):
        run(default_http_get("https://internal.example/"))


def test_default_http_get_blocks_if_any_resolved_address_is_private(monkeypatch):
    # DNS rebinding-ish setups return a public decoy plus the real private target:
    # ALL addresses must be public, one bad address blocks the fetch.
    _fake_dns(monkeypatch, "93.184.216.34", "192.168.1.7")
    _fake_transport(monkeypatch, b"must never be reached")
    with pytest.raises(ValueError, match="non-public"):
        run(default_http_get("https://rebind.example/"))


@pytest.mark.parametrize(
    "bad_url",
    [
        "http://127.0.0.1/steal",
        "http://10.1.2.3/",
        "http://172.16.0.9/",
        "http://192.168.0.1/router",
        "http://169.254.169.254/latest/meta-data/",
        "http://0.0.0.0/",
        "http://[::1]/",
        "http://[fc00::1]/",
        "http://localhost/admin",
    ],
)
def test_default_http_get_blocks_ip_literals_without_dns(monkeypatch, bad_url):
    import socket

    def _no_dns(*args, **kwargs):  # literal guard must fire BEFORE any DNS lookup
        raise AssertionError("getaddrinfo must not be called for a blocked literal")

    monkeypatch.setattr(socket, "getaddrinfo", _no_dns)
    _fake_transport(monkeypatch, b"must never be reached")
    with pytest.raises(ValueError):
        run(default_http_get(bad_url))


def test_default_http_get_allow_private_hosts_is_an_explicit_operator_opt_in(monkeypatch):
    # The override exists for operator-configured local services only; the
    # research path never sets it.
    _fake_transport(monkeypatch, b"local ok")
    res = run(default_http_get("http://127.0.0.1:8080/health", allow_private_hosts=True))
    assert res.status == 200 and res.body == "local ok"


def test_redirect_handler_blocks_private_and_non_http_targets(monkeypatch):
    import urllib.request

    import gen.tools.http as http_mod

    handler = http_mod._redirect_handler(allow_private_hosts=False)
    req = urllib.request.Request("https://start.example/")
    with pytest.raises(ValueError, match="redirect"):
        handler.redirect_request(req, None, 302, "Found", {}, "http://169.254.169.254/creds")
    with pytest.raises(ValueError, match="redirect"):
        handler.redirect_request(req, None, 302, "Found", {}, "file:///etc/passwd")
    # a public redirect target passes through to the stdlib handler
    _fake_dns(monkeypatch, "93.184.216.34")
    new_req = handler.redirect_request(req, None, 302, "Found", {}, "https://public.example/")
    assert new_req is not None and new_req.full_url == "https://public.example/"


# --- D8: WebFetchTool refuses non-public literal hosts before ANY transport ----


@pytest.mark.parametrize(
    "bad_url",
    [
        "http://127.0.0.1/steal",
        "http://192.168.1.1/router",
        "http://169.254.169.254/latest/meta-data/",
        "http://0.0.0.0/",
        "http://[::1]/",
        "http://[fc00::1]/",
        "http://localhost/admin",
    ],
)
def test_fetch_blocks_non_public_host_literals(bad_url):
    get, calls = http_spy()
    res = run(WebFetchTool(get)(url=bad_url))
    assert res.ok is False
    assert res.content is None
    assert "non-public" in res.reason or "loopback" in res.reason
    assert calls == []  # blocked before the transport was touched
    assert res.to_source_ref().retrieved is False  # honest, ledger-visible failure


def test_fetch_block_is_recorded_in_ledger():
    ledger = InMemoryLedgerStore()
    get, _ = http_spy()
    tool = WebFetchTool(get, ledger=ledger, run_id="r1")
    run(tool(url="http://169.254.169.254/latest/meta-data/"))
    rec = run(ledger.get_fetch("r1", "http://169.254.169.254/latest/meta-data/"))
    assert rec is not None and rec.ok is False and rec.content_hash is None


def test_fetch_allows_public_ip_literal():
    res = run(WebFetchTool(http_returning(200, "body"))(url="http://93.184.216.34/"))
    assert res.ok is True and res.content == "body"


# --- D9: final_url provenance — the result carries the REAL retrieved URL ------


def http_redirecting_to(final_url: str, body: str = "redirected body"):
    async def _get(url: str) -> HttpResponse:
        return HttpResponse(status=200, body=body, final_url=final_url)

    return _get


def test_fetch_result_carries_final_url_after_redirect():
    ledger = InMemoryLedgerStore()
    tool = WebFetchTool(
        http_redirecting_to("https://final.example/doc"), ledger=ledger, run_id="r1"
    )
    res = run(tool(url="https://start.example/moved"))
    assert res.ok is True
    assert res.url == "https://final.example/doc"  # provenance = where content came from
    assert res.requested_url == "https://start.example/moved"  # audit trail keeps the ask
    assert res.to_source_ref().url_or_id == "https://final.example/doc"
    # the ledger records the fetch under the real final URL
    rec = run(ledger.get_fetch("r1", "https://final.example/doc"))
    assert rec is not None and rec.ok is True and rec.content_hash == res.content_hash


def test_fetch_without_redirect_has_no_requested_url_noise():
    res = run(WebFetchTool(http_returning(200, "body"))(url="https://ok.example"))
    assert res.ok is True
    assert res.url == "https://ok.example"
    assert res.requested_url is None


def test_fetch_redirect_to_private_final_url_is_blocked():
    # the injected transport followed a redirect into a private range: the tool
    # must still refuse the content (defence in depth for non-default transports).
    tool = WebFetchTool(http_redirecting_to("http://169.254.169.254/creds"))
    res = run(tool(url="https://start.example/moved"))
    assert res.ok is False
    assert res.content is None
    assert "169.254.169.254" in res.reason


def test_fetch_redirect_to_non_http_final_url_is_blocked():
    tool = WebFetchTool(http_redirecting_to("file:///etc/passwd"))
    res = run(tool(url="https://start.example/moved"))
    assert res.ok is False
    assert res.content is None
    assert "scheme" in res.reason
