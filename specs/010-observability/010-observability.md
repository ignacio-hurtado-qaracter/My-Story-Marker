---
id: 010
title: B6 — Observability with Langfuse (contract K2)
status: implemented      # closed 2026-09-25 on the user's delegation (programme 004 close-out)
supersedes: null
programme: 004
block: B6
owns:
  - backend/app/commons/observability/**
  - backend/app/prompts/README.md
depends_on: [B0]
provides: [K2]
consumes: [K1]
closes: [O01, O02, O03]
docs:
  - docs/verification.md#runtime-observability--tracing--d
---

> **Approved 2026-09-24** on the user's delegation for this session (plan 004, deviation V6).
> Process 0 for this block is the programme's: spec 004 § 1.6 and the K2 shape fixed in
> [plan 004](../004-exam-refactor-programme/004-exam-refactor-programme-plan.md#shared-contracts-fixed-here-so-wave-b-can-start-the-moment-wave-a-merges).

## Motivation

Spec 004 § 1.6: the exam asks for one Langfuse session per novel, one trace per generation
or regeneration, a span per role and per tool with tokens, cost and latency, validator
scores on the trace, and prompts versioned in Langfuse. Today only a local turn record
exists, and every wave-B block needs one API to emit through.

## Scope

**In.** `Observer` protocol with `LangfuseObserver` and `NoopObserver`; `get_observer()`;
`traced_complete` around `ClaudeCodeModelClient.complete` with a bounded retry; a pinned
price table and `cost_usd`; prompt loading from `backend/app/prompts/<name>.md` published
to Langfuse prompt management with label `production`; per-call rows in the `llm_call` table
(K1) and totals per chapter and novel.

**Out.** The prompts themselves (each role's block), dashboards in the Langfuse UI, TLC
tracing (never traced, spec 004 § 1.6), sampling and PII scrubbing (fictional recipients,
plan 004).

## Design

- Session id = `novel_id`; `trace(name, session_id, metadata)` opens a root span on its own
  trace; `span("role:<role>" | "tool:<name>")` nests under the current observation;
  `generation(...)` records model, usage (`input`, `output`, `cache_read`,
  `cache_creation`), cost and latency, linked to the Langfuse prompt version.
- `get_observer()` is Langfuse when both keys are set and `LANGFUSE_ENABLED` is not `0`; a
  Langfuse failure never fails a generation (it degrades to a warning).
- Cost = tokens × pinned USD per million tokens of the requested model.
- Prompt version = the Langfuse version number; offline it is the content hash prefix.

## Acceptance criteria

| # | Criterion | Letter |
|---|---|---|
| AC 1 — O02 | `cost_usd` for `claude-haiku-4-5` matches the pinned table for input, output, cache read and cache write. | **T** |
| AC 2 — O01, O02 | With real keys, a trace carrying a session id, a span, a generation and a score reaches Langfuse. | **D** (manual smoke, recorded in the commit body) |
| AC 3 — O03 | `load_prompt` returns a stable version for unchanged content and publishes a new Langfuse version when it changes. | **D** (smoke) · **I** |
| AC 4 — O02 | `traced_complete` records one `llm_call` row per settled call with tokens, cost, latency and prompt version. | **T** (with the fake model client) |
| AC 5 | `ruff` and `mypy --strict` clean on the package. | **A** |

## Verification plan

| AC | Where |
|---|---|
| 1, 4 | `backend/app/commons/observability/tests/test_cost.py` (`# spec 010 / AC n`) |
| 2, 3 | Manual smoke run; the optional `live` test in the same folder, skipped by default |
| 5 | Gate output in the commit body |

## Open questions

None. The Langfuse key rotation noted in spec 004 is the user's.

## Closing note (2026-09-25)

Closed on the user's delegation (programme 004 close-out, Process 2 step 12). Evidence at
`proyecto-desde-cero` @ `0e8118c`: backend gate `ruff check .` clean, `mypy --strict .`
clean (290 files), `pytest` 1758 passed / 8 skipped / 1 failed. The one failure is
`tests/test_boundaries_mirror.py`, the spec 001 store-boundary guard, which flags file I/O
in the new modules; it is not an acceptance criterion of this spec and is left to the
author (`docs/process/README.md`, "Pendiente para el autor").

| AC | Satisfied by |
|---|---|
| 1 | T — `app/commons/observability/tests/test_cost.py` (pinned Haiku 4.5 prices) |
| 2 | D — manual smoke against Langfuse Cloud recorded in the `3878b60` commit body (session, span, generation, score) |
| 3 | D · I — `load_prompt` versions in the same smoke; prompt versions per role in `evals/results/tuning.md` |
| 4 | T — `test_cost.py` (`traced_complete` writes one `llm_call` row per settled call) |
| 5 | A — ruff and mypy --strict clean on `app/commons/observability` |
