---
id: 014
title: B10 — Reader, versions and PDF export (contract K5)
status: approved         # approved 2026-09-24 on the user's delegation for this session (plan 004, V6)
supersedes: null
programme: 004
block: B10
owns:
  - backend/app/reader/**
  - backend/app/export/**
  - frontend/src/cover/**
  - frontend/src/bible/**
  - frontend/src/reader/**
  - frontend/src/scenes/**
  - frontend/e2e/visual-check*
depends_on: [B1, B3]
provides: [K5]
consumes: [K1, K2, K3, K4]
closes: [R01, R02, R03, R04, R05, R06, R07, E05]
docs:
  - docs/architecture.md#the-reader
  - docs/architecture.md#change_factnovel-fact-new_value--novel_version
  - docs/architecture.md#publish_versionnovel-version--published
---

> **Approved 2026-09-24** on the user's delegation (plan 004, deviation V6). Process 0 for
> this block is the programme's; block-level decisions are recorded under "Open questions".

## Motivation

Exam § 2 (Lectura interactiva) asks for a web or PDF reading with a navigable chapter index,
character and place sheets from the story bible linking to the chapters where each appears,
and a cover with a personalised dedication; on the web, a change request from a selected
fragment that regenerates only the chapters using the fact and marks them; on PDF, a
"novedades" page. The previous version must survive. Exam § 5a asks for a visual check of
cover, index and character sheet. Today the frontend reads the legacy file stores and keeps
the dedication in `localStorage` (spec 003), and nothing exports a PDF.

## Scope

**In.** A read-only reader API over the story bible (K1) under `/novels`; the change-request
route that resolves a fact and runs `app.novel.pipeline.change_fact` (K4, provided by B3) in
the background; a PDF export (reportlab) with cover, "Novedades", linked index, chapters,
"Personajes y lugares" sheet and outline, plus a CLI; the React reader (cover with the
dedication from the API, index with "modificado" marks, chapter reader, sheets, version
selector, selection → "Pedir un cambio"); a Playwright visual check and its `pre_publish`
validator `visual_check`; a development seed.

**Out.** The generation pipeline and `change_fact` itself (B3); recording fact usage (B3);
authentication; the legacy `/scenes`, `/canon` routes and their pages, which stay as they
are; the 3D graph page.

## Design

- `app/reader/router.py` opens `BibleRepository.open()` per request (K1). Routes: `GET
  /novels`, `GET /novels/{id}`, `GET /novels/{id}/versions`, `GET
  /novels/{id}/versions/{v}/chapters`, `GET /novels/{id}/versions/{v}/chapters/{n}`, `GET
  /novels/{id}/bible`, `POST /novels/{id}/changes` (202 `{job_id}`), `GET
  /novels/{id}/changes/{job_id}`, `GET /novels/{id}/versions/{v}/pdf`.
- Appearances of a character or place: `chapters_using_fact` of its linked fact in the
  version; with no linked fact or no usage rows, a case-insensitive whole-word search of its
  name across that version's chapters.
- Change resolution (`app/reader/changes.py`): `fact_key` given → that fact. Otherwise a
  deterministic match: the fact whose value appears in the fragment or request, else a kind
  keyword in the request (`perro|gato|mascota` → `pet`, …) with a single candidate; the new
  value is the text after "se llama / es / será / por / →". Ambiguous → one EDITOR call
  through `traced_complete` with the facts list, output `{fact_key, new_value}`. The job
  runs `change_fact` in a daemon thread with its own repository connection; jobs are kept in
  memory (a restart forgets them; the versions stay in the database).
- `change_fact` is imported lazily; without B3 the job fails with a clear message.
- `app/export/pdf.py`: `export_pdf(repo, novel_id, version, out_path)`; the CLI names files
  with the version (`<novel>-v<N>.pdf`) so earlier PDFs are kept (R07).
- The reader shows published versions only (architecture, "The reader"); the API serves any
  version and reports its status.
- Serving: Vite proxies `/api` to the backend (spec 002, FR-API-05), documented in
  `frontend/README.md`.
- `app/reader/visual_check.py`: validator `visual_check` at `pre_publish`; runs the
  Playwright spec when `VISUAL_CHECK=1` and `BASE_URL` answers, else passes with
  "skipped: VISUAL_CHECK not enabled".

## Acceptance criteria

1. AC 1 — R01, R02: `GET /novels/{id}/versions/{v}/chapters` lists every chapter with title,
   words and `changed_vs_parent`. **T**
   *Clarified (browser-MCP finding 1): this holds under concurrent requests too — the
   per-request repository is opened with `check_same_thread=False`.*
   *Clarified (browser-MCP finding 2): `GET /novels/{id}/bible?version=v` (and the PDF
   sheet) shows each character and place with the name v's chapters use; names changed
   later are mapped back from the `change` notes of later versions. The cast itself stays
   unversioned (limit recorded in Open questions).*
2. AC 2 — R03, R04, R06, E05: `export_pdf` writes a PDF with a cover (title, recipient,
   dedication), a "Novedades" page when version > 1, a linked index, the chapters and the
   character/place sheet with links, and internal links throughout. **T**
   *Clarified (tuning iteration 1): "Novedades" renders the version note for a reader —
   `{"change": {key, old, new}}` as "Cambio: <key>: «old» → «new»", internal keys such as
   `stop_reason` hidden — instead of the raw JSON, then the changed chapters with links
   (`app.export.pdf.note_lines`).*
3. AC 3 — R05: `POST /novels/{id}/changes` resolves a fact deterministically when it can and
   starts `change_fact` in the background, returning 202 and a pollable job. **I · D**
4. AC 4 — R02–R04, R06, R07: the web reader shows the cover with the dedication from the
   API, the index with "modificado" marks, a chapter, the sheets with chapter links, and a
   version selector over published versions. **D** (visual check run, screenshots)
5. AC 5 — § 5a: `visual_check` is registered at `pre_publish`, skips cleanly when disabled
   and runs the Playwright spec when enabled. **I · D**
6. AC 6: `ruff` and `mypy --strict` on `app/reader app/export`; `npm run lint && npm run
   typecheck`. **A**

## Verification plan

- AC 1, AC 2: `backend/app/reader/tests/test_reader.py` (`# spec 014 / AC n`).
- AC 3, AC 5: review note in the closing commit; AC 4, AC 5: one local run of
  `frontend/e2e/visual-check.spec.ts` on the dev seed, screenshots under
  `frontend/screenshots/visual-check/`.
- AC 6: the commands above, pasted in the commit bodies.

## Open questions

Closed on delegation: web + PDF (both); Vite proxy rather than FastAPI serving `dist`; jobs
in memory; the reader shows published versions only; legacy pages kept, not primary.

Known limitation (clarified, browser-MCP finding 2): `character`/`place` are not versioned.
Names are mapped back per version from the `change` notes, but a character's
`description` or `role` is shown as it is now in every version. Versioning the cast is a
K1 design change (spec 005), not done.
