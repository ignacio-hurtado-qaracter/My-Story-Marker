"""DR-05. The Chekhov ledger: `ledger/setups.yaml`.

A setup is a debt incurred with the reader. The file is a document with a named key rather
than a bare YAML list, because DR-10 puts `schema_version` on the file and a top-level list
has nowhere to carry one.
"""

from __future__ import annotations

from pydantic import Field

from app.commons.schemas.common import (
    EntityId,
    HarnessModel,
    SceneId,
    SetupResolution,
    StoreDocument,
)


class Setup(HarnessModel):
    """DR-05. One promise made to the reader, and how it stands.

    `definitions.md` Setup/Payoff calls these explicit pairs carrying an open obligation.
    The obligation is the point: a detail that merely appears is not a setup, and a setup
    that is never collected is not a mystery, it is a loose end. `promise` therefore records
    what the *reader* now expects rather than what was planted, because that is the thing
    invariant 2 asks about at the last scene.

    **Failure mode** (`definitions.md`): not distinguishing deliberate abandonment from
    forgetting. The two look identical on disk unless the decision is written down, so a
    checker without `resolution` reports every unpaid promise, including the ones a writer
    dropped on purpose. That is noise, and noisy checkers get ignored - which costs more
    than the check was ever worth, because a silenced invariant 2 is how a novel reaches its
    last chapter still owing the reader an answer.

    `due_by` is required for the same reason `max_latency` is required on a thread: an open
    debt with no deadline can never be late, so nothing ever reports it. With a deadline,
    FR-AUD-02 can say that a setup due at or before the current scene is still open, and
    escalate that from `reviewable` to `blocking` at the last scene.

    **FR-OPS-03** defines *open* as `paid_in` and `resolution` both empty, with `planted_in`
    at or before the story time being assembled. Open setups are offered to the writer under
    a *may collect* label, never as an instruction to pay a specific one: the writer decides
    whether this scene is where a debt comes due, and an assembler that instructed instead of
    offering would be planning the novel from inside the context window.
    """

    id: EntityId = Field(description="Stable identifier for the debt; the backend never renames.")
    planted_in: SceneId = Field(description="Scene where the promise is made to the reader.")
    promise: str = Field(
        min_length=1,
        description="What the reader now expects - the expectation, not the detail that"
        " created it; a promise nobody could state is one nobody can check as paid.",
    )
    paid_in: SceneId | None = Field(
        default=None,
        description="Scene where it was collected; empty while the debt remains open.",
    )
    due_by: SceneId = Field(
        description="Latest scene at which it can still be collected. Required (DR-05): a debt"
        " with no deadline is never late and so is never reported.",
    )
    resolution: SetupResolution | None = Field(
        default=None,
        description="`paid`, `subverted` or `deliberately_abandoned`; optional while `paid_in`"
        " is empty. `deliberately_abandoned` is a decision on record, not a forgotten promise.",
    )


class SetupsFile(StoreDocument):
    """DR-05, DR-10. The whole of `ledger/setups.yaml`.

    One file for the book rather than one per scene: a debt is planted in one scene and paid
    in another, so it belongs to neither, and splitting it by `planted_in` would put the
    half-written history of every promise in a different place from the question being asked.
    """

    setups: list[Setup] = Field(
        default_factory=list,
        description="Every reader debt, open and closed; FR-OPS-03 offers the open ones to the"
        " writer and FR-AUD-02 reports those past `due_by`.",
    )


__all__ = [
    "Setup",
    "SetupsFile",
]
