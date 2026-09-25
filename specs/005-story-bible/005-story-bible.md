---
id: 005
title: B1 — Authoritative story bible (contracts K1 and K3)
status: implemented      # closed 2026-09-25 on the user's delegation (programme 004 close-out)
supersedes: null
programme: 004
block: B1
owns:
  - backend/app/bible/**
  - backend/app/commons/db/authoritative/**
  - backend/app/validators/__init__.py
  - backend/app/validators/protocol.py
  - backend/app/validators/registry.py
depends_on: [B0]
provides: [K1, K3]
consumes: [K2]
closes: [M01, M02, R07]
docs:
  - docs/architecture.md#memory-and-context-budget
  - docs/architecture.md#storage-layout
  - docs/architecture.md#draft
  - docs/verification.md#guardrails--a-structural--t-behavioural
---

> **Approved 2026-09-24** on the user's delegation for this session (plan 004, deviation V6).
> Process 0 for this block is the programme's: decisions D1, D2, D6 of
> [spec 004](../004-exam-refactor-programme/004-exam-refactor-programme.md#2-cross-cutting-decisions)
> and the K1/K3 shapes fixed in
> [plan 004](../004-exam-refactor-programme/004-exam-refactor-programme-plan.md#shared-contracts-fixed-here-so-wave-b-can-start-the-moment-wave-a-merges).

## Motivation

Spec 004 § 1.4 rows M01 and M02, and § 1.2 row R07 (store half). Today SQLite is only a
derived index, so there is nowhere authoritative to keep the brief's facts, which scene uses
which fact, the chronology the Lean block proves, the versions a reader regeneration must
not overwrite, the forbidden-word lists and the validator results. Every wave-B block
(B2–B5, B7, B8, B10) needs one repository to code against.

## Scope

**In.**
- K1: one authoritative SQLite database at `HARNESS_DB` (default `data/harness.sqlite`,
  git-ignored), WAL and foreign keys on, migrations in the range `1000–1099`, and a
  `BibleRepository` that is the only code touching it. Tables: `novel`, `brief`, `fact`,
  `fact_usage`, `character`, `place`, `chronology_event`, `event_participant`,
  `novel_version`, `chapter_version`, `checkpoint`, `forbidden_term`, `policy_decision`,
  `validator_result`, `llm_call` (the last one for B6 cost totals).
- `chronology_json(novel_id)`: the export B8 turns into Lean.
- K3 interface: `ValidationPoint`, `ValidationContext`, `ValidationResult`, the `Validator`
  protocol, and the registry with `run_point` persisting results (K1) and scoring them (K2).
- Four new `AgentRole` members (`interviewer`, `planner`, `editor`, `judge`) and the
  `HARNESS_DB` setting, as a separate small commit to the shared files.

**Out.** Any concrete validator (B4), the brief schema and interview (B2), the pipeline and
hook points K4 (B3), forbidden-word normalisation (B5), HTTP routes over the bible (B10),
the Lean file itself (B8), any edit of `docs/` (B0).

## Design

- `app/commons/db/authoritative/` opens the database (`open_authoritative(path)`) and runs
  its own numbered migrations recorded in `authoritative_migrations`; the derived index's
  runner and sequence are untouched.
- `app/bible/models.py` holds frozen pydantic records; `app/bible/repository.py` holds
  `BibleRepository`. Nothing is deleted (D6): a new version is a new `novel_version` row
  with a `parent_version`; a chapter version stores its text and its SHA-256.
- Fact usage is recorded per scene (D6); chapters using a fact are derived.
- New roles get no row in the file-store write table: the gift-novel pipeline writes the
  authoritative database only (plan 004, V4), so no file permission is widened (D7).

## Acceptance criteria

| # | Criterion | Letter |
|---|---|---|
| AC 1 — M01 | A fact round-trips through the repository and the chapters that use it are derived from per-scene usage rows. | **T** |
| AC 2 — M02 | `chronology_json` returns exactly the K1 format (characters with nullable birth date, places, events with participants, kind and declared ages). | **T** |
| AC 3 — R07 | A new version keeps its parent; saving a chapter of the new version leaves the parent's text and hash unchanged. | **T** |
| AC 4 — K3 | `run_point` persists one `validator_result` per registered validator, turning an exception into a failed result, and sends one score per result. | **T** |
| AC 5 | `ruff` and `mypy --strict` are clean on the new packages; the existing suite stays green. | **A** |
| AC 6 — T02, T03 | The TLC counterexample rules hold: a chapter's text and its `complete` checkpoint are written in one transaction (CE1); chapter-close retries are countable from persisted `validator_result` rows by run id (CE2); `chapter_version` is unique per (novel, version, chapter), upserted, frozen once published, and rejected texts are kept in `chapter_attempt` (CE3); `repair_rounds` is set with `blocked` in one statement, and `create_version_from(parent, copy_chapters_except)` copies chapters and checkpoints in one transaction without touching the parent (CE4). | **T** |

## Verification plan

| AC | Where |
|---|---|
| 1–3 | `backend/app/bible/tests/test_repository.py` (`# spec 005 / AC n`) |
| 4 | `backend/app/validators/tests/test_registry.py` with `NoopObserver` |
| 6 | `backend/app/bible/tests/test_repository.py::test_tlc_rules`; run id in `test_registry.py` |
| 5 | Gate output in the commit bodies |

## Open questions

**Revised 2026-09-24** (scope grew): the TLA+ block's TLC run (spec 013) found counterexamples
CE1–CE4, relayed by the orchestrator; AC 6 and migration `1001_tlc_rules` implement them.
The spec went back to draft and was re-approved on the user's delegation the same day.

Otherwise none. Deferred: migrating to a server database, concurrent writers beyond WAL — accepted
under plan 004 V3 (light verification).

## Closing note (2026-09-25)

Closed on the user's delegation (programme 004 close-out, Process 2 step 12). Evidence at
`proyecto-desde-cero` @ `0e8118c`: backend gate `ruff check .` clean, `mypy --strict .`
clean (290 files), `pytest` 1758 passed / 8 skipped / 1 failed. The one failure is
`tests/test_boundaries_mirror.py`, the spec 001 store-boundary guard, which flags file I/O
in the new modules; it is not an acceptance criterion of this spec and is left to the
author (`docs/process/README.md`, "Pendiente para el autor").

| AC | Satisfied by |
|---|---|
| 1 | T — `app/bible/tests/test_repository.py` (fact round-trip, chapters from `fact_usage`) |
| 2 | T — `app/bible/tests/test_repository.py` (`chronology_json` in K1 format); consumed by `app/formal/tests/test_lean.py` |
| 3 | T — `app/bible/tests/test_repository.py` (new version keeps parent text and hash) |
| 4 | T — `app/validators/tests/test_registry.py` (`run_point`: one row per validator, exception → failed, one score each) |
| 5 | A — ruff and mypy --strict clean on `app/bible`, `app/validators`; `app/bible` has no boundary finding |
| 6 | T — `app/bible/tests/test_repository.py` (CE1–CE4 rules); migration `1001_tlc_rules.sql` |
