---
description: Generate a gift novel from a brief with the backend CLI, resuming from the last checkpoint if a run was interrupted
argument-hint: <path/to/brief.json>
---

Generate a novel from the brief at `$ARGUMENTS` (default: `evals/briefs/ejemplo.json`).

1. Check the brief exists and is JSON. If it does not validate against
   `backend/schemas/brief*.json`, stop and report the schema errors; do not "fix" the
   brief yourself.
2. Check `backend/.env` exists (copy of `backend/.env.example`). Langfuse keys are optional:
   without them tracing is a no-op, say so in the report.
3. Run, from the repository root:

   ```bash
   cd backend && uv run python -m app.novel.cli generate --brief ../$ARGUMENTS
   ```

   Run it in the background and watch its output; a 10-chapter novel takes a while.
4. Report per chapter: checkpoint status, word count, validators passed/failed (from the
   CLI output, or `validator_result` in `HARNESS_DB`, default `data/harness.sqlite`).
5. If it stops with an error, do not restart from scratch: re-run the same command, which
   resumes from the last completed chapter. If the same role fails twice, report it; raising
   a role's model is a decision for the user and goes in `docs/process/iteraciones.md`.
6. End with the `novel_id`, the published version, and the Langfuse session id if any.

Do not edit prompts, validators or code from this command. It runs the system; it does
not change it.
