"""DR-12. What a model-invoked role is allowed to return, one schema per role call.

Nothing here is a store file. These models never reach disk under their own name: they are
the structured-output format FR-LLM-04 attaches to each request, and the orchestrator is
what turns an accepted output into the store records of `draft.py`, `digest.py`,
`proposed.py` and `violation.py`. So they extend `HarnessModel` and carry no
`schema_version` - a wire shape is versioned by the code that sends it, not by a file
header.

**Why the shapes are this flat.** Every model here is serialised to JSON Schema and handed
to the provider, and FR-LLM-04 *rejects rather than repairs*: an output that does not
validate costs one retry and then fails the turn step. A deeply nested shape, and above all
a union of models, is the shape most likely to come back almost-right, so there are no
unions here at all and no model nests more than one level deep. The plan names exactly this
as a stop condition.

**Why the fields are fewer than the store records they become.** A role may state what it
observed; it may not state what the system decided. `ProposedFactDraft` has no `status`,
no `conflict` and no `ruling`; `SemanticViolation` has no `source` and no `resolution`.
Those fields are the permission table of Figure 3 written into a schema: a field a role
cannot emit is a decision a role cannot make, and unlike a prompt instruction it holds even
when the model ignores what it was told, because `extra="forbid"` makes the extra key a
validation failure rather than a value somebody might read.
"""

from __future__ import annotations

from pydantic import Field

from app.commons.schemas.common import (
    EntityId,
    Evidence,
    HarnessModel,
    Invariant,
    Severity,
)


class ProposedFactDraft(HarnessModel):
    """DR-12. A world detail a role claims the prose asserts, as the role may state it.

    This is the writer's and the canoniser's half of `ProposedFact`: the address and the
    claim, and nothing about what happens next. The orchestrator assigns `id`,
    `extracted_from`, `source_scene` and `status: pending`, and only `promote` ever sets
    `conflict` or `existing_value`, and only a human ruling fills `ruling` (FR-OPS-06,
    FR-OPS-07).

    **Failure mode** (`architecture.md` ProposedFact): automatic promotion with no review.
    Canon fills with improvised noise and stops being worth consulting. The queue exists to
    stop that, and a queue whose entries can arrive already marked `promoted` is not a
    queue. Leaving `status`, `conflict` and `ruling` out of the schema is the same statement
    as the writer's empty canon column in Figure 3 - a role proposes, it does not commit -
    made at the one layer the model cannot argue with.

    `evidence` is a quotation from the draft rather than an `Evidence` record because the
    role has no reliable way to count characters in text it is producing; the offset a store
    record needs is located by the orchestrator against the written draft, the same way
    `words` and `literal_tail` are derived rather than reported (DR-11).
    """

    target_entity: EntityId = Field(
        description=(
            "The canon or cast record the claim would attach to. With `target_field` it is "
            "the address `promote` detects a collision at."
        ),
    )
    target_field: str = Field(
        min_length=1,
        description="The field on that record the `payload` would fill.",
    )
    payload: str = Field(
        min_length=1,
        description="The asserted value, as the prose has it.",
    )
    evidence: str = Field(
        min_length=1,
        description=(
            "The span of the draft the claim is read out of, quoted. It is what makes the "
            "proposal checkable against the prose instead of taken on trust."
        ),
    )


class WriterOutput(HarnessModel):
    """DR-12, FR-AGENT-01. The writer's `write` call: the scene, and what it had to invent.

    The two fields go to two different stores under the same role: `body` becomes
    `manuscript/NNN.md` and `proposed_facts` is appended to `ledger/proposed.yaml` with
    `status: pending`. That split is the writer's whole Figure 3 row - prose it owns,
    inventions it may only queue - and it is why an invention arrives here as a separate
    field rather than as something a later pass must go looking for in the prose.

    `proposed_facts` is required and not defaulted: a writer that invented nothing says so
    with an empty list. An absent key would be indistinguishable from a writer that invented
    plenty and reported none, and that is the silence the canonisation queue exists to
    prevent.
    """

    body: str = Field(
        min_length=1,
        description=(
            "The prose of the scene. The store layer derives `words` and `literal_tail` "
            "from it; the writer is never asked for either (DR-11)."
        ),
    )
    proposed_facts: list[ProposedFactDraft] = Field(
        description=(
            "Details about the world the scene asserts that canon did not already hold. "
            "Empty is a valid and meaningful answer."
        ),
    )


