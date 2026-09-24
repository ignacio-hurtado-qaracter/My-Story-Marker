# frontend

The React + three.js client of My Story Marker. It reaches the backend only through the
typed OpenAPI client in `src/shared/api/` and never touches the harness stores
([architecture](../docs/architecture.md#frontend--package-by-feature-not-fsd)).

Built under [`specs/002-frontend-foundation/002-frontend-foundation.md`](../specs/002-frontend-foundation/002-frontend-foundation.md),
to [its implementation plan](../specs/002-frontend-foundation/002-frontend-foundation-plan.md).

## Running it

Node 24 (see `.nvmrc`) and npm. Every dependency is pinned to an exact version.

```sh
npm ci                 # install from package-lock.json
npm run dev            # Vite on http://localhost:5173
```

The dev server proxies `/api/*` to the backend, with the prefix stripped, so the backend needs
no CORS configuration. The target is `http://127.0.0.1:8000` (the backend's `uvicorn`
default); set `VITE_BACKEND_URL` to point elsewhere. Start the backend as its
[README](../backend/README.md) says.

## Reading a novel (spec 014)

The web reader is served by the Vite dev server (or `vite preview` after `npm run build`),
whose `/api` proxy reaches the backend; FastAPI does not serve `dist/`. From the repository
root, in two terminals:

```sh
# 1. backend: the story bible at HARNESS_DB (default data/harness.sqlite)
cd backend
uv run python -m app.reader.dev_seed          # optional: a 3-chapter, 2-version demo novel "demo-faro"
STORY_ROOT=tests/fixtures/repo uv run uvicorn app.main:app --port 8000

# 2. frontend
cd frontend
npm run dev                                   # http://localhost:5173
```

`/` lists the novels; `/novelas/<id>` is the cover (title, recipient, dedication from the
API), then `indice` (chapters changed against the previous version are marked
"modificado"), `capitulos/<n>`, and `personajes` (character and place sheets linking to the
chapters where each appears). `?v=<n>` reads an earlier published version; the version
selector and the PDF link are in the reader's bar. Selecting text in a chapter shows
**Pedir un cambio**: the request goes to `POST /novels/<id>/changes`, the page polls the job
and, when the new version is published, switches to its index. (`STORY_ROOT` is only the
legacy harness's startup check; any tree with `canon/project.md` will do.)

**Visual check** (exam § 5a): with both servers running,

```sh
NOVEL_ID=demo-faro BASE_URL=http://127.0.0.1:5173 npx playwright test --config e2e/visual-check.config.ts
```

checks the cover, the index, a chapter and the sheets, and writes screenshots to
`screenshots/visual-check/`. The backend's `pre_publish` validator `visual_check` runs the
same spec when `VISUAL_CHECK=1` (and `BASE_URL`) are set and the reader answers.

## Scripts

| Script | What it does |
|---|---|
| `npm run dev` | Dev server with the `/api` proxy |
| `npm run build` | Production build into `dist/` |
| `npm run typecheck` | `tsc -b` over both projects: `src/` + `test/`, and `e2e/` + `scripts/` + configs |
| `npm run lint` | ESLint with the architecture boundary rules, zero warnings allowed |
| `npm test` | Vitest: components in jsdom with a typed MSW server, and the Node-run checks |
| `npm run gen:api` | Regenerate `src/shared/types/openapi.d.ts` from `../backend/openapi.json` (`-- --schema <path>` for another file) |
| `npm run check:api` | Fail if the committed types are stale against the schema |
| `npm run check:bundle` | After a build: no three.js in the initial bundle, and at most 250 KB gzipped |
| `npm run e2e` | Playwright against the real backend on a temp copy of its fixture (needs `uv` or `backend/.venv`, and `npx playwright install chromium` once) |
| `npm run screenshots` | Screenshots of every route at 1280 and 390 px into `screenshots/out/` (git-ignored), for visual review; not part of the gate |
| `npm run gate` | Everything CI runs, in CI's order; the summary names failures and skips |

## The API contract

The backend publishes `backend/openapi.json`; the frontend's types are generated from that
file, never from a running server, and committed. When the backend changes a route or a model,
`npm run check:api` fails until the types are regenerated with `npm run gen:api` and committed
as a `contract:` commit. The typed client in `src/shared/api/` is the only module that issues a
request.
