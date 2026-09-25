---
id: 015
title: B11 — Evals and red-team
status: implemented      # closed 2026-09-25 on the user's delegation (programme 004 close-out)
supersedes: null
programme: 004
block: B11
owns:
  - evals/**                      # except evals/human-review/ (B7)
  - ejemplos/brief-ejemplo.json   # ejemplos/README.md is B12's
depends_on: [B2, B3, B4, B5, B7, B8, B10]
provides: []
consumes: [K1, K3]                # BibleRepository reads; validator_result rows written via K3
closes: [EV1, EV2, EV3, E02, E05]
docs:
  - docs/verification.md#evals--t-offline--d-online
  - docs/verification.md#red-teaming--adversarial-testing--t--i
  - docs/definitions.md#brief
---

> **Approved 2026-09-24** on the user's delegation, as spec 004's plan, deviation V6,
> allows. Process 0 was the delegated one; the defaults below are recorded as decisions.
> This spec covers the **preparation phase**: briefs and harness. The runs themselves (and
> E05's PDF) happen once the generation pipeline (`app.novel`) is merged.

## Motivation

Spec 004 § 1.5 row EV1–EV3 is *absent*: there are no test briefs, no validator × brief
table and no documented tuning iteration. E02 (reproducible example brief) and E05
(example novel PDF) are pending. The exam (§ 5 "Evaluación del sistema") asks for five
briefs, one adversarial (injection in free text) and one designed to provoke a temporal
incoherence, a table of which validators passed per brief, and one tuning iteration with
before/after results tied to prompt versions.

## Scope

**In.** Five briefs in `evals/briefs/`; `ejemplos/brief-ejemplo.json`; a runner
`evals/run_evals.py` that validates each brief, calls the generation CLI as a subprocess,
reads results back through `BibleRepository` and writes `evals/results/<label>/*.json`,
`table.md` and the root index `evals/results.md`; `evals/compare_iterations.py` writing
`evals/results/tuning.md`; `evals/README.md`.

**Out.** The generation pipeline itself (B3/B8); any validator, policy or judge change
(B4/B5/B7); `evals/human-review/` (B7); the red-team log `docs/process/red-team-log.md`
(B12, written from `evals/results`); running generations in this phase; `ejemplos/README.md`.

## Design

- Briefs validate against `app.interview.brief.Brief` (spec 006) and are checked with
  `app.interview.cli validate`. `b5-contradiction` is *designed to be rejected*; its eval
  result is the rejection.
- The runner never writes the stores. It runs `python -m app.novel.cli generate --brief P
  --novel-id eval-<label>-<brief> [--chapters N]` with `HARNESS_DB` set, a per-brief timeout
  and up to three processes in parallel (one WAL database; the pipeline owns its per-run
  Lean directory). After the run it opens the database read-only through `BibleRepository`
  and reads `validator_result` (latest row per validator, chapter and scene),
  `policy_decision`, `cost_summary` and the latest `novel_version` status.
- A validator with no row shows `—`; a missing pipeline module is recorded as
  `pipeline_unavailable`, never a crash. The injection column combines the stored
  `free_text_injection` decisions with the deterministic `prescan_injection` of the brief.
- `compare_iterations.py` diffs two labels per brief and per validator and lists, per role,
  the `llm_call.prompt_version` values each label used.

## Acceptance criteria

1. **AC 1 — EV1.** `evals/briefs/` holds five briefs: an example, a child recipient, a
   prompt injection, a temporal incoherence, an age × genre/tone contradiction. — **I**
2. **AC 2 — EV1.** Four briefs validate; `b5-contradiction` is rejected with a
   contradiction and a missing field. — **D** (validate output in the commit body)
3. **AC 3 — EV2.** `run_evals.py` writes a table, briefs × validators, with ✅/❌/— plus
   final status, cost and tokens, into `evals/results/<label>/table.md` and
   `evals/results.md`. — **D** (after the pipeline merges)
4. **AC 4 — EV3.** `compare_iterations.py` writes `evals/results/tuning.md` with before and
   after per brief and validator and the prompt versions per role. — **D**
5. **AC 5 — E02.** `ejemplos/brief-ejemplo.json` equals `evals/briefs/ejemplo.json` and
   the brief has ten chapters. — **A** (`exam/check.py` glob + `cmp`)
6. **AC 6 — E05.** The example novel PDF is produced from `ejemplo.json` in the run phase.
   — **D** (deferred to the run phase)
7. **AC 7.** Both scripts pass `ruff check` and answer `--help`. — **A**

## Verification plan

AC 1, AC 5: review and `exam/check.py`. AC 2: `validate` run over the five briefs, pasted
into the `evals:` commit. AC 3, AC 4, AC 6: demonstrated in the run phase, results committed
under `evals/results/`. AC 7: `uv run ruff check ../evals` and `--help`.

## Open questions

None open. Decided on delegation: one shared database; per-brief timeout default 45 min;
`b3`/`b4`/`b2` use 3 chapters, `ejemplo` 10; the tuning iteration is before/after one
prompt change chosen from the "before" table.

## Closing note (2026-09-25)

Closed on the user's delegation (programme 004 close-out, Process 2 step 12). Evidence at
`proyecto-desde-cero` @ `0e8118c`: backend gate `ruff check .` clean, `mypy --strict .`
clean (290 files), `pytest` 1758 passed / 8 skipped / 1 failed. The one failure is
`tests/test_boundaries_mirror.py`, the spec 001 store-boundary guard, which flags file I/O
in the new modules; it is not an acceptance criterion of this spec and is left to the
author (`docs/process/README.md`, "Pendiente para el autor").

| AC | Satisfied by |
|---|---|
| 1 | I — `evals/briefs/` holds `ejemplo`, `b2-infantil`, `b3-injection`, `b4-temporal`, `b5-contradiction` |
| 2 | D — validate run in the `evals:` commit; `b5-contradiction` rejected (`evals/results.md`, "Rejected by brief validation") |
| 3 | D — `evals/results/before/table.md`, `evals/results/after/table.md`, `evals/results.md` |
| 4 | D — `evals/results/tuning.md` (before/after per brief and validator, prompt versions) |
| 5 | A — `exam/check.py` E02; `cmp ejemplos/brief-ejemplo.json evals/briefs/ejemplo.json` identical |
| 6 | D — `ejemplos/novela-ejemplo.pdf` from `ejemplo.json` (`novela-ejemplo-a` v1, `c0a9e90`) |
| 7 | A — `ruff check` clean; `run_evals.py --help` and `compare_iterations.py --help` answer |
