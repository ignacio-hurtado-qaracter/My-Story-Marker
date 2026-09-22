"""The cast feature's access to the store layer, and the only module under `app/cast/` that
names a store path.

FR-STORE-02 puts every file primitive inside `app/commons/stores/`, and FR-STORE-05 puts
every path inside `commons.stores.paths`. This module is the seam between the two rules and
the feature: it turns a character id into the `Store` call that reads or writes one of the
five files of the cast -- the four per character (`dossier.md`, `voice.md`, `knowledge.yaml`,
`changes.yaml`, per the storage layout and Decision R2-5) and the one shared
`relationships.yaml`, which belongs to neither end of the edges it holds.

It carries no policy. Whether a role may write `cast/**` is decided by Figure 3 inside
`Store.write` (FR-PERM-03), which is why every write below takes its role from the caller and
none of them has a default: a default role would be a guess, and FR-STORE-04 would then
record the guess as provenance.
"""

from __future__ import annotations

from typing import Final, Literal

from app.cast.models import Character, VoiceProfile
from app.commons.permissions import Actor, AgentRole
from app.commons.schemas import ChangesFile, KnowledgeFile, RelationshipsFile
from app.commons.stores import Store, paths
from app.commons.stores.provenance import ProvenanceRecord

CastFile = Literal["dossier", "voice", "knowledge", "changes"]
"""The four per-character files, spelled as IF-04 spells them in
`PUT /cast/{id}/{dossier|voice|knowledge|changes}`. `paths.cast_file` maps each to its file
name and rejects anything else; this alias is the same closed set at type-check time, so a
misspelling fails the gate rather than a request.
"""

CAST_ROOT: Final[str] = "cast"
"""The directory `cast/` occupies in the storage layout: one subdirectory per character,
named by the character's id.

It is a fixed directory name rather than a path derived from an identifier, which is why it
may be spelled here at all. Every path that identifies a *file* is built by
`commons.stores.paths` and never by string concatenation (FR-STORE-05).
"""


def file_path(character: str, which: CastFile) -> str:
    """The store path of one per-character file, built by the store layer.

    Exposed rather than kept private because the service names the same file when it refuses
    a record (FR-STORE-06), and a feature with two ideas of where a character lives is a
    feature that will eventually write to one and read from the other.
    """
    return paths.cast_file(character, which)


def _names_a_character(directory: str) -> bool:
    """Whether a subdirectory of `cast/` could be a character at all.

    `paths.entity_id` holds the one grammar (FR-STORE-05), so this asks it rather than
    repeating the pattern. A directory that fails it can never become a path, so listing it
    would be a listing that lies: the client would read an id it can only get a 500 for.
    """
    try:
        paths.entity_id(directory)
    except ValueError:
        return False
    return True


def list_character_ids(store: Store) -> list[str]:
    """IF-03, `GET /cast`. The cast as the tree has it, sorted, with no index in the way.

    `cast/` is the one place `list_subdirectories` is needed, because a character is a
    directory rather than a file. It reads the tree on every call: FR-STORE-08 forbids an
    in-process cache, and a human who adds a character by hand expects to see it at once.
    """
    return [name for name in store.list_subdirectories(CAST_ROOT) if _names_a_character(name)]


def read_dossier(store: Store, character: str) -> Character:
    """IF-03, `GET /cast/{id}`. The whole record, untrimmed (FR-STORE-06)."""
    return store.read(file_path(character, "dossier"), Character)


def read_voice(store: Store, character: str) -> VoiceProfile:
    """IF-03, `GET /cast/{id}/voice`. Separate from the dossier because it is read at a
    different moment and by a different role: the style editor reads the voice and never the
    dossier."""
    return store.read(file_path(character, "voice"), VoiceProfile)


def read_knowledge(store: Store, character: str) -> KnowledgeFile:
    """IF-03, `GET /cast/{id}/knowledge`. Every recorded state, including the ones the
    character has not reached yet at any given scene; dating them is FR-OPS-01's job, not
    this one's."""
    return store.read(file_path(character, "knowledge"), KnowledgeFile)


def read_changes(store: Store, character: str) -> ChangesFile:
    """IF-03, `GET /cast/{id}/changes`. The register invariant 3 is measured against: without
    it, a scar that appears in chapter nine and a continuity error look identical."""
    return store.read(file_path(character, "changes"), ChangesFile)


def read_relationships(store: Store) -> RelationshipsFile:
    """IF-03, `GET /cast/relationships`. One file for every directed edge in the cast, because
    an edge belongs to neither end of itself."""
    return store.read(paths.RELATIONSHIPS, RelationshipsFile)


def write_dossier(
    store: Store,
    character: str,
    record: Character,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /cast/{id}/dossier`. Figure 3 gives `cast/**` to the canoniser; the check
    is `Store.write`'s, and refusal happens before any byte touches disk (FR-STORE-03)."""
    return store.write(file_path(character, "dossier"), record, role=role, actor=actor)


def write_voice(
    store: Store,
    character: str,
    record: VoiceProfile,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /cast/{id}/voice`."""
    return store.write(file_path(character, "voice"), record, role=role, actor=actor)


def write_knowledge(
    store: Store,
    character: str,
    record: KnowledgeFile,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /cast/{id}/knowledge`."""
    return store.write(file_path(character, "knowledge"), record, role=role, actor=actor)


def write_changes(
    store: Store,
    character: str,
    record: ChangesFile,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /cast/{id}/changes`."""
    return store.write(file_path(character, "changes"), record, role=role, actor=actor)


def write_relationships(
    store: Store,
    record: RelationshipsFile,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /cast/relationships`. The whole file at once: an edge is directed and the
    two directions of a pair are free to disagree, so there is no per-character slice of this
    file that could be written on its own."""
    return store.write(paths.RELATIONSHIPS, record, role=role, actor=actor)


__all__ = [
    "CAST_ROOT",
    "CastFile",
    "file_path",
    "list_character_ids",
    "read_changes",
    "read_dossier",
    "read_knowledge",
    "read_relationships",
    "read_voice",
    "write_changes",
    "write_dossier",
    "write_knowledge",
    "write_relationships",
    "write_voice",
]
