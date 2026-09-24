---
spec: 002                 # the approved spec this plan implements
status: approved          # draft · approved · done
---

Implementation plan for [`002-frontend-foundation.md`](./002-frontend-foundation.md).
The spec says *what* and *why*; this file says *how* and *in what order*. Anything not
listed under "Files to touch" is out of scope; a file that turns out to be needed means this
plan is wrong and goes back to `draft`.

> **Approved by the user on 2026-09-23**, together with the re-approved spec. This revision
> follows the spec's round-3 alignment with `docs/` (the SSE step removed, `health/` and
> `scenes/` as features, no `shared/three/`, test utilities outside `src/`, a per-chunk bundle
> report, 18 criteria).

Branch: **`spec/001-backend`**, in the same folder where the backend session is working at
the same time. This departs from Process 3 step 3 (`spec/NNN-short-slug`) at the user's
explicit request (2026-09-23; spec Decision 1), so the MVP grows on one branch; by the same
decision spec 002 rides on the pull request that merges `spec/001-backend` (rule 18).

**Commit conventions** (Process 3 rules 14–17):

- Prefixes are the areas of rule 17: `frontend:` and `contract:`. Every step is one commit,
  small enough to review alone.
- Each commit body says `Implements spec 002, AC …`, carries the gate's one-line summary
  (the full gate output goes in the PR description, rule 14), and ends with the session's
  `Co-Authored-By` trailer.
