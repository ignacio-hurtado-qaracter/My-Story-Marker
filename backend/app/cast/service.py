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

`dossier(character, at)` (FR-OPS-01, AC 10) is the as-of trim of the same record, and the
load-bearing call of the feature. A writer handed the complete dossier uses facts the
character has not yet learned, because nothing in the text marks them as future: the record
reads as true, and everything true in the context is fair to write. `read_character` returns
the whole record for a human reading their own tree; an assembled context only ever gets the
trim.

The trim is split in two on purpose. `dossier` reads the files; `trim_dossier` is a pure
function of the records and a scene clock. The property AC 10 names - nothing dated after
`at` ever appears - is then tested over generated tables without a disk in the loop, and the
function the property holds for is the one the route runs.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass

from app.cast import repository
from app.cast.models import (
    ArcEntry,
    Character,
    RelationshipAsOf,
    TrimmedDossier,
    VoiceProfile,
)
from app.commons.errors import InvalidRecord
from app.commons.permissions import Actor, AgentRole
from app.commons.schemas import (
    ChangeEvent,
    ChangesFile,
    KnowledgeFile,
    KnowledgeState,
    RelationshipsFile,
    Scene,
)
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
    """IF-03, `GET /cast/{id}`. The complete dossier; the as-of trim is `dossier` below."""
    return repository.read_dossier(store, character)


# --------------------------------------------------------------------------------------
# FR-OPS-01 -- dossier(character, at)
# --------------------------------------------------------------------------------------


@dataclass(frozen=True, order=True, slots=True)
class SceneInstant:
    """Where a scene sits on the story axis, as a total order.

    `story_time` decides "at or before `at`" and nothing else does: FR-OPS-01 is stated on
    story time, and discourse order is the axis the reader meets scenes on, which is exactly
    the wrong one to date a character's knowledge by (an analepsis read last happened first).

    The other two fields exist only to break ties when "the latest" has to pick one entry
    among several at the same hour - scenes 004 and 005 of the fixture are both at 318. The
    spec does not say how; `discourse_order` then the scene id makes the choice deterministic,
    so two calls over the same tree cannot hand the writer two different arc states.
    """

    story_time: int
    discourse_order: int
    scene: str


SceneClock = Mapping[str, SceneInstant]
"""Scene id -> instant, for the scenes that exist. A scene id missing from the clock cannot
be placed in time, and nothing anchored to it is shown: FR-OPS-01's "nothing later appears"
is only provable for what can be placed."""


def scene_clock(scenes: Mapping[str, Scene]) -> dict[str, SceneInstant]:
    """The clock of a set of scene records, keyed by the id they were read under.

    Keyed by the path's id rather than the record's `id` field: the path is what the anchors
    name, and a record whose own id disagrees with its file is a separate fault.
    """
    return {
        identifier: SceneInstant(record.story_time, record.discourse_order, identifier)
        for identifier, record in scenes.items()
    }


def _placed(scene: str, clock: SceneClock, at: int) -> SceneInstant | None:
    """The instant of `scene` if it exists and is at or before `at`; otherwise `None`.

    Both failures give the same answer on purpose. A scene that does not exist cannot be shown
    to be at or before `at`, and FR-OPS-01's guarantee is about what is shown: the dossier
    excludes the row and FR-AUD-01 is what reports the dangling anchor.
    """
    instant = clock.get(scene)
    if instant is None or instant.story_time > at:
        return None
    return instant


def _physical_keys(record: Character, changes: Sequence[ChangeEvent]) -> frozenset[str]:
    """The attributes that are part of the body: the stored map, plus any attribute a change
    gives a value to (a scar that appears has no key before it does)."""
    given = {change.attribute for change in changes if change.to_value.strip()}
    return frozenset(record.immutable_physical) | given


def _is_forgetting(change: ChangeEvent, physical: frozenset[str]) -> bool:
    """`definitions.md` ChangeEvent: `attribute` is "the `immutable_physical` key, or the
    `fact_ref` forgotten", and `to` "is empty for a forgotten fact". So a change is the
    `Knows -> Unaware` edge exactly when its `to` is empty and its attribute is no part of the
    body; an emptied physical attribute is still a physical change."""
    return not change.to_value.strip() and change.attribute not in physical


