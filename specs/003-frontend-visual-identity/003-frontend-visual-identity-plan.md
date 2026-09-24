---
spec: 003                 # the approved spec this plan implements
status: approved          # draft · approved · done
---

Implementation plan for [`003-frontend-visual-identity.md`](./003-frontend-visual-identity.md),
**revision 2** (2026-09-24). Revision 1's plan was carried out (commits `ce1362c`..`3ffc6e1`:
tokens, fonts, header, restyled screens, planet, identity e2e, screenshots); its review notes
are kept at the end. This revision went back to `draft` with the spec and was **re-approved by
the agent under the user's written delegation**. Anything not listed under "Files to touch"
is out of scope; a file found to be needed is added here in the commit that needs it.

Branch and sharing rules as before: `spec/001-backend`; write only `frontend/**` and
`specs/002-*`, `specs/003-*`; commit by explicit path; no stash, checkout, reset, rebase,
clean, merge, pull or push. Commits `frontend:`, bodies `Implements spec 003, AC …`, gate
summary, `Co-Authored-By`; tests `// spec 003 / AC n`, each shown to fail without its change.

## Implementation decisions (revision 2)

| # | Decision | Why |
|---|---|---|
| Q8 | New features `cover/` and `bible/`, flat. `scenes/` gains `ChapterPage.tsx` and `chapterTitle.ts`; its `index.ts` exports `ScenesRoutes` (mounted at `scenes/*`) and `ChaptersRoutes` (mounted at `chapters/*`). `bible/index.ts` exports `CharactersRoutes` and `LocationsRoutes`; `cover/index.ts` exports `CoverRoute`; `graph3d/index.ts` adds `PlanetHero`. | FR-IA-01; rule 2 (index.ts only). |
| Q9 | `Prose` moves from `scenes/` to `shared/ui/Prose.tsx` (same API `Prose({ markdown })`, same `prose` class), exported from `shared/ui/index.ts`. | Two users (scenes, bible). |
| Q10 | Revision 1's `BookHeader.tsx`, `BookHeader.test.tsx`, `useProject.ts` and `fetchProject` leave `scenes/`; the cover fetches the project itself. | R2-7. |
| Q11 | Cover settings: `cover/useCoverSettings.ts` reads and writes `localStorage['msm.cover.v1']` (JSON `{ title, to, dedication, from }`) inside try/catch; state lives in the component, the save happens in the event handler. | FR-COVER-03; spec 002 FR-TOOL-03 (local UI state). |
| Q12 | Appearances: `bible/appearances.ts`, pure, `characterAppearances(id, chapters, scenes)` and `locationAppearances(id, chapters, scenes, locations)`; `bible/api.ts` loads chapters, scene ids and every scene record with `useQueries`, and every location record for the parent tree. | FR-BIBLE-01; spec R2-5. |
| Q13 | Display title: `scenes/chapterTitle.ts` returns the text between the first pair of straight or curly double quotes at the start of `function`, else `null` (the caller shows "Capítulo N"). The bible feature derives chapter titles the same way in its own module (two lines, not worth a shared module that would bind two features). | R2-4. |
| Q14 | Spec 002 and revision-1 test edits: `routes.test.tsx` (nav, brand href, `/` renders the cover), `e2e/a11y.spec.ts`, `e2e/identity.spec.ts`, `e2e/graph3d.spec.ts` (reach `/graph3d` through the footer link "Vista 3D"), `e2e/scenes.spec.ts` (`/scenes` title "Índice"), `TocPage.test.tsx` (new tests), `screenshots.spec.ts` (new routes). Nothing else of spec 002 changes. | Spec "What changes in spec 002". |

## Files to touch (revision 2)