- Every test added carries `// spec 002 / AC n` (rule 16), and is shown to fail without the
  change it verifies (rule 15): the commit body says how — a planted fixture or report, a
  stubbed component, or the test run before the implementation file existed.

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
| P5 | Boundary rules by mechanism: `eslint-plugin-boundaries` for (a)–(c) and (g) of FR-STATIC-02, with elements `app`, `shared`, and `feature` (any other top-level folder of `src/`), and a feature's `index.ts` as its only entry point for both other features and `app/`; `import-x/no-cycle` for (d); `no-restricted-imports` for `openapi-fetch`, `three` and `@react-three/*`, and `no-restricted-globals` for `fetch` and `XMLHttpRequest`, for (e)–(f), each with an override that re-allows it only in `src/shared/api/` or `src/graph3d/`. | Spec FR-STATIC-02. `boundaries` handles imports between elements, not globals, packages or cycles. |
| P6 | Lint fixtures are files under `frontend/lint-fixtures/`, excluded from the normal lint run. The AC 3 test reads each one and lints its text with the project config at a **virtual path** under `src/` (ESLint `lintText` with `filePath`), taken from a header comment in the fixture. Type-aware rules are off for that one test config. | Spec AC 3. Fixtures never enter `src/`, so they are never built, typechecked or shipped. |
| P7 | `gen:api` and `check:api` use the `openapi-typescript` **Node API** in one module, `scripts/openapi.mjs`, so both produce the file byte for byte the same way. The output is formatted by the generator only; Prettier is not in the stack. | Spec FR-API-01, FR-API-03. |
| P8 | The dev proxy target defaults to `http://127.0.0.1:8000` (the backend README's `uvicorn` default) and reads `VITE_BACKEND_URL`. Playwright starts its own backend on port **8765**, so a developer's running backend is never the one under test. | Spec FR-API-05, NFR-05. |
| P9 | Playwright's global setup copies `backend/tests/fixtures/repo/` into a temporary directory and starts the backend there with `STORY_ROOT` and `STORY_INDEX` pointing into it. `EMBED_OFFLINE` stays **unset**: with it set, a missing model is a startup error (FR-EMB-03), and online no model is loaded until a rebuild, which no test here triggers. | Spec NFR-05; `backend/app/main.py`. |
| P10 | The backend is started with `uv run uvicorn app.main:app` when `uv` is on PATH (CI), else with `backend/.venv`'s Python (`-m uvicorn`). `uv` is not on this machine's bash PATH. | Local and CI both work, with no new tool. |
| P11 | The table-of-contents logic is a **pure function**, `buildToc(chapters, sceneIds)` in `scenes/toc.ts`, tested with examples and with `fast-check` properties (every scene appears exactly once; chapter order is preserved; unassigned scenes come last); `neighbours(toc, id)` derives previous/next from the same flattened order, with the property that they are inverse neighbours. | Spec FR-SCN-01/03/04. |
| P12 | A small Vite plugin in `vite.config.ts` writes `dist/bundle-report.json` in `generateBundle`: for every chunk, its file, whether it is the entry, its static imports and its `chunk.modules` keys — the module list the Vite manifest does not carry. `check-bundle.mjs` walks the entry chunk's static-import graph (what `/scenes` loads), fails if any module id contains `/three/` or `@react-three`, and sums the gzipped sizes of those files with Node's `zlib`. `test/check-bundle.test.ts` runs the check on a planted report with a three.js module in the entry chunk and expects failure. | Spec AC 12, NFR-01; AGENTS.md rule 15. |
| P13 | The gate is `scripts/gate.mjs`, with a stage that fails on any range (`^`, `~`, `*`, `x`) in `package.json` (AC 14): every stage runs even after one fails, and the summary lists failures **and** skips by name, as the backend gate does. The e2e stage is SKIPPED locally when the backend's environment cannot be started, and is never skipped in CI. | Spec AC 1, AC 5, AC 14; `backend/gate.sh` convention. |
| P14 | "The same change" of Process 3 rule 11 is the same pull request (spec Decision R3-10, confirmed by the user on 2026-09-23). The frontend regenerates in a `contract:` commit right after a backend commit that changes `openapi.json`; until then `check:api` and the frontend workflow are red. The frontend never edits anything under `backend/`. | Spec FR-API-03, R3-10. |
| P15 | Markdown prose is rendered by `react-markdown` with its defaults and **no** `rehype-raw`; links in prose open without `target=_blank`. | Spec FR-TOOL-05, AC 9. |
| P16 | Initial placement of UI components (FR-UI-01): `shared/ui/` gets `Heading` (used by `app/`'s not-found page, `scenes/`, `graph3d/`) and `ErrorPanel` (used by `app/`'s error boundary, `scenes/`, `graph3d/`); `app/` keeps `Layout`; `scenes/` keeps `Prose` and `Skeleton`; `health/` keeps `StatusBadge`. If actual use differs when the code is written, the component moves to match use, and the PR's AC 15 note says so. | Spec FR-UI-01; [placement rule](../../docs/architecture.md#code-architecture--package-by-feature). |
| P17 | Each feature's public surface is its `index.ts`, and it exports only what `app/` wires: `ScenesRoutes`, `HealthBadge`, `Graph3dRoute`. | Spec FR-SHELL-02. |

---

## Files to touch

Paths are relative to the repository root. `frontend/src/` is abbreviated `src/`.

| Path | What changes |
|---|---|
| `.github/workflows/frontend.yml` | New. One job running `npm run gate` on Ubuntu with Node 24 and `uv`; triggered by `frontend/**`, `backend/openapi.json`, `backend/app/**`, `backend/tests/fixtures/**` and the workflow itself. |
| `frontend/package.json`, `frontend/package-lock.json`, `frontend/.npmrc`, `frontend/.nvmrc`, `frontend/.gitignore` | New. Dependencies, exact pins, the scripts of FR-TOOL-07; ignores for `playwright-report/`, `test-results/`, `.vite/` (`node_modules/` and `dist/` are already ignored at the root, which this plan does not edit). |
| `frontend/README.md` | New. How to install, run against a local backend, regenerate the client, and run the gate. |
| `frontend/index.html`, `frontend/vite.config.ts` | New. Entry page (`lang="es"`), dev proxy, the bundle-report plugin (P12), Vitest config. |
| `frontend/tsconfig.json`, `frontend/tsconfig.app.json`, `frontend/tsconfig.node.json` | New. `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes` in both projects. `tsconfig.app.json` (DOM) includes `src/` **and `test/`**; `tsconfig.node.json` includes `vite.config.ts`, `playwright.config.ts`, `e2e/` and `scripts/` (with `allowJs` + `checkJs` for the `.mjs` scripts). `tsconfig.json` references both, and `npm run typecheck` is `tsc -b` (AC 1, AC 17). |
| `frontend/eslint.config.js` | New. The rules of FR-STATIC-01/02 and P5. |
| `frontend/lint-fixtures/*.tsx` | New. One violating file per boundary rule (a)–(g), and one accepted import through `index.ts` (P6). |
| `frontend/scripts/openapi.mjs`, `frontend/scripts/check-api.mjs` | New. Generation and drift check (P7). |
| `frontend/scripts/check-bundle.mjs` | New. P12. |
| `frontend/scripts/gate.mjs` | New. P13. |
| `frontend/test/setup.ts`, `frontend/test/server.ts`, `frontend/test/render.tsx` | New. Vitest setup, typed MSW server (P4), render with providers (NFR-06). |
| `frontend/test/server.test.ts` | New. The harness smoke test, and the planted wrongly-typed handler of AC 17. |
| `frontend/test/lint.test.ts` | New. AC 3. |
| `frontend/test/check-bundle.test.ts` | New. The planted-report case of AC 12 (P12). |
| `src/main.tsx` | New. Mounts `app/`. |
| `src/app/App.tsx`, `src/app/routes.tsx`, `src/app/providers.tsx`, `src/app/Layout.tsx`, `src/app/NotFoundPage.tsx` | New. FR-SHELL-01…04. No API call. |
| `src/app/routes.test.tsx` | New. AC 16. |
| `src/shared/types/openapi.d.ts` | New, generated. |
| `src/shared/api/client.ts`, `src/shared/api/errors.ts`, `src/shared/api/index.ts` | New. FR-API-02, FR-API-04 (the three error cases). |
| `src/shared/api/contract.test.ts` | New. AC 4. |
| `src/shared/ui/Heading.tsx`, `src/shared/ui/ErrorPanel.tsx`, `src/shared/ui/index.ts` | New. P16. |
| `src/health/index.ts`, `src/health/api.ts`, `src/health/HealthBadge.tsx`, `src/health/StatusBadge.tsx`, `src/health/HealthBadge.test.tsx` | New. FR-HLT-01; AC 7. |
| `src/scenes/index.ts`, `src/scenes/api.ts`, `src/scenes/toc.ts`, `src/scenes/useToc.ts`, `src/scenes/useScene.ts`, `src/scenes/TocPage.tsx`, `src/scenes/ScenePage.tsx`, `src/scenes/Prose.tsx`, `src/scenes/Skeleton.tsx`, `src/scenes/routes.tsx` | New. FR-SCN-01…06. |
| `src/scenes/toc.test.ts`, `src/scenes/TocPage.test.tsx`, `src/scenes/ScenePage.test.tsx` | New. AC 8, AC 9. |
| `src/graph3d/index.ts`, `src/graph3d/Graph3dPage.tsx`, `src/graph3d/LazyCanvas.tsx`, `src/graph3d/EmptyScene.tsx` | New. FR-3D-01/02. |
| `src/graph3d/Graph3dPage.test.tsx` | New. AC 18. |
| `frontend/playwright.config.ts`, `frontend/e2e/global-setup.ts`, `frontend/e2e/backend.ts` | New. P8–P10. |
| `frontend/e2e/api-error.spec.ts`, `frontend/e2e/scenes.spec.ts`, `frontend/e2e/a11y.spec.ts`, `frontend/e2e/graph3d.spec.ts` | New. AC 6, 10, 11, 13. |
| `specs/002-frontend-foundation/002-frontend-foundation-plan.md` | This file; status moves to `done` when the spec closes. |

Nothing under `backend/`, `docs/`, `src/shared/three/`, `src/shared/lib/` or any other spec
is created or touched.

---

## Steps

Each step is one commit and leaves `npm run lint`, `npm run typecheck` and `npm test` green
from step 2 onward.

1. **Scaffold.** `package.json` with exact pins (P1), `.npmrc`, `.nvmrc`, `frontend/.gitignore`,
   tsconfigs with the strict flags, `vite.config.ts`, `index.html`, a `main.tsx` rendering an
   empty `App`, and `frontend/README.md`. `npm run typecheck` passes. — *AC 1 (partial)*.
   `frontend:`
2. **Lint and boundaries.** `eslint.config.js` with FR-STATIC-01 and P5; one fixture per rule
   (a)–(g) and one accepted fixture under `lint-fixtures/`; `test/lint.test.ts` asserting each
   fixture raises its rule id, the accepted one raises none, and `src/` is clean. — *AC 2,
   AC 3*. `frontend:`
3. **Contract pipeline.** `scripts/openapi.mjs` (P7), `gen:api` and `check:api`; generated
   `src/shared/types/openapi.d.ts`; `client.ts` on `openapi-fetch` with base URL `/api`;
   `errors.ts` with `ApiError` and its three-case parser (IF-07, `HTTPValidationError`, unknown); `contract.test.ts` running the generator on a
   one-field mutation of the schema and asserting a diff. — *AC 4; AC 6 (parser)*.
   `contract:`
4. **Test harness.** Vitest in `vite.config.ts` (jsdom, setup from `frontend/test/`), the
   typed MSW server (P4) and `render.tsx`. `test/server.test.ts` proves a typed handler is
   served, and holds the planted wrongly-typed handler under `@ts-expect-error`. — *AC 17;
   AC 7–9 (prerequisite)*. `frontend:`
5. **App shell and `health/`.** `app/` (router, providers with the query client and error
   boundary, layout, not-found), `shared/ui/` `Heading` and `ErrorPanel` (P16), the `health/`
   feature with its `api.ts`, badge with its three states polling `/health` at most every
   30 s, and `HealthBadge.test.tsx` (network error, non-JSON `502`, fake timers for the interval); `app/` places the badge
   through `health/index.ts` (P17); `routes.test.tsx` for the not-found page inside the layout
   and the `/` redirect. Spanish UI strings. — *AC 7, AC 16*. `frontend:`
6. **`scenes/` feature.** `toc.ts` (`buildToc`, P11) with example and `fast-check` tests;
   `scenes/api.ts` over the client for `/structure/chapters`, `/scenes`, `/scenes/{id}` and
   `/manuscript/{id}`; `useToc`, `useScene`; `TocPage` and `ScenePage` with their four states
   each; prev/next; the scene-id pattern check before any request (FR-SCN-06); `Prose`
   without raw HTML (P15); `Skeleton`. Component tests for every state, the chapter-order
   case, the "Sin capítulo" case, the draft-`404` empty state, the scene-`404` not-found state,
   `/scenes/abc` with no request issued, a non-JSON `500` in the error panel, and the
   script/`onerror` injection case;
   `fast-check` properties for order and prev/next. — *AC 8, AC 9*.
   `frontend:`
7. **`graph3d/` feature.** `LazyCanvas` behind `React.lazy` + `Suspense` with a text
   fallback and the error panel when the chunk or WebGL fails, `EmptyScene` (camera, light,
   orbit controls), `Graph3dPage`, wired by `app/` through `graph3d/index.ts`;
   `Graph3dPage.test.tsx` with the lazy import mocked to reject and with WebGL detection
   mocked to fail. — *AC 18; AC 12, AC 13
   (prerequisite)*. `frontend:`
8. **End-to-end harness and runs.** `playwright.config.ts` with two `webServer`s (Vite dev
   server and the backend on 8765, P8–P10), `global-setup.ts` copying the fixture; specs for
   the `404` body (AC 6), the walk through `002` → `003` and the `001` empty state (AC 10),
   axe on each route (AC 11), and the lazy three.js chunk on `/graph3d` only (AC 13). —
   *AC 6, AC 10, AC 11, AC 13*. `frontend:`
9. **Bundle check.** The bundle-report plugin, `scripts/check-bundle.mjs` (P12) with the
   250 KB budget, and `test/check-bundle.test.ts` with the planted report. — *AC 12*.
   `frontend:`
10. **Gate.** `scripts/gate.mjs` (P13): lint → typecheck → test → check:api → build →
    check:bundle → suppression grep → exact-version check → `npm audit --omit=dev
    --audit-level=high` → e2e, with a failures-and-skips summary. — *AC 1, AC 14*. `frontend:`
11. **CI.** `.github/workflows/frontend.yml` running `npm ci`, Playwright browser install,
    `uv sync --locked` in `backend/`, then `npm run gate`, with the path filters listed above.
    — *AC 5*. `frontend:`

After step 11: the PR that merges `spec/001-backend` into `main` also carries this spec; its
description lists, for spec 002, each criterion, its letter and its verification, and the
review note for AC 15, and the full gate output (rule 14). After merge, close the spec and move this plan to `done` in one
`spec(002):` commit.

---

## Verification mapping

| AC | Letter | Satisfied by | Lives in |
|---|---|---|---|
| 1 | A | `tsc -b` over both projects with the strict flags; gate's grep for `any`, `@ts-ignore` and `eslint-disable` without a `spec 002` comment | `frontend/tsconfig.app.json`, `frontend/tsconfig.node.json`, `frontend/scripts/gate.mjs` |
| 2 | A | `eslint .` with zero findings | `frontend/eslint.config.js` |
| 3 | T | One fixture per rule (a)–(g), each asserting its rule id; one accepted `index.ts` import; `src/` clean | `frontend/lint-fixtures/`, `frontend/test/lint.test.ts` |
| 4 | T | `check:api` in the gate; generator run on a mutated schema asserts a diff | `frontend/scripts/check-api.mjs`, `src/shared/api/contract.test.ts` |
| 5 | I | Review of the path filters and the single `npm run gate` step | `.github/workflows/frontend.yml` |
| 6 | T | Playwright request to `/api/scenes/999` parsed by `ApiError` | `frontend/e2e/api-error.spec.ts` |
| 7 | T | Loading, mocked `/health` ok, network error, non-JSON `502`; fake timers for the 30 s interval | `src/health/HealthBadge.test.tsx` |
| 8 | T | Four states; chapter order against shuffled ids; "Sin capítulo"; `fast-check` properties of `buildToc` and prev/next | `src/scenes/TocPage.test.tsx`, `src/scenes/toc.test.ts` |
| 9 | T | Markdown rendered; draft `404` → empty; scene `404` → not-found; `/scenes/abc` → not-found with no request; non-JSON `500` → generic message and status; injected markup stays text | `src/scenes/ScenePage.test.tsx` |
| 10 | D | Walk `/scenes` → `002` → next `003`; open `001` → empty state, against the real backend | `frontend/e2e/scenes.spec.ts` |
| 11 | T | `@axe-core/playwright` on `/scenes`, `/scenes/002`, `/graph3d`, an unknown route | `frontend/e2e/a11y.spec.ts` |
| 12 | T | Per-chunk module report: no three.js in the entry graph; gzipped ≤ 250 KB; planted report fails | `frontend/scripts/check-bundle.mjs`, `frontend/test/check-bundle.test.ts` |
| 13 | D | Canvas mounted on `/graph3d`; three.js chunk requested there and not on `/scenes` | `frontend/e2e/graph3d.spec.ts` |
| 14 | A | `npm audit --omit=dev --audit-level=high` and the exact-version stage in the gate | `frontend/scripts/gate.mjs` |
| 15 | I | Reviewer's note in the PR, including the `shared/ui/` placement check (P16), the four states of every screen, and the language split | PR description |
| 16 | T | Unknown route inside the layout; `/` → `/scenes` | `src/app/routes.test.tsx` |
| 17 | A | `tsc -b` rejects the planted handler, because `test/` is in `tsconfig.app.json`; removing the `@ts-expect-error` line makes typecheck fail (rule 15) | `frontend/test/server.test.ts`, `frontend/tsconfig.app.json` |
| 18 | T | Lazy import mocked to reject, and WebGL detection mocked to fail → error panel | `src/graph3d/Graph3dPage.test.tsx` |

---

## Risks and stop conditions

The agent stops, sets this plan back to `draft` and reopens Process 0 if any of these happens.

- **A change to `backend/` looks necessary** — CORS, a missing route, a startup that needs a
  rebuild, an error body that is not the IF-07 shape on `GET /scenes/999`. `backend/` is out of
  scope; the finding goes to spec 001's Open questions, not into this plan.
- **The fixture cannot drive a criterion** — e.g. `structure/chapters.yaml` or the drafts
  change so that `002`, `003` or the draftless `001` no longer exist. AC 10 names them; a
  different walk is a spec clarification.
- **The 250 KB budget or the three.js split cannot be met** with the stack as specified.
  The budget is in the spec (NFR-01); it is revised there, not relaxed in the script.
- **A boundary rule cannot be expressed** with the tools of P5 without an `eslint-disable` in
  `src/`. Stop rather than suppress.
- **A component would need to enter `shared/` with one user**, or a second feature needs
  something that lives in another feature. The placement rule decides; if it means creating
  `shared/lib/` or `shared/three/`, the plan's file list changes first.
- **A dependency has a high-severity advisory with no fixed version** (AC 14). Options go
  to the user: pin an alternative, or register a **U** with a reason.
- **The backend cannot be started locally for e2e** (no `uv`, no `backend/.venv`). The gate
  reports e2e as SKIPPED (P13), CI still runs it, and the PR says which criteria were shown
  only in CI.
- **The backend session changes `openapi.json` in a way that breaks a screen** (a renamed
  field in `Scene`, `Draft` or `Chapter`). Regenerate and fix in a `contract:` commit if the
  fix is mechanical (P14); if it changes what a screen shows, reopen the spec.
- **The other session's uncommitted changes break the e2e run** (the backend in the working
  tree does not start, or answers differently). Wait for its commit rather than touching
  `backend/`; report the affected criteria as not yet demonstrated.
