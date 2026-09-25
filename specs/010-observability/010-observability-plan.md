---
spec: 010
status: done              # closed 2026-09-25 with spec 010 (programme 004 close-out)
---

## Files to touch

- `backend/pyproject.toml`, `backend/uv.lock` — add `langfuse` pinned (shared-file commit).
- `backend/app/commons/config.py` — `LANGFUSE_*` settings (with spec 005's settings commit).
- `backend/app/commons/observability/{__init__,protocol,noop,langfuse_observer,pricing,prompts,traced}.py`
  and `tests/`.
- `backend/app/prompts/README.md` — where role prompts live.

## Steps

1. Spec and plan (this commit).
2. Dependency commit (`langfuse`).
3. `Observer` protocol, `NoopObserver`, pricing, `get_observer()`. AC 1, 5.
4. `LangfuseObserver`, `prompts.py`, `traced_complete` with `llm_call` recording. AC 2–5.
5. Manual smoke against Langfuse Cloud; result in the commit body. AC 2, 3.

## Verification mapping

| AC | Letter | Satisfied by |
|---|---|---|
| 1 | T | `tests/test_cost.py::test_haiku_price_table` |
| 2 | D | Manual smoke (trace + span + generation + score), success line in commit body |
| 3 | D · I | Manual smoke of `load_prompt` twice; review of `prompts.py` |
| 4 | T | `tests/test_cost.py::test_traced_complete_records_call` |
| 5 | A | `ruff check`, `mypy --strict` output |

## Risks and stop conditions

- The installed SDK API differs from the docs → code against the installed source, note it.
- Network to Langfuse blocked → the smoke is recorded as failed and AC 2 stays open.
- `traced_complete` needs `llm_call` columns K1 lacks → add them in migration range 1000–1099.
