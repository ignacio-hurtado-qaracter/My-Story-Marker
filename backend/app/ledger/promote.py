"""FR-OPS-06, FR-OPS-07. `promote` and `rule`: the return edge from the queue into canon.

`architecture.md` Operations: `promote` is "the return edge. The only write path into canon
during drafting, and the sole responsibility of the canoniser. When a proposed fact collides
with an existing record it is escalated rather than resolved silently." The failure mode it
names under ProposedFact is automatic promotion with no review: canon fills with improvised
noise and stops being authoritative, at which point nobody consults it and it constrains
nothing.

**This module is the one place in `ledger/` that writes `canon/` or `cast/`**, and it does so
only inside the two functions named `promote` and `rule`. That is AC 13's static rule
(`semgrep/canon-write-outside-promote.yaml` and its AST mirror in `tools/check_boundaries.py`):
the call that writes a target record is lexically inside one of those two bodies, never in a
helper, so a reviewer finds every canon write of the feature by reading two functions. The
helpers below read, resolve and compute; none of them writes.

What `promote` does to a field depends on the field's shape, and the three rules are the
design (FR-OPS-06 "it never overwrites"):

* **A scalar string** (`geometry`, `wants`, a `str | None` such as `Location.parent`): empty
  or absent -> set; equal to the payload -> promoted with no change; different -> **collision**.
* **A list of strings** (`competences`, `exceptions`, `derives_from`): canon grows additively,
  so a payload the list lacks is appended and one it already holds is a no-op. A list never
  collides -- adding an item contradicts nothing that is there.
* **A string mapping** (`immutable_physical`), payload written `key: value`: an absent key is
  added, the same value is a no-op, a different value is a **collision**.

On a collision `promote` sets `conflict` and `existing_value` on the fact, leaves it
`pending`, returns an `Escalation`, and writes nothing but `ledger/proposed.yaml`; `canon/` and
`cast/` stay byte-identical (AC 13). Only `rule`, under the canoniser **and** with
`X-Actor: human`, resolves it (FR-OPS-07). A fact that already carries `conflict: true` is not
re-examined by `promote` at all: `ProposedFact.conflict` "is never cleared by code; only a human
ruling settles it", so a second `promote` answers the same escalation and writes nothing.

**What cannot be promoted is refused, not escalated.** A target entity that does not exist, a
field the record does not have, a field no single string can fill (an integer date, a list of
arc entries, the `id` itself), or a payload that fails the field's own validation is a 422
`InvalidRecord` naming `ledger/proposed.yaml` and the offending field of the fact, and nothing
is written. The URL named a fact that exists, so a 404 would mislead; what is wrong is the
content of the queued record, which is precisely what a 422 naming file and field tells a
caller to go and fix. Escalating these instead would put a question in front of a human that
has no answer they could give: accepting a fact about an entity that was never created cannot
make it exist, because creating an entity is the world builder's act, not the canoniser's.

**Write order is canon first, queue second**, in both functions. If the process dies between
the two, the fact is still `pending` and the target already holds the payload, so the next
`promote` finds it equal (or already in the list, or the same mapping value) and settles the
fact with no further change. The other order could mark a fact `promoted` whose payload never
reached canon, and nothing would ever notice.
"""

from __future__ import annotations

import types
from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Final, Union, get_args, get_origin

from pydantic import ValidationError

from app.canon import service as canon_service
from app.canon.service import CanonEntity
from app.cast import service as cast_service
from app.cast.models import Character
from app.commons.errors import InvalidRecord, NotFound, PermissionDenied
from app.commons.permissions import Actor, AgentRole, may_write
from app.commons.schemas import FactStatus, ProposedFact, ProposedFile, Ruling, RulingKind
from app.commons.stores import Store, paths
from app.commons.stores.provenance import ProvenanceRecord, now
from app.ledger import repository
from app.ledger.models import Escalation, Promoted, RulingApplied

PROPOSED: Final[str] = repository.PROPOSED_PATH
"""`ledger/proposed.yaml`, named once. Every refusal below points at a field of this file."""

