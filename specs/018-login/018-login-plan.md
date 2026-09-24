---
spec: 018
status: approved          # approved 2026-09-24 on the user's delegation for this session
---

## Files to touch

- `backend/pyproject.toml`, `backend/uv.lock` — `bcrypt`, `pyjwt` pinned.
- `backend/app/commons/db/authoritative/migrations/1700_auth.sql` — `app_user`, `novel.owner_id`, the `local` user.
- `backend/app/bible/{models,repository}.py` — `AppUser`, `Novel.owner_id`, user methods, `scoped_to` (additive).
- `backend/app/auth/**` — security, deps, router, tests.
- `backend/app/main.py` — mount `/auth`.
- `backend/app/reader/router.py`, `backend/app/interview/{router,service}.py` — owner scoping (service: `owner_id` kwarg).
- `backend/app/mcp_server/server.py` — env identity. `backend/app/tools/*` unchanged: the scoping lives in the repository the tools receive.
- `backend/conftest.py` — `AUTH_REQUIRED=0` default for the existing suites.
- `backend/tests/test_api_contract.py`, `backend/openapi.json`, `frontend/src/shared/types/openapi.d.ts`.
- `frontend/src/shared/api/{client,auth-token,index}.ts`, `frontend/src/auth/**`, `frontend/src/app/{routes,Layout}.tsx`, `frontend/src/reader/ReaderLayout.tsx` (PDF with the header), `frontend/e2e/{backend,visual-check.spec}.ts`.
- `.env.example`, `backend/.env.example`, `docs/security-report.md`.

## Steps

1. Spec and plan. 2. Dependencies. 3. Migration + repository (AC 5). 4. `app.auth` + mount
(AC 1). 5. Reader and interview scoping (AC 2, 3). 6. MCP identity (AC 4). 7. Contract,
OpenAPI, types. 8. Frontend (AC 6, 7). 9. Security report.

## Verification mapping

| AC | Letter | Where |
|---|---|---|
| 1 | T | `app/auth/tests/test_auth.py::test_register_login_and_hash` |
| 2 | T | `test_auth.py::test_reader_requires_a_token` |
| 3 | T | `test_auth.py::test_user_cannot_reach_another_users_novel` |
| 4 | T | `test_auth.py::test_mcp_tools_are_scoped_to_the_env_user` |
| 5 | T | existing suites + `test_auth.py::test_existing_novels_belong_to_local` |
| 6 | T | `frontend/src/auth/auth.test.tsx` |
| 7 | I | review |

## Risks and stop conditions

A route that reads a novel without going through the scoped repository would leak; every
`/novels/{novel_id}` route resolves the novel through one dependency first. If a store
family other than the story bible turns out to hold client data, reopen Process 0.
