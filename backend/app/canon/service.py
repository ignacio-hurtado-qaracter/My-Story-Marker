"""The canon feature's operations: the five kinds, the rules a route must not skip, and
`reconcile`.

Three things live here that are neither storage nor HTTP.

**The kind-to-model map.** `paths.CANON_KINDS` says which directories exist; this says what
a file in each of them is. The two are checked against each other at import time, in the
same way `AgentRole` is checked against `config.ROLE_NAMES`, because a kind with a directory
and no model would surface as a `KeyError` while registering routes, and a model with no
directory would never be reachable at all.

**The id agreement rule.** A `PUT` carries the identifier twice - once in the path, once in
the record - and the two are not allowed to disagree. See `replace_entity`.

**`reconcile`** (`POST /canon/reconcile`, FR-OPS-08): when canon changes retroactively, which
written work depended on the previous fact. It is split like `dossier` in the cast feature:
`find_dependents` is a pure function of the records, so AC 14's property can be tested over
generated scenes with no disk in the loop, and `reconcile` reads the tree and calls it.
`reconcile` reads other features' files (`scenes/`, `cast/*/knowledge.yaml`, the turn records
under `.index/`) through `Store` with `commons.schemas` models, which is the only way `canon`,
at the bottom of the NFR-04 layers, may see them.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Final

from pydantic import BaseModel, Field

from app.canon import repository
from app.canon.models import (
    Axiom,
    DependencyEdge,
    DependencyReason,
    Dependent,
    Faction,
    HistoricalEvent,
    Location,
    Project,
    Reconciliation,
    StyleBible,
    Technology,
)
from app.commons.errors import InvalidRecord, NotFound
from app.commons.permissions import Actor, AgentRole
from app.commons.schemas import KnowledgeFile, KnowledgeState, Scene, TurnRecord
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


# --------------------------------------------------------------------------------------
# FR-OPS-08 -- reconcile(entity_id)
# --------------------------------------------------------------------------------------

SCENE_SUFFIX: Final[str] = ".yaml"
"""`scenes/NNN.yaml`: the extension scene records carry, for listing `scenes/`."""

_Edges = dict[str, set[tuple[DependencyReason, str]]]


def _folded(value: str) -> str:
    return value.strip().casefold()


def _location_chain(leaf: str, parents: Mapping[str, str | None]) -> list[str]:
    """`leaf` and every ancestor through `Location.parent`, nearest first.

    Stops at a root, at a location with no record (a dangling `parent` has nothing above it
    that can be named), and at the first repeat: a cycle in the tree is a canon fault, and
    walking it for ever would turn a data error into a hung request.
    """
    chain: list[str] = []
    current: str | None = leaf
    while current is not None and current not in chain:
        chain.append(current)
        current = parents.get(current)
    return chain


def _scene_edges(
    entity_id: str,
    record: Scene,
    parents: Mapping[str, str | None],
    scope: frozenset[str],
) -> set[tuple[DependencyReason, str]]:
    """The references one scene record makes to the entity: FR-OPS-08's `pov`, `participants`,
    `location` or ancestors, and `tags`, plus `pins` (FR-OPS-02 pins by identifier, so a pinned
    entity was in that scene's context by construction)."""
    edges: set[tuple[DependencyReason, str]] = set()
    if record.pov == entity_id:
        edges.add((DependencyReason.POV, f"{entity_id} is the POV"))
    if entity_id in record.participants:
        edges.add((DependencyReason.PARTICIPANT, f"{entity_id} is present"))
    chain = _location_chain(record.location, parents)
    if chain[0] == entity_id:
        edges.add((DependencyReason.LOCATION, f"set in {entity_id}"))
    elif entity_id in chain:
        edges.add(
            (DependencyReason.LOCATION_ANCESTOR, f"set in {record.location}, inside {entity_id}")
        )
    if entity_id in record.pins:
        edges.add((DependencyReason.PINNED, f"{entity_id} is in pins"))
    matched = sorted({tag for tag in record.tags if _folded(tag) in scope})
    if matched:
        edges.add((DependencyReason.TAG_SCOPE, f"tags {', '.join(matched)} intersect its scope"))
    return edges


def _dependents(edges: _Edges) -> list[Dependent]:
    return [
        Dependent(
            id=identifier,
            reasons=[
                DependencyEdge(code=code, detail=detail)
                for code, detail in sorted(found, key=lambda edge: (edge[0].value, edge[1]))
            ],
        )
        for identifier, found in sorted(edges.items())
        if found
    ]


def find_dependents(
    entity_id: str,
    *,
    scenes: Mapping[str, Scene],
    parents: Mapping[str, str | None],
    scope: Sequence[str] = (),
    knowledge: Sequence[KnowledgeState] = (),
    turns: Sequence[TurnRecord] = (),
) -> tuple[list[Dependent], list[Dependent]]:
    """FR-OPS-08, AC 14. The pure half of `reconcile`: the scenes and the turn records that
    depend on `entity_id`, each once, sorted, with every reason.

    `scenes` is keyed by the id the record was read under (its file name), which is the id
    every other reference uses. `parents` maps each location to its `parent`. `scope` is the
    entity's `Axiom.scope` when it is an axiom and empty otherwise.

    Three decisions, each resolved towards inclusion because the answer is a superset (AC 14):

    * **Tags match the scope case-insensitively, whitespace trimmed.** FR-OPS-02 pins by the
      same intersection; a looser match here can only add scenes, never lose one that
      selection pinned.
    * **A turn that selected the entity also marks its scene** (`selected`). FR-OPS-08 asks for
      the turn record; the scene that turn wrote is the work that actually saw the entity in
      its context, which is the strongest evidence of dependence there is.
    * **A knowledge row whose `acquired_in` names no scene file is still reported.** The id
      depends on the entity whether or not the record exists yet, and dropping it would hide
      exactly the dangling reference FR-AUD-01 exists to find.
    """
    wanted = frozenset(_folded(tag) for tag in scope if tag.strip())
    scene_edges: _Edges = defaultdict(set)
    for identifier, record in scenes.items():
        scene_edges[identifier] |= _scene_edges(entity_id, record, parents, wanted)

    for row in knowledge:
        if row.fact_ref == entity_id:
            detail = f"{row.character} acquired it here ({row.certainty.value}, {row.via.value})"
            scene_edges[row.acquired_in].add((DependencyReason.KNOWLEDGE, detail))

    turn_edges: _Edges = defaultdict(set)
    for turn in turns:
        for selected in turn.selected:
            if selected.entity_id != entity_id:
                continue
            pinned = ", pinned" if selected.pinned else ""
            detail = f"selected for scene {turn.scene} as {selected.kind}{pinned}"
            turn_edges[turn.id].add((DependencyReason.SELECTED, detail))
            scene_edges[turn.scene].add((DependencyReason.SELECTED, f"selected in turn {turn.id}"))

    return _dependents(scene_edges), _dependents(turn_edges)


def _definitions(store: Store, entity_id: str) -> list[str]:
    """Every store file that defines the id: a canon entity of any kind, a character's
    dossier, or `canon/lexicon.yaml` when a term carries it (scenes pin terms, e.g. `lx_vault`).
    """
    found = [
        relative
        for kind in paths.CANON_KINDS
        if store.exists(relative := paths.canon_entity(kind, entity_id))
    ]
    dossier = paths.cast_file(entity_id, "dossier")
    if store.exists(dossier):
        found.append(dossier)
    if store.exists(paths.LEXICON) and any(
        term.id == entity_id for term in repository.read_lexicon(store).terms
    ):
        found.append(paths.LEXICON)
    return sorted(found)


def _all_scenes(store: Store) -> dict[str, Scene]:
    """Every scene record, keyed by file id. A scene file that fails validation raises
    `InvalidRecord` rather than being read around: a scene reconcile could not read is a scene
    it could not report, and a silent omission is the one wrong answer a superset can give."""
    scenes: dict[str, Scene] = {}
    for relative in store.list_files(paths.SCENES, SCENE_SUFFIX):
        name = relative.rsplit("/", 1)[-1].removesuffix(SCENE_SUFFIX)
        try:
            identifier = paths.scene_id(name)
        except ValueError as error:
            message = f"{relative} cannot be addressed as a scene: {error}"
            raise InvalidRecord(message, file=relative) from error
        scenes[identifier] = store.read(paths.scene(identifier), Scene)
    return scenes


def _location_parents(store: Store) -> dict[str, str | None]:
    return {
        identifier: repository.read_entity(store, "locations", identifier, Location).parent
        for identifier in repository.list_entity_ids(store, "locations")
    }


def _all_knowledge(store: Store) -> list[KnowledgeState]:
    """Every knowledge row in the cast, whoever holds it.

    A subdirectory of `cast/` whose name is not an entity id is not a character and cannot
    hold a path (FR-STORE-05), exactly as the cast listing treats it. A character with no
    `knowledge.yaml` yet holds no rows that could reference anything.
    """
    rows: list[KnowledgeState] = []
    for name in store.list_subdirectories(paths.CAST):
        try:
            character = paths.entity_id(name)
        except ValueError:
            continue
        relative = paths.cast_file(character, "knowledge")
        if store.exists(relative):
            rows.extend(store.read(relative, KnowledgeFile).knowledge)
    return rows


def reconcile(store: Store, entity_id: str) -> Reconciliation:
    """FR-OPS-08, IF-05 `POST /canon/reconcile`. Which written work depended on the entity.

    **An id that defines nothing is a 404**, not an empty answer. An empty list says "nothing
    depends on this, decide freely", and saying that about a mistyped id is the most expensive
    wrong answer this operation could give.

    Reads everything it reasons over on every call (FR-STORE-08): all scene records, every
    location for the parent chains, every character's knowledge, and the turn records.
    """
    defined_in = _definitions(store, entity_id)
    if not defined_in:
        message = f"no canon entity, character or lexicon term with id {entity_id!r}"
        raise NotFound(message, kind="entity", identifier=entity_id)
    axiom = paths.canon_entity("axioms", entity_id)
    scope = (
        repository.read_entity(store, "axioms", entity_id, Axiom).scope
        if store.exists(axiom)
        else []
    )
    scenes, turns = find_dependents(
        entity_id,
        scenes=_all_scenes(store),
        parents=_location_parents(store),
        scope=scope,
        knowledge=_all_knowledge(store),
        turns=store.turn_records(),
    )
    return Reconciliation(entity_id=entity_id, defined_in=defined_in, scenes=scenes, turns=turns)


__all__ = [
    "CANON_MODELS",
    "SCENE_SUFFIX",
    "CanonEntity",
    "KindIndex",
    "entity",
    "find_dependents",
    "lexicon",
    "list_kind",
    "project",
    "reconcile",
    "replace_entity",
    "replace_lexicon",
    "replace_temporal_system",
    "style",
    "temporal_system",
]
