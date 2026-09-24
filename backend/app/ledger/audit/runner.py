"""`audit_scene` -- the entry point of the mechanical audit (FR-AUD-01..09).

Runs the eight mechanical checks, in FR-AUD order, over one scene and returns every finding
with the accounting of what ran and what did not. It reads and never writes: persistence is a
separate call (`persist.persist`) that only the auditor can make succeed, so that "audit" and
"write a report" cannot be the same accident.

**The model-backed half is not run here.** Invariants 3 and 6, and the prose halves of 1 and
8, are judged by the auditor role (FR-AGENT-06/07), which lives in `agents` -- above this
package in NFR-04's layers, so this module cannot call it. The combined audit runs this
function with `semantic=False` first, hands the mechanical findings to the role as data, and
folds the role's answer into the report with `with_semantic`. Called with `semantic=True`, this
function is the audit of a process with no model-backed auditor wired in: it lists those four
in `skipped` with the reason, which is exactly FR-AUD-09's answer to a model step that fails:
the absence of a violation is never mistaken for a pass. A request with `semantic=False` asked
for the mechanical half only and gets it, with nothing listed for the half it did not ask for.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from app.commons.schemas import Invariant, Violation, ViolationSource
from app.commons.stores import Store
from app.ledger.audit import inv_01, inv_02, inv_04, inv_05, inv_07, inv_08, inv_09, inv_10
from app.ledger.audit.findings import MechanicalCheck, Skip
from app.ledger.audit.material import load_material
from app.ledger.audit.report import AuditReport, CheckRef, SkippedCheck

MECHANICAL_CHECKS: Final[tuple[MechanicalCheck, ...]] = (
    MechanicalCheck(check=inv_01.CHECK, invariant=inv_01.INVARIANT, run=inv_01.run),
    MechanicalCheck(check=inv_02.CHECK, invariant=inv_02.INVARIANT, run=inv_02.run),
    MechanicalCheck(check=inv_04.CHECK, invariant=inv_04.INVARIANT, run=inv_04.run),
    MechanicalCheck(check=inv_05.CHECK, invariant=inv_05.INVARIANT, run=inv_05.run),
    MechanicalCheck(check=inv_07.CHECK, invariant=inv_07.INVARIANT, run=inv_07.run),
    MechanicalCheck(check=inv_08.CHECK, invariant=inv_08.INVARIANT, run=inv_08.run),
    MechanicalCheck(check=inv_09.CHECK, invariant=inv_09.INVARIANT, run=inv_09.run),
    MechanicalCheck(check=inv_10.CHECK, invariant=inv_10.INVARIANT, run=inv_10.run),
)
"""FR-AUD-01 ... FR-AUD-08, one module each, in the spec's order. Spelled out rather than
built in a loop over the modules so the type checker sees each module's own signatures."""

SEMANTIC_CHECK: Final[str] = "FR-AUD-09"
SEMANTIC_HALVES: Final[tuple[tuple[Invariant, str], ...]] = (
    (1, "The prose half of invariant 1 (information referenced before it is acquired)"),
    (3, "Invariant 3 (a body changing without a registered ChangeEvent)"),
    (6, "Invariant 6 (an axiom of the turn's selected list violated)"),
    (8, "The prose half of invariant 8 (the prose delivering the signed value_change)"),
)
"""What FR-AUD-09 delegates to the model-backed auditor, in invariant order."""

SEMANTIC_UNAVAILABLE: Final[str] = (
    "is judged by the model-backed auditor (FR-AUD-09, plan step 17), and none is wired into "
    "this process; it was not checked"
)


def _first_of_each(violations: list[Violation]) -> list[Violation]:
    """Drop repeats of the same finding, keeping the first.

    Two lexicon variants can match one span; the evidence and therefore the id are then
    identical, and two records with one id would make `ledger/violations.yaml` unwritable
    (DR-08) for a finding that is really one.
    """
    seen: set[str] = set()
    unique: list[Violation] = []
    for finding in violations:
        if finding.id not in seen:
            seen.add(finding.id)
            unique.append(finding)
    return unique


