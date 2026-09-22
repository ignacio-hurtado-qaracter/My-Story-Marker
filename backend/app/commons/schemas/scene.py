"""DR-03. The scene record: `scenes/NNN.yaml`.

One module, one model, because the scene is the atomic unit of writing and the only unit
of context. Everything the harness does to produce a chapter is a function of this record:
selection reads it, assembly is anchored to it, and the mechanical invariants run over its
`story_time`, `location`, `pov` and `participants`.
"""

from __future__ import annotations

from pydantic import Field, model_validator

from app.commons.schemas.common import (
    EntityId,
    Order,
    Outcome,
    SceneId,
    StoreDocument,
    StoryHours,
    Words,
)


class Scene(StoreDocument):
    """DR-03. The whole of `scenes/NNN.yaml`, with the fields `definitions.md` Scene gives it.

    The dramatic fields are not prose for a human planner to read. FR-OPS-02 builds the
    selection query out of `goal`, `conflict`, `value_change`, `pov`, `location`,
    `entry_state`, `exit_state` and `notes`, and whatever that query retrieves is the world
    the writer is handed. A record whose conflict is "something goes wrong" matches nothing
    in particular, so the retrieval falls back to whatever ranked first, and the scene is
    written against generic material. The vagueness does not stay in the record; it becomes
    the context, and the context becomes the prose.

    **Failure mode** (`definitions.md` Scene): specifying the *how* as well as the *what*.
    The record states dramatic function - what the POV wants, what prevents it, which value
    moves and in which direction, how much room there is - and leaves execution free. An
    over-prescriptive record produces dead prose, because the writer then writes to satisfy
    the record rather than to write well.

    Two fields carry decisions rather than description. `story_time` is an integer count of
    hours since `epoch_zero` (Decision 8), not a date string, because invariants 4 and 5
    subtract it; and `participants` (Decision 9) exists so the spatial and transit checks
    have the full cast of the scene, not only its POV.

    `tags` and `pins` are two pinning mechanisms and not one. `tags` are domain tags matched
    against an Axiom's `scope`, so they are free text; `pins` name an entity by identifier, so
    they obey the identifier grammar. Collapsed into one field, whichever grammar wins makes
    the other mechanism unusable -- an axiom scoped `FTL` becomes unpinnable, or a pin stops
    resolving to a record (docs `aa05ee9`).
    """

    id: SceneId = Field(description="`NNN`, stable forever; the file is named after it.")
    pov: EntityId = Field(
        description="The single POV character; determines the knowledge trim of assembly.",
    )
    participants: list[EntityId] = Field(
        description=(
            "Characters present besides the POV. Required, and may be empty: invariants 4 "
            "and 5 run over `pov` plus this list, so a missing name is a check that "
            "silently does not run, and an omitted field would narrow both checks to the "
            "POV alone with nothing recording that it had happened. The POV is never "
            "repeated here and no character appears twice."
        ),
    )
    story_time: StoryHours = Field(
        description=(
            "When it happens in the world: integer hours since `epoch_zero` of the "
            "TemporalSystem. Negative is legal - prequel scenes exist."
        ),
    )
    discourse_order: Order = Field(
        description="Where the reader encounters it; the axis tension is designed on.",
    )
    location: EntityId = Field(description="A leaf of the location tree.")
    goal: str = Field(description="What the POV wants on entering.")
    conflict: str = Field(description="What prevents it.")
    outcome: Outcome = Field(description="How the scene answers the goal; the four-value enum.")
    value_change: str = Field(
        description=(
            "Which value moves, and in which direction. FR-AUD-06 reports an empty or "
            "unsigned value as `reviewable`, so this field is deliberately not constrained "
            "to be non-empty here: an inert scene must be readable in order to be reported."
        ),
    )
    entry_state: str = Field(description="The world as the scene opens; half of the delta.")
    exit_state: str = Field(
        description="The world as the scene closes; the verifiable other half of the delta.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description=(
            "Optional domain tags, free text in the world's own vocabulary. An axiom whose "
            "`scope` intersects them is pinned into the context regardless of ranking "
            "(FR-OPS-02). Free text on purpose: a scope written `FTL` could never be matched "
            "by a field constrained to the identifier grammar."
        ),
    )
    pins: list[EntityId] = Field(
        default_factory=list,
        description=(
            "Optional identifiers of entities that enter the context regardless of ranking, "
            "named directly rather than matched. FR-OPS-02 prepends them. This is the half "
            "of pinning that resolves to a record; `tags` is the half that matches a scope."
        ),
    )
    notes: str | None = Field(
        default=None,
        description=(
            "Free text for what the structured fields cannot hold. It feeds selection and "
            "never binds the writer."
        ),
    )

    @model_validator(mode="after")
    def _cast_is_well_formed(self) -> Scene:
        """`participants` is "characters present **besides** the POV" (`definitions.md`).

        Repeating the POV there, or naming anyone twice, makes invariants 4 and 5 walk the
        same character more than once for one scene. The checks would still be correct, and
        the duplicate would still be a record saying something the author did not mean.
        """
        if self.pov in self.participants:
            message = f"the POV {self.pov!r} must not be repeated in participants"
            raise ValueError(message)
        seen = self.participants
        duplicates = sorted({name for name in seen if seen.count(name) > 1})
        if duplicates:
            message = f"participants names a character more than once: {', '.join(duplicates)}"
            raise ValueError(message)
        return self
    budget: Words = Field(
        description="Assigned words; the turn records the draft's count against it.",
    )


__all__ = ["Scene"]
