"""FR-OPS-06, FR-OPS-07. `promote` and `rule`: the return edge from the queue into canon.

`architecture.md` Operations: `promote` is the return edge, the only write path into canon
during drafting and the sole responsibility of the canoniser. **Promotion is add-only**
(FR-OPS-06, AC 13): it adds to a record what the record does not already specify, and nothing
it writes replaces anything canon already says. It looks for no collision and escalates
nothing. Whether the prose may contradict canon is the auditor's question, asked before the
draft is accepted (FR-AGENT-06, FR-TURN-02); by the time a fact reaches `promote` that
judgement has been made, and a promotion that argued it again would be a second auditor with
write access to canon.

**This module is the one place in `ledger/` that writes `canon/` or `cast/`**, and it does so
only inside the two functions named `promote` and `rule`. That is AC 13's static rule
(`semgrep/canon-write-outside-promote.yaml` and its AST mirror in `tools/check_boundaries.py`):
the call that writes a target record is lexically inside one of those two bodies, never in a
helper, so a reviewer finds every canon write of the feature by reading two functions. The
helpers below read, resolve and compute; none of them writes.

What `promote` adds to a field depends on the field's shape (`_addition`):

* **A scalar string** (`geometry`, `wants`): empty or absent -> set to the payload. Already
  holding text -> the payload is appended to it as one more clause,
  `existing.rstrip() + "; " + payload.strip()`, unless the text already contains it, in which
  case nothing is written. "Contains" is word-bounded (`_contains`): the payload's words,
  compatibility-normalised and case-folded, form a contiguous run of the text's words, so
  `red` is not taken as said by `reddish`. The existing text is extended, never edited.
* **An atomic scalar** -- an identifier (a pattern-constrained string such as
  `Location.parent`) or a name (`_ATOMIC_FIELDS`): empty -> set; the same value -> nothing
  written; a different value -> **not applied**. Appending to an identifier makes an invalid
  one, and appending to a name corrupts the name every reader sees.
* **A list of strings** (`competences`, `exceptions`, `derives_from`): a payload the list lacks
  is appended; one it already holds is a no-op.
* **A string mapping** (`immutable_physical`), payload written `key: value`: a key the record
  does not have is added, as given. A key it already has is **never changed**: the same value
  is a no-op and any other value is not applied. Keys are compared case-folded, with runs of
  space, `_` and `-` counted as equal. For a character's body, a key a registered ChangeEvent
  names counts as one the record has even when the stored map lacks it: adding it to the base
  map would make the attribute hold from the story's start and rewrite the history the change
  records (invariant 3).

**Not applied** means the record already specifies what the fact addresses. The fact is settled
`rejected` with no `ruling` -- a ruling is a human decision, and `promote` never forges one --
only `ledger/proposed.yaml` is written, and the target stays byte-identical. No person is asked
and no turn waits. It is the one reason `promote` ever sets `rejected`, so the queue entry
(rejected, no ruling) is itself the record of why.

`conflict` and `existing_value` are never set or cleared by `promote`. A queue entry that
already carries `conflict: true` -- recorded before promotion became add-only -- is promoted
add-only like any other pending fact, and both fields are left exactly as they were.

`rule` is the manual tool of FR-OPS-07 and is unchanged: under the canoniser with
`X-Actor: human`, `accept` writes the payload even over a different value -- the one path that
can overwrite canon -- and records what it overwrote in `existing_value`; `reject` marks the
fact rejected. No turn calls it.

**What cannot be promoted is refused.** A target entity that does not exist, a field the record
does not have, a field no single string can fill (an integer date, a list of arc entries, the
`id` itself), a payload that asserts nothing (no word at all), or a payload that fails the
field's own validation is a 422 `InvalidRecord` naming `ledger/proposed.yaml` and the offending
field of the fact, and nothing is written. The URL named a fact that exists, so a 404 would
mislead; what is wrong is the content of the queued record, which is precisely what a 422
naming file and field tells a caller to go and fix. Settling these as "not applied" instead
would hide a fact that no promotion could ever write behind a status that means the record
already says it.

**Write order is canon first, queue second**, in both functions. If the process dies between
the two, the fact is still `pending` and the target already holds the payload, so the next
`promote` finds it there (contained in the text, already in the list, the same key with the
same value, the same identifier) and settles the fact with no second write. The other order
could mark a fact `promoted` whose payload never reached canon, and nothing would ever notice.
"""

