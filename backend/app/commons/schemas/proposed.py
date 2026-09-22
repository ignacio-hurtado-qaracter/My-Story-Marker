"""DR-07. The canonisation queue: `ledger/proposed.yaml`.

Every invented detail waits here before it is allowed to become canon. The file is a
document with a named key rather than a bare YAML list, because DR-10 puts `schema_version`
on the file.
"""

from __future__ import annotations

from pydantic import Field

from app.commons.schemas.common import (
    EntityId,
    FactStatus,
    HarnessModel,
    Ruling,
    SceneId,
    StoreDocument,
)


class ProposedFact(HarnessModel):
    """DR-07. A detail invented mid-draft, queued for review before it can reach canon.

    `architecture.md` calls this the entity most systems omit, and its absence is why details
    get lost and contradicted thirty chapters later. Prose invents constantly - a ship's
    name, a rank, the colour of a uniform - and none of it is in canon at the moment it is
    written. Without a queue the invention either vanishes, and the next scene invents
    something else, or it is written straight into canon by whatever produced it.

    **Failure mode** (`architecture.md`): automatic promotion with no review. Canon fills
    with improvised noise and stops being authoritative, at which point it is no longer worth
    consulting - and a canon nobody consults is a canon that constrains nothing, which is the
    whole system failing quietly rather than loudly.

    **FR-OPS-06.** `promote` never overwrites. When `target_entity.target_field` already
    holds a different value it sets `conflict`, records `existing_value`, leaves `status`
    pending and returns an `Escalation`; nothing on disk changes. The collision is the
    interesting case precisely because it is where a machine would have to guess which of two
    truths the novel holds, and that guess is not the canoniser's to make.

    **FR-OPS-07.** Only `rule`, under the canoniser role with `actor: human`, resolves one:
    `accept` promotes despite the collision, `reject` marks the fact rejected, and either way
    the decision and its reason are recorded in `ruling`. This is the human gate of
    `verification.md`, and the reason it is a field rather than a log line is that the next
    reader of this record needs to see who decided and why, not merely that something did.
    """

    id: EntityId = Field(description="Stable identifier; turn records name facts by it.")
    extracted_from: str = Field(
        min_length=1,
        description="The source draft the assertion was read out of, so a promotion can be"
        " traced back to the prose that claimed it.",
    )
    target_entity: EntityId = Field(description="The canon or cast record it would attach to.")
    target_field: str = Field(
        min_length=1,
        description="The field on that record the `payload` would fill; with `target_entity`"
        " it is the address a collision is detected at.",
    )
    payload: str = Field(
        min_length=1,
        description="The asserted value, as the prose has it.",
    )
    source_scene: SceneId = Field(
        description="The scene whose turn produced the assertion; dates it on the story axis"
        " through the scene record.",
    )
    conflict: bool = Field(
        default=False,
        description="Set by `promote` when the target already holds a different value. It is"
        " never cleared by code; only a human ruling settles it (FR-OPS-07).",
    )
    existing_value: str | None = Field(
        default=None,
        description="What the target already held, recorded at the moment of collision so the"
        " human ruling compares two stated values rather than one and a memory.",
    )
    status: FactStatus = Field(
        default=FactStatus.PENDING,
        description="`pending`, `promoted` or `rejected`. Pending is the default because"
        " nothing becomes canon without an act (FR-OPS-06).",
    )
    ruling: Ruling | None = Field(
        default=None,
        description="The human decision, with who, why and when; empty until `rule` is called.",
    )


class ProposedFile(StoreDocument):
    """DR-07, DR-10. The whole of `ledger/proposed.yaml`.

    The one store two roles append to: the writer proposes its own inventions as it drafts,
    and the canoniser adds what `extract_facts` finds in the accepted draft. FR-TURN-03 keeps
    the writer's proposals from every iteration, including the ones whose draft was revised
    away, because a rejected draft can still have invented a good name for something.

    Facts are kept after they are promoted or rejected rather than removed: the record of
    what was refused, and why, is what stops the same invention being proposed and argued
    about again twenty scenes later.
    """

    proposed: list[ProposedFact] = Field(
        default_factory=list,
        description="The whole queue, pending and settled; FR-TURN-04 promotes the pending"
        " non-colliding ones before the turn returns.",
    )


__all__ = [
    "ProposedFact",
    "ProposedFile",
]
