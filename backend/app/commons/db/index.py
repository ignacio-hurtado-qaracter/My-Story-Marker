"""The entity index: its rows, its two searches, and what `/index/status` reports.

Three rules from the spec shape everything here.

* **The index is derived, never a source** (FR-IDX-02, `architecture.md` Memory tiers). A
  row exists because a file exists; `status` counts the rows whose file is gone, and AC 6
  asserts the count is zero. Retrieval can only choose among facts that exist.
* **Searches return identifiers, kinds and scores, never text** (FR-OPS-02). The row text
  is stored because FTS5 needs it and the embedder needed it, and it stops here. "Selection
  returns identifiers, not text": what the writer receives is loaded by the store after
  selection, as of the scene's instant, so retrieval can never hand the writer a version of
  a record that the scene's instant forbids.
* **No code path fails for a missing extension** (FR-IDX-03). Every vector operation is
  guarded by `OpenIndex.vector`; without `sqlite-vec` the vector search answers with no
  hits and the FTS5 half carries selection alone.

Every read and write is wrapped in `with_retry`, so SQLITE_BUSY becomes `IndexBusy` only
after the busy timeout and the retries (FR-IDX-06).
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import struct
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, Field

from app.commons.config import EMBEDDING_DIM
from app.commons.db.connection import (
    connect,
    load_vector_extension,
    transaction,
    with_retry,
)
from app.commons.db.migrations import MigrationStatus, migrate
from app.commons.stores import Store

VectorState = Literal["available", "unavailable"]


class IndexKind(StrEnum):
    """What a row is. The `kind` of `SelectedEntity` on the turn record takes these values.

    One kind per canon directory, plus the three row sources that are not canon files:
    lexicon terms (one row per term of `canon/lexicon.yaml`, plan step 9), characters (one
    row per directory under `cast/`) and chapter digests. There is no scene-digest or
    arc-digest kind, because those are never rows (FR-IDX-02).
    """

    AXIOM = "axiom"
    TECHNOLOGY = "technology"
    LOCATION = "location"
    FACTION = "faction"
    HISTORICAL_EVENT = "historical_event"
    TERM = "term"
    CHARACTER = "character"
    CHAPTER_DIGEST = "chapter_digest"


CANON_KIND_BY_DIRECTORY: Final[Mapping[str, IndexKind]] = {
    "axioms": IndexKind.AXIOM,
    "technology": IndexKind.TECHNOLOGY,
    "locations": IndexKind.LOCATION,
    "factions": IndexKind.FACTION,
    "history": IndexKind.HISTORICAL_EVENT,
}
"""`canon/<directory>/` to row kind. The keys are exactly `paths.CANON_KINDS`, which a test
asserts, so a new canon directory cannot be added without deciding its kind."""

CANON_DIRECTORY_BY_KIND: Final[Mapping[IndexKind, str]] = {
    kind: directory for directory, kind in CANON_KIND_BY_DIRECTORY.items()
}
"""The inverse, for a caller that turns a hit back into `paths.canon_entity(directory, id)`."""

# --- metadata keys (FR-IDX-07) ----------------------------------------------------------

META_EMBEDDING_MODEL: Final[str] = "embedding_model"
META_EMBEDDING_DIM: Final[str] = "embedding_dim"
META_VECTOR_INDEXED: Final[str] = "vector_indexed"
"""`true` when every row has its embedding in `entity_vec`. `false` when the last write ran
without `sqlite-vec`, so a later open with the extension knows its vector table is empty or
stale and forces a rebuild instead of fusing half an index."""

VECTOR_MIGRATION: Final[str] = "0003_vec"


@dataclass(frozen=True, slots=True)
class IndexRow:
    """One row as derived from the tree (FR-IDX-02). Internal to `commons/db`: it carries
    text, and text does not leave this package."""

    entity_id: str
    kind: IndexKind
    path: str
    text: str
    content_hash: str
    updated_at: str | None

    @property
    def key(self) -> tuple[str, str]:
        return (self.kind.value, self.entity_id)


def text_hash(text: str) -> str:
    """FR-IDX-08. The hash of what is embedded, not of the file.

    Hashing the row text rather than the file bytes is what lets one edited lexicon term
    re-embed one row instead of all of them: every term shares `canon/lexicon.yaml`, and a
    file hash would change for all of them at once.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class IndexHit:
    """What a search answers: an identifier, a kind and a score, higher is better.

    No text field, by construction (FR-OPS-02, AC 11). Step 11 fuses the two lists by
    reciprocal rank; only the order within each list matters for that, and the scores are
    kept so the turn record can show them.
    """

    entity_id: str
    kind: str
    score: float