from __future__ import annotations

import re
import types
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Final, Union, get_args, get_origin

from pydantic import ValidationError
from pydantic.fields import FieldInfo

from app.canon import service as canon_service
from app.canon.service import CanonEntity
from app.cast import service as cast_service
from app.cast.models import Character
from app.commons.errors import InvalidRecord, NotFound, PermissionDenied
from app.commons.permissions import Actor, AgentRole, may_write
from app.commons.schemas import (
    FactStatus,
    ProposedFact,
    ProposedFile,
    Ruling,
    RulingKind,
    Scene,
)
from app.commons.stores import Store, paths
from app.commons.stores.provenance import ProvenanceRecord, now
from app.ledger import repository
from app.ledger.models import Promoted, RulingApplied

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

_ATOMIC_FIELDS: Final[frozenset[tuple[str, str]]] = frozenset({(Character.__name__, "name")})
"""FR-OPS-06, AC 13. Scalar fields that hold one indivisible value and so are never appended
to, keyed by `(model name, attribute)`. A pattern-constrained string (an identifier such as
`Location.parent`) is atomic by its annotation (`_has_pattern`); a name carries no pattern, so
it is listed here. Appending a clause to a character's name would change the name every
document shows."""

CLAUSE_SEPARATOR: Final[str] = "; "
"""FR-OPS-06, AC 13. What joins a new detail to the text a scalar field already holds."""

_WORD: Final[re.Pattern[str]] = re.compile(r"\w+")
_KEY_SEPARATORS: Final[re.Pattern[str]] = re.compile(r"[\s_-]+")


class FieldShape(StrEnum):
    """The three shapes a promotable field has, and so the three ways `promote` fills it."""

    SCALAR = "scalar"
    """One string: set when empty; otherwise the payload is appended as one more clause,
    unless the text already says it. An identifier or a name is never appended to."""
    LIST = "list"
    """A list of strings: the payload is appended as one more item unless already present."""
    MAPPING = "mapping"
    """A string-to-string map: the payload is written `key: value`; only a new key is added."""


@dataclass(frozen=True, slots=True)
class _Target:
    """The record a fact addresses, where it lives, and the attribute and shape of its field."""

    path: str
    record: TargetRecord
    attribute: str
    shape: FieldShape
    atomic: bool = False
    """A scalar that holds one indivisible value -- an identifier or a name -- and so is set
    once and never appended to (`_is_atomic`)."""


@dataclass(frozen=True, slots=True)
class _Addition:
    """FR-OPS-06, AC 13. What `promote` adds to the field: add-only, never a replacement.

    `value` is the field's new value, or `None` when nothing is written. `applied` is false
    when the record already specifies what the fact addresses (a different identifier or name,
    a key the record already has with another value); `value` is then `None` too, and the fact
    is settled `rejected` with no ruling.
    """

    value: FieldValue | None
    applied: bool = True


_UNCHANGED: Final[_Addition] = _Addition(None)
"""Canon already holds the payload: the fact is promoted and only the queue is written."""

_NOT_APPLIED: Final[_Addition] = _Addition(None, applied=False)
"""The record already specifies this: the fact is rejected and only the queue is written."""


