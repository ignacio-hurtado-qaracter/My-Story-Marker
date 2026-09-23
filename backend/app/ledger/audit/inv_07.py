"""FR-AUD-05 -- invariant 7, canonical lexicon. Severity `blocking`.

"Zero occurrences of any `forbidden_variants` in the manuscript." Every forbidden variant of
every canonical term in `canon/lexicon.yaml` is searched for, case-insensitively, in this
scene's draft; each occurrence is one violation whose evidence is the draft's own text at
that span and its character offset in the body -- DR-07's quote and offset, exactly.

Blocking because a lexicon drifts one variant at a time and never drifts back: a book that
says `readkey` once and `read-key` everywhere else has two objects in it as far as a reader
and every later retrieval are concerned.

The draft is the only text searched, and a scene with no draft is **skipped**, not clean
(fixture README: scenes 001, 004, 005 and 006 are silent "for that reason rather than
because the prose is clean"). Two variants that match the same span -- the same text listed
under two terms, say -- are one finding, not two: the evidence is identical, and so is the id
(`findings.violation_id`); the entry point keeps the first.
"""

from __future__ import annotations

from typing import Final

from app.commons.schemas import Severity, Violation
from app.commons.stores import paths
from app.ledger.audit.findings import CheckOutcome, Skip, occurrences, violation
from app.ledger.audit.material import AuditMaterial

CHECK: Final[str] = "FR-AUD-05"
INVARIANT: Final[int] = 7
SEVERITY: Final[Severity] = Severity.BLOCKING


def run(material: AuditMaterial) -> CheckOutcome:
    """Every occurrence of a forbidden variant in the draft body, in draft order."""
    scene = material.scene
    if material.draft is None:
        return Skip(f"{paths.draft(scene.id)} is absent; there is no prose to search")
    if material.lexicon is None:
        return Skip(f"{paths.LEXICON} is absent; there are no forbidden variants to search for")

    body = material.draft.body
    found: list[Violation] = [
        violation(scene=scene.id, invariant=INVARIANT, severity=SEVERITY, evidence=evidence)
        for term in material.lexicon.terms
        for variant in term.forbidden_variants
        for evidence in occurrences(body, variant)
    ]
    return sorted(found, key=lambda finding: finding.evidence.offset)


__all__ = ["CHECK", "INVARIANT", "run"]
