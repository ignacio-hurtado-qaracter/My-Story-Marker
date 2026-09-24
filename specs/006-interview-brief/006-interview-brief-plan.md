---
spec: 006
status: approved          # approved 2026-09-24 on the user's delegation for this session
---

# Plan 006 — Interview and brief

## Files to touch

- `backend/app/interview/__init__.py` — package docstring, public names.
- `backend/app/interview/brief.py` — `Brief`, `BriefDraft`, `validate_brief`, `BriefReport`.
- `backend/app/interview/extract.py` — `prescan_injection`, `extract_facts_from_free_text`.
- `backend/app/interview/interviewer.py` — `Interviewer`, `InterviewTurn`, merge of updates.
- `backend/app/interview/service.py` — `ingest_brief`, `InvalidBriefError`.
- `backend/app/interview/router.py` — the three routes.
- `backend/app/interview/cli.py` — `interview`, `validate`, `ingest`.
- `backend/app/interview/tests/test_brief.py` — four light tests.
- `backend/app/prompts/interviewer.md`, `backend/app/prompts/fact_extractor.md`.
- `backend/schemas/brief.v1.json` — exported.
- Shared: `backend/scripts/export_schemas.py` (a `RECORD_MODELS` registry for database
  records with a schema), `backend/tests/test_schema_export.py` (orphan check includes it),
  `backend/app/main.py` (mount router), `backend/openapi.json` (regenerated).

## Steps

1. Spec and plan (`spec(006):`, `plan(006):`).
2. `brief.py` + schema export + test for AC 1–3 (`backend:`, shared `contract:` for the
   export script).
3. `extract.py` + prompt `fact_extractor.md` + pre-scan test (AC 5).
4. `service.py` ingest + test (AC 4).
5. `interviewer.py`, prompt `interviewer.md`, `cli.py`, `router.py` (AC 7).
6. Mount router in `main.py`, regenerate `openapi.json` (`contract:`).
7. Manual live extractor call (AC 6).

## Verification mapping

| AC | Letter | Satisfied by |
|---|---|---|
| 1 | T | `test_missing_fields_reported` |
| 2 | T | `test_age_genre_contradiction` |
| 3 | A | `export_schemas.py --check` |
| 4 | T | `test_ingest_creates_facts_and_characters` |
| 5 | T | `test_prescan_flags_spanish_injection` |
| 6 | D | manual live run, reported |
| 7 | I | review note; `export_openapi.py --check` |

## Risks and stop conditions

- A needed change to `app/bible` (K1) → stop, ask the orchestrator; do not edit it.
- The live client rejects the documents or schema → adjust the output model, not K2.
- Another block edits `main.py` or `export_schemas.py` concurrently → keep the commits
  small and separate so the orchestrator can resolve.