| Path | What changes |
|---|---|
| `frontend/src/app/Layout.tsx`, `Layout.css`, `routes.tsx`, `routes.test.tsx` | New navigation, brand to `/`, footer link, all routes. |
| `frontend/src/cover/index.ts`, `api.ts`, `CoverPage.tsx`, `useCoverSettings.ts`, `cover.css`, `CoverPage.test.tsx` | New. FR-COVER. |
| `frontend/src/graph3d/PlanetHero.tsx`, `index.ts`, `Graph3dPage.tsx`, `graph3d.css` | `PlanetHero` for the cover. |
| `frontend/src/scenes/TocPage.tsx`, `TocPage.test.tsx`, `ChapterPage.tsx`, `ChapterPage.test.tsx`, `chapterTitle.ts`, `chapterTitle.test.ts`, `routes.tsx`, `index.ts`, `api.ts`, `scenes.css`, `ScenePage.tsx`; delete `Prose.tsx`, `BookHeader.tsx`, `BookHeader.test.tsx`, `useProject.ts` | FR-INDEX, FR-READ. |
| `frontend/src/shared/ui/Prose.tsx`, `index.ts` | `Prose` moved here. |
| `frontend/src/bible/index.ts`, `api.ts`, `appearances.ts`, `appearances.test.ts`, `names.ts`, `CharactersPage.tsx`, `CharacterPage.tsx`, `LocationsPage.tsx`, `LocationPage.tsx`, `Appearances.tsx`, `bible.css`, `CharactersPage.test.tsx`, `CharacterPage.test.tsx`, `LocationPage.test.tsx` | New. FR-BIBLE. |
| `frontend/e2e/a11y.spec.ts`, `identity.spec.ts`, `graph3d.spec.ts`, `scenes.spec.ts`, `reader.spec.ts` (new) | Q14; AC 2, 3, 4, 8, 9, 18. |
| `frontend/screenshots/screenshots.spec.ts` | Every route. |
| `specs/003-frontend-visual-identity/003-frontend-visual-identity-plan.md` | This file; review notes. |

## Steps (revision 2)

8. **Scenes: index and reader** (FR-INDEX, FR-READ; `Prose` to `shared/ui/`; book header out). — *AC 14, 15*.
9. **Story bible** (FR-BIBLE). — *AC 16, 17*.
10. **Cover and planet hero** (FR-COVER, FR-3D-05). — *AC 5, AC 8 (cover half)*.
11. **App shell and routes** (FR-IA). — *AC 6*.
12. **e2e and screenshots** (Q14; reader walk). — *AC 2, 3, 4, 8, 9, 11, 18*.
13. **Gate and review.** — *AC 10, 12, 13*.

Steps 8–10 touch disjoint folders and run in parallel; step 11 wires them; each step is its
own commit.

## Verification mapping (revision 2)

| AC | Letter | Lives in |
|---|---|---|
| 1 | T | `frontend/test/palette.test.ts` |
| 2 | T | `frontend/e2e/a11y.spec.ts` |
| 3, 4, 8, 9 | T | `frontend/e2e/identity.spec.ts` |
| 5 | T | `frontend/src/cover/CoverPage.test.tsx` |
| 6 | T | `frontend/src/app/routes.test.tsx` |
| 7 | T | `frontend/src/graph3d/Graph3dPage.test.tsx` |
| 10 | T | `npm run gate` |
| 11 | D | `npm run screenshots` |
| 12, 13 | I | review notes below |
| 14 | T | `frontend/src/scenes/TocPage.test.tsx`, `chapterTitle.test.ts` |
| 15 | T | `frontend/src/scenes/ChapterPage.test.tsx` |
| 16 | T | `frontend/src/bible/appearances.test.ts` |
| 17 | T | `frontend/src/bible/*.test.tsx` |
| 18 | D | `frontend/e2e/reader.spec.ts` |

## Risks and stop conditions

- A backend change looks necessary → ask the backend session; nothing under `backend/`.
- A spec 002 assertion outside Q14 would have to change → stop and revise the spec first.
- The cover's planet breaks NFR-01 or AC 13 → drop it from the cover (decorative only).
- A contrast pair fails → change the token, never the test.

## Review notes

*(Revision 2 notes are added at step 13; revision 1's notes follow.)*

### Revision 1 — AC 12 visual review and AC 13 placement (2026-09-24)

Revision 1's screenshots matched `main`'s palette, header, pills, cards, type and planet;
deliberate differences: the accessible accent, underlined links in text, no landing page or
library, the planet framed with a pause toggle. Tokens and base in `shared/ui/`, feature CSS
flat, no new shared component. Leftovers: `@react-three/drei` unused; a cosmetic chunk name in
`test/check-bundle.test.ts`.
