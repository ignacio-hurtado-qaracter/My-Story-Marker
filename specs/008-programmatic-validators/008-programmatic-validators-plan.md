---
spec: 008                 # the approved spec this plan implements
status: approved          # draft · approved · done
---

> **Approved** (2026-09-24) by the agent on the user's explicit delegation.

Implementation plan for [`008-programmatic-validators.md`](./008-programmatic-validators.md).

## Files to touch

- `backend/app/validators/programmatic/__init__.py` — `register_validators()`, exports.
- `backend/app/validators/programmatic/text.py` — normalisation, tokens, stopwords, edit distance, fact term matching.
- `backend/app/validators/programmatic/length.py` — `chapter_length`.
- `backend/app/validators/programmatic/names.py` — `exact_names`.
- `backend/app/validators/programmatic/coverage.py` — `fact_usage_recorder`, `brief_coverage`.
- `backend/app/validators/programmatic/schema.py` — `schema_role_output`, `schema_brief`.
- `backend/app/validators/programmatic/chronology.py` — `lean_chronology`.
- `backend/app/validators/programmatic/prose.py` — `prose_repetition`.
- `backend/app/validators/programmatic/tests/__init__.py`, `tests/test_programmatic.py`.

## Steps

1. Spec and plan (commits `spec(008):`, `plan(008):`). — all
2. Validators, registration and tests in one `backend:` commit. — AC 1–7

## Verification mapping

| AC | Letter | Satisfied by |
|---|---|---|
| AC 1 | T | `test_chapter_length_boundaries` |
| AC 2 | T | `test_exact_names_variants` |
| AC 3 | T | `test_brief_coverage_in_memory` |
| AC 4 | T | `test_lean_missing_toolchain` / `test_lean_runs` (skipif) |
| AC 5–7 | I | review note in the `backend:` commit body |

## Risks and stop conditions

- B2's `Brief` model or fact values differ from 004-contracts: matching is guarded and
  degrades to skipped-pass / value matching; a contract change reopens Process 0.
- A needed change to the `protocol.py` / `registry.py` API: stop (only additive bug fixes).
