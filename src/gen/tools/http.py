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


async def default_http_get(
    url: str,
    *,
    timeout: float = 20.0,
    headers: Mapping[str, str] | None = None,
) -> HttpResponse:
    """Standard-library GET, run in a worker thread (used in real runs only).

    A non-2xx response is returned as an ``HttpResponse`` carrying the status
    code (so the caller can mark the source as not-ok) rather than raising.
    Transport-level failures (DNS, connection, timeout) propagate as exceptions;
    the WebFetchTool catches them and reports ``ok=False`` — never a fabricated
    success.
    """
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    hdrs = {"User-Agent": "GENESIS/alpha (+anti-hallucination research)"}
    if headers:
        hdrs.update(headers)

    def _do() -> HttpResponse:
        req = urllib.request.Request(url, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                body = raw.decode("utf-8", errors="replace")
                return HttpResponse(
                    status=getattr(resp, "status", 200) or 200,
                    body=body,
                    final_url=resp.geturl(),
                )
        except urllib.error.HTTPError as exc:  # non-2xx -> keep the status code
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001 - body is best-effort only
                pass
            return HttpResponse(status=exc.code, body=body, final_url=url)

    return await asyncio.to_thread(_do)
