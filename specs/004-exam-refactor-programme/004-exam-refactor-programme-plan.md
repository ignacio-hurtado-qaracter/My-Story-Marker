---
spec: 004
status: done              # closed 2026-09-25: waves A–D run; only the author's demo video and human review remain (spec 004 AC 9)
---

# Plan 004 — Exam refactor programme, run as parallel agent waves

The user delegated every approval of this session (specs, block specs, plans) to the agent,
asked for light verification (few tests, cut the slow ones first), Haiku 4.5 for every role
(Sonnet 5 only for a role that keeps failing, recorded in the iteration log), fictional
recipients, and — if time runs short — a finished 10-chapter novel before anything else.

## Deviations from spec 004 adopted at approval

| # | Spec 004 says | Plan does | Why |
|---|---|---|---|
| V1 | One branch `spec/NNN-slug` per block, integration branch `spec/001-backend` | Each block agent works in its own git worktree; the orchestrating session merges into `proyecto-desde-cero`, the only branch this session may push | Session constraint on push targets |
| V2 | B0 is a serial gate before every other block | B0 runs **in parallel** with wave A; it owns `docs/` exclusively so no file collides | One night of wall-clock; docs are aligned before the programme closes |
| V3 | Every block passes the full `AGENTS.md` gate | New modules: `ruff` + `mypy --strict` on the new package + 1–3 focused tests per block; no schemathesis / hypothesis for new code. The legacy gate stays as it is | User asked for light verifiers; recorded as **U** in the accepted-risk register |
| V4 | Prose stays in files, one store tree per novel | Chapter text is stored as rows of `chapter_version` in the authoritative DB (D6 already puts text and hash per chapter there); the legacy file stores are not used by the gift-novel pipeline | Removes a second source of truth for the same text |
| V5 | Chapter = 3–5 scenes | The planner plans **3 scenes** per chapter by default (allowed: 3–5) | Cost and latency on Haiku; within D3 |
| V6 | Block specs are drafted one per session after their own Process 0 | Each block agent drafts its block spec from the § 6 template, approves it and its plan on the delegation, then implements | Delegation; the spec is still written before the code |

## Block spec numbers

| Block | Spec id | Wave |
|---|---|---|
| B0 docs alignment | under 004 | A |
| B1 story bible + contracts K1, K3, K4 | 005 | A |
| B6 observability (K2) | 010 (written by the B1 agent, same wave) | A |
| B8 Lean 4 | 012 | A (toolchain + model), C (wiring) |
| B9 TLA+ | 013 | A (model), C (mapping) |
| B12 repo, process docs, presentation | 016 | A (scaffold), D (close) |
| B2 interview and brief | 006 | B |
| B3 generation pipeline | 007 | B |
| B4 programmatic validators | 008 | B |
| B5 guardrails, policy, hooks | 009 | B |
| B7 judge and human review | 011 | B |
| B10 reader, versions, PDF | 014 | B |
| B11 evals and red-team | 015 | C |

## Shared contracts (fixed here so wave B can start the moment wave A merges)

**K1 — `backend/app/bible/`** (B1). SQLite at `HARNESS_DB` (default `data/harness.sqlite`,
git-ignored). Migrations numbered per block range (§ 5.4 of the spec). Tables, all keyed by
`novel_id`: `novel`, `brief`, `fact(key, value, kind, source ∈ {interview, free_text,
planner}, mandatory)`, `fact_usage(fact_id, chapter, scene)`, `character(name, role,
birth_date, description)`, `place(name, description)`, `chronology_event(seq, story_date,
chapter, scene, place_id, description, kind ∈ {normal, death, departure})`,
`event_participant(event_id, character_id)`, `novel_version(version, parent_version, status
∈ {draft, published, blocked}, changed_chapters, note)`, `chapter_version(version, chapter,
title, text, hash, summary)`, `checkpoint(version, chapter, status)`, `forbidden_term(scope ∈
{global, novel}, term)`, `policy_decision`, `validator_result`. A `BibleRepository` class
is the only code that touches this database.

