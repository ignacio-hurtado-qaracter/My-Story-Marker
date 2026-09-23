"""FR-AUD-01 -- invariant 1, knowledge monotonicity, the record half. Severity `blocking`.

"Nobody references information whose `acquired_in` is later than the current scene." Whether
the *prose* references something too early is a judgement about the page and belongs to the
model-backed auditor (FR-AUD-09). What code can check is that the knowledge records the
as-of dossier (FR-OPS-01) is built from are anchored where they claim to be:

* every `KnowledgeState` with `acquired_in` equal to this scene names a character who is in
  it -- the POV or a participant. A character cannot have witnessed, been told or worked out
  anything *in* a scene they were not in, and a row that says so hands every later scene a
  fact whose origin is fiction. That is the fixture's planted row: quiej, acquiring
  `ax_brine_dark` in 004, where she is neither the POV nor a participant.
* every `acquired_in` resolves to a scene record. A dangling anchor cannot be placed on the
  story axis, so the as-of question "does she know this yet?" has no answer for the holder.
  It is reported at every scene the holder is present in, because that is where the
  unanswerable question is asked; the spec names the rule but not the scene it is reported
  against, and this attribution is a decision reported with the step.

Blocking, as the spec sets it: a mis-anchored knowledge state leaks into every context
assembled after it, and the writer of the next scene cannot tell it from a real one.
"""

from __future__ import annotations

from typing import Final

from app.commons.schemas import Severity, Violation
from app.commons.stores import paths
from app.ledger.audit.findings import CheckOutcome, present, record_evidence, violation
from app.ledger.audit.material import AuditMaterial

CHECK: Final[str] = "FR-AUD-01"
INVARIANT: Final[int] = 1
SEVERITY: Final[Severity] = Severity.BLOCKING


def run(material: AuditMaterial) -> CheckOutcome:
    """Knowledge rows anchored in this scene to someone absent, or held by someone present
    and anchored to no scene at all."""
    scene = material.scene
    here = present(scene)
    found: list[Violation] = []
    for character in sorted(material.knowledge):
        relative = paths.cast_file(character, "knowledge")
        for row in material.knowledge[character].knowledge:
            locator = f"{relative} ({row.character}, {row.fact_ref}, {row.acquired_in})"
            if row.acquired_in == scene.id and row.character not in here:
                detail = (
                    f"{locator}: {row.character} acquired {row.fact_ref} in {scene.id} via "
                    f"{row.via.value}, but scene {scene.id} has pov {scene.pov} and "
                    f"participants [{', '.join(scene.participants)}]"
                )
            elif row.character in here and row.acquired_in not in material.scenes:
                detail = (
                    f"{locator}: {row.character} acquired {row.fact_ref} in "
                    f"{row.acquired_in}, and there is no scene {row.acquired_in} to anchor it"
                )
            else:
                continue
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
