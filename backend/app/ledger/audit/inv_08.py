"""FR-AUD-06 -- invariant 8, no inert scenes, the record half. Severity `reviewable`.

"Every scene declares a signed `value_change`, and the prose delivers it." Whether the prose
delivers it is a judgement and belongs to the model-backed auditor (FR-AUD-09). The record
half is mechanical: `value_change` must be non-empty and must carry a sign.

**What "signed" means.** Neither the spec nor `definitions.md` fixes a notation; they say
"which value moves, and in which direction". The fixture's convention, followed by every
scene but the planted one, is a trailing `(+)` or `(-)`, and the README reduces this check to
"non-empty and contains `(+)` or `(-)`". That is the rule implemented here, and the absence of
a notation in the docs is reported with the step: a book written with `(^)` / `(v)`, or with a
Unicode minus, would report every scene.

A scene that names a value without saying which way it moves is the case the invariant
exists for: `authority over the vault` reads as a scene about something and says nothing
about whether anything changed.
"""

from __future__ import annotations

from typing import Final

from app.commons.schemas import Severity
from app.commons.stores import paths
from app.ledger.audit.findings import CheckOutcome, record_evidence, violation
from app.ledger.audit.material import AuditMaterial

CHECK: Final[str] = "FR-AUD-06"
INVARIANT: Final[int] = 8
SEVERITY: Final[Severity] = Severity.REVIEWABLE
SIGN_TOKENS: Final[tuple[str, ...]] = ("(+)", "(-)")
EMPTY_MARKER: Final[str] = "(empty)"
"""Stands in for an empty value in the evidence, which DR-07 requires to be non-empty."""


def run(material: AuditMaterial) -> CheckOutcome:
    """An empty or unsigned `value_change` on this scene's record."""
    scene = material.scene
    value = scene.value_change
    if value.strip() and any(token in value for token in SIGN_TOKENS):
        return []
    shown = value if value.strip() else EMPTY_MARKER
    detail = f"{paths.scene(scene.id)} value_change: {shown}"
    return [
        violation(
            scene=scene.id,
            invariant=INVARIANT,
            severity=SEVERITY,
            evidence=record_evidence(detail),
        )
    ]


__all__ = ["CHECK", "INVARIANT", "run"]
