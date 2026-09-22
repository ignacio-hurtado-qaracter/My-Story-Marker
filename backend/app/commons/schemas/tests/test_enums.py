"""AC 5 — every enum field in DR-04...07 rejects out-of-enum values and booleans.

The boolean half is the point. `definitions.md` names modelling KnowledgeState as a boolean
as its failure mode, and a validator that quietly accepted `true` for `certainty` would let
exactly that shape back in through the file format. The same test covers the strict integer
aliases, because pydantic's lax mode reads `true` as 1 and a `story_time` of hour 1 is the
kind of nonsense the invariants are supposed to catch.

Each enum is probed through a one-field model built at run time, and every probe goes through
`model_validate` with a mapping rather than a keyword argument: a dynamically built model has
no static signature, and writing one probe class per enum by hand would be eighteen classes
that all say the same thing.
"""

from __future__ import annotations

from enum import StrEnum

import pytest
from pydantic import ValidationError, create_model

from app.commons.schemas.common import (
    Certainty,
    DigestLevel,
    FactStatus,
    HarnessModel,
    Invariant,
    Order,
    Outcome,
    RulingKind,
    SetupResolution,
    Severity,
    StoryHours,
    ThreadState,
    Via,
    ViolationResolution,
    ViolationSource,
    Words,
)

ENUMS: list[type[StrEnum]] = [
    Certainty,
    DigestLevel,
    FactStatus,
    Outcome,
    RulingKind,
    Severity,
    SetupResolution,
    ThreadState,
    Via,
    ViolationResolution,
    ViolationSource,
]

REJECTED = ["definitely", "", "YES", True, False, 1, 0, None, 3.5, ["yes"]]


def probe(annotation: object) -> type[HarnessModel]:
    """A one-field model carrying `annotation`, so a bare type can be validated."""
    return create_model("Probe", __base__=HarnessModel, value=(annotation, ...))


# spec 001 / AC 5
@pytest.mark.parametrize("enum_type", ENUMS, ids=lambda e: e.__name__)
def test_every_member_is_accepted_by_its_own_value(enum_type: type[StrEnum]) -> None:
    model = probe(enum_type)
    for member in enum_type:
        assert model.model_validate({"value": member.value}).model_dump()["value"] == member


# spec 001 / AC 5
@pytest.mark.parametrize("enum_type", ENUMS, ids=lambda e: e.__name__)
@pytest.mark.parametrize("bad", REJECTED, ids=repr)
def test_out_of_enum_values_and_booleans_are_rejected(
    enum_type: type[StrEnum], bad: object
) -> None:
    if isinstance(bad, str) and bad in {member.value for member in enum_type}:
        pytest.skip("that string is a member of this enum")
    with pytest.raises(ValidationError):
        probe(enum_type).model_validate({"value": bad})


# spec 001 / AC 5 — a member added without a migration is a silent contract change.
@pytest.mark.parametrize("enum_type", ENUMS, ids=lambda e: e.__name__)
def test_enums_are_closed_and_string_valued(enum_type: type[StrEnum]) -> None:
    members = list(enum_type)
    assert len(members) >= 2
    assert all(isinstance(member.value, str) for member in members)


# spec 001 / AC 5
@pytest.mark.parametrize(
    "alias",
    [StoryHours, Order, Words, Invariant],
    ids=["StoryHours", "Order", "Words", "Invariant"],
)
@pytest.mark.parametrize("bad", [True, False, "1", 1.0], ids=repr)
def test_strict_integers_reject_booleans_and_coercible_lookalikes(
    alias: object, bad: object
) -> None:
    with pytest.raises(ValidationError):
        probe(alias).model_validate({"value": bad})


# spec 001 / AC 5
@pytest.mark.parametrize(
    ("alias", "bad"),
    [
        (Invariant, 0),
        (Invariant, 11),
        (Order, 0),
        (Order, -1),
        (Words, -1),
    ],
)
def test_bounded_aliases_reject_out_of_range(alias: object, bad: int) -> None:
    with pytest.raises(ValidationError):
        probe(alias).model_validate({"value": bad})


# spec 001 / AC 5 — the bounds accept what they should, so the test above is not vacuous.
@pytest.mark.parametrize(
    ("alias", "good"),
    [
        (Invariant, 1),
        (Invariant, 10),
        (Order, 1),
        (Words, 0),
        (StoryHours, -48),
    ],
)
def test_bounded_aliases_accept_their_edges(alias: object, good: int) -> None:
    assert probe(alias).model_validate({"value": good}).model_dump()["value"] == good
