"""WebFetchTool — the honest fetch (PHASE_ALPHA §3.2 / Aufgabe 3).

The single most safety-critical adapter. Its contract: a source that could not
be retrieved is NEVER reported as a usable source. A failed fetch yields
``FetchResult(ok=False, content=None)`` and is recorded in the ledger as a failed
fetch, so the gate's DEAD_CITATION check (PHASE_ALPHA §4 cond. 5) can reject any
claim that tries to cite it. There is no code path that turns a failure into
content.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlsplit

from ..core.errors import FetchFailedError
from ..core.state import SourceRef, SourceSupport
from .http import HttpGet, content_hash

# The fetch target is attacker-influenced (it comes from a search-API response or
# an injected SERP parser), and a real transport (urllib) will happily open
# file:// / ftp:// / data:// — a local-file read / SSRF vector. Only these two
# schemes are ever fetchable; anything else is refused at the contract boundary.
_ALLOWED_SCHEMES = ("http", "https")

# Text fields carrying readable prose in common JSON API responses, in priority
# order (a Wikipedia REST summary uses 'extract').
_PROSE_FIELDS = ("extract", "content", "text", "body", "abstract", "summary")


def readable_text(content: str) -> str:
    """Return human-readable prose from a fetched body.

    If the body is a JSON API response (e.g. a Wikipedia REST summary), return its
    main prose field so consumers — the scholar's model and its verbatim-quote
    guard, the skeptic's judge — work on clean prose instead of a JSON envelope
    they would otherwise paraphrase or misjudge. Plain-text or non-JSON bodies
    (and JSON without a known prose field) pass through unchanged, so this never
    hides content.
    """
    stripped = content.lstrip()
    if not stripped.startswith("{"):
        return content
    try:
        doc = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return content
    if not isinstance(doc, dict):
        return content
    for field in _PROSE_FIELDS:
        value = doc.get(field)
        if isinstance(value, str) and value.strip():
            return value
    return content


@dataclass(frozen=True)
class FetchResult:
    """Outcome of one fetch attempt. `ok` is the single source of truth.

    `content`/`content_hash` are populated ONLY when ``ok is True``. When the
    fetch failed, both are None and `reason` explains why.
    """

    url: str
    ok: bool
    content: str | None
    content_hash: str | None
    reason: str | None = None
    status: int | None = None

    def to_source_ref(
        self, *, support: SourceSupport = SourceSupport.SUPPORTS, span: str | None = None
    ) -> SourceRef:
        """Build a SourceRef whose `retrieved` flag mirrors `ok` exactly.

        This is the bridge that keeps the gate honest: a non-ok fetch produces a
        SourceRef with ``retrieved=False``, which the gate flags as DEAD_CITATION
        if anyone tries to cite it as fact.
        """
        return SourceRef(
            url_or_id=self.url,
            retrieved=self.ok,
            content_hash=self.content_hash,
            span=span,
            support=support,
        )


def require_ok(result: FetchResult) -> str:
    """Return fetched content, or raise FetchFailedError if the fetch failed.

    For callers (scholar/skeptic) that cannot proceed without the content and
    prefer an exception to a None check.
    """
    if not result.ok or result.content is None:
        raise FetchFailedError(result.url, result.reason or "fetch not ok")
    return result.content


class WebFetchTool:
    """Fetches a URL and reports retrieval honestly. Satisfies the ``Tool`` Protocol.

    Optionally records every attempt (success and failure) in a ledger via
    ``record_fetch``, which is what makes dead citations detectable later.
    """

    name = "web_fetch"

    def __init__(self, http_get: HttpGet, *, ledger=None, run_id: str | None = None) -> None:
        self._http_get = http_get
        self._ledger = ledger
        self._run_id = run_id

    async def __call__(self, *, url: str) -> FetchResult:  # type: ignore[override]
        """Fetch `url`. Never raises on a bad response; returns ok=False instead.

        Transport exceptions are caught and turned into ``ok=False`` so a network
        problem can never masquerade as a fabricated success. A non-http(s) URL is
        refused here, before the transport, so a malicious candidate URL can never
        reach urllib's file:// / ftp:// handlers — it becomes an honest, recorded
        ok=False regardless of which ``http_get`` is injected.
        """
        scheme = urlsplit(url).scheme.lower()
        if scheme not in _ALLOWED_SCHEMES:
            return await self._finish(
                url,
                ok=False,
                content=None,
                reason=f"unsupported URL scheme: {scheme or '(none)'}",
                status=None,
            )
        try:
            resp = await self._http_get(url)
        except Exception as exc:  # noqa: BLE001 - any transport failure => not ok
            return await self._finish(url, ok=False, content=None, reason=str(exc), status=None)

        if not (200 <= resp.status < 300):
            return await self._finish(
                url, ok=False, content=None, reason=f"HTTP {resp.status}", status=resp.status
            )
        if not resp.body.strip():
            return await self._finish(
                url, ok=False, content=None, reason="empty body", status=resp.status
            )

        h = content_hash(resp.body)
        return await self._finish(
            url, ok=True, content=resp.body, reason=None, status=resp.status, h=h
        )

    async def _finish(
        self,
        url: str,
        *,
        ok: bool,
        content: str | None,
        reason: str | None,
        status: int | None,
        h: str | None = None,
    ) -> FetchResult:
        if self._ledger is not None and self._run_id is not None:
            await self._ledger.record_fetch(self._run_id, url, ok, h)
        return FetchResult(
            url=url, ok=ok, content=content, content_hash=h, reason=reason, status=status
        )