**K2 — `backend/app/commons/observability/`** (B6). `get_observer()` returns a Langfuse
observer when `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` are set, a no-op otherwise.
Session = novel, trace = one generation or regeneration, spans named `role:<role>` and
`tool:<tool>`, generations with tokens, cost (pinned price table) and latency, `score(...)`.
`traced_complete(...)` wraps `ClaudeCodeModelClient.complete` with the span, the usage, the
prompt name and version, and a bounded retry. Prompts are published to Langfuse prompt
management and their version recorded per call.

**K3 — `backend/app/validators/protocol.py`** (B1 provides the interface; B4 owns the
module afterwards). `ValidationPoint ∈ {scene_accept, chapter_close, pre_publish, hook}`,
`ValidationResult(name, passed, score, evidence, explanation)`, a registry, and
`run_point(point, ctx)` which persists each result through K1 and scores it through K2.

**K4 — hook points of the pipeline** (B3): `before_scene_accept`, `before_chapter_close`,
`before_publish`, each calling `run_point` for its point.

**K5 — `change_fact` / `publish_version`** (B10 with B3), routes under `/novels/...`.

## Steps

1. **Wave A** (parallel agents, one worktree each): B0, B1+B6 (contracts first), B8
   toolchain + Lean invariants over a JSON chronology, B9 TLA+ model + TLC run, B12
   scaffold (`.mcp.json` with Playwright MCP, `.claude/commands`, `.claude/memory`, the
   harness skill, root `README.md`, `.env.example`, `presentacion/README.md`).
2. **Merge wave A** into `proyecto-desde-cero`, run the quick gate, push.
3. **Wave B** (parallel): B2, B3, B4, B5, B7, B10. Shared files (`main.py`, `config.py`,
   `pyproject.toml`) are edited in small, separate commits; the orchestrator resolves
   merge conflicts.
4. **Merge wave B**, smoke-generate a 1-chapter novel, fix what breaks, push.
5. **Wave C**: launch the two novels at the same time (3 and 10 chapters, fictional
   recipients); in parallel B8 wiring into `pre_publish`, B9 code mapping, B11 evals
   (five briefs incl. one injection and one temporal incoherence, validator × brief table,
   one tuning iteration), the browser-MCP visual check.
6. **Wave D**: B12 close — `docs/process/**` (initial spec, trade-offs, explainers,
   diagrams, iteration log, red-team log), `ejemplos/novela-ejemplo.pdf`, presentation deck
   (PPTX + PDF) and annexes, human-review template for the user, `exam/check.py` report.
   Close spec 004 and the block specs whose ACs hold.

## Verification mapping

| Spec 004 AC | Letter | Satisfied by |
|---|---|---|
| AC 1 | A · I | `exam/check.py` (B12 adds `--coverage 004` if time allows; otherwise review note) |
| AC 2 | I · A | B0 `docs:` commits + grep noted in their bodies |
| AC 3 | A | B0 runs a link + Mermaid check once and pastes the output |
| AC 4 | I | Coverage matrix rows added by B0 |
| AC 5, 7 | A · I | Block specs 005–016 frontmatter; review note |
| AC 6 | I | Block specs' `consumes` |
| AC 8 | A | `python exam/check.py` before/after |
| AC 9 | A · I | Programme close, wave D |

## Risks and stop conditions

- A novel run fails repeatedly on one role → raise only that role to Sonnet 5, log it.
- Lean or TLC cannot be installed → Docker fallback; if none, document as **U** and keep
  the exported `.lean` file and the TLA+ spec.
- A block needs a file owned by another block → the orchestrator arbitrates (delegated
  Process 0), records it here.
- Running out of time → finish the 10-chapter novel and its PDF first, then docs.
