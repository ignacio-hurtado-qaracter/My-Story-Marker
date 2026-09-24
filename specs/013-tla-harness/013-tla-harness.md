---
id: 013
title: B9 — TLA+ model of the gift-novel harness flow
status: approved         # approved 2026-09-24 on the user's delegation (plan 004, V6)
supersedes: null
programme: 004
block: B9
owns: [formal/tla/**, specs/013-tla-harness/**]
depends_on: [B0 (docs), B3 design (final mapping, wave C)]
provides: []
consumes: [K1 (novel_version, chapter_version, checkpoint), K3 (validation points), K4 (hook points), K5 (change_fact, publish_version)]
closes: [T01, T02, T03, T04, T05]
docs:
  - docs/verification.md#model-checking--a
  - docs/verification.md#coverage-matrix
  - specs/004-exam-refactor-programme/004-exam-refactor-programme.md#2-cross-cutting-decisions
  - specs/004-exam-refactor-programme/004-exam-refactor-programme-plan.md#shared-contracts-fixed-here-so-wave-b-can-start-the-moment-wave-a-merges
---

> **Approved 2026-09-24** on the user's explicit delegation for this session (plan 004,
> deviation V6). Process 0 was run by the orchestrating session; the decisions it left to
> this block are recorded under [Open questions](#open-questions) with the choice taken.

## Motivation

Spec 004 § 1, row T01–T05: the exam asks for a TLA+ model of the harness flow
(configuration → planning → chapter writing → validation → publication, with retries,
checkpoint resume and reader regeneration), at least three safety invariants and one
liveness property, a TLC configuration on 5 chapters × 2 retries, a README mapping each
action to the code, and every counterexample documented with the change it caused. Today
`formal/tla/` does not exist, so all five items fail `exam/check.py`. Without the model, the
two properties the reader relies on most — a crash never duplicates or loses a chapter, and
a regeneration never overwrites the version already read — rest on inspection alone.

## Scope

**In.** T01–T05: `formal/tla/GiftNovelHarness.tla`, `GiftNovelHarness.cfg`, a pinned TLC
toolchain fetched by `formal/tla/run-tlc.sh` (the jar is git-ignored), the saved TLC output,
`COUNTEREXAMPLES.md`, and `README.md` with the action → code mapping.

**Out.** Everything owned by another block, in particular the pipeline code
(`backend/app/novel/**`, B3) and the repository (`backend/app/bible/**`, B1): the model
states the rules they must follow, it does not edit them. Also out, as in spec 004 Scope:
TLA+ of the MCP server, of concurrent regenerations, and of the prose itself (validator
outcomes are nondeterministic). Running TLC per generation is out: it runs in development.

## Design

One module models one novel. **Durable** variables stand for K1 rows that survive a crash
(`novel_version.status`, `novel_version.changed_chapters`, `chapter_version`, `checkpoint`,
the persisted `validator_result` rows); **volatile** variables stand for the pipeline's
memory (phase, current chapter and scene, in-memory retry counters) and are reset by
`Crash`. Validator outcomes at the three points of decision D4 (`scene_accept`,
`chapter_close`, `pre_publish`) are nondeterministic. `ChangeFact` models K5 on the latest
published version. Crashes and reader changes are bounded by constants so liveness is
checkable. Ghost variables record what the invariants need (published snapshots, retry
totals across crashes). The code mapping is written against the names fixed in plan 004 and
is marked "to be confirmed against code in wave C".

## Acceptance criteria

1. AC 1 — T01. `formal/tla/GiftNovelHarness.tla` models configuration, planning, scene
   writing and `scene_accept` with bounded retry, editor pass, `chapter_close` with bounded
   rewrite, checkpoint, `pre_publish` with one bounded repair round, publication, stop on
   error, crash and resume, and reader regeneration into a new version. **A** (TLC parses
   and explores it) · **I** (this review).
2. AC 2 — T02. The `.cfg` checks at least the invariants `TypeOK`, `NoUnvalidatedPublish`,
   `ResumeNoDupNoLoss`, `PreviousVersionKept`, `RetriesBounded`, and the liveness property
   that every generation reaches `Published` or `StoppedError` under weak fairness. **A**
3. AC 3 — T03. `GiftNovelHarness.cfg` sets 5 chapters and 2 retries (scene and chapter);
   `run-tlc.sh` finishes in under 10 minutes with no error, and its output is saved in
   `formal/tla/tlc-output.txt`. **A** · **D**
4. AC 4 — T04. `formal/tla/README.md` maps every action of the spec to a function or row
   of the expected code (`backend/app/novel/pipeline.py`, `backend/app/bible/repository.py`),
   marked "to be confirmed against code in wave C". **I**
5. AC 5 — T05. Every counterexample TLC found while the model was developed is recorded in
   `formal/tla/COUNTEREXAMPLES.md` (trace summary, invariant violated, fix in the model,
   rule it implies for the code), and the README links it. **I**

## Verification plan

| AC | Letter | Check | Where |
|---|---|---|---|
| AC 1 | A · I | TLC run; review of the module against this list | `formal/tla/tlc-output.txt`; this spec |
| AC 2 | A | `exam/check.py` T02 greps `INVARIANT` and `PROPERTY` in the `.cfg`; TLC reports no violation | `formal/tla/GiftNovelHarness.cfg`, `tlc-output.txt` |
| AC 3 | A · D | `formal/tla/run-tlc.sh`; output saved with state count and time | `formal/tla/tlc-output.txt` |
| AC 4 | I | Review of the mapping table; re-confirmed in wave C against B3's code | `formal/tla/README.md` |
| AC 5 | I | Review of each recorded trace against the TLC output that produced it | `formal/tla/COUNTEREXAMPLES.md` |

## Open questions

All closed on the delegation; recorded here as decisions.

1. **Plain TLA+ or PlusCal?** Plain TLA+: the durable/volatile split and the crash action
   are clearer as explicit variables than as PlusCal labels.
2. **Scenes per chapter in the model.** A constant `SCENES`, set to 3 (plan 004, V5) unless
   the state space forces fewer; the choice is recorded in the `.cfg`.
3. **Are scenes durable?** No. Plan 004 V4 stores text per chapter; an interrupted chapter
   restarts from its first scene, so its scene retry counter restarts with it. The chapter
   retry counter and the repair round are the budgets that must survive a crash.
4. **Repair round.** A failed `pre_publish` marks the version `blocked` and sends a
   nondeterministic non-empty subset of chapters back through the chapter loop, once
   (`MAX_REPAIR_ROUNDS = 1`); a second failure stops with an error.
   *Revised 2026-09-24 — tuning iteration 1 (approval delegated; status unchanged): the
   pipeline allows `MAX_REPAIR_ROUNDS = 2`; the `.cfg` follows and TLC was re-run with it
   (`formal/tla/tlc-output.txt`: no error, 5,492,531 distinct states, depth 127).*
5. **Toolchain.** `tla2tools.jar` v1.8.0 from the TLA+ GitHub releases, pinned by URL and
   SHA-256 in `run-tlc.sh`, downloaded into the git-ignored `formal/tla/tools/`.
