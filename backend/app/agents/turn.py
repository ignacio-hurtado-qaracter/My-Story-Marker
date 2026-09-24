"""The writing turn: Figure 4 as a state machine over the stores (FR-TURN-01..10, plan step 18).

    assemble -> write -> audit -> (revise -> audit)* -> polish -> recheck -> digest
             -> extract -> promote -> merged | awaiting_ruling          (else escalated)

**Each step is a fresh model call over the stores** (FR-TURN-01, FR-AGENT-11). A step reads what
it needs through the owning features' services -- the auditor the draft the writer's step
wrote to `manuscript/NNN.md`, the revise step the blocking violations the auditor's step wrote to
`ledger/violations.yaml` -- and the orchestrator hands it nothing but identifiers: the scene id,
the selected list from the turn record (FR-OPS-05) and the cap. The turn record is the only
thing carried from one step to the next, and it holds ids, counts and states, never text
(NFR-10). No transcript exists to carry.

**Every store write goes through the step's role** (FR-TURN-06): the persist functions of
`app.agents.service`, each of which asks the role's tool set first (FR-PERM-06), and the ledger's
`promote` under the canoniser. The orchestrator itself holds no role. Its own writes are the turn
record and the lock, under `.index/` (`records`, `lock`), which is not a store.

**The steps, and the decisions the spec left to this module.**

* *assemble* selects (FR-OPS-02) and puts the selected list on the record before anything else
  (FR-OPS-05), then assembles the writer's context with the writer's real system prompt and
  instruction, so a mandatory part over the cap stops the turn before any call (AC 22).
* *write* persists the draft and the writer's proposals under the writer.
* *audit* is the combined audit (FR-AGENT-07), persisted under the auditor. **In a turn, a
  semantic half that did not run escalates** with the failure's category: the report, mechanical
  findings and `skipped` included, is still written, but a draft whose invariants 1, 3, 6 and 8
  were never judged is not accepted. Blocking findings are then read back from the file; while
  any remain the draft is revised, at most `TURN_MAX_REVISIONS` times (FR-TURN-02).
* *revise* is measured by the diff guard (FR-AGENT-02): over `TURN_REVISE_MAX_CHANGED_RATIO` the
  revision is not written and is retried once with the stronger instruction; a second rejection
  escalates. A rejected revision does not count as one of the three.
* *polish* is followed by *recheck* (FR-AGENT-04): the mechanical lexicon and voice checks
  (FR-AUD-05, -07) re-run on the polished draft. **The re-check fails when the polish introduced
  a finding** -- a lexicon or voice finding whose quote the scene's mechanical findings on file
  (those of the accepted draft, resolved ones included) did not already hold. A failing re-check
  writes the polished draft's mechanical report under the auditor, so the evidence is on disk
  with offsets into the prose that is there, and escalates `polish_recheck`; the polished draft
  stays where the style editor put it. Nothing is reverted: a person decides. A passing re-check
  writes nothing.
* *digest* is the scene digest of the accepted draft (FR-AGENT-03). It runs after the re-check
  and before extraction: Figure 4 does not place it, and a digest is a summary of accepted prose,
  so it waits for acceptance like extraction does. The chapter hint for `rollup` is taken here.
* *extract* runs on the accepted draft only (FR-TURN-03); its facts join the writer's, one per
  `target_entity + target_field + normalised payload`, because both roles' proposals are queued
  under the id that key derives (`canoniser.proposal_id`).
* *promote* promotes each of this turn's pending facts under the canoniser, with `actor: agent`,
  and runs `reconcile(target_entity)` after every promotion (FR-TURN-04). A collision is left to
  a human: the turn ends `awaiting_ruling`. A fact `promote` refuses outright -- an entity that
  does not exist, a field no string fills -- stays `pending`, is listed as `refused` on the
  record and does not hold the turn: no ruling can make it promotable, and FR-TURN-05 blocks only
  on collisions.

**Escalation is terminal and never an empty draft** (Figure 4 note). A harness error from a
step -- a model failure after its retries, a refusal with its category, a budget overflow
before the call, a record that does not validate -- ends the turn `escalated` with the error's
IF-07 code as the category; the turn's own bounds (revisions, revise scope, polish re-check) have
categories of their own. Whatever the completed steps wrote stays on disk.

**Anything else is a crash, not an escalation.** An exception that is not a harness error leaves
the record as the last completed step wrote it, still `running`, and propagates; the lock is
released on the way out. `resume` continues such a turn from its cursor without re-running a
completed step (FR-TURN-09).
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable, Generator, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from types import TracebackType
from typing import Final

from pydantic import BaseModel

from app.agents import lock, records, service
from app.agents.models import RoleCall, RulingRequest, TurnEvent
from app.agents.roles import canoniser, style_editor, system_prompt, writer
from app.canon import service as canon_service
from app.commons.config import (
    CONTEXT_TOKEN_CAP,
    DIGEST_WORD_TARGETS,
    TURN_MAX_REVISIONS,
    Settings,
)
from app.commons.embeddings import Embedder
from app.commons.errors import (
    ContextBudgetExceeded,
    HarnessError,
    InvalidRecord,
    ModelCallFailed,
    ModelRefused,
    NotFound,
    TurnLocked,
)
from app.commons.llm import ModelClient
from app.commons.permissions import Actor, AgentRole
from app.commons.schemas import (
    AuditIteration,
    DigestMeasure,
    DraftMeasure,
    EscalationCategory,
    FactRecord,
    FactStatus,
    ModelCallRecord,
    ProposedFactDraft,
    RevisionScopeRecord,
    RulingKind,
    SelectedEntity,
    SkippedRecord,
    StepRecord,
    StepStatus,
    TurnEscalation,
    TurnOutcome,
    TurnRecord,
    TurnStep,
    Violation,
    ViolationSource,
    WriteRecord,
)
from app.commons.stores import Store, paths
from app.commons.stores.provenance import ProvenanceRecord
from app.ledger import audit as ledger_audit
from app.ledger import service as ledger_service
from app.ledger.models import Promoted
from app.manuscript import service as manuscript_service
from app.scenes import service as scenes_service
from app.scenes.models import AssembledContext

_LOG: Final[logging.Logger] = logging.getLogger(__name__)

STEP_ROLES: Final[Mapping[TurnStep, AgentRole | None]] = {
    TurnStep.ASSEMBLE: None,
    TurnStep.WRITE: AgentRole.WRITER,
    TurnStep.AUDIT: AgentRole.AUDITOR,
    TurnStep.REVISE: AgentRole.WRITER,
    TurnStep.POLISH: AgentRole.STYLE_EDITOR,
    TurnStep.RECHECK: AgentRole.AUDITOR,
    TurnStep.DIGEST: AgentRole.WRITER,
    TurnStep.EXTRACT: AgentRole.CANONISER,
    TurnStep.PROMOTE: AgentRole.CANONISER,
}
"""FR-TURN-06: the role Figure 4 gives each step. The assembly has none -- the orchestrator
holds no role -- and writes nothing to a store."""

RECHECK_CHECKS: Final[frozenset[str]] = frozenset({"FR-AUD-05", "FR-AUD-07"})
"""FR-AGENT-04: the checks a polished draft is held to before it is accepted -- the canonical
lexicon and the POV's voice, the two a style edit can break."""

