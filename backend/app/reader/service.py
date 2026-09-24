"""Read side of the reader (spec 014): K1 records turned into the reader's shapes.

Shared by the HTTP routes and the PDF export, so the web and the PDF say the same thing
about which chapters changed and where each character appears.
"""

from __future__ import annotations

import re

from app.bible import BibleNotFoundError, BibleRepository, ChapterVersion, Novel
from app.reader.models import (
    BibleEntry,
    ChapterDetail,
    ChapterEntry,
    ChapterIndex,
    FactRef,
    NovelDetail,
    NovelSummary,
    StoryBible,
    VersionInfo,
)


def current_version(repo: BibleRepository, novel_id: str) -> int | None:
    """The version the reader opens: the latest published (architecture, "The reader")."""
    latest = repo.latest_version(novel_id, status="published")
    return None if latest is None else latest.version


def _summary(repo: BibleRepository, novel: Novel) -> NovelSummary:
    return NovelSummary(
        id=novel.id,
        title=novel.title,
        recipient=novel.recipient_name,
        status=novel.status,
        current_version=current_version(repo, novel.id),
    )


def list_novels(repo: BibleRepository) -> list[NovelSummary]:
    return [_summary(repo, novel) for novel in repo.list_novels()]


def list_versions(repo: BibleRepository, novel_id: str) -> list[VersionInfo]:
    repo.get_novel(novel_id)
    return [
        VersionInfo(
            version=v.version,
            status=v.status,
            parent=v.parent_version,
            changed_chapters=_changed(repo, novel_id, v.version),
            note=v.note,
            created_at=v.created_at,
        )
        for v in repo.list_versions(novel_id)
    ]


def novel_detail(repo: BibleRepository, novel_id: str) -> NovelDetail:
    novel = repo.get_novel(novel_id)
    return NovelDetail(
        id=novel.id,
        title=novel.title,
        dedication=novel.dedication,
        recipient=novel.recipient_name,
        status=novel.status,
        current_version=current_version(repo, novel_id),
        versions=list_versions(repo, novel_id),
    )


def _changed(repo: BibleRepository, novel_id: str, version: int) -> list[int]:
    """R06. The stored list once the status was set; computed from hashes before that."""
    stored = repo.get_version(novel_id, version)
    if stored.changed_chapters or stored.status != "draft":
        return list(stored.changed_chapters)
    return repo.changed_chapters(novel_id, version)


def changed_vs_parent(repo: BibleRepository, novel_id: str, version: int) -> set[int]:
    """Chapters marked "modificado": only a version with a parent has changes to show."""
    if repo.get_version(novel_id, version).parent_version is None:
        return set()
    return set(repo.changed_chapters(novel_id, version))


def chapter_index(repo: BibleRepository, novel_id: str, version: int) -> ChapterIndex:
    info = repo.get_version(novel_id, version)
    changed = changed_vs_parent(repo, novel_id, version)
    return ChapterIndex(
        novel_id=novel_id,
        version=version,
        status=info.status,
        parent=info.parent_version,
        chapters=[
            ChapterEntry(
                n=c.chapter,
                title=chapter_title(c),
                words=c.word_count,
                changed_vs_parent=c.chapter in changed,
            )
            for c in repo.list_chapters(novel_id, version)
        ],
    )


def chapter_title(chapter: ChapterVersion) -> str:
    return chapter.title.strip() or f"Capítulo {chapter.chapter}"


def chapter_detail(repo: BibleRepository, novel_id: str, version: int, n: int) -> ChapterDetail:
    chapters = repo.list_chapters(novel_id, version)
    numbers = [c.chapter for c in chapters]
    found = next((c for c in chapters if c.chapter == n), None)
    if found is None:
        message = f"no chapter {n} in version {version} of {novel_id!r}"
        raise BibleNotFoundError(message)
    position = numbers.index(n)
    facts = repo.facts_used_in_chapter(novel_id, n, version=version)
    return ChapterDetail(
        novel_id=novel_id,
        version=version,
        n=n,
        title=chapter_title(found),
        text=found.text,
        words=found.word_count,
        changed=n in changed_vs_parent(repo, novel_id, version),
        facts=[FactRef(key=f.key, value=f.value, kind=f.kind) for f in facts],
        previous=numbers[position - 1] if position > 0 else None,
        next=numbers[position + 1] if position + 1 < len(numbers) else None,
    )


def _name_pattern(name: str) -> re.Pattern[str] | None:
    clean = name.strip()
    if len(clean) < 2:
        return None
    return re.compile(rf"(?<!\w){re.escape(clean)}(?!\w)", re.IGNORECASE)


def _appearances(
    repo: BibleRepository,
    chapters: list[ChapterVersion],
    *,
    name: str,
    fact_id: int | None,
    version: int,
) -> list[int]:
    """R03: from fact usage first; a whole-word search of the name when there is none."""
    if fact_id is not None:
        used = repo.chapters_using_fact(fact_id, version=version)
        if used:
            return used
    pattern = _name_pattern(name)
    if pattern is None:
        return []
    return [c.chapter for c in chapters if pattern.search(c.text)]


def story_bible(repo: BibleRepository, novel_id: str, version: int | None = None) -> StoryBible:
    repo.get_novel(novel_id)
    target = version if version is not None else current_version(repo, novel_id)
    if target is None:
        latest = repo.latest_version(novel_id)
        target = None if latest is None else latest.version
    chapters = repo.list_chapters(novel_id, target) if target is not None else []

    def where(name: str, fact_id: int | None) -> list[int]:
        if target is None:
            return []
        return _appearances(repo, chapters, name=name, fact_id=fact_id, version=target)

    return StoryBible(
        novel_id=novel_id,
        version=target,
        characters=[
            BibleEntry(
                id=c.id,
                kind="character",
                name=c.name,
                role=c.role,
                description=c.description,
                chapters=where(c.name, c.fact_id),
            )
            for c in repo.list_characters(novel_id)
        ],
        places=[
            BibleEntry(
                id=p.id,
                kind="place",
                name=p.name,
                description=p.description,
                chapters=where(p.name, p.fact_id),
            )
            for p in repo.list_places(novel_id)
        ],
    )


__all__ = [
    "changed_vs_parent",
    "chapter_detail",
    "chapter_index",
    "chapter_title",
    "current_version",
    "list_novels",
    "list_versions",
    "novel_detail",
    "story_bible",
]