@dataclass(frozen=True, slots=True)
class OpenIndex:
    """A migrated connection, and whether its vector half is usable.

    `vector` is true only when `sqlite-vec` loaded on this connection **and** the vector
    table exists. An index built with the extension and opened without it has the table but
    cannot touch it -- SQLite answers "no such module" -- so both conditions are needed.
    """

    connection: sqlite3.Connection
    vector: bool
    migrations: dict[str, MigrationStatus]


@contextmanager
def opened_index(index_path: Path) -> Iterator[OpenIndex]:
    """Open, load the extension if it loads, migrate, and always close.

    Opening is retried like any other operation: switching a brand-new file to WAL and
    applying the first migration both need the write lock, and two processes can meet
    there (AC 8).
    """
    connection = with_retry(lambda: connect(index_path, with_vector=False))
    try:
        loaded = load_vector_extension(connection)
        state = with_retry(lambda: migrate(connection, vector=loaded))
        vector = loaded and state.get(VECTOR_MIGRATION) is MigrationStatus.APPLIED
        yield OpenIndex(connection=connection, vector=vector, migrations=state)
    finally:
        connection.close()


# --- reads ------------------------------------------------------------------------------


def read_metadata(connection: sqlite3.Connection) -> dict[str, str]:
    rows = connection.execute("select key, value from index_metadata").fetchall()
    return {str(row[0]): str(row[1]) for row in rows}


@dataclass(frozen=True, slots=True)
class StoredRow:
    """The part of a stored row the incremental update compares against."""

    id: int
    path: str
    content_hash: str
    updated_at: str | None


def stored_rows(connection: sqlite3.Connection) -> dict[tuple[str, str], StoredRow]:
    rows = connection.execute(
        "select id, kind, entity_id, path, content_hash, updated_at from entity"
    ).fetchall()
    return {
        (str(row["kind"]), str(row["entity_id"])): StoredRow(
            id=int(row["id"]),
            path=str(row["path"]),
            content_hash=str(row["content_hash"]),
            updated_at=None if row["updated_at"] is None else str(row["updated_at"]),
        )
        for row in rows
    }


# --- writes -----------------------------------------------------------------------------


def _vector_blob(vector: Sequence[float]) -> bytes:
    """The float32 layout `sqlite-vec` reads, as `sqlite_vec.serialize_float32` produces it.

    Packed here rather than through that helper so this module never imports `sqlite_vec`,
    which the `absent` cell of the CI matrix does not have (FR-IDX-03).
    """
    if len(vector) != EMBEDDING_DIM:
        message = (
            f"a {len(vector)}-d vector cannot enter a float[{EMBEDDING_DIM}] table "
            "(FR-EMB-02 accepts only 384-d models)"
        )
        raise ValueError(message)
    return struct.pack(f"{len(vector)}f", *vector)


def _insert_row(
    connection: sqlite3.Connection,
    row: IndexRow,
    vector: Sequence[float] | None,
    *,
    with_vector: bool,
    identifier: int | None = None,
) -> int:
    """Insert or update one row by (entity_id, kind), then its FTS row and its vector.

    The upsert keeps `id` stable for an existing row, so the FTS and vector rows keyed on
    it stay attached to the same entity.
    """
    cursor = connection.execute(
        "insert into entity (id, entity_id, kind, path, text, content_hash, updated_at) "
        "values (?, ?, ?, ?, ?, ?, ?) "
        "on conflict (entity_id, kind) do update set "
        "path = excluded.path, text = excluded.text, "
        "content_hash = excluded.content_hash, updated_at = excluded.updated_at "
        "returning id",
        (
            identifier,
            row.entity_id,
            row.kind.value,
            row.path,
            row.text,
            row.content_hash,
            row.updated_at,
        ),
    )
    fetched = cursor.fetchone()
    cursor.close()
    if fetched is None:  # pragma: no cover - RETURNING always yields the row it wrote
        message = f"the index did not return an id for {row.key}"
        raise RuntimeError(message)
    row_id = int(fetched[0])

    connection.execute("delete from entity_fts where rowid = ?", (row_id,))
    connection.execute(
        "insert into entity_fts (rowid, entity_id, kind, text) values (?, ?, ?, ?)",
        (row_id, row.entity_id, row.kind.value, row.text),
    )
    if with_vector and vector is not None:
        connection.execute("delete from entity_vec where entity_rowid = ?", (row_id,))
        connection.execute(
            "insert into entity_vec (entity_rowid, embedding) values (?, ?)",
            (row_id, _vector_blob(vector)),
        )
    return row_id


