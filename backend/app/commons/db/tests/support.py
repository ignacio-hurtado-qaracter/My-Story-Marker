"""Helpers the index suites share: raw snapshots of the index, and two test embedders.

The snapshots read SQLite directly rather than through `commons/db`'s own functions on
purpose. AC 6 asserts that two rebuilds produce *identical rows and embeddings*; checking
that with the module under test would let one bug hide another.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.commons.db.connection import connect, load_vector_extension, vector_extension_available
from app.commons.embeddings import FakeEmbedder

requires_sqlite_vec = pytest.mark.skipif(
    not vector_extension_available(),
    reason="sqlite-vec does not load here; the CI `present` cell runs this (AC 7)",
)

RowTuple = tuple[int, str, str, str, str, str, str | None]
SchemaEntry = tuple[str, str, str, str | None]


def raw(index_path: Path) -> tuple[sqlite3.Connection, bool]:
    """A plain connection, with `sqlite-vec` loaded when it loads."""
    connection = connect(index_path, with_vector=False)
    return connection, load_vector_extension(connection)


def rows_of(index_path: Path) -> list[RowTuple]:
    """Every entity row, every column, in id order."""
    connection, _ = raw(index_path)
    try:
        return [
            (
                int(row[0]),
                str(row[1]),
                str(row[2]),
                str(row[3]),
                str(row[4]),
                str(row[5]),
                None if row[6] is None else str(row[6]),
            )
            for row in connection.execute(
                "select id, entity_id, kind, path, text, content_hash, updated_at "
                "from entity order by id"
            ).fetchall()
        ]
    finally:
        connection.close()


def rows_by_key(index_path: Path) -> dict[tuple[str, str], tuple[str, str, str, str | None]]:
    """Rows keyed by (kind, entity_id), without the internal id: for comparing an
    incrementally updated index with a rebuilt one, which number their rows differently."""
    return {
        (kind, entity_id): (path, text, content_hash, updated_at)
        for _, entity_id, kind, path, text, content_hash, updated_at in rows_of(index_path)
    }


def fts_of(index_path: Path) -> list[tuple[str, str, str, bool]]:
    """The FTS5 table as sorted (kind, entity_id, text, attached) tuples.

    `attached` is true when the FTS rowid is the id of the entity row with the same key.
    Compared separately from `rows_of` because the FTS table is a second copy of the text,
    written by the same code paths but not by the same statements: an update that refreshed
    `entity` and forgot `entity_fts` would leave a search answering with a deleted or stale
    entity while every row comparison still passed. A list, not a dict, so a duplicated FTS
    row shows up as one.
    """
    connection, _ = raw(index_path)
    try:
        found = connection.execute(
            "select f.kind, f.entity_id, f.text, "
            "(e.kind is f.kind and e.entity_id is f.entity_id) from entity_fts f "
            "left join entity e on e.id = f.rowid"
        ).fetchall()
    finally:
        connection.close()
    return sorted((str(row[0]), str(row[1]), str(row[2]), bool(row[3])) for row in found)


def has_table(index_path: Path, name: str) -> bool:
    connection, _ = raw(index_path)
    try:
        found = connection.execute(
            "select 1 from sqlite_master where name = ?", (name,)
        ).fetchone()
        return found is not None
    finally:
        connection.close()


def embeddings_of(index_path: Path) -> dict[tuple[str, str], bytes]:
    """Each row's stored embedding, keyed by (kind, entity_id). Empty without `sqlite-vec`."""
    connection, loaded = raw(index_path)
    try:
        if not loaded:
            return {}
        exists = connection.execute(
            "select 1 from sqlite_master where name = 'entity_vec'"
        ).fetchone()
        if exists is None:
            return {}
        return {
            (str(row[0]), str(row[1])): bytes(row[2])
            for row in connection.execute(
                "select e.kind, e.entity_id, v.embedding from entity_vec v "
                "join entity e on e.id = v.entity_rowid"
            ).fetchall()
        }
    finally:
        connection.close()


def schema_of(index_path: Path) -> list[SchemaEntry]:
    """`sqlite_master`, sorted: what FR-IDX-05 means by "the schema"."""
    connection, _ = raw(index_path)
    try:
        return [
            (str(row[0]), str(row[1]), str(row[2]), None if row[3] is None else str(row[3]))
            for row in connection.execute(
                "select type, name, tbl_name, sql from sqlite_master order by type, name"
            ).fetchall()
        ]
    finally:
        connection.close()


def metadata_of(index_path: Path) -> dict[str, str]:
    connection, _ = raw(index_path)
    try:
        return {
            str(row[0]): str(row[1])
            for row in connection.execute("select key, value from index_metadata").fetchall()
        }
    finally:
        connection.close()


def delete_index(index_path: Path) -> None:
    """Remove the index file and its WAL companions, and nothing else under `.index/`.

    Not a whole `.index/` clear: the provenance log beside the index is where each row's
    `updated_at` comes from, and it is not rebuildable (AC 31), so a rebuild after this
    reproduces the rows exactly, which it would not after deleting the log too."""
    for suffix in ("", "-wal", "-shm"):
        candidate = index_path.with_name(index_path.name + suffix)
        if candidate.exists():
            candidate.unlink()


class CountingEmbedder(FakeEmbedder):
    """The fake, recording every text it is asked to embed (FR-IDX-08)."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return super().embed(texts)

    @property
    def texts(self) -> list[str]:
        return [text for call in self.calls for text in call]


class OtherModelEmbedder(FakeEmbedder):
    """A different "model": another name and different vectors for the same text, which is
    what switching `EMBED_MODEL` does to an index (FR-IDX-07, AC 9)."""

    @property
    def model_name(self) -> str:
        return "fake-other-model-384"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return super().embed([f"other-model:{text}" for text in texts])


__all__ = [
    "CountingEmbedder",
    "OtherModelEmbedder",
    "delete_index",
    "embeddings_of",
    "fts_of",
    "has_table",
    "metadata_of",
    "raw",
    "requires_sqlite_vec",
    "rows_by_key",
    "rows_of",
    "schema_of",
]