def _body_at(
    record: Character,
    changes: Sequence[ChangeEvent],
    clock: SceneClock,
    at: int,
) -> dict[str, str]:
    """The body at `at`: the stored `immutable_physical` with every physical change dated at
    or before `at` applied, in story order.

    FR-OPS-01 does not name ChangeEvents; `docs/architecture.md` ("the character as they were
    at that instant") and `definitions.md` ChangeEvent ("before it, the old value holds") do.
    The stored map is the baseline the changes move off - the fixture's Ilan still reads
    `left_hand: flesh` - so without this the dossier would show the flesh hand for ever after
    scene 002, and a writer given that body writes a hand the character no longer has.

    A change whose scene cannot be placed withholds the attribute altogether: neither the old
    value nor the new one can be shown to hold at `at`, and withholding is more reliable than
    guessing (the same reasoning as the rest of the trim).
    """
    body = dict(record.immutable_physical)
    physical = _physical_keys(record, changes)
    applied: list[tuple[SceneInstant, int, ChangeEvent]] = []
    withheld: set[str] = set()
    for index, change in enumerate(changes):
        if _is_forgetting(change, physical):
            continue
        instant = clock.get(change.scene)
        if instant is None:
            withheld.add(change.attribute)
        elif instant.story_time <= at:
            applied.append((instant, index, change))
    for _, _, change in sorted(applied, key=lambda item: (item[0], item[1])):
        body[change.attribute] = change.to_value
    for attribute in withheld:
        body.pop(attribute, None)
    return body


def _erased(
    fact_ref: str,
    acquired: SceneInstant,
    forgettings: Sequence[ChangeEvent],
    clock: SceneClock,
    at: int,
) -> bool:
    """Whether a registered forgetting at or before `at` erased a state acquired at
    `acquired`.

    `domain-knowledge.md` Figure 4: `Knows -> Unaware` "must be explicitly registered", and a
    ChangeEvent is that registration. It erases only what was held when it happened - a state
    acquired *after* the forgetting is the fact learnt again, and survives. A same-scene tie
    counts as erased: the character leaves that scene without the fact.

    A forgetting whose scene cannot be placed erases every state on the fact: it cannot be
    shown that any of them survived it, and showing a fact the character may have lost is the
    direction of error this trim exists to prevent.
    """
    for change in forgettings:
        if change.attribute != fact_ref:
            continue
        instant = clock.get(change.scene)
        if instant is None:
            return True
        if instant.story_time <= at and acquired <= instant:
            return True
    return False


def _knowledge_at(
    character: str,
    knowledge: KnowledgeFile,
    forgettings: Sequence[ChangeEvent],
    clock: SceneClock,
    at: int,
) -> list[KnowledgeState]:
    """FR-OPS-01. The rows whose `acquired_in` scene has `story_time <= at`, minus the ones a
    registered forgetting has erased, in story order.

    Superseded states are kept (`suspects` at 012 and `knows` at 031 are both in the past at
    040): FR-OPS-01 asks for rows, and `KnowledgeFile` keeps a list precisely so the history
    survives. Story order makes the last row per `fact_ref` the state in force.

    A row naming another character is not this character's knowledge and is left out. The
    write path already refuses such a row (`save_knowledge`); a file edited by hand can still
    hold one, and showing bob's knowledge in alice's dossier is the leak AC 10 forbids.
    """
    kept: list[tuple[SceneInstant, int, KnowledgeState]] = []
    for index, row in enumerate(knowledge.knowledge):
        if row.character != character:
            continue
        instant = _placed(row.acquired_in, clock, at)
        if instant is None or _erased(row.fact_ref, instant, forgettings, clock, at):
            continue
        kept.append((instant, index, row))
    return [row for _, _, row in sorted(kept, key=lambda item: (item[0], item[1]))]


def _arc_at(arc: Sequence[ArcEntry], clock: SceneClock, at: int) -> ArcEntry | None:
    """FR-OPS-01. The arc entry anchored to the latest scene with `story_time <= at`.

    Latest on the story axis, never by position in the file: `Character.arc` is "ordered by
    the story axis at read time, never assumed sorted on disk". Two entries on one scene are
    a malformed arc; the later one in the file wins, so the answer is still deterministic.
    """
    placed = [
        (instant, index, entry)
        for index, entry in enumerate(arc)
        if (instant := _placed(entry.scene, clock, at)) is not None
    ]
    if not placed:
        return None
    return max(placed, key=lambda item: (item[0], item[1]))[2]


def _relationships_at(
    character: str,
    relationships: RelationshipsFile,
    clock: SceneClock,
    at: int,
) -> list[RelationshipAsOf]:
    """FR-OPS-01. Per edge from this character, the latest valence dated `<= at`.

    Latest by story time, not by file order and not by discourse order. The fixture tells the
    last two apart: vance -> ilan reads +2 at scene 006 (hour 310, read last) and +3 at 004
    (hour 318, read fourth). At 318 the answer is +3; ordering by discourse would say +2.

    An edge with no reading at or before `at` is left out, standing context and all: nothing
    on it can be shown to hold yet.
    """
    edges: list[RelationshipAsOf] = []
    for edge in relationships.relationships:
        if edge.from_character != character:
            continue
        readings = [
            (instant, index, reading)
            for index, reading in enumerate(edge.valence)
            if (instant := _placed(reading.scene, clock, at)) is not None
        ]
        if not readings:
            continue
        latest = max(readings, key=lambda item: (item[0], item[1]))[2]
        edges.append(
            RelationshipAsOf(
                to=edge.to_character,
                valence=latest,
                shared_history=edge.shared_history,
                unspoken=edge.unspoken,
            )
        )
    return sorted(edges, key=lambda edge: edge.to)


