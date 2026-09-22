"""The canon feature's one door to the store layer (FR-STORE-02).

Everything this feature reads or writes goes through `Store`, and every path it names is
built by `app.commons.stores.paths`. Nothing here opens a file and nothing here spells a
path: FR-STORE-05 keeps the identifier-to-path grammar inside the store layer, which is what
makes "an identifier that would escape the root is rejected" a property of the system rather
than a habit of this module.

The model to validate against is a parameter rather than a lookup here, for the same reason
`Store.read` takes one. Which record a canon kind holds is a fact the routes already carry -
one typed route per kind, see `router.py` - and threading it through keeps this file
ignorant of the difference between an axiom and a faction, so a new kind is a line in
`service.CANON_MODELS` and nothing here.

`canon/project.md` and `canon/style.md` are read-only from the API (IF-03 lists them, IF-04
does not). Figure 3 lets the world builder write `canon/**`, so the permission exists; the
route does not, and adding one is a spec change rather than a convenience.
"""

from __future__ import annotations

from typing import Final

from app.canon.models import Project, StyleBible
from app.commons.errors import InvalidRecord, NotFound
from app.commons.permissions import Actor, AgentRole
from app.commons.schemas.common import StoreDocument
from app.commons.schemas.lexicon import LexiconFile
from app.commons.schemas.time import TemporalSystem
from app.commons.stores import Store, paths
from app.commons.stores.provenance import ProvenanceRecord

MARKDOWN_SUFFIX: Final[str] = ".md"
"""DR-02. Every canon entity file is Markdown with frontmatter."""

_DIRECTORY_PROBE: Final[str] = "probe"
"""An id used only to ask `paths` where a kind lives. See `kind_directory`."""


# --- paths ----------------------------------------------------------------------------


def entity_path(kind: str, identifier: str) -> str:
    """`canon/<kind>/<id>.md`, built by the store layer and validated by it.

    The single call site for the canon path grammar in this feature, so a bad kind or a bad
    identifier fails in one place and with the message `paths` writes.
    """
    return paths.canon_entity(kind, identifier)


def kind_directory(kind: str) -> str:
    """The directory holding one kind, read back off a path the store layer built.

    `paths` has no directory builder for a canon kind, and this feature may not invent one:
    a `canon/{kind}` spelled here would be a second place that knows the storage layout, and
    the first time the layout moved, the listing route would keep answering from the old
    one. Asking `canon_entity` for a path and dropping the file name keeps `paths` the only
    module that knows where a kind lives. A `paths.canon_kind_dir(kind)` would make this one
    call and belongs in `commons/`; it is reported with this step rather than added here.
    """
    return entity_path(kind, _DIRECTORY_PROBE).rsplit("/", 1)[0]


# --- reads ----------------------------------------------------------------------------


def read_project(store: Store) -> Project:
    """IF-03, `GET /canon/project`. Half of the fixed block (FR-OPS-03)."""
    return store.read(paths.PROJECT, Project)


def read_style(store: Store) -> StyleBible:
    """IF-03, `GET /canon/style`. The other half of the fixed block."""
    return store.read(paths.STYLE, StyleBible)


def read_lexicon(store: Store) -> LexiconFile:
    """IF-03, `GET /canon/lexicon`. DR-09."""
    return store.read(paths.LEXICON, LexiconFile)


def read_temporal_system(store: Store) -> TemporalSystem:
    """IF-03, `GET /canon/time`. DR-09."""
    return store.read(paths.TIME, TemporalSystem)


def read_entity[RecordT: StoreDocument](
    store: Store, kind: str, identifier: str, model: type[RecordT]
) -> RecordT:
    """IF-03, `GET /canon/{kind}/{id}`.

    The existence check is here rather than left to the store layer so the 404 body names
    the kind and the id the caller asked for (IF-07) instead of the file name it happened to
    become. A record that exists but does not validate is a different answer - `InvalidRecord`,
    422, naming file and field - and FR-STORE-06 is why the two are never merged: a missing
    axiom and a broken one call for different repairs.
    """
    relative = entity_path(kind, identifier)
    if not store.exists(relative):
        message = f"no {kind} record with id {identifier!r}"
        raise NotFound(message, kind=kind, identifier=identifier)
    return store.read(relative, model)


def list_entity_ids(store: Store, kind: str) -> list[str]:
    """IF-03, `GET /canon/{kind}`. Identifiers, sorted, never records.

    A file whose name is not a valid identifier raises `InvalidRecord` rather than being
    skipped. It cannot be addressed by any route (FR-STORE-05 rejects the id), so skipping
    it would leave an entity in the tree that nothing can reach and nobody is told about,
    which is the same silent repair FR-STORE-06 refuses elsewhere.
    """
    directory = kind_directory(kind)
    identifiers: list[str] = []
    for relative in store.list_files(directory, MARKDOWN_SUFFIX):
        name = relative.rsplit("/", 1)[-1].removesuffix(MARKDOWN_SUFFIX)
        try:
            identifiers.append(paths.entity_id(name))
        except ValueError as error:
            message = f"{relative} cannot be addressed as a {kind} record: {error}"
            raise InvalidRecord(message, file=relative) from error
    return identifiers


# --- writes ---------------------------------------------------------------------------
#
# Every write below names the role it is performed under, and that role arrives from the
# `X-Agent-Role` header (IF-02) rather than from a default here. There is no role argument
# with a value in this file: a default would mean the provenance log recorded this module's
# opinion instead of the caller's claim (FR-STORE-04).
#
# Which roles Figure 3 actually allows is not restated here either. `Store.write` calls
# `may_write`, the single check (FR-PERM-03), and refuses with `PermissionDenied` before any
# byte touches disk. A second guard in this feature could only ever drift from the table.


def write_entity(
    store: Store,
    kind: str,
    identifier: str,
    record: StoreDocument,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /canon/{kind}/{id}`."""
    return store.write(entity_path(kind, identifier), record, role=role, actor=actor)


def write_lexicon(
    store: Store, record: LexiconFile, *, role: AgentRole, actor: Actor
) -> ProvenanceRecord:
    """IF-04, `PUT /canon/lexicon`."""
    return store.write(paths.LEXICON, record, role=role, actor=actor)


def write_temporal_system(
    store: Store, record: TemporalSystem, *, role: AgentRole, actor: Actor
) -> ProvenanceRecord:
    """IF-04, `PUT /canon/time`."""
    return store.write(paths.TIME, record, role=role, actor=actor)


__all__ = [
    "MARKDOWN_SUFFIX",
    "entity_path",
    "kind_directory",
    "list_entity_ids",
    "read_entity",
    "read_lexicon",
    "read_project",
    "read_style",
    "read_temporal_system",
    "write_entity",
    "write_lexicon",
    "write_temporal_system",
]