- **Anything not in "Files to touch" is needed.** The plan is wrong; revise it first.

---

## Clarifications recorded during implementation (2026-09-24)

Added at the user's request after steps 1-11 were done. None changes the spec's scope or
criteria; each is also in the body of the commit named.

| # | What differs from the text above | Why | Commit |
|---|---|---|---|
| C1 | TypeScript is 5.9.3, not the newest 7.0.2; ESLint is 9.39.5, not 10.11.0 (P1). | typescript-eslint needs TS < 6.1 and openapi-typescript needs TS 5.x; eslint-plugin-jsx-a11y supports ESLint up to 9. ESLint 9 is out of upstream support; it is a dev-only tool and `npm audit` reports nothing. Revisit when jsx-a11y supports ESLint 10. | `0ebd2a1` |
| C2 | `eslint.config.js` is not in the Node type-check project. | Two ESLint plugins ship no types; the plan never listed the file there. | `793d528` |
| C3 | `lint-fixtures/` is a miniature real `src/` tree (`.ts` files, its own `tsconfig.app.json` and `README.md`), not virtual paths (P6). | The boundary and cycle rules resolve imports on disk; virtual paths cannot resolve. | `793d528` |
| C4 | `src/shared/api/errors.test.ts` exists (not in the file list). | Unit tests of the three-case parser (FR-API-04); the AC 6 e2e test covers only the real 404. | `5f8b11f` |
| C5 | `check:api` regenerates in memory, not into a temp file (FR-API-03). | Same comparison, fewer files; ignores CRLF/LF. | `5f8b11f` |
| C6 | The client looks up `globalThis.fetch` per call and uses an absolute `<origin>/api` base. | openapi-fetch captured `fetch` at import, before MSW patches it; Node's fetch under Vitest does not resolve relative URLs. Same behaviour in the browser. | `d664812` |
| C7 | The graph3d test seam is `scene` (a lazy component), not `load` (a loader). | Creating a lazy component from a loader during render is rejected by react-hooks' static-components rule. | `510cd8c` |
| C8 | A 404 on `GET /structure/chapters` is shown as "no chapters yet", not as an error panel. | A book without `chapters.yaml` is not a failure, and a retry could never fix it. Accepted by the user on 2026-09-24. | `98aee2a` |
| C9 | No `e2e/global-setup.ts`; the fixture copy lives in `e2e/backend.ts`. | Playwright starts its `webServer`s before global setup, so the backend command itself must prepare its story root. | `289a1ba` |
| C10 | Nav links and table-of-contents links carry an inline 24 px target. | AC 11 found WCAG 2.2 target-size violations; there is no stylesheet in the plan's file list. | `289a1ba` |

