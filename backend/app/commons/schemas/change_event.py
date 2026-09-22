"""DR-08, Decision R2-5. Registered changes to things the model otherwise treats as fixed.

`cast/{id}/changes.yaml` is the file this module types: a document with a named key, not a
bare YAML list, because DR-10 needs `schema_version` on the file itself.

A ChangeEvent is what an `immutable_physical` attribute is measured against. Without the
record, invariant 3 has only two readings of a scar that appears in chapter nine - the body
changed, or the prose is wrong - and no way to choose between them.
"""

from __future__ import annotations

from pydantic import ConfigDict, Field

from app.commons.schemas.common import EntityId, HarnessModel, SceneId, StoreDocument


class ChangeEvent(HarnessModel):
    """DR-08. One registered change to a body or a memory.

    This is what lets a scar, an amputation, a memory wipe or a conditioning be told apart
    from a continuity error. Invariant 3 (stable bodies) asks that a physical attribute in
    the prose match `immutable_physical`; the exception it allows is exactly one of these,
    dated at or before the scene under audit. The same record covers the `Knows -> Unaware`
    edge of the knowledge lifecycle, which is why `attribute` is either an
    `immutable_physical` key or the `fact_ref` that was forgotten.

    **Failure mode: registering the change after the checker complains.** A ChangeEvent is
    a decision taken before the prose, not an excuse written after it. Nothing in the shape
    can enforce that - it is a discipline, and the provenance log is where it is visible -
    but it is the reason `cause` is required: a change with no cause is a plot hole with a
    receipt, and demanding the cause at write time is what makes the retrofit feel like
    what it is.

    `scene` dates the event on the story axis through the scene record. Before that scene
    the old value holds, which is what the auditor compares against.
    """

    # `from` and `to` are the field names `definitions.md` gives, and the keys the YAML on
    # disk carries. `from` is a Python keyword and `to` reads as one next to it, so the
    # Python attributes are suffixed and the wire names restored by alias. `populate_by_name`
    # keeps construction in code readable (`ChangeEvent(from_value=...)`) while the store
    # layer round-trips the documented keys.
    model_config = ConfigDict(populate_by_name=True)

    character: EntityId = Field(description="Whose body or memory changed.")
    attribute: str = Field(
        min_length=1,
        description="The `immutable_physical` key that changed, or the `fact_ref` forgotten.",
    )
    from_value: str = Field(
        alias="from",
        description="The value before the change; for a forgotten fact, what was believed.",
    )
    to_value: str = Field(
        alias="to",
        description="The value after the change; empty for a forgotten fact.",
    )
    scene: SceneId = Field(
        description="Where it happens; before this scene on the story axis, the old value holds.",
    )
    cause: str = Field(
        min_length=1,
        description="What did it; a change with no cause is a plot hole with a receipt.",
    )


class ChangesFile(StoreDocument):
    """DR-08, DR-10. The whole of `cast/{id}/changes.yaml`.

    A list, because a character can lose the same attribute twice - a hand, then the
    prosthesis - and each step has its own scene and its own cause.
    """

    changes: list[ChangeEvent] = Field(
        default_factory=list,
        description="Every registered change for this character; the auditor reads those dated"
        " at or before the scene under audit.",
    )


__all__ = [
    "ChangeEvent",
    "ChangesFile",
]
