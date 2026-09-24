"""Contract K1: the typed records of the authoritative story bible (spec 005).

Frozen pydantic models, one per table (plus the chronology export). They are what
`BibleRepository` returns; nothing outside `app.bible` sees a `sqlite3.Row`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

FactSource = Literal["interview", "free_text", "planner"]
EventKind = Literal["normal", "death", "departure"]
VersionStatus = Literal["draft", "published", "blocked"]
CheckpointStatus = Literal["pending", "in_progress", "complete", "failed"]
TermScope = Literal["global", "novel"]


class _Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Novel(_Record):
    id: str
    session_id: str
    title: str | None = None
    dedication: str | None = None
    recipient_name: str | None = None
    status: str = "draft"
    created_at: str
    updated_at: str


class Brief(_Record):
    novel_id: str
    data: dict[str, JsonValue]
    schema_version: str = "1"
    valid: bool = False
    created_at: str
    updated_at: str


class Fact(_Record):
    id: int
    novel_id: str
    key: str
    value: str
    kind: str
    source: FactSource
    mandatory: bool = False
    created_at: str
    updated_at: str


class FactUsage(_Record):
    fact_id: int
    version: int
    chapter: int
    scene: int


class Character(_Record):
    id: str
    novel_id: str
    name: str
    role: str = ""
    birth_date: str | None = None
    description: str = ""
    fact_id: int | None = None


class Place(_Record):
    id: str
    novel_id: str
    name: str
    description: str = ""
    fact_id: int | None = None


class Participant(_Record):
    character_id: str
    age_at_event: int | None = None


class ChronologyEvent(_Record):
    id: str
    novel_id: str
    seq: int
    story_date: str | None = None
    chapter: int | None = None
    scene: int | None = None
    place_id: str | None = None
    description: str = ""
    kind: EventKind = "normal"
    participants: tuple[Participant, ...] = ()


class NovelVersion(_Record):
    novel_id: str
    version: int
    parent_version: int | None = None
    status: VersionStatus = "draft"
    changed_chapters: tuple[int, ...] = ()
    note: str = ""
    trace_id: str | None = None
    created_at: str
    updated_at: str


class ChapterVersion(_Record):
    novel_id: str
    version: int
    chapter: int
    title: str = ""
    text: str
    hash: str = Field(description="SHA-256 hex of `text` (UTF-8).")
    summary: str = ""
    word_count: int
    created_at: str


class Checkpoint(_Record):
    novel_id: str
    version: int
    chapter: int
    status: CheckpointStatus
    detail: str = ""
    updated_at: str


class ForbiddenTerm(_Record):
    id: int
    scope: TermScope
    novel_id: str | None = None
    term: str
    reason: str = ""


class PolicyDecision(_Record):
    id: int
    novel_id: str | None = None
    version: int | None = None
    chapter: int | None = None
    scene: int | None = None
    policy: str
    decision: str
    term: str | None = None
    detail: str = ""
    attempt: int | None = None
    trace_id: str | None = None
    created_at: str


class StoredValidatorResult(_Record):
    id: int
    novel_id: str
    version: int | None = None
    chapter: int | None = None
    scene: int | None = None
    name: str
    point: str
    passed: bool
    score: float | None = None
    evidence: tuple[str, ...] = ()
    explanation: str = ""
    trace_id: str | None = None
    created_at: str


class ChapterCost(_Record):
    chapter: int | None
    calls: int
    input_tokens: int
    output_tokens: int
    cache_read: int
    cost_usd: float
    latency_s: float


class CostSummary(_Record):
    novel_id: str
    calls: int
    input_tokens: int
    output_tokens: int
    cache_read: int
    cache_creation: int
    cost_usd: float
    latency_s: float
    by_chapter: tuple[ChapterCost, ...] = ()
    by_role: dict[str, float] = Field(default_factory=dict)


__all__ = [
    "Brief",
    "ChapterCost",
    "ChapterVersion",
    "Character",
    "Checkpoint",
    "CheckpointStatus",
    "ChronologyEvent",
    "CostSummary",
    "EventKind",
    "Fact",
    "FactSource",
    "FactUsage",
    "ForbiddenTerm",
    "Novel",
    "NovelVersion",
    "Participant",
    "Place",
    "PolicyDecision",
    "StoredValidatorResult",
    "TermScope",
    "VersionStatus",
]
