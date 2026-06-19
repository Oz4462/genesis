"""OpenAlex search backend — prior-art / literature discovery over a CC0 scholarly graph.

OpenAlex (https://openalex.org) is a free, openly-licensed (data CC0) index of ~250M scholarly works — the
open successor to Microsoft Academic Graph. It needs no API key (a polite ``mailto`` opts into the faster
pool). This backend queries the works endpoint and returns ``SourceCandidate``s, DISCOVERY only: it never
asserts a fact, the candidate is unfetched until ``scholar`` retrieves it, and each candidate's id is the
stable OpenAlex work id (its DOI in the note) — real provenance, never invented.

Transport is the injected ``HttpGet`` (offline-testable, live-probeable). A non-2xx or unparseable response
raises ``SearchBackendError`` (loud) rather than fabricating results. Deterministic given a response.
"""

from __future__ import annotations

import json
from urllib.parse import quote_plus

from ...core.errors import SearchBackendError
from ...core.state import SourceCandidate
from ..http import HttpGet
from ..search import _truncate, to_keywords

_API = "https://api.openalex.org/works"


class OpenAlexBackend:
    """Discovery via the OpenAlex works API (data CC0). Satisfies the ``SearchBackend`` Protocol.

    ``mailto`` (optional) joins OpenAlex's polite pool per their etiquette; it is sent as a query param only,
    never logged into a candidate."""

    name = "openalex"

    def __init__(self, http_get: HttpGet, *, mailto: str | None = None) -> None:
        self._http_get = http_get
        self._mailto = mailto

    async def search(self, query: str, limit: int) -> list[SourceCandidate]:
        url = f"{_API}?search={quote_plus(to_keywords(query))}&per-page={max(1, limit)}"
        if self._mailto:
            url += f"&mailto={quote_plus(self._mailto)}"
        try:
            resp = await self._http_get(url)
        except Exception as exc:  # noqa: BLE001 - transport failure is a loud backend error, not a fake miss
            raise SearchBackendError(self.name, str(exc)) from exc
        if not (200 <= resp.status < 300):
            raise SearchBackendError(self.name, f"HTTP {resp.status}")
        try:
            data = json.loads(resp.body)
        except json.JSONDecodeError as exc:
            raise SearchBackendError(self.name, f"bad JSON: {exc}") from exc

        out: list[SourceCandidate] = []
        for work in (data.get("results") or [])[:limit]:
            work_id = (work.get("id") or "").strip()
            if not work_id:
                continue  # no stable id -> skip, never invent one
            title = work.get("title")
            title = " ".join(title.split()) if isinstance(title, str) and title.strip() else None
            note_bits = []
            year = work.get("publication_year")
            if year:
                note_bits.append(f"published {year}")
            doi = work.get("doi")
            if isinstance(doi, str) and doi:
                note_bits.append(f"doi {doi}")
            cited = work.get("cited_by_count")
            if isinstance(cited, int):
                note_bits.append(f"cited_by {cited}")
            note = "OpenAlex (CC0): " + ("; ".join(_truncate(b) for b in note_bits) if note_bits else "match")
            out.append(SourceCandidate(
                url_or_id=work_id, title=title, backend=self.name, relevance_note=note, fetched_ok=False))
        return out


__all__ = ["OpenAlexBackend"]
