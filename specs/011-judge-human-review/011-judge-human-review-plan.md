---
spec: 011
status: approved          # approved 2026-09-24 on the user's delegation for this session
---

## Files to touch

- `backend/app/judge/{__init__,rubric,models,validators,compare}.py` — rubric, output
  schemas, the two validators, `register_validators()`, the comparison logic.
- `backend/app/judge/tests/test_judge.py` — pass rule and comparison tests.
- `backend/app/prompts/judge_chapter.md`, `backend/app/prompts/judge_novel.md` — prompts.
- `evals/human-review/{README.md,rubrica.md,review-template.yaml,compare.py}` — protocol,
  rendered rubric and template, thin wrapper over `app.judge.compare`.

## Steps

1. Spec and plan.
2. Rubric, schemas, pass rule, validators, prompts, tests. AC 1, 2, 5.
3. Comparison module and `evals/human-review/`. AC 3, 4.

## Verification mapping

| AC | Letter | Satisfied by |
|---|---|---|
| 1 | T | `test_judge.py::test_pass_rule` |
| 2 | D | Live Haiku call on a ~300-word sample chapter; scores and seconds in the commit body |
| 3 | T | `test_judge.py::test_compare_tiny_db` |
| 4 | I | Review of `evals/human-review/` |
| 5 | A | `ruff check app/judge`, `mypy --strict app/judge` |

## Risks and stop conditions

- The plan dict shape (B3) is unknown → the validator looks up the chapter entry
  defensively and omits it when absent.
- Chapter summaries missing → fall back to the chapter's first and last words.
- Haiku over-reports blocking issues and blocks every chapter → tighten the prompt; if the
  pass rule itself must change, reopen this spec.