def audit_scene(store: Store, scene_id: str, *, semantic: bool) -> AuditReport:
    """IF-05, `audit(scene)`. The mechanical checks over `scene_id`, and the accounting.

    `semantic` has no default in Python: whether the model-backed half was asked for decides
    what `skipped` must say, and a caller that never decided would get a report that means
    something it did not intend. The HTTP route defaults it to true, as IF-05 describes the
    full audit.

    Raises `NotFound` for a scene with no record and `InvalidRecord` for any input that exists
    and does not validate (FR-STORE-06); both stop the audit rather than narrowing it.
    """
    material = load_material(store, scene_id)
    violations: list[Violation] = []
    checked: list[CheckRef] = []
    skipped: list[SkippedCheck] = []
    for check in MECHANICAL_CHECKS:
        outcome = check.run(material)
        if isinstance(outcome, Skip):
            skipped.append(
                SkippedCheck(
                    check=check.check,
                    invariant=check.invariant,
                    source=ViolationSource.MECHANICAL,
                    reason=outcome.reason,
                )
            )
            continue
        checked.append(
            CheckRef(
                check=check.check,
                invariant=check.invariant,
                source=ViolationSource.MECHANICAL,
            )
        )
        violations.extend(outcome)

    if semantic:
        skipped.extend(
            SkippedCheck(
                check=SEMANTIC_CHECK,
                invariant=invariant,
                source=ViolationSource.MODEL,
                reason=f"{what} {SEMANTIC_UNAVAILABLE}",
            )
            for invariant, what in SEMANTIC_HALVES
        )

    return AuditReport(
        scene=material.scene.id,
        semantic=semantic,
        violations=_first_of_each(violations),
        checked=checked,
        skipped=skipped,
    )


def with_semantic(
    report: AuditReport,
    *,
    violations: Sequence[Violation],
    checked: Sequence[Invariant],
    skipped: Sequence[tuple[Invariant, str]],
) -> AuditReport:
    """FR-AGENT-07. The combined audit: a mechanical report, and the model-backed half's answer.

    `report` must be the mechanical half alone (`semantic=False`): the semantic accounting is
    added here exactly once, and a report that already carries it would end up listing the
    same invariant as both skipped for want of an auditor and checked by one. `violations` are
    the model's findings, already DR-07 records with `source: model`; `checked` the semantic
    invariants the model step judged; `skipped` the ones it could not -- every one of them when
    the step failed (FR-AUD-09), or one entry per input the cap pruned (FR-CTX-04). An
    invariant may appear in both lists: judged, but without one of its inputs, which the
    reason names.

    A model finding is never allowed to carry the mechanical source, and one whose id repeats
    an earlier finding is dropped, as the mechanical half drops its own repeats.
    """
    if report.semantic:
        message = "with_semantic takes the mechanical half alone (semantic=False)"
        raise ValueError(message)
    for finding in violations:
        if finding.source is not ViolationSource.MODEL:
            message = f"{finding.id} is not a model finding; FR-AUD-09 findings carry source model"
            raise ValueError(message)
    return AuditReport(
        scene=report.scene,
        semantic=True,
        violations=_first_of_each([*report.violations, *violations]),
        checked=[
            *report.checked,
            *(
                CheckRef(check=SEMANTIC_CHECK, invariant=invariant, source=ViolationSource.MODEL)
                for invariant in checked
            ),
        ],
        skipped=[
            *report.skipped,
            *(
                SkippedCheck(
                    check=SEMANTIC_CHECK,
                    invariant=invariant,
                    source=ViolationSource.MODEL,
                    reason=reason,
                )
                for invariant, reason in skipped
            ),
        ],
    )


__all__ = [
    "MECHANICAL_CHECKS",
    "SEMANTIC_CHECK",
    "SEMANTIC_HALVES",
    "audit_scene",
    "with_semantic",
]
