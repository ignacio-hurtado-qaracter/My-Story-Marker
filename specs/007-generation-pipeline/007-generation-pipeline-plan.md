---
spec: 007
status: done              # closed 2026-09-25 with spec 007 (programme 004 close-out)
---

## Files to touch

- `backend/app/novel/__init__.py` — package doc, public names.
- `backend/app/novel/models.py` — pydantic role outputs (`NovelPlan`, `SceneDraft`, `ChapterEdit`) and run results.
- `backend/app/novel/plan_check.py` — programmatic plan validation.
- `backend/app/novel/context.py` — documents handed to each role (brief summary, tails, summaries).
- `backend/app/novel/roles.py` — planner, writer, editor calls through `traced_complete`.
- `backend/app/novel/pipeline.py` — `generate`, `plan_novel`, `write_chapter`, `close_chapter`, `checkpoint`, `publish_version`, `change_fact`, hook points.
- `backend/app/novel/_bible_ext.py` — plan storage as a planner fact, character/place rename.
- `backend/app/novel/setup.py` — `register_all()`.
- `backend/app/novel/cli.py` — argparse CLI, run as `python -m app.novel.cli`.
- `backend/app/novel/_ingest_fallback.py` — minimal brief ingest when B2 is absent.
- `backend/app/prompts/{planner,writer,editor}.md` — role prompts (Spanish prose rules).
- `backend/app/novel/tests/{test_pipeline.py,fixtures/brief_smoke.json}`.

## Steps

1. Models, plan check, context, prompts (AC 5).
2. Roles and pipeline, setup, bible helpers (AC 1–4, 6).
3. Ingest fallback and CLI (AC 1, AC 6).
4. Tests with the fake client (AC 1, 2, 3, 5).
5. Live smoke, fixes (AC 1, AC 6).

## Verification mapping

| AC | Letter | Satisfied by |
|---|---|---|
| AC 1 | T · D | `test_pipeline.py::test_happy_path_two_chapters`; live smoke |
| AC 2 | T · I | `test_pipeline.py::test_chapter_retries_bounded`; review of `close_chapter` / `publish_version` |
| AC 3 | T | `test_pipeline.py::test_resume_no_duplicate` |
| AC 4 | I · D | review of `change_fact`; live run if time allows |
| AC 5 | T | `test_pipeline.py::test_plan_check` |
| AC 6 | D | Langfuse trace of the live smoke |

## Risks and stop conditions

- Haiku writes chapters shorter than 1000 words → one bounded length adjustment by the editor
  before `chapter_close`; if it keeps failing, raise only the editor to Sonnet 5 (plan 004).
- Structured output of a 10-chapter plan exceeds limits → split the plan call and record it
  here.
- A contract turns out wrong → stop, note it in spec 007 Open questions, tell the orchestrator.
