"""Minimal async HTTP boundary for tool adapters.

Why an abstraction instead of calling a library directly: it lets every tool be
tested WITHOUT a network (inject a fake ``HttpGet``), and keeps the concrete
client a swappable adapter detail (CLAUDE.md §6). The default implementation
uses only the standard library, so the package has no hard HTTP dependency.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import socket
from dataclasses import dataclass
from typing import Awaitable, Callable, Mapping
from urllib.parse import urlsplit


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


# --- SSRF guard (WORK_QUEUE D8) -------------------------------------------------
# The research fetch target is attacker-influenced (it comes from search-API
# responses / SERP parsers). A compromised source must not be able to steer the
# transport into loopback, RFC1918, link-local (cloud metadata 169.254.169.254),
# 0.0.0.0 or ULA fc00::/7. NOTE: this guards the UNTRUSTED research path only —
# operator-configured local services (Ollama LLM/embedder base_url) use their own
# transports and stay reachable; `allow_private_hosts=True` is the explicit
# operator opt-in for local targets on this transport.

_SSRF_SCHEMES = ("http", "https")


def _ip_block_reason(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str | None:
    """Why this address must not be fetched, or None if it is publicly routable."""
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped  # ::ffff:10.0.0.1 must be judged as 10.0.0.1
    if ip.is_unspecified:
        return "unspecified address (0.0.0.0 / ::)"
    if ip.is_loopback:
        return "loopback address"
    if ip.is_link_local:
        return "link-local address (incl. cloud metadata 169.254.169.254)"
    if ip.is_private:
        return "private range (RFC1918 / ULA fc00::/7)"
    if ip.is_multicast:
        return "multicast address"
    if ip.is_reserved:
        return "reserved address"
    return None


def ssrf_host_block_reason(url: str) -> str | None:
    """Syntactic SSRF check (no DNS): block literal non-public IPs and localhost.

    Returns a human-readable reason if the URL's host is a literal address in a
    non-public range (or a loopback hostname), else None. Hostnames that need
    DNS are NOT judged here — that happens in the transport, where every
    resolved address is checked (``_resolved_ssrf_block_reason``). This split
    keeps the check usable in offline tests and injected fakes.
    """
    host = urlsplit(url).hostname
    if not host:
        return "missing host"
    lowered = host.lower()
    if lowered == "localhost" or lowered.endswith(".localhost"):
        return f"loopback host {host!r}"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return None  # a DNS name; resolution-time check happens in the transport
    reason = _ip_block_reason(ip)
    return f"non-public IP {host} ({reason})" if reason else None


def _resolved_ssrf_block_reason(url: str) -> str | None:
    """Full SSRF check: scheme allowlist + literal guard + DNS resolution.

    ALL addresses returned by ``socket.getaddrinfo`` must be publicly routable —
    one private address blocks the fetch (a rebinding-style answer with a public
    decoy and a private target must not pass). A DNS *failure* returns None: the
    connect will fail loudly with the same error, so nothing is hidden.
    """
    parts = urlsplit(url)
    if parts.scheme.lower() not in _SSRF_SCHEMES:
        return f"unsupported URL scheme: {parts.scheme or '(none)'}"
    literal = ssrf_host_block_reason(url)
    if literal:
        return literal
    host = parts.hostname
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass  # a DNS name — resolve and check below
    else:
        return None  # a literal that survived the guard above is public: no DNS needed
    port = parts.port or (443 if parts.scheme.lower() == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return None  # resolution failure surfaces identically at connect time
    if not infos:
        return f"DNS returned no addresses for {host}"
    for _family, _type, _proto, _canon, sockaddr in infos:
        addr = str(sockaddr[0]).split("%", 1)[0]  # strip IPv6 zone id
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return f"unparseable resolved address {addr!r} for {host}"
        reason = _ip_block_reason(ip)
        if reason:
            return f"{host} resolves to non-public address {addr} ({reason})"
    return None


def _redirect_handler(allow_private_hosts: bool):
    """Redirect handler that re-validates EVERY redirect target (D8).

    The first URL being clean means nothing if hop 2 points at 169.254.169.254;
    each hop is checked with the same scheme allowlist + resolved-address guard
    as the initial request. A blocked hop raises ``ValueError`` (the caller turns
    it into an honest ``ok=False``).
    """
    import urllib.request

    class _GuardedRedirects(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if urlsplit(newurl).scheme.lower() not in _SSRF_SCHEMES:
                raise ValueError(f"blocked redirect to non-http(s) URL {newurl!r}")
            if not allow_private_hosts:
                reason = _resolved_ssrf_block_reason(newurl)
                if reason:
                    raise ValueError(f"blocked redirect to {newurl!r}: {reason}")
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    return _GuardedRedirects()


def _guarded_urlopen(req, *, timeout: float, allow_private_hosts: bool = False):
    """Open a request through an opener whose redirect hops are SSRF-checked."""
    import urllib.request

    opener = urllib.request.build_opener(_redirect_handler(allow_private_hosts))
    return opener.open(req, timeout=timeout)


async def default_http_get(
    url: str,
    *,
    timeout: float = 20.0,
    headers: Mapping[str, str] | None = None,
    max_retries: int = 2,
    max_bytes: int = 5_000_000,
    allow_private_hosts: bool = False,
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

    SSRF guard (WORK_QUEUE D8): before connecting, the target host is checked —
    literal non-public IPs are refused outright and DNS names must resolve to
    publicly routable addresses ONLY. Every redirect hop is re-validated with the
    same rule. A blocked target raises ``ValueError`` with the reason, which the
    WebFetchTool converts into an honest, ledger-visible ``ok=False``.
    ``allow_private_hosts=True`` is the explicit operator opt-in for local
    targets (e.g. a self-hosted service); the research path never sets it.
    """
    import urllib.error
    import urllib.request

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
        if not allow_private_hosts:
            block = _resolved_ssrf_block_reason(url)
            if block:
                raise ValueError(f"blocked non-public URL {url!r}: {block}")
        req = urllib.request.Request(url, headers=hdrs)
        try:
            with _guarded_urlopen(
                req, timeout=timeout, allow_private_hosts=allow_private_hosts
            ) as resp:
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
            except Exception:
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
