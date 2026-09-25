---
spec: 020
status: approved          # approved 2026-09-25 with the spec (delegated)
---

## Files to touch

- `docs/architecture.md` — one bullet under "The reader": a new novel from the web.
- `backend/app/reader/generation.py` — `GenerationJobs` (submit, cap, status from job + DB).
- `backend/app/reader/models.py` — `GenerateRequest`, `GenerateAccepted`, `GenerationStatus`.
- `backend/app/reader/router.py` — the two routes.
- `backend/app/reader/tests/test_generation.py` — AC 1, AC 2.
- `backend/tests/test_api_contract.py`, `backend/openapi.json`,
  `frontend/src/shared/types/openapi.d.ts` — AC 4.
- `frontend/src/newnovel/**` — wizard, progress view, api, example brief, tests, css.
- `frontend/src/app/routes.tsx`, `frontend/src/app/Layout.tsx` — one route, one nav item.
- `frontend/screenshots/new-novel/` — AC 6.

## Steps

1. Spec and plan (`spec(020):`).
2. Docs bullet (`docs:`).
3. Backend jobs, routes, tests (AC 1–3, `backend:`).
4. Contract: route table, OpenAPI, frontend types (AC 4, `contract:`).
5. Frontend wizard, progress view and tests (AC 5, `frontend:`).
6. Screenshots (AC 6, `frontend:`).

## Verification mapping

| AC | Letter | Where |
|---|---|---|
| 1 | T | `backend/app/reader/tests/test_generation.py::test_invalid_brief_is_422` |
| 2 | T | `backend/app/reader/tests/test_generation.py::test_valid_brief_starts_generate` |
| 3 | I | review of `GenerationJobs.submit` |
| 4 | T | `backend/tests/test_api_contract.py`, `npm run check:api` |
| 5 | T | `frontend/src/newnovel/NewNovelPage.test.tsx` |
| 6 | D | `frontend/screenshots/new-novel/*.png` |

## Risks and stop conditions

A needed change to the pipeline, the Brief model or a permission reopens Process 0.