RECHECK_INVARIANTS: Final[frozenset[int]] = frozenset(
    check.invariant for check in ledger_audit.MECHANICAL_CHECKS if check.check in RECHECK_CHECKS
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


# --- the context of a running turn ------------------------------------------------------


@dataclass(slots=True)
class TurnContext:
    """What every step receives: the dependencies, the cap, and the turn record.

    Nothing else. The record is the only state carried between steps, and it holds identifiers
    (FR-AGENT-11); every text a step needs, it reads from the stores itself.
    """

    store: Store
    client: ModelClient
    embedder: Embedder
    settings: Settings
    record: TurnRecord
    cap: int = CONTEXT_TOKEN_CAP

    @property
    def scene(self) -> str:
        return self.record.scene


class _Escalation(Exception):  # noqa: N818 - a control-flow signal, never raised to a caller
    """A step decided the turn cannot go on: the revise bound, the revise guard, the polish
    re-check, or a semantic audit that did not run. The step has already recorded itself."""

    def __init__(
        self,
        category: EscalationCategory,
        detail: str,
        *,
        refusal_category: str | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(detail)
        self.category = category
        self.detail = detail
        self.refusal_category = refusal_category
        self.reason = reason

    @classmethod
    def of(cls, error: HarnessError) -> _Escalation:
        return cls(
            _category(error),
            safe_detail(error),
            refusal_category=_context_text(error, "category")
            if isinstance(error, ModelRefused)
            else None,
            reason=_context_text(error, "reason") if isinstance(error, ModelCallFailed) else None,
        )


SAFE_CONTEXT_KEYS: Final[tuple[str, ...]] = (
    "file",
    "field",
    "path",
    "role",
    "kind",
    "identifier",
    "reason",
    "status",
    "counted",
    "cap",
    "category",
)
"""The error-body fields a turn record may repeat: identifiers, codes and counts."""


def safe_detail(error: HarnessError) -> str:
    """NFR-10. What a turn record says about an error: its code and its identifying fields,
    never its message. A message may quote what the model wrote -- an `InvalidRecord` from
    `promote` quotes the payload it could not place -- and the record lives outside the store
    tree, where no prompt or draft text may go."""
    parts = [error.code]
    for key in SAFE_CONTEXT_KEYS:
        value = error.context.get(key)
        if isinstance(value, str | int) and not isinstance(value, bool):
            parts.append(f"{key}={value}")
    return " ".join(parts)


def _category(error: HarnessError) -> EscalationCategory:
    try:
        return EscalationCategory(error.code)
    except ValueError:
        return EscalationCategory.HARNESS_ERROR


def _context_text(error: HarnessError, key: str) -> str | None:
    value = error.context.get(key)
    return value if isinstance(value, str) else None


# --- helpers every step shares ------------------------------------------------------------


def _iteration(record: TurnRecord, step: TurnStep) -> int:
    """0 for the written draft, k after revision k; a revision is numbered by the one it makes."""
    return record.revisions + 1 if step is TurnStep.REVISE else record.revisions


def _writes(lines: Iterable[ProvenanceRecord | None]) -> list[WriteRecord]:
    return [
        WriteRecord(
            path=line.path,
            role=line.role.value,
            actor=line.actor.value,
            content_hash=line.content_hash,
        )
        for line in lines
        if line is not None
    ]


def _call_record[T: BaseModel](call: RoleCall[T]) -> ModelCallRecord:
    """FR-TURN-07, FR-CTX-06, NFR-10. What the record says about one call: figures, never text."""
    completion = call.completion
    usage = completion.usage
    return ModelCallRecord(
        requested_model=completion.requested_model,
        model_id=completion.model_id,
        prompt_version=call.prompt_version,
        estimate=completion.estimate,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_input_tokens=usage.cache_read_input_tokens,
        cache_creation_input_tokens=usage.cache_creation_input_tokens,
        over_cap=completion.over_cap,
        attempts=completion.attempts,
        elapsed_seconds=completion.elapsed_seconds,
        cli_version=completion.cli_version,
    )


def _step[T: BaseModel](
    ctx: TurnContext,
    step: TurnStep,
    started: str,
    *,
    call: RoleCall[T] | None = None,
    status: StepStatus = StepStatus.COMPLETED,
    writes: Iterable[ProvenanceRecord | None] = (),
    estimate: int | None = None,
    removed: Sequence[str] = (),
    truncated_at: str | None = None,
    scope: RevisionScopeRecord | None = None,
    error: str | None = None,
) -> StepRecord:
    """One step's record. A model call supplies its own estimate and pruning (FR-CTX-03)."""
    role = STEP_ROLES[step]
    return StepRecord(
        step=step,
        iteration=_iteration(ctx.record, step),
        role=role.value if role is not None else None,
        status=status,
        started_at=started,
        ended_at=_now(),
        estimate=call.completion.estimate if call is not None else estimate,
        call=_call_record(call) if call is not None else None,
        removed=list(call.removed) if call is not None else list(removed),
        truncated_at=call.truncated_at if call is not None else truncated_at,
        writes=_writes(writes),
        scope=scope,
        error=error,
    )


def _measure_draft(ctx: TurnContext) -> None:
    """FR-TURN-07: the draft's `words`, measured on write (DR-11), against the scene budget."""
    draft = manuscript_service.read_draft(ctx.store, ctx.scene)
    budget = scenes_service.read_scene(ctx.store, ctx.scene).budget
    ctx.record.draft = DraftMeasure(words=draft.words, budget=budget)


def _note_facts(ctx: TurnContext, facts: Iterable[ProposedFactDraft], role: AgentRole) -> None:
    """This turn's proposals, one entry per queue id: the writer's first, then the canoniser's,
    a fact both found noted once with both roles (FR-AGENT-05)."""
    by_id = {fact.fact_id: fact for fact in ctx.record.facts}
    for proposal in facts:
        identifier = canoniser.proposal_id(ctx.scene, proposal)
        known = by_id.get(identifier)
        if known is None:
            known = FactRecord(
                fact_id=identifier,
                target_entity=proposal.target_entity,
                target_field=proposal.target_field,
            )
            ctx.record.facts.append(known)
            by_id[identifier] = known
        if role.value not in known.proposed_by:
            known.proposed_by = [*known.proposed_by, role.value]


def _reconcile(store: Store, fact: FactRecord) -> None:
    """FR-TURN-04, FR-OPS-08. The work that depends on the fact's target, named now."""
    result = canon_service.reconcile(store, fact.target_entity)
    scenes = [dependent.id for dependent in result.scenes]
    fact.reconciled_scenes = scenes
    fact.written_scenes = [scene for scene in scenes if store.exists(paths.draft(scene))]
    fact.reconciled_turns = [dependent.id for dependent in result.turns]


def _chapter_hint(ctx: TurnContext) -> None:
    """FR-TURN-07: whether the scene closes its chapter, and whether every scene of the chapter
    now has the digest a rollup reads (FR-AGENT-08; rollup stays a manual call in v1)."""
    if not ctx.store.exists(paths.CHAPTERS):
        return
    for chapter in scenes_service.read_chapters(ctx.store).chapters:
        if ctx.scene in chapter.scenes:
            ctx.record.chapter = chapter.id
            ctx.record.closes_chapter = chapter.scenes[-1] == ctx.scene
            ctx.record.rollup_ready = all(
                ctx.store.exists(paths.digest(scene)) for scene in chapter.scenes
            )
            return


def writer_context(
    store: Store, scene_id: str, selected: Sequence[SelectedEntity], *, cap: int
) -> AssembledContext:
    """FR-OPS-03, FR-TURN-10. The writer's context exactly as `writer.write` assembles it: the
    writer's system prompt, its instruction and the scene record counted in the mandatory part.
    Built here too because the assembly step and `dry_run` must stop where the call would."""
    scene = scenes_service.read_scene(store, scene_id)
    instruction = writer.scene_write_instruction(store, scene_id, selected)
    return scenes_service.assemble_context(
        store,
        scene_id,
        selected,
        system=system_prompt(AgentRole.WRITER),
        instruction=instruction,
        cap=cap,
        role_inputs=[(paths.scene(scene_id), scenes_service.render_record(scene))],
    )


# --- the steps --------------------------------------------------------------------------


def _assemble(ctx: TurnContext, started: str) -> None:
    """FR-OPS-02, FR-OPS-05, FR-OPS-03. Select, record the list at once, assemble to the cap."""
    selection = scenes_service.select_entities(ctx.store, ctx.embedder, ctx.settings, ctx.scene)
    ctx.record.selected = list(selection.entities)
    records.save(ctx.store, ctx.record)
    context = writer_context(ctx.store, ctx.scene, ctx.record.selected, cap=ctx.cap)
    ctx.record.steps.append(
        _step(
            ctx,
            TurnStep.ASSEMBLE,
            started,
            estimate=context.estimate,
            removed=context.removed,
            truncated_at=context.truncated_at,
        )
    )
    ctx.record.next_step = TurnStep.WRITE


def _write(ctx: TurnContext, started: str) -> None:
    """FR-AGENT-01. The draft to `manuscript/NNN.md`, the proposals to the queue, as the writer."""
    # `writer.write` is the role's model call, not a store write. Its arguments are named because
    # AC 13's rule reads every `<x>.write(<first argument>, ...)` as a store write whose path it
    # must prove is not canon, and a named call is not that shape.
    call = writer.write(
        store=ctx.store,
        client=ctx.client,
        scene_id=ctx.scene,
        selected=ctx.record.selected,
        cap=ctx.cap,
    )
    draft = service.persist_draft(ctx.store, ctx.scene, call.output.body, role=AgentRole.WRITER)
    queued = service.persist_proposals(
        ctx.store, ctx.scene, call.output.proposed_facts, role=AgentRole.WRITER
    )
    _note_facts(ctx, call.output.proposed_facts, AgentRole.WRITER)
    _measure_draft(ctx)
    ctx.record.steps.append(_step(ctx, TurnStep.WRITE, started, call=call, writes=[draft, queued]))
    ctx.record.next_step = TurnStep.AUDIT


def _skipped(report: ledger_audit.AuditReport) -> list[SkippedRecord]:
    return [
        SkippedRecord(
            check=skip.check, invariant=skip.invariant, source=skip.source.value, reason=skip.reason
        )
        for skip in report.skipped
    ]


def _audit(ctx: TurnContext, started: str) -> None:
    """FR-AGENT-07, FR-AGENT-11, FR-TURN-02. The combined audit of the draft on disk, written
    under the auditor; the blocking findings are then read back from the file it wrote."""
    combined = service.audit(ctx.store, ctx.client, ctx.scene, ctx.record.selected, cap=ctx.cap)
    persisted = service.persist_audit(ctx.store, combined.report)
    blocking = [finding.id for finding in writer.blocking_violations(ctx.store, ctx.scene)]
    ctx.record.iterations.append(
        AuditIteration(
            iteration=ctx.record.revisions,
            violations=[finding.id for finding in combined.report.violations],
            blocking=blocking,
            skipped=_skipped(combined.report),
        )
    )
    failure = combined.failure
    call = combined.semantic.call if combined.semantic is not None else None
    counted = failure.context.get("counted") if isinstance(failure, ContextBudgetExceeded) else None
    ctx.record.steps.append(
        _step(
            ctx,
            TurnStep.AUDIT,
            started,
            call=call,
            status=StepStatus.FAILED if failure is not None else StepStatus.COMPLETED,
            writes=[persisted],
            estimate=counted if isinstance(counted, int) else None,
            error=failure.code if failure is not None else None,
        )
    )
    if failure is not None:
        raise _Escalation.of(failure)
    if not blocking:
        ctx.record.next_step = TurnStep.POLISH
        return
    if ctx.record.revisions >= TURN_MAX_REVISIONS:
        detail = (
            f"{len(blocking)} blocking violation(s) still open after {TURN_MAX_REVISIONS} "
            f"revisions (FR-TURN-02): {', '.join(blocking)}"
        )
        raise _Escalation(EscalationCategory.REVISION_BOUND, detail)
    ctx.record.next_step = TurnStep.REVISE


def _revise(ctx: TurnContext, started: str) -> None:
    """FR-AGENT-02. Only the flagged spans; a revision that changed too much is not written."""
    if not writer.blocking_violations(ctx.store, ctx.scene):
        # Resolved by a person since the audit (IF-04): nothing to revise, so audit again.
        ctx.record.steps.append(_step(ctx, TurnStep.REVISE, started))
        ctx.record.next_step = TurnStep.AUDIT
        return
    before = manuscript_service.read_draft(ctx.store, ctx.scene).body
    strict = ctx.record.revise_rejections > 0
    call = writer.revise(
        ctx.store, ctx.client, ctx.scene, ctx.record.selected, strict=strict, cap=ctx.cap
    )
    measured = writer.revision_scope(
        before, call.output.body, ctx.settings.turn_revise_max_changed_ratio
    )
    scope = RevisionScopeRecord(
        ratio=measured.ratio,
        limit=measured.limit,
        sentences=measured.sentences,
        changed=measured.changed,
        within=measured.within,
    )
    if not measured.within:
        ctx.record.steps.append(
            _step(ctx, TurnStep.REVISE, started, call=call, status=StepStatus.REJECTED, scope=scope)
        )
        if ctx.record.revise_rejections == 0:
            ctx.record.revise_rejections = 1
            ctx.record.next_step = TurnStep.REVISE
            return
        detail = (
            f"the revision changed {measured.ratio:.0%} of the draft's sentences, over the "
            f"{measured.limit:.0%} limit, twice (FR-AGENT-02)"
        )
        raise _Escalation(EscalationCategory.REVISE_SCOPE, detail)
    draft = service.persist_draft(ctx.store, ctx.scene, call.output.body, role=AgentRole.WRITER)
    ctx.record.steps.append(
        _step(ctx, TurnStep.REVISE, started, call=call, writes=[draft], scope=scope)
    )
    ctx.record.revisions += 1
    ctx.record.revise_rejections = 0
    _measure_draft(ctx)
    ctx.record.next_step = TurnStep.AUDIT


def _polish(ctx: TurnContext, started: str) -> None:
    """FR-AGENT-04. The clean draft in the book's voice, written by the style editor."""
    call = style_editor.polish(ctx.store, ctx.client, ctx.scene, cap=ctx.cap)
    draft = service.persist_draft(
        ctx.store, ctx.scene, call.output.body, role=AgentRole.STYLE_EDITOR
    )
    _measure_draft(ctx)
    ctx.record.steps.append(_step(ctx, TurnStep.POLISH, started, call=call, writes=[draft]))
    ctx.record.next_step = TurnStep.RECHECK


def _finding_key(finding: Violation) -> tuple[int, str]:
    return finding.invariant, finding.evidence.quote.casefold()


def _recheck(ctx: TurnContext, started: str) -> None:
    """FR-AGENT-04, FR-AUD-05, FR-AUD-07. The polished draft against the lexicon and the voice,
    compared with the mechanical findings on file for the accepted draft (module docstring)."""
    on_file = (
        ledger_service.violations(ctx.store).violations
        if ctx.store.exists(paths.VIOLATIONS)
        else []
    )
    baseline = Counter(
        _finding_key(finding)
        for finding in on_file
        if finding.scene == ctx.scene
        and finding.source is ViolationSource.MECHANICAL
        and finding.invariant in RECHECK_INVARIANTS
    )
    report = ledger_audit.audit_scene(ctx.store, ctx.scene, semantic=False)
    introduced: list[str] = []
    for finding in report.violations:
        if finding.invariant not in RECHECK_INVARIANTS:
            continue
        key = _finding_key(finding)
        if baseline[key] > 0:
            baseline[key] -= 1
        else:
            introduced.append(finding.id)
    if not introduced:
        ctx.record.steps.append(_step(ctx, TurnStep.RECHECK, started))
        ctx.record.next_step = TurnStep.DIGEST
        return
    persisted = service.persist_audit(ctx.store, report)
    ctx.record.steps.append(
        _step(
            ctx,
            TurnStep.RECHECK,
            started,
            status=StepStatus.FAILED,
            writes=[persisted],
            error=EscalationCategory.POLISH_RECHECK.value,
        )
    )
    detail = (
        f"the polished draft has {len(introduced)} lexicon or voice finding(s) the accepted "
        f"draft did not (FR-AGENT-04): {', '.join(introduced)}"
    )
    raise _Escalation(EscalationCategory.POLISH_RECHECK, detail)


def _digest(ctx: TurnContext, started: str) -> None:
    """FR-AGENT-03. The scene digest of the accepted draft, as the writer; measured on write."""
    result = writer.digest(ctx.store, ctx.client, ctx.scene, cap=ctx.cap)
    persisted = service.persist_digest(ctx.store, result)
    written = manuscript_service.read_digest(ctx.store, result.digest_id)
    measure = DigestMeasure(
        digest_id=result.digest_id,
        level=written.level,
        words=written.words,
        target=DIGEST_WORD_TARGETS[written.level.value],
    )
    ctx.record.digests = [
        *(kept for kept in ctx.record.digests if kept.digest_id != measure.digest_id),
        measure,
    ]
    _chapter_hint(ctx)
    ctx.record.steps.append(
        _step(ctx, TurnStep.DIGEST, started, call=result.call, writes=[persisted])
    )
    ctx.record.next_step = TurnStep.EXTRACT


def _extract(ctx: TurnContext, started: str) -> None:
    """FR-AGENT-05, FR-TURN-03. Facts the accepted draft asserts, queued under the canoniser."""
    call = canoniser.extract_facts(
        ctx.store, ctx.client, ctx.scene, ctx.record.selected, cap=ctx.cap
    )
    queued = service.persist_proposals(
        ctx.store, ctx.scene, call.output.facts, role=AgentRole.CANONISER
    )
    _note_facts(ctx, call.output.facts, AgentRole.CANONISER)
    ctx.record.steps.append(_step(ctx, TurnStep.EXTRACT, started, call=call, writes=[queued]))
    ctx.record.next_step = TurnStep.PROMOTE


def _promote(ctx: TurnContext, started: str) -> None:
    """FR-OPS-06, FR-TURN-04. Each of this turn's pending facts, promoted or escalated; the
    record saved after every one, so a resume never promotes a fact twice."""
    writes: list[ProvenanceRecord] = []
    for fact in ctx.record.facts:
        if fact.settled:
            continue
        queued = {entry.id: entry for entry in ledger_service.proposed(ctx.store).proposed}
        entry = queued.get(fact.fact_id)
        if entry is None:
            fact.refused = f"{fact.fact_id} is not in {paths.PROPOSED}"
        elif entry.status is not FactStatus.PENDING:
            fact.status = entry.status
            if entry.status is FactStatus.PROMOTED:
                _reconcile(ctx.store, fact)
        elif entry.conflict:
            fact.conflict = True
        else:
            try:
                result = ledger_service.promote(
                    ctx.store,
                    fact.fact_id,
                    role=AgentRole.CANONISER,
                    actor=Actor.AGENT,
                    scene=ctx.scene,
                    turn=ctx.record.id,
                )
            except InvalidRecord as refusal:
                fact.refused = safe_detail(refusal)
            else:
                writes.extend(result.writes)
                if isinstance(result, Promoted):
                    fact.status = FactStatus.PROMOTED
                    fact.changed = result.changed
                    _reconcile(ctx.store, fact)
                else:
                    fact.conflict = True
        records.save(ctx.store, ctx.record)
    ctx.record.steps.append(_step(ctx, TurnStep.PROMOTE, started, writes=writes))
    ctx.record.outcome = (
        TurnOutcome.AWAITING_RULING if _awaiting(ctx.record) else TurnOutcome.MERGED
    )
    ctx.record.ended_at = _now()
    ctx.record.next_step = TurnStep.DONE


def _awaiting(record: TurnRecord) -> list[FactRecord]:
    """The facts of the turn that wait for a human ruling (FR-TURN-04, FR-TURN-08)."""
    return [fact for fact in record.facts if fact.conflict and fact.status is FactStatus.PENDING]


STEPS: Final[Mapping[TurnStep, Callable[[TurnContext, str], None]]] = {
    TurnStep.ASSEMBLE: _assemble,
    TurnStep.WRITE: _write,
    TurnStep.AUDIT: _audit,
    TurnStep.REVISE: _revise,
    TurnStep.POLISH: _polish,
    TurnStep.RECHECK: _recheck,
    TurnStep.DIGEST: _digest,
    TurnStep.EXTRACT: _extract,
    TurnStep.PROMOTE: _promote,
}


# --- the driver -----------------------------------------------------------------------------


def _escalate(record: TurnRecord, step: TurnStep, iteration: int, stop: _Escalation) -> None:
    record.escalation = TurnEscalation(
        category=stop.category,
        step=step,
        iteration=iteration,
        detail=stop.detail,
        refusal_category=stop.refusal_category,
        reason=stop.reason,
    )
    record.outcome = TurnOutcome.ESCALATED
    record.ended_at = _now()
    record.next_step = TurnStep.DONE


def _failed(ctx: TurnContext, step: TurnStep, started: str, error: HarnessError) -> StepRecord:
    """A step a harness error stopped. The cap's refusal keeps its estimate (FR-CTX-05)."""
    counted = error.context.get("counted") if isinstance(error, ContextBudgetExceeded) else None
    return _step(
        ctx,
        step,
        started,
        status=StepStatus.FAILED,
        estimate=counted if isinstance(counted, int) else None,
        error=error.code,
    )


def _log(record: TurnRecord, step: TurnStep) -> None:
    """NFR-10. One structured line per step: role, model, prompt version, tokens, elapsed --
    never a prompt, a document or a draft."""
    last = record.steps[-1] if record.steps else None
    call = last.call if last is not None else None
    _LOG.info(
        "turn %s step %s: %s",
        record.id,
        step.value,
        last.status.value if last is not None else "none",
        extra={
            "turn": record.id,
            "scene": record.scene,
            "step": step.value,
            "role": last.role if last is not None else None,
            "model_id": call.model_id if call is not None else None,
            "prompt_version": call.prompt_version if call is not None else None,
            "estimate": last.estimate if last is not None else None,
            "input_tokens": call.input_tokens if call is not None else None,
            "output_tokens": call.output_tokens if call is not None else None,
            "cache_read_input_tokens": call.cache_read_input_tokens if call is not None else None,
            "elapsed_seconds": call.elapsed_seconds if call is not None else None,
            "outcome": record.outcome.value,
        },
    )


def _event(record: TurnRecord, step: TurnStep) -> TurnEvent:
    last = record.steps[-1] if record.steps and record.steps[-1].step is step else None
    return TurnEvent(
        kind="step",
        turn_id=record.id,
        scene=record.scene,
        step=step,
        iteration=last.iteration if last is not None else _iteration(record, step),
        status=last.status if last is not None else None,
        outcome=record.outcome,
        next_step=record.next_step,
        escalation=record.escalation.category if record.escalation is not None else None,
    )


def drive(ctx: TurnContext) -> Iterator[TurnEvent]:
    """Run the turn from its cursor to a terminal state, one event per step, then the outcome.

    The record is saved after every step (FR-TURN-07). A harness error or a step's own
    escalation ends the turn `escalated`; any other exception propagates with the record as the
    last completed step left it.
    """
    record = ctx.record
    while record.next_step is not TurnStep.DONE:
        step = record.next_step
        iteration = _iteration(record, step)
        started = _now()
        try:
            STEPS[step](ctx, started)
        except _Escalation as stop:
            _escalate(record, step, iteration, stop)
        except HarnessError as error:
            record.steps.append(_failed(ctx, step, started, error))
            _escalate(record, step, iteration, _Escalation.of(error))
        records.save(ctx.store, record)
        _log(record, step)
        yield _event(record, step)
    yield TurnEvent(
        kind="outcome",
        turn_id=record.id,
        scene=record.scene,
        outcome=record.outcome,
        next_step=record.next_step,
        escalation=record.escalation.category if record.escalation is not None else None,
    )


class TurnRun:
    """A turn holding the store root's lock, ready to run (FR-TURN-05).

    The lock is released on every exit path: when `events` finishes, raises or is closed, and by
    `close`, which is idempotent and is what a caller that never iterates must call. Usable as a
    context manager for exactly that.
    """

    def __init__(self, ctx: TurnContext, handle: lock.TurnLockHandle) -> None:
        self._ctx = ctx
        self._handle = handle
        self._closed = False

    @property
    def record(self) -> TurnRecord:
        return self._ctx.record

    def events(self) -> Generator[TurnEvent]:
        """The turn, step by step. Releases the lock when it ends, however it ends."""
        try:
            yield from drive(self._ctx)
        finally:
            self.close()

    def run(self) -> TurnRecord:
        """Run to the end and return the record."""
        for _ in self.events():
            pass
        return self.record

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            lock.release(self._handle)

    def __enter__(self) -> TurnRun:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


# --- entry points ---------------------------------------------------------------------------


def _refuse_pending_collisions(store: Store, scene_id: str) -> None:
    """FR-TURN-05. No turn on a scene while a collision from an earlier turn of it waits for a
    human ruling: the next draft would be written against a canon nobody has settled."""
    if not store.exists(paths.PROPOSED):
        return
    waiting = [
        fact.id
        for fact in ledger_service.proposed(store).proposed
        if fact.source_scene == scene_id and fact.status is FactStatus.PENDING and fact.conflict
    ]
    if waiting:
        message = (
            f"scene {scene_id} has fact(s) pending a human ruling after a collision: "
            f"{', '.join(waiting)}. Rule on them first (FR-TURN-05, FR-TURN-08)"
        )
        raise TurnLocked(message, scene=scene_id)


def begin_turn(
    store: Store,
    client: ModelClient,
    embedder: Embedder,
    settings: Settings,
    scene_id: str,
    *,
    cap: int = CONTEXT_TOKEN_CAP,
) -> TurnRun:
    """FR-TURN-01, FR-TURN-05. A new turn on `scene_id`, locked and recorded, not yet run.

    Refused before anything is written: a scene with no record (404), another turn running on
    the store root (409), a collision of this scene waiting for a ruling (409).
    """
    scenes_service.read_scene(store, scene_id)
    identifier = records.next_turn_id(store, scene_id)
    handle = lock.acquire(store.index_dir, identifier)
    try:
        if records.next_turn_id(store, scene_id) != identifier:
            message = f"another turn of scene {scene_id} started meanwhile; start again"
            raise TurnLocked(message, scene=scene_id)
        _refuse_pending_collisions(store, scene_id)
        record = TurnRecord(id=identifier, scene=scene_id, started_at=_now())
        records.save(store, record)
    except BaseException:
        lock.release(handle)
        raise
    context = TurnContext(store, client, embedder, settings, record, cap)
    return TurnRun(context, handle)


def resume_turn(
    store: Store,
    client: ModelClient,
    embedder: Embedder,
    settings: Settings,
    turn_id: str,
    *,
    cap: int = CONTEXT_TOKEN_CAP,
) -> TurnRun:
    """FR-TURN-09. A `running` turn, continued from its record's cursor: the steps it records as
    done are not run again. A turn that ended is not resumable (409); a lock the crashed turn
    left behind is taken over (`lock.acquire`)."""
    _refuse_unless_running(records.load(store, turn_id))
    handle = lock.acquire(store.index_dir, turn_id, take_over=True)
    try:
        record = records.load(store, turn_id)
        _refuse_unless_running(record)
    except BaseException:
        lock.release(handle)
        raise
    context = TurnContext(store, client, embedder, settings, record, cap)
    return TurnRun(context, handle)


def _refuse_unless_running(record: TurnRecord) -> None:
    if record.outcome is not TurnOutcome.RUNNING:
        message = (
            f"turn {record.id} is {record.outcome.value}; only a running turn can be resumed "
            "(FR-TURN-09)"
        )
        raise TurnLocked(message, scene=record.scene)


def run_turn(
    store: Store,
    client: ModelClient,
    embedder: Embedder,
    settings: Settings,
    scene_id: str,
    *,
    cap: int = CONTEXT_TOKEN_CAP,
) -> TurnRecord:
    """`begin_turn`, run to the end."""
    return begin_turn(store, client, embedder, settings, scene_id, cap=cap).run()


def resume(
    store: Store,
    client: ModelClient,
    embedder: Embedder,
    settings: Settings,
    turn_id: str,
    *,
    cap: int = CONTEXT_TOKEN_CAP,
) -> TurnRecord:
    """`resume_turn`, run to the end."""
    return resume_turn(store, client, embedder, settings, turn_id, cap=cap).run()


def dry_run(
    store: Store,
    embedder: Embedder,
    settings: Settings,
    scene_id: str,
    *,
    cap: int = CONTEXT_TOKEN_CAP,
) -> AssembledContext:
    """FR-TURN-10. Assembly only: the writer's context with its estimate and the selected ids,
    no model call, no turn record and no lock -- nothing is written but the derived index."""
    selection = scenes_service.select_entities(store, embedder, settings, scene_id)
    return writer_context(store, scene_id, selection.entities, cap=cap)


def apply_rulings(
    store: Store,
    turn_id: str,
    rulings: Sequence[RulingRequest],
    *,
    role: AgentRole,
    actor: Actor,
) -> TurnRecord:
    """FR-TURN-08, FR-OPS-07. A human's rulings on the turn's collided facts.

    Everything that can be checked is checked before the first ruling lands, so a batch is
    applied whole or not at all: the turn is `awaiting_ruling`, each fact is one of its
    collisions, none twice, and every reason says something. The role and the actor are the
    ledger's `rule` to refuse (403), which it does before reading anything. An accepted fact is
    reconciled (FR-TURN-04); the turn is `merged` once no collision is left.
    """
    record = records.load(store, turn_id)
    if record.outcome is not TurnOutcome.AWAITING_RULING:
        message = f"turn {turn_id} is {record.outcome.value}, not awaiting a ruling (FR-TURN-08)"
        raise TurnLocked(message, scene=record.scene)
    waiting = {fact.fact_id: fact for fact in _awaiting(record)}
    seen: set[str] = set()
    for ruling in rulings:
        if ruling.fact_id not in waiting:
            message = f"turn {turn_id} has no collision waiting on fact {ruling.fact_id}"
            raise NotFound(message, kind="fact", identifier=ruling.fact_id)
        if ruling.fact_id in seen:
            message = f"fact {ruling.fact_id} is ruled on twice in one request"
            raise InvalidRecord(message, file=paths.PROPOSED, field="fact_id")
        if not ruling.reason.strip():
            message = f"the ruling on {ruling.fact_id} needs a reason (FR-OPS-07)"
            raise InvalidRecord(message, file=paths.PROPOSED, field="reason")
        seen.add(ruling.fact_id)
    handle = lock.acquire(store.index_dir, turn_id)
    try:
        for ruling in rulings:
            fact = waiting[ruling.fact_id]
            applied = ledger_service.rule(
                store,
                ruling.fact_id,
                ruling.ruling,
                ruling.reason,
                role=role,
                actor=actor,
                scene=record.scene,
                turn=record.id,
            )
            fact.ruling = ruling.ruling
            if ruling.ruling is RulingKind.ACCEPT:
                fact.status = FactStatus.PROMOTED
                fact.changed = applied.changed
                _reconcile(store, fact)
            else:
                fact.status = FactStatus.REJECTED
            records.save(store, record)
        if not _awaiting(record):
            record.outcome = TurnOutcome.MERGED
            record.ended_at = _now()
        records.save(store, record)
    finally:
        lock.release(handle)
    return record


__all__ = [
    "RECHECK_CHECKS",
    "RECHECK_INVARIANTS",
    "STEPS",
    "STEP_ROLES",
    "TurnContext",
    "TurnRun",
    "apply_rulings",
    "begin_turn",
    "drive",
    "dry_run",
    "resume",
    "resume_turn",
    "run_turn",
    "writer_context",
]
