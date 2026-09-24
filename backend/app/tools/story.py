"""The read-only story-bible tools (spec 017). Every handler only calls read methods of
`BibleRepository`; facts of kind `plan` (the planner's internal notes) are never returned."""

from __future__ import annotations

from typing import Final

from app.bible import BibleNotFoundError, BibleRepository, ChapterVersion, NovelVersion
from app.tools.base import ToolNotFoundError
from app.tools.models import (
    ChapterOutput,
    ChapterSummaryOutput,
    CharacterInfo,
    EventInfo,
    FactInfo,
    GetChapterInput,
    GetChapterSummaryInput,
    ListNovelsInput,
    ListNovelsOutput,
    ListVersionsInput,
    ListVersionsOutput,
    NovelInfo,
    PlaceInfo,
    QueryStoryBibleInput,
    QueryStoryBibleOutput,
    VersionInfo,
)

HIDDEN_FACT_KINDS: Final[frozenset[str]] = frozenset({"plan"})


def require_novel(repo: BibleRepository, novel_id: str) -> None:
    try:
        repo.get_novel(novel_id)
    except BibleNotFoundError as exc:
        raise ToolNotFoundError(str(exc)) from exc


def resolve_version(repo: BibleRepository, novel_id: str, version: int | None) -> NovelVersion:
    """`version`, or the latest one when None."""
    require_novel(repo, novel_id)
    if version is None:
        latest = repo.latest_version(novel_id)
        if latest is None:
            message = f"novel {novel_id!r} has no version yet"
            raise ToolNotFoundError(message)
        return latest
    try:
        return repo.get_version(novel_id, version)
    except BibleNotFoundError as exc:
        raise ToolNotFoundError(str(exc)) from exc


def _chapter(repo: BibleRepository, novel_id: str, version: int, chapter: int) -> ChapterVersion:
    resolve_version(repo, novel_id, version)
    row = repo.get_chapter(novel_id, version, chapter)
    if row is None:
        message = f"novel {novel_id!r} version {version} has no chapter {chapter}"
        raise ToolNotFoundError(message)
    return row


def list_novels(repo: BibleRepository, _: ListNovelsInput) -> ListNovelsOutput:
    novels: list[NovelInfo] = []
    for novel in repo.list_novels():
        latest = repo.latest_version(novel.id)
        published = repo.latest_version(novel.id, status="published")
        novels.append(
            NovelInfo(
                id=novel.id,
                title=novel.title,
                status=novel.status,
                recipient_name=novel.recipient_name,
                latest_version=latest.version if latest else None,
                latest_status=latest.status if latest else None,
                published_version=published.version if published else None,
            )
        )
    return ListNovelsOutput(novels=novels)


def list_versions(repo: BibleRepository, args: ListVersionsInput) -> ListVersionsOutput:
    require_novel(repo, args.novel_id)
    versions = [
        VersionInfo(
            version=v.version,
            parent_version=v.parent_version,
            status=v.status,
            # A draft version's `changed_chapters` is only stored when its status is set;
            # derive it from the hashes so the history is right for every version.
            changed_chapters=list(v.changed_chapters)
            if v.status != "draft"
            else repo.changed_chapters(args.novel_id, v.version),
            note=v.note,
            created_at=v.created_at,
        )
        for v in repo.list_versions(args.novel_id)
    ]
    return ListVersionsOutput(novel_id=args.novel_id, versions=versions)


def get_chapter(repo: BibleRepository, args: GetChapterInput) -> ChapterOutput:
    row = _chapter(repo, args.novel_id, args.version, args.chapter)
    return ChapterOutput(
        novel_id=row.novel_id,
        version=row.version,
        chapter=row.chapter,
        title=row.title,
        text=row.text,
        summary=row.summary,
        word_count=row.word_count,
        hash=row.hash,
    )


def get_chapter_summary(
    repo: BibleRepository, args: GetChapterSummaryInput
) -> ChapterSummaryOutput:
    version = resolve_version(repo, args.novel_id, args.version).version
    row = _chapter(repo, args.novel_id, version, args.chapter)
    return ChapterSummaryOutput(
        novel_id=row.novel_id,
        version=row.version,
        chapter=row.chapter,
        title=row.title,
        summary=row.summary,
    )


def _matches(query: str | None, *fields: str | None) -> bool:
    if query is None:
        return True
    needle = query.casefold()
    return any(needle in (f or "").casefold() for f in fields)


def query_story_bible(repo: BibleRepository, args: QueryStoryBibleInput) -> QueryStoryBibleOutput:
    require_novel(repo, args.novel_id)
    novel_id, q = args.novel_id, args.query
    out = QueryStoryBibleOutput(novel_id=novel_id, kind=args.kind)
    if args.kind == "characters":
        characters = [
            CharacterInfo(
                id=c.id,
                name=c.name,
                role=c.role,
                birth_date=c.birth_date,
                description=c.description,
            )
            for c in repo.list_characters(novel_id)
            if _matches(q, c.name, c.role, c.description)
        ]
        return out.model_copy(update={"characters": characters})
    if args.kind == "places":
        places = [
            PlaceInfo(id=p.id, name=p.name, description=p.description)
            for p in repo.list_places(novel_id)
            if _matches(q, p.name, p.description)
        ]
        return out.model_copy(update={"places": places})
    if args.kind == "facts":
        latest = repo.latest_version(novel_id)
        facts = [
            FactInfo(
                key=f.key,
                value=f.value,
                kind=f.kind,
                mandatory=f.mandatory,
                chapters=repo.chapters_using_fact(f.id, version=latest.version) if latest else [],
            )
            for f in repo.list_facts(novel_id)
            if f.kind not in HIDDEN_FACT_KINDS and _matches(q, f.key, f.value, f.kind)
        ]
        return out.model_copy(update={"facts": facts})
    names = {c.id: c.name for c in repo.list_characters(novel_id)}
    places_by_id = {p.id: p.name for p in repo.list_places(novel_id)}
    events = []
    for e in repo.list_events(novel_id):
        who = [names.get(p.character_id, p.character_id) for p in e.participants]
        place = places_by_id.get(e.place_id) if e.place_id else None
        if not _matches(q, e.description, place, e.story_date, *who):
            continue
        events.append(
            EventInfo(
                id=e.id,
                seq=e.seq,
                story_date=e.story_date,
                chapter=e.chapter,
                scene=e.scene,
                place=place,
                description=e.description,
                kind=e.kind,
                participants=who,
            )
        )
    return out.model_copy(update={"events": events})


__all__ = [
    "HIDDEN_FACT_KINDS",
    "get_chapter",
    "get_chapter_summary",
    "list_novels",
    "list_versions",
    "query_story_bible",
    "require_novel",
    "resolve_version",
]
