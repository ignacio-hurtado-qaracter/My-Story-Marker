"""FR-AUD-04 -- invariant 5, possible transits. `blocking`; a missing matrix entry is `note`.

"Every movement respects the `transit_matrix`." Each character's scenes are walked in story
order, and each consecutive pair must leave at least `transit_matrix[from][to]` hours between
them. Only the pairs that include this scene are checked here -- its predecessor and its
successor on each present character's walk -- and, like FR-AUD-03, a failing pair is
reported against both members with the same evidence text.

**Ties.** Two scenes at the same hour are ordered by `discourse_order`, then by id, so the
walk -- and therefore which pairs exist -- is the same on every run. The fixture README shows
that its one tie (004 and 005 at hour 318) yields the same single finding whichever way it is
broken; the tie-break is fixed here anyway, because a walk that depended on dictionary order
would be deterministic on the fixture and nowhere else.

**No movement, nothing to check.** A pair in the same location is not a movement, so it
needs no matrix entry at all; the fixture's zero diagonal says the same thing, and a matrix
that omitted its diagonal would otherwise report a `note` for every character who stays put.

**A missing entry** between two different locations is a `note`, as the spec sets it: the
check cannot decide, and says so instead of passing.
"""

from __future__ import annotations

from typing import Final

from app.commons.schemas import Scene, Severity, Violation
from app.commons.stores import paths
from app.ledger.audit.findings import CheckOutcome, Skip, present, record_evidence, violation
from app.ledger.audit.material import AuditMaterial

CHECK: Final[str] = "FR-AUD-04"
INVARIANT: Final[int] = 5
SEVERITY: Final[Severity] = Severity.BLOCKING
MISSING_ENTRY: Final[Severity] = Severity.NOTE


def _story_order(record: Scene) -> tuple[int, int, str]:
    return (record.story_time, record.discourse_order, record.id)


def run(material: AuditMaterial) -> CheckOutcome:
    """Adjacent story-axis pairs through this scene that move faster than the matrix allows."""
    if material.time is None:
        return Skip(f"{paths.TIME} is absent; there is no transit matrix to check against")

    matrix = material.time.transit_matrix
    scene = material.scene
    found: list[Violation] = []
    for character in present(scene):
        walk = sorted(
            (record for record in material.scenes.values() if character in present(record)),
            key=_story_order,
        )
        position = next(index for index, record in enumerate(walk) if record.id == scene.id)
        pairs = [
            (walk[index], walk[index + 1])
            for index in (position - 1, position)
            if 0 <= index < len(walk) - 1
        ]
        for earlier, later in pairs:
            if earlier.location == later.location:
                continue
            leg = (
                f"{paths.scene(earlier.id)} (hour {earlier.story_time}, {earlier.location}) "
                f"-> {paths.scene(later.id)} (hour {later.story_time}, {later.location}): "
                f"{character} crosses"
            )
            entry = f"{paths.TIME} transit_matrix[{earlier.location}][{later.location}]"
            required = matrix.get(earlier.location, {}).get(later.location)
            elapsed = later.story_time - earlier.story_time
            if required is None:
                severity = MISSING_ENTRY
                detail = f"{leg}, and {entry} is missing, so the crossing cannot be checked"
            elif elapsed < required:
                severity = SEVERITY
                detail = f"{leg} in {elapsed} hours against {entry} = {required}"
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
