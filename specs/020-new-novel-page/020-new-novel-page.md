---
id: 020
title: "Nueva novela" — fill in the brief and launch a generation from the web
status: approved         # approved 2026-09-25 on the user's request (delegated for this session)
supersedes: null
owns:
  - backend/app/reader/generation.py, backend/app/reader/tests/test_generation.py
  - backend/app/reader/{router,models}.py (additive)
  - frontend/src/newnovel/**
  - frontend/src/app/{routes.tsx,Layout.tsx} (one additive line each)
  - specs/020-new-novel-page/
docs:
  - docs/architecture.md#the-reader
  - docs/definitions.md#brief
---

> **Approved 2026-09-25** on the user's request, with approvals delegated for this session.
> Process 0 is the request itself: a frontend page where the user fills in the
> personalisation and launches a new novel, reusing the interview and change-job code.

## Motivation

Today a novel can only be started from the CLI (`app.novel.cli generate`) or through the
conversational `/interview` routes, which ingest a brief but never generate. A reader with
a login has no way to commission a novel from the web.

## Scope

In: `POST /novels/generate` and `GET /novels/{id}/generation`, owner-scoped, running
`app.novel.pipeline.generate` in a background thread like the change jobs (spec 014); a
concurrency cap; the `/nueva` wizard page (5 steps) with live validation through
`POST /interview/validate`, an example filler, and a progress view.

Out: no change to the pipeline, the validators, the Brief model or the permission table
(Figure 3); no persistence of job state beyond the process (the database's checkpoints and
cost rows are the durable record, and the status route falls back to them); no cancel
button; no conversational interviewer in the page.

## Design

- The route validates the brief with `validate_brief` (422 with the `BriefReport` as
  `detail`), then submits a job. The job ingests with `ingest_brief(owner_id=<caller>)`
  (so the novel is owned by the caller, spec 018) and calls `generate(repo, novel_id,
  chapters=...)` on its own repository connection. Nothing in the route writes a store.
- `chapters` (1–10) overrides `brief.length.chapters`.
- At most 2 generations run per process; a third is a 429.
- Status: in-memory job (phase from the pipeline's progress lines) merged with the
  database (novel status, latest version status, complete checkpoints, `cost_summary`,
  last failed validator results). A novel without a job (restart, CLI) is answered from
  the database only. Another owner's novel is a 404.
- Lean: each novel has its own Lake copy (`app.novel.setup.register_lean_for`); in one
  process the `lake build` of two runs is serialised by `lean_runner._BUILD_LOCK`, and
  each build writes its own novel's chronology first, so concurrent runs do not mix.

## Acceptance criteria

1. An invalid brief is answered 422 with its missing fields and contradictions; nothing is
   ingested. — **T**
2. A valid brief is answered 202 with `{novel_id, job_id}` and the job calls `generate` for
   that novel, owned by the caller; its status is readable, and 404 for another owner. — **T**
3. A third concurrent generation is a 429. — **I** (review of `GenerationJobs.submit`)
4. The route table, `openapi.json` and the frontend types include the two routes. — **T**
   (`tests/test_api_contract.py`, `npm run check:api`)
5. The wizard shows the validation report in Spanish and blocks submit until valid; submit
   posts the brief. — **T** (vitest)
6. The wizard and the progress view render at desktop and 390 px. — **D** (screenshots in
   `frontend/screenshots/new-novel/`)

## Verification plan

`backend/app/reader/tests/test_generation.py` (AC 1, 2, with `generate` monkeypatched —
no model calls); `tests/test_api_contract.py` (AC 4); `frontend/src/newnovel/*.test.tsx`
(AC 5); Playwright screenshots (AC 6); one optional 1-chapter live smoke (D).

## Open questions

None.
