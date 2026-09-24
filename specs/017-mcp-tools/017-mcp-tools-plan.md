---
spec: 017
status: approved          # approved 2026-09-24 on the user's delegation for this session
---

## Files to touch

- `backend/pyproject.toml`, `backend/uv.lock` — add `fastmcp==4.0.9` (shared-file commit).
- `backend/app/tools/{__init__,base,models,story,download}.py` and `tests/` — the tool layer.
- `backend/app/novel/context.py` — tool-backed builders for summaries and character sheet.
- `backend/app/novel/pipeline.py` — the writer and editor call sites switch to the
  tool-backed builders; nothing else. Needed because `context.py` only receives
  precomputed data and cannot reach the repository by itself.
- `backend/app/mcp_server/{__init__,__main__,server}.py`, `README.md`.
- `.mcp.json` — `story-maker` entry beside Playwright.

## Steps

1. Spec and plan.
2. Dependency commit (`fastmcp`).
3. Tool layer + tests. AC 1, 2, 7.
4. Context wiring. AC 3.
5. MCP server, README, `.mcp.json`, manual stdio check. AC 4–7.

## Verification mapping

| AC | Letter | Satisfied by |
|---|---|---|
| 1 | T | `app/tools/tests/test_tools.py::test_invalid_input_is_rejected` |
| 2 | T | `app/tools/tests/test_tools.py::test_list_novels_and_get_chapter` |
| 3 | T · I | `pytest app/novel`; review of `context.py` |
| 4 | D · I | stdio `tools/list` run in the commit body |
| 5, 6 | I | review of `server.py`, `README.md` |
| 7 | A | `ruff`, `mypy --strict` output |

## Risks and stop conditions

- The pipeline's documents change beyond the new character sheet → revert to the old
  builders and reopen.
- `app.export` absent at runtime → `download_novel` returns a typed error, never raises.
- Opening the live `data/harness.sqlite` while generations run → read-only URI only.