## AC 15 review note (2026-09-24)

Delegated to the agent by the user; the agent also wrote much of the code, so a human may
want to re-read it.

- **Feature folders are flat and self-contained:** `app/`, `health/`, `scenes/`, `graph3d/`
  have no subfolders; each feature exposes only its `index.ts` (`HealthBadge`,
  `ScenesRoutes`, `Graph3dRoute`), and the boundary rules (a)-(g) enforce the rest.
- **`app/` only composes:** router, providers, layout, not-found; no API call.
- **`shared/ui/` placement:** `Heading` is used by `app/` (not-found), `scenes/` and
  `graph3d/`; `ErrorPanel` by `app/` (error boundary), `scenes/` and `graph3d/`. The
  single-user components stay in their feature: `StatusBadge` (health), `Prose` and
  `Skeleton` (scenes), `LazyCanvas` and `EmptyScene` (graph3d). No `shared/three/` and no
  `shared/lib/`.
- **Four states per screen:** `/scenes` and `/scenes/:id` specify and test loading, empty,
  error and loaded; the health badge has loading, error and loaded (empty does not apply);
  `/graph3d` has loading, error (chunk or WebGL) and loaded (empty does not apply); the
  not-found page is static.
- **Language:** UI strings in Spanish; identifiers, comments and tests in English.