@dataclass(frozen=True, slots=True)
class _Change:
    """What a human ruling's `accept` does to the field (`rule`, FR-OPS-07).

    `value` is the field's new value, or `None` when canon already holds the payload. `existing`
    is the differing value the target holds -- set only when the accepted payload replaces it --
    in the same textual shape as the payload, so what the human overwrote stays readable.
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


def _shape_of(annotation: object) -> FieldShape | None:
    """The field's shape, from its annotation, or `None` when a string payload cannot fill it.

    Constrained strings (`EntityId`) are strings: the constraint is enforced when the new value
    is assigned (`_updated`), not guessed at here.
    """
    bare = _unwrap(annotation)
    if bare is str:
        return FieldShape.SCALAR
    origin = get_origin(bare)
    arguments = tuple(_unwrap(argument) for argument in get_args(bare))
    if origin in _UNION_ORIGINS and set(arguments) == {str, type(None)}:
        return FieldShape.SCALAR
    if origin is list and arguments == (str,):
        return FieldShape.LIST
    if origin is dict and arguments == (str, str):
        return FieldShape.MAPPING
    return None


def field_shape(attribute: str, info: FieldInfo) -> FieldShape | None:
    """The one test of whether a fact may target a field, and how the field is filled.

    `None` for an identifier or `schema_version` (`_UNPROMOTABLE`) and for a field no single
    string can fill. `_locate` refuses a fact by this test and `promotable_fields` lists the
    fields that pass it, so what promotion can write and what extraction is told it may
    target (FR-AGENT-05) are one computation, never two lists that can drift apart.
    """
    if attribute in _UNPROMOTABLE:
        return None
    return _shape_of(info.annotation)


def _constrained(constraints: Iterable[object]) -> bool:
    """True when one of the constraints is a pattern (`Field(pattern=...)` carries it as
    metadata with a `pattern` attribute)."""
    return any(isinstance(getattr(item, "pattern", None), str) for item in constraints)


def _has_pattern(annotation: object) -> bool:
    """True when a string annotation carries a pattern constraint, as an identifier does
    (`EntityId`), through `Annotated` and `Optional` alike."""
    origin = get_origin(annotation)
    if origin is Annotated:
        bare, *extras = get_args(annotation)
        for extra in extras:
            if _constrained(extra.metadata if isinstance(extra, FieldInfo) else [extra]):
                return True
        return _has_pattern(bare)
    if origin in _UNION_ORIGINS:
        return any(_has_pattern(argument) for argument in get_args(annotation))
    return False


def _is_atomic(model: type[TargetRecord], attribute: str, info: FieldInfo) -> bool:
    """FR-OPS-06, AC 13. Whether a scalar field holds one indivisible value: an identifier (a
    pattern constraint on the field or in its annotation) or a name (`_ATOMIC_FIELDS`). Such a
    field is set once and never appended to."""
    return (
        (model.__name__, attribute) in _ATOMIC_FIELDS
        or _constrained(info.metadata)
        or _has_pattern(info.annotation)
    )


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


def _model_of(kind: str) -> type[TargetRecord]:
    """The record model a `_candidate_paths` kind is read as: a canon kind's, or the dossier's."""
    return Character if kind == "cast" else canon_service.CANON_MODELS[kind]


# --------------------------------------------------------------------------------------
# What a fact may target -- read-only, derived from the same tests `promote` applies
# --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PromotableField:
    """FR-OPS-06, FR-AGENT-05. One field a proposed fact may name as `target_field`.

    `name` is the key the record carries on disk (the alias where the model has one) and
    `attribute` the model's own name; `promote` resolves either. `meaning` is the field's
    Pydantic description on one line: the code's statement of what the field holds, not store
    content.
    """

    name: str
    attribute: str
    shape: FieldShape
    meaning: str


@dataclass(frozen=True, slots=True)
class PromotableTarget:
    """FR-OPS-06, FR-AGENT-05. One existing record a proposed fact may name as `target_entity`,
    and the fields `promote` can fill on it. `record_type` is the model's name (`Location`,
    `Character`); `path` is the one file `promote` would write."""

    entity: str
    record_type: str
    path: str
    fields: tuple[PromotableField, ...]

    def field(self, wanted: str) -> PromotableField | None:
        """The field a fact's `target_field` names, by disk name or attribute, as `_locate`
        resolves it; `None` when `promote` would refuse the name."""
        return next((item for item in self.fields if wanted in {item.name, item.attribute}), None)


def _meaning(info: FieldInfo) -> str:
    """The field's description, whitespace collapsed to one line."""
    return " ".join((info.description or "").split())


def promotable_fields(model: type[TargetRecord]) -> tuple[PromotableField, ...]:
    """FR-OPS-06, FR-AGENT-05. Every field of `model` that passes `field_shape`, in the model's
    declaration order: exactly the fields `_locate` does not refuse."""
    fields: list[PromotableField] = []
    for attribute, info in model.model_fields.items():
        shape = field_shape(attribute, info)
        if shape is not None:
            name = info.alias or attribute
            fields.append(PromotableField(name, attribute, shape, _meaning(info)))
    return tuple(fields)


