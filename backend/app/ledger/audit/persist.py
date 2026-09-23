"""Writing an audit into `ledger/violations.yaml` (AC 16): merged, never duplicated, and only
ever under the role Figure 3 allows.

**Who may write.** Nothing here decides it. The write goes through `Store.write`, whose
single check (`may_write`, FR-PERM-03) allows the auditor on `ledger/violations.yaml` and
refuses every other role with `PermissionDenied` -- a 403 -- before any byte touches disk.
A second guard in this module could only drift from the table. For the same reason the write
is attempted even when the merged file equals the one on disk: skipping a no-op write would
answer a forbidden role with success instead of the refusal Figure 3 owes it.

**How a report merges with the file** (`merge`), for the audited scene and the mechanical
source only -- everything else in the file is someone else's and is kept untouched, in place:

1. A **resolved** mechanical finding for the scene is kept exactly as it is, and a fresh
   finding with the same natural key is *not* added beside it. Resolutions are human rulings
   (IF-04); an audit that re-raised an accepted finding on every run would overrule the human
   by repetition, and one that dropped it would erase the ruling's history.
2. An **unresolved** mechanical finding that the fresh audit reproduces is kept, with its id
   and position, and takes the fresh severity (FR-AUD-02's severity moves when the last
   scene moves). Recognition is by natural key, not by id, so a prior report written with a
   hand-made id -- the fixture's `vi_002` -- is recognised and not duplicated.
3. An **unresolved** mechanical finding the fresh audit does *not* reproduce is dropped, but
   only if its invariant was actually checked in this run. That is how a revised draft's
   report says a finding is gone (the reason `PUT /ledger/violations` is a replace); and a
   check that was skipped -- a draft missing, a lexicon absent -- vouches for nothing, so the
   findings it would have re-examined are kept.
4. A fresh finding matching nothing is appended, in audit order.

Model-sourced findings are never touched here, whatever their scene: they are the
model-backed auditor's (FR-AUD-09), and a mechanical run has no standing to retract them.
Re-running the same audit and persisting it again therefore yields the same file, byte for
byte -- which is what "re-running must not duplicate" means when it is checked.

**An absent file** is an empty report, on the way in only. The auditor's first audit of a new
book has to be able to create it; there is nothing else in the file for the merge to keep.
"""

from __future__ import annotations

from app.commons.errors import InvalidRecord, PermissionDenied
from app.commons.permissions import Actor, AgentRole, may_write
from app.commons.schemas import Violation, ViolationsFile, ViolationSource
from app.commons.stores import Store
from app.commons.stores.provenance import ProvenanceRecord
from app.ledger import repository
from app.ledger.audit.findings import natural_key
from app.ledger.audit.report import AuditReport


def _refuse_duplicate_ids(violations: list[Violation]) -> None:
    """DR-08. A merged file in which two findings share an id is refused, never written.

    Reachable only through a digest collision or a hand-written id equal to a derived one;
    either way the turn record and `revise` address violations by id, and a file with two
    records under one id would make both of them mean two things.
    """
    seen: set[str] = set()
    for index, finding in enumerate(violations):
        if finding.id in seen:
            message = (
                f"{repository.VIOLATIONS_PATH} would declare {finding.id!r} twice; identifiers "
                "are stable and every reference to this one would be ambiguous (DR-08)"
            )
            raise InvalidRecord(
                message, file=repository.VIOLATIONS_PATH, field=f"violations.{index}.id"
            )
        seen.add(finding.id)


def merge(existing: ViolationsFile, report: AuditReport) -> ViolationsFile:
    """The file that results from persisting `report` over `existing` (rules in the module
    docstring). Pure, so the rules are testable without a store."""
    fresh = {natural_key(finding): finding for finding in report.violations}
    checked = {ref.invariant for ref in report.checked}
    covered: set[tuple[str, int, str, str, int]] = set()
    merged: list[Violation] = []
    for finding in existing.violations:
        ours = finding.scene == report.scene and finding.source is ViolationSource.MECHANICAL
        if not ours:
            merged.append(finding)
            continue
        key = natural_key(finding)
        if finding.resolution is not None:
            merged.append(finding)
            covered.add(key)
            continue
        reproduced = fresh.get(key)
        if reproduced is not None:
            merged.append(finding.model_copy(update={"severity": reproduced.severity}))
            covered.add(key)
        elif finding.invariant not in checked:
            merged.append(finding)
    merged.extend(finding for key, finding in fresh.items() if key not in covered)
    _refuse_duplicate_ids(merged)
    return ViolationsFile(violations=merged)


def persist(
    store: Store,
    report: AuditReport,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """AC 16. Merge `report` into `ledger/violations.yaml` and write it under `role`.

    Only the auditor succeeds (Figure 3, enforced inside `Store.write`); any other role gets
    `PermissionDenied` and the tree is byte-identical. The write goes through the ledger's
    repository, the feature's one door to this file, like `PUT /ledger/violations`.

    The permission is asked first, before the existing file is read, so a forbidden role gets
    its 403 even when `ledger/violations.yaml` is broken: the answer to "may you write this?"
    must not depend on the state of the file. `Store.write` asks again; this is the same rule
    asked earlier, not a second one.
    """
    if not may_write(role, repository.VIOLATIONS_PATH):
        message = f"Figure 3 does not allow {role.value} to write {repository.VIOLATIONS_PATH}"
        raise PermissionDenied(message, role=role.value, path=repository.VIOLATIONS_PATH)
    present = store.exists(repository.VIOLATIONS_PATH)
    existing = repository.read_violations(store) if present else ViolationsFile()
    merged = merge(existing, report)
    return repository.write_violations(store, merged, role=role, actor=actor)


__all__ = ["merge", "persist"]
