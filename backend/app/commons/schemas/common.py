"""The conventions every store record follows, and the closed enums of DR-04…07.

Two bases, and the difference matters:

* `StoreDocument` is a **file**. It carries `schema_version`, because DR-10 versions a
  schema per file, in the filename and in the record, and an unknown version fails
  validation rather than being read optimistically.
* `HarnessModel` is a **value inside a file** — a knowledge row, a dated valence, a piece of
  evidence. It has no version of its own; it is versioned by the document that holds it.

Both forbid unknown fields. A store file with a field nobody modelled is not a record with a
harmless extra; it is a record whose author believed something the system does not, and
reading it as if the field were not there is how that divergence survives to chapter forty.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION: Final[int] = 1
"""DR-10. Bumping this is a migration, not an edit."""

ENTITY_ID_PATTERN: Final[str] = r"^[a-z0-9][a-z0-9_-]*$"
"""FR-STORE-05. Paths derive from identifiers inside the store layer; an id that could
escape the root, or that differs from this grammar, never reaches a path."""

SCENE_ID_PATTERN: Final[str] = r"^\d{3}$"
"""FR-STORE-05, and `definitions.md` Scene: `NNN`, stable forever."""

EntityId = Annotated[str, Field(pattern=ENTITY_ID_PATTERN, min_length=1, max_length=120)]
SceneId = Annotated[str, Field(pattern=SCENE_ID_PATTERN)]

# Every integer in a store record is strict. Pydantic's lax mode reads `true` as 1, and a
# `story_time: true` that silently becomes hour 1 is exactly the kind of quiet nonsense the
# invariants are meant to catch. AC 5 only asks this of the enums; it costs nothing to make
# the numbers as unforgiving.
StrictInteger = Annotated[int, Field(strict=True)]
StoryHours = Annotated[int, Field(strict=True)]
"""Decision 8: hours since `epoch_zero`. May be negative — prequel scenes exist."""

Order = Annotated[int, Field(strict=True, ge=1)]
"""A 1-based position: `discourse_order`, a latency, a count of scenes."""

Words = Annotated[int, Field(strict=True, ge=0)]
"""A word count or budget."""

Valence = Annotated[int, Field(strict=True, ge=-3, le=3)]
"""`definitions.md` Relationship: -3 to +3, dated per scene."""

Invariant = Annotated[int, Field(strict=True, ge=1, le=10)]
"""DR-07. The ten domain invariants of `definitions.md`, by number."""


class HarnessModel(BaseModel):
    """A value inside a store file."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        use_enum_values=False,
        str_strip_whitespace=False,
    )


class StoreDocument(HarnessModel):
    """A store file. DR-10: the version travels with the record, not only in the filename."""

    schema_version: Literal[1] = 1

    @field_validator("schema_version", mode="before")
    @classmethod
    def _version_is_not_a_boolean(cls, value: object) -> object:
        """DR-10: an unknown version fails validation.

        `Literal[1]` alone does not achieve that, because `True == 1` in Python and pydantic
        accepts it. YAML `schema_version: true` would then be read as version 1 -- the same
        "lax mode reads true as 1" hole the strict integer aliases above exist to close, in
        the one field where it decides how the whole record is interpreted.
        """
        if isinstance(value, bool):
            message = f"schema_version must be an integer version, got {value!r}"
            raise ValueError(message)
        return value


# --------------------------------------------------------------------------------------
# Closed enums. AC 5 tests that each rejects an out-of-enum string and a boolean.
# --------------------------------------------------------------------------------------


class Outcome(StrEnum):
    """DR-03. The four-value scene outcome.

    `yes-but` and `no-and-furthermore` are the two that carry a novel: a scene that only ever
    answers `yes` or `no` has no complication and no escalation.
    """

    YES = "yes"
    NO = "no"
    YES_BUT = "yes-but"
    NO_AND_FURTHERMORE = "no-and-furthermore"


