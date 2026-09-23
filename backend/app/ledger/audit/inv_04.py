"""FR-AUD-03 -- invariant 4, spatial uniqueness. Severity `blocking`.

"No character occupies two locations at the same `story_time`." For each character in this
scene -- POV and participants, never the POV alone (DR-03) -- every other scene that also has
them at the same hour and a different location is a breach.

The finding is a *pair* of scenes and it is reported against both members: this module, run
for either scene, finds the other. The evidence names the pair in scene-id order, so the two
reports quote the same text and differ only in the `scene` they are filed under -- a reader
can see at once that they are one fact seen from two sides. (The fixture README leaves "one
finding or two" as a reporting convention; this is the convention.)

One violation per character: two people both double-booked by the same pair of scenes are two
breaches, and either can be fixed without the other.
"""

from __future__ import annotations

from typing import Final

from app.commons.schemas import Severity, Violation
from app.commons.stores import paths
from app.ledger.audit.findings import CheckOutcome, present, record_evidence, violation
from app.ledger.audit.material import AuditMaterial

CHECK: Final[str] = "FR-AUD-03"
INVARIANT: Final[int] = 4
SEVERITY: Final[Severity] = Severity.BLOCKING


def run(material: AuditMaterial) -> CheckOutcome:
    """Characters of this scene placed elsewhere at the same story hour by another scene."""
    scene = material.scene
    found: list[Violation] = []
    for character in present(scene):
        for other_id in sorted(material.scenes):
            other = material.scenes[other_id]
            if (
                other_id == scene.id
                or character not in present(other)
                or other.story_time != scene.story_time
                or other.location == scene.location
            ):
                continue
            first, second = sorted((scene, other), key=lambda record: record.id)
            detail = (
                f"{paths.scene(first.id)} and {paths.scene(second.id)}: {character} is at "
                f"{first.location} and at {second.location} at the same hour "
                f"{scene.story_time}"
            )
            found.append(
                violation(
                    scene=scene.id,
                    invariant=INVARIANT,
                    severity=SEVERITY,
                    evidence=record_evidence(detail),
                )
            )
    return found


__all__ = ["CHECK", "INVARIANT", "run"]
