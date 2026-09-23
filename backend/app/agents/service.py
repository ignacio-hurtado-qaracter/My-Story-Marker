"""The agents feature's operations: persisting role outputs, the combined audit, and rollup.

**Roles read; this module writes, and only through a role's tool set** (FR-PERM-06,
FR-TURN-06). A role function in `app.agents.roles` returns a value and touches no store. Each
function below turns one kind of output into one store write, and does it in the same two
steps every time: first `toolset_for(role).authorise(target)` -- the write table's answer to
"may this role's output land here?", a `PermissionDenied` before anything is read or written
when it may not -- and then the owning feature's service, under that role and with
`actor: agent`, because the content is a model's even when a person asked for it (Decision
R2-7). The store layer asks Figure 3 again inside `Store.write` (FR-PERM-03); the tool set is
the same table asked first, so a write routed to the wrong target fails without side effects.

| Output | Target | Role (Figure 4) | Through |
|---|---|---|---|
| `WriterOutput.body`, `ReviseOutput.body` | `manuscript/NNN.md` | writer | `persist_draft` |
| `PolishOutput.body` | `manuscript/NNN.md` | style editor | `persist_draft` |
| proposed facts | `ledger/proposed.yaml`, appended | writer or canoniser | `persist_proposals` |
| `DigestOutput` | `manuscript/digests/NNN.md` | writer | `persist_digest` |
| the combined audit | `ledger/violations.yaml`, merged | auditor | `persist_audit` |

**The combined audit** (`audit`, FR-AGENT-07) runs the mechanical checks, hands their findings
to the auditor role as data, and folds the role's answer into one report; a model step that
fails leaves the semantic halves in `skipped` (FR-AUD-09) and the failure on the result.
`semantic_auditor` is the same half packaged as `commons.deps.SemanticAuditor`, which `main.py`
wires into the audit route: the route lives in `scenes` and cannot import this feature.

**Rollup** (`rollup`, FR-AGENT-08, IF-06) plans first, authorises the target under the calling
role, and only then spends a model call: a refused role or a partial chapter costs nothing.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from app.agents.models import CombinedAudit, DigestResult, RollupResponse, SemanticAuditResult
from app.agents.roles import auditor, canoniser, writer
from app.commons.config import CONTEXT_TOKEN_CAP, Settings
from app.commons.deps import (
    EmbedderDep,
    ModelClientDep,
    SemanticAuditor,
    SemanticFindings,
    SemanticSkip,
    SettingsDep,
)
from app.commons.embeddings import Embedder
from app.commons.errors import (
    ContextBudgetExceeded,
    HarnessError,
    InvalidRecord,
    MalformedModelOutput,
    ModelCallFailed,
    ModelRefused,
    NotFound,
    OutputTruncated,
)
from app.commons.llm import ModelClient
from app.commons.permissions import Actor, AgentRole, ToolOperation, toolset_for
from app.commons.schemas import (
    Draft,
    ProposedFact,
    ProposedFactDraft,
    SelectedEntity,
    Violation,
)
from app.commons.stores import Store, paths
from app.commons.stores.provenance import ProvenanceRecord
from app.ledger import audit as ledger_audit
from app.ledger import service as ledger_service
from app.manuscript import service as manuscript_service
from app.scenes import service as scenes_service

MODEL_STEP_FAILURES: Final[tuple[type[HarnessError], ...]] = (
    ModelCallFailed,
    MalformedModelOutput,
    ModelRefused,
    OutputTruncated,
    ContextBudgetExceeded,
)
"""FR-AUD-09's "the model step fails": every way the auditor's call can end without a valid
answer -- the process, the output, a refusal, a truncation, or a mandatory part over the cap
that stopped the call before it was made (FR-CTX-05). Anything else -- a record that does not
validate, a scene that does not exist -- is not a model failure and propagates, as it would
have from the mechanical half."""


# --- persisting outputs, one function per output -------------------------------------------


def persist_draft(
    store: Store, scene_id: str, body: str, *, role: AgentRole = AgentRole.WRITER
) -> ProvenanceRecord:
    """A scene's prose to `manuscript/NNN.md`: the writer's draft or revision, or the style
    editor's polish (Figure 4). `words` and `literal_tail` are derived by the manuscript
    feature from the body, never taken from a model (DR-11)."""
    toolset_for(role).authorise(paths.draft(scene_id))
    record = Draft(scene_ref=scene_id, words=0, literal_tail="", body=body)
    return manuscript_service.save_draft(store, scene_id, record, role=role, actor=Actor.AGENT)


def persist_proposals(
    store: Store,
    scene_id: str,
    facts: Sequence[ProposedFactDraft],
    *,
    role: AgentRole = AgentRole.WRITER,
) -> ProvenanceRecord | None:
    """FR-AGENT-01, FR-AGENT-05. Proposed facts appended to `ledger/proposed.yaml`, `pending`.

    Each gets `canoniser.proposal_id`, derived from its address and normalised payload, and
    one whose id the queue already holds -- proposed in an earlier iteration, or by the other
    role -- is not queued again; nor is a repeat within `facts`. Nothing left to queue writes
    nothing and returns None. The tool is an append (FR-PERM-06): the queue is added to, never
    rewritten. The draft the facts were read from is `extracted_from`; their quoted evidence has
    no field in DR-07's `ProposedFact` and is not stored.
    """
    toolset_for(role).authorise(paths.PROPOSED, ToolOperation.APPEND)
    queued = (
        {fact.id for fact in ledger_service.proposed(store).proposed}
        if store.exists(paths.PROPOSED)
        else set()
    )
    fresh: list[ProposedFact] = []
    for fact in facts:
        identifier = canoniser.proposal_id(scene_id, fact)
        if identifier in queued:
            continue
        queued.add(identifier)
        fresh.append(
            ProposedFact(
                id=identifier,
                extracted_from=paths.draft(scene_id),
                target_entity=fact.target_entity,
                target_field=fact.target_field,
                payload=fact.payload,
                source_scene=scene_id,
            )
        )
    if not fresh:
        return None
    request = ledger_service.ProposedAppend(facts=fresh)
    return ledger_service.append_proposed(store, request, role=role, actor=Actor.AGENT)


def persist_digest(
    store: Store, result: DigestResult, *, role: AgentRole = AgentRole.WRITER
) -> ProvenanceRecord:
    """FR-AGENT-03, FR-AGENT-08. A digest to `manuscript/digests/NNN.md`; `words` is measured
    again on write (DR-11)."""
    toolset_for(role).authorise(paths.digest(result.digest_id))
    return manuscript_service.save_digest(
        store, result.digest_id, result.record, role=role, actor=Actor.AGENT
    )


def persist_audit(
    store: Store, report: ledger_audit.AuditReport, *, role: AgentRole = AgentRole.AUDITOR
) -> ProvenanceRecord:
    """AC 16. An audit merged into `ledger/violations.yaml` under the auditor. Each half's
    findings are reconsidered only by that half's checks (`ledger.audit.merge`), so persisting
    a report whose model step failed never retracts a model finding."""
    toolset_for(role).authorise(paths.VIOLATIONS)
    return ledger_audit.persist(store, report, role=role, actor=Actor.AGENT)


# --- the combined audit ---------------------------------------------------------------------


def _skip_all(reason: str) -> SemanticFindings:
    """FR-AUD-09. Every semantic half listed as not checked, with one reason."""
    return SemanticFindings(
        violations=(),
        checked=(),
        skipped=tuple(
            SemanticSkip(invariant=invariant, reason=f"{what}: {reason}")
            for invariant, what in ledger_audit.SEMANTIC_HALVES
        ),
    )


def _findings(result: SemanticAuditResult) -> SemanticFindings:
    return SemanticFindings(
        violations=result.violations,
        checked=tuple(invariant for invariant, _ in ledger_audit.SEMANTIC_HALVES),
        skipped=result.skipped,
    )


def _semantic(
    store: Store,
    client: ModelClient,
    scene_id: str,
    selected: Sequence[SelectedEntity],
    mechanical: Sequence[Violation],
    cap: int,
) -> tuple[SemanticFindings, SemanticAuditResult | None, HarnessError | None]:
    """The auditor's half and its accounting, whatever happens to the call.

    An input that does not exist is treated as the mechanical half treats one: the half that
    needed it is skipped, with the missing file as the reason (`NotFound` is carried as the
    failure). An input that exists and does not validate still stops the audit (FR-STORE-06).
    """
    if not store.exists(paths.draft(scene_id)):
        reason = f"{paths.draft(scene_id)} does not exist, so there is no prose to judge"
        return _skip_all(reason), None, None
    try:
        result = auditor.audit_semantic(store, client, scene_id, selected, mechanical, cap=cap)
    except MODEL_STEP_FAILURES as failure:
        reason = f"the model step failed and it was not checked ({failure.message})"
        return _skip_all(reason), None, failure
    except NotFound as missing:
        reason = f"an input of the auditor is missing and it was not checked ({missing.message})"
        return _skip_all(reason), None, missing
    return _findings(result), result, None


def audit(
    store: Store,
    client: ModelClient,
    scene_id: str,
    selected: Sequence[SelectedEntity],
    *,
    cap: int = CONTEXT_TOKEN_CAP,
) -> CombinedAudit:
    """FR-AGENT-07. `audit(scene)` = the mechanical checks, then `audit_semantic` over the same
    scene with their findings as data. Reads only; `persist_audit` writes."""
    mechanical = ledger_audit.audit_scene(store, scene_id, semantic=False)
    findings, result, failure = _semantic(
        store, client, scene_id, selected, mechanical.violations, cap
    )
    report = ledger_audit.with_semantic(
        mechanical,
        violations=findings.violations,
        checked=findings.checked,
        skipped=[(skip.invariant, skip.reason) for skip in findings.skipped],
    )
    return CombinedAudit(report=report, semantic=result, failure=failure)


def semantic_findings(
    store: Store,
    client: ModelClient,
    embedder: Embedder,
    settings: Settings,
    scene_id: str,
    mechanical: Sequence[Violation],
) -> SemanticFindings:
    """The audit route's semantic half. Outside a turn there is no recorded selected list, so
    the scene is selected here (FR-OPS-02) -- the list a turn's writer would have received --
    and only when there is a draft to judge, since selection updates the index first.

    A selection the tree cannot support -- a pin naming an entity that no longer exists, a
    record the index needs gone -- skips the semantic half with that reason instead of failing
    the audit: the mechanical half has run and its report is still owed.
    """
    if not store.exists(paths.draft(scene_id)):
        reason = f"{paths.draft(scene_id)} does not exist, so there is no prose to judge"
        return _skip_all(reason)
    try:
        selection = scenes_service.select_entities(store, embedder, settings, scene_id)
    except (NotFound, InvalidRecord) as unselectable:
        reason = f"the scene could not be selected, so it was not checked ({unselectable.message})"
        return _skip_all(reason)
    findings, _, _ = _semantic(
        store, client, scene_id, selection.entities, mechanical, CONTEXT_TOKEN_CAP
    )
    return findings


def semantic_auditor(
    client: ModelClientDep, embedder: EmbedderDep, settings: SettingsDep
) -> SemanticAuditor:
    """The provider `main.py` substitutes for `commons.deps.get_semantic_auditor`: the auditor
    role, bound to the request's model client, embedder and settings -- the dependencies the
    offline suite overrides, so a test's fakes reach it."""

    def run(store: Store, scene_id: str, mechanical: Sequence[Violation]) -> SemanticFindings:
        return semantic_findings(store, client, embedder, settings, scene_id, mechanical)

    return run