def promotable_targets(store: Store, entities: Iterable[str]) -> tuple[PromotableTarget, ...]:
    """FR-OPS-06, FR-AGENT-05. Of `entities`, the ones `promote` can resolve, each once and in
    the order given, with the fields it can fill on each.

    An identifier is kept when exactly one record holds it -- a canon entity of one of the five
    kinds, or a character's dossier -- which is `_locate`'s own resolution (`_candidate_paths`).
    One that no record holds (a lexicon term, an unknown id) or that two kinds both hold is
    left out, because `promote` refuses a fact addressed to it. Reads existence only; writes
    nothing.
    """
    targets: list[PromotableTarget] = []
    seen: set[str] = set()
    for entity in entities:
        if entity in seen:
            continue
        seen.add(entity)
        candidates = _candidate_paths(store, entity)
        if len(candidates) != 1:
            continue
        [(kind, relative)] = candidates
        model = _model_of(kind)
        targets.append(PromotableTarget(entity, model.__name__, relative, promotable_fields(model)))
    return tuple(targets)


def _body_as_of(store: Store, record: Character, scene_id: str) -> dict[str, str] | None:
    """FR-OPS-07. The character's body as of `scene_id` (`cast_service.body_at`), the value a
    human ruling's `accept` compares a body fact with; `None` when the scene record or the
    character's `changes.yaml` is absent -- then only the stored map can be compared. `promote`
    does not use it: add-only never compares a value it would replace. Reads only."""
    scene_path = paths.scene(scene_id)
    if not store.exists(scene_path) or not store.exists(paths.cast_file(record.id, "changes")):
        return None
    at = store.read(scene_path, Scene).story_time
    try:
        return cast_service.body_at(store, record.id, at)
    except NotFound:
        return None


def _registered_keys(store: Store, target: _Target) -> frozenset[str]:
    """Invariant 3, FR-OPS-06, AC 13. The normalised `attribute` of every ChangeEvent registered
    for the target character, at any scene, when the fact targets the character's body; empty
    for every other target. A missing `changes.yaml` registers nothing -- a character with no
    change has no file -- rather than a `NotFound` that would stop the promotion. Reads only."""
    record = target.record
    if not isinstance(record, Character) or target.shape is not FieldShape.MAPPING:
        return frozenset()
    if not store.exists(paths.cast_file(record.id, "changes")):
        return frozenset()
    changes = cast_service.read_changes(store, record.id).changes
    return frozenset(_key(change.attribute) for change in changes if change.character == record.id)


def _locate(store: Store, fact: ProposedFact, index: int) -> _Target:
    """Resolve `target_entity` to one record and `target_field` to one of its fields.

    Refused with `InvalidRecord` when the entity exists nowhere, when two kinds both hold a
    file of that id (the fact does not say which it meant), when the record has no such field,
    and when the field is not promotable. See the module docstring for why each is a 422.
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
        shape = field_shape(attribute, info)
        if shape is None:
            message = (
                f"{relative} field {wanted!r} cannot be filled by a promoted fact; change it "
                "through the owning role's PUT route instead"
            )
            raise InvalidRecord(message, file=PROPOSED, field=f"proposed.{index}.target_field")
        atomic = shape is FieldShape.SCALAR and _is_atomic(type(record), attribute, info)
        return _Target(relative, record, attribute, shape, atomic)

    message = f"{relative} has no field {wanted!r}"
    raise InvalidRecord(message, file=PROPOSED, field=f"proposed.{index}.target_field")


# --------------------------------------------------------------------------------------
# Computing the change -- pure. `promote` adds (`_addition`); `rule` decides (`_compute_ruling`)
# --------------------------------------------------------------------------------------


def split_mapping_payload(payload: str) -> tuple[str, str] | None:
    """`key: value`, split on the first colon, or `None` when either half is missing. Pure; the
    canoniser's check of a mapping payload (FR-AGENT-05) and `promote` both use it."""
    key, separator, value = payload.partition(":")
    key, value = key.strip(), value.strip()
    if not separator or not key or not value:
        return None
    return key, value