def _write_metadata(connection: sqlite3.Connection, metadata: Mapping[str, str]) -> None:
    for key in sorted(metadata):
        connection.execute(
            "insert into index_metadata (key, value) values (?, ?) "
            "on conflict (key) do update set value = excluded.value",
            (key, metadata[key]),
        )


def replace_all(
    index: OpenIndex,
    rows: Sequence[IndexRow],
    vectors: Sequence[Sequence[float]] | None,
    metadata: Mapping[str, str],
) -> None:
    """FR-IDX-04. Empty the derived tables and repopulate them, in one transaction.

    The rows are emptied rather than the tables dropped: the schema belongs to the
    migrations and `schema_migrations` records it, so a rebuild that re-created tables
    itself would be a second, unrecorded way for the schema to come into being. Ids are
    assigned explicitly, 1..n in the order given, so the result does not depend on how
    SQLite happens to allocate rowids -- AC 6 compares two rebuilds row for row.

    One transaction, so a reader sees the old index or the new one and never half of each.
    """
    if vectors is not None and len(vectors) != len(rows):
        message = f"{len(vectors)} vectors for {len(rows)} rows"
        raise ValueError(message)

    def run() -> None:
        with transaction(index.connection) as connection:
            connection.execute("delete from entity_fts")
            if index.vector:
                connection.execute("delete from entity_vec")
            connection.execute("delete from entity")
            for position, row in enumerate(rows):
                vector = vectors[position] if vectors is not None else None
                _insert_row(
                    connection, row, vector, with_vector=index.vector, identifier=position + 1
                )
            _write_metadata(connection, metadata)

    with_retry(run)


def apply_changes(
    index: OpenIndex,
    *,
    upserts: Sequence[tuple[IndexRow, Sequence[float] | None]],
    deletes: Sequence[tuple[str, str]],
    metadata: Mapping[str, str],
) -> None:
    """FR-IDX-08. Insert or update some rows and delete others, in one transaction.

    A row whose vector is `None` keeps the vector it has: that is the case of a row whose
    text did not change but whose path or `updated_at` did, and re-embedding it would spend
    the model on a text it has already embedded.
    """

    def run() -> None:
        with transaction(index.connection) as connection:
            for kind, entity_id in deletes:
                found = connection.execute(
                    "select id from entity where kind = ? and entity_id = ?", (kind, entity_id)
                ).fetchone()
                if found is None:
                    continue
                row_id = int(found[0])
                connection.execute("delete from entity_fts where rowid = ?", (row_id,))
                if index.vector:
                    connection.execute("delete from entity_vec where entity_rowid = ?", (row_id,))
                connection.execute("delete from entity where id = ?", (row_id,))
            for row, vector in upserts:
                _insert_row(connection, row, vector, with_vector=index.vector)
            _write_metadata(connection, metadata)

    with_retry(run)


# --- searches ---------------------------------------------------------------------------

_TOKEN = re.compile(r"\w+")


def fts_query(text: str) -> str | None:
    """Free text to an FTS5 MATCH expression: every distinct word, quoted, OR-ed.

    The query is a scene record, not an FTS5 expression, and it contains characters FTS5
    reads as syntax (`-`, `:`, `"`, `*`, `NEAR`). Quoting each word turns every one of them
    into a literal term, and OR lets BM25 rank by how many terms a row shares with the
    scene rather than demanding all of them. `None` when there is no word at all.
    """
    seen: dict[str, None] = {}
    for token in _TOKEN.findall(text.lower()):
        seen.setdefault(token, None)
    if not seen:
        return None
    return " OR ".join(f'"{token}"' for token in seen)


