"""FR-TURN-07, FR-OPS-05. The record of one writing turn.

It lives in `commons/` rather than in `agents/` for the reason DR-01 gives: two features use
it. `agents/` writes it, and `canon/`'s `reconcile` reads it (FR-OPS-08: "every turn record
whose selected list contains" the changed entity). `canon/` sits below `agents/` in the
feature layers of NFR-04, so it could not import the model from there.

Turn records live under `.index/turns/`, which is **not** a store: it is not governed by
Figure 3 and no agent reads it (Decision R2-1). They are also not rebuildable (AC 31).

**What the record holds, and what it never holds.** Identifiers, counts, timestamps, token
figures and the reasons a step did not run -- everything FR-TURN-07 lists -- and no prompt,
no document and no prose (NFR-10). The draft is in `manuscript/`, the findings in
`ledger/violations.yaml`, the facts in `ledger/proposed.yaml`: the record names them by path
and id. That is also what makes it the one thing the orchestrator carries between steps
(FR-AGENT-11): a step reads its inputs from the stores the previous step wrote, and learns
from the record only *which* ids to read.

**It is written after every step** (FR-TURN-07, FR-TURN-09), so it doubles as the turn's
cursor. `next_step`, `revisions` and `revise_rejections` are exactly the state Figure 4's
machine needs to continue, which is how `POST /agents/turns/{id}/resume` re-enters a turn
killed mid-way without re-running a completed step. Every field has a default, so the
record `reconcile` reads -- id, scene and selected list -- stays valid on its own.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator

from app.commons.config import ROLE_NAMES
from app.commons.schemas.common import (
    DigestLevel,
    EntityId,
    FactStatus,
    HarnessModel,
    RulingKind,
    SceneId,
    StoreDocument,
    Words,
)

TURN_ID_PATTERN = r"^\d{3}-\d+$"
"""`NNN-<n>`: the scene id and the attempt, counted from 1 per scene (FR-TURN-07)."""


class TurnOutcome(StrEnum):
    """Figure 4's terminal states, plus the two a record can be read in before one."""

    RUNNING = "running"
    AWAITING_RULING = "awaiting_ruling"
    MERGED = "merged"
    ESCALATED = "escalated"


class TurnStep(StrEnum):
    """The steps of Figure 4 as the orchestrator runs them, in order (FR-TURN-01).

    `recheck` is FR-AGENT-04's mechanical lexicon and voice check of the polished draft;
    `done` is the cursor of a turn with nothing left to run.
    """

    ASSEMBLE = "assemble"
    WRITE = "write"
    AUDIT = "audit"
    REVISE = "revise"
    POLISH = "polish"
    RECHECK = "recheck"
    DIGEST = "digest"
    EXTRACT = "extract"
    PROMOTE = "promote"
    DONE = "done"


class StepStatus(StrEnum):
    """How one step ended."""

    COMPLETED = "completed"
    REJECTED = "rejected"
    """A revision over `TURN_REVISE_MAX_CHANGED_RATIO` (FR-AGENT-02): made, measured, and not
    written. The first one is retried with a stronger instruction."""
    FAILED = "failed"


class EscalationCategory(StrEnum):
    """Why a turn ended `escalated` (FR-TURN-02, FR-LLM-04..08, FR-CTX-05, FR-AGENT-02, -04).

    The five model failures carry the IF-07 code of the error that stopped the step, so the
    record and an HTTP error body say the same thing. The three that are not errors are the
    turn's own bounds. Any other refusal of the harness -- a record that does not validate, an
    input that is missing -- carries its IF-07 code too; `harness_error` is the catch-all for a
    code this list does not name.
    """

    CONTEXT_BUDGET_EXCEEDED = "context_budget_exceeded"
    MALFORMED_MODEL_OUTPUT = "malformed_model_output"
    MODEL_REFUSED = "model_refused"
    MODEL_CALL_FAILED = "model_call_failed"
    OUTPUT_TRUNCATED = "output_truncated"
    REVISION_BOUND = "revision_bound"
    """FR-TURN-02: blocking violations still open after `TURN_MAX_REVISIONS` revisions."""
    REVISE_SCOPE = "revise_scope"
    """FR-AGENT-02: the revision changed too much of the scene twice."""
    POLISH_RECHECK = "polish_recheck"
    """FR-AGENT-04: the polish introduced a lexicon or voice finding the accepted draft did
    not have."""
    INVALID_RECORD = "invalid_record"
    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"
    INDEX_BUSY = "index_busy"
    HARNESS_ERROR = "harness_error"