# --- rollup ---------------------------------------------------------------------------------


def rollup(
    store: Store,
    client: ModelClient,
    *,
    role: AgentRole,
    chapter_id: str | None = None,
    arc_id: str | None = None,
) -> RollupResponse:
    """FR-AGENT-08, IF-06. Plan, authorise, call, write -- in that order, so a refusal (a
    missing digest, a role whose tool set does not reach `manuscript/digests/`) comes before
    the model is called."""
    plan = writer.plan_rollup(store, chapter_id=chapter_id, arc_id=arc_id)
    toolset_for(role).authorise(paths.digest(plan.digest_id))
    result = writer.run_rollup(client, plan)
    persisted = persist_digest(store, result, role=role)
    written = manuscript_service.read_digest(store, result.digest_id)
    completion = result.call.completion
    return RollupResponse(
        digest_id=result.digest_id,
        digest=written,
        persisted=persisted,
        claimed_povs=list(result.claimed_povs),
        povs_agree=result.povs_agree,
        model_id=completion.model_id,
        estimate=completion.estimate,
        over_cap=completion.over_cap,
        prompt_version=result.call.prompt_version,
    )


__all__ = [
    "MODEL_STEP_FAILURES",
    "audit",
    "persist_audit",
    "persist_digest",
    "persist_draft",
    "persist_proposals",
    "rollup",
    "semantic_auditor",
    "semantic_findings",
]
