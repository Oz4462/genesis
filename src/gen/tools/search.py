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
import re
from typing import Callable, Mapping
from urllib.parse import quote, quote_plus

from ..core.errors import SearchBackendError
from ..core.state import SourceCandidate
from .http import HttpGet


def _truncate(text: str, n: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


# Leading interrogative framing that hurts keyword search ("What is ...", "How
# does the ...", "Which of ..."). Stripped so the content keywords surface the
# right article. Kept deliberately small: only the unambiguous lead-in, never
# mid-sentence words (which could be meaningful).
_QUESTION_LEAD = re.compile(
    r"^\s*(what|which|who|whom|whose|how|why|when|where)\b"
    r"(\s+(is|are|was|were|do|does|did|can|could|should|would|will))?"
    r"(\s+(a|an|the))?\s+",
    re.IGNORECASE,
)

# Unit / dimension tokens that drown Wikipedia ranking ("density of steel in kg/m3"
# ranks generic Density pages; "density of steel" ranks Steel). Pure units only —
# never strip content words that share letters with units in longer tokens.
_UNIT_TOKEN = re.compile(
    r"(?i)^(kg(?:\/?(?:m(?:³|3)?))?|g(?:\/?(?:cm(?:³|3)?))?|"
    r"mpa|gpa|kpa|pa|n(?:·?m)?|kn|hz|khz|mhz|"
    r"mm|cm|km|m(?:²|2|³|3)?|s|ms|µs|us|kwh|wh|j|w|v|a|"
    r"lb|ft|in|oz|psi|°?c|°?f)$"
)


def to_keywords(query: str) -> str:
    """Reduce a natural-language question to keyword form for full-text search.

    Wikipedia's search matches keywords, not questions: a leading "What is ..."
    and a trailing "?" pollute the ranking and surface tangential articles. This
    strips that framing, question punctuation, and pure unit tokens (``kg/m3``,
    ``MPa``, …) while preserving content words (and their case, so proper nouns
    like "Open Cascade Technology" stay intact). Already-keyword queries pass
    through largely unchanged. If stripping would empty the query, the original
    is kept (never search for nothing).

    Live diagnosis 2026-07-13: ``What is the density of steel in kg/m3?`` →
    ``density of steel in kg/m3`` ranked generic Density pages; after unit strip
    → ``density of steel`` ranks Steel first (which states 7750–8050 kg/m³).
    """
    cleaned = query.replace("?", " ").replace("(", " ").replace(")", " ")
    # Split compound units so ``kg/m3`` becomes two tokens both matched by _UNIT_TOKEN.
    cleaned = cleaned.replace("/", " ")
    stripped = _QUESTION_LEAD.sub("", cleaned, count=1)
    tokens = [t for t in stripped.split() if t and not _UNIT_TOKEN.match(t)]
    result = " ".join(tokens)
    return result or " ".join(query.split())

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

        papers = data.get("data")
        if papers is None or not isinstance(papers, list):
            # A 200 without the documented 'data' array is a malformed/error
            # envelope, NOT an honest "no results" — fail loud rather than return
            # a silent empty list that would mask an API outage as "nothing found"
            # (the module contract: discovery raises, never silently empties).
            raise SearchBackendError(self.name, "malformed response: missing 'data' array")
        out: list[SourceCandidate] = []
        for paper in papers[:limit]:
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
    """Keyless discovery via the MediaWiki search API + full plain-text extracts.

    The free Semantic Scholar API rate-limits (HTTP 429) without a key; Wikipedia's
    API needs none and is reliable, so it is GENESIS's default discovery workhorse.

    A candidate's ``url_or_id`` points at ``action=query&prop=extracts&explaintext``
    (full article plain text), not the short REST *summary* endpoint. Live diagnosis
    2026-07-13: REST summaries for Steel omit the density band (7750–8050 kg/m³), so
    scholar could extract nothing; the full extract includes it for quote-checking.
    Like every backend this does DISCOVERY only: candidates, never facts; transport
    failure raises ``SearchBackendError`` rather than a silent empty list.
    """

    name = "wikipedia"
    _SEARCH = "https://en.wikipedia.org/w/api.php"

    def __init__(self, http_get: HttpGet, *, lang: str = "en") -> None:
        self._http_get = http_get
        if lang != "en":  # keep the default endpoints unless a caller overrides lang
            self._SEARCH = f"https://{lang}.wikipedia.org/w/api.php"

    def _extract_url(self, title: str) -> str:
        """MediaWiki plain-text extract URL for a page title (full article prose)."""
        return (
            f"{self._SEARCH}?action=query&prop=extracts&explaintext=1"
            f"&format=json&redirects=1&titles={quote(title, safe='')}"
        )

    @staticmethod
    def _prefer_canonical_titles(keywords: str, titles: list[str]) -> list[str]:
        """Re-order MediaWiki hits so base material pages beat alloys / generics.

        Live self-improve 2026-07-13: ``density of steel`` still surfaced
        Stainless/Electrical steel and generic Density before **Steel**, so α
        verified a stainless band instead of the carbon-steel 7750–8050 kg/m³
        fact. When the query names a base material without an alloy qualifier,
        exact/base titles rank first; alloy variants and pure property pages last.
        """
        if not titles:
            return titles
        kw = keywords.lower()
        # Base materials we care about for property questions
        bases = ("steel", "iron", "aluminum", "aluminium", "copper", "titanium")
        base = next((b for b in bases if re.search(rf"\b{re.escape(b)}\b", kw)), None)
        if base is None:
            return titles
        # Query already names a specific alloy family → keep MediaWiki order
        if any(a in kw for a in ("stainless", "electrical", "tool steel", "damascus")):
            return titles

        def score(title: str) -> tuple[int, str]:
            tl = title.lower().strip()
            if tl == base or tl == base.replace("aluminium", "aluminum"):
                return (0, tl)
            if base == "steel" and tl == "carbon steel":
                return (1, tl)
            if base in tl and not any(
                m in tl for m in ("stainless", "electrical", "tool", "damascus", "weathering")
            ):
                return (2, tl)
            if base in tl:  # alloy variants of the base
                return (8, tl)
            if tl in ("density", "specific gravity", "relative density", "energy density"):
                return (9, tl)  # generic property pages lack material numbers
            # Unrelated titles (Gauge, Density cup, plastics) sink when query names a metal
            return (10, tl)

        return sorted(titles, key=score)

    async def search(self, query: str, limit: int) -> list[SourceCandidate]:
        keywords = to_keywords(query)
        # Fetch extra hits so re-ranking can promote canonical titles that
        # MediaWiki ranked below alloys (self-improve 2026-07-13).
        fetch_n = min(max(limit * 2, limit), 20)
        url = (
            f"{self._SEARCH}?action=query&list=search&format=json"
            f"&srsearch={quote_plus(keywords)}&srlimit={fetch_n}"
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

        query_obj = data.get("query")
        search_hits = query_obj.get("search") if isinstance(query_obj, dict) else None
        if not isinstance(search_hits, list):
            # Missing query.search is an error envelope (MediaWiki returns
            # {"error": ...} without "query"); a real zero-result reply is
            # {"query": {"search": []}}. Fail loud on the former, honest [] on the
            # latter — never a silent empty list that hides an outage.
            raise SearchBackendError(self.name, "malformed response: missing query.search list")
        raw_titles = [h.get("title") for h in search_hits if h.get("title")]
        ordered = self._prefer_canonical_titles(keywords, list(raw_titles))[:limit]
        out: list[SourceCandidate] = []
        for title in ordered:
            out.append(
                SourceCandidate(
                    url_or_id=self._extract_url(title),
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
