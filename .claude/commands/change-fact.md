---
description: Request a reader change to one fact of a novel ("el perro se llama Nala") and regenerate only the chapters that use it
argument-hint: <novel_id> <fact key or text> <new value>
---

A reader change (exam § 2; spec 004 D2 and contract K5 `change_fact` / `publish_version`).
Arguments: `$ARGUMENTS`.

1. Find the fact in the story bible (`HARNESS_DB`, table `fact`) by key or by matching its
   value. If more than one fact matches, list them and ask which one; never guess.
2. Show which chapters use it (`fact_usage`). Those, and only those, will be regenerated.
3. Request the change through the backend, never by editing the database or chapter text:
   - API: the `change_fact` route under `/novels/{novel_id}/...` (contract K5);
   - or CLI: the `change-fact` subcommand of `app.novel.cli`.

   Exact route and flags are fixed by block B10 (spec 014): read them from
   `backend/openapi.json` and `cd backend && uv run python -m app.novel.cli --help`
   before calling. Pending until B10 merges.
4. Wait for the new version. Report: new version number, chapters changed, validators
   result, and that the previous version is still readable.
5. Optionally run `/inspect-novel <novel_id>` to see the "changed" marks in the reader.
