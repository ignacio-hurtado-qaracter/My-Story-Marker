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
| `npm run gate` | Everything CI runs, in CI's order; the summary names failures and skips |

## The API contract

The backend publishes `backend/openapi.json`; the frontend's types are generated from that
file, never from a running server, and committed. When the backend changes a route or a model,
`npm run check:api` fails until the types are regenerated with `npm run gen:api` and committed
as a `contract:` commit. The typed client in `src/shared/api/` is the only module that issues a
request.