class Certainty(StrEnum):
    """DR-04. Five values, not a boolean.

    `believes_falsely` is the one that earns the enum: without it you cannot write deception
    or dramatic irony at all, which is the failure mode `definitions.md` names for
    KnowledgeState.
    """

    UNAWARE = "unaware"
    SUSPECTS = "suspects"
    BELIEVES = "believes"
    KNOWS = "knows"
    BELIEVES_FALSELY = "believes_falsely"


class Via(StrEnum):
    """DR-04. How the knowledge was acquired."""

    WITNESSED = "witnessed"
    WAS_TOLD = "was_told"
    DEDUCED = "deduced"
    SUSPECTS = "suspects"


class SetupResolution(StrEnum):
    """DR-05. How a reader debt was closed.

    `deliberately_abandoned` is what separates a decision from a forgotten promise. Without
    it the checker reports noise, and noisy checkers get ignored.
    """

    PAID = "paid"
    SUBVERTED = "subverted"
    DELIBERATELY_ABANDONED = "deliberately_abandoned"


class ThreadState(StrEnum):
    """DR-06. Where a plot line stands."""

    PLANTED = "planted"
    DEVELOPING = "developing"
    DORMANT = "dormant"
    RESOLVED = "resolved"
    ABANDONED = "abandoned"


class FactStatus(StrEnum):
    """DR-07. A proposed fact is pending until the canoniser acts on it."""

    PENDING = "pending"
    PROMOTED = "promoted"
    REJECTED = "rejected"


class RulingKind(StrEnum):
    """FR-OPS-07. The human decision on a collision, and the only way one is resolved."""

    ACCEPT = "accept"
    REJECT = "reject"


class Severity(StrEnum):
    """DR-07. Only `blocking` stops a turn; the rest are reported and carried."""

    BLOCKING = "blocking"
    REVIEWABLE = "reviewable"
    NOTE = "note"


class ViolationResolution(StrEnum):
    """DR-07. What a human decided to do about a violation.

    The auditor never sets this: it reports and does not repair (AC 16). It is written
    through `PUT /ledger/violations` by a human acting as the auditor with `X-Actor: human`,
    which is the dotted escalate-ruling edge of Figure 1.
    """

    FIX_PROSE = "fix_prose"
    FIX_CANON = "fix_canon"
    ACCEPT_WITH_REASON = "accept_with_reason"


class ViolationSource(StrEnum):
    """DR-07. Mechanical checks and the model-backed auditor are told apart on the record,
    because FR-AUD-09 reports the model half as `skipped` when it fails and a reader has to
    be able to see which half produced a finding."""

    MECHANICAL = "mechanical"
    MODEL = "model"


class DigestLevel(StrEnum):
    """DR-11. Only `chapter` is indexed for retrieval (FR-IDX-02)."""

    SCENE = "scene"
    CHAPTER = "chapter"
    ARC = "arc"


# --------------------------------------------------------------------------------------
# Small shared values
# --------------------------------------------------------------------------------------


class Evidence(HarnessModel):
    """DR-07. A quotation and where it is, so a violation can be pointed at rather than
    argued about."""

    quote: str = Field(min_length=1, description="The offending text, verbatim.")
    offset: Words = Field(description="Character offset of the quote in the draft.")


class Ruling(HarnessModel):
    """DR-07, FR-OPS-07. The human decision recorded on a proposed fact."""

    by: str = Field(min_length=1, description="Who ruled.")
    ruling: RulingKind
    reason: str = Field(min_length=1, description="Why; a ruling without one is unreviewable.")
    at: str = Field(min_length=1, description="ISO-8601 timestamp of the ruling.")


__all__ = [
    "ENTITY_ID_PATTERN",
    "SCENE_ID_PATTERN",
    "SCHEMA_VERSION",
    "Certainty",
    "DigestLevel",
    "EntityId",
    "Evidence",
    "FactStatus",
    "HarnessModel",
    "Invariant",
    "Order",
    "Outcome",
    "Ruling",
    "RulingKind",
    "SceneId",
    "SetupResolution",
    "Severity",
    "StoreDocument",
    "StoryHours",
    "StrictInteger",
    "ThreadState",
    "Valence",
    "Via",
    "ViolationResolution",
    "ViolationSource",
    "Words",
]
