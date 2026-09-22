"""DR-07. Violation reports: `ledger/violations.yaml`.

The auditor's only output, and the only path by which it writes anything at all. The file is
a document with a named key rather than a bare YAML list, because DR-10 puts
`schema_version` on the file.
"""

from __future__ import annotations

from pydantic import Field

from app.commons.schemas.common import (
    EntityId,
    Evidence,
    HarnessModel,
    Invariant,
    SceneId,
    Severity,
    StoreDocument,
    ViolationResolution,
    ViolationSource,
)


class Violation(HarnessModel):
    """DR-07. One breach of a domain invariant, reported and not repaired.

    **Failure mode** (`architecture.md` Violation): letting the auditor self-correct. An
    auditor with a write into the prose trims precisely the living details that made the
    scene work, because those are exactly the ones that deviate from the plan - the
    unplanned gesture, the line nobody outlined. So this record is a report: it names the
    invariant, quotes the offending text and stops. Only a human sets `resolution`, through
    the auditor's route with `X-Actor: human`, and the prose or canon edit that follows goes
    through the role that owns that path.

    `evidence` is what makes the report arguable rather than assertable. A finding that says
    "the timeline is wrong" cannot be checked, agreed with or dismissed; a quote with its
    offset can be looked at, and a wrong one can be shown to be wrong. That matters most for
    the model-backed half of the audit, where the finding is a judgement and the quote is the
    only thing anchoring it to the page.

    `source` tells the mechanical checks apart from the model. FR-AUD-09 reports the model
    half as `skipped` when it fails, so a reader must be able to see which half produced a
    finding and, by absence, which half never ran. Reading a silent audit as a pass is the
    error the pair of fields exists to prevent.

    **FR-OPS-03.** A violation with a `resolution` set has left the working tier and never
    enters a context again: it is settled, and carrying it forward would spend budget on a
    question already answered.
    """

    id: EntityId = Field(description="Stable identifier; the turn record names violations by it.")
    scene: SceneId = Field(description="The scene whose draft or record breaches the invariant.")
    invariant: Invariant = Field(
        description="Which of the ten domain invariants of `definitions.md` broke, by number.",
    )
    evidence: Evidence = Field(
        description="The offending text and its offset, so the finding is pointed at rather"
        " than argued about.",
    )
    severity: Severity = Field(
        description="`blocking`, `reviewable` or `note`. Only `blocking` stops a turn; the"
        " revise step receives the blocking ones and nothing else (FR-AGENT-02).",
    )
    resolution: ViolationResolution | None = Field(
        default=None,
        description="`fix_prose`, `fix_canon` or `accept_with_reason`; set only by a human."
        " Once set, the violation leaves the working tier (FR-OPS-03).",
    )
    source: ViolationSource = Field(
        description="`mechanical` or `model`. FR-AUD-09 reports the model half as `skipped` on"
        " failure, so absence of a finding is never mistaken for a pass.",
    )


class ViolationsFile(StoreDocument):
    """DR-07, DR-10. The whole of `ledger/violations.yaml`.

    The auditor's single writable path (Figure 3), which is what makes "the auditor reports
    and does not repair" checkable rather than merely intended. Roles hand work to each other
    through the stores (FR-AGENT-11): `revise` reads the blocking violations back from this
    file after the auditor's write has landed, not from memory.
    """

    violations: list[Violation] = Field(
        default_factory=list,
        description="Every violation reported against the manuscript, open and resolved; the"
        " resolved ones stay as history and never enter a context.",
    )


__all__ = [
    "Violation",
    "ViolationsFile",
]
