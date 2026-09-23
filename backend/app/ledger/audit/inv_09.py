"""FR-AUD-07 -- invariant 9, recognisable voice. Severity `reviewable`.

"No dialogue contains material marked `never_says` for that speaker." Mechanically, and as
spec Decision 13 narrows it: the **POV's** `never_says` list is searched, case-insensitively,
in the whole draft. Other characters' lists are not searched -- attributing a line of dialogue
to its speaker is a judgement about the page, not a string search -- and the whole draft is
searched rather than only quoted speech, because a mechanical split into dialogue and
narration would be a second, silent heuristic. Both narrowings are why the severity is
`reviewable`: a human decides whether a hit is really the character talking.

The evidence is the draft's own text and offset, like FR-AUD-05. A scene with no draft, or a
POV with no `voice.md`, is skipped rather than reported clean.
"""

from __future__ import annotations

from typing import Final

from app.commons.schemas import Severity, Violation
from app.commons.stores import paths
from app.ledger.audit.findings import CheckOutcome, Skip, occurrences, violation
from app.ledger.audit.material import AuditMaterial

CHECK: Final[str] = "FR-AUD-07"
INVARIANT: Final[int] = 9
SEVERITY: Final[Severity] = Severity.REVIEWABLE


def run(material: AuditMaterial) -> CheckOutcome:
    """Every occurrence of the POV's `never_says` material in the draft body."""
    scene = material.scene
    if material.draft is None:
        return Skip(f"{paths.draft(scene.id)} is absent; there is no prose to search")
    if material.voice is None:
        voice_path = paths.cast_file(scene.pov, "voice")
        return Skip(f"{voice_path} is absent; the POV has no never_says list to search for")

    body = material.draft.body
    found: list[Violation] = [
        violation(scene=scene.id, invariant=INVARIANT, severity=SEVERITY, evidence=evidence)
        for phrase in material.voice.never_says
        for evidence in occurrences(body, phrase)
    ]
    return sorted(found, key=lambda finding: finding.evidence.offset)


__all__ = ["CHECK", "INVARIANT", "run"]
