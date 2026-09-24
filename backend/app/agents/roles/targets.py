"""What a proposed fact may address, as an instruction states it (FR-AGENT-01, FR-AGENT-05,
FR-OPS-06, AC 27).

Two roles propose facts: the writer reports its own inventions as it drafts, and the canoniser
reads the accepted prose for what it asserts. Both proposals end at `promote`, which sets one
field of one existing record and refuses anything else. A role that is not told which records
exist and which fields each has invents addresses (a field named after the answer, an object
that has no record), and a fact aimed at an address that does not exist can never be promoted.
So both instructions carry the same list, rendered here once.

**Everything listed is derived by code.** The records and their fields come from
`app.ledger.service.promotable_targets`, the tests `promote` itself applies; each field's
meaning is its Pydantic description (`PromotableField.meaning`). Two code-owned tables add
what a description does not say, and both are keyed by the record models themselves, so they
are the same for every novel and cannot name a store entity:

* `RECORD_NOTES` -- what one record of each type is, in a line, so a model can tell which
  record an assertion is *about* (a rule, a place, a device) rather than where it happens.
* `FIELD_NOTES` -- how one item of a field is read, where the description only says what the
  field must not be (an axiom's `exceptions` is described by what an exception is not).

Only identifiers and these code-owned sentences enter an instruction, never store text
(FR-PERM-07). `test_roles` checks that every key of both tables is a real record type and a
promotable field of it, so a renamed field breaks a test rather than drifting silently.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from typing import Final

from app.canon.models import Axiom, Faction, HistoricalEvent, Location, Technology
from app.cast.models import Character
from app.ledger.service import FieldShape, PromotableTarget

SHAPE_RULES: Final[Mapping[FieldShape, str]] = {
    FieldShape.SCALAR: "the payload is its one value",
    FieldShape.LIST: "the payload is one more item, one fact per item",
    FieldShape.MAPPING: 'the payload is written "key: value", the key naming what is set',
}
"""How each of `promote`'s three field shapes takes a payload (FR-OPS-06), as the instruction
states it once before the list; each field is then marked with its shape."""

FIELD_RULE: Final[str] = (
    "target_field must be one of the fields listed for that record: choose the field whose "
    "meaning fits the assertion, and do not invent fields."
)
"""The rule the instruction states after the list; `prompts/canoniser.md` states it too."""

ABOUT_RULE: Final[str] = (
    "Address each fact to the record the assertion is about, not to the record of the place "
    "where it happens. Something new that has no record of its own is asserted as a fact "
    "about the listed record it belongs to or is found in."
)
"""FR-AGENT-01, FR-AGENT-05. Which record: the first live run filed a relaxed rule under the
place it was relaxed in, and a writer addressed an object that has no record."""

RECORD_NOTES: Final[Mapping[str, str]] = {
    Axiom.__name__: (
        "one rule of the world: what is the case, what follows from it and what it forbids, "
        "the cases it does not cover, and what using it costs"
    ),
    Technology.__name__: (
        "one device or system: what it can and cannot do, how it fails, who has it and how it "
        "feels in use"
    ),
    Location.__name__: (
        "one place: what it is like to be in, what constrains movement and sight in it, and "
        "how one gets there"
    ),
    Faction.__name__: (
        "one collective agent: what it says it wants, what it is really after, and what it "
        "can mobilise"
    ),
    HistoricalEvent.__name__: (
        "one event from before the story: the version told in public and what actually happened"
    ),
    Character.__name__: (
        "one person: the body that does not change without a registered change, what they "
        "want and need, the lie they believe about themselves, and what they can do"
    ),
}
"""What one record of each promotable type is, keyed by the model's name
(`PromotableTarget.record_type`)."""

FIELD_NOTES: Final[Mapping[tuple[str, str], str]] = {
    (Axiom.__name__, "exceptions"): (
        "One item is one case the rule does not cover as stated: a circumstance in which it is "
        "relaxed, suspended or does not apply, written with the condition that bounds it. "
        "Such a case belongs here, on the record of the rule it relaxes, whether "
        "the prose narrates it or a character states it."
    ),
}
"""How one item of a field is read, keyed by `(record type, field name)`, where the field's
description says what the field must not be rather than what it holds."""


def _field_lines(target: PromotableTarget) -> list[str]:
    """One line per promotable field of the target's record type, each with its shape and its
    meaning, and a code-owned note on the next line where `FIELD_NOTES` has one."""
    lines: list[str] = []
    for field in target.fields:
        lines.append(f"- {field.name} [{field.shape.value}]: {field.meaning}")
        note = FIELD_NOTES.get((target.record_type, field.name))
        if note is not None:
            lines.append(f"  How one item is read: {note}")
    return lines


def render_targets(
    targets: Sequence[PromotableTarget],
    *,
    hidden: Collection[str] = (),
    meanings: bool = True,
) -> list[str]:
    """FR-AGENT-01, FR-AGENT-05, FR-OPS-06. The instruction's list of what a fact may address:
    per record type, what one such record is, the identifiers of that type and the fields
    `promote` can fill on it, each with its shape and its meaning.

    `hidden` names listed records whose documents the role is not given (the canoniser never
    reads a dossier). A model cannot see what such a record already holds, so a restatement of
    it in other words would collide with the record and hold the turn for a person; the list
    says so and asks only for what the scene shows new. Identifiers and code-owned sentences
    only (FR-PERM-07).

    `meanings=False` is the compact form the writer gets: per record type, the identifiers and
    the field names with their shapes on one line, without the notes and descriptions. The
    writer reads the records themselves as documents, so what it lacks is only which addresses
    exist; its instruction is counted in the mandatory part of every assembly, so it stays
    short."""
    if not targets:
        return [
            (
                "No record is open to a fact in this scene, since promotion never creates one: "
                "answer with an empty facts list."
            )
        ]
    groups: dict[str, list[PromotableTarget]] = {}
    for target in targets:
        groups.setdefault(target.record_type, []).append(target)
    legend = "; ".join(f"{shape.value}: {rule}" for shape, rule in SHAPE_RULES.items())
    lines = [
        (
            "A fact sets one field of one existing record; promotion never creates a record. "
            "target_entity must be one of these identifiers, and target_field one of the fields "
            "listed for its record type."
        ),
        f"Each field is marked with its shape ({legend}).",
    ]
    for record_type, members in groups.items():
        identifiers = ", ".join(member.entity for member in members)
        if not meanings:
            fields = ", ".join(f"{item.name} [{item.shape.value}]" for item in members[0].fields)
            lines.append(f"{record_type} records: {identifiers}. Their fields: {fields}.")
            continue
        lines.append(f"{record_type} records: {identifiers}. Their fields:")
        note = RECORD_NOTES.get(record_type)
        if note is not None:
            lines.append(f"  Each {record_type} record is {note}.")
        lines.extend(_field_lines(members[0]))
    unseen = [target.entity for target in targets if target.entity in hidden]
    if unseen:
        lines.append(
            "You are not given the documents of these listed records, so you cannot see what "
            f"they already hold: {', '.join(unseen)}. For them, propose only what this scene "
            "shows happening, changing or being learned in it, never a restatement in other "
            "words of how they already are."
        )
    lines.extend([FIELD_RULE, ABOUT_RULE])
    return lines


__all__ = [
    "ABOUT_RULE",
    "FIELD_NOTES",
    "FIELD_RULE",
    "RECORD_NOTES",
    "SHAPE_RULES",
    "render_targets",
]
