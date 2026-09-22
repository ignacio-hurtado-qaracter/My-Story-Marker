"""The canon feature's operations: the five kinds, and the rules a route must not skip.

Two things live here that are neither storage nor HTTP.

**The kind-to-model map.** `paths.CANON_KINDS` says which directories exist; this says what
a file in each of them is. The two are checked against each other at import time, in the
same way `AgentRole` is checked against `config.ROLE_NAMES`, because a kind with a directory
and no model would surface as a `KeyError` while registering routes, and a model with no
directory would never be reachable at all.

**The id agreement rule.** A `PUT` carries the identifier twice - once in the path, once in
the record - and the two are not allowed to disagree. See `replace_entity`.

`reconcile` (`POST /canon/reconcile`, FR-OPS-08) is the third operation this feature owns and
it arrives at plan step 13. It is deliberately absent here: the read and write surface of
IF-03 and IF-04 is step 7, and a stub route would answer a caller with a promise.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, Field

from app.canon import repository
from app.canon.models import (
    Axiom,
    Faction,
    HistoricalEvent,
    Location,
    Project,
    StyleBible,
    Technology,
)
from app.commons.errors import InvalidRecord
from app.commons.permissions import Actor, AgentRole
from app.commons.schemas.common import EntityId, StoreDocument
from app.commons.schemas.lexicon import LexiconFile
from app.commons.schemas.time import TemporalSystem
from app.commons.stores import Store, paths
from app.commons.stores.provenance import ProvenanceRecord

CanonEntity = Axiom | Technology | Location | Faction | HistoricalEvent
"""The five kinds of `canon/<kind>/<id>.md` as one static type.

It is never a request body. A union body would ask pydantic to guess which model a `PUT`
carries, and a guess that lands on the wrong model writes a valid-looking file of the wrong
kind - an axiom stored as a faction, validating cleanly, wrong for good. The routes bind one
concrete model per kind instead (`router.py`); this alias exists so the code that handles
all five can be typed without naming a lowest common denominator that has no `id`.
"""

CANON_MODELS: Final[dict[str, type[CanonEntity]]] = {
    "axioms": Axiom,
    "technology": Technology,
    "locations": Location,
    "factions": Faction,
    "history": HistoricalEvent,
}
"""DR-01. Which record each canon kind holds, in the order `paths.CANON_KINDS` lists them."""


if tuple(CANON_MODELS) != paths.CANON_KINDS:  # pragma: no cover - import-time
    message = (
        f"canon kinds {list(CANON_MODELS)} and paths.CANON_KINDS {list(paths.CANON_KINDS)} "
        "disagree; one of them was edited without the other"
    )
    raise RuntimeError(message)


class KindIndex(BaseModel):
    """IF-03, `GET /canon/{kind}`: the identifiers of one kind, and nothing else.

    Identifiers rather than records, because a list route that returned every axiom's full
    text would be the easiest way there is to spend the 100k context cap (NFR-05) from the
    client side, and it would do it without any of the ranking that FR-OPS-02 exists to
    apply. A caller that wants a record asks for it by id.
    """

    kind: str = Field(description="The canon kind these identifiers belong to.")
    ids: list[EntityId] = Field(
        description="Every entity of that kind, sorted; empty for a kind nothing has been"
        " written to yet, which is a legitimate state rather than a 404.",
    )


# --- reads ----------------------------------------------------------------------------


def project(store: Store) -> Project:
    """IF-03. Part of the fixed block (FR-OPS-03)."""
    return repository.read_project(store)


def style(store: Store) -> StyleBible:
    """IF-03. The other part of the fixed block."""
    return repository.read_style(store)


def lexicon(store: Store) -> LexiconFile:
    """IF-03. DR-09."""
    return repository.read_lexicon(store)


def temporal_system(store: Store) -> TemporalSystem:
    """IF-03. DR-09."""
    return repository.read_temporal_system(store)


def list_kind(store: Store, kind: str) -> KindIndex:
    """IF-03. The identifiers of one kind, with the kind named so the body stands alone."""
    return KindIndex(kind=kind, ids=repository.list_entity_ids(store, kind))


def entity[RecordT: StoreDocument](
    store: Store, kind: str, identifier: str, model: type[RecordT]
) -> RecordT:
    """IF-03. One record, validated against the model its kind declares."""
    return repository.read_entity(store, kind, identifier, model)


# --- writes ---------------------------------------------------------------------------


def replace_entity(
    store: Store,
    kind: str,
    identifier: str,
    record: CanonEntity,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04. Write one canon entity under the role the request names.

    The record's `id` must equal the identifier in the path, and a mismatch is refused
    rather than resolved. Either way of resolving it silently is wrong: the file name is
    what every path in the store points at, and the `id` field is what the index keys its
    row on and what `derives_from`, `who_has_it` and every other edge in the ontology
    resolves against. Letting the two differ writes a record that is reachable under one
    name and referenced under another, and nothing downstream can tell which was meant.
    """
    if record.id != identifier:
        message = (
            f"the record's id {record.id!r} is not the id in the path, {identifier!r}; "
            "the file name and the id are the same identifier and cannot disagree"
        )
        raise InvalidRecord(message, file=repository.entity_path(kind, identifier), field="id")
    return repository.write_entity(store, kind, identifier, record, role=role, actor=actor)


def replace_lexicon(
    store: Store, record: LexiconFile, *, role: AgentRole, actor: Actor
) -> ProvenanceRecord:
    """IF-04. The whole vocabulary at once: DR-09 keeps it in one file, so a write is total."""
    return repository.write_lexicon(store, record, role=role, actor=actor)


def replace_temporal_system(
    store: Store, record: TemporalSystem, *, role: AgentRole, actor: Actor
) -> ProvenanceRecord:
    """IF-04. There is exactly one temporal system per project (DR-09), so likewise."""
    return repository.write_temporal_system(store, record, role=role, actor=actor)


__all__ = [
    "CANON_MODELS",
    "CanonEntity",
    "KindIndex",
    "entity",
    "lexicon",
    "list_kind",
    "project",
    "replace_entity",
    "replace_lexicon",
    "replace_temporal_system",
    "style",
    "temporal_system",
]
