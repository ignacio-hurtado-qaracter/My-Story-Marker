---
spec: 003                 # the approved spec this plan implements
status: approved          # draft · approved · done
---

Implementation plan for [`003-frontend-visual-identity.md`](./003-frontend-visual-identity.md)
(approved 2026-09-24). **Approved by the agent on 2026-09-24 under the user's written
delegation** (spec 003, D-0): approve the plan and implement it without further interaction.
Anything not listed under "Files to touch" is out of scope; a file that turns out to be needed
is added here in the same commit that needs it, with the reason in the commit body.

Branch: `spec/001-backend`, shared with the backend session, under the same rules as plan 002
("Sharing the branch"): write only `frontend/**` and `specs/003-*/`; commit by explicit path;
never stash, checkout, reset, rebase, clean, merge, pull or push. Commit conventions as plan
002: prefixes `frontend:`; bodies say `Implements spec 003, AC …`, carry the gate summary and
the `Co-Authored-By` trailer; tests carry `// spec 003 / AC n` and are shown to fail without
their change.

## Implementation decisions

| # | Decision | Why |
|---|---|---|
| Q1 | `@fontsource/inter` 5.3.0 and `@fontsource/jetbrains-mono` 5.3.0, exact. `tokens.css` imports `@fontsource/inter/latin-{400,500,600,700}.css` and `@fontsource/jetbrains-mono/latin-400.css`. | FR-FONT-01; latest on 2026-09-24, OFL-1.1. |
| Q2 | `app/App.tsx` imports `../shared/ui/tokens.css` and `../shared/ui/base.css` once; each component imports its own CSS file. | FR-TOK, D-4. |
| Q3 | The palette test parses `tokens.css` with a regex for `--name: #hex;` and computes WCAG contrast in the test; it runs in Node and is type-checked by `tsconfig.node.json`, like plan 002's Node-run tests. | AC 1. |
| Q4 | The book header is a new `scenes/BookHeader.tsx` rendered by `TocPage`, with `fetchProject` in `scenes/api.ts` and `useProject.ts`; a `404` or any error yields no premise block. | FR-BOOK. |
| Q5 | `graph3d/PlanetScene.tsx` replaces `EmptyScene.tsx`. A seeded mulberry32 generator at module scope builds particle positions and satellite phases once. `Graph3dPage` owns the `paused` state, initialised from `useReducedMotion()` (a `useSyncExternalStore` hook in `graph3d/useReducedMotion.ts`). `PlanetScene` receives `paused`, keeps it in a ref, returns early from `useFrame` while paused, and sets `frameloop` to `demand` when paused. | FR-3D-03/04. |
| Q6 | The canvas screenshot comparison of AC 8 uses `locator.screenshot()` of the canvas container, compared as buffers. | AC 8. |
| Q7 | Screenshots: `frontend/playwright.screenshots.config.ts` with `testDir: './screenshots'`, reusing plan 002's two webServers; output to `frontend/screenshots/out/` (git-ignored via `frontend/.gitignore`); `npm run screenshots` runs it. The default config's `testDir` stays `./e2e`, so the gate never runs it. | AC 11, D-6. |

## Files to touch

| Path | What changes |
|---|---|
| `frontend/package.json`, `frontend/package-lock.json` | The two `@fontsource` dependencies; the `screenshots` script. |
| `frontend/.gitignore` | `screenshots/out/`. |
| `frontend/tsconfig.app.json`, `frontend/tsconfig.node.json` | `test/palette.test.ts` in the Node project; `playwright.screenshots.config.ts` and `screenshots/` in the Node project. |
| `frontend/src/shared/ui/tokens.css`, `base.css` | New. FR-TOK, FR-FONT. |
| `frontend/src/shared/ui/Heading.tsx`, `Heading.css`, `ErrorPanel.tsx`, `ErrorPanel.css` | CSS imports and styles. FR-UI3. |
| `frontend/src/app/App.tsx` | Global CSS imports. |
| `frontend/src/app/Layout.tsx`, `Layout.css`, `logo-qaracter.svg`, `NotFoundPage.tsx` | Header, brand, nav pills, footer; inline targets removed. FR-SHELL3. |
| `frontend/src/app/routes.test.tsx` | `GET /canon/project` handler; new AC 6 tests. |
| `frontend/src/health/StatusBadge.tsx`, `StatusBadge.css` | Pill and pulsing dot. FR-HLT3. |
| `frontend/src/scenes/api.ts`, `useProject.ts`, `BookHeader.tsx`, `BookHeader.test.tsx`, `scenes.css`, `TocPage.tsx`, `ScenePage.tsx`, `Skeleton.tsx`, `Prose.tsx` | Book header, cards, chips, detail layout; inline targets removed. FR-BOOK, FR-SCN3. |
| `frontend/src/scenes/TocPage.test.tsx` | `GET /canon/project` handler only. |
| `frontend/src/graph3d/PlanetScene.tsx` (replaces `EmptyScene.tsx`), `LazyCanvas.tsx`, `Graph3dPage.tsx`, `useReducedMotion.ts`, `graph3d.css`, `Graph3dPage.test.tsx` | Planet, pause, reduced motion; new AC 7 tests. FR-3D. |
| `frontend/e2e/graph3d.spec.ts` | Chunk regex `EmptyScene` → `PlanetScene` only. |
| `frontend/e2e/a11y.spec.ts` | New AC 2 test (book header loaded). |
| `frontend/e2e/identity.spec.ts` | New. AC 3, 4, 8, 9. |
| `frontend/test/palette.test.ts` | New. AC 1. |
| `frontend/playwright.screenshots.config.ts`, `frontend/screenshots/screenshots.spec.ts` | New. AC 11. |
| `frontend/README.md` | The `screenshots` script. |
| `specs/003-frontend-visual-identity/003-frontend-visual-identity-plan.md` | This file; review notes AC 12–13; status `done` at closure. |

