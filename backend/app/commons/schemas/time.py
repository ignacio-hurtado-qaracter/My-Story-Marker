"""DR-09. The temporal system: `canon/time.yaml`.

The file that turns "it took weeks" into a quantity something can check. Every `story_time`
in `scenes/NNN.yaml` is an integer count of hours since `epoch_zero` (Decision 8), so this
document is what those integers mean; and the transit matrix is what makes a difference
between two of them either possible or a violation.

It is a single document rather than a list file: there is exactly one temporal system per
project, and `schema_version` sits on it directly (DR-10). The world builder writes it; the
auditor reads it (Figure 3).
"""

from __future__ import annotations

from typing import Final

from pydantic import Field, JsonValue

from app.commons.schemas.common import (
    ENTITY_ID_PATTERN,
    EntityId,
    HarnessModel,
    StoreDocument,
    StoryHours,
)

_ENTITY_KEY_SCHEMA: Final[dict[str, JsonValue]] = {
    "pattern": ENTITY_ID_PATTERN,
    "minLength": 1,
    "maxLength": 120,
}
"""What an `EntityId` used as a mapping key really allows."""


def _faithful_transit_matrix_schema(schema: dict[str, JsonValue]) -> None:
    """Replace pydantic's rendering of the transit matrix with one that says what the model
    enforces.

    Pydantic renders a constrained-key mapping as `patternProperties` with the key pattern,
    but leaves `propertyNames` carrying only the length bounds and adds no
    `additionalProperties`. The result accepts keys -- and, at the inner level, values -- that
    the model rejects. These schemas are a committed contract that other things read (DR-01),
    so a schema looser than its model is a defect rather than a cosmetic difference, and the
    generative round-trip of AC 4 is what surfaced it.

    The whole node is rebuilt rather than merged into, because the inner mapping sits inside
    pydantic's generated `patternProperties` where an extra key cannot reach it.
    """
    title = schema.get("title")
    description = schema.get("description")
    schema.clear()
    if title is not None:
        schema["title"] = title
    if description is not None:
        schema["description"] = description
    schema.update(
        {
            "type": "object",
            "propertyNames": dict(_ENTITY_KEY_SCHEMA),
            "additionalProperties": {
                "type": "object",
                "propertyNames": dict(_ENTITY_KEY_SCHEMA),
                "additionalProperties": {"type": "integer"},
            },
        }
    )


class Calendar(HarnessModel):
    """DR-09. One culture's way of naming the time that `epoch_zero` counts.

    Calendars are presentation, not arithmetic. Nothing in the harness computes with them -
    the invariants subtract raw hours - so `conversion` is prose stating how this calendar
    relates to the epoch, for a human and for the writer's context, and is deliberately not
    a machine-evaluated expression. Getting a second calendar wrong is a flavour error;
    getting `epoch_zero` wrong would be an arithmetic one, which is why they are separate.
    """

    id: EntityId = Field(description="Stable identifier for the calendar.")
    name: str = Field(min_length=1, description="What the culture that uses it calls it.")
    conversion: str = Field(
        min_length=1,
        description="How it maps to hours since `epoch_zero`, stated for a reader; not evaluated.",
    )


class TemporalSystem(StoreDocument):
    """DR-09, DR-10. The whole of `canon/time.yaml`: origin, calendars, transits, dilation.

    **Failure mode** (`definitions.md` TemporalSystem): skipping the transit matrix.
    Characters then get teleported and nobody can prove it - two scenes an hour apart on
    opposite sides of a system read as fast pacing rather than as an error, and by the time
    a reader notices, the chapter between them depends on it. FR-AUD-04 is the check the
    matrix exists for: for each character it walks consecutive scenes on the story axis and
    requires `delta story_time >= transit_matrix[from][to]`. Where the pair has no entry it
    cannot conclude anything, so it reports a `note` rather than passing silently - an
    absent route is an unanswered question, not a permission.

    That is why `epoch_zero` and `transit_matrix` are required (DR-09) while the rest is
    optional. Without the origin the scene integers have no referent; without the matrix
    invariant 5 does not run at all, and an invariant that does not run is worse than one
    that fails, because nothing reports its absence.

    **`dilation_factor` is carried but not applied.** The v1 transit check compares raw
    `story_time` and ignores this field entirely (plan Residual 3). It is stored so the
    canon can record the offset between proper and coordinate time where the setting has
    one, and so the later spec that makes invariant 5 character-relative finds the data
    already there. Nobody should read a value here as evidence that a relativistic transit
    has been checked: in v1 it has not been.
    """

    epoch_zero: str = Field(
        min_length=1,
        description="The absolute origin every `story_time` is counted from, in hours."
        " Required (DR-09): without it the scene integers refer to nothing.",
    )
    calendars: list[Calendar] = Field(
        default_factory=list,
        description="One per culture, with its conversion; presentation only, never arithmetic.",
    )
    transit_matrix: dict[EntityId, dict[EntityId, StoryHours]] = Field(
        description="Minimum travel time in hours between pairs of location ids, as"
        " `transit_matrix[from][to]`. Required (DR-09); a missing pair makes FR-AUD-04 report"
        " a `note`, so an empty matrix checks nothing and says so.",
        json_schema_extra=_faithful_transit_matrix_schema,
    )
    dilation_factor: float | None = Field(
        default=None,
        description="Offset between proper and coordinate time. Carried only: the v1 transit"
        " check does not apply it (plan Residual 3).",
    )


__all__ = [
    "Calendar",
    "TemporalSystem",
]
