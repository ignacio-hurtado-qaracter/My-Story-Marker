"""Contract K1: the authoritative story bible (spec 005).

from app.bible import BibleRepository

repo = BibleRepository.open()            # HARNESS_DB, default data/harness.sqlite
novel = repo.create_novel(title="...", recipient_name="...", dedication="...")
version = repo.create_version(novel.id)  # version 1, draft
"""

from __future__ import annotations

from app.bible.models import (
    AppUser,
    Brief,
    ChapterAttempt,
    ChapterCost,
    ChapterVersion,
    Character,
    Checkpoint,
    CheckpointStatus,
    ChronologyEvent,
    CostSummary,
    EventKind,
    Fact,
    FactSource,
    FactUsage,
    ForbiddenTerm,
    Novel,
    NovelVersion,
    Participant,
    Place,
    PolicyDecision,
    StoredValidatorResult,
    TermScope,
    VersionStatus,
)
from app.bible.repository import (
    DEFAULT_CHAPTERS,
    LOCAL_OWNER_ID,
    BibleError,
    BibleNotFoundError,
    BibleRepository,
    VersionFrozenError,
    text_hash,
    word_count,
)

__all__ = [
    "DEFAULT_CHAPTERS",
    "LOCAL_OWNER_ID",
    "AppUser",
    "BibleError",
    "BibleNotFoundError",
    "BibleRepository",
    "Brief",
    "ChapterAttempt",
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
    "VersionFrozenError",
    "VersionStatus",
    "text_hash",
    "word_count",
]
