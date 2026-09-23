"""FR-AUD-02 -- invariant 2, closed debts. `reviewable`; `blocking` at the last scene.

"Every setup has a payoff or a declared abandonment before the book ends." The check: a setup
whose `due_by` scene is at or before this scene on the **story** axis, and which is still
open -- `paid_in` empty and `resolution` empty -- is a loose end at this scene.

Open is both fields empty, as the spec states it. `resolution: deliberately_abandoned` is
what separates a decision from a forgotten promise (DR-05), and a checker that ignored it
would report every dropped thread the writer meant to drop -- the noise that gets a checker
switched off.

**Severity.** `reviewable` everywhere except at the last scene by discourse order, where
there is no later scene left to collect the debt in and it becomes `blocking`. The fixture's
last scene is 006, which is why su_readkey reports `reviewable` at 004 and 005 and nothing at
006 (hour 310, before its deadline at 318).

That last point is a gap the step reports rather than papers over: an open setup due *later*
on the story axis than the scene the book ends on -- a book that closes on an analepsis --
is never reported by the rule as written, although invariant 2 says the book must not end
owing it. The fixture README depends on the literal rule (006 must be clean), so the literal
rule is what runs.

**A deadline that cannot be placed.** A `due_by` naming no scene record cannot be compared on
the story axis at all. It is reported as a `note` -- the same answer FR-AUD-04 gives a missing
transit entry -- rather than dropped, because dropping it would make the debt unreportable
for ever.
"""

from __future__ import annotations

from typing import Final

from app.commons.schemas import Severity, Violation
from app.ledger import repository
from app.ledger.audit.findings import CheckOutcome, Skip, record_evidence, violation
from app.ledger.audit.material import AuditMaterial

CHECK: Final[str] = "FR-AUD-02"
INVARIANT: Final[int] = 2


def run(material: AuditMaterial) -> CheckOutcome:
    """Open setups due at or before this scene's story time."""
    if material.setups is None:
        return Skip(f"{repository.SETUPS_PATH} is absent; there are no setups to check")

    scene = material.scene
    due_severity = Severity.BLOCKING if material.is_last_scene else Severity.REVIEWABLE
    found: list[Violation] = []
    for setup in material.setups.setups:
        if setup.paid_in is not None or setup.resolution is not None:
            continue
        locator = f"{repository.SETUPS_PATH} {setup.id}"
        deadline = material.scenes.get(setup.due_by)
        if deadline is None:
            severity = Severity.NOTE
            detail = (
                f"{locator}: due_by {setup.due_by}, and there is no scene {setup.due_by}; the "
                "deadline cannot be placed on the story axis"
            )
        elif deadline.story_time <= scene.story_time:
            severity = due_severity
            detail = (
                f"{locator}: due_by {setup.due_by} (hour {deadline.story_time}), paid_in "
                f"empty, resolution empty; scene {scene.id} is at hour {scene.story_time}"
            )
        else:
            continue
        found.append(
            violation(
                scene=scene.id,
                invariant=INVARIANT,
                severity=severity,
                evidence=record_evidence(detail),
            )
        )
    return found


__all__ = ["CHECK", "INVARIANT", "run"]