TargetRecord = CanonEntity | Character
"""What a fact may be promoted into: a canon entity of any of the five kinds, or a character's
dossier. `canon/project.md`, `canon/style.md`, the lexicon, the temporal system and the other
cast files are not targets: none of them is addressed by an entity id alone, and the brief of
FR-OPS-06 is `target_entity.target_field`."""

FieldValue = str | list[str] | dict[str, str]
"""The three shapes a promotable field has; see the module docstring for what each one means."""

_UNPROMOTABLE: Final[frozenset[str]] = frozenset({"id", "schema_version"})
"""Fields no fact may target even though they are strings. Identifiers are stable and the
backend never renames (DR-08): an accepted fact that rewrote `id` would leave a record whose
file name and id disagree. `schema_version` is not a fact about the world at all (DR-10)."""

_UNION_ORIGINS: Final[tuple[object, ...]] = (Union, types.UnionType)
"""`Optional[X]` and `X | None` have different runtime origins; both mean the same field."""


class _Shape(Enum):
    SCALAR = "scalar"
    LIST = "list"
    MAPPING = "mapping"


@dataclass(frozen=True, slots=True)
class _Target:
    """The record a fact addresses, where it lives, and the attribute and shape of its field."""

    path: str
    record: TargetRecord
    attribute: str
    shape: _Shape


@dataclass(frozen=True, slots=True)
class _Change:
    """What promoting the payload would do to the field.

    `value` is the field's new value, or `None` when canon already holds the payload. `existing`
    is the differing value the target holds -- set only on a collision -- in the same textual
    shape as the payload so the human ruling compares like with like.
    """

    value: FieldValue | None
    existing: str | None


# --------------------------------------------------------------------------------------
# Refusals that happen before anything is read or written
# --------------------------------------------------------------------------------------


def _require_canoniser(role: AgentRole, operation: str) -> None:
    """FR-OPS-06 / FR-OPS-07: both operations run "under the canoniser role".

    Checked before anything is read. This is a statement about the operation, not a second copy
    of Figure 3: the world builder may write `canon/**` too, but it may not write `cast/**` or
    the queue, and a promotion under it could land the canon half and be refused the queue half,
    leaving canon changed and the fact still pending. Figure 3's `Out` column gives the
    canoniser all three families, which is why the operation belongs to it alone.
    """
    if role is not AgentRole.CANONISER:
        message = (
            f"{operation} runs under the canoniser (FR-OPS-06, FR-OPS-07); "
            f"{role.value} may not promote facts into canon"
        )
        raise PermissionDenied(message, role=role.value, path=PROPOSED)


def _refuse_unless_permitted(role: AgentRole, *relatives: str) -> None:
    """Figure 3, asked for every file the operation will write **before** the first write.

    `Store.write` checks each write again (FR-STORE-03); this pre-flight is what makes the pair
    all-or-nothing with respect to permissions, so a refusal can never arrive after the canon
    half has already landed.
    """
    for relative in relatives:
        if not may_write(role, relative):
            message = f"Figure 3 does not allow {role.value} to write {relative}"
            raise PermissionDenied(message, role=role.value, path=relative)


# --------------------------------------------------------------------------------------
# Reading the queue and resolving the target
# --------------------------------------------------------------------------------------


def _find(queue: ProposedFile, fact_id: str) -> int:
    """The index of the fact in the queue. `NotFound` when absent; `InvalidRecord` when two
    entries claim the id, because every reference to it would then mean two things (DR-08) and
    promoting either one would be a guess."""
    matches = [index for index, fact in enumerate(queue.proposed) if fact.id == fact_id]
    if not matches:
        message = f"no proposed fact with id {fact_id!r} in {PROPOSED}"
        raise NotFound(message, kind="proposed_fact", identifier=fact_id)
    if len(matches) > 1:
        message = (
            f"{PROPOSED} declares the fact {fact_id!r} {len(matches)} times; identifiers are "
            "stable and a promotion cannot choose between them (DR-08)"
        )
        raise InvalidRecord(message, file=PROPOSED, field=f"proposed.{matches[1]}.id")
    return matches[0]


