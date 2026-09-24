---
id: 006
title: B2 — Interview and brief
status: approved         # approved 2026-09-24 on the user's delegation for this session
supersedes: null
programme: 004
block: B2
owns:
  - backend/app/interview/**
  - backend/schemas/brief*.json
  - backend/app/prompts/interviewer.md
  - backend/app/prompts/fact_extractor.md
depends_on: [B1, B6]
provides: [Brief, ingest_brief]
consumes: [K1, K2]
closes: [C01, C02, C03, C04, V04, R04]
docs:
  - docs/definitions.md#brief
  - docs/definitions.md#recipient
  - docs/definitions.md#fact
  - docs/verification.md#red-teaming--adversarial-testing--t--i
---

> **Approved 2026-09-24** on the user's delegation for this session (plan 004, deviation V6).
> Process 0 for this block is the programme's: decisions D2, D7 and D9 of
> [spec 004](../004-exam-refactor-programme/004-exam-refactor-programme.md#2-cross-cutting-decisions)
> and the Brief contract in
> [004-contracts](../004-exam-refactor-programme/004-contracts.md#brief-b2-provides-appinterviewbriefbrief-pydantic-json-schema-backendschemasbriefv1json).

## Motivation

Spec 004 § 1.1 rows C01–C04 and § 1.5 row V04 (brief half): no interviewer exists, the
brief has no schema, nothing detects missing data or contradictions, and pasted free text
has no untrusted-data path. Without this block the planner receives holes and fills them
with invention ([Brief, failure mode](../../docs/definitions.md#brief)).

## Scope

**In.** C01–C04, V04 (brief half), R04 (the `dedication` field stored on the novel).

- `Brief` pydantic model with the contract shape and Spanish enum values; JSON Schema
  exported to `backend/schemas/brief.v1.json`.
- `validate_brief` → missing fields, contradictions, schema errors.
- Free-text fact extraction as untrusted data, with a deterministic injection pre-scan.
- `Interviewer` agent (one turn = one model call), CLI and three API routes.
- `ingest_brief` into the story bible (K1), as fixed by the contracts page.

**Out.** Planning from the brief (B3), forbidden-word matching in prose (B5), the reader's
rendering of the dedication (B10), evals and red-team logs (B11), any edit to `docs/`.

## Design

**Contract.** The `Brief` shape is exactly the one on the contracts page. `genre` and `tone`
use the contract's Spanish values; the docs' English list names the same concepts
(D9: prose and user-facing values in Spanish).

**Validation** ([Brief § Validation](../../docs/definitions.md#brief)). `validate_brief(data)`
returns `BriefReport(valid, missing, contradictions, errors)`:

1. *Missing*: `recipient.name`, `recipient.age`, ≥1 trait, ≥1 memory, `genre`, `tone`,
   `length`, `dedication` — reported by dotted path, empty strings and lists count as missing.
2. *Contradictions* (each names both fields):
   - age < 12 with `tone: oscuro`; age < 12 with `genre: romance`; age < 16 with
     `genre: romance` and `tone: oscuro` (rule 2);
   - `recipient.birth_date` inconsistent with `recipient.age` by more than one year;
   - a memory dated before the recipient's birth date, or in the future;
   - `length.words_min > length.words_max`;
   - a mandatory element or memory mentioning a forbidden term (rule 3).
3. *Errors*: schema errors from the pydantic model (the source of the exported schema).

**Free text** is untrusted: passed to the extractor only as a `Document` (delimited data,
[DATA_STATEMENT](../../backend/app/commons/llm/protocol.py)), never inside the instruction.
Output: candidate people, pets, places, memories, traits, plus `injection_suspected` and
`injection_reason`. A deterministic pre-scan for injection markers (Spanish and English)
runs first and logs `policy=free_text_injection` through `log_policy_decision` whatever the
model says; the model's own suspicion is logged too.

**Interviewer.** Role `INTERVIEWER`, prompt `interviewer.md`. Input: the current partial
brief (a document) and the user's last answer (a document, untrusted). Output: updated
fields, next question in Spanish, `done`. `done` is only honoured when `validate_brief`
passes; otherwise the next question asks about the first missing field or contradiction,
deterministically. The Langfuse session is the novel id, created at the start (`--novel-id`
accepted) so interview and generation share one session.

**Ingest.** `ingest_brief(repo, brief, *, novel_id=None, observer=None) -> str` as on the
contracts page: refuses an invalid brief (`InvalidBriefError` carrying the report); stores
the brief and the `brief_schema` validator result (point `hook`) and a Langfuse score;
facts with stable keys and kinds, mandatory flags; characters (recipient, people, pets as
role `mascota`) with birth dates; places; novel-scope forbidden terms; `dedication` and
`recipient_name` on the novel. Free-text facts are added with `source="free_text"`, never
mandatory.

**API.** `POST /interview/validate`, `POST /interview/briefs`, `POST /interview/turn`.
**CLI.** `python -m app.interview.cli {interview --out PATH [--novel-id ID] | validate --brief PATH | ingest --brief PATH}`.

## Acceptance criteria

1. AC 1 — C03: a brief without traits and dedication is reported with both paths in
   `missing` and `valid=false`. **T**
2. AC 2 — C03: age 6 with `genre: romance` (and with `tone: oscuro`) is reported as a
   contradiction naming both fields. **T**
3. AC 3 — C02, V04: `backend/schemas/brief.v1.json` is exported from the model and
   `export_schemas.py --check` passes. **A**
4. AC 4 — C01, R04: `ingest_brief` creates the novel with dedication and recipient name,
   mandatory facts (`recipient.name`, each person, pet, memory, element), characters with
   birth dates, novel-scope forbidden terms and a passed `brief_schema` result. **T**
5. AC 5 — C04: a Spanish injection string in free text is flagged by the pre-scan and
   logged as a `free_text_injection` policy decision. **T**
6. AC 6 — C04: one live extractor call on a Spanish anecdote with an injection attempt
   returns facts and ignores the instruction. **D**
7. AC 7 — C01: the interviewer, CLI and routes exist and each model call runs in a
   `role:interviewer` span. **I**

## Verification plan

| AC | Where |
|---|---|
| 1, 2, 4, 5 | `backend/app/interview/tests/test_brief.py`, `# spec 006 / AC n` |
| 3 | `uv run python scripts/export_schemas.py --check`; `tests/test_schema_export.py` |
| 6 | manual run, result in the block report and the closing commit |
| 7 | review note in the closing commit; `openapi.json` regenerated |

## Open questions

None open. Deferred: a live interviewer conversation eval (B11).
