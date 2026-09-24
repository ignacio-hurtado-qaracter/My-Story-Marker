"""Read-only MCP server over the story bible (spec 017, X01). See `README.md`."""

from __future__ import annotations

from app.mcp_server.server import SERVER_NAME, build_server, open_readonly, run_tool

__all__ = ["SERVER_NAME", "build_server", "open_readonly", "run_tool"]
