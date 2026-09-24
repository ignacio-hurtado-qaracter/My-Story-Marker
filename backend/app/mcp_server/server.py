"""The read-only MCP server (spec 017, exam X01).

Serves every tool of `app.tools.REGISTRY` over MCP with FastMCP. Each MCP tool advertises
the tool's own input and output JSON Schemas, validates its arguments through the tool
layer (`Tool.run`), and runs inside a Langfuse trace (session = novel) with a
`tool:<name>` span and a `tool_ok` score (K2; a no-op without Langfuse keys).

Read-only by construction: the database is opened with `mode=ro` and `query_only`, no
migration runs, and no tool handler calls a write method of `BibleRepository`.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Final

import anyio.to_thread
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError as McpToolError
from fastmcp.tools import Tool as McpTool
from fastmcp.tools import ToolResult
from mcp.types import ToolAnnotations
from pydantic import JsonValue, PrivateAttr

from app.bible import BibleRepository
from app.commons.config import get_settings
from app.commons.observability import Observer, get_observer
from app.tools import REGISTRY, AnyTool, ToolError, ToolOutput

SERVER_NAME: Final[str] = "story-maker"
DEFAULT_SESSION: Final[str] = "mcp-server"

INSTRUCTIONS: Final[str] = (
    "Read-only access to the gift-novel platform: list novels and their versions, read "
    "chapters and chapter summaries, query the story bible (characters, places, facts, "
    "chronology) and download a novel as PDF. No tool writes."
)


def open_readonly(path: Path | None = None) -> BibleRepository:
    """The authoritative database, read-only (`mode=ro`, `query_only`), without migrating."""
    target = (path or get_settings().harness_db_path).resolve()
    if not target.exists():
        message = f"story bible not found at {target} (set HARNESS_DB)"
        raise McpToolError(message)
    connection = sqlite3.connect(
        f"{target.as_uri()}?mode=ro", uri=True, isolation_level=None, check_same_thread=False
    )
    connection.row_factory = sqlite3.Row
    connection.execute("pragma query_only = ON")
    connection.execute("pragma busy_timeout = 5000")
    return BibleRepository(connection)


def run_tool(
    tool: AnyTool,
    arguments: dict[str, object],
    *,
    observer: Observer,
    db_path: Path | None = None,
) -> ToolOutput:
    """One MCP call: a trace per call, the tool's own span and validation, a score."""
    novel_id = arguments.get("novel_id")
    session = (
        observer.start_session(novel_id)
        if isinstance(novel_id, str) and novel_id
        else DEFAULT_SESSION
    )
    try:
        with observer.trace(f"mcp:{tool.name}", session_id=session, metadata={"via": "mcp"}):
            try:
                tool.validate_input(arguments)  # reject bad input before touching the DB
                with open_readonly(db_path) as repo:
                    result = tool.run(repo, arguments, observer=observer)
            except (ToolError, McpToolError) as exc:
                observer.score("tool_ok", 0.0, comment=f"{tool.name}: {exc}"[:500])
                raise McpToolError(str(exc)) from exc
            observer.score("tool_ok", 1.0, comment=tool.name)
    finally:
        observer.flush()
    return result


class BibleTool(McpTool):  # type: ignore[explicit-any]  # fastmcp.Tool has Any fields (spec 017)
    """A FastMCP tool backed by one validated tool of `app.tools`."""

    _tool: AnyTool = PrivateAttr()
    _db_path: Path | None = PrivateAttr(default=None)

    @classmethod
    def wrap(cls, tool: AnyTool, *, db_path: Path | None = None) -> BibleTool:
        mcp_tool = cls(
            name=tool.name,
            description=tool.description,
            parameters=tool.input_schema,
            output_schema=tool.output_schema,
            annotations=ToolAnnotations(
                read_only_hint=True,
                destructive_hint=False,
                idempotent_hint=True,
                open_world_hint=False,
            ),
        )
        mcp_tool._tool = tool
        mcp_tool._db_path = db_path
        return mcp_tool

    async def run(self, arguments: dict[str, JsonValue]) -> ToolResult:
        observer = get_observer()
        args: dict[str, object] = dict(arguments)
        result = await anyio.to_thread.run_sync(
            lambda: run_tool(self._tool, args, observer=observer, db_path=self._db_path)
        )
        payload = result.model_dump(mode="json")
        return ToolResult(
            content=json.dumps(payload, ensure_ascii=False), structured_content=payload
        )


def build_server(*, db_path: Path | None = None) -> FastMCP:  # type: ignore[explicit-any]  # FastMCP is generic over an Any lifespan result (spec 017)
    """The FastMCP server with every registry tool. `db_path` overrides `HARNESS_DB`."""
    server = FastMCP(SERVER_NAME, instructions=INSTRUCTIONS)
    for tool in REGISTRY.values():
        server.add_tool(BibleTool.wrap(tool, db_path=db_path))
    return server


__all__ = ["SERVER_NAME", "BibleTool", "build_server", "open_readonly", "run_tool"]
