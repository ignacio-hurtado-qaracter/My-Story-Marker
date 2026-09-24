---
spec: 016
status: approved          # approved 2026-09-24 on the user's delegation for this session
---

# Plan 016 — B12 repository, process docs and presentation

## Files to touch

Scaffold (wave A):

- `.mcp.json` — Playwright MCP server, headless, no machine path.
- `.claude/commands/generate-novel.md`, `inspect-novel.md`, `exam-gap.md`, `change-fact.md` — one command each.
- `.claude/memory/project.md`, `conventions.md` — project facts and working conventions.
- `.claude/skills/gift-novel-run/SKILL.md` — the reusable harness skill.
- `.claude/skills/README.md` — one appended row and a short section for `gift-novel-run`.
- `README.md` — root README in Spanish.
- `.env.example` — root placeholders, pointing to `backend/.env.example`.
- `presentacion/README.md`, `ejemplos/README.md`, `docs/process/README.md` — skeletons.

Close (wave D): the pages listed in `docs/process/README.md`, `presentacion/*.pptx|pdf`,
`presentacion/anexo-*.pdf`, and a refresh of every file above.

## Steps

1. Spec and plan, approved on delegation. Commit `spec(016):`.
2. `.mcp.json`; verify the server over stdio (AC 4). Commit `chore:`.
3. Commands, memory and the skill with its README entry (AC 3, AC 5). Commit `chore:`.
4. Root `README.md` and `.env.example` (AC 1, AC 2). Commit `chore:`.
5. `presentacion/README.md`, `ejemplos/README.md`, `docs/process/README.md` (AC 6, part of
   AC 5). Commit `docs(process):`.
6. *(Wave D)* Process pages, deck, annexes, README refresh (AC 7, AC 8). Closing commit
   lists each AC and its check; spec to `implemented`, plan to `done`.

## Verification mapping

| AC | Letter | Satisfied by |
|---|---|---|
| AC 1 | A · I | `exam/check.py` E01, E03; review note |
| AC 2 | A | `exam/check.py` E04 |
| AC 3 | A | `exam/check.py` K01, K02 |
| AC 4 | D | stdio run of `@playwright/mcp` (`initialize` + `browser_navigate`), pasted in the step 2 commit |
| AC 5 | A · I | `exam/check.py` H02, K04; review note |
| AC 6 | A | `exam/check.py` P01 |
| AC 7 | A · I | `exam/check.py` K05, K06, V05, D01–D06 (wave D) |
| AC 8 | A · I | `exam/check.py` P02–P05 (wave D) |

## Risks and stop conditions

- A command or the skill needs an operation another block has not fixed yet (CLI flags,
  change route): write the step with the name from spec 004 § 4 and mark it pending; the
  close phase corrects it. Inventing a flag is not allowed.
- Anything requiring an edit outside the owned paths (`.gitignore` for the MCP output
  directory `.playwright-mcp/`, `CLAUDE.md` links) is reported to the orchestrator, not
  done here.
- The Playwright MCP cannot start on this machine: record it as **U** and keep the config.
