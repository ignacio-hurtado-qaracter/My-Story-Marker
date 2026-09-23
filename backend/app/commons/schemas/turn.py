"""FR-TURN-07, FR-OPS-05. The record of one writing turn, as far as anyone but the
orchestrator needs to read it.

It lives in `commons/` rather than in `agents/` for the reason DR-01 gives: two features use
it. `agents/` writes it, and `canon/`'s `reconcile` reads it (FR-OPS-08: "every turn record
whose selected list contains" the changed entity). `canon/` sits below `agents/` in the
feature layers of NFR-04, so it could not import the model from there.

This is the part of the record that is stable now. Plan step 18 adds the per-step detail --
role, model id, prompt version, token counts, elapsed, violations per iteration, promotion
results -- when the orchestrator that produces it exists.

Turn records live under `.index/turns/`, which is **not** a store: it is not governed by
Figure 3 and no agent reads it (Decision R2-1). They are also not rebuildable (AC 31).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from app.commons.schemas.common import EntityId, HarnessModel, SceneId, StoreDocument


class TurnOutcome(StrEnum):
    """Figure 4's terminal states, plus the two a record can be read in before one."""

    RUNNING = "running"
    AWAITING_RULING = "awaiting_ruling"
    MERGED = "merged"
    ESCALATED = "escalated"


class SelectedEntity(HarnessModel):
    """One entry of the selected list (FR-OPS-02, FR-OPS-05).

    Recorded rather than recomputed because selection is not reproducible: two runs may rank
    differently, and "which axioms apply to this scene" must have one answer per turn, shared
    by the writer and the auditor.
    """

    entity_id: EntityId
    kind: str = Field(min_length=1, description="The index row's kind: axiom, character, ...")
    score: float = Field(description="Fused rank score; higher is more relevant.")
    pinned: bool = Field(
        default=False,
        description="True when the entity entered through `pins` or a tag-scope match.",
    )


class TurnRecord(StoreDocument):
    """`.index/turns/NNN-<n>.yaml`. Written after every step, so a crash leaves the steps
    completed so far on disk (FR-TURN-09)."""

    id: str = Field(pattern=r"^\d{3}-\d+$", description="`NNN-<n>`: scene id and attempt.")
    scene: SceneId
    outcome: TurnOutcome = TurnOutcome.RUNNING
    selected: list[SelectedEntity] = Field(default_factory=list)


__all__ = ["SelectedEntity", "TurnOutcome", "TurnRecord"]
