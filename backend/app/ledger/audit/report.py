"""The answer of `audit(scene)`: what was found, what was checked, and what was not.

Not a store record -- nothing writes it to disk as it stands; `persist` writes its violations
into `ledger/violations.yaml`. It is the wire shape of `POST /scenes/{id}/audit` (IF-05) and
the value the orchestrator's audit step will hand on, so it is the public surface of the
operation and lives beside the checks that produce it.

**Three lists, because one would lie.** `violations` alone cannot distinguish "the scene is
clean" from "the check did not run". FR-AUD-09 requires the model-backed half to be listed as
`skipped` when it does not run, so its silence is never read as a pass; this report applies
the same accounting to the mechanical half -- a text check with no draft, a transit check
with no matrix -- and adds `checked`, the checks that did run. A reader can then say exactly
which invariants the empty list of violations vouches for.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.commons.schemas import Invariant, SceneId, Violation, ViolationSource
from app.commons.stores.provenance import ProvenanceRecord


class CheckRef(BaseModel):
    """One check of the audit, named by its FR-AUD row, its invariant and its half."""

    model_config = ConfigDict(extra="forbid")

    check: str = Field(
        description="The spec row: `FR-AUD-01` ... `FR-AUD-08` for the mechanical checks,"
        " `FR-AUD-09` for the model-backed half.",
    )
    invariant: Invariant = Field(description="The domain invariant of `definitions.md` served.")
    source: ViolationSource = Field(
        description="The half that runs it, as DR-07 `source` names it: `mechanical` or"
        " `model`. A finding with this source can only come from a check listed as run.",
    )


class SkippedCheck(CheckRef):
    """A check that did not run. Its silence is not a pass (FR-AUD-09)."""

    reason: str = Field(
        min_length=1,
        description="Why it did not run: the absent input, or the model step that is missing"
        " or failed.",
    )


class AuditReport(BaseModel):
    """IF-05, `POST /scenes/{id}/audit`. The audit of one scene. Reports; does not repair."""

    model_config = ConfigDict(extra="forbid")

    scene: SceneId = Field(description="The scene audited.")
    semantic: bool = Field(
        description="Whether the model-backed half (FR-AUD-09) was requested. When it was and"
        " did not run, its invariants are listed in `skipped`.",
    )
    violations: list[Violation] = Field(
        description="Every finding, mechanical checks in FR-AUD order, each with a deterministic"
        " id so a persisted re-run recognises its own findings.",
    )
    checked: list[CheckRef] = Field(
        description="The checks that ran. The absence of a violation vouches for these and"
        " nothing else.",
    )
    skipped: list[SkippedCheck] = Field(
        description="The checks that did not run, and why.",
    )
    persisted: ProvenanceRecord | None = Field(
        default=None,
        description="The write to `ledger/violations.yaml`, when `persist=true` was requested"
        " under the auditor role; empty when nothing was written.",
    )


__all__ = ["AuditReport", "CheckRef", "SkippedCheck"]
