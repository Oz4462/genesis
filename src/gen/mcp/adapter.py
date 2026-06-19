"""MCP (Model Context Protocol) client adapter — wrap an MCP server's tools as GENESIS Tools.

MCP is the 2026 de-facto standard for connecting an agent to external tools/data (Anthropic-official,
so it satisfies the owner's official-first rule). This adapter makes one MCP tool satisfy GENESIS's
existing ``core.interfaces.Tool`` protocol (``name`` + async ``__call__``), so the 5,800+ official
servers (Postgres, filesystem, web, …) become reachable behind the seam GENESIS already codes against
— no framework leaks into core (CLAUDE.md §6).

The adapter itself depends ONLY on a duck-typed ``session`` (anything exposing async ``list_tools`` /
``call_tool`` whose result carries ``isError`` / ``structuredContent`` / ``content``), so it is fully
offline-testable with a fake session — no subprocess, no network. The real connection helpers
(``connect_stdio`` / ``connect_http``) import the optional ``mcp`` package lazily; absent → they raise
``ToolError`` rather than fabricate a connection.

SECURITY / honesty (Agent-5 research note; matches the owner's production-agent rules):
  * An MCP result is UNTRUSTED DATA — never an instruction, never an ungated fact. The caller MUST
    route it through GENESIS's gate/ledger before it becomes a Claim. The adapter only fetches.
  * stdio (local subprocess) is the deterministic default; HTTP is opt-in for remote servers and stays
    out of the offline suite, exactly like the live-CLI path.
  * Pin server versions and prefer vendored/forked servers — many reference servers are archived.
Deterministic given a deterministic session; the core needs no network.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Mapping, Sequence

from ..core.errors import ToolError

try:  # the mcp package is optional — its absence is an honest abstention, not a failure
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamable_http_client

    HAVE_MCP = True
except ImportError:  # pragma: no cover - exercised on machines without mcp
    HAVE_MCP = False


def _extract(result: Any) -> object:
    """Pull usable data from a ``CallToolResult``: prefer ``structuredContent``, else the text blocks."""
    structured = getattr(result, "structuredContent", None)
    if structured:
        return structured
    content = getattr(result, "content", None) or []
    return [t for t in (getattr(c, "text", None) for c in content) if t is not None]


class McpTool:
    """One MCP server tool exposed as a GENESIS ``Tool`` (``name`` + async ``__call__``).

    Holds an ALREADY-INITIALIZED session (its lifecycle is owned by the caller / a connect_* helper).
    ``__call__(**kwargs)`` invokes the remote tool and returns its data; a transport failure OR an
    error envelope raises ``ToolError`` (a typed failure, never a fabricated result). The returned
    data is UNTRUSTED — the caller must gate it before treating it as a fact.
    """

    def __init__(self, session: Any, name: str) -> None:
        if not name.strip():
            raise ValueError("MCP tool name is empty; a Tool needs a real name for the audit.")
        self._session = session
        self.name = name

    async def __call__(self, **kwargs: Any) -> object:
        try:
            result = await self._session.call_tool(self.name, arguments=dict(kwargs))
        except Exception as exc:  # transport / server crash -> typed failure, never a silent None
            raise ToolError(self.name, f"MCP call failed: {exc}") from exc
        if getattr(result, "isError", False):
            raise ToolError(self.name, f"MCP server returned an error: {_extract(result)!r}")
        return _extract(result)


async def mcp_tools(session: Any) -> list[McpTool]:
    """Discover every tool the connected MCP server exposes and wrap each as an ``McpTool``."""
    listing = await session.list_tools()
    return [McpTool(session, tool.name) for tool in listing.tools]


def _require_mcp() -> None:
    if not HAVE_MCP:
        raise ToolError("mcp", 'the "mcp" package is not installed; run: pip install "mcp[cli]"')


@asynccontextmanager
async def connect_stdio(
    command: str, args: Sequence[str] = (), env: Mapping[str, str] | None = None
) -> AsyncIterator[Any]:
    """Connect to a LOCAL MCP server over stdio (the deterministic default) and yield an initialized
    ``ClientSession``. Requires the optional ``mcp`` package (else ``ToolError``)."""
    _require_mcp()
    params = StdioServerParameters(command=command, args=list(args), env=dict(env) if env else None)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


@asynccontextmanager
async def connect_http(url: str) -> AsyncIterator[Any]:
    """Connect to a REMOTE MCP server over streamable HTTP (opt-in; non-deterministic, needs network)
    and yield an initialized ``ClientSession``. Requires the optional ``mcp`` package (else ``ToolError``)."""
    _require_mcp()
    async with streamable_http_client(url) as (read, write, *_):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session
