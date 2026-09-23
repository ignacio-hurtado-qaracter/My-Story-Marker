---
spec: 002                 # the approved spec this plan implements
status: draft             # draft · approved · done
---

Implementation plan for [`002-frontend-foundation.md`](./002-frontend-foundation.md)
(status `approved`, 2026-09-23). The spec says *what* and *why*; this file says *how* and
*in what order*. Anything not listed under "Files to touch" is out of scope; a file that
turns out to be needed means this plan is wrong and goes back to `draft`.

Branch: **`spec/001-backend`**, in the same folder where the backend session is working at
the same time. This departs from Process 3 step 3 (`spec/NNN-short-slug`) at the user's
explicit request (2026-09-23), so the MVP grows on one branch. Commit prefixes: `frontend:`,
`contract:`, `chore:`. Every step is one commit, small enough to review alone, and names the
acceptance criteria it advances. Every test added carries `// spec 002 / AC n`.

**Sharing the branch without disturbing the backend session.** These rules hold for every
step:

- This plan writes only under `frontend/`, `specs/002-frontend-foundation/` and
  `.github/workflows/frontend.yml`. It never edits a file the backend session owns, and
  never a shared root file (`.gitignore`, `AGENTS.md`, `README.md`) — `frontend/.gitignore`
  holds the frontend's ignores.
- Every commit names its paths (`git commit -- frontend/ …`), so nothing the other session
  has staged or left modified can enter it. Never `git add -A`, `git add .` or `commit -a`.
- Never `checkout`, `switch`, `rebase`, `reset`, `stash`, `merge`, `pull` or `push` in this
  folder: all of them move the HEAD or the working tree under the other session's feet.
  The branch history is linear because both sessions only append commits.
- If `.git/index.lock` exists, wait and retry; never delete it.
- Before each commit, `git status --short -- <my paths>` must show only this step's files.

---

## Implementation decisions taken while planning

The spec leaves these open at the level of implementation. Each is resolved here with the
plain default; approving the plan approves them. Any one can be changed before approval
without touching the spec.

