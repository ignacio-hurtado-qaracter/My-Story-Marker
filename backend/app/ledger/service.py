"""The ledger feature's operations: five reads, an append that is not a replace, and a report
file a human can settle.

Reads are pass-through by design. FR-STORE-06 already says what a read is -- validated, or
`InvalidRecord` naming file and field, never repaired and never partially returned -- and a
service that added anything on top would be a second opinion about a file the store layer has
already ruled on.

The two writes are not pass-through, and each carries the one rule that only this layer can
see.

* **The queue is appended to, never replaced** (`append_proposed`). FR-TURN-03 keeps the
  writer's proposals from every iteration, including the ones whose draft was revised away,
  because a rejected draft can still have invented a good name for something. A route that
  took the whole file would make losing them a typo.
* **Identifiers in these two files are addresses.** `promote(fact_id)` and `rule(fact_id)`
  (FR-OPS-06, FR-OPS-07) resolve a fact by id, and a turn record names violations by id. Two
  records claiming one id do not lose a record; they make every reference to that id mean two
  things, and no later `reconcile` can recover which was meant because the information was
  never written down.

`promote` and `rule` (IF-05, FR-OPS-06, FR-OPS-07) live in `app.ledger.promote` and are
re-exported here, so the orchestrator of plan step 18 reaches them through this feature's
public surface (NFR-04) rather than through a module it would otherwise have to know about.
They are kept in their own module because they are the only code in `ledger/` that writes
`canon/` or `cast/`, and AC 13's static rule looks for exactly those two function names: a
reviewer auditing the return edge into canon reads one file. The mechanical audit (IF-05,
`POST /scenes/{id}/audit`) arrives at step 14.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.commons.errors import InvalidRecord
from app.commons.permissions import Actor, AgentRole
from app.commons.schemas import (
    ProposedFact,
    ProposedFile,
    SetupsFile,
    ThreadsFile,
    ViolationsFile,
)
from app.commons.stores import Store
from app.commons.stores.provenance import ProvenanceRecord
from app.ledger import repository
from app.ledger.models import TimelineFile
from app.ledger.promote import promote, rule


class ProposedAppend(BaseModel):
    """The body of `POST /ledger/proposed`: the facts to add, and nothing about the file.

    Deliberately not a `ProposedFile`. That model carries `schema_version` and means *the whole
    queue*, and a body shaped like the file is a body a caller will eventually fill with the
    file -- at which point an append silently becomes a replace and FR-TURN-03's earlier
    proposals are gone with no error anywhere. A distinct model makes the two impossible to
    confuse, in the code and in the committed OpenAPI document (IF-08).

    Unknown fields are refused rather than ignored: a caller that sent `fact` for `facts` would
    otherwise get a 422 for a missing key, but a caller that sent an extra key beside a valid
    one would be told nothing at all.
    """

    model_config = ConfigDict(extra="forbid")

    facts: list[ProposedFact] = Field(
        min_length=1,
        description="The proposed facts to append to the queue, in the order they were"
        " invented. At least one: an empty append would rewrite the file and add a provenance"
        " line for a write that changed nothing, and a log that records those is a log a"
        " reader has to filter before trusting.",
    )


def _refuse_duplicate_ids(*, path: str, field: str, identifiers: list[str]) -> None:
    """DR-08. Two records in one file claiming the same identifier.

    A 422 rather than last-one-wins, and the first duplicate is named: a message that says only
    "there are duplicates" leaves the caller to find it by eye in a file a turn just generated.
    """
    seen: set[str] = set()
    for index, identifier in enumerate(identifiers):
        if identifier in seen:
            message = (
                f"{path} would declare {identifier!r} twice; identifiers are stable and every "
                "reference to this one would be ambiguous (DR-08)"
            )
            raise InvalidRecord(message, file=path, field=f"{field}.{index}.id")
        seen.add(identifier)


# --- reads ----------------------------------------------------------------------------


def setups(store: Store) -> SetupsFile:
    """IF-03, `GET /ledger/setups`. DR-05."""
    return repository.read_setups(store)


def threads(store: Store) -> ThreadsFile:
    """IF-03, `GET /ledger/threads`. DR-06."""
    return repository.read_threads(store)


def timeline(store: Store) -> TimelineFile:
    """IF-03, `GET /ledger/timeline`. The story axis, the discourse axis and the mapping."""
    return repository.read_timeline(store)


def proposed(store: Store) -> ProposedFile:
    """IF-03, `GET /ledger/proposed`. DR-07."""
    return repository.read_proposed(store)


def violations(store: Store) -> ViolationsFile:
    """IF-03, `GET /ledger/violations`. DR-07."""
    return repository.read_violations(store)


# --- writes ---------------------------------------------------------------------------


def append_proposed(
    store: Store,
    request: ProposedAppend,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `POST /ledger/proposed` (writer, canoniser). Append; never replace.

    The queue on disk is read, the incoming facts are added after it, and the extended file is
    written. FR-TURN-03 is the reason the order of those three steps is not negotiable: a
    turn's later iterations must not cost it the inventions of its earlier ones.

    **A missing file is not an error here**, and this is the one place in the feature where
    absence is treated as emptiness. `ledger/proposed.yaml` has no `PUT` and no other way of
    coming into existence -- IF-04 opens exactly this route onto it -- so a first turn against
    a tree that has never queued a fact would fail at its first write, with no role able to
    repair it. An absent queue and an empty queue mean the same thing on the way in: nothing
    has been proposed. On the way out they do not, which is why the reads above still 404.

    The duplicate check names the caller's index rather than the file's, because the caller's
    facts are the ones it can fix. Facts already on disk are not re-checked against each other:
    that would refuse a good append over a defect it did not cause and cannot correct.
    """
    queue = repository.read_proposed(store) if repository.proposed_exists(store) else ProposedFile()
    queued = {fact.id for fact in queue.proposed}

    _refuse_duplicate_ids(
        path=repository.PROPOSED_PATH,
        field="facts",
        identifiers=[fact.id for fact in request.facts],
    )
    for index, fact in enumerate(request.facts):
        if fact.id in queued:
            message = (
                f"{repository.PROPOSED_PATH} already holds a fact with id {fact.id!r}; "
                "identifiers are stable and `promote` resolves a fact by id (DR-08)"
            )
            raise InvalidRecord(
                message, file=repository.PROPOSED_PATH, field=f"facts.{index}.id"
            )

    extended = ProposedFile(proposed=[*queue.proposed, *request.facts])
    return repository.write_proposed(store, extended, role=role, actor=actor)


def replace_violations(
    store: Store,
    record: ViolationsFile,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /ledger/violations` (auditor). The whole report file at once.

    A replace rather than an append, unlike the queue beside it, because a violation report is
    the state of a scene and not a history of assertions: re-auditing a revised draft has to be
    able to say that a finding is gone. The set is also what `revise` is handed (FR-AGENT-02),
    so writing it in halves could leave the writer revising against half an audit.

    This is also the route a human resolves an escalation through: read the file, set
    `resolution` on the violation in question -- `fix_prose`, `fix_canon` or
    `accept_with_reason` -- and write it back as the auditor with `X-Actor: human`. The prose
    or canon edit that follows goes through the role that owns that path, never through here.
    """
    _refuse_duplicate_ids(
        path=repository.VIOLATIONS_PATH,
        field="violations",
        identifiers=[violation.id for violation in record.violations],
    )
    return repository.write_violations(store, record, role=role, actor=actor)


__all__ = [
    "ProposedAppend",
    "append_proposed",
    "promote",
    "proposed",
    "replace_violations",
    "rule",
    "setups",
    "threads",
    "timeline",
    "violations",
]
