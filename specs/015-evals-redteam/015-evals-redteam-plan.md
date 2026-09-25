---
spec: 015
status: done              # closed 2026-09-25 with spec 015 (programme 004 close-out)
---

## Files to touch

- `evals/briefs/{ejemplo,b2-infantil,b3-injection,b4-temporal,b5-contradiction}.json` — the five briefs.
- `ejemplos/brief-ejemplo.json` — byte copy of `evals/briefs/ejemplo.json`.
- `evals/run_evals.py` — validate, generate (subprocess), collect, write JSON and tables.
- `evals/compare_iterations.py` — before/after diff and prompt versions → `evals/results/tuning.md`.
- `evals/README.md` — what each brief tests, how to run, mapping to EV1–EV3, E02, E05.

## Steps

1. Spec and this plan (`spec(015):`, `plan(015):`).
2. Briefs and the example copy; run `validate` on all five (AC 1, AC 2, AC 5) — `evals:`.
3. `run_evals.py`, `compare_iterations.py`, `README.md`; `ruff check` and `--help` (AC 3,
   AC 4, AC 7) — `evals:`.
4. Run phase (after `app.novel` merges): `--label before`, one prompt change, `--label
   after`, `compare_iterations.py before after`, PDF of `ejemplo` (AC 3, AC 4, AC 6).

## Verification mapping

| AC | Letter | Verification |
|---|---|---|
| 1 | I | Review of `evals/briefs/` and `evals/README.md` |
| 2 | D | `app.interview.cli validate` output in the step-2 commit body |
| 3 | D | `evals/results/<label>/table.md`, `evals/results.md` committed in step 4 |
| 4 | D | `evals/results/tuning.md` committed in step 4 |
| 5 | A | `exam/check.py` E02 glob; `cmp evals/briefs/ejemplo.json ejemplos/brief-ejemplo.json` |
| 6 | D | `ejemplos/novela-ejemplo.pdf` committed in step 4 |
| 7 | A | `uv run ruff check ../evals`; `--help` of both scripts |

## Risks and stop conditions

- The pipeline CLI's flags or novel-id handling differ from `generate --brief --novel-id
  --chapters`: adapt the single `_generate_cmd` function; if it needs a store write from
  the harness, stop (Process 0).
- Validator names differ from the table's columns: the column → names alias map is the only
  place to change; a validator with no row stays `—`.
- The Brief model changes (spec 006 revised): re-validate the briefs before running.
