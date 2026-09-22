"""DR-04. Who knows what, and from which exact scene.

`cast/{id}/knowledge.yaml` is the file this module types. It is a document with a named
key rather than a bare YAML list because DR-10 puts `schema_version` on every file, and a
top-level list has nowhere to carry one.

The whole point of the shape is that knowledge is *dated*. A row without `acquired_in` is
unanswerable: it can say that a character knows something, but not whether they could have
known it in the scene being written, which is the only question the harness is ever asked.
"""

from __future__ import annotations

from pydantic import Field

from app.commons.schemas.common import (
    Certainty,
    EntityId,
    HarnessModel,
    SceneId,
    StoreDocument,
    Via,
)


class KnowledgeState(HarnessModel):
    """DR-04. One character's standing on one fact, anchored to the scene that created it.

    `definitions.md` calls this the highest-value entity in the system, and the reason is
    arithmetic rather than sentiment: most serious continuity errors in a long novel are
    characters who know something they could not yet have learned. Every other entity can
    be wrong in a way a reader forgives; this one cannot.

    **Failure mode: modelling it as a boolean.** A `knows: bool` collapses five distinct
    states into two, and the one it destroys first is `believes_falsely` - which is not a
    degraded `knows` but the opposite dramatic device. Without it you cannot write
    deception, and you cannot write dramatic irony at all, because both consist precisely
    of a character holding a confident belief the reader knows to be false. `suspects` and
    `believes` are the graduations between, and `via` records how the state was reached, so
    that a fact a character deduced can be told apart from one they were told - the
    difference between a deduction that can be wrong and a lie that was planted.

    **FR-OPS-01.** `dossier(character, at=T)` includes a row only when the scene named by
    `acquired_in` has `story_time <= T`. The filtering is done on the *scene's* story time,
    not on any field here, which is why `acquired_in` is a scene id and not a timestamp: a
    scene can be re-dated on the story axis without every knowledge row having to be
    rewritten behind it.
    """

    character: EntityId = Field(description="Whose knowledge this is.")
    fact_ref: EntityId = Field(description="The canon entity this state is held about.")
    acquired_in: SceneId = Field(
        description="Scene where the state was reached; before it, the character is unaware.",
    )
    via: Via = Field(description="How it was acquired: witnessed, was told, deduced, suspects.")
    certainty: Certainty = Field(
        description="One of the five values; never a boolean (DR-04, AC 5).",
    )
    may_tell: list[EntityId] = Field(
        default_factory=list,
        description="Characters this one is socially free to disclose the fact to; empty means"
        " no constraint has been recorded, not that disclosure is forbidden.",
    )


class KnowledgeFile(StoreDocument):
    """DR-04, DR-10. The whole of `cast/{id}/knowledge.yaml`.

    The rows are not keyed by `fact_ref`, because a character can hold successive states on
    the same fact - `suspects` at scene 012, `knows` at scene 031 - and a mapping would
    force the earlier one out. A list keeps the history that FR-OPS-01 reads as-of.
    """

    knowledge: list[KnowledgeState] = Field(
        default_factory=list,
        description="Every recorded state for this character, in no significant order;"
        " as-of queries order by the story time of `acquired_in`.",
    )


__all__ = [
    "KnowledgeFile",
    "KnowledgeState",
]
