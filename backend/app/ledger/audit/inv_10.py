"""FR-AUD-08 -- invariant 10, thread latency. Severity `reviewable`.

"No active thread exceeds its `max_latency` without reappearing." The only invariant measured
on the **discourse** axis: a subplot vanishes from the page, not from history, so the gap is
counted in `discourse_order` between this scene and the thread's last appearance at or before
it. A gap equal to `max_latency` is within it; only a larger gap is reported (fixture README:
scene 003, gap 2 against 2, is clean).

The population is threads `planted` or `developing`. A `dormant` thread is deliberately
resting, and a `resolved` or `abandoned` one is closed and can never be late. A thread whose
first appearance is after this scene has not begun yet and has no latency here.

Appearances are placed by the scene records' `discourse_order`, not by their position in the
thread's list, because the records are the authority on the axes. A listed scene with no
record cannot be placed and is reported as a `note` -- dropping it silently could make a late
thread look fresh, or a fresh one late.
"""

from __future__ import annotations

from typing import Final

from app.commons.schemas import Severity, ThreadState, Violation
from app.commons.stores import paths
from app.ledger import repository
from app.ledger.audit.findings import CheckOutcome, Skip, record_evidence, violation
from app.ledger.audit.material import AuditMaterial

CHECK: Final[str] = "FR-AUD-08"
INVARIANT: Final[int] = 10
SEVERITY: Final[Severity] = Severity.REVIEWABLE
ACTIVE: Final[frozenset[ThreadState]] = frozenset({ThreadState.PLANTED, ThreadState.DEVELOPING})


def run(material: AuditMaterial) -> CheckOutcome:
    """Active threads whose last appearance is further back than their `max_latency`."""
    if material.threads is None:
        return Skip(f"{repository.THREADS_PATH} is absent; there are no threads to check")

    scene = material.scene
    here = scene.discourse_order
    found: list[Violation] = []
    for thread in material.threads.threads:
        if thread.state not in ACTIVE:
            continue
        locator = f"{repository.THREADS_PATH} {thread.id}"
        details: list[tuple[Severity, str]] = [
            (
                Severity.NOTE,
                (
                    f"{locator}: lists scene {listed}, and there is no scene {listed} to place "
                    "on the discourse axis"
                ),
            )
            for listed in thread.scenes
            if listed not in material.scenes
        ]
        placed = [
            material.scenes[listed]
            for listed in thread.scenes
            if listed in material.scenes and material.scenes[listed].discourse_order <= here
        ]
        if placed:
            last = max(placed, key=lambda record: record.discourse_order)
            gap = here - last.discourse_order
            if gap > thread.max_latency:
                details.append(
                    (
                        SEVERITY,
                        (
                            f"{locator} ({thread.state.value}): last appears at "
                            f"{paths.scene(last.id)} (discourse {last.discourse_order}); "
                            f"scene {scene.id} is at discourse {here}, a gap of {gap} against "
                            f"max_latency {thread.max_latency}"
                        ),
                    )
                )
        found.extend(
            violation(
                scene=scene.id,
                invariant=INVARIANT,
                severity=severity,
                evidence=record_evidence(detail),
            )
            for severity, detail in details
        )
    return found


__all__ = ["CHECK", "INVARIANT", "run"]