## Steps

1. **Tokens, base, fonts.** Dependencies, `tokens.css`, `base.css`, imports in `App.tsx`, `test/palette.test.ts`. — *AC 1, AC 3 (fonts)*.
2. **Shell, shared primitives, health.** Layout, logo, nav pills, footer, NotFound, Heading, ErrorPanel, StatusBadge; routes tests. — *AC 6*.
3. **Scenes.** Book header, cards, chips, detail layout, states; TocPage/BookHeader tests. — *AC 5*.
4. **Planet.** PlanetScene, pause, reduced motion, graph3d tests, e2e regex. — *AC 7*.
5. **Identity e2e and axe.** `identity.spec.ts`, the new axe test. — *AC 2, 3, 4, 8, 9*.
6. **Screenshots.** Config, spec, script, gitignore. — *AC 11*.
7. **Gate and review.** `npm run gate`; screenshots reviewed against `main`; notes AC 12–13 below. — *AC 10, 12, 13*.

Steps 2, 3 and 4 touch disjoint files after step 1 and may run in parallel; each is committed on its own, in order.

## Verification mapping

| AC | Letter | Satisfied by | Lives in |
|---|---|---|---|
| 1 | T | contrast of every FR-TOK-02 pair from `tokens.css` | `frontend/test/palette.test.ts` |
| 2 | T | axe on `/scenes` with the book header, plus spec 002's axe tests | `frontend/e2e/a11y.spec.ts` |
| 3 | T | request origins per route; `woff2` URLs in built CSS | `frontend/e2e/identity.spec.ts` |
| 4 | T | Tab order, computed outline, sticky-header clearance | `frontend/e2e/identity.spec.ts` |
| 5 | T | premise shown, answer never, skeleton, 500/404 omission, pills timing | `frontend/src/scenes/BookHeader.test.tsx` |
| 6 | T | brand name, `aria-current`, `contentinfo` | `frontend/src/app/routes.test.tsx` |
| 7 | T | stub scene receives `paused`; toggle; reduced motion; no `matchMedia` | `frontend/src/graph3d/Graph3dPage.test.tsx` |
| 8 | T | dot animation on/off; canvas frames differ / identical; reduced motion | `frontend/e2e/identity.spec.ts` |
| 9 | T | scrollWidth at 320 and 390 px; planted overflow fails | `frontend/e2e/identity.spec.ts` |
| 10 | T | `npm run gate` | `frontend/scripts/gate.mjs` |
| 11 | D | `npm run screenshots` | `frontend/screenshots/` |
| 12 | I | visual review note | below |
| 13 | I | placement review note | below |

## Risks and stop conditions

- **A spec 002 assertion would have to change** (beyond the chunk regex): stop; the design is
  wrong, not the test.
- **The planet breaks the bundle rules or cannot really pause** (AC 7–8, AC 12–13 of spec
  002): drop it under Process 2 rule 10 (spec 003 D-5), keeping spec 002's scene restyled.
- **A contrast pair fails** in AC 1 or axe: change the token, never the test.
- **A backend change looks necessary**: ask the backend session first; nothing under
  `backend/` is edited here.

## Review notes

### AC 12 — visual review (2026-09-24, agent, delegated)

Screenshots from `npm run screenshots` (1280 × 800 and 390 × 844, five routes) compared with
`main`'s `web/` pages:

- **Carried over:** the Qaracter logo and divider in a white glass header; pill navigation;
  Inter throughout with `main`'s type scale; soft cards with a 14 px radius and `main`'s
  shadow; orange uppercase eyebrows; pills; `main`'s detail layout on the scene page
  (eyebrow, title, key–value card, word-count pill); `main`'s orange-50 → white hero
  gradient on the book header and the planet card; the planet itself (flat-shaded orange
  core, wireframe shell, ink rings with satellites, orange particles); the green "live" dot.
- **Deliberate differences:** text and filled orange use the accessible accent `#AE4E14`
  instead of `#E5661F` / `#FF7A2F` (FR-TOK-02), so the active pill is a deeper orange with
  white text; links in text are underlined; no landing page, create form or library (Out);
  the planet sits in a framed stage on `/graph3d` rather than behind a hero, has no pointer
  parallax, and has a pause toggle; on phones the logo image hides and the header wraps
  (the brand text, nav and badge stay).
- **Fixed during review:** the footer floated mid-screen on short pages (commit "the footer
  sits at the bottom of short pages").

### AC 13 — placement review (2026-09-24, agent, delegated)

- `tokens.css` and `base.css` live in `src/shared/ui/`, imported once by `app/App.tsx`.
- Each feature's CSS sits flat beside its components: `app/Layout.css`,
  `health/StatusBadge.css`, `scenes/scenes.css`, `graph3d/graph3d.css`, and
  `shared/ui/Heading.css`, `shared/ui/ErrorPanel.css`. No feature imports another feature's
  CSS (checked by grep of `import './…css'` per folder).
- No new `shared/ui/` component was created; the shared classes in `base.css` (`.card`,
  `.pill`, `.eyebrow`, `.btn-ghost`) are used by two or more of `app/`, `scenes/`,
  `graph3d/` and `shared/ui/ErrorPanel`.

### Leftovers, for a later dependency change

- `@react-three/drei` is no longer imported (the planet has no controls); it stays in
  `package.json` until a spec removes it.
- `test/check-bundle.test.ts` (spec 002) names its synthetic lazy chunk `EmptyScene.js`;
  cosmetic, not tied to the real module.
