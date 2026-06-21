"""Minimal async HTTP boundary for tool adapters.

Why an abstraction instead of calling a library directly: it lets every tool be
tested WITHOUT a network (inject a fake ``HttpGet``), and keeps the concrete
client a swappable adapter detail (CLAUDE.md §6). The default implementation
uses only the standard library, so the package has no hard HTTP dependency.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from typing import Awaitable, Callable, Mapping


@dataclass(frozen=True)
class HttpResponse:
    """A normalized HTTP response. `body` is decoded text (possibly empty)."""

    status: int
    body: str
    final_url: str | None = None


# An injectable async GET. Real adapters and test fakes both satisfy this.
HttpGet = Callable[[str], Awaitable[HttpResponse]]


def content_hash(text: str) -> str:
    """Stable SHA-256 of fetched content — anchors reproducibility (A5)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Descriptive UA per public-API etiquette (Wikipedia/Semantic Scholar ask clients
# to identify themselves); a generic UA is a common cause of throttling.
_USER_AGENT = "GENESIS/alpha (anti-hallucination research; +https://github.com/genesis)"


async def default_http_get(
    url: str,
    *,
    timeout: float = 20.0,
    headers: Mapping[str, str] | None = None,
    max_retries: int = 2,
    max_bytes: int = 5_000_000,
) -> HttpResponse:
    """Standard-library GET, run in a worker thread (used in real runs only).

    A non-2xx response is returned as an ``HttpResponse`` carrying the status
    code (so the caller can mark the source as not-ok) rather than raising.
    Transport-level failures (DNS, connection, timeout) propagate as exceptions;
    the WebFetchTool catches them and reports ``ok=False`` — never a fabricated
    success.

    The body read is capped at ``max_bytes``: the fetch target is attacker-
    influenced, so an unbounded ``read()`` of a hostile multi-gigabyte response
    would exhaust memory. An over-cap body raises (→ honest ``ok=False`` upstream)
    rather than silently truncating, which would corrupt the content hash (A5).

    Polite throttle handling: on 429/503 it backs off (honoring ``Retry-After``
    when present) and retries up to ``max_retries`` times. If the throttle
    persists, the final 429/503 response is returned as-is — so an exhausted
    retry still becomes an honest ``ok=False`` downstream, never a fake success.
    """
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    hdrs = {"User-Agent": _USER_AGENT}
    if headers:
        hdrs.update(headers)

    def _read_capped(reader) -> bytes:
        # read one byte past the cap so an exactly-at-cap body is still accepted
        # but anything larger is detected and refused (no silent truncation).
        raw = reader.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ValueError(f"response body exceeds {max_bytes} bytes")
        return raw

    def _do() -> tuple[HttpResponse, str | None]:
        """Return (response, Retry-After header). Retry-After is None unless throttled."""
        req = urllib.request.Request(url, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = _read_capped(resp).decode("utf-8", errors="replace")
                return HttpResponse(
                    status=getattr(resp, "status", 200) or 200,
                    body=body,
                    final_url=resp.geturl(),
                ), None
        except urllib.error.HTTPError as exc:  # non-2xx -> keep the status code
            body = ""
            try:
                body = _read_capped(exc).decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001 - body is best-effort only
                pass
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            return HttpResponse(status=exc.code, body=body, final_url=url), retry_after

    backoff = 1.0
    resp, retry_after = await asyncio.to_thread(_do)
    for _ in range(max_retries):
        if resp.status not in (429, 503):
            return resp
        try:
            delay = float(retry_after) if retry_after else backoff
        except ValueError:  # Retry-After can be an HTTP-date; fall back to backoff
            delay = backoff
        await asyncio.sleep(min(delay, 10.0))  # cap so a hostile header can't stall us
        backoff *= 2
        resp, retry_after = await asyncio.to_thread(_do)
    return resp
