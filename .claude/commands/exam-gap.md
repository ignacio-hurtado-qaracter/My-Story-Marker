---
description: Run the exam compliance checker and summarise what is still missing, grouped by owning block
---

1. From the repository root run `python exam/check.py --stdout` (standard library only, no
   virtualenv needed). Use `--strict` only if asked for an exit code.
2. Summarise:
   - totals: met, partial, missing, manual;
   - every missing or partial required item as `id — text — detail`, grouped by the block
     that owns it in spec 004 § 3 (`specs/004-exam-refactor-programme/`);
   - manual items still needing a human (review, email, video).
3. Point out any item that regressed compared to the committed `exam/compliance.md`.
4. Do not commit the regenerated report unless asked; the checker is heuristic, a pass
   means an artefact exists, not that it is good.
