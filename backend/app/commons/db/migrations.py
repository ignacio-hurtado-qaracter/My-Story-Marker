"""Numbered SQL migrations, recorded in `schema_migrations`.

FR-IDX-05: *applying them to an old index yields the fresh schema.* That is only true if
there is exactly one way a schema comes into being, so a fresh index and an old one go
through the same runner: a fresh file is simply an index with nothing recorded yet.

Two rules make the runner safe to call on every open:

* **It takes the write lock only when there is something to do.** Reading which migrations
  are recorded is a plain read, so opening the index for a search is never blocked by a
  rebuild in progress. When work is pending, the recorded state is read again inside the
  `BEGIN IMMEDIATE` transaction, so two processes opening a new index at once cannot both
  decide to apply 0001 (AC 8).
* **The vector migration is conditional** (FR-IDX-03). Without `sqlite-vec` it is recorded
  as `skipped`, not left unrecorded and not failed; "no code path fails for a missing
  extension". A skipped migration is applied the next time the index is opened with the
  extension loaded, which is the one case where migrations can land out of numeric order.
  That is acceptable because the vector table depends on nothing after 0002.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from importlib import resources
from typing import Final

from app.commons.db.connection import transaction

MIGRATIONS_PACKAGE: Final[str] = "app.commons.db"
MIGRATIONS_DIRECTORY: Final[str] = "migrations"

VECTOR_MIGRATIONS: Final[frozenset[str]] = frozenset({"0003_vec"})
"""Migrations that need `sqlite-vec` loaded. Named explicitly rather than sniffed from the
SQL, so adding a vector table is a visible decision in this file."""

_NAME = re.compile(r"^(\d{4})_[a-z0-9_]+$")

SCHEMA_MIGRATIONS_DDL: Final[str] = """
create table if not exists schema_migrations (
    version     text primary key,
    status      text not null check (status in ('applied', 'skipped')),
    recorded_at text not null
)
"""
"""Created by the runner, not by a migration: it is what records the migrations, so it
cannot itself be one of them."""


class MigrationStatus(StrEnum):
    APPLIED = "applied"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class Migration:
    """One `NNNN_name.sql` file."""

    name: str
    sql: str

    @property
    def requires_vector(self) -> bool:
        return self.name in VECTOR_MIGRATIONS


def available_migrations() -> list[Migration]:
    """Every migration file shipped with the package, in numeric order.

    Read through `importlib.resources` so the files travel with the package rather than
    being looked up relative to the working directory. A file whose name does not match
    `NNNN_name.sql`, or two files sharing a number, is a packaging bug and fails loudly: a
    runner that guessed the order would be the thing FR-IDX-05 exists to rule out.
    """
    directory = resources.files(MIGRATIONS_PACKAGE).joinpath(MIGRATIONS_DIRECTORY)
    found: list[Migration] = []
    numbers: set[str] = set()
    for entry in directory.iterdir():
        if not entry.name.endswith(".sql"):
            continue
        name = entry.name.removesuffix(".sql")
        match = _NAME.fullmatch(name)
        if match is None:
            message = f"migration file {entry.name!r} is not named NNNN_name.sql"
            raise RuntimeError(message)
        if match.group(1) in numbers:
            message = f"two migrations share the number {match.group(1)}"
            raise RuntimeError(message)
        numbers.add(match.group(1))
        found.append(Migration(name=name, sql=entry.read_text(encoding="utf-8")))
    return sorted(found, key=lambda migration: migration.name)


def recorded(connection: sqlite3.Connection) -> dict[str, MigrationStatus]:
    """What `schema_migrations` says, or nothing for an index that has never been opened."""
    exists = connection.execute(
        "select 1 from sqlite_master where type = 'table' and name = 'schema_migrations'"
    ).fetchone()
    if exists is None:
        return {}
    rows = connection.execute("select version, status from schema_migrations").fetchall()
    return {str(row[0]): MigrationStatus(str(row[1])) for row in rows}


def _action(
    migration: Migration, state: dict[str, MigrationStatus], *, vector: bool
) -> MigrationStatus | None:
    """What this migration needs now: applied, recorded as skipped, or nothing."""
    current = state.get(migration.name)
    if current is MigrationStatus.APPLIED:
        return None
    if migration.requires_vector and not vector:
        return None if current is MigrationStatus.SKIPPED else MigrationStatus.SKIPPED
    return MigrationStatus.APPLIED


def _statements(sql: str) -> list[str]:
    """Split a migration file into single statements.

    `sqlite3.complete_statement` is SQLite's own tokenizer, so a semicolon inside a comment
    or a string literal does not end a statement. Executing statement by statement, rather
    than through `executescript`, keeps the whole migration inside the caller's transaction:
    `executescript` commits any open transaction before it runs.
    """
    statements: list[str] = []
    buffer = ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            if _has_code(statement):
                statements.append(statement)
            buffer = ""
    if _has_code(buffer):
        message = "migration ends with an incomplete statement"
        raise RuntimeError(message)
    return statements


def _has_code(text: str) -> bool:
    return any(
        line.strip() and not line.strip().startswith("--") for line in text.splitlines()
    )


def migrate(
    connection: sqlite3.Connection, *, vector: bool, until: str | None = None
) -> dict[str, MigrationStatus]:
    """Bring the index up to date, and return what is recorded afterwards.

    `vector` is whether `sqlite-vec` is loaded on this connection. `until` stops after the
    named migration; it exists so a test can build the old index FR-IDX-05 talks about with
    the same runner that builds a fresh one.
    """
    pending = [
        migration
        for migration in available_migrations()
        if until is None or migration.name <= until
    ]
    before = recorded(connection)
    if not any(_action(migration, before, vector=vector) for migration in pending):
        return before

    with transaction(connection):
        connection.execute(SCHEMA_MIGRATIONS_DDL)
        # Re-read under the write lock: another process may have migrated since the check.
        state = recorded(connection)
        for migration in pending:
            action = _action(migration, state, vector=vector)
            if action is None:
                continue
            if action is MigrationStatus.APPLIED:
                for statement in _statements(migration.sql):
                    connection.execute(statement)
            connection.execute(
                "insert into schema_migrations (version, status, recorded_at) values (?, ?, ?) "
                "on conflict (version) do update set "
                "status = excluded.status, recorded_at = excluded.recorded_at",
                (migration.name, action.value, datetime.now(UTC).isoformat()),
            )
            state[migration.name] = action
    return recorded(connection)


__all__ = [
    "VECTOR_MIGRATIONS",
    "Migration",
    "MigrationStatus",
    "available_migrations",
    "migrate",
    "recorded",
]
