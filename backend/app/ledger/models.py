"""DR-01, DR-10. The two temporal axes of the book: `ledger/timeline.yaml`.

The storage layout gives this file one line -- "story axis <-> discourse axis" -- and Figure 3
hands it to the auditor as an input. It had no model until now, which meant the one file in
the tree whose whole subject is the difference between two orderings was the one file nothing
could validate.

It lives in this feature rather than in `commons/schemas/` because DR-01 puts a record read by
one feature in that feature's `models.py`, and the reader is the ledger: the mechanical audit
of plan step 14 is `app/ledger/audit/`, and the invariants that run over the story axis run
there.
"""

from __future__ import annotations

from pydantic import Field

from app.commons.schemas.common import (
    HarnessModel,
    Order,
    SceneId,
    StoreDocument,
    StoryHours,
)


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


__all__ = [
    "TimelineEntry",
    "TimelineFile",
]
