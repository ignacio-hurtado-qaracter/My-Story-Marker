"""The operations of the cast feature: reads that hand back a whole record, and writes that
refuse a record which does not belong to the character in the path.

Reads are pass-through by design. FR-STORE-06 already says what a read is -- validated, or
`InvalidRecord` naming file and field, never repaired and never partially returned -- and a
service that added anything on top would be a second opinion about a file the store layer has
already ruled on.

Writes are not pass-through, because there is one thing only this layer can see: the store
path carries the character id, and so does the record. `cast/alice/knowledge.yaml` holding
bob's rows is a file that validates, reads cleanly, and is invisible to every query that
matters -- the dossier trim looks in `cast/bob/` and finds nothing, and nobody is told. Ids
are stable and the backend never renames (DR-08), so the disagreement can only be resolved by
refusing it at the door.

Still to come, at plan step 10: `dossier(character, at)` and `GET /cast/{id}/dossier?at=`
(FR-OPS-01), the as-of trim of this same record. It is the load-bearing call of the feature.
A writer handed the complete dossier uses facts the character has not yet learned, because
nothing in the text marks them as future: the record reads as true, and everything true in
the context is fair to write. Until that step, `read_character` returns the whole record and
only a human reads it.
"""

from __future__ import annotations

from app.cast import repository
from app.cast.models import Character, VoiceProfile
from app.commons.errors import InvalidRecord
from app.commons.permissions import Actor, AgentRole
from app.commons.schemas import ChangesFile, KnowledgeFile, RelationshipsFile
from app.commons.stores import Store
from app.commons.stores.provenance import ProvenanceRecord


def _refuse_foreign_id(*, path: str, field: str, expected: str, found: str) -> None:
    """FR-STORE-06. A record whose id disagrees with the path it is being written to.

    A 422 rather than a silent correction: rewriting `found` to `expected` would file bob's
    knowledge under alice and report success, and the only trace left would be prose that
    quotes a character who was never told.
    """
    if found == expected:
        return
    message = (
        f"{path} belongs to {expected!r} but the record names {found!r}; "
        "identifiers are stable and the backend never renames (DR-08)"
    )
    raise InvalidRecord(message, file=path, field=field)


def list_characters(store: Store) -> list[str]:
    """IF-03, `GET /cast`."""
    return repository.list_character_ids(store)


def read_character(store: Store, character: str) -> Character:
    """IF-03, `GET /cast/{id}`. The complete dossier; the as-of trim is FR-OPS-01, step 10."""
    return repository.read_dossier(store, character)


def read_voice(store: Store, character: str) -> VoiceProfile:
    """IF-03, `GET /cast/{id}/voice`."""
    return repository.read_voice(store, character)


def read_knowledge(store: Store, character: str) -> KnowledgeFile:
    """IF-03, `GET /cast/{id}/knowledge`."""
    return repository.read_knowledge(store, character)


def read_changes(store: Store, character: str) -> ChangesFile:
    """IF-03, `GET /cast/{id}/changes`."""
    return repository.read_changes(store, character)


def read_relationships(store: Store) -> RelationshipsFile:
    """IF-03, `GET /cast/relationships`."""
    return repository.read_relationships(store)


def save_dossier(
    store: Store,
    character: str,
    record: Character,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /cast/{id}/dossier`. The id in the record is the id in the path or nothing
    is written."""
    _refuse_foreign_id(
        path=repository.file_path(character, "dossier"),
        field="id",
        expected=character,
        found=record.id,
    )
    return repository.write_dossier(store, character, record, role=role, actor=actor)


def save_voice(
    store: Store,
    character: str,
    record: VoiceProfile,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /cast/{id}/voice`. The voice carries the same id as the dossier, and the
    style editor reads it by that id."""
    _refuse_foreign_id(
        path=repository.file_path(character, "voice"),
        field="id",
        expected=character,
        found=record.id,
    )
    return repository.write_voice(store, character, record, role=role, actor=actor)


def save_knowledge(
    store: Store,
    character: str,
    record: KnowledgeFile,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /cast/{id}/knowledge`. Every row is checked, not just the first: one
    foreign row among thirty is exactly the case that survives review."""
    path = repository.file_path(character, "knowledge")
    for index, state in enumerate(record.knowledge):
        _refuse_foreign_id(
            path=path,
            field=f"knowledge.{index}.character",
            expected=character,
            found=state.character,
        )
    return repository.write_knowledge(store, character, record, role=role, actor=actor)


def save_changes(
    store: Store,
    character: str,
    record: ChangesFile,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /cast/{id}/changes`. A ChangeEvent filed under the wrong character is the
    worst of the four: invariant 3 would then excuse a body that never changed and flag one
    that did."""
    path = repository.file_path(character, "changes")
    for index, change in enumerate(record.changes):
        _refuse_foreign_id(
            path=path,
            field=f"changes.{index}.character",
            expected=character,
            found=change.character,
        )
    return repository.write_changes(store, character, record, role=role, actor=actor)


def save_relationships(
    store: Store,
    record: RelationshipsFile,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /cast/relationships`.

    No id check here, and none is possible: the file is the whole graph, so there is no path
    id for a row to disagree with. That the endpoints of an edge exist in `cast/` is a canon
    consistency question, which `reconcile` answers at plan step 13 -- refusing it here would
    make the file unwritable during the window in which a character is being added.
    """
    return repository.write_relationships(store, record, role=role, actor=actor)


__all__ = [
    "list_characters",
    "read_changes",
    "read_character",
    "read_knowledge",
    "read_relationships",
    "read_voice",
    "save_changes",
    "save_dossier",
    "save_knowledge",
    "save_relationships",
    "save_voice",
]
