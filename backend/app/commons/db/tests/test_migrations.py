"""AC 6 (migration half), FR-IDX-05: applying the migrations to an old index yields the fresh
schema, and `schema_migrations` records what was applied and what was skipped.

A "v0 index" here is one on which only `0001_init` was ever applied -- the index as it would
have been before FTS5 and vectors existed. It is built with the same runner a fresh index
uses, stopped early, because there is exactly one way the schema comes into being.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.commons.db.connection import connect, load_vector_extension, vector_extension_available
from app.commons.db.index import opened_index
from app.commons.db.migrations import (
    VECTOR_MIGRATIONS,
    MigrationStatus,
    available_migrations,
    migrate,
    recorded,
)
from app.commons.db.tests.support import has_table, requires_sqlite_vec, schema_of


def _fresh(path: Path) -> dict[str, MigrationStatus]:
    with opened_index(path) as index:
        return dict(index.migrations)


def _v0(path: Path) -> None:
    """An index with only 0001 applied, and one row in it that must survive migration."""
    connection = connect(path, with_vector=False)
    try:
        state = migrate(connection, vector=load_vector_extension(connection), until="0001_init")
        assert state == {"0001_init": MigrationStatus.APPLIED}
        connection.execute(
            "insert into entity (entity_id, kind, path, text, content_hash, updated_at) "
            "values ('ax_old', 'axiom', 'canon/axioms/ax_old.md', 'old', 'h', null)"
        )
    finally:
        connection.close()


# spec 001 / AC 6 -- migrations on a v0 index match a fresh schema.
def test_migrating_a_v0_index_yields_the_fresh_schema(tmp_path: Path) -> None:
    fresh, old = tmp_path / "fresh.sqlite", tmp_path / "old.sqlite"
    fresh_state = _fresh(fresh)
    _v0(old)
    assert schema_of(old) != schema_of(fresh)

    old_state = _fresh(old)

    assert schema_of(old) == schema_of(fresh)
    assert old_state == fresh_state


# spec 001 / AC 6 -- migrating keeps what was already there; the runner adds, never resets.
def test_migrating_a_v0_index_keeps_its_rows(tmp_path: Path) -> None:
    old = tmp_path / "old.sqlite"
    _v0(old)
    _fresh(old)

    connection = connect(old, with_vector=False)
    try:
        rows = connection.execute("select entity_id from entity").fetchall()
    finally:
        connection.close()
    assert [tuple(row) for row in rows] == [("ax_old",)]


# spec 001 / AC 6 -- a fresh index records every migration, in order, once.
def test_a_fresh_index_records_every_migration(tmp_path: Path) -> None:
    state = _fresh(tmp_path / "index.sqlite")
    names = [migration.name for migration in available_migrations()]

    assert names == sorted(names) == ["0001_init", "0002_fts", "0003_vec"]
    assert set(state) == set(names)
    assert state["0001_init"] is state["0002_fts"] is MigrationStatus.APPLIED
    expected_vec = (
        MigrationStatus.APPLIED if vector_extension_available() else MigrationStatus.SKIPPED
    )
    assert state["0003_vec"] is expected_vec


# spec 001 / AC 6 -- opening an up-to-date index again changes nothing, not even the time a
# migration was recorded: the runner writes only when there is something to do.
def test_reopening_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "index.sqlite"
    _fresh(path)
    connection = connect(path, with_vector=False)
    try:
        before = connection.execute("select * from schema_migrations order by version").fetchall()
    finally:
        connection.close()

    _fresh(path)
    _fresh(path)

    connection = connect(path, with_vector=False)
    try:
        after = connection.execute("select * from schema_migrations order by version").fetchall()
    finally:
        connection.close()
    assert [tuple(row) for row in after] == [tuple(row) for row in before]


# spec 001 / AC 7 -- FR-IDX-03: without sqlite-vec the vector migration is recorded as
# skipped, not failed and not left unrecorded, and the vector table does not exist.
def test_the_vector_migration_is_skipped_without_sqlite_vec(
    tmp_path: Path, without_sqlite_vec: None
) -> None:
    path = tmp_path / "index.sqlite"
    state = _fresh(path)

    assert {"0003_vec"} == VECTOR_MIGRATIONS
    assert state["0003_vec"] is MigrationStatus.SKIPPED
    assert not has_table(path, "entity_vec")
    assert has_table(path, "entity_fts")


# spec 001 / AC 7 -- and applied the next time the index is opened with the extension.
@requires_sqlite_vec
def test_a_skipped_vector_migration_is_applied_once_sqlite_vec_loads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "index.sqlite"
    with monkeypatch.context() as patched:
        patched.setitem(sys.modules, "sqlite_vec", None)
        assert _fresh(path)["0003_vec"] is MigrationStatus.SKIPPED

    state = _fresh(path)

    assert state["0003_vec"] is MigrationStatus.APPLIED
    assert has_table(path, "entity_vec")
    assert schema_of(path) == schema_of(_fresh_path(tmp_path))


def _fresh_path(tmp_path: Path) -> Path:
    path = tmp_path / "reference.sqlite"
    _fresh(path)
    return path


# spec 001 / AC 6 -- the record is readable on its own, and empty for a file never opened.
def test_recorded_is_empty_for_a_new_file(tmp_path: Path) -> None:
    connection = connect(tmp_path / "index.sqlite", with_vector=False)
    try:
        assert recorded(connection) == {}
    finally:
        connection.close()
