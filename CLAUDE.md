# CLAUDE.md

@AGENTS.md

Everything in `AGENTS.md` applies — the rules, the documentation map, Processes 0–3 and the
parallel-work protocol. This file is the entry point for Claude Code: what the project is,
how to run it, and where each piece of tooling lives.

## What this project is

A **harness that writes personalised gift novels**. A person answers an interview about the
recipient (name, age, traits, memories, genre, tone, vetoed topics, dedication); the harness
validates that brief, plans a 10-chapter novel of 1,000–1,500 words per chapter, writes it
scene by scene with bounded rewrites, validates every chapter, proves its chronology in
Lean 4, and publishes it to a web reader with a PDF export. The reader can ask for a change
("el perro se llama Nala"): only the chapters that use that fact are regenerated, into a new
version, and the previous version is kept.

The design is in [`docs/`](./docs/), in this order of authority:
[`definitions.md`](./docs/definitions.md) (what things are),
[`domain-knowledge.md`](./docs/domain-knowledge.md) (how they relate),
[`architecture.md`](./docs/architecture.md) (how the system runs — Figure 3 is the
permission table, Figure 5 the generation flow) and
[`verification.md`](./docs/verification.md) (how each claim is proven). Changes go through
[`specs/`](./specs/); the programme that brought the exam requirements in is
[spec 004](./specs/004-exam-refactor-programme/004-exam-refactor-programme.md).

Languages: novel prose, the root README and the presentation are in Spanish; `docs/`,
specs, code and this file are in English.

## Repository layout

```
backend/          FastAPI + Python: the pipeline, the stores, the authoritative SQLite DB
  app/bible/        the story bible (HARNESS_DB, default data/harness.sqlite)
  app/novel/        the gift-novel pipeline and its CLI
  app/validators/   the validator registry (scene_accept, chapter_close, pre_publish, hook)
  app/commons/      store layer, permissions, config, observability (Langfuse)
frontend/         React + three.js: the web reader first, spatial views second
docs/             the design (docs/process/ is the build record, not design)
specs/            one folder per change: spec + implementation plan
evals/briefs/     example and evaluation briefs
exam/             the exam brief, requirements and compliance checker
.claude/          skills, commands, memory, hooks for Claude Code
```

## Running a generation

```bash
cd backend
uv sync
uv run python -m app.novel.cli generate --brief ../evals/briefs/<file>.json
```

The example brief is `evals/briefs/ejemplo.json` (a copy lives at
`ejemplos/brief-ejemplo.json`). A run that stops resumes at the first incomplete chapter
when launched again with the same brief. The run's validator results are in the
authoritative database; its trace is in Langfuse.

The backend's local gate (Process 3 step 14) is `backend/gate.sh` (`gate.ps1` on Windows).

## Models

Every role — interviewer, planner, writer, editor, judge, canoniser — runs on
**Claude Haiku 4.5** (`claude-haiku-4-5`). A role is raised to a stronger model only when
it keeps failing in live runs, per role through `MODEL_<ROLE>` in `backend/.env`, and the
change is recorded in the iteration log under `docs/process/`.

## Observability

Langfuse, enabled when `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set (see
`backend/.env.example`; a no-op otherwise). One session per novel, one trace per generation
or regeneration, spans `role:<role>` and `tool:<tool>` with tokens, cost and latency, every
validator result as a score, prompts versioned in Langfuse prompt management. Never commit
keys; `.env` files are git-ignored.

## Claude Code tooling

- **Skills** — `.claude/skills/`, provenance in
  [`.claude/skills/README.md`](./.claude/skills/README.md): `react`, `sqlite`, `sqlite-vec`,
  `verification`, and `gift-novel-run` (run and inspect one generation end to end). The
  FastAPI skill is a managed install under `backend/.claude/skills/fastapi/`, pinned to the
  backend's FastAPI version; the README says how to refresh it.
- **Commands** — `.claude/commands/`: `/generate-novel`, `/inspect-novel`, `/change-fact`,
  `/exam-gap`.
- **Memory** — `.claude/memory/`: durable project notes for Claude Code sessions.
- **MCP** — `.mcp.json` configures the **Playwright MCP**, used by the pre-publish visual
  check of the reader (cover, chapter index, sheets). On this container it needs
  `PLAYWRIGHT_MCP_EXECUTABLE_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`.
- **Hooks** — `.claude/settings.json` registers two hooks that run the same code as the
  pipeline on hand edits: one runs the chapter validators, one the forbidden-term policy.
  They exist so that editing a chapter outside the pipeline cannot skip validation.

## Working rules worth repeating

- Run Process 0 before any edit; decisions are the user's, facts are yours to look up.
- Docs, then specs, then code — never patch a contradiction at the lower layer.
- Store access only through the store layer and the bible repository, naming the role.
- No model gets a write tool; roles never widen their own permissions.
- Every diagram is Mermaid.