def _known_role(value: str | None) -> str | None:
    """A role is one of Figure 3's six names. Plain strings, because `commons.schemas` sits
    beside `commons.permissions` in the import contract and cannot import `AgentRole`."""
    if value is not None and value not in ROLE_NAMES:
        message = f"{value!r} is not an agent role; expected one of {', '.join(ROLE_NAMES)}"
        raise ValueError(message)
    return value


class SelectedEntity(HarnessModel):
    """One entry of the selected list (FR-OPS-02, FR-OPS-05).

    Recorded rather than recomputed because selection is not reproducible: two runs may rank
    differently, and "which axioms apply to this scene" must have one answer per turn, shared
    by the writer and the auditor.
    """

    entity_id: EntityId
    kind: str = Field(min_length=1, description="The index row's kind: axiom, character, ...")
    score: float = Field(description="Fused rank score; higher is more relevant.")
    pinned: bool = Field(
        default=False,
        description="True when the entity entered through `pins` or a tag-scope match.",
    )


class ModelCallRecord(HarnessModel):
    """One model call that settled (FR-TURN-07, FR-LLM-03, FR-LLM-09, FR-CTX-06, NFR-01)."""

    requested_model: str = Field(description="The model passed as `--model` (FR-LLM-03).")
    model_id: str | None = Field(
        description="The model id the CLI reported having used; null when it reported none.",
    )
    prompt_version: str = Field(description="SHA-256 of the role's prompt file (FR-AGENT-10).")
    estimate: Words = Field(description="The pre-call input estimate (FR-CTX-02).")
    input_tokens: Words = 0
    output_tokens: Words = 0
    cache_read_input_tokens: Words = 0
    cache_creation_input_tokens: Words = 0
    over_cap: bool = Field(
        default=False,
        description="FR-CTX-06: the real input count, less the CLI's overhead, exceeded the cap.",
    )
    attempts: Words = Field(default=1, description="Attempts the call took (FR-LLM-04, -08).")
    elapsed_seconds: float = Field(default=0.0, ge=0.0)
    cli_version: str | None = Field(default=None, description="The CLI version (NFR-01).")


class WriteRecord(HarnessModel):
    """One store write a step made, as the provenance log recorded it (FR-STORE-04, AC 32)."""

    path: str
    role: str
    actor: str
    content_hash: str

    @field_validator("role")
    @classmethod
    def _role_is_known(cls, value: str) -> str:
        _known_role(value)
        return value


class RevisionScopeRecord(HarnessModel):
    """FR-AGENT-02. How much of the draft a revision changed, against the limit."""

    ratio: float = Field(ge=0.0, le=1.0)
    limit: float = Field(ge=0.0, le=1.0)
    sentences: Words
    changed: Words
    within: bool


class StepRecord(HarnessModel):
    """One step of the turn, whatever it did (FR-TURN-07, FR-CTX-03).

    `role` is the role Figure 4 gives the step (FR-TURN-06); the assembly has none, because
    the orchestrator holds no role. `estimate` is the input estimate of the call, or of the
    assembled context for the assembly, and is present even when the cap stopped the call
    (FR-CTX-05). `removed` and `truncated_at` name what the cap pruned, in rank order.
    `error` is the IF-07 code of what stopped a failed step.
    """

    step: TurnStep
    iteration: Words = Field(
        default=0,
        description="The revise-audit iteration: 0 for the written draft, k after revision k.",
    )
    role: str | None = None
    status: StepStatus = StepStatus.COMPLETED
    started_at: str
    ended_at: str
    estimate: Words | None = None
    call: ModelCallRecord | None = None
    removed: list[str] = Field(default_factory=list)
    truncated_at: str | None = None
    writes: list[WriteRecord] = Field(default_factory=list)
    scope: RevisionScopeRecord | None = None
    error: str | None = None

    @field_validator("role")
    @classmethod
    def _role_is_known(cls, value: str | None) -> str | None:
        return _known_role(value)


class SkippedRecord(HarnessModel):
    """A check of the audit that did not run, or ran without one of its inputs (FR-AUD-09,
    FR-CTX-04)."""

    check: str
    invariant: int = Field(ge=1, le=10)
    source: str
    reason: str


class AuditIteration(HarnessModel):
    """The violation ids of one audit (FR-TURN-07: "violation ids per iteration").

    `violations` is every finding the audit reported; `blocking` the scene's open blocking
    findings read back from `ledger/violations.yaml` after the auditor's write -- what the next
    revision, if any, is handed (FR-AGENT-11).
    """

    iteration: Words
    violations: list[str] = Field(default_factory=list)
    blocking: list[str] = Field(default_factory=list)
    skipped: list[SkippedRecord] = Field(default_factory=list)