def _refuse_settled(fact: ProposedFact, index: int) -> None:
    """A promoted or rejected fact is history, not a queue entry.

    Re-promoting a settled fact would rewrite canon under a decision that was already taken --
    for a rejected fact, one a human took *against* it. The record of what was refused is kept
    precisely so the same invention is not argued about again.
    """
    if fact.status is not FactStatus.PENDING:
        message = (
            f"the fact {fact.id!r} is already {fact.status.value}; only a pending fact can be "
            "promoted or ruled on"
        )
        raise InvalidRecord(message, file=PROPOSED, field=f"proposed.{index}.status")


def _unwrap(annotation: object) -> object:
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    return annotation


def _shape_of(annotation: object) -> _Shape | None:
    """The field's shape, from its annotation, or `None` when a string payload cannot fill it.

    Constrained strings (`EntityId`) are strings: the constraint is enforced when the new value
    is assigned (`_updated`), not guessed at here.
    """
    bare = _unwrap(annotation)
    if bare is str:
        return _Shape.SCALAR
    origin = get_origin(bare)
    arguments = tuple(_unwrap(argument) for argument in get_args(bare))
    if origin in _UNION_ORIGINS and set(arguments) == {str, type(None)}:
        return _Shape.SCALAR
    if origin is list and arguments == (str,):
        return _Shape.LIST
    if origin is dict and arguments == (str, str):
        return _Shape.MAPPING
    return None


def _candidate_paths(store: Store, entity: str) -> list[tuple[str, str]]:
    """Every file that could be `entity`: `(kind, path)` for each canon kind and the dossier."""
    candidates = [
        (kind, relative)
        for kind in paths.CANON_KINDS
        if store.exists(relative := paths.canon_entity(kind, entity))
    ]
    dossier = paths.cast_file(entity, "dossier")
    if store.exists(dossier):
        candidates.append(("cast", dossier))
    return candidates


def _locate(store: Store, fact: ProposedFact, index: int) -> _Target:
    """Resolve `target_entity` to one record and `target_field` to one of its fields.

    Refused with `InvalidRecord` when the entity exists nowhere, when two kinds both hold a
    file of that id (the fact does not say which it meant), when the record has no such field,
    and when the field is not promotable. See the module docstring for why each is a 422 and
    not an escalation.
    """
    entity = fact.target_entity
    candidates = _candidate_paths(store, entity)
    if not candidates:
        message = (
            f"the fact {fact.id!r} targets {entity!r}, which is neither a canon entity nor a "
            "character; promote sets a field on an existing record and never creates one"
        )
        raise InvalidRecord(message, file=PROPOSED, field=f"proposed.{index}.target_entity")
    if len(candidates) > 1:
        where = ", ".join(relative for _, relative in candidates)
        message = f"the fact {fact.id!r} targets {entity!r}, which is ambiguous: {where}"
        raise InvalidRecord(message, file=PROPOSED, field=f"proposed.{index}.target_entity")

    kind, relative = candidates[0]
    record: TargetRecord = (
        cast_service.read_character(store, entity)
        if kind == "cast"
        else canon_service.entity(store, kind, entity, canon_service.CANON_MODELS[kind])
    )

    wanted = fact.target_field
    for attribute, info in type(record).model_fields.items():
        if wanted not in {attribute, info.alias}:
            continue
        shape = _shape_of(info.annotation)
        if attribute in _UNPROMOTABLE or shape is None:
            message = (
                f"{relative} field {wanted!r} cannot be filled by a promoted fact; change it "
                "through the owning role's PUT route instead"
            )
            raise InvalidRecord(message, file=PROPOSED, field=f"proposed.{index}.target_field")
        return _Target(relative, record, attribute, shape)

    message = f"{relative} has no field {wanted!r}"
    raise InvalidRecord(message, file=PROPOSED, field=f"proposed.{index}.target_field")


# --------------------------------------------------------------------------------------
# Computing the change -- pure, and the same for `promote` and `rule`
# --------------------------------------------------------------------------------------


