---
id: 016
title: B12 — Repository, process docs and presentation
status: approved         # approved 2026-09-24 on the user's delegation for this session
supersedes: null
programme: 004
block: B12
owns:
  - docs/process/**
  - .claude/skills/gift-novel-run/
  - .claude/skills/README.md      # one appended entry only
  - .claude/commands/**
  - .claude/memory/**
  - .mcp.json
  - README.md
  - .env.example
  - presentacion/**
  - ejemplos/README.md            # ejemplos/ is otherwise B11's
depends_on: [B0]                  # scaffold starts at once; close waits for every block
provides: []
consumes: [K1, K2, K4, K5]        # documented, not called
closes: [E01, E03, E04, K01, K02, K03, K04, K05, K06, D01, D02, D03, D04, D05, D06, P01, P02, P03, P04, P05, H02, V05]
docs:
  - docs/architecture.md#repository-and-application-stack
  - docs/verification.md#accepted-risks-u-register
  - docs/verification.md#guardrails--a-structural--t-behavioural
---

> **Approved 2026-09-24** on the user's delegation ("apruebo todo lo que vayamos a hacer en
> esta sesión"), as spec 004's plan, deviation V6, allows. Process 0 for this block is the
> delegated one: the defaults below were decided by the agent and are recorded as decisions.

## Motivation

Spec 004 § 1.8 rows E01–E05, K01–K06, D01–D06 and P01–P05 are *partial* or *absent*: the
repository has no root README, no `.claude/commands/`, no `.claude/memory/`, no browser MCP
configuration, no harness skill, no `docs/process/` and no `presentacion/`. Without them the
exam fails on deliverables regardless of how good the harness is ("un proyecto sin
documentación de proceso en /docs no aprueba").

## Scope

**In** — two phases, per plan 004 (wave A scaffold, wave D close):

1. *Scaffold* (this spec's first delivery): `.mcp.json` with Playwright MCP; four commands
   (`generate-novel`, `inspect-novel`, `exam-gap`, `change-fact`); memory files
   (`project.md`, `conventions.md`); the harness skill `gift-novel-run`; root `README.md`
   and `.env.example`; `presentacion/README.md`; `ejemplos/README.md`;
   `docs/process/README.md` as the index of the record area.
2. *Close* (wave D): the process documents themselves (spec inicial, trade-offs,
   explainers, diagrams, iteration log, red-team log, browser MCP log, subagents and
   commands), the deck in PPTX and PDF, the annexes, the demo video link, and a refreshed
   README that no longer marks anything as pending.

**Out** — everything owned by another block in spec 004 § 3: code under `backend/` and
`frontend/`, `docs/` outside `docs/process/`, `AGENTS.md`, `CLAUDE.md` (B0), `.claude/settings.json`
and `.claude/hooks/` (B5), `formal/` (B8, B9), `evals/` and the example novel PDF itself
(B11). The submission email (E07–E08) is the user's.

## Design

- **Record area.** `docs/process/` cites `docs/` and never defines design (spec 004 D10).
  It is edited without Process 1 unless a page starts stating how the system works, in
  which case the statement moves to the owning doc.
- **Language.** Root README, `presentacion/` and `ejemplos/` in Spanish; spec, commands,
  memory and skill in English (spec 004 D9). `docs/process/` pages in Spanish, since they
  are read by the examiner.
- **Browser MCP.** `.mcp.json` at the repository root (the project-scope file Claude Code
  reads) declares one server, `playwright`, run as `npx @playwright/mcp@latest --headless
  --isolated --browser chromium`. It carries no machine path. A machine whose Playwright
  browser cache does not match the MCP's pinned revision sets
  `PLAYWRIGHT_MCP_EXECUTABLE_PATH` in its own environment; the README documents this.
- **Commands and skill** wrap operations the other blocks provide (the CLI of B3, the
  change operation K5 of B10, `exam/check.py`). Where the operation is not built yet the
  command says so; nothing is invented.
- **Placeholders.** Sections of the README that depend on code not yet merged carry a short
  "pendiente (bloque Bn)" marker. The close phase removes every marker.

## Acceptance criteria

1. AC 1 — E01, E03. `README.md` and `.env.example` exist at the root; the README covers
   what, architecture (Mermaid), requirements, install, example run, reading, change
   request, validators, formal, observability, layout and links. **A** (`exam/check.py`) · **I**.
2. AC 2 — E04. No versioned file carries a key: `.env.example` has empty values only. **A**
   (`exam/check.py` E04).
3. AC 3 — K01, K02. At least one command in `.claude/commands/*.md` and one memory file in
   `.claude/memory/*.md`. **A**.
4. AC 4 — K03. `.mcp.json` declares Playwright MCP and the server answers `initialize` and a
   `browser_navigate` call on this machine. **D** (run recorded in the commit body).
5. AC 5 — H02, K04. `.claude/skills/gift-novel-run/SKILL.md` exists with frontmatter, is
   listed in `.claude/skills/README.md` and referenced from `docs/process/`. **A** · **I**.
6. AC 6 — P01. `presentacion/README.md` lists the planned contents and states the language. **A**.
7. AC 7 — K05, K06, V05, D01–D06 (close phase). The process pages exist, and the browser
   MCP log records a real inspection, what it found and what changed. **A** · **I**.
8. AC 8 — P02–P05 (close phase). Deck in PDF and PPTX, annexes `anexo-*.pdf`, demo video
   linked. **A** · **I**.

## Verification plan

Light verification, per plan 004 deviation V3: no new tests. AC 1–3, 5–8 are checked by
`python exam/check.py` (the rows named in each AC) plus a review note in the closing
commit. AC 4 is a demonstrated run of the MCP server over stdio, pasted in the commit that
adds `.mcp.json`. AC 7 and AC 8 are only met in the close phase; the scaffold leaves them
open by design.

## Open questions

None. Decided on delegation: `.mcp.json` at the root rather than `.claude/mcp.json`
(the file Claude Code reads for project scope); machine path by environment variable, not
in the file; the skill is named `gift-novel-run`.

## Status note (2026-09-25)

Not closed: AC 8 is not met. Status stays `approved` and the plan stays `approved` until the
author links the demo video; then this spec closes with the table below plus the video row.

| AC | State |
|---|---|
| 1 | Met — A: `exam/check.py` E01, E03 ✅; I: root `README.md` rewritten with every built section and a "Resultados" section (close-out) |
| 2 | Met — A: `exam/check.py` E04 ✅ (`.env.example` values empty) |
| 3 | Met — A: `.claude/commands/*.md` (4), `.claude/memory/*.md` (2); K01, K02 ✅ |
| 4 | Met — D: Playwright MCP `initialize` + `browser_navigate` recorded in the commit that added `.mcp.json` and in `docs/process/browser-mcp-log.md` |
| 5 | Met — A · I: `.claude/skills/gift-novel-run/SKILL.md`, listed in `.claude/skills/README.md`, cited from `docs/process/subagentes-comandos-skills.md` |
| 6 | Met — A: `presentacion/README.md` (P01 ✅) |
| 7 | Met — A · I: every `docs/process/` page exists; the browser-MCP log records two real inspections, the two findings and their fixes (`b612d34`, `ed58daa`) |
| 8 | **Pending** — deck (`presentacion/presentacion.pdf`, `.pptx`) and five `anexo-*.pdf` exist (P02–P04 ✅); the demo video (P05 ❌) is recorded by the author |

