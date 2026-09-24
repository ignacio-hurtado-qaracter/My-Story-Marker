"""The reader API's response and request shapes (spec 014, contract K5).

Read models only: they are built from K1 records by `app.reader.service` and never written
back. The frontend's types are generated from them through `openapi.json`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

JobStatus = Literal["queued", "resolving", "running", "done", "failed"]
EntryKind = Literal["character", "place"]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class NovelSummary(_Model):
    id: str
    title: str | None = None
    recipient: str | None = None
    status: str
    current_version: int | None = Field(
        default=None, description="The latest published version; None while nothing is published."
    )


class VersionInfo(_Model):
    version: int
    status: str
    parent: int | None = None
    changed_chapters: list[int] = Field(default_factory=list)
    note: str = ""
    created_at: str


class NovelDetail(_Model):
    id: str
    title: str | None = None
    dedication: str | None = None
    recipient: str | None = None
    status: str
    current_version: int | None = None
    versions: list[VersionInfo] = Field(default_factory=list)


class ChapterEntry(_Model):
    n: int
    title: str
    words: int
    changed_vs_parent: bool = Field(
        description="R06: the chapter's hash differs from the parent version's."
    )


class ChapterIndex(_Model):
    novel_id: str
    version: int
    status: str
    parent: int | None = None
    chapters: list[ChapterEntry]


class FactRef(_Model):
    key: str
    value: str
    kind: str


class ChapterDetail(_Model):
    novel_id: str
    version: int
    n: int
    title: str
    text: str
    words: int
    changed: bool
    facts: list[FactRef] = Field(default_factory=list)
    previous: int | None = None
    next: int | None = None


class BibleEntry(_Model):
    id: str
    kind: EntryKind
    name: str
    role: str = ""
    description: str = ""
    chapters: list[int] = Field(
        default_factory=list, description="R03: chapters of the version where it appears."
    )


class StoryBible(_Model):
    novel_id: str
    version: int | None = None
    characters: list[BibleEntry]
    places: list[BibleEntry]


class ChangeRequest(_Model):
    """R05: what the reader asks for. `fragment` is the selected text, if any."""

    fragment: str | None = Field(default=None, max_length=4000)
    fact_key: str | None = Field(default=None, max_length=200)
    request: str = Field(min_length=1, max_length=1000)


class ChangeAccepted(_Model):
    job_id: str


class ChangeJob(_Model):
    job_id: str
    novel_id: str
    status: JobStatus
    fact_key: str | None = None
    new_value: str | None = None
    resolved_by: Literal["request", "match", "model"] | None = None
    new_version: int | None = None
    changed_chapters: list[int] = Field(default_factory=list)
    detail: str = ""


__all__ = [
    "BibleEntry",
    "ChangeAccepted",
    "ChangeJob",
    "ChangeRequest",
    "ChapterDetail",
    "ChapterEntry",
    "ChapterIndex",
    "EntryKind",
    "FactRef",
    "JobStatus",
    "NovelDetail",
    "NovelSummary",
    "StoryBible",
    "VersionInfo",
]