def _split_mapping_payload(payload: str, index: int) -> tuple[str, str]:
    """`key: value`, split on the first colon. A payload without both halves asserts nothing a
    mapping can hold, and guessing a key would be inventing canon."""
    key, separator, value = payload.partition(":")
    key, value = key.strip(), value.strip()
    if not separator or not key or not value:
        message = (
            f"the payload {payload!r} targets a mapping field and must be written "
            "`key: value`, with both halves non-empty"
        )
        raise InvalidRecord(message, file=PROPOSED, field=f"proposed.{index}.payload")
    return key, value


def _compute(target: _Target, payload: str, index: int) -> _Change:
    """FR-OPS-06's three field rules. Values are compared exactly, whitespace and case
    included: a spurious collision costs a human one ruling, while a spurious "equal" would
    discard a difference silently, which is the one outcome promotion must never have."""
    current: object = getattr(target.record, target.attribute)

    if target.shape is _Shape.SCALAR:
        if current is None or (isinstance(current, str) and not current.strip()):
            return _Change(payload, None)
        held = str(current)
        return _Change(None, None) if held == payload else _Change(payload, held)

    if target.shape is _Shape.LIST:
        items = [str(item) for item in current] if isinstance(current, list) else []
        return _Change(None, None) if payload in items else _Change([*items, payload], None)

    key, value = _split_mapping_payload(payload, index)
    held_map = (
        {str(name): str(entry) for name, entry in current.items()}
        if isinstance(current, dict)
        else {}
    )
    if key not in held_map:
        return _Change({**held_map, key: value}, None)
    if held_map[key] == value:
        return _Change(None, None)
    return _Change({**held_map, key: value}, f"{key}: {held_map[key]}")


def _updated(target: _Target, value: FieldValue, index: int) -> TargetRecord:
    """The target record with the field replaced, validated by the record's own model.

    Store records validate on assignment (`HarnessModel`), so a payload that breaks the field's
    constraint -- an `EntityId` pattern, say -- is caught here, before any write, and before it
    can be escalated to a human who could only accept something the store would then refuse.
    """
    updated = target.record.model_copy(deep=True)
    try:
        setattr(updated, target.attribute, value)
    except ValidationError as error:
        detail = error.errors()[0]["msg"]
        message = f"the payload does not fit {target.path} field {target.attribute!r}: {detail}"
        raise InvalidRecord(message, file=PROPOSED, field=f"proposed.{index}.payload") from error
    return updated


def _with_fact(queue: ProposedFile, index: int, fact: ProposedFact) -> ProposedFile:
    """The queue with one entry replaced and every other entry, settled ones included, kept."""
    entries = list(queue.proposed)
    entries[index] = fact
    return ProposedFile(proposed=entries)


# --------------------------------------------------------------------------------------
# The two operations. The only functions in `ledger/` that write canon or cast.
# --------------------------------------------------------------------------------------


def promote(
    store: Store,
    fact_id: str,
    *,
    role: AgentRole,
    actor: Actor,
    scene: str | None = None,
    turn: str | None = None,
) -> Promoted | Escalation:
    """FR-OPS-06, AC 13. Promote one pending fact, or escalate its collision. Never overwrites.

    `scene` and `turn` are passed through to both provenance lines (FR-STORE-04) when the
    orchestrator promotes inside a turn; an HTTP call supplies neither.
    """
    _require_canoniser(role, "promote")
    queue = repository.read_proposed(store)
    index = _find(queue, fact_id)
    fact = queue.proposed[index]
    _refuse_settled(fact, index)
    target = _locate(store, fact, index)

    if fact.conflict:
        return Escalation(
            fact=fact,
            target_path=target.path,
            payload=fact.payload,
            existing_value=fact.existing_value,
            reason="the collision is already on record; only a human ruling settles it",
            writes=[],
        )

    change = _compute(target, fact.payload, index)
    updated = _updated(target, change.value, index) if change.value is not None else None
    _refuse_unless_permitted(role, target.path, PROPOSED)

    if change.existing is not None:
        escalated = fact.model_copy(update={"conflict": True, "existing_value": change.existing})
        line = store.write(
            PROPOSED,
            _with_fact(queue, index, escalated),
            role=role,
            actor=actor,
            scene=scene,
            turn=turn,
        )
        return Escalation(
            fact=escalated,
            target_path=target.path,
            payload=fact.payload,
            existing_value=change.existing,
            reason=f"{target.path} already holds a different value for {fact.target_field!r}",
            writes=[line],
        )

    writes: list[ProvenanceRecord] = []
    if updated is not None:
        writes.append(
            store.write(target.path, updated, role=role, actor=actor, scene=scene, turn=turn)
        )
    promoted = fact.model_copy(update={"status": FactStatus.PROMOTED})
    writes.append(
        store.write(
            PROPOSED,
            _with_fact(queue, index, promoted),
            role=role,
            actor=actor,
            scene=scene,
            turn=turn,
        )
    )
    return Promoted(
        fact=promoted, target_path=target.path, changed=updated is not None, writes=writes
    )