class FactRecord(HarnessModel):
    """One of this turn's proposed facts and what became of it (FR-TURN-03, -04, -07).

    `status` mirrors the fact in `ledger/proposed.yaml`. `conflict` is a collision left for a
    human ruling; `refused` is why `promote` could not act on the fact at all (an entity that
    does not exist, a field no string can fill), in which case it stays `pending` for a person.
    `reconciled_scenes` are the scenes `reconcile(target_entity)` returned after the promotion
    or the accepting ruling, and `written_scenes` those of them that already have a draft --
    the retroactive change, named when it is made.
    """

    fact_id: EntityId
    target_entity: EntityId
    target_field: str
    proposed_by: list[str] = Field(default_factory=list)
    status: FactStatus = FactStatus.PENDING
    conflict: bool = False
    changed: bool = False
    refused: str | None = None
    ruling: RulingKind | None = None
    reconciled_scenes: list[SceneId] = Field(default_factory=list)
    written_scenes: list[SceneId] = Field(default_factory=list)
    reconciled_turns: list[str] = Field(default_factory=list)

    @field_validator("proposed_by")
    @classmethod
    def _roles_known(cls, value: list[str]) -> list[str]:
        for role in value:
            _known_role(role)
        return value

    @property
    def settled(self) -> bool:
        """True once the promotion step has nothing left to do for this fact (FR-OPS-06, AC 20).

        `conflict` does not settle a fact: promotion is add-only, so a pending fact that still
        carries `conflict: true` from before is promoted like any other."""
        return self.status is not FactStatus.PENDING or self.refused is not None


class DraftMeasure(HarnessModel):
    """The draft's `words` against the scene `budget` (FR-TURN-07, DR-11)."""

    words: Words
    budget: Words


class DigestMeasure(HarnessModel):
    """A digest's `words` against its level's target (FR-TURN-07, DR-11)."""

    digest_id: SceneId
    level: DigestLevel
    words: Words
    target: Words


class TurnEscalation(HarnessModel):
    """Why the turn stopped, where, and with what the provider said (AC 19, 21, 22)."""

    category: EscalationCategory
    step: TurnStep
    iteration: Words = 0
    detail: str = Field(description="What stopped the step; never prompt or draft text.")
    refusal_category: str | None = Field(
        default=None, description="FR-LLM-06: the refusal's category, when the provider gave one."
    )
    reason: str | None = Field(
        default=None, description="FR-LLM-08: the failure reason of a failed model call."
    )


class TurnRecord(StoreDocument):
    """`.index/turns/NNN-<n>.yaml`. Written after every step, so a crash leaves the steps
    completed so far on disk (FR-TURN-09)."""

    id: str = Field(pattern=TURN_ID_PATTERN, description="`NNN-<n>`: scene id and attempt.")
    scene: SceneId
    outcome: TurnOutcome = TurnOutcome.RUNNING
    selected: list[SelectedEntity] = Field(default_factory=list)
    started_at: str | None = None
    ended_at: str | None = None
    next_step: TurnStep = Field(
        default=TurnStep.ASSEMBLE, description="The step a resume runs next (FR-TURN-09)."
    )
    revisions: Words = Field(default=0, description="Revisions accepted so far (FR-TURN-02).")
    revise_rejections: Words = Field(
        default=0, description="Rejected revisions in the current iteration (FR-AGENT-02)."
    )
    steps: list[StepRecord] = Field(default_factory=list)
    iterations: list[AuditIteration] = Field(default_factory=list)
    facts: list[FactRecord] = Field(default_factory=list)
    draft: DraftMeasure | None = None
    digests: list[DigestMeasure] = Field(default_factory=list)
    chapter: EntityId | None = Field(default=None, description="The chapter listing the scene.")
    closes_chapter: bool = Field(
        default=False,
        description="The scene is the last its chapter lists: a hint for the manual rollup.",
    )
    rollup_ready: bool = Field(
        default=False,
        description="Every scene of the chapter has a scene digest, so a rollup would not be"
        " refused as partial (FR-AGENT-08).",
    )
    escalation: TurnEscalation | None = None


__all__ = [
    "TURN_ID_PATTERN",
    "AuditIteration",
    "DigestMeasure",
    "DraftMeasure",
    "EscalationCategory",
    "FactRecord",
    "ModelCallRecord",
    "RevisionScopeRecord",
    "SelectedEntity",
    "SkippedRecord",
    "StepRecord",
    "StepStatus",
    "TurnEscalation",
    "TurnOutcome",
    "TurnRecord",
    "TurnStep",
    "WriteRecord",
]
