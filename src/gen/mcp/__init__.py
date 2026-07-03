"""MCP (Model Context Protocol) integration — external tools behind GENESIS's Tool protocol."""

from .adapter import HAVE_MCP, McpTool, connect_http, connect_stdio, mcp_tools

__all__ = ["HAVE_MCP", "McpTool", "mcp_tools", "connect_stdio", "connect_http"]
