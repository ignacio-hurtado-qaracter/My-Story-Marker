"""The mechanical audit (plan step 14; spec FR-AUD-01..09, AC 15, AC 16).

`audit(scene)` in `architecture.md`: "runs the domain invariants against the draft and current
canon. Reports; does not repair." The second sentence is the design. An auditor that
self-corrects trims precisely the living details that made the scene work, because those are
the ones that deviate from the plan -- so nothing in this package writes a draft, a scene
record or canon. It produces `Violation`s; the only file it can write is
`ledger/violations.yaml`, through `persist`, and only the auditor role gets past Figure 3.

One module per mechanical invariant, named by invariant number:

    inv_01  FR-AUD-01  1  knowledge monotonicity, record half   blocking
    inv_02  FR-AUD-02  2  closed debts                          reviewable; blocking at last
    inv_04  FR-AUD-03  4  spatial uniqueness                    blocking
    inv_05  FR-AUD-04  5  possible transits                     blocking; missing entry note
    inv_07  FR-AUD-05  7  canonical lexicon                     blocking
    inv_08  FR-AUD-06  8  no inert scenes, record half          reviewable
    inv_09  FR-AUD-07  9  recognisable voice (POV only)         reviewable
    inv_10  FR-AUD-08  10 thread latency                        reviewable

Invariants 3 and 6 and the prose halves of 1 and 8 are the model-backed auditor's (FR-AUD-09),
the auditor role in `agents`. The combined audit runs the mechanical checks here first and
folds the role's findings in with `with_semantic`; `violation_id` gives a model finding its
deterministic id, and `persist` merges both halves into `ledger/violations.yaml` by the same
rules. With no auditor wired, a request for the semantic half lists those four in `skipped`.

This package is the ledger's public surface for the audit: `scenes` (the route) and, later,
`agents` (the turn's audit step) import it; neither imports the modules behind it.
"""

from __future__ import annotations

from app.ledger.audit.findings import natural_key, violation_id
from app.ledger.audit.persist import merge, persist
from app.ledger.audit.report import AuditReport, CheckRef, SkippedCheck
from app.ledger.audit.runner import (
    MECHANICAL_CHECKS,
    SEMANTIC_CHECK,
    SEMANTIC_HALVES,
    audit_scene,
    with_semantic,
)

__all__ = [
    "MECHANICAL_CHECKS",
    "SEMANTIC_CHECK",
    "SEMANTIC_HALVES",
    "AuditReport",
    "CheckRef",
    "SkippedCheck",
    "audit_scene",
    "merge",
    "natural_key",
    "persist",
    "violation_id",
    "with_semantic",
]
