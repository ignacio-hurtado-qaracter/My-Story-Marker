"""Contract K1: `BibleRepository`, the only code that touches the authoritative database.

Spec 005, spec 004 decisions D1, D2, D6. Three rules the methods enforce:

* **Nothing is deleted.** A regeneration is a new `novel_version` with a `parent_version`;
  its chapters are new `chapter_version` rows. A published or blocked version's chapters
  cannot be overwritten (`VersionFrozenError`).
* **A fact has one value.** `update_fact_value` changes it in place (D2); which scenes used
  it is recorded per scene in `fact_usage` and chapters are derived from that.
* **Every chapter text carries its SHA-256.** "Changed" between two versions is a hash
  difference (spec 004 decision 27), computed by `changed_chapters`.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Self

from pydantic import JsonValue, TypeAdapter

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
from app.commons.config import get_settings
from app.commons.db.authoritative import open_authoritative
from app.commons.db.connection import transaction
from app.commons.observability.traced import LlmCallRecord

DEFAULT_CHAPTERS: Final[int] = 10
"""Spec 004 D3: a novel has ten chapters."""

LOCAL_OWNER_ID: Final[str] = "local"
"""Spec 018: the built-in owner (migration 1700) of every novel created without one."""

DEFAULT_OWNER_ENV: Final[str] = "STORY_MAKER_USER"
"""Spec 018: the email of a registered user who owns what the local CLI creates."""

_JSON_OBJECT: Final[TypeAdapter[dict[str, JsonValue]]] = TypeAdapter(dict[str, JsonValue])


_ID_QUERIES: Final[dict[str, str]] = {
    "character": "select id from character where novel_id = ?",
    "place": "select id from place where novel_id = ?",
}


class BibleError(Exception):
    """Base of the repository's own errors."""


class BibleNotFoundError(BibleError):
    """The novel, version, fact or row asked for does not exist."""


class VersionFrozenError(BibleError):
    """A published or blocked version is never overwritten (R07)."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def text_hash(text: str) -> str:
    """SHA-256 hex of a chapter text, UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def word_count(text: str) -> int:
    return len(text.split())


def _opt_int(value: object) -> int | None:
    return None if value is None else int(str(value))


def _opt_str(value: object) -> str | None:
    return None if value is None else str(value)


