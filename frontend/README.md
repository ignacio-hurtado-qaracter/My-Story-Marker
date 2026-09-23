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
