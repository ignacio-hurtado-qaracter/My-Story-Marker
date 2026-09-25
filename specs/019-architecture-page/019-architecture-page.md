---
id: 019
title: "Cómo funciona" architecture page and library polish
status: approved         # approved 2026-09-25 on the user's request (delegated approvals)
supersedes: null
owns:
  - frontend/src/architecture/**
  - frontend/src/reader/NovelsPage.tsx, frontend/src/reader/library.css, frontend/src/reader/NovelsPage.test.tsx
  - frontend/src/app/routes.tsx, frontend/src/app/Layout.tsx (one route + one nav link each)
  - frontend/screenshots/architecture/
docs:
  - docs/architecture.md#figure-5--one-novel-generation
  - docs/process/diagramas.md#arquitectura-del-harness
  - docs/process/diagramas.md#validadores-y-punto-de-ejecución
---

> **Approved 2026-09-25** on the user's request; the user delegated approvals for this
> session (AGENTS.md, parallel work rule 7). Process 0 is the user's brief for this change.

## Motivation

The web app shows novels but nothing explains how the harness writes them, and the novel
list at `/` shows only a title and a version.

## Scope

In: a read-only page `/arquitectura` ("Cómo funciona") with an ~12-node diagram of the
harness drawn in React (HTML nodes + inline SVG arrows), each node explaining what it does,
what it reads and writes, which validators run there and its code path; a legend; a card per
novel at `/` ("Biblioteca") with status, version, chapter count, links and filter chips.

Out: any backend or API change (the library uses `GET /novels`, `GET /novels/{id}` and the
chapter index already published under K5); no new dependency; no change to the design in
`docs/` — the page restates Figure 5 and `diagramas.md`, it defines nothing.

## Design

A new feature folder `frontend/src/architecture/` exported through its `index.ts`
(architecture rule 2). The node data is a static typed table; the diagram is a CSS grid of
buttons with SVG arrows, collapsing to a vertical list on phone widths. The library derives
the status badge from `NovelDetail` (`published` → publicada; latest version `blocked` →
bloqueada; `stopped_error` → parada; otherwise en curso) and the chapter count from the
current version's chapter index.

## Acceptance criteria

1. `/arquitectura` renders every node as a keyboard-focusable button with an `aria-label`;
   activating one shows its name, explanation, reads/writes, validators and code path. **T**
2. Every code path named on the page exists in the repository. **I** (review against `ls`)
3. The page stacks vertically at 390 px with no horizontal scroll and honours
   `prefers-reduced-motion`. **D** (screenshots in `frontend/screenshots/architecture/`)
4. `/` shows one card per novel with title, recipient, status badge, version, chapter count
   and links to cover, index and PDF; the chips filter todas / publicadas / otras. **T**
5. `npm run lint && npm run typecheck && npm test` pass. **A**

## Verification plan

`frontend/src/architecture/ArchitecturePage.test.tsx` (AC 1) and
`frontend/src/reader/NovelsPage.test.tsx` (AC 4) over the typed MSW server; screenshots at
1280 and 390 px (AC 3); the local gate (AC 5).

## Open questions

None.
