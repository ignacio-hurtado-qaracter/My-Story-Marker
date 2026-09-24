---
id: 008
title: B4 — Programmatic validators
status: approved         # draft · approved · implemented · superseded
supersedes: null
programme: 004
block: B4
owns: [backend/app/validators/programmatic/**, specs/008-programmatic-validators/]
depends_on: [B1, B6, B8]
provides: [app.validators.programmatic.register_validators]
consumes: [K1 (BibleRepository), K2 (score via run_point), K3 (validator protocol), verify_chronology (spec 012)]
closes: [V01, V02, V03, V04, V06, X02]
docs:
  - docs/verification.md#validator-registry-and-execution-points
  - docs/definitions.md
  - specs/004-exam-refactor-programme/004-contracts.md
---

> **Approved** (2026-09-24) by the agent on the user's explicit delegation of all
> approvals for programme 004.

## Motivation

Spec 004 § 1 rows V01–V04 and V06: chapter length, exact names and brief coverage must be
named validators at fixed points, persisted in SQLite and scored in Langfuse; the brief and
role outputs are reported as schema validators; the Lean 4 chronology gates publication.
Invariants 11–13 of [`definitions.md`](../../docs/definitions.md) are "checked by named
validators" and none existed. Without them the pipeline (B3) has no programmatic gate and
the bible's "chapters using each fact" (M01, needed by the reader and `change_fact`) stays
empty.

## Scope

**In.** The concrete validators below, in `backend/app/validators/programmatic/`, and
`register_validators()` (K3 registration convention, 004-contracts). The prose linter X02.

**Out.** The protocol and registry (`protocol.py`, `registry.py`, spec 005) — unchanged.
Calling `run_point` from the pipeline (B3), forbidden terms and policy (B5), the judge (B7),
the visual check (B10), the Lean model itself (spec 012). No new tables or migrations.

## Design

Each validator is a frozen dataclass with `name`, `point` and `run(ctx)`; it only reads
`ctx` and the repository, except `fact_usage_recorder` and `brief_coverage`, which write
`fact_usage` rows through `BibleRepository.record_fact_usage` (K1). Every result carries
evidence and a Spanish explanation phrased as feedback for the role named in the table.
Results are persisted and scored by `run_point` (V06), never by the validator.

| Name | Type | Point(s) | Blocking? | Feedback target |
|---|---|---|---|---|
| `chapter_length` | word count vs brief `length` (default 1000–1500) | chapter_close, hook | yes | writer |
| `exact_names` | near-miss variants of canonical names (accent, case, 1 edit) | chapter_close, hook | yes | editor |
| `fact_usage_recorder` | fact detection, writes `fact_usage` | chapter_close | no (always passes; reports coverage so far) | — (bible) |
| `brief_coverage` | every mandatory fact in ≥ 1 chapter (SQLite + text) | pre_publish | yes | writer of the assigned chapter |
| `schema_role_output` | pydantic re-validation of `ctx.extra["role_output"]` | scene_accept | yes | role that produced it |
| `schema_brief` | stored brief vs `app.interview.brief.Brief` or `schemas/brief.v1.json` | pre_publish | yes (skipped-pass if no schema is available) | interviewer |
| `lean_chronology` | `repo.chronology_json` → `verify_chronology` (Lean 4) | pre_publish | yes (toolchain missing = fail) | editor |
| `prose_repetition` | repeated words / 4-grams, Spanish AI clichés (X02) | chapter_close, hook | soft: fails only if ≥ 3 clichés or ≥ 3 repetition hits | editor |

**Matching rules** (documented in the module docstrings):

- *Normalisation*: casefold, accents stripped, non-letters to spaces.
- *Names*: canonical tokens from characters, `novel.recipient_name`, the brief recipient,
  pets and people, and `*.name` facts. Only capitalised text tokens are compared; a token is
  a variant when it differs from a canonical token only in case/accents, or is one edit
  away (both ≥ 4 letters). Stoplist words, other canonical tokens, and words that also
  appear lowercase in the chapter are never variants.
- *Facts*: a value of ≤ 3 words matches as a normalised phrase; a longer value (and every
  memory, by its title) matches when ≥ 50 % of its key terms — content words of ≥ 5
  letters not in the stoplist, plus capitalised words of ≥ 3 letters — appear in one
  chapter.
- *Coverage*: a mandatory fact is covered when the text of some chapter of the version
  renders it (D11: presence in the prose, not a row). Missing `fact_usage` rows for a
  rendered fact are backfilled and reported; a row without rendering is reported as stale.

`ctx.extra` keys read: `brief` (dict, for `length` and names), `plan` (dict, for the
chapter a missing fact was assigned to), `role_output` (a pydantic model, or a dict with
`role_output_model`, a pydantic model class).

## Tuning iteration 1 (revision, 2026-09-24)

> Approval delegated by the user for this session; status stays `approved`. Reason: the
> 'before' evals (`evals/results/before/`) stopped `b2` and `b3` on `brief_coverage` for
> memories the chapters told in full, and stopped `b4` at plan stage on a `noAfterExit`
> false positive.

- **Memory coverage.** A title of ≤ 3 words used to need the exact phrase ("El caracol
  campeón"), so "los caracoles de Martina…" did not count. Now a memory is covered when a
  chapter contains **≥ half (and ≥ 1) of the title's content words, or ≥ 30 % of the
  description's content words**, words folded by `app.policy.normalise` (case, accents,
  plurals: `caracoles` → `caracol`). Content words have ≥ 4 letters and are not
  stopwords, digits, generic title words ("primera", "última"…) or names from the brief, so
  a name alone never proves a memory. The rule is in the docstring of `coverage.py`.
- **`noAfterExit` mirror.** `diagnose` marked **every** participant of a death or departure
  event as exited (in `b4`, the recipient who buries his dog), while Lean exits only the
  first participant; and both ordered by `seq`. Now, like the revised Lean check (spec 012),
  only the first participant exits and only a **later story date** counts as an appearance
  after exit; a flashback dated before the exit and the exit day itself pass.

## Acceptance criteria

1. AC 1 — V01: `chapter_length` passes inside the brief range (inclusive), fails outside,
   score decreases with distance and the explanation says how many words to add or cut. **T**
2. AC 2 — V02: `exact_names` reports an accent variant ("Lucia" for "Lucía") and a one-edit
   misspelling ("Tobby" for "Toby") with the canonical form, and does not flag the
   canonical names or common words. **T**
3. AC 3 — V03: `brief_coverage` over an in-memory bible fails listing a mandatory fact that
   no chapter renders and passes once it is rendered; `fact_usage_recorder` writes the rows. **T**
   *Revised (tuning 1): memories by the content-word rule above
   (`test_memory_coverage_content_words`). **T***
4. AC 4 — L03/V06: `lean_chronology` fails with an explanation when `lake` is missing, and
   runs Lean when present. **T** (skip-marked by toolchain presence)
   *Revised (tuning 1): `diagnose` agrees with Lean on `noAfterExit` on the story axis
   (`app/formal/tests/test_lean.py::test_no_after_exit_is_on_the_story_axis`). **T***
5. AC 5 — V04: `schema_role_output` and `schema_brief` report schema results as named
   validators, guarded against B2 not being merged. **I** (review of the guarded imports)
6. AC 6 — V06: `register_validators()` registers every validator of the table at its
   point(s); results reach SQLite and Langfuse through `run_point`. **I** (review; the
   persistence path is tested by spec 005)
7. AC 7 — X02: `prose_repetition` is soft as specified. **I**

## Verification plan

`backend/app/validators/programmatic/tests/test_programmatic.py`, tests tagged
`# spec 008 / AC n`: AC 1 (length boundaries), AC 2 (variants), AC 3 (coverage over
`BibleRepository.open(":memory:")`), AC 4 (`skipif` on `find_lake()`). AC 5–7 by review in
the `backend:` commit. Gate: `ruff check`, `mypy --strict`, `pytest -q` on `app/validators`.

## Open questions

None open. Decided on delegation: soft prose linter to avoid rewrite loops; coverage
requires text rendering (D11) rather than trusting rows; the Lean evidence names events by
a Python-side diagnosis of the same four invariants, since `LeanResult` only names the
invariant.