def _split_mapping_payload(payload: str, index: int) -> tuple[str, str]:
    """`key: value`, split on the first colon. A payload without both halves asserts nothing a
    mapping can hold, and guessing a key would be inventing canon."""
    split = split_mapping_payload(payload)
    if split is None:
        message = (
            f"the payload {payload!r} targets a mapping field and must be written "
            "`key: value`, with both halves non-empty"
        )
        raise InvalidRecord(message, file=PROPOSED, field=f"proposed.{index}.payload")
    return split


def normalised_words(text: str) -> list[str]:
    r"""FR-OPS-06, AC 13. The words promotion compares: compatibility-normalised, case-folded
    `\w+` runs of the text. What "already contains" and "the same value" mean for `promote`.
    Kept apart from the canoniser's `normalise_payload`, which keys `proposal_id` and must not
    move: changing it would re-identify every fact already queued."""
    return _WORD.findall(unicodedata.normalize("NFKC", text).casefold())


def _key(name: str) -> str:
    """FR-OPS-06. A mapping key as compared: case-folded, runs of space, `_` and `-` equal."""
    folded = unicodedata.normalize("NFKC", name).casefold()
    return _KEY_SEPARATORS.sub(" ", folded).strip()


def _contains(text: str, words: list[str]) -> bool:
    """FR-OPS-06. True when `words` form a contiguous run of the text's words: word-bounded, so
    `red` is not contained in `reddish`, while case and punctuation do not count."""
    held = normalised_words(text)
    size = len(words)
    return any(held[start : start + size] == words for start in range(len(held) - size + 1))


def _asserted_words(value: str, index: int) -> list[str]:
    """The words of a payload that must assert something. One with no word at all -- only
    punctuation or symbols -- would be "contained" in any text and settle as promoted while
    adding nothing, so it is refused as a 422 on the payload instead."""
    words = normalised_words(value)
    if not words:
        message = f"the payload {value!r} asserts nothing: it holds no word"
        raise InvalidRecord(message, file=PROPOSED, field=f"proposed.{index}.payload")
    return words


