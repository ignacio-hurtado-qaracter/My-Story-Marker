"""What a role call returns, and the wire shapes of the agents routes.

**A role returns values, never writes** (FR-AGENT-01..08, FR-PERM-06). Each role function in
`app.agents.roles` reads its Figure 3 inputs, makes one model call and answers with a
`RoleCall`: the validated DR-12 output, the `Completion` the client reported, the documents it
sent, what the cap pruned and the version of the prompt it ran under. That is everything the
turn record needs about the step (FR-TURN-07, FR-CTX-03) and nothing that could land in a store
by itself. Persisting an output is a separate act in `app.agents.service`, under the role's
tool set, so a role that is wrong about where its output goes cannot put it there.

Two roles add what code, not the model, establishes about their output. The auditor's findings
are converted to DR-07 violations with `source: model`, a deterministic id and evidence that
is checked against the draft (`SemanticAuditResult`); the writer's digests are given the level,
the range and the `povs` the records state (`DigestResult`). In both, where code and model
disagree the disagreement is kept on the result rather than resolved out of sight.

The request and response models at the end are the wire shapes of IF-06: rollup's, and the
turn routes' -- the body that starts a turn, the rulings a human hands down, and the Server-Sent
Event a running turn emits after every step (P5).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.commons.deps import SemanticSkip
from app.commons.errors import HarnessError
from app.commons.llm import Completion, Document
from app.commons.permissions import AgentRole
from app.commons.schemas import (
    DigestOutput,
    EscalationCategory,
    ExtractOutput,
    ProposedFactDraft,
    RulingKind,
    SceneDigest,
    SemanticAuditOutput,
    StepStatus,
    TurnOutcome,
    TurnStep,
    Violation,
)
from app.commons.schemas.common import EntityId, SceneId
from app.commons.schemas.turn import TURN_ID_PATTERN
from app.commons.stores.provenance import ProvenanceRecord
from app.ledger.audit import AuditReport


@dataclass(frozen=True, slots=True)
class RoleCall[T: BaseModel]:
    """One settled role call and everything the turn record says about it.

    `documents` are exactly what the model received, in order, each labelled with its path.
    `removed` names the prunable inputs the cap left out, in rank order, and `truncated_at` the
    first of them (FR-CTX-03); both are empty when everything fit.
    """

    role: AgentRole
    completion: Completion[T]
    documents: tuple[Document, ...]
    instruction: str
    removed: tuple[str, ...]
    truncated_at: str | None
    prompt_version: str
    """FR-AGENT-10. The SHA-256 of the prompt file the call ran under."""

    @property
    def output(self) -> T:
        """The validated DR-12 output."""
        return self.completion.output


@dataclass(frozen=True, slots=True)
class RejectedFact:
    """FR-AGENT-05, FR-OPS-06. A fact the canoniser returned that `promote` could not write.

    `attempt` is 1 for the first answer and 2 for the retry; `index` is the fact's position in
    that answer's `facts`. `reason` says which half of the address failed: an entity that is
    not one of the listed records, a field that record does not have, or a mapping payload not
    written `key: value`.
    """

    attempt: int
    index: int
    fact: ProposedFactDraft
    reason: str


@dataclass(frozen=True, slots=True)
class ExtractCall(RoleCall[ExtractOutput]):
    """FR-AGENT-05, AC 27. The canoniser's call with every fact checked against what `promote`
    can write (`app.ledger.service.promotable_targets`).

    `output.facts` holds only facts whose address is promotable, so everything the orchestrator
    queues from it can be promoted or escalated, never refused for its address. When the first
    answer named any other target, the call was retried once with those targets named in the
    instruction; `first` is then that first call, as the model answered it, and `completion`,
    `documents` and `instruction` are the retry's, its output replaced by the valid facts of
    both answers merged by key (first answer's first). `retried` lists what the first answer
    got wrong; `rejected` what the retry still got wrong -- never queued, and kept here so no
    fact is dropped out of sight. `targets` names the entity ids the instruction listed.
    """

    targets: tuple[str, ...] = ()
    retried: tuple[RejectedFact, ...] = ()
    rejected: tuple[RejectedFact, ...] = ()
    first: RoleCall[ExtractOutput] | None = None


@dataclass(frozen=True, slots=True)
class RevisionScope:
    """FR-AGENT-02. How much of a draft a revision changed, against the configured limit.

    `ratio` is the share of the draft's sentences the revision replaced, removed or added to
    (see `roles.writer.changed_sentence_ratio`); `within` is whether it stays at or under
    `limit`, `TURN_REVISE_MAX_CHANGED_RATIO`. Retrying with a stronger instruction and
    escalating on the second failure are the orchestrator's (plan step 18).
    """

    ratio: float
    limit: float
    sentences: int
    changed: int

    @property
    def within(self) -> bool:
        return self.ratio <= self.limit


@dataclass(frozen=True, slots=True)
class DigestResult:
    """FR-AGENT-03, FR-AGENT-08. A writer digest call and the record it would become.

    `record` is the `SceneDigest` as code establishes it: `scene_ref`, `level` and `povs` from
    the scene records and the structure, `delta` from the model, `words` measured. `digest_id`
    is the file it goes to under `manuscript/digests/`. `claimed_povs` is what the model said;
    `povs_agree` is false when that differs from the records, which is kept visible rather
    than silently corrected.
    """

    call: RoleCall[DigestOutput]
    digest_id: str
    record: SceneDigest
    claimed_povs: tuple[str, ...]

    @property
    def povs_agree(self) -> bool:
        return set(self.claimed_povs) == set(self.record.povs)


class Adjustment(StrEnum):
    """What code did to one model finding before it became a DR-07 violation."""

    RELOCATED = "relocated"
    """The quote is in the draft but not at the stated offset: moved to its nearest occurrence."""
    UNANCHORED = "unanchored"
    """The quote is nowhere in the draft: kept, with a blocking severity lowered to reviewable."""
    OUT_OF_REMIT = "out_of_remit"
    """An invariant FR-AGENT-06 does not delegate to the model: not recorded as a violation."""
    DUPLICATE = "duplicate"
    """The same finding twice in one answer: recorded once."""


@dataclass(frozen=True, slots=True)
class FindingAdjustment:
    """One model finding code did not take exactly as given, and why. `index` is its position
    in the model's `violations` list."""

    index: int
    invariant: int
    adjustment: Adjustment
    detail: str


@dataclass(frozen=True, slots=True)
class SemanticAuditResult:
    """FR-AGENT-06. The auditor's call, its findings as DR-07 violations, and the accounting.

    `violations` carry `source: model` and ids from `ledger.audit.violation_id`. `skipped`
    lists one entry per input the cap pruned, under the invariant it serves (FR-CTX-04).
    `adjustments` lists every finding code moved, downgraded or did not record, so no finding
    is dropped out of sight.
    """

    call: RoleCall[SemanticAuditOutput]
    violations: tuple[Violation, ...]
    skipped: tuple[SemanticSkip, ...]
    adjustments: tuple[FindingAdjustment, ...]


@dataclass(frozen=True, slots=True)
class CombinedAudit:
    """FR-AGENT-07. `audit(scene)`: the mechanical checks, then the auditor role.

    `report` is the combined report. `semantic` is the auditor's call when it settled, and
    `failure` the error that stopped it otherwise -- in which case the report's `skipped` names
    the semantic halves (FR-AUD-09) and the orchestrator decides what the turn does with it.
    """

    report: AuditReport
    semantic: SemanticAuditResult | None
    failure: HarnessError | None


class RollupRequest(BaseModel):
    """IF-06, the body of `POST /agents/digests/rollup`: one chapter or one arc, never both."""

    model_config = ConfigDict(extra="forbid")

    chapter_id: EntityId | None = Field(
        default=None,
        description="Roll the scene digests of this chapter of `structure/chapters.yaml` into a"
        " chapter digest.",
    )
    arc_id: EntityId | None = Field(
        default=None,
        description="Roll the chapter digests of this arc of `structure/arcs.yaml` into an arc"
        " digest.",
    )

    @model_validator(mode="after")
    def _exactly_one(self) -> RollupRequest:
        if (self.chapter_id is None) == (self.arc_id is None):
            message = "name exactly one of chapter_id and arc_id"
            raise ValueError(message)
        return self


class RollupResponse(BaseModel):
    """IF-06. The digest written, where, under whom, and what the call cost."""

    digest_id: SceneId = Field(
        description="The file under `manuscript/digests/`: 900 + k for the k-th chapter of"
        " `structure/chapters.yaml`, 989 + k for the k-th arc of `structure/arcs.yaml`.",
    )
    digest: SceneDigest = Field(description="The record as written, `words` measured.")
    persisted: ProvenanceRecord = Field(description="The provenance line of the write.")
    claimed_povs: list[EntityId] = Field(
        description="The `povs` the model reported. The record's `povs` come from the scene"
        " records; the two are compared, not merged.",
    )
    povs_agree: bool = Field(description="Whether `claimed_povs` names the same characters.")
    model_id: str | None = Field(description="The model id the CLI reported (FR-LLM-03).")
    estimate: int = Field(ge=0, description="The pre-call input estimate (FR-CTX-02).")
    over_cap: bool = Field(description="FR-CTX-06: the real count exceeded the cap.")
    prompt_version: str = Field(description="FR-AGENT-10: the writer prompt's SHA-256.")


class TurnRequest(BaseModel):
    """IF-06, the body of `POST /agents/turns`: the scene to write. Nothing else -- the scene
    record says what the scene is for, and the stores say everything the roles may read."""

    model_config = ConfigDict(extra="forbid")

    scene_id: SceneId = Field(description="The scene to run one turn on (FR-TURN-01).")


class RulingRequest(BaseModel):
    """FR-TURN-08, one entry of the body of `POST /agents/turns/{id}/rulings`: a human's
    decision on one collided fact of the turn, with the reason FR-OPS-07 records on it."""

    model_config = ConfigDict(extra="forbid")

    fact_id: EntityId = Field(description="A fact of this turn left `pending` on a collision.")
    ruling: RulingKind = Field(description="`accept` promotes despite it; `reject` refuses it.")
    reason: str = Field(
        min_length=1, description="Why; recorded on the fact so the same fact is not argued twice."
    )


class TurnEvent(BaseModel):
    """IF-06. One Server-Sent Event of a running turn: one per step, then one with the outcome.

    `kind` is also the SSE `event` field. A `step` event names the step that just ended, its
    iteration and how it ended, and where the turn goes next; the final `outcome` event carries
    the turn's outcome and, for an escalated turn, why. The turn record at
    `GET /agents/turns/{turn_id}` holds everything else -- an event carries identifiers and
    states only, never text a role produced (NFR-10).
    """

    kind: Literal["step", "outcome"] = Field(description="`step`, or the final `outcome`.")
    turn_id: str = Field(pattern=TURN_ID_PATTERN, description="The turn record's id, `NNN-<n>`.")
    scene: SceneId
    step: TurnStep | None = Field(
        default=None, description="The step that ended; null on the outcome event."
    )
    iteration: int | None = Field(default=None, ge=0)
    status: StepStatus | None = None
    outcome: TurnOutcome = Field(description="The turn's outcome as of this event.")
    next_step: TurnStep = Field(description="The step that runs next, `done` when none does.")
    escalation: EscalationCategory | None = Field(
        default=None, description="Why the turn escalated, once it has."
    )


__all__ = [
    "Adjustment",
    "CombinedAudit",
    "DigestResult",
    "ExtractCall",
    "FindingAdjustment",
    "RejectedFact",
    "RevisionScope",
    "RoleCall",
    "RollupRequest",
    "RollupResponse",
    "RulingRequest",
    "SemanticAuditResult",
    "TurnEvent",
    "TurnRequest",
]
