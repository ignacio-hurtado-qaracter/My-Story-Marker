"""Read-only tools with validated schema (spec 017, exam H05).

Usage:

    from app.tools import call_tool
    out = call_tool("query_story_bible", repo, {"novel_id": nid, "kind": "characters"},
                    observer=observer)

Every tool has an input model and an output model; `REGISTRY[name].input_schema` and
`.output_schema` are their JSON Schemas. `call_tool` validates both sides and opens a
`tool:<name>` span (K2). The same registry is served by the MCP server (`app.mcp_server`).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from app.bible import BibleRepository
from app.commons.observability import Observer
from app.tools import models
from app.tools.base import (
    AnyTool,
    Tool,
    ToolError,
    ToolInput,
    ToolInputError,
    ToolNotFoundError,
    ToolOutput,
    ToolOutputError,
    ToolUnavailableError,
)
from app.tools.download import download_novel
from app.tools.story import (
    get_chapter,
    get_chapter_summary,
    list_novels,
    list_versions,
    query_story_bible,
)

LIST_NOVELS: Final = Tool(
    name="list_novels",
    description="List every novel with its status, latest version and published version.",
    input_model=models.ListNovelsInput,
    output_model=models.ListNovelsOutput,
    handler=list_novels,
)
LIST_VERSIONS: Final = Tool(
    name="list_versions",
    description="Version history of a novel and which chapters changed in each version.",
    input_model=models.ListVersionsInput,
    output_model=models.ListVersionsOutput,
    handler=list_versions,
)
GET_CHAPTER: Final = Tool(
    name="get_chapter",
    description="One chapter (title, text, summary) of one version of a novel.",
    input_model=models.GetChapterInput,
    output_model=models.ChapterOutput,
    handler=get_chapter,
)
GET_CHAPTER_SUMMARY: Final = Tool(
    name="get_chapter_summary",
    description="The digest (~120 words) of one chapter; latest version when omitted.",
    input_model=models.GetChapterSummaryInput,
    output_model=models.ChapterSummaryOutput,
    handler=get_chapter_summary,
)
QUERY_STORY_BIBLE: Final = Tool(
    name="query_story_bible",
    description=(
        "Query the story bible of a novel: characters, places, facts (with the chapters "
        "that use them) or chronology events, optionally filtered by a substring."
    ),
    input_model=models.QueryStoryBibleInput,
    output_model=models.QueryStoryBibleOutput,
    handler=query_story_bible,
)
DOWNLOAD_NOVEL: Final = Tool(
    name="download_novel",
    description="The whole novel as a PDF (base64); latest published version when omitted.",
    input_model=models.DownloadNovelInput,
    output_model=models.DownloadNovelOutput,
    handler=download_novel,
)

REGISTRY: Final[Mapping[str, AnyTool]] = {
    t.name: t
    for t in (
        LIST_NOVELS,
        LIST_VERSIONS,
        GET_CHAPTER,
        GET_CHAPTER_SUMMARY,
        QUERY_STORY_BIBLE,
        DOWNLOAD_NOVEL,
    )
}


def call_tool(
    name: str,
    repo: BibleRepository,
    raw: Mapping[str, object] | None = None,
    *,
    observer: Observer | None = None,
) -> ToolOutput:
    """Run the tool `name` with validated input and output under a `tool:<name>` span."""
    tool = REGISTRY.get(name)
    if tool is None:
        message = f"unknown tool {name!r}"
        raise ToolInputError(message)
    return tool.run(repo, raw, observer=observer)


__all__ = [
    "DOWNLOAD_NOVEL",
    "GET_CHAPTER",
    "GET_CHAPTER_SUMMARY",
    "LIST_NOVELS",
    "LIST_VERSIONS",
    "QUERY_STORY_BIBLE",
    "REGISTRY",
    "AnyTool",
    "Tool",
    "ToolError",
    "ToolInput",
    "ToolInputError",
    "ToolNotFoundError",
    "ToolOutput",
    "ToolOutputError",
    "ToolUnavailableError",
    "call_tool",
    "models",
]
