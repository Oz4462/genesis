"""Search backends — source DISCOVERY only (PHASE_ALPHA §3.2 / Aufgabe 3).

A SearchBackend returns ``SourceCandidate``s: "this might be relevant, and here
is why". It never asserts facts and never marks a candidate as fetched — the
candidate's ``fetched_ok`` stays False until ``scholar`` actually retrieves it
with the WebFetchTool. That separation is deliberate: discovery is cheap and
fallible; only a real fetch earns the right to back a claim.

Two adapters:
  * ``SemanticScholarBackend`` — concrete, free, no API key (academic source).
  * ``WebSearchBackend``       — generic JSON-SERP adapter; the concrete provider
    (endpoint + response shape) is injected, so the choice stays swappable
    (CLAUDE.md §6, PHASE_ALPHA §9).

All transport goes through an injected ``HttpGet`` so tests run without a network.
On transport failure a backend raises ``SearchBackendError`` (loud, not a silent
empty list).
"""

from __future__ import annotations

import json
from typing import Callable, Mapping
from urllib.parse import quote, quote_plus

from ..core.errors import SearchBackendError
from ..core.state import SourceCandidate
from .http import HttpGet


def _truncate(text: str, n: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


class SemanticScholarBackend:
    """Academic search via the free Semantic Scholar Graph API.

    Endpoint: ``/graph/v1/paper/search``. No key required for modest use. Maps
    each paper to a SourceCandidate, preferring a DOI/arXiv URL as the stable id.
    The ``relevance_note`` is built only from fields the API actually returned
    (year + abstract snippet) — never invented.
    """

    name = "semantic_scholar"
    _BASE = "https://api.semanticscholar.org/graph/v1/paper/search"
    _FIELDS = "title,url,abstract,year,externalIds"

    def __init__(self, http_get: HttpGet) -> None:
        self._http_get = http_get

    async def search(self, query: str, limit: int) -> list[SourceCandidate]:
        url = f"{self._BASE}?query={quote_plus(query)}&limit={limit}&fields={self._FIELDS}"
        try:
            resp = await self._http_get(url)
        except Exception as exc:  # noqa: BLE001
            raise SearchBackendError(self.name, str(exc)) from exc
        if not (200 <= resp.status < 300):
            raise SearchBackendError(self.name, f"HTTP {resp.status}")
        try:
            data = json.loads(resp.body)
        except json.JSONDecodeError as exc:
            raise SearchBackendError(self.name, f"bad JSON: {exc}") from exc

        out: list[SourceCandidate] = []
        for paper in (data.get("data") or [])[:limit]:
            url_or_id = _best_paper_id(paper)
            if not url_or_id:
                continue  # no stable identifier -> skip, do not invent one
            year = paper.get("year")
            abstract = paper.get("abstract") or ""
            note_bits = []
            if year:
                note_bits.append(f"year {year}")
            if abstract:
                note_bits.append(_truncate(abstract))
            note = "Semantic Scholar: " + ("; ".join(note_bits) if note_bits else "match")
            out.append(
                SourceCandidate(
                    url_or_id=url_or_id,
                    title=paper.get("title"),
                    backend=self.name,
                    relevance_note=note,
                    fetched_ok=False,
                )
            )
        return out


class WikipediaBackend:
    """Keyless discovery via the MediaWiki search API.

    The free Semantic Scholar API rate-limits (HTTP 429) without a key; Wikipedia's
    API needs none and is reliable, so it is GENESIS's default discovery workhorse.

    A candidate's ``url_or_id`` points at the REST *summary* endpoint, whose body
    is clean, fact-dense prose — exactly what the scholar's verbatim quote guard
    needs to actually match (a raw article URL fetches noisy HTML instead). Like
    every backend this does DISCOVERY only: it returns candidates, never facts, and
    raises ``SearchBackendError`` on transport failure rather than a silent empty
    list.
    """

    name = "wikipedia"
    _SEARCH = "https://en.wikipedia.org/w/api.php"
    _SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/"

    def __init__(self, http_get: HttpGet, *, lang: str = "en") -> None:
        self._http_get = http_get
        if lang != "en":  # keep the default endpoints unless a caller overrides lang
            self._SEARCH = f"https://{lang}.wikipedia.org/w/api.php"
            self._SUMMARY = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/"

    async def search(self, query: str, limit: int) -> list[SourceCandidate]:
        url = (
            f"{self._SEARCH}?action=query&list=search&format=json"
            f"&srsearch={quote_plus(query)}&srlimit={limit}"
        )
        try:
            resp = await self._http_get(url)
        except Exception as exc:  # noqa: BLE001
            raise SearchBackendError(self.name, str(exc)) from exc
        if not (200 <= resp.status < 300):
            raise SearchBackendError(self.name, f"HTTP {resp.status}")
        try:
            data = json.loads(resp.body)
        except json.JSONDecodeError as exc:
            raise SearchBackendError(self.name, f"bad JSON: {exc}") from exc

        results = (((data.get("query") or {}).get("search")) or [])[:limit]
        out: list[SourceCandidate] = []
        for hit in results:
            title = hit.get("title")
            if not title:
                continue  # no title -> no stable summary URL; skip, never invent
            path = quote(title.replace(" ", "_"), safe="")
            out.append(
                SourceCandidate(
                    url_or_id=self._SUMMARY + path,
                    title=title,
                    backend=self.name,
                    relevance_note=f"Wikipedia: search match for {query!r}",
                    fetched_ok=False,
                )
            )
        return out


def _best_paper_id(paper: Mapping) -> str | None:
    ext = paper.get("externalIds") or {}
    if ext.get("DOI"):
        return f"https://doi.org/{ext['DOI']}"
    if ext.get("ArXiv"):
        return f"https://arxiv.org/abs/{ext['ArXiv']}"
    if paper.get("url"):
        return paper["url"]
    if paper.get("paperId"):
        return f"https://www.semanticscholar.org/paper/{paper['paperId']}"
    return None


# A parser turns a provider's raw JSON into (url, title, note) triples.
SerpParser = Callable[[object], list[tuple[str, str | None, str]]]


class WebSearchBackend:
    """Generic web-search adapter over a JSON SERP endpoint.

    The concrete provider is injected as:
      * ``endpoint_template`` — a URL with ``{query}`` and ``{limit}`` placeholders;
      * ``parse`` — maps the decoded JSON to ``(url, title, note)`` triples.

    This keeps GENESIS provider-agnostic: Brave, SerpAPI, Bing, etc. differ only
    in template + parser, both supplied at the edge.
    """

    def __init__(
        self,
        http_get: HttpGet,
        *,
        endpoint_template: str,
        parse: SerpParser,
        name: str = "web",
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self._http_get = http_get
        self._endpoint_template = endpoint_template
        self._parse = parse
        self.name = name
        self._headers = headers  # reserved for adapters that pass auth via http_get

    async def search(self, query: str, limit: int) -> list[SourceCandidate]:
        url = self._endpoint_template.format(query=quote_plus(query), limit=limit)
        try:
            resp = await self._http_get(url)
        except Exception as exc:  # noqa: BLE001
            raise SearchBackendError(self.name, str(exc)) from exc
        if not (200 <= resp.status < 300):
            raise SearchBackendError(self.name, f"HTTP {resp.status}")
        try:
            data = json.loads(resp.body)
        except json.JSONDecodeError as exc:
            raise SearchBackendError(self.name, f"bad JSON: {exc}") from exc

        hits = self._parse(data)
        return [
            SourceCandidate(
                url_or_id=url_,
                title=title,
                backend=self.name,
                relevance_note=note,
                fetched_ok=False,
            )
            for (url_, title, note) in hits[:limit]
            if url_
        ]
