"""arXiv search backend (Tier-3, ported from ATLAS).

Widens GENESIS's research breadth (gap #2: discovery was Semantic Scholar + Wikipedia
only). Queries the arXiv API and returns SourceCandidates — DISCOVERY only, like every
backend: it never asserts a fact, and the candidate stays unfetched until `scholar`
actually retrieves the /abs/ page.

Ported from ATLAS `hunter/scrape_arxiv.py` (Ozan's own project) but adapted to GENESIS:
transport goes through the injected ``HttpGet`` (offline-testable), and the Atom feed is
parsed with the stdlib ``xml.etree`` instead of pulling in ``feedparser`` — GENESIS keeps
its dependency surface minimal. Transport failure raises ``SearchBackendError`` (loud).
"""

from __future__ import annotations

from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

from ..core.errors import SearchBackendError
from ..core.state import SourceCandidate
from .http import HttpGet
from .search import _truncate, to_keywords

_API = "https://export.arxiv.org/api/query"
_ATOM = "{http://www.w3.org/2005/Atom}"


def _abs_id(raw_id: str) -> str:
    """'http://arxiv.org/abs/2511.12345v1' -> '2511.12345v1' (else the raw id)."""
    return raw_id.rsplit("/abs/", 1)[1] if "/abs/" in raw_id else raw_id


class ArxivBackend:
    """Discovery via the arXiv API. Satisfies the ``SearchBackend`` Protocol."""

    name = "arxiv"

    def __init__(self, http_get: HttpGet) -> None:
        self._http_get = http_get

    async def search(self, query: str, limit: int) -> list[SourceCandidate]:
        url = (
            f"{_API}?search_query=all:{quote_plus(to_keywords(query))}"
            f"&start=0&max_results={limit}&sortBy=relevance&sortOrder=descending"
        )
        try:
            resp = await self._http_get(url)
        except Exception as exc:  # noqa: BLE001
            raise SearchBackendError(self.name, str(exc)) from exc
        if not (200 <= resp.status < 300):
            raise SearchBackendError(self.name, f"HTTP {resp.status}")
        try:
            root = ET.fromstring(resp.body)
        except ET.ParseError as exc:
            raise SearchBackendError(self.name, f"bad Atom XML: {exc}") from exc

        out: list[SourceCandidate] = []
        for entry in root.findall(f"{_ATOM}entry")[:limit]:
            raw_id = (entry.findtext(f"{_ATOM}id") or "").strip()
            if not raw_id:
                continue  # no stable id -> skip, never invent one
            arxiv_id = _abs_id(raw_id)
            title = (entry.findtext(f"{_ATOM}title") or "").strip() or None
            summary = " ".join((entry.findtext(f"{_ATOM}summary") or "").split())
            published = (entry.findtext(f"{_ATOM}published") or "").strip()[:10]
            note_bits = []
            if published:
                note_bits.append(f"published {published}")
            if summary:
                note_bits.append(_truncate(summary))
            note = "arXiv: " + ("; ".join(note_bits) if note_bits else "match")
            out.append(
                SourceCandidate(
                    url_or_id=f"https://arxiv.org/abs/{arxiv_id}",
                    title=" ".join(title.split()) if title else None,
                    backend=self.name,
                    relevance_note=note,
                    fetched_ok=False,
                )
            )
        return out


__all__ = ["ArxivBackend"]
