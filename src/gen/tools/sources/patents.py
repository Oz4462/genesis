"""PatentsView search backend — the prior-art PATENT channel (INVENTOR §7/§13 patent gap).

PatentsView (https://patentsview.org) is a USPTO-funded, public-domain (US government work) patent database.
This backend queries its API and returns ``SourceCandidate``s, DISCOVERY only: it never asserts a fact, the
candidate is unfetched until retrieved, and each candidate's id resolves to a real patent (a Google Patents
URL built from the stable ``patent_id``) — provenance, never invented. Patents are the prior-art channel a
novelty check needs and literature alone misses.

KEY BOUNDARY (honest): the current PatentsView v1 endpoint requires an ``X-Api-Key`` header. The seam's
``HttpGet`` takes only a URL, so the key is baked into the INJECTED transport by the caller
(``functools.partial(default_http_get, headers={"X-Api-Key": key})``), not handled here — keeping the seam
uniform. Without a key the endpoint returns 403, which becomes a loud ``SearchBackendError`` (an honest
BLOCKED, never a fabricated miss). Offline-fixture-testable through the same injected transport.
"""

from __future__ import annotations

import json
from urllib.parse import quote

from ...core.errors import SearchBackendError
from ...core.state import SourceCandidate
from ..http import HttpGet
from ..search import _truncate, to_keywords

_API = "https://search.patentsview.org/api/v1/patent/"
_FIELDS = '["patent_id","patent_title","patent_date"]'


def _patent_candidates(data: dict, backend: str, limit: int) -> list[SourceCandidate]:
    """Parse a PatentsView response (``{"patents":[{patent_id,patent_title,patent_date}]}``, tolerating a
    ``data.patents`` nesting) into candidates. Rows without a stable ``patent_id`` are skipped."""
    rows = data.get("patents")
    if rows is None and isinstance(data.get("data"), dict):
        rows = data["data"].get("patents")
    out: list[SourceCandidate] = []
    for row in (rows or [])[:limit]:
        pid = str(row.get("patent_id") or "").strip()
        if not pid:
            continue  # no stable id -> skip, never invent one
        title = row.get("patent_title")
        title = " ".join(title.split()) if isinstance(title, str) and title.strip() else None
        date = row.get("patent_date")
        note_bits = [f"granted {date}"] if date else []
        note = "PatentsView (US gov, public domain): " + (
            "; ".join(_truncate(b) for b in note_bits) if note_bits else "patent match")
        url = f"https://patents.google.com/patent/US{pid}" if pid.isalnum() else f"patentsview:{pid}"
        out.append(SourceCandidate(
            url_or_id=url, title=title, backend=backend, relevance_note=note, fetched_ok=False))
    return out


class PatentsViewBackend:
    """Discovery via the PatentsView patent API (public domain). Satisfies the ``SearchBackend`` Protocol.

    The injected ``http_get`` must carry the ``X-Api-Key`` header for the live v1 endpoint (see module note);
    offline tests inject a fake transport returning a canned PatentsView JSON body."""

    name = "patents"

    def __init__(self, http_get: HttpGet) -> None:
        self._http_get = http_get

    async def search(self, query: str, limit: int) -> list[SourceCandidate]:
        q = json.dumps({"_text_any": {"patent_title": to_keywords(query)}})
        o = json.dumps({"size": max(1, limit)})
        url = f"{_API}?q={quote(q)}&f={quote(_FIELDS)}&o={quote(o)}"
        try:
            resp = await self._http_get(url)
        except Exception as exc:
            raise SearchBackendError(self.name, str(exc)) from exc
        if not (200 <= resp.status < 300):
            raise SearchBackendError(self.name, f"HTTP {resp.status}")
        try:
            data = json.loads(resp.body)
        except json.JSONDecodeError as exc:
            raise SearchBackendError(self.name, f"bad JSON: {exc}") from exc
        return _patent_candidates(data, self.name, limit)


__all__ = ["PatentsViewBackend"]
