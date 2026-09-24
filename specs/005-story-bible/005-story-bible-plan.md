---
spec: 005
status: approved          # approved 2026-09-24 on the user's delegation for this session
---

## Files to touch

- `.gitignore` — ignore `data/`.
- `backend/app/commons/permissions/roles.py`, `backend/app/commons/config.py`,
  `backend/app/commons/permissions/table.py`, `backend/app/commons/permissions/inputs.py`
  — four new roles with empty file-store rows; `HARNESS_DB` and Langfuse settings (one
  shared-file commit). `backend/openapi.json` regenerated because `/permissions` lists roles.
- `backend/app/commons/db/authoritative/{__init__,connection,migrations}.py` and
  `migrations/1000_init.sql` — connection and migration runner.
- `backend/app/bible/{__init__,models,repository}.py` and `tests/` — K1.
- `backend/app/validators/{__init__,protocol,registry}.py` and `tests/` — K3 interface.

## Steps

1. Spec and plan (this commit).
2. Roles and settings (shared-file commit). AC 5.
3. Authoritative connection, migrations and `BibleRepository` with tests. AC 1–3, 5.
4. Validator protocol and registry with a test, after spec 010 step 2 provides `Observer`. AC 4, 5.
5. Migration `1001_tlc_rules` and the CE1–CE4 repository methods, with `run_id` set by
   `run_point`. AC 6. (Added 2026-09-24 with the spec revision; plan re-approved on delegation.)

## Verification mapping

| AC | Letter | Satisfied by |
|---|---|---|
| 1 | T | `app/bible/tests/test_repository.py::test_fact_usage_roundtrip` |
| 2 | T | `app/bible/tests/test_repository.py::test_chronology_json_format` |
| 3 | T | `app/bible/tests/test_repository.py::test_versions_keep_parent` |
| 4 | T | `app/validators/tests/test_registry.py::test_run_point_persists_and_scores` |
| 5 | A | `ruff check`, `mypy --strict`, `pytest -q` output in commit bodies |
| 6 | T | `app/bible/tests/test_repository.py::test_tlc_rules`, `app/validators/tests/test_registry.py` |

## Risks and stop conditions

- A legacy test enumerating roles asserts a fixed count → adapt minimally, note it.
- A wave-B block needs a column not here → it adds a migration in its own range.
- Needing any file outside the list above → stop, revise this plan.