| # | Decision | Why |
|---|---|---|
| P1 | Versions are the **latest stable release of each package on the day of step 1**, pinned exactly (`frontend/.npmrc` with `save-exact=true`) and locked in `package-lock.json`. `engines.node` is `>=24 <25`, with `.nvmrc` = `24`. The resolved versions are listed in the step 1 commit body. | Spec FR-TOOL-01. Node 24.19 and npm 11.17 are on the machine. |
| P2 | React Router in **declarative mode** (`<BrowserRouter>` + `<Routes>`), not data mode. Data loading is TanStack Query's job; two loaders for one fetch would disagree. | Spec FR-TOOL-03. |
| P3 | react-three-fiber **v9** or later (the first major that supports React 19), with `three` and `@react-three/drei` at matching versions. | Spec FR-TOOL-06. |
| P4 | Typed MSW handlers through **`openapi-msw`** over the generated `paths`, so a handler for an unpublished route or a wrong response shape fails `tsc`. | Spec NFR-04. |
| P5 | Boundary rules: `eslint-plugin-boundaries` for the import rules between `app`, `shared/*` and features; `no-restricted-imports` for `openapi-fetch`, `three` and `@react-three/*`; `no-restricted-globals` for `fetch`, `XMLHttpRequest` and `EventSource`. Each has an override that re-allows it only in the folder the spec permits. | Spec FR-STATIC-02. `boundaries` handles imports between elements, not globals or packages. |
| P6 | Lint fixtures are files under `frontend/lint-fixtures/`, excluded from the normal lint run. The AC 3 test reads each one and lints its text with the project config at a **virtual path** under `src/` (ESLint `lintText` with `filePath`), taken from a header comment in the fixture. Type-aware rules are off for that one test config. | Spec AC 3. Fixtures never enter `src/`, so they are never built, typechecked or shipped. |
| P7 | `gen:api` and `check:api` use the `openapi-typescript` **Node API** in one module, `scripts/openapi.mjs`, so both produce the file byte for byte the same way. The output is formatted by the generator only; Prettier is not in the stack. | Spec FR-API-01, FR-API-03. |
| P8 | The dev proxy target defaults to `http://127.0.0.1:8000` (the backend README's `uvicorn` default) and reads `VITE_BACKEND_URL`. Playwright starts its own backend on port **8765**, so a developer's running backend is never the one under test. | Spec FR-API-05, NFR-05. |
| P9 | Playwright's global setup copies `backend/tests/fixtures/repo/` into a temporary directory and starts the backend there with `STORY_ROOT` and `STORY_INDEX` pointing into it. `EMBED_OFFLINE` stays **unset**: with it set, a missing model is a startup error (FR-EMB-03), and online no model is loaded until a rebuild, which no test here triggers. | Spec NFR-05; `backend/app/main.py`. |
| P10 | The backend is started with `uv run uvicorn app.main:app` when `uv` is on PATH (CI), else with `backend/.venv`'s Python (`-m uvicorn`). `uv` is not on this machine's bash PATH. | Local and CI both work, with no new tool. |
| P11 | The table-of-contents logic is a **pure function**, `buildToc(chapters, sceneIds)`, tested with examples and with `fast-check` properties (every scene appears exactly once; chapter order is preserved; unassigned scenes come last). | Spec FR-READ-01/03; [property-based testing](../../docs/verification.md#property-based-testing--t) names `fast-check` for pure frontend logic. |
| P12 | The bundle check reads Vite's `dist/.vite/manifest.json`, walks the static imports of the entry chunk (what `/scenes` loads), fails if any module path contains `three` or `@react-three`, and sums their gzipped sizes with Node's `zlib`. | Spec AC 13, NFR-01. |
| P13 | The gate is `scripts/gate.mjs`: every stage runs even after one fails, and the summary lists failures **and** skips by name, as the backend gate does. The e2e stage is SKIPPED locally when the backend's environment cannot be started, and is never skipped in CI. | Spec AC 1, AC 5, AC 15; `backend/gate.sh` convention. |
| P14 | The frontend and the backend share one branch, so a backend commit that changes `openapi.json` makes `check:api` fail at once; the frontend regenerates in its own `contract:` commit. The frontend never edits anything under `backend/`. | Spec "Out"; Process 3 rule 11. |
| P15 | Markdown prose is rendered by `react-markdown` with its defaults and **no** `rehype-raw`; links in prose open without `target=_blank`. | Spec FR-TOOL-05, AC 10. |

---

## Files to touch

Paths are relative to the repository root. `frontend/src/` is abbreviated `src/`.

| Path | What changes |
|---|---|
| `frontend/.gitignore` | New. `playwright-report/`, `test-results/`, `.vite/`. (`node_modules/` and `dist/` are already ignored at the root, which this plan does not edit.) |
| `.github/workflows/frontend.yml` | New. One job running `npm run gate` on Ubuntu with Node 24 and `uv`; triggered by `frontend/**`, `backend/openapi.json`, `backend/app/**`, `backend/tests/fixtures/**` and the workflow itself. |
| `frontend/package.json`, `frontend/package-lock.json`, `frontend/.npmrc`, `frontend/.nvmrc` | New. Dependencies, exact pins, the scripts of FR-TOOL-07. |
| `frontend/README.md` | New. How to install, run against a local backend, regenerate the client, and run the gate. |
| `frontend/index.html`, `frontend/vite.config.ts` | New. Entry page (`lang="es"`), dev proxy, manifest on, Vitest config. |
| `frontend/tsconfig.json`, `frontend/tsconfig.app.json`, `frontend/tsconfig.node.json` | New. `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`. |
| `frontend/eslint.config.js` | New. The rules of FR-STATIC-01/02 and P5. |
| `frontend/lint-fixtures/*.tsx` | New. One violating file per boundary rule (P6). |
| `frontend/scripts/openapi.mjs`, `frontend/scripts/check-api.mjs` | New. Generation and drift check (P7). |
| `frontend/scripts/check-bundle.mjs` | New. P12. |
| `frontend/scripts/gate.mjs` | New. P13. |
| `src/main.tsx` | New. Mounts `app/`. |
| `src/app/App.tsx`, `src/app/routes.tsx`, `src/app/providers.tsx`, `src/app/Layout.tsx`, `src/app/HealthBadge.tsx`, `src/app/NotFoundPage.tsx`, `src/app/api.ts` | New. FR-SHELL-01…04. |
| `src/app/HealthBadge.test.tsx` | New. AC 8. |
| `src/shared/types/openapi.d.ts` | New, generated. |
| `src/shared/api/client.ts`, `src/shared/api/errors.ts`, `src/shared/api/sse.ts`, `src/shared/api/index.ts` | New. FR-API-02, -04, -06. |
| `src/shared/api/contract.test.ts`, `src/shared/api/sse.test.ts` | New. AC 4, AC 7. |
| `src/shared/ui/*.tsx` | New. Layout, heading, prose container, status badge, error panel, skeleton — only these. |
| `src/shared/three/LazyCanvas.tsx`, `src/shared/three/EmptyScene.tsx` | New. FR-3D-01. |
| `src/shared/test/setup.ts`, `src/shared/test/server.ts`, `src/shared/test/render.tsx` | New. Vitest setup, typed MSW server (P4), render with providers. |
| `src/shared/lint.test.ts` | New. AC 3. |
| `src/reader/api.ts`, `src/reader/toc.ts`, `src/reader/useToc.ts`, `src/reader/useScene.ts`, `src/reader/TocPage.tsx`, `src/reader/ScenePage.tsx`, `src/reader/routes.tsx` | New. FR-READ-01…04. |
| `src/reader/toc.test.ts`, `src/reader/TocPage.test.tsx`, `src/reader/ScenePage.test.tsx` | New. AC 9, AC 10. |
| `src/graph3d/Graph3dPage.tsx`, `src/graph3d/routes.tsx` | New. FR-3D-02. |
| `frontend/playwright.config.ts`, `frontend/e2e/global-setup.ts`, `frontend/e2e/backend.ts` | New. P8–P10. |
| `frontend/e2e/api-error.spec.ts`, `frontend/e2e/reader.spec.ts`, `frontend/e2e/a11y.spec.ts`, `frontend/e2e/graph3d.spec.ts` | New. AC 6, 11, 12, 14. |
| `specs/002-frontend-foundation/002-frontend-foundation-plan.md` | This file; status moves to `done` when the spec closes. |

Nothing under `backend/`, `docs/` or any other spec is touched.

---

## Steps

Each step is one commit and leaves `npm run lint`, `npm run typecheck` and `npm test` green
from step 2 onward.

1. **Scaffold.** `package.json` with exact pins (P1), `.npmrc`, `.nvmrc`, tsconfigs with the
   strict flags, `vite.config.ts`, `index.html`, a `main.tsx` rendering an empty `App`, the
   `frontend/.gitignore` and `frontend/README.md`. `npm run typecheck` passes. —
   *AC 1 (partial)*. `frontend:`
2. **Lint and boundaries.** `eslint.config.js` with FR-STATIC-01 and P5; one fixture per
   boundary rule under `lint-fixtures/`; `src/shared/lint.test.ts` asserting each fixture
   raises its rule id and that `src/` is clean. — *AC 2, AC 3*. `frontend:`
3. **Contract pipeline.** `scripts/openapi.mjs` (P7), `gen:api` and `check:api`; generated
   `src/shared/types/openapi.d.ts`; `client.ts` on `openapi-fetch` with base URL `/api`;
   `errors.ts` with `ApiError` and its parser; `contract.test.ts` running the generator on a
   one-field mutation of the schema and asserting a diff. — *AC 4; AC 6 (parser)*.
   `contract:`
4. **SSE wrapper.** `sse.ts` with `streamEvents<T>` over `fetch` + `ReadableStream`, frame
   parsing, per-frame validation and `AbortSignal`; `sse.test.ts` over a hand-built stream.
   — *AC 7*. `frontend:`
5. **Test harness.** Vitest in `vite.config.ts` (jsdom), `src/shared/test/` with the typed
   MSW server (P4) and `render.tsx`. A smoke test proves a typed handler is served. — *AC 8–10
   (prerequisite)*. `frontend:`
6. **App shell and primitives.** `app/` (router, providers with the query client and error
   boundary, layout, not-found), `HealthBadge` polling `/health` at most every 30 s,
   `src/shared/ui/` primitives, Spanish UI strings. `HealthBadge.test.tsx`. — *AC 8*.
   `frontend:`
7. **Reader slice.** `toc.ts` (`buildToc`, P11) with example and `fast-check` tests;
   `reader/api.ts` over the client; `useToc`, `useScene`; `TocPage` and `ScenePage` with their
   four states each; prev/next; Markdown without raw HTML (P15). Component tests for every
   state, the chapter-order case, the "Sin capítulo" case, the draft-`404` empty state, the
   scene-`404` not-found state and the script/`onerror` injection case. — *AC 9, AC 10*.
   `frontend:`
8. **three.js readiness.** `LazyCanvas` behind `React.lazy` + `Suspense` with a text
   fallback; `EmptyScene` (camera, light, orbit controls); `/graph3d` route. — *AC 13, AC 14
   (prerequisite)*. `frontend:`
9. **End-to-end harness and runs.** `playwright.config.ts` with two `webServer`s (Vite dev
   server and the backend on 8765, P8–P10), `global-setup.ts` copying the fixture; specs for
   the `404` body (AC 6), the reader walk through `002` → `003` and the `001` empty state
   (AC 11), axe on each route (AC 12), and the lazy three.js chunk on `/graph3d` only
   (AC 14). — *AC 6, AC 11, AC 12, AC 14*. `frontend:`
10. **Bundle check.** `build.manifest: true`; `scripts/check-bundle.mjs` (P12) with the
    250 KB budget. — *AC 13*. `frontend:`
11. **Gate.** `scripts/gate.mjs` (P13): lint → typecheck → test → check:api → build →
    check:bundle → suppression grep → `npm audit --omit=dev --audit-level=high` → e2e, with a
    failures-and-skips summary. — *AC 1, AC 15*. `frontend:`
12. **CI.** `.github/workflows/frontend.yml` running `npm ci`, Playwright browser install,
    `uv sync --locked` in `backend/`, then `npm run gate`, with the path filters listed above.
    — *AC 5*. `chore:`

After step 12: the PR that merges `spec/001-backend` into `main` also carries this spec; its
description lists, for spec 002, each criterion, its
letter and its verification, and the review note for AC 16. After merge, close the spec and
move this plan to `done` in one `spec(002):` commit.

---

## Verification mapping

| AC | Letter | Satisfied by | Lives in |
|---|---|---|---|
| 1 | A | `tsc --noEmit` with the strict flags; gate's grep for `any`, `@ts-ignore` and `eslint-disable` without a `spec 002` comment | `frontend/tsconfig.app.json`, `frontend/scripts/gate.mjs` |
| 2 | A | `eslint .` with zero findings | `frontend/eslint.config.js` |
| 3 | A | One fixture per rule, each asserting its rule id; `src/` clean | `frontend/lint-fixtures/`, `src/shared/lint.test.ts` |
| 4 | T | `check:api` in the gate; generator run on a mutated schema asserts a diff | `frontend/scripts/check-api.mjs`, `src/shared/api/contract.test.ts` |
| 5 | I | Review of the path filters and the single `npm run gate` step | `.github/workflows/frontend.yml` |
| 6 | T | Playwright request to `/api/scenes/999` parsed by `ApiError` | `frontend/e2e/api-error.spec.ts` |
| 7 | T | Frames, validation failure, abort | `src/shared/api/sse.test.ts` |
| 8 | T | Mocked `/health` ok and network error | `src/app/HealthBadge.test.tsx` |
| 9 | T | Four states; chapter order against shuffled ids; "Sin capítulo"; `fast-check` properties of `buildToc` | `src/reader/TocPage.test.tsx`, `src/reader/toc.test.ts` |
| 10 | T | Markdown rendered; draft `404` → empty; scene `404` → not-found; injected markup stays text | `src/reader/ScenePage.test.tsx` |
| 11 | D | Walk `/scenes` → `002` → next `003`; open `001` → empty state, against the real backend | `frontend/e2e/reader.spec.ts` |
| 12 | T | `@axe-core/playwright` on `/scenes`, `/scenes/002`, `/graph3d`, an unknown route | `frontend/e2e/a11y.spec.ts` |
| 13 | T | Manifest walk: no three.js in the entry graph; gzipped ≤ 250 KB | `frontend/scripts/check-bundle.mjs` |
| 14 | D | Canvas mounted on `/graph3d`; three.js chunk requested there and not on `/scenes` | `frontend/e2e/graph3d.spec.ts` |
| 15 | A | `npm audit --omit=dev --audit-level=high` in the gate | `frontend/scripts/gate.mjs` |
| 16 | I | Reviewer's note in the PR | PR description |

---

## Risks and stop conditions

The agent stops, sets this plan back to `draft` and reopens Process 0 if any of these happens.

- **A change to `backend/` looks necessary** — CORS, a missing route, a startup that needs a
  rebuild, an error body that is not the IF-07 shape on `GET /scenes/999`. `backend/` is out of
  scope; the finding goes to spec 001's Open questions, not into this branch.
- **The fixture cannot drive a criterion** — e.g. `structure/chapters.yaml` or the drafts
  change on `spec/001-backend` so that `002`, `003` or the draftless `001` no longer exist.
  AC 11 names them; a different walk is a spec clarification.
- **The 250 KB budget or the three.js split cannot be met** with the stack as specified.
  The budget is in the spec (NFR-01); it is revised there, not relaxed in the script.
- **A boundary rule cannot be expressed** with the tools of P5 without an `eslint-disable` in
  `src/`. Stop rather than suppress.
- **A dependency has a high-severity advisory with no fixed version** (AC 15). Options go
  to the user: pin an alternative, or register a **U** with a reason.
- **The backend cannot be started locally for e2e** (no `uv`, no `backend/.venv`). The gate
  reports e2e as SKIPPED (P13), CI still runs it, and the PR says which criteria were shown
  only in CI.
- **The backend session changes `openapi.json` in a way that breaks a screen** (a renamed
  field in `Scene`, `Draft` or `Chapter`). Regenerate and fix in a `contract:` commit if the
  fix is mechanical; if it changes what a screen shows, reopen the spec.
- **The other session's uncommitted changes break the frontend's e2e run** (the backend in
  the working tree does not start, or answers differently). Wait for its commit rather than
  touching `backend/`; report the affected criteria as not yet demonstrated.
- **Anything not in "Files to touch" is needed.** The plan is wrong; revise it first.