def _is_empty(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _addition(target: _Target, payload: str, index: int, registered: frozenset[str]) -> _Addition:
    """FR-OPS-06, AC 13. What the payload adds to the field, add-only (module docstring).

    Nothing canon holds is ever replaced: a scalar is set when empty and otherwise extended by
    one clause, a list by one item, a mapping by one new key. Equality is tested before "already
    specified", so a payload canon already holds -- the same identifier, the same key with the
    same value, words the text already contains -- settles as promoted with no write, which is
    also what lets a promotion that died between its two writes settle on resume.
    `registered` is `_registered_keys`: the body keys a ChangeEvent names.
    """
    current: object = getattr(target.record, target.attribute)

    if target.shape is FieldShape.LIST:
        items = [str(item) for item in current] if isinstance(current, list) else []
        return _UNCHANGED if payload in items else _Addition([*items, payload])

    if target.shape is FieldShape.MAPPING:
        key, value = _split_mapping_payload(payload, index)
        words = _asserted_words(value, index)
        held = (
            {str(name): str(entry) for name, entry in current.items()}
            if isinstance(current, dict)
            else {}
        )
        stored = next((name for name in held if _key(name) == _key(key)), None)
        if stored is not None:
            return _UNCHANGED if normalised_words(held[stored]) == words else _NOT_APPLIED
        if _key(key) in registered:
            return _NOT_APPLIED
        return _Addition({**held, key: value})

    words = _asserted_words(payload, index)
    if target.atomic:
        _updated(target, payload, index)  # the bare payload must fit, even when not applied
    if _is_empty(current):
        return _Addition(payload)
    existing = str(current)
    if target.atomic:
        return _UNCHANGED if normalised_words(existing) == words else _NOT_APPLIED
    if _contains(existing, words):
        return _UNCHANGED
    return _Addition(f"{existing.rstrip()}{CLAUSE_SEPARATOR}{payload.strip()}")


def _compute_ruling(
    target: _Target, payload: str, index: int, held: dict[str, str] | None
) -> _Change:
    """FR-OPS-07. What a human's `accept` writes: the payload, over a different value if need be.

    Values are compared exactly, whitespace and case included, so what the human overwrote is
    recorded whenever it differs at all. For a character's body the value compared is `held`,
    the body as of the fact's scene (`_body_as_of`), falling back to the stored value for a key
    the as-of body withholds. `promote` never uses this: it only adds (`_addition`).
    """
    current: object = getattr(target.record, target.attribute)

    if target.shape is FieldShape.SCALAR:
        if _is_empty(current):
            return _Change(payload, None)
        existing = str(current)
        return _Change(None, None) if existing == payload else _Change(payload, existing)

    if target.shape is FieldShape.LIST:
        items = [str(item) for item in current] if isinstance(current, list) else []
        return _Change(None, None) if payload in items else _Change([*items, payload], None)

    key, value = _split_mapping_payload(payload, index)
    held_map = (
        {str(name): str(entry) for name, entry in current.items()}
        if isinstance(current, dict)
        else {}
    )
    # A key the as-of body withholds (a change that cannot be placed) falls back to the stored
    # value, never to "absent".
    reference = {**held_map, **held} if held is not None else held_map
    if key not in reference:
        return _Change({**held_map, key: value}, None)
    if reference[key] == value:
        return _Change(None, None)
    return _Change({**held_map, key: value}, f"{key}: {reference[key]}")


def _updated(target: _Target, value: FieldValue, index: int) -> TargetRecord:
    """The target record with the field replaced, validated by the record's own model.

    Store records validate on assignment (`HarnessModel`), so a payload that breaks the field's
    constraint -- an `EntityId` pattern, say -- is caught here as a 422 on the payload, before
    any write and before the fact could be settled as anything.
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
) -> Promoted:
    """FR-OPS-06, AC 13. Add one pending fact to canon, add-only: never overwrites, never
    escalates (module docstring).

    Always answers `Promoted`, and `fact.status` says what happened: `promoted` when canon now
    holds the payload -- `changed` says whether this call wrote it -- or `rejected`, with no
    `ruling`, when the record already specifies what the fact addresses and nothing outside
    `ledger/proposed.yaml` was written. `conflict` and `existing_value` are carried over as
    they were. `scene` and `turn` are passed through to both provenance lines (FR-STORE-04)
    when the orchestrator promotes inside a turn; an HTTP call supplies neither.
    """
    _require_canoniser(role, "promote")
    queue = repository.read_proposed(store)
    index = _find(queue, fact_id)
    fact = queue.proposed[index]
    _refuse_settled(fact, index)
    target = _locate(store, fact, index)
    addition = _addition(target, fact.payload, index, _registered_keys(store, target))
    updated = _updated(target, addition.value, index) if addition.value is not None else None
    _refuse_unless_permitted(role, target.path, PROPOSED)

    writes: list[ProvenanceRecord] = []
    if updated is not None:
        writes.append(
            store.write(target.path, updated, role=role, actor=actor, scene=scene, turn=turn)
        )
    status = FactStatus.PROMOTED if addition.applied else FactStatus.REJECTED
    settled = fact.model_copy(update={"status": status})
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
    return Promoted(
        fact=settled, target_path=target.path, changed=updated is not None, writes=writes
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
    """FR-OPS-07, AC 13. A human's decision on a pending fact: `accept` writes the payload even
    over a different value, `reject` marks the fact rejected, and either way the ruling is
    recorded on the fact. A manual tool: no turn calls it, since promotion is add-only.

    **Refused for `actor: agent`** with `PermissionDenied` (403) before anything is read. This
    is the only path that can overwrite canon, and it means nothing if a process may make the
    call as itself. The header is trusted in v1 (Decision 3, AC 25); what this guarantees is
    that the orchestrator, which always sends `agent`, can never overwrite canon on its own.

    An accepted payload that overwrites a different value also sets `conflict` and
    `existing_value` on the fact, so what the human overwrote stays readable on the record the
    decision was taken about.
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
    held = (
        _body_as_of(store, target.record, fact.source_scene)
        if isinstance(target.record, Character) and target.shape is FieldShape.MAPPING
        else None
    )
    change = _compute_ruling(target, fact.payload, index, held)
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


__all__ = [
    "FieldShape",
    "PromotableField",
    "PromotableTarget",
    "field_shape",
    "normalised_words",
    "promotable_fields",
    "promotable_targets",
    "promote",
    "rule",
    "split_mapping_payload",
]
