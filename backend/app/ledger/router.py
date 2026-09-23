"""The HTTP surface of `ledger/`: IF-03's five reads, IF-04's two writes and IF-05's two
operations on the queue, under `/ledger`.

The ledger is where the loop of Figure 1 turns. Prose flows into it as proposed facts and as
violations, and both of those are the *input* to a decision: `promote` returns a fact to canon
under the canoniser, a human ruling settles a fact that collided, and a human settles what a
violation costs through the violations write. The handlers here only carry the request to the
operation; what may be decided, and by whom, is the operation's and Figure 3's business.

Three conventions hold in every handler and each is a rule from the spec rather than a style
preference:

* **Plain `def`, never `async def`.** Every handler ends in the store layer, which is blocking
  file I/O (FR-STORE-07: temp file, fsync, rename). Declared `async`, it would run on the event
  loop and stall every other request for the duration of an fsync; declared `def`, FastAPI runs
  it in a worker thread.
* **The role comes from the header and nowhere else** (IF-02). `RoleDep` is a 400 when
  `X-Agent-Role` is missing or unknown, and there is no default: the write is then refused or
  allowed by Figure 3 inside `Store.write` (FR-PERM-03), and the provenance line records the
  role that was actually claimed (FR-STORE-04).
* **No `HTTPException`.** Handlers raise the domain errors of `commons.errors`, and the handler
  registered by the app factory maps each to its IF-07 status code, so the status table lives
  in exactly one place.

Writes answer with the provenance line that was appended -- path, role, actor, content hash,
timestamp. A caller that has just written under a role can therefore see what the log will
show, which is the point of a log no caller can skip.

**Why only two of the five files have a write route.** Figure 3's `Out` column gives
`ledger/proposed.yaml` to the writer and the canoniser and `ledger/violations.yaml` to the
auditor, and names no role for `setups.yaml`, `threads.yaml` or `timeline.yaml`. IF-03 lists
all five as reads and IF-04 lists only the two, and the permission table transcribes the same
absence. A convenience route onto the other three would be a write path with no row in the
table behind it.

**The two operations on the queue** (IF-05) are `POST /ledger/proposed/{id}/promote`
(FR-OPS-06) and `POST /ledger/proposed/{id}/rule` (FR-OPS-07): the return edge of Figure 1,
from proposed facts back into canon, and the human gate on it. The mechanical `audit` whose
findings land in `violations.yaml` (FR-AUD) arrives at plan step 14.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path

from app.commons.deps import ActorDep, RoleDep, StoreDep
from app.commons.schemas import ProposedFile, SetupsFile, ThreadsFile, ViolationsFile
from app.commons.schemas.common import ENTITY_ID_PATTERN
from app.commons.stores.provenance import ProvenanceRecord
from app.ledger import service
from app.ledger.models import PromotionResult, RuleRequest, RulingApplied, TimelineFile
from app.ledger.service import ProposedAppend

router = APIRouter(prefix="/ledger", tags=["ledger"])

FactIdPath = Annotated[
    str,
    Path(
        alias="id",
        pattern=ENTITY_ID_PATTERN,
        description="The proposed fact's stable identifier, as `ledger/proposed.yaml` holds it.",
    ),
]
"""A fact id is an entity id (`ProposedFact.id` is an `EntityId`), so the same grammar is part
of the published contract and a malformed one is a 422 before any handler runs."""


# --------------------------------------------------------------------------------------
# Reads (IF-03). A missing file answers 404 naming the path, rather than an empty document:
# "this project has no ledger yet" and "the ledger is empty" are different facts and a
# caller has to be able to tell them apart.
# --------------------------------------------------------------------------------------


@router.get("/setups", summary="Read the Chekhov ledger")
def read_setups(store: StoreDep) -> SetupsFile:
    """IF-03, `GET /ledger/setups`. Every reader debt, open and closed.

    Open ones -- `paid_in` and `resolution` both empty -- are what FR-OPS-03 offers the writer
    under a *may collect* label, and what FR-AUD-02 reports once they are past `due_by`.
    """
    return service.setups(store)


@router.get("/threads", summary="Read the plot threads")
def read_threads(store: StoreDep) -> ThreadsFile:
    """IF-03, `GET /ledger/threads`. Every plot line, with the latency it tolerates.

    `scenes` is in discourse order in each thread, because latency is a reading-order distance:
    a subplot set in the past can still be fresh on the page, and one set yesterday can still
    have vanished for eighty pages.
    """
    return service.threads(store)


@router.get("/timeline", summary="Read both temporal axes")
def read_timeline(store: StoreDep) -> TimelineFile:
    """IF-03, `GET /ledger/timeline`. The story axis, the discourse axis, and the mapping.

    Two axes that must never be merged: consistency is verified against story time, tension is
    designed on discourse time. The scene records are the authority for both (DR-03); this is
    the projection the auditor is handed (Figure 3), and no role may write it.
    """
    return service.timeline(store)


@router.get("/proposed", summary="Read the canonisation queue")
def read_proposed(store: StoreDep) -> ProposedFile:
    """IF-03, `GET /ledger/proposed`. The whole queue, settled entries included.

    Promoted and rejected facts stay: the record of what was refused, and why, is what stops
    the same invention being proposed and argued about again twenty scenes later.
    """
    return service.proposed(store)


@router.get("/violations", summary="Read the violation reports")
def read_violations(store: StoreDep) -> ViolationsFile:
    """IF-03, `GET /ledger/violations`. Every violation reported against the manuscript.

    Also the hand-off surface of FR-AGENT-11: `revise` reads the blocking violations of a scene
    back from this file after the auditor's write has landed, not from the auditor's answer.
    """
    return service.violations(store)


# --------------------------------------------------------------------------------------
# Writes (IF-04)
# --------------------------------------------------------------------------------------


@router.post("/proposed", summary="Append proposed facts to the queue")
def append_proposed(
    store: StoreDep,
    role: RoleDep,
    actor: ActorDep,
    request: ProposedAppend,
) -> ProvenanceRecord:
    """IF-04, `POST /ledger/proposed` (writer). Appends; it never replaces the file.

    `POST` rather than `PUT` because the operation is not idempotent and is not a statement
    about the whole file: two identical calls are two appends, and the second is refused only
    because the ids collide. The response is the provenance line, not the created facts -- no
    URL addresses one, and the line is what the log will show for this write.

    **The writer proposes; it cannot commit.** Figure 3 gives the writer -- the agent that
    generates the most tokens and therefore has the most opportunities to be wrong -- no write
    edge into `canon/` at all. This route is the whole of its influence over what becomes true,
    and `promote` under the canoniser is the only thing that acts on it (FR-OPS-06).

    **Appending is what makes FR-TURN-03 hold.** The writer's proposals from every iteration
    are kept, including those of a draft the audit rejected, because a rejected draft can still
    have invented a good name for something. A route that replaced the file would lose them to
    a turn that simply ran twice.
    """
    return service.append_proposed(store, request, role=role, actor=actor)


@router.put("/violations", summary="Write the violation reports")
def replace_violations(
    store: StoreDep,
    role: RoleDep,
    actor: ActorDep,
    record: ViolationsFile,
) -> ProvenanceRecord:
    """IF-04, `PUT /ledger/violations` (auditor). The whole report file.

    **The dotted "escalate ruling" edge of Figure 1 is this route.** A violation can be
    resolved by changing the prose or by changing the canon, and the system does not choose
    between them: a checker that silently rewrote either side would sand off exactly the detail
    that made a scene good. So a human resolves an escalated violation here -- acting as the
    auditor, with `X-Actor: human` -- by setting `resolution` to `fix_prose`, `fix_canon` or
    `accept_with_reason`. The edit that follows goes through the role that owns the path it
    touches; nothing about the prose or the canon changes through this route.

    That is also why the auditor writes nothing else. Figure 3 gives it this file and no other:
    `Violations` is reachable from prose and has no edge back into it. The auditor reports; it
    does not repair.

    The whole file rather than one violation, because the set of findings on a scene is what
    `revise` is handed (FR-AGENT-02) and what a re-audit has to be able to shrink.
    """
    return service.replace_violations(store, record, role=role, actor=actor)


# --------------------------------------------------------------------------------------
# Operations (IF-05). Canoniser only; the ruling additionally needs `X-Actor: human`.
# --------------------------------------------------------------------------------------


@router.post("/proposed/{id}/promote", summary="Promote a proposed fact into canon")
def promote_fact(
    fact_id: FactIdPath,
    store: StoreDep,
    role: RoleDep,
    actor: ActorDep,
) -> PromotionResult:
    """IF-05, FR-OPS-06 (canoniser). `Promoted`, or `Escalation` when the target disagrees.

    **A collision is escalated, never resolved.** When the target field already holds a
    different value the fact is marked `conflict: true` with the value it collided with, stays
    `pending`, and the answer is an `Escalation`; `canon/` and `cast/` are left byte-identical.
    Both answers are `200`: an escalation is the operation working, not failing, and the
    `outcome` field says which one arrived.

    A fact that cannot be promoted at all -- its target entity or field does not exist, or the
    field is not one a single string can fill -- is a `422` naming the field of the queued fact
    that is wrong, and nothing is written.
    """
    return service.promote(store, fact_id, role=role, actor=actor)


@router.post("/proposed/{id}/rule", summary="Rule on a proposed fact")
def rule_on_fact(
    fact_id: FactIdPath,
    request: RuleRequest,
    store: StoreDep,
    role: RoleDep,
    actor: ActorDep,
) -> RulingApplied:
    """IF-05, FR-OPS-07 (canoniser, `X-Actor: human`). The human gate on promotion.

    `accept` promotes the fact despite a collision -- the human decided which of the two truths
    the novel holds -- and `reject` marks it rejected. Either way the ruling, its reason and
    its time are recorded on the fact, because the next reader needs to see who decided and
    why, not merely that something did.

    **An agent may not rule.** Without `X-Actor: human` the call is a `403` and nothing is
    read or written: the orchestrator always sends `agent`, so this is what keeps it from
    settling a collision on its own (AC 13).
    """
    return service.rule(store, fact_id, request.ruling, request.reason, role=role, actor=actor)


__all__ = ["FactIdPath", "router"]
