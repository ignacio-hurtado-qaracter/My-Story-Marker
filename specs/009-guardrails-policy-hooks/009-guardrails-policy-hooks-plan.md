---
spec: 009
status: approved          # approved 2026-09-24 on the user's delegation for this session
---

## Files to touch

- `backend/app/policy/__init__.py` — public surface, `register_validators()`.
- `backend/app/policy/normalise.py` — `normalise`, `term_variants`, `find_forbidden`, `Match`, `Term`.
- `backend/app/policy/engine.py` — `PolicyEngine`, `PolicyDecision`, injection markers.
- `backend/app/policy/validators.py` — the two validators and the constants.
- `backend/app/policy/hooks.py` — shared logic the two Claude Code hooks call.
- `backend/app/policy/tests/test_forbidden_words.py` — the tests.
- `backend/app/commons/db/authoritative/migrations/1300_forbidden_terms_global.sql` — seed.
- `.claude/settings.json`, `.claude/hooks/validate_chapter.py`, `.claude/hooks/policy_guard.py`,
  `.claude/hooks/README.md`.
- `.gitignore` — `.claude/hooks/*.log`.

## Steps

1. Spec and plan (`spec(009):`, `plan(009):`).
2. Normaliser, engine, validators, seed migration and tests (`backend:`). AC 1–5.
3. `.gitignore` line (`chore:`).
4. Hooks, settings and README, with sample runs in the body (`chore:`). AC 6–7.

## Verification mapping

| AC | Letter | Satisfied by |
|---|---|---|
| 1, 2, 4, 5 | T | `app/policy/tests/test_forbidden_words.py` |
| 3 | T · I | validator test; B3 loop review |
| 6, 7 | D | pipe runs in `.claude/hooks/README.md`, output in the commit body |

## Risks and stop conditions

- The seed migration changes the list of applied migrations that spec 005's test asserts
  (`["1000_init", "1001_tlc_rules"]`); that test is B1's and every block adding a migration
  breaks it — reported to the orchestrator, not edited here.
- A hook slower than 2 s on code edits → keep the stdlib fast path; if the chapter path
  cannot import `app`, the hook fails open with a warning (never blocks unrelated work).