class ReviseOutput(HarnessModel):
    """DR-12, FR-AGENT-02. The writer's `revise` call: the full scene, minimally changed.

    The field is the whole scene text and not a patch, because a patch against prose is
    harder to apply correctly than the text is to re-emit - but a full re-emission is also
    an invitation to rewrite the scene, and `revise` exists to fix the flagged spans and
    nothing else. So the guard lives outside the schema: the orchestrator diff-checks this
    body against the draft it sent and rejects a revision that changed more than
    `TURN_REVISE_MAX_CHANGED_RATIO` of the sentences, retrying once with a stronger
    instruction and escalating on the second failure.

    **Failure mode**: a revision that regenerates the scene. The blocking violations would
    go away and so would every living detail the audit never objected to, which is the same
    damage `architecture.md` names under Violation when it forbids the auditor to
    self-correct. The revise step receives only the blocking violations, read back from
    `ledger/violations.yaml` after the auditor's write (FR-AGENT-11), for the same reason:
    the narrower the brief, the smaller the rewrite it can justify.
    """

    body: str = Field(
        min_length=1,
        description=(
            "The FULL scene text with only the flagged spans changed. The orchestrator "
            "compares it sentence by sentence against the draft it sent."
        ),
    )


class PolishOutput(HarnessModel):
    """DR-12, FR-AGENT-04. The style editor's `polish` call: the scene in the book's voice.

    One field, because the style editor's Figure 3 row grants one path: it rewrites
    `manuscript/NNN.md` and may touch nothing else. It runs on an already-accepted draft, so
    it has no violations to answer and nothing to propose - a style pass that discovered a
    fact about the world would be inventing one, and it holds no tool that could queue it.

    The polished body is re-checked by the mechanical lexicon and voice checks (FR-AUD-05,
    FR-AUD-07) before acceptance, because a pass over the prose is exactly where a forbidden
    variant gets reintroduced by a hand tidying a sentence.
    """

    body: str = Field(
        min_length=1,
        description="The polished prose, replacing `manuscript/NNN.md` in full.",
    )


class ExtractOutput(HarnessModel):
    """DR-12, FR-AGENT-05. The canoniser's `extract_facts` call over the accepted draft.

    The draft has already passed audit, so what this returns is read out of prose that will
    exist in the book. Its results are merged with the writer's own `proposed_facts`,
    deduplicated by `target_entity + target_field + normalised payload`; two roles looking
    for inventions is redundancy on purpose, since a detail neither of them queues is a
    detail that contradicts something in chapter forty.

    Like `WriterOutput.proposed_facts`, `facts` is required: an extractor that found nothing
    states it.
    """

    facts: list[ProposedFactDraft] = Field(
        description=(
            "Assertions about the world in the accepted draft that canon does not already "
            "hold. Merged with the writer's proposals, not trusted over them."
        ),
    )


