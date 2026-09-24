"""DR-01, DR-10. The ledger's own records and the answers of its two operations.

`ledger/timeline.yaml` -- the two temporal axes of the book. The storage layout gives this file
one line -- "story axis <-> discourse axis" -- and Figure 3 hands it to the auditor as an
input. It lives in this feature rather than in `commons/schemas/` because DR-01 puts a record
read by one feature in that feature's `models.py`, and the reader is the ledger: the
mechanical audit of plan step 14 is `app/ledger/audit/`.

`Promoted`, `Escalation`, `RuleRequest` and `RulingApplied` are the wire shapes of
`POST /ledger/proposed/{id}/promote` and `.../rule` (IF-05, FR-OPS-06, FR-OPS-07). They are
not store records -- nothing writes them to disk -- but the orchestrator of plan step 18 reads
them to record what became of each fact of a turn, so they are the public surface of the
operation and live here rather than inside the module that computes them.

Promotion is add-only (FR-OPS-06, AC 13): `promote` always answers `Promoted`, and a client
reads `fact.status` -- `promoted` when canon holds the payload, `rejected` with no ruling when
the record already specified it -- never `outcome` alone. `Escalation` stays in the contract
(IF-05) and in the discriminated `PromotionResult`, unused: no v1 promotion returns one. The
emitted descriptions of these models predate the add-only design and are left as they are so
the committed OpenAPI document does not move; spec 001 lists them for regeneration.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.commons.schemas.common import (
    HarnessModel,
    Order,
    RulingKind,
    SceneId,
    StoreDocument,
    StoryHours,
)
from app.commons.schemas.proposed import ProposedFact
from app.commons.stores.provenance import ProvenanceRecord


class TimelineEntry(HarnessModel):
    """`definitions.md` TemporalAxes `mapping`: one scene's place on both axes at once.

    The three fields are the correspondence itself. `story_time` says when the scene happens
    and `discourse_order` says when the reader meets it, and holding them side by side is what
    makes the distance between the two measurable rather than felt.
    """

    scene: SceneId = Field(description="The scene this entry places on both axes.")
    story_time: StoryHours = Field(
        description="Hours since `epoch_zero` in `canon/time.yaml` (Decision 8). May be"
        " negative: a prequel scene happens before the origin without being unreadable.",
    )
    discourse_order: Order = Field(
        description="1-based position in reading order. FR-AUD-08 measures thread latency as a"
        " distance in this number, because a subplot vanishes from the page, not from history.",
    )


class TimelineFile(StoreDocument):
    """DR-10. The whole of `ledger/timeline.yaml`: the story axis, the discourse axis, and the
    mapping between them.

    **Failure mode** (`definitions.md` TemporalAxes): a single axis. The moment the first
    flashback or the first relativistic ship appears, nothing can be validated any more -- a
    scene set two hundred hours earlier reads as a contradiction if the only order the system
    knows is the reader's, and a chapter that withholds an event reads as a gap in causality if
    the only order it knows is the world's. Consistency is verified against story time; tension
    is designed on discourse time; the two are kept apart here so that neither question can be
    asked of the wrong one.

    **Derived, and authoritative about nothing.** `story_time` and `discourse_order` live on
    `scenes/NNN.yaml` (DR-03), and those records are the authority. This file is the projection
    the auditor is handed (Figure 3) and the one page a reviewer can see both axes on. That is
    also why no route writes it: Figure 3's `Out` column names no role for `ledger/timeline.yaml`
    -- as it names none for `setups.yaml` or `threads.yaml` -- so IF-03 lists it as a read and
    IF-04 opens no write.

    The two axis lists are orderings of the same scenes and are stated rather than derived, so
    that a reader and a checker disagree in the open. That they really are permutations of
    `mapping`, sorted by `story_time` and by `discourse_order`, is a cross-record consistency
    question and belongs to `reconcile` (FR-OPS-08) and to the mechanical audit, not to a
    schema: refusing the file here would make it unwritable during the window in which a scene
    is being inserted.
    """

    story_axis: list[SceneId] = Field(
        default_factory=list,
        description="Scene ids in causal order, earliest `story_time` first. Every invariant of"
        " `definitions.md` runs over this axis.",
    )
    discourse_axis: list[SceneId] = Field(
        default_factory=list,
        description="Scene ids in reading order. Admits jumps, ellipsis and analepsis, which is"
        " exactly why it cannot double as the causal one.",
    )
    mapping: list[TimelineEntry] = Field(
        default_factory=list,
        description="The correspondence, scene by scene. Empty is legitimate for a book whose"
        " scenes have not been planned yet.",
    )


# --------------------------------------------------------------------------------------
# promote and rule (IF-05, FR-OPS-06, FR-OPS-07)
# --------------------------------------------------------------------------------------


class Promoted(BaseModel):
    """FR-OPS-06. The fact is canon now: its payload is in the target record, or already was.

    `changed` tells the two apart, because they are different events for everyone downstream.
    `changed: true` means bytes under `canon/` or `cast/` moved and `reconcile` has something to
    look for (plan step 18 runs it on every promoted target); `changed: false` means canon
    already said this -- an equal scalar, a list that already held the item, a mapping key that
    already had the value -- and only the queue entry was settled.

    `writes` is every provenance line the operation appended, in the order the writes landed:
    the target record first, `ledger/proposed.yaml` second. A reader of the log can therefore
    match a promotion to exactly the lines it produced (FR-STORE-04).
    """

    outcome: Literal["promoted"] = Field(
        default="promoted",
        description="Discriminator: the fact was promoted. The other answer is `escalation`.",
    )
    fact: ProposedFact = Field(description="The queue entry as it now stands on disk.")
    target_path: str = Field(description="The store file the payload was promoted into.")
    changed: bool = Field(
        description="True when the target record was rewritten; false when it already held"
        " the payload and only the queue entry was settled.",
    )
    writes: list[ProvenanceRecord] = Field(
        description="The provenance lines this promotion appended, in the order they landed.",
    )


class Escalation(BaseModel):
    """FR-OPS-06. The target already holds a different value, and nothing was overwritten.

    **Failure mode** (`architecture.md` ProposedFact): automatic promotion with no review. A
    collision is exactly the place a machine would have to guess which of two truths the novel
    holds, and a canoniser that guessed would fill canon with improvised noise until nobody
    consulted it. So the collision is recorded on the fact -- `conflict: true`, `existing_value`
    -- and handed to a human, who settles it with `rule` (FR-OPS-07). `canon/` and `cast/` are
    byte-identical after an escalation; `writes` holds at most the one line for
    `ledger/proposed.yaml`, and none when the collision was already on record.
    """

    outcome: Literal["escalation"] = Field(
        default="escalation",
        description="Discriminator: the fact collided and waits for a human ruling.",
    )
    fact: ProposedFact = Field(description="The queue entry as it now stands on disk.")
    target_path: str = Field(description="The store file the payload would have gone into.")
    payload: str = Field(description="What the fact asserts, verbatim.")
    existing_value: str | None = Field(
        description="What the target holds instead, as recorded on the fact. For a mapping"
        " field it is written `key: value`, the same shape as the payload, so the two can be"
        " compared side by side.",
    )
    reason: str = Field(description="Why the fact was not promoted, in one sentence.")
    writes: list[ProvenanceRecord] = Field(
        description="The provenance line for `ledger/proposed.yaml` when the collision was"
        " recorded by this call; empty when it was already on record.",
    )


PromotionResult = Annotated[Promoted | Escalation, Field(discriminator="outcome")]
"""IF-05: `POST /ledger/proposed/{id}/promote` answers `Promoted | Escalation`. Discriminated
on `outcome` so the committed OpenAPI document (IF-08) says which one a client is holding
without it having to probe for fields."""


class RuleRequest(BaseModel):
    """The body of `POST /ledger/proposed/{id}/rule` (FR-OPS-07).

    `reason` is required and non-empty because `Ruling.reason` is: a ruling without one is
    unreviewable, and the record of *why* something was refused is what stops the same
    invention being proposed and argued about again twenty scenes later. Unknown fields are
    refused rather than ignored, as on every request body in this feature.
    """

    model_config = ConfigDict(extra="forbid")

    ruling: RulingKind = Field(
        description="`accept` promotes the fact despite a collision; `reject` marks it"
        " rejected and leaves canon as it is.",
    )
    reason: str = Field(
        min_length=1,
        pattern=r"\S",
        description="Why. Recorded on the fact beside who ruled and when; blanks are refused.",
    )


class RulingApplied(BaseModel):
    """FR-OPS-07. What a human ruling did: the fact as it now stands, and what moved.

    On `accept`, `target_path` names the record the payload went into and `changed` says
    whether its bytes moved; when the payload overwrote a different value, the fact carries
    `conflict: true` and the overwritten value in `existing_value`, so the history of the
    decision survives on the record it was taken about. On `reject`, `target_path` is `None`
    and nothing outside `ledger/proposed.yaml` was touched -- a rejection does not even resolve
    the target, so a fact about an entity that was never created can still be turned down.
    """

    fact: ProposedFact = Field(description="The queue entry, with its `ruling` recorded.")
    ruling: RulingKind = Field(description="The decision that was applied.")
    target_path: str | None = Field(
        description="The record an accepted payload went into; `None` for a rejection.",
    )
    changed: bool = Field(
        description="True when the target record was rewritten; always false for a rejection.",
    )
    writes: list[ProvenanceRecord] = Field(
        description="The provenance lines this ruling appended, in the order they landed.",
    )


__all__ = [
    "Escalation",
    "Promoted",
    "PromotionResult",
    "RuleRequest",
    "RulingApplied",
    "TimelineEntry",
    "TimelineFile",
]