def rule(
    store: Store,
    fact_id: str,
    ruling: RulingKind,
    reason: str,
    *,
    role: AgentRole,
    actor: Actor,
    scene: str | None = None,
    turn: str | None = None,
) -> RulingApplied:
    """FR-OPS-07, AC 13. The human gate: `accept` promotes despite a collision, `reject` marks
    the fact rejected, and either way the ruling is recorded on the fact.

    **Refused for `actor: agent`** with `PermissionDenied` (403) before anything is read. This
    is the only path that resolves a collision, and "no code path resolves a collision without a
    `rule` call carrying `actor: human`" (AC 13) means nothing if a process may make that call
    as itself. The header is trusted in v1 (Decision 3, AC 25); what this guarantees is that the
    orchestrator, which always sends `agent`, can never settle a collision on its own.

    An accepted payload that overwrites a different value also sets `conflict` and
    `existing_value` on the fact -- whether or not `promote` recorded the collision first -- so
    what the human overwrote stays readable on the record the decision was taken about.
    """
    _require_canoniser(role, "rule")
    if actor is not Actor.HUMAN:
        message = (
            "rule is the human gate of FR-OPS-07: it requires X-Actor: human, and an agent "
            "may not settle a proposed fact on its own"
        )
        raise PermissionDenied(message, role=role.value, path=PROPOSED)

    queue = repository.read_proposed(store)
    index = _find(queue, fact_id)
    fact = queue.proposed[index]
    _refuse_settled(fact, index)
    if not reason.strip():
        message = (
            f"a ruling on {fact_id} needs a reason: a ruling without one is unreviewable, and "
            "the record of why is what stops the same fact being argued again"
        )
        raise InvalidRecord(message, file=PROPOSED, field=f"proposed.{index}.ruling.reason")
    decided = Ruling(by=actor.value, ruling=ruling, reason=reason, at=now())

    if ruling is RulingKind.REJECT:
        _refuse_unless_permitted(role, PROPOSED)
        rejected = fact.model_copy(update={"status": FactStatus.REJECTED, "ruling": decided})
        line = store.write(
            PROPOSED,
            _with_fact(queue, index, rejected),
            role=role,
            actor=actor,
            scene=scene,
            turn=turn,
        )
        return RulingApplied(
            fact=rejected, ruling=ruling, target_path=None, changed=False, writes=[line]
        )

    target = _locate(store, fact, index)
    change = _compute(target, fact.payload, index)
    updated = _updated(target, change.value, index) if change.value is not None else None
    _refuse_unless_permitted(role, target.path, PROPOSED)

    writes: list[ProvenanceRecord] = []
    if updated is not None:
        writes.append(
            store.write(target.path, updated, role=role, actor=actor, scene=scene, turn=turn)
        )
    settled = fact.model_copy(update={"status": FactStatus.PROMOTED, "ruling": decided})
    if change.existing is not None:
        settled = settled.model_copy(update={"conflict": True, "existing_value": change.existing})
    writes.append(
        store.write(
            PROPOSED,
            _with_fact(queue, index, settled),
            role=role,
            actor=actor,
            scene=scene,
            turn=turn,
        )
    )
    return RulingApplied(
        fact=settled,
        ruling=ruling,
        target_path=target.path,
        changed=updated is not None,
        writes=writes,
    )


__all__ = ["promote", "rule"]