class SemanticViolation(HarnessModel):
    """DR-12, FR-AGENT-06. One finding of the model-backed auditor, before it reaches the
    ledger.

    It carries neither `source` nor `resolution`, and the two omissions say different
    things. `source` is stamped `model` by the orchestrator, because which half of the audit
    a finding came from is a fact about the system rather than about the prose, and FR-AUD-09
    needs it to be true even when the model is confused about what it is. A model that could
    write `source: mechanical` could disguise a judgement as a deterministic check.

    `resolution` is absent because the auditor reports and does not repair (AC 16). Only a
    human sets it, through the auditor's route with `X-Actor: human`, and the prose or canon
    edit that follows goes through the role that owns that path. A schema that let the model
    decide `fix_prose` would hand the auditor the self-correction `architecture.md` names as
    its failure mode: it trims precisely the living details that made the scene work,
    because those are the ones that deviate from the plan.

    `invariant` is the shared 1-10 alias rather than only the numbers FR-AGENT-06 delegates
    here (3, 6, and the prose halves of 1 and 8). A narrower type would turn one
    out-of-remit finding into a whole-response schema failure, and FR-LLM-04 would then
    discard the correct findings alongside it; the orchestrator drops the single row
    instead, which loses less.
    """

    invariant: Invariant = Field(
        description=(
            "Which of the ten domain invariants of `definitions.md` the prose breaks. "
            "FR-AGENT-06 delegates 3, 6 and the prose halves of 1 and 8 to this role."
        ),
    )
    evidence: Evidence = Field(
        description=(
            "The offending quotation and its offset in the draft. It is what makes a "
            "judgement arguable: a wrong quote can be shown to be wrong."
        ),
    )
    severity: Severity = Field(
        description=(
            "`blocking`, `reviewable` or `note`. Only `blocking` stops the turn and reaches "
            "the revise step, so this is the field that decides whether the model's reading "
            "costs an iteration."
        ),
    )
    explanation: str = Field(
        min_length=1,
        description=(
            "Why the quoted span breaks that invariant, in one or two sentences. The "
            "reviewer of an escalation reads this to decide whether the finding is right."
        ),
    )


class SemanticAuditOutput(HarnessModel):
    """DR-12, FR-AGENT-06. Everything the semantic half of `audit` found in one scene.

    `violations` is required, and an empty list is the clean result. Absence of a finding and
    absence of an answer must never look alike here: FR-AUD-09 reports the model half as
    `skipped` when the step fails, precisely so that a silent audit is not read as a pass,
    and a schema in which the key could simply be missing would reopen that hole from the
    other side.

    The mechanical findings are already in the prompt as data, so the model is asked not to
    re-report them (FR-AGENT-07); what comes back here is the judgement half, and the
    orchestrator stamps `source: model` on each row before it reaches
    `ledger/violations.yaml`.
    """

    violations: list[SemanticViolation] = Field(
        description=(
            "The findings, or an empty list for a clean scene. Never omitted: silence and a "
            "pass are different answers."
        ),
    )


class DigestOutput(HarnessModel):
    """DR-12, FR-AGENT-03 and FR-AGENT-08. The writer's summary of a scene, chapter or arc.

    `words` and `level` are not here: the store layer measures the one and the caller knows
    the other, and a length a model reports about its own output is a claim rather than a
    measurement (DR-11). What the model is asked for is the two things it alone can produce -
    what changed, and whose eyes it changed in front of.

    **Failure mode** (`architecture.md` SceneDigest): treating the digest as canon. A digest
    records what the prose *said*; whether that becomes true of the world is decided by
    `promote`. That is why `delta` is prose and not a list of field updates - a shape that
    looked like canon would eventually be read as canon.

    `povs` is the field that earns its place. FR-OPS-03 filters by it, labelling a digest
    whose `povs` does not include the assembling scene's POV as events the POV did not
    witness. A name wrongly present hands a character knowledge nobody gave them - invariant
    1 broken by bookkeeping rather than by the prose - and a name wrongly absent loses a
    thread the POV lived through. The assembler has nothing else to go on; it never reads
    the prose the digest was made from.
    """

    delta: str = Field(
        min_length=1,
        description=(
            "What changed in the world, who learned what, which setups were paid. Roughly "
            "100 words at scene level, 250 at chapter, 400 at arc."
        ),
    )
    povs: list[EntityId] = Field(
        description=(
            "Whose scenes the digest covers. FR-OPS-03 filters by it, so it is a claim "
            "about witnessing and not a credit list."
        ),
    )


__all__ = [
    "DigestOutput",
    "ExtractOutput",
    "PolishOutput",
    "ProposedFactDraft",
    "ReviseOutput",
    "SemanticAuditOutput",
    "SemanticViolation",
    "WriterOutput",
]
