---
spec: 019
status: approved          # approved 2026-09-25 on the user's request (delegated approvals)
---

## Files to touch

- `frontend/src/architecture/{ArchitecturePage.tsx,nodes.ts,architecture.css,index.ts,ArchitecturePage.test.tsx}` — the page, its node table, styles, public surface, test.
- `frontend/src/app/routes.tsx` — one route `arquitectura`.
- `frontend/src/app/Layout.tsx` — one nav link "Cómo funciona".
- `frontend/src/reader/NovelsPage.tsx`, `frontend/src/reader/library.css` — the library cards and chips.
- `frontend/src/reader/NovelsPage.test.tsx` — library test.
- `frontend/screenshots/architecture/*.png` — review screenshots.

## Steps

1. Spec and plan (`spec(019):`).
2. Architecture page, route and nav link (AC 1–3).
3. Library cards and filter chips (AC 4).
4. Screenshots, visual fixes, gate (AC 3, AC 5).

## Verification mapping

| AC | Letter | Verification |
|---|---|---|
| 1 | T | `src/architecture/ArchitecturePage.test.tsx` |
| 2 | I | paths checked with `ls` during review |
| 3 | D | `frontend/screenshots/architecture/arquitectura-{1280,390}.png` |
| 4 | T | `src/reader/NovelsPage.test.tsx` |
| 5 | A | local gate output in the final report |

## Risks and stop conditions

A field the library needs that the API does not publish would require a backend change and a
contract commit: stop and reopen Process 0 rather than widening scope silently.
