"""Rebuilding the index from the tree, and keeping it current incrementally.

What becomes a row (FR-IDX-02, plan step 9):

* one per entity file under `canon/<kind>/` for the five canon kinds;
* **one per term** of `canon/lexicon.yaml`, so a term is retrievable on its own;
* one per character under `cast/`, built from `cast/<id>/dossier.md` -- "what the index knows
  about a character is one embedding of their record" (`architecture.md`). `knowledge.yaml`
  and `changes.yaml` are as-of data that `dossier(at)` trims; the index does not need them to
  rank, and `voice.md` is register, not identity;
* **chapter-level digests only.** Scene and arc digests are never rows, as the SceneDigest
  section of `architecture.md` states, so a scene digest can never be selected into a
  context by ranking.

`canon/project.md` and `canon/style.md` are the fixed block, loaded into every context
unconditionally, so ranking them would be meaningless; `canon/time.yaml` is a calendar, not
an entity. None of the three is a row.

`commons/` may not import a feature's models (NFR-04), so canon entities and dossiers are
read with `Store.read_mapping` and their text is extracted generically. Digests and the
lexicon have shared models in `commons/schemas/` and are read validated. Either way a file
that does not parse raises `InvalidRecord` naming it: the index does not skip what the rest
of the system would refuse, because an index that quietly left an entity out would make
selection blind to it with nobody told.

**`updated_at` is the time of the last write of the backing file recorded in the provenance
log** (FR-STORE-04), or null when the file was never written through the backend. It is read
from the log, not from the clock, because AC 6 asserts that two rebuilds of the same tree
yield identical rows: any wall-clock value would differ between them by construction. It
is also not the file's mtime, which `commons/db` could only get by touching the tree itself
(FR-STORE-02), and which a checkout rewrites without any change of content.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field

from app.commons.config import EMBEDDING_DIM
from app.commons.db.connection import with_retry
from app.commons.db.index import (
    CANON_KIND_BY_DIRECTORY,
    META_EMBEDDING_DIM,
    META_EMBEDDING_MODEL,
    META_VECTOR_INDEXED,
    IndexKind,
    IndexRow,
    OpenIndex,
    VectorState,
    apply_changes,
    opened_index,
    read_metadata,
    rebuild_reason_without_embedder,
    replace_all,
    stored_rows,
    text_hash,
)
from app.commons.embeddings import Embedder
from app.commons.errors import InvalidRecord
from app.commons.schemas.common import DigestLevel
from app.commons.schemas.digest import SceneDigest
from app.commons.schemas.lexicon import LexiconFile
from app.commons.stores import Store, paths
from app.commons.stores.frontmatter import BODY_FIELD

MARKDOWN = ".md"


class IndexReport(BaseModel):
    """`POST /index/rebuild`, and what an incremental update did."""

    mode: Literal["rebuild", "incremental"] = Field(
        description="`rebuild` when every row was rewritten, `incremental` otherwise."
    )
    reason: str | None = Field(
        description=(
            "Why a rebuild ran: `requested` for `POST /index/rebuild`, or the FR-IDX-07 "
            "condition that forced one during an update. Null for an incremental update."
        )
    )
    rows: int = Field(description="Rows in the index afterwards.")
    embedded: int = Field(
        description="Texts sent to the embedder. FR-IDX-08: only rows whose hash changed."
    )
    removed: int = Field(description="Rows deleted because their record left the tree.")
    embedding_model: str = Field(description="The model recorded in the index metadata.")
    vector: VectorState = Field(description="Whether embeddings were written (FR-IDX-03).")


# --- text extraction --------------------------------------------------------------------


def _strings(value: object) -> list[str]:
    """Every string inside a parsed record, depth first, in the record's own order.

    Only strings: an `int` story time or a `bool` flag carries nothing a BM25 term or an
    embedding can use, and dates are skipped for the same reason. The order is the file's
    (YAML mappings keep it), so the same file always yields the same text.
    """
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, Mapping):
        found: list[str] = []
        for item in value.values():
            found.extend(_strings(item))
        return found
    if isinstance(value, list | tuple):
        found = []
        for item in value:
            found.extend(_strings(item))
        return found
    return []


def record_text(record: Mapping[str, object]) -> str:
    """A deterministic concatenation of the record's string values, with the body last.

    The body goes last so that the typed fields -- the part `definitions.md` says must be
    queryable -- lead the text whatever the length of the prose after them.
    """
    fields = {key: value for key, value in record.items() if key != BODY_FIELD}
    pieces = _strings(fields)
    body = record.get(BODY_FIELD)
    if isinstance(body, str) and body.strip():
        pieces.append(body.strip())
    return "\n".join(pieces)


def _row(
    entity_id: str,
    kind: IndexKind,
    path: str,
    text: str,
    written: Mapping[str, str],
) -> IndexRow:
    return IndexRow(
        entity_id=entity_id,
        kind=kind,
        path=path,
        text=text,
        content_hash=text_hash(text),
        updated_at=written.get(path),
    )


def _stem(relative: str) -> str:
    return PurePosixPath(relative).name.removesuffix(MARKDOWN)


# --- row sources ------------------------------------------------------------------------


def _canon_rows(store: Store, written: Mapping[str, str]) -> list[IndexRow]:
    rows: list[IndexRow] = []
    for directory in paths.CANON_KINDS:
        kind = CANON_KIND_BY_DIRECTORY[directory]
        for relative in store.list_files(paths.canon_dir(directory), MARKDOWN):
            identifier = _entity_id(relative, _stem(relative))
            record = store.read_mapping(relative)
            declared = record.get("id")
            if declared is not None and declared != identifier:
                # The canon write route refuses this mismatch; an index row keyed on the file
                # name whose text names another id would be a record the system refuses.
                message = (
                    f"{relative} declares id {declared!r}, but its file name says "
                    f"{identifier!r}"
                )
                raise InvalidRecord(message, file=relative, field="id")
            rows.append(_row(identifier, kind, relative, record_text(record), written))
    return rows


def _term_rows(store: Store, written: Mapping[str, str]) -> list[IndexRow]:
    if not store.exists(paths.LEXICON):
        return []
    lexicon = store.read(paths.LEXICON, LexiconFile)
    rows: list[IndexRow] = []
    seen: set[str] = set()
    for position, term in enumerate(lexicon.terms):
        if term.id in seen:
            message = f"{paths.LEXICON} registers the term id {term.id!r} twice"
            raise InvalidRecord(message, file=paths.LEXICON, field=f"terms.{position}.id")
        seen.add(term.id)
        text = record_text(term.model_dump(mode="json"))
        rows.append(_row(term.id, IndexKind.TERM, paths.LEXICON, text, written))
    return rows


def _character_rows(store: Store, written: Mapping[str, str]) -> list[IndexRow]:
    rows: list[IndexRow] = []
    for name in store.list_subdirectories(paths.CAST):
        try:
            dossier = paths.cast_file(name, "dossier")
        except ValueError as error:
            message = f"cast directory {name!r} cannot be addressed as a character: {error}"
            raise InvalidRecord(message, file=paths.CAST, field=name) from error
        if not store.exists(dossier):
            message = f"cast directory {name!r} has no dossier, so the character has no record"
            raise InvalidRecord(message, file=dossier)
        record = store.read_mapping(dossier)
        declared = record.get("id")
        if declared is not None and declared != name:
            message = f"{dossier} declares id {declared!r}, but its directory says {name!r}"
            raise InvalidRecord(message, file=dossier, field="id")
        rows.append(_row(name, IndexKind.CHARACTER, dossier, record_text(record), written))
    return rows


def _chapter_digest_rows(store: Store, written: Mapping[str, str]) -> list[IndexRow]:
    """Chapter digests only. A scene or arc digest is read, validated, and left out.

    Validated even though it is left out: the level is what decides, and a digest whose
    level cannot be read is one the system would refuse anywhere else.
    """
    rows: list[IndexRow] = []
    for relative in store.list_files(paths.DIGESTS, MARKDOWN):
        identifier = _stem(relative)
        try:
            paths.scene_id(identifier)
        except ValueError as error:
            message = f"{relative} cannot be addressed as a digest: {error}"
            raise InvalidRecord(message, file=relative) from error
        digest = store.read(relative, SceneDigest)
        if digest.level is not DigestLevel.CHAPTER:
            continue
        text = record_text(digest.model_dump(mode="json", exclude={"schema_version"}))
        rows.append(_row(identifier, IndexKind.CHAPTER_DIGEST, relative, text, written))
    return rows


def _entity_id(relative: str, name: str) -> str:
    try:
        return paths.entity_id(name)
    except ValueError as error:
        message = f"{relative} cannot be addressed as an entity: {error}"
        raise InvalidRecord(message, file=relative) from error


def _last_writes(store: Store) -> dict[str, str]:
    """Path to the timestamp of its latest provenance record (FR-STORE-04).

    The log is append-only, so the last line for a path is its latest write; taking the last
    rather than the greatest timestamp avoids comparing ISO strings that differ in whether
    they carry a fraction of a second.
    """
    latest: dict[str, str] = {}
    for record in store.provenance():
        latest[record.path] = record.at
    return latest


def collect_rows(store: Store) -> list[IndexRow]:
    """Every row the tree implies, sorted by (kind, entity_id).

    Sorted so the order -- and with it the ids `replace_all` assigns -- depends on nothing
    but the tree. Reads everything before anything is written, so a file that does not
    parse leaves the existing index untouched rather than half rebuilt.
    """
    written = _last_writes(store)
    rows = [
        *_canon_rows(store, written),
        *_term_rows(store, written),
        *_character_rows(store, written),
        *_chapter_digest_rows(store, written),
    ]
    return sorted(rows, key=lambda row: row.key)


# --- embedding --------------------------------------------------------------------------


def _embed(embedder: Embedder, rows: Sequence[IndexRow]) -> list[list[float]]:
    """FR-EMB-04: batched, synchronous, here and in `update`, never inside a role's request.

    The count and width are checked because a vector that does not fit `float[384]` would
    otherwise surface as an opaque SQLite error halfway through the write transaction.
    """
    if not rows:
        return []
    vectors = embedder.embed([row.text for row in rows])
    if len(vectors) != len(rows):
        message = f"{embedder.model_name} returned {len(vectors)} vectors for {len(rows)} texts"
        raise ValueError(message)
    for vector in vectors:
        if len(vector) != EMBEDDING_DIM:
            message = (
                f"{embedder.model_name} produced a {len(vector)}-d vector; the index is "
                f"float[{EMBEDDING_DIM}] (FR-EMB-02)"
            )
            raise ValueError(message)
    return vectors


def _metadata(embedder: Embedder, *, vector_indexed: bool) -> dict[str, str]:
    return {
        META_EMBEDDING_MODEL: embedder.model_name,
        META_EMBEDDING_DIM: str(embedder.dim),
        META_VECTOR_INDEXED: "true" if vector_indexed else "false",
    }


def rebuild_reason(index: OpenIndex, embedder: Embedder) -> str | None:
    """FR-IDX-07: why the index must be rebuilt for this embedder, or `None`.

    The recorded model and dimension are compared with the embedder's actual ones -- the
    model loaded, which after FR-EMB-02's fallback is not always the one configured.
    """
    metadata = with_retry(lambda: read_metadata(index.connection))
    reason = rebuild_reason_without_embedder(metadata, vector=index.vector)
    if reason is not None:
        return reason
    recorded_model = metadata.get(META_EMBEDDING_MODEL)
    if recorded_model != embedder.model_name:
        return f"the index was built with {recorded_model}; the embedder is {embedder.model_name}"
    recorded_dim = metadata.get(META_EMBEDDING_DIM)
    if recorded_dim != str(embedder.dim):
        return f"the index was built {recorded_dim}-d; the embedder is {embedder.dim}-d"
    return None


def _rebuild_into(
    index: OpenIndex, rows: Sequence[IndexRow], embedder: Embedder, reason: str
) -> IndexReport:
    vectors = _embed(embedder, rows) if index.vector else None
    replace_all(index, rows, vectors, _metadata(embedder, vector_indexed=index.vector))
    return IndexReport(
        mode="rebuild",
        reason=reason,
        rows=len(rows),
        embedded=len(vectors) if vectors is not None else 0,
        removed=0,
        embedding_model=embedder.model_name,
        vector="available" if index.vector else "unavailable",
    )


def rebuild(store: Store, embedder: Embedder, index_path: Path) -> IndexReport:
    """FR-IDX-04. Empty the derived tables and repopulate them from the tree.

    Without `sqlite-vec` nothing is embedded: there is nowhere to put a vector, and FTS5
    carries selection alone (FR-IDX-03). The model is still recorded, and the metadata says
    the vectors are missing, so the first update after the extension appears rebuilds.
    """
    rows = collect_rows(store)
    with opened_index(index_path) as index:
        return _rebuild_into(index, rows, embedder, "requested")


def update(store: Store, embedder: Embedder, index_path: Path) -> IndexReport:
    """FR-IDX-08. Bring the index in line with the tree, re-embedding only changed rows.

    The whole tree is re-read and re-hashed, which is cheap -- no model runs for a row whose
    hash is unchanged -- and is the only way to also notice rows whose record was deleted.
    A row whose text is unchanged but whose `updated_at` or path moved is rewritten without
    being re-embedded, so an update always leaves exactly the rows a rebuild would.

    FR-IDX-07: when the recorded model or dimension differ from the embedder's, or the
    vectors were never built, this rebuilds instead, because an incremental update would mix
    vectors from two models in one table.
    """
    rows = collect_rows(store)
    with opened_index(index_path) as index:
        reason = rebuild_reason(index, embedder)
        if reason is not None:
            return _rebuild_into(index, rows, embedder, reason)

        existing = with_retry(lambda: stored_rows(index.connection))
        current = {row.key: row for row in rows}
        changed = [
            row
            for row in rows
            if row.key not in existing or existing[row.key].content_hash != row.content_hash
        ]
        moved = [
            row
            for row in rows
            if row.key in existing
            and existing[row.key].content_hash == row.content_hash
            and (
                existing[row.key].path != row.path
                or existing[row.key].updated_at != row.updated_at
            )
        ]
        removed = sorted(key for key in existing if key not in current)

        upserts: list[tuple[IndexRow, Sequence[float] | None]]
        if index.vector:
            vectors = _embed(embedder, changed)
            upserts = [(row, vector) for row, vector in zip(changed, vectors, strict=True)]
        else:
            upserts = [(row, None) for row in changed]
        upserts.extend((row, None) for row in moved)
        if upserts or removed:
            apply_changes(
                index,
                upserts=upserts,
                deletes=removed,
                metadata=_metadata(embedder, vector_indexed=index.vector),
            )
        return IndexReport(
            mode="incremental",
            reason=None,
            rows=len(rows),
            embedded=len(changed) if index.vector else 0,
            removed=len(removed),
            embedding_model=embedder.model_name,
            vector="available" if index.vector else "unavailable",
        )


def ensure_current(store: Store, embedder: Embedder, index_path: Path) -> IndexReport | None:
    """Rebuild if FR-IDX-07 says the index cannot serve this embedder; otherwise do nothing.

    For the caller about to search by vector (plan step 11): `search_vector` refuses a query
    embedded by a model other than the recorded one, and this is what makes that refusal
    unreachable in practice. Returns the rebuild's report, or `None` when nothing was needed.
    """
    with opened_index(index_path) as index:
        reason = rebuild_reason(index, embedder)
        if reason is None:
            return None
        return _rebuild_into(index, collect_rows(store), embedder, reason)


__all__ = [
    "IndexReport",
    "collect_rows",
    "ensure_current",
    "rebuild",
    "rebuild_reason",
    "record_text",
    "update",
]
