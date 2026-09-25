---
id: 018
title: X03 — Login with SQLite and per-owner novels (closes SEC-01)
status: implemented      # closed 2026-09-25 on the user's delegation (programme 004 close-out)
supersedes: null
programme: 004
block: optional X03
owns:
  - backend/app/auth/**
  - backend/app/commons/db/authoritative/migrations/17xx_*.sql (range 1700–1749)
  - frontend/src/auth/**
  - specs/018-login/
depends_on: [B1 (K1), K5 reader, B2 interview, spec 017 tools/MCP]
closes: [X03, SEC-01, SEC-08 (ownership half)]
docs:
  - docs/security-report.md#sec-01--sin-autenticación-ni-autorización-media-aceptado
  - docs/architecture.md#read-only-tools-for-the-model
---

> **Approved 2026-09-24** on the user's delegation for this session (plan 004, deviation V6).
> Process 0 is the programme's: exam brief, optional "Login de usuarios con SQLite", and the
> fix proposed for SEC-01 in `docs/security-report.md`.

## Motivation

SEC-01: no route of `/novels` or `/interview` and no MCP tool asks for an identity, so any
client lists, reads, downloads and changes every novel. X03 asks for register/login with a
hashed password in SQLite, a session token, every novel, brief and audit entry tied to an
owner, the MCP server respecting the identity, and tests that a user cannot reach another
user's novels.

## Scope

In:

- `app_user` table and `novel.owner_id` (migration `1700_auth.sql`); a built-in user
  `local` owns every pre-existing novel and every novel created without an owner (the CLI
  pipeline, `app.novel.cli`, stays unauthenticated: it is local; `STORY_MAKER_USER=<email>`
  makes a registered user the default owner instead).
- `POST /auth/register`, `POST /auth/login`, `GET /auth/me`. Passwords hashed with bcrypt;
  a JWT (HS256, PyJWT) signed with `AUTH_SECRET` (dev default generated per process, with a
  warning), 12 h expiry.
- `AUTH_REQUIRED` (default `1`): reader (`/novels/**`) and interview routes need a valid
  `Authorization: Bearer` token and only see the caller's novels (404 for another owner's).
  With `AUTH_REQUIRED=0` a request without a token acts as `local`.
- `BibleRepository.scoped_to(owner_id)`: an owner-scoped view whose `get_novel`,
  `list_novels` and `list_policy_decisions` hide other owners' rows. Additive; unscoped use
  is unchanged.
- MCP: every tool runs on a repository scoped to `STORY_MAKER_USER` (email) or `local`.
- Frontend: `/login` page (login and register), token in memory + `localStorage`
  (try/catch), `Authorization: Bearer` on every API call, logout, redirect to `/login` on
  401, PDF download with the header. Spec 003 styles.

Out: password reset, roles/admin, refresh tokens, token revocation, rate limiting, token
auth for the MCP HTTP transport (it binds 127.0.0.1 and uses the same env identity), the
store routes of spec 001 (`/canon`, `/scenes`, ... — the harness tree, not client novels).

**Ownership of briefs and audit entries.** `brief`, `validator_result` and
`policy_decision` rows are keyed by `novel_id`; their owner is `novel.owner_id` by join. No
extra column: a join cannot drift from the novel's owner, a copied column could.

## Design

`app.auth` owns hashing, tokens and the FastAPI dependency `CurrentUserDep`. The token is
stateless (`sub` = user id, `email`), so identity costs no query. The reader's per-request
repository is `repo.scoped_to(user.id)`, and every `/novels/{novel_id}/...` route first
resolves the novel through it, so another owner's novel is exactly as absent as a missing
one (404, same body). The interview creates the novel with the caller as owner, and refuses
(404) a `novel_id` owned by someone else; an already-ingested brief answers 409 instead of
500 (SEC-08).

## Acceptance criteria

1. Register stores a bcrypt hash (never the password) and login returns a JWT; a wrong
   password is 401; a duplicate email is 409. — **T**
2. With `AUTH_REQUIRED=1`, `/novels` without a token is 401. — **T**
3. User B does not see user A's novel: `GET /novels` omits it; its chapter, PDF and a change
   request are 404. — **T**
4. The MCP tool layer, scoped to user B, does not list user A's novels and `download_novel`
   of A's novel is `ToolNotFoundError`. — **T**
5. Existing novels and CLI-created novels belong to `local`; the existing suites pass
   unchanged (`AUTH_REQUIRED=0` in the root conftest). — **T**
6. The frontend attaches the stored token as `Authorization: Bearer`. — **T**
7. The login page renders with spec 003 styles and logout clears the token. — **I**

## Verification plan

`backend/app/auth/tests/test_auth.py` (AC 1–5), `frontend/src/app/auth.test.tsx` (AC 6),
review of the page (AC 7). The contract test and schemathesis run with `AUTH_REQUIRED=0`
(root conftest); the auth routes are added to the contract's route table.

## Open questions

None. Deferred: token auth for MCP over HTTP; revocation.

## Closing note (2026-09-25)

Closed on the user's delegation (programme 004 close-out, Process 2 step 12). Evidence at
`proyecto-desde-cero` @ `0e8118c`: backend gate `ruff check .` clean, `mypy --strict .`
clean (290 files), `pytest` 1758 passed / 8 skipped / 1 failed. The one failure is
`tests/test_boundaries_mirror.py`, the spec 001 store-boundary guard, which flags file I/O
in the new modules; it is not an acceptance criterion of this spec and is left to the
author (`docs/process/README.md`, "Pendiente para el autor").

| AC | Satisfied by |
|---|---|
| 1 | T — `app/auth/tests/test_auth.py` (bcrypt hash, JWT, 401, 409) |
| 2 | T — `test_auth.py` (`AUTH_REQUIRED=1` → 401) |
| 3 | T — `test_auth.py` (user isolation: list, chapter, PDF, change request → 404) |
| 4 | T — `test_auth.py` (tool layer scoped per user, `ToolNotFoundError`) |
| 5 | T — `test_auth.py` (`local` owner); suites pass with `AUTH_REQUIRED=0` in the root conftest |
| 6 | T — `frontend/src/app/auth.test.tsx` (Bearer header) |
| 7 | I — review of `frontend/src/auth/LoginPage.tsx` and `UserMenu.tsx` (spec 003 styles, logout clears the token) |