class BibleRepository:
    """K1. Construct with a connection from `open_authoritative`, or with `open()`."""

    def __init__(self, connection: sqlite3.Connection, *, owner_id: str | None = None) -> None:
        self._db = connection
        self._owner = owner_id

    def scoped_to(self, owner_id: str) -> BibleRepository:
        """Spec 018: a view on the same connection that only sees `owner_id`'s novels.

        `get_novel` of another owner's novel raises `BibleNotFoundError`, exactly as for a
        missing one; `list_novels` and `list_policy_decisions` omit other owners' rows.
        Every other method is unchanged, so a caller resolves the novel first (the reader
        and the tools do). Closing the view closes the shared connection."""
        return BibleRepository(self._db, owner_id=owner_id)

    @property
    def owner_id(self) -> str | None:
        """The owner this view is scoped to; None for the unscoped repository."""
        return self._owner

    @classmethod
    def open(cls, path: Path | str | None = None, *, check_same_thread: bool = True) -> Self:
        """Open `path`, or `HARNESS_DB` (default `data/harness.sqlite` at the repo root).

        `check_same_thread=False` for a repository opened in one thread and used in
        another, one at a time (the reader's per-request dependency)."""
        target = path if path is not None else get_settings().harness_db_path
        return cls(open_authoritative(target, check_same_thread=check_same_thread))

    @property
    def connection(self) -> sqlite3.Connection:
        return self._db

    def close(self) -> None:
        self._db.close()

    @contextmanager
    def transaction(self) -> Iterator[Self]:
        """One atomic unit over several repository calls (`BEGIN IMMEDIATE` ... `COMMIT`,
        or a SAVEPOINT when already inside one). Methods that open their own transaction
        nest inside it, so everything commits or rolls back together."""
        with transaction(self._db):
            yield self

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ----------------------------------------------------------------------------------
    # Novel
    # ----------------------------------------------------------------------------------

    def create_novel(
        self,
        *,
        novel_id: str | None = None,
        title: str | None = None,
        dedication: str | None = None,
        recipient_name: str | None = None,
        session_id: str | None = None,
        owner_id: str | None = None,
    ) -> Novel:
        """A new novel. Its Langfuse session id is the novel id unless given (O01).

        Spec 018: its owner is `owner_id`, else this view's owner, else the default owner
        (`STORY_MAKER_USER`'s user, or `local`)."""
        identifier = novel_id or f"nov-{uuid.uuid4().hex[:12]}"
        owner = owner_id or self._owner or self.default_owner_id()
        now = _now()
        self._db.execute(
            "insert into novel (id, session_id, title, dedication, recipient_name, status, "
            "created_at, updated_at, owner_id) values (?, ?, ?, ?, ?, 'draft', ?, ?, ?)",
            (
                identifier,
                session_id or identifier,
                title,
                dedication,
                recipient_name,
                now,
                now,
                owner,
            ),
        )
        return self.get_novel(identifier)

    def get_novel(self, novel_id: str) -> Novel:
        row = self._db.execute(
            "select * from novel where id = ? and (? is null or owner_id = ?)",
            (novel_id, self._owner, self._owner),
        ).fetchone()
        if row is None:
            message = f"no novel {novel_id!r}"
            raise BibleNotFoundError(message)
        return Novel.model_validate(dict(row))

    def list_novels(self) -> list[Novel]:
        rows = self._db.execute(
            "select * from novel where (? is null or owner_id = ?) order by created_at",
            (self._owner, self._owner),
        ).fetchall()
        return [Novel.model_validate(dict(row)) for row in rows]

    # ----------------------------------------------------------------------------------
    # Users (spec 018)
    # ----------------------------------------------------------------------------------

    def create_user(self, *, email: str, password_hash: str) -> AppUser:
        """A new login. `email` is stored as given (callers normalise it); a duplicate
        raises `sqlite3.IntegrityError`."""
        identifier = f"usr-{uuid.uuid4().hex[:12]}"
        self._db.execute(
            "insert into app_user (id, email, password_hash, created_at) values (?, ?, ?, ?)",
            (identifier, email, password_hash, _now()),
        )
        return self.get_user(identifier)

    def get_user(self, user_id: str) -> AppUser:
        row = self._db.execute("select * from app_user where id = ?", (user_id,)).fetchone()
        if row is None:
            message = f"no user {user_id!r}"
            raise BibleNotFoundError(message)
        return AppUser.model_validate(dict(row))

    def find_user_by_email(self, email: str) -> AppUser | None:
        row = self._db.execute("select * from app_user where email = ?", (email,)).fetchone()
        return None if row is None else AppUser.model_validate(dict(row))

    def default_owner_id(self) -> str:
        """`STORY_MAKER_USER`'s user id when that email is registered, else `local`."""
        email = os.environ.get(DEFAULT_OWNER_ENV, "").strip().casefold()
        if email:
            user = self.find_user_by_email(email)
            if user is not None:
                return user.id
        return LOCAL_OWNER_ID

    def update_novel(
        self,
        novel_id: str,
        *,
        title: str | None = None,
        dedication: str | None = None,
        recipient_name: str | None = None,
        status: str | None = None,
    ) -> Novel:
        """Set the given fields; None leaves a field unchanged."""
        current = self.get_novel(novel_id)
        self._db.execute(
            "update novel set title = ?, dedication = ?, recipient_name = ?, status = ?, "
            "updated_at = ? where id = ?",
            (
                title if title is not None else current.title,
                dedication if dedication is not None else current.dedication,
                recipient_name if recipient_name is not None else current.recipient_name,
                status if status is not None else current.status,
                _now(),
                novel_id,
            ),
        )
        return self.get_novel(novel_id)

    # ----------------------------------------------------------------------------------
    # Brief
    # ----------------------------------------------------------------------------------

    def save_brief(
        self,
        novel_id: str,
        data: Mapping[str, JsonValue],
        *,
        valid: bool,
        schema_version: str = "1",
    ) -> Brief:
        """Insert or replace the novel's brief (one per novel; the facts are the history)."""
        now = _now()
        self._db.execute(
            "insert into brief (novel_id, data_json, schema_version, valid, created_at, "
            "updated_at) values (?, ?, ?, ?, ?, ?) on conflict (novel_id) do update set "
            "data_json = excluded.data_json, schema_version = excluded.schema_version, "
            "valid = excluded.valid, updated_at = excluded.updated_at",
            (
                novel_id,
                json.dumps(dict(data), ensure_ascii=False, sort_keys=True),
                schema_version,
                int(valid),
                now,
                now,
            ),
        )
        brief = self.get_brief(novel_id)
        if brief is None:  # pragma: no cover - just written
            message = f"brief of {novel_id!r} vanished"
            raise BibleError(message)
        return brief

    def get_brief(self, novel_id: str) -> Brief | None:
        row = self._db.execute("select * from brief where novel_id = ?", (novel_id,)).fetchone()
        if row is None:
            return None
        return Brief(
            novel_id=str(row["novel_id"]),
            data=_JSON_OBJECT.validate_json(str(row["data_json"])),
            schema_version=str(row["schema_version"]),
            valid=bool(row["valid"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    # ----------------------------------------------------------------------------------
    # Facts and their usage
    # ----------------------------------------------------------------------------------

    def add_fact(
        self,
        novel_id: str,
        *,
        key: str,
        value: str,
        kind: str,
        source: FactSource,
        mandatory: bool = False,
    ) -> Fact:
        """A new fact; `key` is unique per novel (e.g. `pet.name`)."""
        now = _now()
        cursor = self._db.execute(
            "insert into fact (novel_id, key, value, kind, source, mandatory, created_at, "
            "updated_at) values (?, ?, ?, ?, ?, ?, ?, ?)",
            (novel_id, key, value, kind, source, int(mandatory), now, now),
        )
        return self.get_fact(int(cursor.lastrowid or 0))

    def get_fact(self, fact_id: int) -> Fact:
        row = self._db.execute("select * from fact where id = ?", (fact_id,)).fetchone()
        if row is None:
            message = f"no fact {fact_id}"
            raise BibleNotFoundError(message)
        return _fact(row)

    def find_fact(self, novel_id: str, key: str) -> Fact | None:
        row = self._db.execute(
            "select * from fact where novel_id = ? and key = ?", (novel_id, key)
        ).fetchone()
        return None if row is None else _fact(row)

    def list_facts(
        self, novel_id: str, *, mandatory: bool | None = None, kind: str | None = None
    ) -> list[Fact]:
        sql = "select * from fact where novel_id = ?"
        params: list[object] = [novel_id]
        if mandatory is not None:
            sql += " and mandatory = ?"
            params.append(int(mandatory))
        if kind is not None:
            sql += " and kind = ?"
            params.append(kind)
        rows = self._db.execute(sql + " order by id", params).fetchall()
        return [_fact(row) for row in rows]

    def update_fact_value(self, fact_id: int, new_value: str) -> Fact:
        """D2: a fact never has two versions. The value changes in place."""
        self.get_fact(fact_id)
        self._db.execute(
            "update fact set value = ?, updated_at = ? where id = ?", (new_value, _now(), fact_id)
        )
        return self.get_fact(fact_id)

    def record_fact_usage(
        self, fact_id: int, *, chapter: int, scene: int, version: int = 1
    ) -> None:
        """Idempotent: the same (fact, version, chapter, scene) is recorded once."""
        self._db.execute(
            "insert or ignore into fact_usage (fact_id, version, chapter, scene, created_at) "
            "values (?, ?, ?, ?, ?)",
            (fact_id, version, chapter, scene, _now()),
        )

    def fact_usages(self, fact_id: int, *, version: int | None = None) -> list[FactUsage]:
        sql = "select fact_id, version, chapter, scene from fact_usage where fact_id = ?"
        params: list[object] = [fact_id]
        if version is not None:
            sql += " and version = ?"
            params.append(version)
        rows = self._db.execute(sql + " order by version, chapter, scene", params).fetchall()
        return [FactUsage.model_validate(dict(row)) for row in rows]

    def chapters_using_fact(self, fact_id: int, *, version: int | None = None) -> list[int]:
        """M01: the chapters that use a fact, derived from its per-scene usage rows."""
        return sorted({usage.chapter for usage in self.fact_usages(fact_id, version=version)})

    def facts_used_in_chapter(self, novel_id: str, chapter: int, *, version: int) -> list[Fact]:
        rows = self._db.execute(
            "select distinct f.* from fact f join fact_usage u on u.fact_id = f.id "
            "where f.novel_id = ? and u.chapter = ? and u.version = ? order by f.id",
            (novel_id, chapter, version),
        ).fetchall()
        return [_fact(row) for row in rows]

    # ----------------------------------------------------------------------------------
    # Characters, places, chronology
    # ----------------------------------------------------------------------------------

    def add_character(
        self,
        novel_id: str,
        *,
        name: str,
        character_id: str | None = None,
        role: str = "",
        birth_date: str | None = None,
        description: str = "",
        fact_id: int | None = None,
    ) -> Character:
        """`birth_date` is ISO `YYYY-MM-DD` or None. Ids default to `c1`, `c2`, ..."""
        identifier = character_id or self._next_id("character", novel_id, "c")
        self._db.execute(
            "insert into character (id, novel_id, name, role, birth_date, description, fact_id) "
            "values (?, ?, ?, ?, ?, ?, ?)",
            (identifier, novel_id, name, role, birth_date, description, fact_id),
        )
        return self._character(novel_id, identifier)

    def list_characters(self, novel_id: str) -> list[Character]:
        rows = self._db.execute(
            "select * from character where novel_id = ? order by rowid", (novel_id,)
        ).fetchall()
        return [Character.model_validate(dict(row)) for row in rows]

    def add_place(
        self,
        novel_id: str,
        *,
        name: str,
        place_id: str | None = None,
        description: str = "",
        fact_id: int | None = None,
    ) -> Place:
        identifier = place_id or self._next_id("place", novel_id, "p")
        self._db.execute(
            "insert into place (id, novel_id, name, description, fact_id) values (?, ?, ?, ?, ?)",
            (identifier, novel_id, name, description, fact_id),
        )
        row = self._db.execute(
            "select * from place where novel_id = ? and id = ?", (novel_id, identifier)
        ).fetchone()
        return Place.model_validate(dict(row))

    def list_places(self, novel_id: str) -> list[Place]:
        rows = self._db.execute(
            "select * from place where novel_id = ? order by rowid", (novel_id,)
        ).fetchall()
        return [Place.model_validate(dict(row)) for row in rows]

    def add_event(
        self,
        novel_id: str,
        *,
        seq: int,
        description: str = "",
        story_date: str | None = None,
        place_id: str | None = None,
        participants: Sequence[str] | Mapping[str, int | None] = (),
        chapter: int | None = None,
        scene: int | None = None,
        kind: EventKind = "normal",
        event_id: str | None = None,
    ) -> ChronologyEvent:
        """M02. `participants` is a list of character ids, or a mapping from character id to
        the age the text declares at this event (None when the text states none)."""
        identifier = event_id or f"e{seq}"
        ages: Mapping[str, int | None] = (
            participants if isinstance(participants, Mapping) else dict.fromkeys(participants)
        )
        with transaction(self._db):
            self._db.execute(
                "insert into chronology_event (id, novel_id, seq, story_date, chapter, scene, "
                "place_id, description, kind) values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    identifier,
                    novel_id,
                    seq,
                    story_date,
                    chapter,
                    scene,
                    place_id,
                    description,
                    kind,
                ),
            )
            for character_id, age in ages.items():
                self._db.execute(
                    "insert into event_participant (novel_id, event_id, character_id, "
                    "age_at_event) values (?, ?, ?, ?)",
                    (novel_id, identifier, character_id, age),
                )
        return next(event for event in self.list_events(novel_id) if event.id == identifier)

    def list_events(self, novel_id: str) -> list[ChronologyEvent]:
        """Events in `seq` order, each with its participants."""
        participants: dict[str, list[Participant]] = {}
        for row in self._db.execute(
            "select event_id, character_id, age_at_event from event_participant "
            "where novel_id = ? order by rowid",
            (novel_id,),
        ).fetchall():
            participants.setdefault(str(row["event_id"]), []).append(
                Participant(
                    character_id=str(row["character_id"]),
                    age_at_event=_opt_int(row["age_at_event"]),
                )
            )
        rows = self._db.execute(
            "select * from chronology_event where novel_id = ? order by seq", (novel_id,)
        ).fetchall()
        return [
            ChronologyEvent.model_validate(
                {**dict(row), "participants": tuple(participants.get(str(row["id"]), []))}
            )
            for row in rows
        ]

    def chronology_json(self, novel_id: str) -> dict[str, JsonValue]:
        """The chronology export consumed by the Lean block (B8), in exactly the K1 format:

        {"novel_id", "characters": [{"id","name","birth_date"}], "places": [{"id","name"}],
         "events": [{"id","seq","story_date","place_id","participants","kind",
                     "declared_ages","chapter","description"}]}
        """
        characters: list[JsonValue] = [
            {"id": c.id, "name": c.name, "birth_date": c.birth_date}
            for c in self.list_characters(novel_id)
        ]
        places: list[JsonValue] = [{"id": p.id, "name": p.name} for p in self.list_places(novel_id)]
        events: list[JsonValue] = []
        for event in self.list_events(novel_id):
            declared: dict[str, JsonValue] = {
                p.character_id: p.age_at_event
                for p in event.participants
                if p.age_at_event is not None
            }
            events.append(
                {
                    "id": event.id,
                    "seq": event.seq,
                    "story_date": event.story_date,
                    "place_id": event.place_id,
                    "participants": [p.character_id for p in event.participants],
                    "kind": event.kind,
                    "declared_ages": declared,
                    "chapter": event.chapter,
                    "description": event.description,
                }
            )
        return {"novel_id": novel_id, "characters": characters, "places": places, "events": events}

    # ----------------------------------------------------------------------------------
    # Versions and chapters
    # ----------------------------------------------------------------------------------

    def create_version(
        self,
        novel_id: str,
        *,
        parent: int | None = None,
        note: str = "",
        trace_id: str | None = None,
        copy_chapters: bool = True,
    ) -> NovelVersion:
        """A new draft version numbered after the latest. With a `parent` and
        `copy_chapters`, the parent's chapters and checkpoints are copied as the starting
        point (see `create_version_from`)."""
        return self._new_version(
            novel_id, parent, note=note, trace_id=trace_id, copy=copy_chapters, skip=set()
        )

    def create_version_from(
        self,
        novel_id: str,
        parent: int,
        *,
        copy_chapters_except: set[int] | frozenset[int] = frozenset(),
        note: str = "",
        trace_id: str | None = None,
    ) -> NovelVersion:
        """TLC CE4 / `change_fact`: a new draft child of `parent` holding copies of every
        parent chapter row **and its checkpoint** except those in `copy_chapters_except`,
        all in one transaction. The parent's rows are only read, never touched, so the
        previous version survives the regeneration whatever happens next."""
        return self._new_version(
            novel_id,
            parent,
            note=note,
            trace_id=trace_id,
            copy=True,
            skip=set(copy_chapters_except),
        )

    def _new_version(
        self,
        novel_id: str,
        parent: int | None,
        *,
        note: str,
        trace_id: str | None,
        copy: bool,
        skip: set[int],
    ) -> NovelVersion:
        self.get_novel(novel_id)
        chapters: list[int] = []
        if parent is not None:
            self.get_version(novel_id, parent)
            if copy:
                chapters = [
                    c.chapter for c in self.list_chapters(novel_id, parent) if c.chapter not in skip
                ]
        now = _now()
        with transaction(self._db):
            row = self._db.execute(
                "select coalesce(max(version), 0) + 1 from novel_version where novel_id = ?",
                (novel_id,),
            ).fetchone()
            number = int(row[0])
            self._db.execute(
                "insert into novel_version (novel_id, version, parent_version, status, "
                "changed_chapters, note, trace_id, created_at, updated_at) "
                "values (?, ?, ?, 'draft', '[]', ?, ?, ?, ?)",
                (novel_id, number, parent, note, trace_id, now, now),
            )
            for chapter in chapters:
                self._db.execute(
                    "insert into chapter_version (novel_id, version, chapter, title, text, hash, "
                    "summary, word_count, created_at) select novel_id, ?, chapter, title, text, "
                    "hash, summary, word_count, ? from chapter_version "
                    "where novel_id = ? and version = ? and chapter = ?",
                    (number, now, novel_id, parent, chapter),
                )
                self._db.execute(
                    "insert into checkpoint (novel_id, version, chapter, status, detail, "
                    "updated_at) select novel_id, ?, chapter, status, detail, ? from checkpoint "
                    "where novel_id = ? and version = ? and chapter = ?",
                    (number, now, novel_id, parent, chapter),
                )
        return self.get_version(novel_id, number)

    def get_version(self, novel_id: str, version: int) -> NovelVersion:
        row = self._db.execute(
            "select * from novel_version where novel_id = ? and version = ?", (novel_id, version)
        ).fetchone()
        if row is None:
            message = f"no version {version} of {novel_id!r}"
            raise BibleNotFoundError(message)
        return _version(row)

    def list_versions(self, novel_id: str) -> list[NovelVersion]:
        rows = self._db.execute(
            "select * from novel_version where novel_id = ? order by version", (novel_id,)
        ).fetchall()
        return [_version(row) for row in rows]

    def latest_version(
        self, novel_id: str, *, status: VersionStatus | None = None
    ) -> NovelVersion | None:
        versions = [v for v in self.list_versions(novel_id) if status is None or v.status == status]
        return versions[-1] if versions else None

    def set_version_status(
        self,
        novel_id: str,
        version: int,
        status: VersionStatus,
        *,
        note: str | None = None,
        repair_rounds: int | None = None,
    ) -> NovelVersion:
        """Record which chapters changed against the parent and set the status, in one
        statement. `repair_rounds` (TLC CE4) is written in that same statement, so a
        `blocked` version never exists without the rounds that led to it. Publishing
        freezes the version's chapters; a published version never changes status."""
        current = self.get_version(novel_id, version)
        if current.status == "published" and status != "published":
            message = f"version {version} of {novel_id!r} is published and cannot change status"
            raise VersionFrozenError(message)
        changed = self.changed_chapters(novel_id, version)
        self._db.execute(
            "update novel_version set status = ?, changed_chapters = ?, note = ?, "
            "repair_rounds = ?, updated_at = ? where novel_id = ? and version = ?",
            (
                status,
                json.dumps(changed),
                note if note is not None else current.note,
                repair_rounds if repair_rounds is not None else current.repair_rounds,
                _now(),
                novel_id,
                version,
            ),
        )
        return self.get_version(novel_id, version)

    def block_version(
        self, novel_id: str, version: int, *, repair_rounds: int, note: str = ""
    ) -> NovelVersion:
        """TLC CE4: `blocked` and its repair rounds, atomically."""
        return self.set_version_status(
            novel_id, version, "blocked", note=note, repair_rounds=repair_rounds
        )

    def changed_chapters(self, novel_id: str, version: int) -> list[int]:
        """R06: chapters whose hash differs from the parent version's (all, without one)."""
        current = self.get_version(novel_id, version)
        mine = {c.chapter: c.hash for c in self.list_chapters(novel_id, version)}
        if current.parent_version is None:
            return sorted(mine)
        theirs = {c.chapter: c.hash for c in self.list_chapters(novel_id, current.parent_version)}
        return sorted(ch for ch in set(mine) | set(theirs) if mine.get(ch) != theirs.get(ch))

    def save_chapter_version(
        self,
        novel_id: str,
        version: int,
        chapter: int,
        *,
        text: str,
        title: str = "",
        summary: str = "",
    ) -> ChapterVersion:
        """Upsert one chapter's text and hash (TLC CE3: unique per novel, version and
        chapter). Refused once the version is published (R07); a blocked version can still
        be repaired. Keep a rejected text with `record_chapter_attempt` before overwriting."""
        self._require_writable(novel_id, version)
        self._upsert_chapter(novel_id, version, chapter, text=text, title=title, summary=summary)
        return self._chapter(novel_id, version, chapter)

    def save_chapter_and_checkpoint(
        self,
        novel_id: str,
        version: int,
        chapter: int,
        *,
        text: str,
        title: str = "",
        summary: str = "",
        detail: str = "",
    ) -> ChapterVersion:
        """TLC CE1: the chapter text and its `complete` checkpoint in ONE transaction, so a
        crash can never leave a completed checkpoint without its text, or the reverse."""
        self._require_writable(novel_id, version)
        with transaction(self._db):
            self._upsert_chapter(
                novel_id, version, chapter, text=text, title=title, summary=summary
            )
            self._db.execute(
                "insert into checkpoint (novel_id, version, chapter, status, detail, updated_at) "
                "values (?, ?, ?, 'complete', ?, ?) on conflict (novel_id, version, chapter) do "
                "update set status = excluded.status, detail = excluded.detail, "
                "updated_at = excluded.updated_at",
                (novel_id, version, chapter, detail, _now()),
            )
        return self._chapter(novel_id, version, chapter)

    def record_chapter_attempt(
        self, novel_id: str, version: int, chapter: int, *, text: str, reason: str = ""
    ) -> ChapterAttempt:
        """TLC CE3 / D6: keep a rejected chapter text. Attempts are numbered 1, 2, ..."""
        self.get_version(novel_id, version)
        with transaction(self._db):
            row = self._db.execute(
                "select coalesce(max(attempt), 0) + 1 from chapter_attempt "
                "where novel_id = ? and version = ? and chapter = ?",
                (novel_id, version, chapter),
            ).fetchone()
            attempt = int(row[0])
            self._db.execute(
                "insert into chapter_attempt (novel_id, version, chapter, attempt, text, hash, "
                "reason, created_at) values (?, ?, ?, ?, ?, ?, ?, ?)",
                (novel_id, version, chapter, attempt, text, text_hash(text), reason, _now()),
            )
        return self.list_chapter_attempts(novel_id, version, chapter)[-1]

    def list_chapter_attempts(
        self, novel_id: str, version: int, chapter: int
    ) -> list[ChapterAttempt]:
        rows = self._db.execute(
            "select * from chapter_attempt where novel_id = ? and version = ? and chapter = ? "
            "order by attempt",
            (novel_id, version, chapter),
        ).fetchall()
        return [ChapterAttempt.model_validate(dict(row)) for row in rows]

    def count_chapter_attempts(self, novel_id: str, version: int, chapter: int) -> int:
        """TLC CE2: how many chapter-close validation runs this chapter has had, derived
        from the persisted `validator_result` rows (one `run_id` per `run_point` call), so
        the retry bound survives a restart."""
        row = self._db.execute(
            "select count(distinct coalesce(run_id, cast(id as text))) from validator_result "
            "where novel_id = ? and version = ? and chapter = ? and point = 'chapter_close'",
            (novel_id, version, chapter),
        ).fetchone()
        return int(row[0])

    def _require_writable(self, novel_id: str, version: int) -> None:
        if self.get_version(novel_id, version).status == "published":
            message = f"version {version} of {novel_id!r} is published and frozen"
            raise VersionFrozenError(message)

    def _chapter(self, novel_id: str, version: int, chapter: int) -> ChapterVersion:
        found = self.get_chapter(novel_id, version, chapter)
        if found is None:  # pragma: no cover - just written
            message = f"chapter {chapter} of version {version} vanished"
            raise BibleError(message)
        return found

    def _upsert_chapter(
        self, novel_id: str, version: int, chapter: int, *, text: str, title: str, summary: str
    ) -> None:
        self._db.execute(
            "insert into chapter_version (novel_id, version, chapter, title, text, hash, summary, "
            "word_count, created_at) values (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "on conflict (novel_id, version, chapter) do update set title = excluded.title, "
            "text = excluded.text, hash = excluded.hash, summary = excluded.summary, "
            "word_count = excluded.word_count, created_at = excluded.created_at",
            (
                novel_id,
                version,
                chapter,
                title,
                text,
                text_hash(text),
                summary,
                word_count(text),
                _now(),
            ),
        )

    def get_chapter(self, novel_id: str, version: int, chapter: int) -> ChapterVersion | None:
        row = self._db.execute(
            "select * from chapter_version where novel_id = ? and version = ? and chapter = ?",
            (novel_id, version, chapter),
        ).fetchone()
        return None if row is None else ChapterVersion.model_validate(dict(row))

    def list_chapters(self, novel_id: str, version: int) -> list[ChapterVersion]:
        rows = self._db.execute(
            "select * from chapter_version where novel_id = ? and version = ? order by chapter",
            (novel_id, version),
        ).fetchall()
        return [ChapterVersion.model_validate(dict(row)) for row in rows]

    # ----------------------------------------------------------------------------------
    # Checkpoints (M04)
    # ----------------------------------------------------------------------------------

    def set_checkpoint(
        self,
        novel_id: str,
        version: int,
        chapter: int,
        status: CheckpointStatus,
        *,
        detail: str = "",
    ) -> Checkpoint:
        self._db.execute(
            "insert into checkpoint (novel_id, version, chapter, status, detail, updated_at) "
            "values (?, ?, ?, ?, ?, ?) on conflict (novel_id, version, chapter) do update set "
            "status = excluded.status, detail = excluded.detail, updated_at = excluded.updated_at",
            (novel_id, version, chapter, status, detail, _now()),
        )
        row = self._db.execute(
            "select * from checkpoint where novel_id = ? and version = ? and chapter = ?",
            (novel_id, version, chapter),
        ).fetchone()
        return Checkpoint.model_validate(dict(row))

    def list_checkpoints(self, novel_id: str, version: int) -> list[Checkpoint]:
        rows = self._db.execute(
            "select * from checkpoint where novel_id = ? and version = ? order by chapter",
            (novel_id, version),
        ).fetchall()
        return [Checkpoint.model_validate(dict(row)) for row in rows]

    def first_incomplete_chapter(
        self, novel_id: str, version: int, *, total_chapters: int = DEFAULT_CHAPTERS
    ) -> int | None:
        """The chapter to resume at: the lowest of 1..total not `complete`; None when done."""
        done = {
            c.chapter for c in self.list_checkpoints(novel_id, version) if c.status == "complete"
        }
        return next((ch for ch in range(1, total_chapters + 1) if ch not in done), None)

    # ----------------------------------------------------------------------------------
    # Forbidden terms and the policy log (G01, G04)
    # ----------------------------------------------------------------------------------

    def add_forbidden_term(
        self,
        term: str,
        *,
        scope: TermScope = "global",
        novel_id: str | None = None,
        reason: str = "",
    ) -> ForbiddenTerm:
        """Idempotent per (scope, novel, term). A `novel` term needs a `novel_id`."""
        self._db.execute(
            "insert or ignore into forbidden_term (scope, novel_id, term, reason, created_at) "
            "values (?, ?, ?, ?, ?)",
            (scope, novel_id if scope == "novel" else None, term, reason, _now()),
        )
        row = self._db.execute(
            "select id, scope, novel_id, term, reason from forbidden_term "
            "where scope = ? and coalesce(novel_id, '') = ? "
            "and term = ?",
            (scope, novel_id if scope == "novel" and novel_id else "", term),
        ).fetchone()
        return ForbiddenTerm.model_validate(dict(row))

    def list_forbidden_terms(self, novel_id: str | None = None) -> list[ForbiddenTerm]:
        """Global terms, plus the novel's own when `novel_id` is given."""
        rows = self._db.execute(
            "select id, scope, novel_id, term, reason from forbidden_term "
            "where scope = 'global' or (scope = 'novel' and novel_id = ?) order by scope, id",
            (novel_id,),
        ).fetchall()
        return [ForbiddenTerm.model_validate(dict(row)) for row in rows]

    def log_policy_decision(
        self,
        *,
        policy: str,
        decision: str,
        novel_id: str | None = None,
        version: int | None = None,
        chapter: int | None = None,
        scene: int | None = None,
        term: str | None = None,
        detail: str = "",
        attempt: int | None = None,
        trace_id: str | None = None,
    ) -> int:
        cursor = self._db.execute(
            "insert into policy_decision (novel_id, version, chapter, scene, policy, decision, "
            "term, detail, attempt, trace_id, created_at) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                novel_id,
                version,
                chapter,
                scene,
                policy,
                decision,
                term,
                detail,
                attempt,
                trace_id,
                _now(),
            ),
        )
        return int(cursor.lastrowid or 0)

    def list_policy_decisions(self, novel_id: str | None = None) -> list[PolicyDecision]:
        """The audit log. A scoped view (spec 018) sees only its owner's novels' entries:
        the owner of an entry is its novel's, by join."""
        if self._owner is not None:
            rows = self._db.execute(
                "select p.* from policy_decision p join novel n on n.id = p.novel_id "
                "where n.owner_id = ? and (? is null or p.novel_id = ?) order by p.id",
                (self._owner, novel_id, novel_id),
            ).fetchall()
        elif novel_id is None:
            rows = self._db.execute("select * from policy_decision order by id").fetchall()
        else:
            rows = self._db.execute(
                "select * from policy_decision where novel_id = ? order by id", (novel_id,)
            ).fetchall()
        return [PolicyDecision.model_validate(dict(row)) for row in rows]

    # ----------------------------------------------------------------------------------
    # Validator results (K3 persists through these)
    # ----------------------------------------------------------------------------------

    def save_validator_result(
        self,
        *,
        novel_id: str,
        name: str,
        point: str,
        passed: bool,
        score: float | None = None,
        evidence: Iterable[str] = (),
        explanation: str = "",
        version: int | None = None,
        chapter: int | None = None,
        scene: int | None = None,
        trace_id: str | None = None,
        run_id: str | None = None,
    ) -> int:
        cursor = self._db.execute(
            "insert into validator_result (novel_id, version, chapter, scene, name, point, "
            "passed, score, evidence_json, explanation, trace_id, run_id, created_at) "
            "values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                novel_id,
                version,
                chapter,
                scene,
                name,
                point,
                int(passed),
                score,
                json.dumps(list(evidence), ensure_ascii=False),
                explanation,
                trace_id,
                run_id,
                _now(),
            ),
        )
        return int(cursor.lastrowid or 0)

    def list_validator_results(
        self,
        novel_id: str,
        *,
        version: int | None = None,
        chapter: int | None = None,
        name: str | None = None,
        point: str | None = None,
    ) -> list[StoredValidatorResult]:
        sql = "select * from validator_result where novel_id = ?"
        params: list[object] = [novel_id]
        for column, value in (
            ("version", version),
            ("chapter", chapter),
            ("name", name),
            ("point", point),
        ):
            if value is not None:
                sql += f" and {column} = ?"
                params.append(value)
        rows = self._db.execute(sql + " order by id", params).fetchall()
        return [
            StoredValidatorResult.model_validate(
                {
                    **{k: row[k] for k in row.keys() if k != "evidence_json"},  # noqa: SIM118
                    "passed": bool(row["passed"]),
                    "evidence": tuple(json.loads(str(row["evidence_json"]))),
                }
            )
            for row in rows
        ]

    # ----------------------------------------------------------------------------------
    # Model calls: tokens, cost, latency (spec 010, O02)
    # ----------------------------------------------------------------------------------

    def record_llm_call(self, record: LlmCallRecord) -> int:
        """Satisfies `observability.LlmCallSink`."""
        stamped = record.stamped()
        cursor = self._db.execute(
            "insert into llm_call (novel_id, version, chapter, role, model, input_tokens, "
            "output_tokens, cache_read, cache_creation, cost_usd, latency_s, attempts, "
            "prompt_name, prompt_version, trace_id, ts) "
            "values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stamped.novel_id,
                stamped.version,
                stamped.chapter,
                stamped.role,
                stamped.model,
                stamped.input_tokens,
                stamped.output_tokens,
                stamped.cache_read,
                stamped.cache_creation,
                stamped.cost_usd,
                stamped.latency_s,
                stamped.attempts,
                stamped.prompt_name,
                stamped.prompt_version,
                stamped.trace_id,
                stamped.ts,
            ),
        )
        return int(cursor.lastrowid or 0)

    def cost_summary(self, novel_id: str, *, version: int | None = None) -> CostSummary:
        """Totals per novel, per chapter (None = calls outside a chapter) and per role."""
        # `? is null or version = ?`: one fixed statement per query, no SQL built from strings.
        params = (novel_id, version, version)
        total = self._db.execute(
            "select count(*), coalesce(sum(input_tokens), 0), coalesce(sum(output_tokens), 0), "
            "coalesce(sum(cache_read), 0), coalesce(sum(cache_creation), 0), "
            "coalesce(sum(cost_usd), 0), coalesce(sum(latency_s), 0) from llm_call "
            "where novel_id = ? and (? is null or version = ?)",
            params,
        ).fetchone()
        chapters = self._db.execute(
            "select chapter, count(*), sum(input_tokens), sum(output_tokens), sum(cache_read), "
            "sum(cost_usd), sum(latency_s) from llm_call "
            "where novel_id = ? and (? is null or version = ?) group by chapter order by chapter",
            params,
        ).fetchall()
        roles = self._db.execute(
            "select role, sum(cost_usd) from llm_call "
            "where novel_id = ? and (? is null or version = ?) group by role",
            params,
        ).fetchall()
        return CostSummary(
            novel_id=novel_id,
            calls=int(total[0]),
            input_tokens=int(total[1]),
            output_tokens=int(total[2]),
            cache_read=int(total[3]),
            cache_creation=int(total[4]),
            cost_usd=round(float(total[5]), 6),
            latency_s=round(float(total[6]), 3),
            by_chapter=tuple(
                ChapterCost(
                    chapter=_opt_int(row[0]),
                    calls=int(row[1]),
                    input_tokens=int(row[2]),
                    output_tokens=int(row[3]),
                    cache_read=int(row[4]),
                    cost_usd=round(float(row[5]), 6),
                    latency_s=round(float(row[6]), 3),
                )
                for row in chapters
            ),
            by_role={str(row[0]): round(float(row[1]), 6) for row in roles},
        )

    # ----------------------------------------------------------------------------------
    # Internals
    # ----------------------------------------------------------------------------------

    def _character(self, novel_id: str, character_id: str) -> Character:
        row = self._db.execute(
            "select * from character where novel_id = ? and id = ?", (novel_id, character_id)
        ).fetchone()
        if row is None:
            message = f"no character {character_id!r} in {novel_id!r}"
            raise BibleNotFoundError(message)
        return Character.model_validate(dict(row))

    def _next_id(self, table: str, novel_id: str, prefix: str) -> str:
        query = _ID_QUERIES[table]
        existing = {str(row[0]) for row in self._db.execute(query, (novel_id,)).fetchall()}
        number = len(existing) + 1
        while f"{prefix}{number}" in existing:
            number += 1
        return f"{prefix}{number}"


def _fact(row: sqlite3.Row) -> Fact:
    return Fact.model_validate({**dict(row), "mandatory": bool(row["mandatory"])})


def _version(row: sqlite3.Row) -> NovelVersion:
    return NovelVersion.model_validate(
        {
            **dict(row),
            "changed_chapters": tuple(json.loads(str(row["changed_chapters"]))),
            "trace_id": _opt_str(row["trace_id"]),
        }
    )


__all__ = [
    "DEFAULT_CHAPTERS",
    "DEFAULT_OWNER_ENV",
    "LOCAL_OWNER_ID",
    "BibleError",
    "BibleNotFoundError",
    "BibleRepository",
    "VersionFrozenError",
    "text_hash",
    "word_count",
]