def search_text(index_path: Path, query: str, *, limit: int = 20) -> list[IndexHit]:
    """FR-OPS-02, the FTS5 half: BM25-ranked hits, best first.

    SQLite's `bm25()` is lower-is-better and negative; the score is its negation so that
    both searches answer higher-is-better. Ties are broken by kind and id, so the same index
    and the same query always give the same order.
    """
    expression = fts_query(query)
    if expression is None or limit <= 0:
        return []
    with opened_index(index_path) as index:

        def run() -> list[sqlite3.Row]:
            return index.connection.execute(
                "select entity_id, kind, bm25(entity_fts) as bm25_score from entity_fts "
                "where entity_fts match ? order by bm25_score, kind, entity_id limit ?",
                (expression, limit),
            ).fetchall()

        rows = with_retry(run)
    return [
        IndexHit(
            entity_id=str(row["entity_id"]),
            kind=str(row["kind"]),
            score=-float(row["bm25_score"]),
        )
        for row in rows
    ]


def kinds_of(index_path: Path, entity_ids: Sequence[str]) -> dict[str, list[str]]:
    """The kinds of the rows carrying each identifier: ids and kinds in, kinds out, no text.

    For a caller holding an identifier without its kind -- a scene's `pins` name an entity by
    id alone (FR-OPS-02, plan step 11). Every id asked about is a key of the answer, and an id
    no row carries maps to an empty list rather than being left out, so "not found" cannot be
    confused with "not asked". More than one kind means more than one record answers to the
    id; the kinds are sorted, so the answer does not depend on how the rows were inserted.
    One parameterised query per distinct id: pins are a handful, and no SQL is assembled.
    """
    found: dict[str, list[str]] = {identifier: [] for identifier in entity_ids}
    if not found:
        return found
    with opened_index(index_path) as index:

        def run() -> dict[str, list[str]]:
            return {
                identifier: [
                    str(row["kind"])
                    for row in index.connection.execute(
                        "select kind from entity where entity_id = ? order by kind",
                        (identifier,),
                    ).fetchall()
                ]
                for identifier in found
            }

        return with_retry(run)


class EmbeddingModelMismatchError(ValueError):
    """A query vector from one model searched against vectors from another.

    FR-IDX-07: vectors from two models are not comparable, and a cosine distance between
    them is a number with no meaning. Fusing it into a ranking would hand selection a
    confident answer to a question nobody asked. The caller calls `ensure_current` first,
    which rebuilds when the recorded model differs; reaching this error is a bug in the
    caller, not a state of the index.
    """


def search_vector(
    index_path: Path,
    embedding: Sequence[float],
    *,
    embedding_model: str,
    limit: int = 20,
) -> list[IndexHit]:
    """FR-OPS-02, the vector half: cosine KNN, best first. Empty when vectors are unusable.

    Empty rather than an error when `sqlite-vec` is missing or the vectors were never built
    (FR-IDX-03: selection is then FTS5-only). The score is cosine similarity, `1 - distance`.
    """
    if len(embedding) != EMBEDDING_DIM:
        message = f"query vector is {len(embedding)}-d; the index is float[{EMBEDDING_DIM}]"
        raise ValueError(message)
    if limit <= 0:
        return []
    with opened_index(index_path) as index:
        if not index.vector:
            return []
        metadata = with_retry(lambda: read_metadata(index.connection))
        recorded_model = metadata.get(META_EMBEDDING_MODEL)
        if recorded_model is not None and recorded_model != embedding_model:
            message = (
                f"the index holds vectors from {recorded_model}; the query was embedded by "
                f"{embedding_model}. Rebuild the index first (FR-IDX-07)."
            )
            raise EmbeddingModelMismatchError(message)
        if metadata.get(META_VECTOR_INDEXED) != "true":
            return []

        blob = _vector_blob(embedding)

        def run() -> list[sqlite3.Row]:
            return index.connection.execute(
                "with knn as ("
                "  select entity_rowid, distance from entity_vec"
                "  where embedding match ? and k = ?"
                ") "
                "select e.entity_id, e.kind, knn.distance from knn "
                "join entity e on e.id = knn.entity_rowid "
                "order by knn.distance, e.kind, e.entity_id",
                (blob, limit),
            ).fetchall()

        rows = with_retry(run)
    return [
        IndexHit(
            entity_id=str(row["entity_id"]),
            kind=str(row["kind"]),
            score=1.0 - float(row["distance"]),
        )
        for row in rows
    ]


