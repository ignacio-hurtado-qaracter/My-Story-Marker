---
id: 012
title: B8 — Lean 4 formal validator of the story chronology
status: approved         # draft · approved · implemented · superseded
supersedes: null
programme: 004
block: B8
owns: [formal/lean/**, backend/app/formal/**, specs/012-lean-chronology/]
depends_on: [B1]
provides: [verify_chronology]
consumes: [K1 (chronology JSON), K3 (validator protocol, wiring later), K2 (score, wiring later)]
closes: [L01, L02, L03, L04]
docs:
  - docs/verification.md#formal-verification--theorem-proving--a
  - docs/domain-knowledge.md#figure-5--story-time-against-discourse-time
  - specs/004-exam-refactor-programme/004-exam-refactor-programme.md#1-confrontation-docs-against-the-exam-brief
---

> **Approved** (2026-09-24) by the agent on the user's explicit delegation of all
> approvals for programme 004.

## Motivation

Spec 004 § 1, row L01–L04: Lean 4 must verify the **story's chronology** — a Lean file
generated from the authoritative data, with events, moment, participants, place and birth
dates, checked by `lake build`, gating publication. Row M02 supplies the chronology table
it reads. Today nothing in the repository proves that a novel's timeline is coherent; the
programmatic and semantic validators sample it, Lean checks every event against every
invariant.

## Scope

**In**

- A core-Lean (no Mathlib) Lake project in `formal/lean/` with library `Chronology`, the
  toolchain pinned in `formal/lean/lean-toolchain`.
- The model and four invariants in `formal/lean/Chronology/Basic.lean`: `temporalOrder`,
  `agesCoherent`, `noBilocation`, `noAfterExit`, each a `Bool` check with a `Prop` wrapper.
- `backend/app/formal/lean_export.py`: `export_lean(chronology, novel_id) -> str` from the
  chronology JSON of K1 (`chronology_json`, produced by the story-bible block).
- `backend/app/formal/lean_runner.py`: `verify_chronology(...) -> LeanResult`, which writes
  the generated file, runs `lake build` and names the failed invariants; a missing
  toolchain is a result, not a crash.
- Two sample chronologies (`formal/lean/examples/ok.json`, `incoherent.json`) and light
  tests.
- `formal/lean/README.md`: what is modelled, the invariants, how to run, how the harness
  calls it, the L04 statement.

**Out**

- Registering the runner as a `pre_publish` validator (K3/K4) and sending the Langfuse
  score (K2): done by the pipeline and validators blocks (B3, B4, B6), which call
  `verify_chronology`.
- Producing the chronology JSON from SQLite: B1/B2 (`chronology_json`).
- Editing `backend/pyproject.toml`, `uv.lock`, `docs/` (shared files owned elsewhere).
- Mathlib, calendars other than the proleptic Gregorian one, time of day.

## Design

- **Dates** are Gregorian `YYYY-MM-DD`. The exporter converts each to a day number (days
  since 0000-03-01, civil-from-days algorithm) and also passes `(y, m, d)` for births and
  events, so Lean computes full years with integer arithmetic on `Nat` only.
- **Lean model.** `Character (id, birth : Option Date)`, `Place (id)`,
  `Event (id, seq, date, place, participants, kind, declaredAges)` with
  `kind : normal | death | departure`. `Story := characters, places, events`.
  `validStory s = temporalOrder s && agesCoherent s && noBilocation s && noAfterExit s`.
- **Generated file** `formal/lean/Chronology/Generated/Story.lean` (regenerated per run,
  git-ignored) defines `def story : Story`, one theorem per invariant proved `by decide`
  (`story_temporalOrder`, `story_agesCoherent`, `story_noBilocation`, `story_noAfterExit`)
  and `story_ok : validStory story = true`. A false invariant makes `decide` fail, so
  `lake build` fails and the error names the theorem. *Clarified in implementation:* the
  proofs use `decide +kernel` (plain `decide` hits `maxRecDepth` past ~100 events); the
  exporter lists events by `seq` (duplicate `seq` is rejected) so `temporalOrder` checks
  adjacent pairs, lifted to all pairs by a proof; each event carries a precomputed `day`
  that Lean re-checks against its date (`datesConsistent`).
- **Identifiers.** Ids and names are never spliced as Lean identifiers: ids become
  `String` literals escaped by the exporter; names appear only in escaped string
  literals. The module name is fixed, so a hostile `novel_id` cannot change the file path.
- **Runner.** Resolves `lake` from `PATH` or `~/.elan/bin`, runs
  `lake build Chronology.Generated.Story` with a timeout, parses `story_<invariant>` from
  the output, returns `LeanResult(passed, failed_invariants, output, lean_file)`.
- **Harness wiring (described, done later).** At `pre_publish` the validator calls
  `verify_chronology`; `passed=False` blocks the version and returns the failed invariants
  and Lean's output to the editor as feedback; the result is the Langfuse score
  `lean_chronology` (1 / 0).

## Acceptance criteria

| AC | Criterion | Req | Letter |
|---|---|---|---|
| AC 1 | `export_lean` turns the chronology JSON into a Lean file that imports `Chronology` and defines `story` and the five theorems; hostile ids and names are escaped | L01 | **T** |
| AC 2 | `formal/lean/` is a Lake project with a pinned toolchain and at least four invariants as `def` in `Basic.lean`; `lake build` passes on the library | L02 | **A** |
| AC 3 | `verify_chronology` on `ok.json` returns `passed=True`; on `incoherent.json` returns `passed=False` naming `agesCoherent` and `noBilocation` | L03 | **T** |
| AC 4 | Without `lake`, `verify_chronology` returns `passed=False` with a "toolchain missing" explanation and does not raise | L03 | **T** |
| AC 5 | `formal/lean/README.md` states what is modelled, how the harness gates on it, and the L04 status (a real case, or why none was found yet) | L04 | **I** |

## Verification plan

- AC 1, AC 3, AC 4: `backend/app/formal/tests/test_lean.py` (`# spec 012 / AC n`); the
  AC 3 tests skip when `lake` is not found.
- AC 2: `lake build` in `formal/lean/`, run by the AC 3 test and by hand; `exam/check.py`
  L02 grep.
- AC 5: review of the README against this spec.
- Gate: `ruff check app/formal && mypy --strict app/formal && pytest -q app/formal`.

## Open questions

Closed on delegation: day numbers over `(y,m,d)` only (both are passed); `by decide`
first, `native_decide` only if the kernel is too slow (recorded in the generated file);
"first participant" of a death/departure event is the one who exits. L04's real case is
recorded once a real novel is exported (B11); until then the README records why none has
been found.
