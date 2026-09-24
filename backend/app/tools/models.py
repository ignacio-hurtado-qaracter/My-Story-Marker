"""Input and output models of the read-only tools (spec 017). Their JSON Schemas are the
tools' `input_schema` / `output_schema`, served verbatim by the MCP server."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from app.tools.base import ToolInput, ToolOutput

NovelId = Annotated[
    str, Field(min_length=1, max_length=128, description="Novel id, e.g. `nov-1a2b3c4d5e6f`.")
]

BibleKind = Literal["characters", "places", "facts", "chronology"]


# -- list_novels -----------------------------------------------------------------------


class ListNovelsInput(ToolInput):
    """No arguments."""


class NovelInfo(ToolOutput):
    id: str
    title: str | None = None
    status: str
    recipient_name: str | None = None
    latest_version: int | None = Field(default=None, description="Highest version number.")
    latest_status: str | None = None
    published_version: int | None = Field(
        default=None, description="Latest published version, the one the reader shows."
    )


class ListNovelsOutput(ToolOutput):
    novels: list[NovelInfo]


# -- list_versions ---------------------------------------------------------------------


class ListVersionsInput(ToolInput):
    novel_id: NovelId


class VersionInfo(ToolOutput):
    version: int
    parent_version: int | None = None
    status: str
    changed_chapters: list[int] = Field(description="Chapters whose text changed vs. parent.")
    note: str = ""
    created_at: str


class ListVersionsOutput(ToolOutput):
    novel_id: str
    versions: list[VersionInfo]


# -- get_chapter / get_chapter_summary ---------------------------------------------------


class GetChapterInput(ToolInput):
    novel_id: NovelId
    version: int = Field(ge=1, le=10_000)
    chapter: int = Field(ge=1, le=100)


class ChapterOutput(ToolOutput):
    novel_id: str
    version: int
    chapter: int
    title: str
    text: str
    summary: str
    word_count: int
    hash: str


class GetChapterSummaryInput(ToolInput):
    novel_id: NovelId
    version: int | None = Field(
        default=None, ge=1, le=10_000, description="Omitted: the latest version."
    )
    chapter: int = Field(ge=1, le=100)


class ChapterSummaryOutput(ToolOutput):
    novel_id: str
    version: int
    chapter: int
    title: str
    summary: str


# -- query_story_bible -----------------------------------------------------------------


class QueryStoryBibleInput(ToolInput):
    novel_id: NovelId
    kind: BibleKind
    query: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Case-insensitive substring filter over names, keys and descriptions.",
    )


class CharacterInfo(ToolOutput):
    id: str
    name: str
    role: str = ""
    birth_date: str | None = None
    description: str = ""


class PlaceInfo(ToolOutput):
    id: str
    name: str
    description: str = ""


class FactInfo(ToolOutput):
    key: str
    value: str
    kind: str
    mandatory: bool
    chapters: list[int] = Field(description="Chapters of the latest version that use the fact.")


class EventInfo(ToolOutput):
    id: str
    seq: int
    story_date: str | None = None
    chapter: int | None = None
    scene: int | None = None
    place: str | None = None
    description: str = ""
    kind: str
    participants: list[str] = Field(description="Character names.")


class QueryStoryBibleOutput(ToolOutput):
    novel_id: str
    kind: BibleKind
    characters: list[CharacterInfo] = Field(default_factory=list)
    places: list[PlaceInfo] = Field(default_factory=list)
    facts: list[FactInfo] = Field(default_factory=list)
    events: list[EventInfo] = Field(default_factory=list)


# -- download_novel --------------------------------------------------------------------


class DownloadNovelInput(ToolInput):
    novel_id: NovelId
    version: int | None = Field(
        default=None,
        ge=1,
        le=10_000,
        description="Omitted: the latest published version, else the latest version.",
    )


class DownloadNovelOutput(ToolOutput):
    novel_id: str
    version: int
    filename: str
    media_type: Literal["application/pdf"] = "application/pdf"
    size_bytes: int
    content_base64: str


__all__ = [
    "BibleKind",
    "ChapterOutput",
    "ChapterSummaryOutput",
    "CharacterInfo",
    "DownloadNovelInput",
    "DownloadNovelOutput",
    "EventInfo",
    "FactInfo",
    "GetChapterInput",
    "GetChapterSummaryInput",
    "ListNovelsInput",
    "ListNovelsOutput",
    "ListVersionsInput",
    "ListVersionsOutput",
    "NovelInfo",
    "PlaceInfo",
    "QueryStoryBibleInput",
    "QueryStoryBibleOutput",
    "VersionInfo",
]
