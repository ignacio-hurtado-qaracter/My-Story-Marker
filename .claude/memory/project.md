# Project memory — My Story Marker (storyMaker)

What this project is and the decisions that are already settled. Read with `AGENTS.md`;
where they differ, `AGENTS.md` and `docs/` win.

## What it is

An agentic harness that writes **personalised novels to give as a gift** (a child, a
partner, a wedding, a retirement). A buyer is interviewed, the answers become a validated
brief, and a team of roles writes, edits and judges a novel the recipient should recognise
themselves in. Personalisation and narrative quality weigh the same (spec 004 D11): a novel
that mentions every detail but reads badly is a failure.

It is the final exam of the Harness Engineering course; the brief is in `ignore.md`
("Anexo") and its requirements as data in `exam/requirements.toml`.

## Settled decisions

| Decision | Value | Source |
|---|---|---|
| Model | **Claude Haiku 4.5 for every role**, through the Claude Code CLI. Sonnet only for a role that keeps failing, logged in `docs/process/` | plan 004 |
| Roles | interviewer, planner, writer, editor (style editor + auditor), judge, canoniser | spec 004 D7 |
| Story bible | **one authoritative SQLite** at `HARNESS_DB` (default `data/harness.sqlite`), keyed by `novel_id`; the derived index under `.index/` is separate | spec 004 D1 |
| Brief facts | authoritative in SQLite; a reader change updates the fact, only chapters using it regenerate | spec 004 D2 |
| Length | **10 chapters × 1,000–1,500 words** | spec 004 D3 |
| Scenes | **3 per chapter** by default (allowed 3–5), about 200–500 words each | plan 004 V5 |
| Chapter text | rows of `chapter_version` in SQLite, with hash; nothing deleted | plan 004 V4, D6 |
| Validator points | scene accept, chapter close, pre-publish (coverage, Lean, visual) | spec 004 D4 |
| Reading | web reader first, PDF export from the backend | spec 004 D8 |
| Language | **novel prose in Spanish**; root README and presentation in Spanish; `docs/`, specs, code in English | spec 004 D9 |
| Observability | Langfuse: session = novel, trace = generation, spans `role:<role>`, `tool:<tool>` | plan 004 K2 |
| Formal | Lean 4 over the chronology (`formal/lean`), TLA+ of the harness checked with TLC (`formal/tla`) | spec 004 B8, B9 |
| Context | at most 100k concurrent tokens | `AGENTS.md` |
| Recipients | fictional only; no real personal data in briefs | plan 004 |

## Where things are

- `backend/` FastAPI + Python, `frontend/` React + three.js reader.
- `specs/004-exam-refactor-programme/` is the programme; blocks are specs 005–016.
- `docs/process/` is a record area (D10): it cites `docs/`, it never defines design.
