"""Open the authoritative database and bring it up to date (spec 005).

Reuses the index's connection pragmas (WAL, `foreign_keys = ON`, busy timeout, explicit
transactions) but keeps its **own** migration sequence and record table, so the derived
index's numbering (0001...) and this one (1000-1599, per-block ranges of spec 004 § 5.4)
can never collide or be applied to the wrong file.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Final

from app.commons.db.connection import connect, transaction

AUTHORITATIVE_MIGRATIONS_TABLE: Final[str] = "authoritative_migrations"
_PACKAGE: Final[str] = "app.commons.db.authoritative"
_NAME = re.compile(r"^(1\d{3})_[a-z0-9_]+$")


def _available() -> list[tuple[str, str]]:
    directory = resources.files(_PACKAGE).joinpath("migrations")
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for entry in directory.iterdir():
        if not entry.name.endswith(".sql"):
            continue
        name = entry.name.removesuffix(".sql")
        match = _NAME.fullmatch(name)
        if match is None:
            message = f"authoritative migration {entry.name!r} is not named 1NNN_name.sql"
            raise RuntimeError(message)
        if match.group(1) in seen:
            message = f"two authoritative migrations share the number {match.group(1)}"
            raise RuntimeError(message)
        seen.add(match.group(1))
        found.append((name, entry.read_text(encoding="utf-8")))
    return sorted(found)


def _statements(sql: str) -> list[str]:
    statements: list[str] = []
    buffer = ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            code = "\n".join(
                row
                for row in buffer.splitlines()
                if row.strip() and not row.strip().startswith("--")
            )
            if code.strip():
                statements.append(code)
            buffer = ""
    if any(row.strip() and not row.strip().startswith("--") for row in buffer.splitlines()):
        message = "authoritative migration ends with an incomplete statement"
        raise RuntimeError(message)
    return statements


def applied_migrations(connection: sqlite3.Connection) -> list[str]:
    """Names of the migrations recorded on this database, in order."""
    exists = connection.execute(
        "select 1 from sqlite_master where type = 'table' and name = ?",
        (AUTHORITATIVE_MIGRATIONS_TABLE,),
    ).fetchone()
    if exists is None:
        return []
    rows = connection.execute(
        "select version from authoritative_migrations order by version"
    ).fetchall()
    return [str(row[0]) for row in rows]


def migrate_authoritative(connection: sqlite3.Connection) -> list[str]:
    """Apply every pending migration in one `BEGIN IMMEDIATE` transaction."""
    pending = [m for m in _available() if m[0] not in set(applied_migrations(connection))]
    if not pending:
        return applied_migrations(connection)
    with transaction(connection):
        connection.execute(
            "create table if not exists authoritative_migrations "
            "(version text primary key, applied_at text not null)"
        )
        done = set(applied_migrations(connection))
        for name, sql in pending:
            if name in done:
                continue
            for statement in _statements(sql):
                connection.execute(statement)
            connection.execute(
                "insert into authoritative_migrations (version, applied_at) values (?, ?)",
                (name, datetime.now(UTC).isoformat()),
            )
    return applied_migrations(connection)


def open_authoritative(path: Path | str, *, check_same_thread: bool = True) -> sqlite3.Connection:
    """Open (creating if needed) and migrate the authoritative database at `path`.

    `":memory:"` is accepted for tests. The connection has `row_factory = sqlite3.Row`,
    autocommit mode (`isolation_level=None`), WAL and foreign keys on.
    `check_same_thread=False` lets one owner hand the connection to another thread (the
    reader's per-request repository, spec 014); it is never shared concurrently.
    """
    if str(path) == ":memory:":
        connection = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("pragma foreign_keys = ON")
    else:
        connection = connect(Path(path), with_vector=False, check_same_thread=check_same_thread)
    try:
        migrate_authoritative(connection)
    except BaseException:
        connection.close()
        raise
    return connection


__all__ = [
    "AUTHORITATIVE_MIGRATIONS_TABLE",
    "applied_migrations",
    "migrate_authoritative",
    "open_authoritative",
    "transaction",
]
