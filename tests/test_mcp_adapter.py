"""Tests for the MCP client adapter (gen/mcp/adapter.py).

Exercised with a duck-typed FAKE session — no real MCP server, no subprocess, no network — so these run
anywhere, offline. Pins: an McpTool satisfies GENESIS's Tool protocol; structured content is preferred
and text blocks are the fallback; an error envelope OR a transport crash raises a typed ToolError
(never a fabricated result); the factory wraps every advertised tool; and a missing ``mcp`` package is
an honest abstention, not a fake connection.
"""

from types import SimpleNamespace

import pytest

from gen.core.errors import ToolError
from gen.core.interfaces import Tool
from gen.mcp import adapter
from gen.mcp.adapter import McpTool, connect_stdio, mcp_tools


class _Result:
    def __init__(self, *, content=None, structured=None, is_error=False):
        self.content = content or []
        self.structuredContent = structured
        self.isError = is_error


class _FakeSession:
    """Satisfies the duck-typed session the adapter needs (async list_tools / call_tool)."""

    def __init__(self, *, tool_names=(), result=None, raise_exc=None):
        self._tool_names = tool_names
        self._result = result if result is not None else _Result(structured={"ok": True})
        self._raise = raise_exc
        self.calls: list[tuple[str, dict]] = []

    async def list_tools(self):
        return SimpleNamespace(tools=[SimpleNamespace(name=n) for n in self._tool_names])

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if self._raise is not None:
            raise self._raise
        return self._result


@pytest.mark.asyncio
async def test_mcp_tool_satisfies_protocol_and_returns_structured_content():
    session = _FakeSession(result=_Result(structured={"rows": 42}))
    tool = McpTool(session, "query")
    assert isinstance(tool, Tool)                       # runtime_checkable Tool protocol (name + __call__)
    out = await tool(sql="select 1", limit=5)
    assert out == {"rows": 42}
    assert session.calls == [("query", {"sql": "select 1", "limit": 5})]   # kwargs -> arguments


@pytest.mark.asyncio
async def test_text_content_is_the_fallback_when_unstructured():
    blocks = [SimpleNamespace(text="line A"), SimpleNamespace(text="line B"), SimpleNamespace(data=b"x")]
    tool = McpTool(_FakeSession(result=_Result(content=blocks)), "read")
    assert await tool(path="/x") == ["line A", "line B"]   # text blocks collected, non-text skipped


@pytest.mark.asyncio
async def test_error_envelope_raises_typed_tool_error():
    tool = McpTool(_FakeSession(result=_Result(structured={"msg": "denied"}, is_error=True)), "danger")
    with pytest.raises(ToolError):
        await tool()


@pytest.mark.asyncio
async def test_transport_crash_raises_typed_tool_error():
    tool = McpTool(_FakeSession(raise_exc=OSError("pipe broke")), "flaky")
    with pytest.raises(ToolError):
        await tool()


def test_empty_tool_name_rejected_at_construction():
    with pytest.raises(ValueError):
        McpTool(_FakeSession(), "   ")


@pytest.mark.asyncio
async def test_mcp_tools_factory_wraps_every_advertised_tool():
    session = _FakeSession(tool_names=("query", "insert", "list_tables"))
    tools = await mcp_tools(session)
    assert [t.name for t in tools] == ["query", "insert", "list_tables"]
    assert all(isinstance(t, McpTool) for t in tools)


@pytest.mark.asyncio
async def test_connect_helper_abstains_honestly_when_mcp_absent(monkeypatch):
    # With the mcp package "absent", a connection attempt raises ToolError instead of fabricating one.
    monkeypatch.setattr(adapter, "HAVE_MCP", False)
    with pytest.raises(ToolError):
        async with connect_stdio("some-server", ["--flag"]):
            pass
