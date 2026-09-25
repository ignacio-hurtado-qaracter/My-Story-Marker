---
spec: 012                 # the approved spec this plan implements
status: done              # closed 2026-09-25 with spec 012 (programme 004 close-out)
---

> **Approved** (2026-09-24) by the agent on the user's explicit delegation.

Implementation plan for [`012-lean-chronology.md`](./012-lean-chronology.md).

## Files to touch

- `formal/lean/lean-toolchain` — pinned Lean 4 stable toolchain.
- `formal/lean/lakefile.toml` — Lake package, library `Chronology`.
- `formal/lean/Chronology.lean` — library root, imports `Chronology.Basic`.
- `formal/lean/Chronology/Basic.lean` — model, `Bool` checks, `Prop` invariants.
- `formal/lean/Chronology/Generated/.gitkeep` — directory for the generated story.
- `formal/lean/.gitignore` — `.lake/` and the generated `Story.lean`.
- `formal/lean/examples/ok.json`, `formal/lean/examples/incoherent.json` — samples.
- `formal/lean/README.md` — model, invariants, install, run, harness wiring, L04.
- `backend/app/formal/__init__.py` — public surface.
- `backend/app/formal/lean_export.py` — `export_lean`.
- `backend/app/formal/lean_runner.py` — `LeanResult`, `find_lake`, `verify_chronology`.
- `backend/app/formal/tests/__init__.py`, `backend/app/formal/tests/test_lean.py`.

## Steps

1. Spec and plan (this commit). — all
2. Install elan and the toolchain; Lake project, `Basic.lean`, README, samples. — AC 2, AC 5
3. `lean_export.py`, `lean_runner.py`, tests. — AC 1, AC 3, AC 4

## Verification mapping

| AC | Letter | Verification | Where |
|---|---|---|---|
| AC 1 | T | `test_export_*` | `backend/app/formal/tests/test_lean.py` |
| AC 2 | A | `lake build` passes | `formal/lean/` |
| AC 3 | T | `test_verify_ok`, `test_verify_incoherent` (skip without `lake`) | same test file |
| AC 4 | T | `test_missing_toolchain` | same test file |
| AC 5 | I | README review | `formal/lean/README.md` |

## Risks and stop conditions

- `decide` too slow on a long novel → `native_decide` fallback, recorded in the generated
  file. A novel of hundreds of events is expected to stay well within the kernel's limits
  since the checks are quadratic at worst.
- The import-linter contract "Only commons.llm spawns subprocesses" lists its source
  modules explicitly and does not list `app.formal`; the runner's `subprocess` use is
  therefore not a breach today. If the owner of `pyproject.toml` adds `app.formal` to it,
  an `ignore_imports` entry for `app.formal.lean_runner -> subprocess` is required — a
  change to a shared file, not made by this block.
- The chronology JSON format changes in K1 → reopen Process 0 with B1.