def trim_dossier(
    record: Character,
    knowledge: KnowledgeFile,
    changes: ChangesFile,
    relationships: RelationshipsFile,
    clock: SceneClock,
    at: int,
) -> TrimmedDossier:
    """FR-OPS-01, AC 10. The pure half of `dossier`: records and a clock in, the character as
    of `at` out.

    Every dated thing is placed through `clock` and kept only when its scene exists and has
    `story_time <= at`. Every undated thing is either standing context the docs name
    (identity, competences, wants / needs / lies, an edge's history once the edge has a
    reading) or it is left out (the Markdown body). `TrimmedDossier` says why.

    A change filed under another character is ignored for the same reason a foreign
    knowledge row is: it is not this character's body or memory.
    """
    own_changes = [change for change in changes.changes if change.character == record.id]
    physical = _physical_keys(record, own_changes)
    forgettings = [change for change in own_changes if _is_forgetting(change, physical)]
    return TrimmedDossier(
        id=record.id,
        name=record.name,
        at=at,
        immutable_physical=_body_at(record, own_changes, clock, at),
        wants=record.wants,
        needs=record.needs,
        lies=record.lies,
        competences=list(record.competences),
        arc=_arc_at(record.arc, clock, at),
        knowledge=_knowledge_at(record.id, knowledge, forgettings, clock, at),
        relationships=_relationships_at(record.id, relationships, clock, at),
    )


def _anchors(
    record: Character,
    knowledge: KnowledgeFile,
    changes: ChangesFile,
    relationships: RelationshipsFile,
) -> Iterator[str]:
    """Every scene id the character's records are anchored to: the only scenes the trim needs
    a story time for."""
    yield from (entry.scene for entry in record.arc)
    yield from (row.acquired_in for row in knowledge.knowledge)
    yield from (change.scene for change in changes.changes)
    for edge in relationships.relationships:
        if edge.from_character == record.id:
            yield from (reading.scene for reading in edge.valence)


def dossier(store: Store, character: str, at: int) -> TrimmedDossier:
    """FR-OPS-01, IF-03 `GET /cast/{id}/dossier?at=`. The character as they were at `at`.

    Reads the four records the trim needs - `dossier.md`, `knowledge.yaml`, `changes.yaml` and
    the shared `relationships.yaml` - and the scene records they are anchored to. Every one of
    them is required: the storage layout gives each character all four files, and a missing
    `changes.yaml` read as "no changes" would show a body that changed as one that did not. A
    missing file is therefore `NotFound` naming it, never an empty record (FR-STORE-06: never
    repaired).

    A `dossier.md` whose `id` is not the id in its path is refused the way a write of it would
    be. The trim filters every row by the record's own id, so a mismatch would otherwise
    answer with an empty dossier and a 200 -- a character with no knowledge and no ties, which
    a writer would take at its word.
    """
    record = repository.read_dossier(store, character)
    _refuse_foreign_id(
        path=repository.file_path(character, "dossier"),
        field="id",
        expected=character,
        found=record.id,
    )
    knowledge = repository.read_knowledge(store, character)
    changes = repository.read_changes(store, character)
    relationships = repository.read_relationships(store)
    scenes = repository.read_scenes(store, _anchors(record, knowledge, changes, relationships))
    return trim_dossier(record, knowledge, changes, relationships, scene_clock(scenes), at)


def body_at(store: Store, character: str, at: int) -> dict[str, str]:
    """Invariant 3, FR-AGENT-06, FR-OPS-07. The character's `immutable_physical` as of `at`:
    the stored map with every registered physical change dated at or before `at` applied, by
    the one rule `dossier` uses (`_body_at`).

    Narrower than `dossier` on purpose: it reads only `dossier.md`, `changes.yaml` and the
    scenes the changes are anchored to, because its callers -- the auditor's view of a
    participant's body and a human ruling's comparison of a body fact (`rule`) -- need the body
    and nothing else, and a malformed knowledge file must not decide what a body holds.
    `promote` does not call it: promotion is add-only and compares no value it would replace
    (FR-OPS-06). A missing `dossier.md` or `changes.yaml` is `NotFound` naming it, never an
    empty body (FR-STORE-06)."""
    record = repository.read_dossier(store, character)
    _refuse_foreign_id(
        path=repository.file_path(character, "dossier"),
        field="id",
        expected=character,
        found=record.id,
    )
    changes = repository.read_changes(store, character)
    own = [change for change in changes.changes if change.character == record.id]
    scenes = repository.read_scenes(store, (change.scene for change in own))
    return _body_at(record, own, scene_clock(scenes), at)


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
    "SceneClock",
    "SceneInstant",
    "body_at",
    "dossier",
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
    "scene_clock",
    "trim_dossier",
]
