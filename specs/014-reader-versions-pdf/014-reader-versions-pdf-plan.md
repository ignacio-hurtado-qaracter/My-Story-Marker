---
spec: 014
status: done              # closed 2026-09-25 with spec 014 (programme 004 close-out)
---

## Files to touch

- `backend/app/reader/{__init__,models,service,changes,router,visual_check,dev_seed}.py`, `tests/` — K5 API, change jobs, validator, seed.
- `backend/app/export/{__init__,pdf,cli}.py` — PDF export and CLI.
- `backend/pyproject.toml`, `uv.lock` — add `reportlab` (shared-file commit).
- `backend/app/main.py` — mount the reader router (shared-file commit).
- `backend/openapi.json`, `frontend/src/shared/types/openapi.d.ts` — regenerated (`contract:`).
- `frontend/src/reader/**` (new) — API hooks, novel list, index, chapter, version selector, change request.
- `frontend/src/cover/**` — cover from the API; the localStorage form is retired.
- `frontend/src/bible/**` — sheets from `/novels/{id}/bible`; the legacy cast pages retired.
- `frontend/src/app/routes.tsx` — `/` lists novels, `/novelas/:id/...` (shared-file commit).
- `frontend/e2e/visual-check.spec.ts`, `frontend/README.md` — visual check, how to run.

## Steps

1. Spec and plan.
2. `reportlab` dependency. AC 2.
3. Reader service, router, change jobs, PDF export, CLI, validator, seed, tests. AC 1–3, 5, 6.
4. Mount the router; regenerate the contract. AC 1.
5. Frontend reader, cover, bible, routes; old tests that no longer apply removed. AC 4, 6.
6. Visual check spec, README; one run on the seed. AC 4, 5.

## Verification mapping

| AC | Letter | Satisfied by |
|---|---|---|
| AC 1 | T | `backend/app/reader/tests/test_reader.py::test_chapter_index` |
| AC 2 | T | `backend/app/reader/tests/test_reader.py::test_pdf_export` |
| AC 3 | I · D | Review note; a manual POST against the seed |
| AC 4 | D | `frontend/e2e/visual-check.spec.ts` run, screenshots |
| AC 5 | I · D | Review note; the run above |
| AC 6 | A | ruff / mypy / eslint / tsc output in the commit bodies |

## Risks and stop conditions

- B3's `change_fact` signature differs from K4 → adapt in `changes.py` only; if it would
  need a store write from the reader, stop (no role widening).
- `fact_usage` is empty for a novel → the name-search fallback keeps the sheets linked.
- A legacy e2e spec depends on the old cover → recorded in the report for the orchestrator.
