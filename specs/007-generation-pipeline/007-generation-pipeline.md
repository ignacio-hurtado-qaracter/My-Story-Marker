---
id: 007
title: B3 — Generation pipeline (planner, writer, editor, checkpoints, publish, change_fact)
status: approved         # approved 2026-09-24 on the user's delegation for this session
supersedes: null
programme: 004
block: B3
owns:
  - backend/app/novel/**
  - backend/app/prompts/planner.md
  - backend/app/prompts/writer.md
  - backend/app/prompts/editor.md
  - specs/007-generation-pipeline/**
depends_on: [B1, B6]
provides: [K4]
consumes: [K1, K2, K3]
closes: [H01, H06, M04, R05]
docs:
  - docs/architecture.md#figure-5--one-novel-generation
  - docs/architecture.md#publish_versionnovel-version--published
  - formal/tla/COUNTEREXAMPLES.md
---

> **Approved 2026-09-24** on the user's delegation for this session (plan 004, deviation V6).
> Process 0 for this block is the programme's: spec 004 decisions, contracts K1–K4 of
> [`004-contracts.md`](../004-exam-refactor-programme/004-contracts.md) and the TLC rules
> CE1–CE4 of [`formal/tla/COUNTEREXAMPLES.md`](../../formal/tla/COUNTEREXAMPLES.md).

## Motivation

Spec 004 § 1 rows H01 (planner, writer, editor/critic), H06 (bounded retries at chapter
level), M04 (checkpoint per chapter, resume) and R05 (change one fact, regenerate only the
chapters that use it). Without this block nothing turns a validated brief into a novel.

## Scope

In: `app.novel` — planner, writer, editor roles and their prompts; the chapter loop of
[Figure 5](../../docs/architecture.md#figure-5--one-novel-generation); hook points
`before_scene_accept`, `before_chapter_close`, `before_publish`; checkpoints and resume;
one repair round; `change_fact`; the CLI; guarded validator registration (`setup.py`).

Out: the brief schema and interview (B2 — a minimal local ingest fallback only), the
validators themselves (B4, B5, B7, B8, B10), HTTP routes (B10), the read-only MCP tools of
H05 (deferred, see Open questions), the legacy `app/agents/**` turn loop (untouched).

## Design

- **Plan.** One PLANNER call (`planner.md`) over the brief and facts passed as documents
  (data, never instructions). Output `NovelPlan` (title, characters, places, N chapters × 3
  scenes with dates, facts used and word budget, chronology events, ending note). A
  programmatic check (N chapters, 3 scenes, every mandatory fact used, ISO dates, scene
  budget per chapter 1100–1350) triggers **one** replan with the error list. The plan is
  stored as a planner-source fact `plan.v1` (no schema change); cast, places, events and
  `fact_usage` are persisted idempotently (match by name / event id), so a crash during
  persistence is repaired on resume.
- **Chapter.** 3 WRITER calls (context: brief summary, novel synopsis, chapter plan, previous
  chapter summaries, last ~250 words of the previous scene in story order, forbidden terms,
  the recipient name) → `scene_accept` per scene, at most `MAX_SCENE_RETRIES = 2` rewrites.
  One EDITOR pass (polish + critic self-check) → one bounded length adjustment when out of
  the brief's range → `chapter_close`. A failure records the rejected text
  (`record_chapter_attempt`) and the editor rewrites with the failed validators' feedback;
  the budget `MAX_CHAPTER_RETRIES = 2` is read from persisted `validator_result` rows (CE2),
  counting only runs after the last `pre_publish` failure of the version (the repair round
  reopens the budget). Pass → `save_chapter_and_checkpoint` (CE1, CE3).
- **Publish.** `pre_publish` pass → `published`. Fail → in one transaction `blocked`,
  `repair_rounds = 1` and the named chapters' checkpoints reset (CE4); the editor repairs
  those chapters, `chapter_close` again, `pre_publish` again; a second failure ends in
  `stopped_error` with the version left `blocked`.
- **Resume.** `generate` on an existing novel reuses the stored plan and continues the latest
  non-published version at `first_incomplete_chapter`.
- **change_fact.** Update the fact, `create_version_from(latest published,
  copy_chapters_except=chapters_using_fact)`, editor rewrite of each affected chapter with the
  new value, `chapter_close`, `pre_publish`, publish. Derived character/place names equal to
  the old value are renamed. The previous version is never touched.
- **Observability.** Session = novel; one trace per `generate`/`change_fact`; spans
  `phase:plan`, `chapter:<n>`, `phase:publish`; role calls through `traced_complete` with
  `sink=repo`; scores `novel_cost_usd`, `novel_tokens`; flush at the end.
- **No validator registered for a point** → the point passes (the pipeline works before
  other blocks merge).

Deviation from Figure 5: a `chapter_close` failure is repaired by an editor rewrite of the
whole chapter with the evidence, not by rewriting only the flagged scene (cheaper on Haiku;
the scenes are already merged by the editor). *Clarified: Figure 5 now says so, and that
resume restarts the first incomplete chapter from its first scene; no longer a deviation.*

## Acceptance criteria

1. AC 1 — H01: a generation runs planner → writer (3 scenes per chapter) → editor for every
   chapter and publishes a version with N chapters. **T** (fake client) · **D** (live smoke).
   *Clarified (red-team R2): no role document carries the raw `free_text`; only facts
   extracted from it (`source = free_text`) do, and the stored brief keeps it. **T***
2. AC 2 — H06: scene retries ≤ 2, chapter retries ≤ 2 counted from persisted rows, one
   repair round; exhaustion ends in `stopped_error` with the reason. **T** · **I**.
3. AC 3 — M04: a run stopped after chapter k resumes at k+1 and never duplicates or rewrites
   a checkpointed chapter. **T**.
4. AC 4 — R05: `change_fact` creates version v+1, rewrites only the chapters using the fact,
   keeps version v published and unchanged. **I** (code review) · **D** when time allows.
   *Clarified (TLA+ divergence 2): the fact update, renames, brief, plan and v+1 commit in
   one `repo.transaction()`; a failure leaves the fact unchanged. **T***
5. AC 5 — every mandatory fact is assigned to ≥ 1 scene by the plan (programmatic check with
   one replan). **T**.
6. AC 6 — observability: one trace per run in the novel's session, role spans with prompt
   versions, cost score. **D** (Langfuse on the live smoke).

## Verification plan

- `backend/app/novel/tests/test_pipeline.py`: AC 1, AC 2 (scene/chapter bound), AC 3, AC 5
  with `FakeModelClient` (`# spec 007 / AC n`).
- Live smoke `uv run python -m app.novel.cli generate --brief
  app/novel/tests/fixtures/brief_smoke.json --chapters 1` with Haiku and Langfuse: AC 1, AC 6.
- AC 2, AC 4: review of `pipeline.py` against CE1–CE4 (mapping in the block's report for the
  B9 README).
- `ruff check app/novel`, `mypy --strict app/novel`.

## Open questions

- H05 (read-only MCP tools `query_story_bible`, `get_chapter_summary`) is deferred: the
  context is assembled by the pipeline and passed as documents. Recorded for wave C.
- Clarified during implementation (no scope change): the plan's chronology is made
  Lean-valid before writing (`app/novel/chronology.py`, B4's `diagnose`), because prose
  rewrites cannot repair chronology rows; each novel gets its own copy of `formal/lean`
  next to `HARNESS_DB` so concurrent runs do not share `Story.lean`; a pipeline-owned
  `no_placeholders` validator (scene_accept, chapter_close) rejects anonymised names.
- The plan is stored as fact `plan.v1` (kind `plan`): B4's `fact_usage_recorder` should
  skip kind `plan`.
- K1 has no method to rename a character or place; `change_fact` does it through a small
  helper in `app/novel/_bible_ext.py` over the repository's connection until B1 adds one.