# --- status -----------------------------------------------------------------------------


class IndexStatus(BaseModel):
    """`GET /index/status`. What a person needs to decide whether to rebuild."""

    rows: int = Field(description="Rows in the entity index.")
    orphans: int = Field(
        description=(
            "Rows whose `path` no longer exists in the tree (FR-IDX-07). An index entry with "
            "no backing record is a bug; AC 6 asserts this is zero after a rebuild."
        )
    )
    kinds: dict[str, int] = Field(description="Row count per kind.")
    embedding_model: str | None = Field(
        description="The model the index was last built with (FR-IDX-07); null if never built."
    )
    embedding_dim: int | None = Field(description="The dimension recorded with it.")
    vector: VectorState = Field(
        description=(
            "FR-IDX-03. `available` when `sqlite-vec` loads and the vector table exists; "
            "otherwise selection is FTS5-only."
        )
    )
    vector_rows: int = Field(description="Rows holding an embedding; 0 without `sqlite-vec`.")
    rebuild_required: str | None = Field(
        description=(
            "Why the next update will rebuild instead of updating incrementally, as far as "
            "can be told without loading the embedding model; null when nothing is known."
        )
    )
    migrations: dict[str, str] = Field(
        description="`schema_migrations`: each migration and whether it was applied or skipped."
    )


def rebuild_reason_without_embedder(
    metadata: Mapping[str, str], *, vector: bool
) -> str | None:
    """The reasons for a forced rebuild that do not need the embedder to know."""
    if META_EMBEDDING_MODEL not in metadata:
        return "the index has never been built"
    if vector and metadata.get(META_VECTOR_INDEXED) != "true":
        return (
            "sqlite-vec is available but the last build ran without it, so the vector table "
            "does not hold every row"
        )
    return None


def status(store: Store, index_path: Path) -> IndexStatus:
    """FR-IDX-07. Counts, the recorded model, vector availability and the orphan count.

    Orphans are counted by asking the store whether each distinct `path` exists, never by
    looking at the disk here: `commons/db` owns `index.sqlite`, not the tree (FR-STORE-02).
    """
    with opened_index(index_path) as index:
        connection = index.connection

        def run() -> tuple[dict[str, int], dict[str, int], dict[str, str], int]:
            kinds = {
                str(row[0]): int(row[1])
                for row in connection.execute(
                    "select kind, count(*) from entity group by kind order by kind"
                ).fetchall()
            }
            by_path = {
                str(row[0]): int(row[1])
                for row in connection.execute(
                    "select path, count(*) from entity group by path"
                ).fetchall()
            }
            vector_rows = 0
            if index.vector:
                found = connection.execute("select count(*) from entity_vec").fetchone()
                vector_rows = int(found[0]) if found is not None else 0
            return kinds, by_path, read_metadata(connection), vector_rows

        kinds, by_path, metadata, vector_rows = with_retry(run)
        vector = index.vector
        migrations = {name: state.value for name, state in sorted(index.migrations.items())}

    orphans = sum(count for path, count in by_path.items() if not store.exists(path))
    dim = metadata.get(META_EMBEDDING_DIM)
    return IndexStatus(
        rows=sum(kinds.values()),
        orphans=orphans,
        kinds=kinds,
        embedding_model=metadata.get(META_EMBEDDING_MODEL),
        embedding_dim=int(dim) if dim is not None else None,
        vector="available" if vector else "unavailable",
        vector_rows=vector_rows,
        rebuild_required=rebuild_reason_without_embedder(metadata, vector=vector),
        migrations=migrations,
    )


__all__ = [
    "CANON_DIRECTORY_BY_KIND",
    "CANON_KIND_BY_DIRECTORY",
    "META_EMBEDDING_DIM",
    "META_EMBEDDING_MODEL",
    "META_VECTOR_INDEXED",
    "EmbeddingModelMismatchError",
    "IndexHit",
    "IndexKind",
    "IndexRow",
    "IndexStatus",
    "OpenIndex",
    "StoredRow",
    "VectorState",
    "apply_changes",
    "fts_query",
    "kinds_of",
    "opened_index",
    "read_metadata",
    "rebuild_reason_without_embedder",
    "replace_all",
    "search_text",
    "search_vector",
    "status",
    "stored_rows",
    "text_hash",
]
