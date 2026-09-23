"""The operations of the scenes feature: whole-record reads, and writes that refuse a file
which contradicts itself or the path it is being written to.

Reads are pass-through by design. FR-STORE-06 already says what a read is -- validated, or
`InvalidRecord` naming file and field, never repaired and never partially returned -- and a
service that added anything on top would be a second opinion about a file the store layer has
already ruled on.

Writes are not pass-through, because each carries one check that only this layer can see.

* `scenes/NNN.yaml` has its id in the path *and* in the record. `scenes/012.yaml` holding
  `id: 003` is a file that validates, reads cleanly, and is wrong everywhere it matters: the
  turn assembles scene 012 and audits scene 003, and both halves report success.
* `structure/arcs.yaml` and `structure/chapters.yaml` are whole files of records that other
  records point at by id. Two arcs with the same id make every `chapter.arc` pointing at it
  ambiguous, and no later `reconcile` (FR-OPS-08) can recover which one was meant, because
  the information was never written down. `list[Arc]` cannot express uniqueness and the
  store layer validates the model, so the check has nowhere else to live; it would sit more
  naturally as a validator on the file models, which is reported with this step.

What is *not* checked here is everything that spans files: that a chapter's `arc` exists in
`arcs.yaml`, that its `scenes` exist under `scenes/`, that `discourse_order` is unique across
the book. Those are canon consistency questions, which `reconcile` answers at plan step 13.
Refusing them here would make the structure unwritable during the window in which a chapter
is being added -- the architect would have to create the parts in an order nobody chose.

`select_entities` (FR-OPS-02) lives in `select.py` and is published here, because this
module is the surface the orchestrator may import (NFR-04: a feature reaches another only
through its `service` and `models`). Still to come: `assemble_context` (FR-OPS-03) at plan
step 12. They are the load-bearing calls of this feature, and both read the record
`save_scene` writes.
"""

from __future__ import annotations

from app.commons.config import Settings
from app.commons.embeddings import Embedder
from app.commons.errors import InvalidRecord
from app.commons.permissions import Actor, AgentRole
from app.commons.schemas import Scene
from app.commons.stores import Store
from app.commons.stores.provenance import ProvenanceRecord
from app.scenes import repository, select
from app.scenes.models import ArcsFile, ChaptersFile, Selection


def _refuse_duplicate_ids(*, path: str, field: str, identifiers: list[str]) -> None:
    """DR-08. Two records in one file claiming the same identifier.

    A 422 rather than last-one-wins: identifiers are stable and every edge in the graph is an
    id, so a duplicate does not lose one record, it makes every pointer at that id mean two
    things at once. The first duplicate is named, because a message that says only "there are
    duplicates" leaves the caller to find it by eye in a file the architect just generated.
    """
    seen: set[str] = set()
    for index, identifier in enumerate(identifiers):
        if identifier in seen:
            message = (
                f"{path} declares {identifier!r} twice; identifiers are stable and every "
                "reference to this one would be ambiguous (DR-08)"
            )
            raise InvalidRecord(message, file=path, field=f"{field}.{index}.id")
        seen.add(identifier)


def list_scenes(store: Store) -> list[str]:
    """IF-03, `GET /scenes`."""
    return repository.list_scene_ids(store)


def read_scene(store: Store, identifier: str) -> Scene:
    """IF-03, `GET /scenes/{id}`."""
    return repository.read_scene(store, identifier)


def select_entities(
    store: Store,
    embedder: Embedder,
    settings: Settings,
    identifier: str,
    *,
    limit: int = select.DEFAULT_LIMIT,
) -> Selection:
    """IF-05, `POST /scenes/{id}/select` (FR-OPS-02, AC 11). Ids, kinds and scores, never
    text; the FR-IDX-08 update runs first. See `select.select_entities`."""
    return select.select_entities(store, embedder, settings, identifier, limit=limit)


def read_arcs(store: Store) -> ArcsFile:
    """IF-03, `GET /structure/arcs`."""
    return repository.read_arcs(store)


def read_chapters(store: Store) -> ChaptersFile:
    """IF-03, `GET /structure/chapters`."""
    return repository.read_chapters(store)


def save_scene(
    store: Store,
    identifier: str,
    record: Scene,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /scenes/{id}` (architect). The id in the record is the id in the path or
    nothing is written.

    Not corrected silently to the path's id: the backend never renames (DR-08), and a record
    the system quietly rewrote is a record whose author and whose reader believe different
    things -- here, about which scene the writer is about to be handed.
    """
    path = repository.scene_path(identifier)
    if record.id != identifier:
        message = (
            f"{path} is scene {identifier!r} but the record names {record.id!r}; "
            "identifiers are stable and the backend never renames (DR-08)"
        )
        raise InvalidRecord(message, file=path, field="id")
    return repository.write_scene(store, identifier, record, role=role, actor=actor)


def save_arcs(
    store: Store,
    record: ArcsFile,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /structure/arcs` (architect)."""
    _refuse_duplicate_ids(
        path=repository.ARCS_PATH,
        field="arcs",
        identifiers=[arc.id for arc in record.arcs],
    )
    return repository.write_arcs(store, record, role=role, actor=actor)


def save_chapters(
    store: Store,
    record: ChaptersFile,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /structure/chapters` (architect)."""
    _refuse_duplicate_ids(
        path=repository.CHAPTERS_PATH,
        field="chapters",
        identifiers=[chapter.id for chapter in record.chapters],
    )
    return repository.write_chapters(store, record, role=role, actor=actor)


__all__ = [
    "list_scenes",
    "read_arcs",
    "read_chapters",
    "read_scene",
    "save_arcs",
    "save_chapters",
    "save_scene",
    "select_entities",
]
