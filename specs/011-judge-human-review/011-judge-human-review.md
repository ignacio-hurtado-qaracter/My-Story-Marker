---
id: 011
title: B7 — LLM-as-judge and human review
status: approved         # approved 2026-09-24 on the user's delegation for this session
supersedes: null
programme: 004
block: B7
owns:
  - backend/app/judge/**
  - backend/app/prompts/judge_chapter.md
  - backend/app/prompts/judge_novel.md
  - evals/human-review/**
depends_on: [B1, B6]
provides: [validators judge_chapter, judge_novel]
consumes: [K1, K2, K3]
closes: [S01, S02]
docs:
  - docs/verification.md#llm-as-judge-and-human-review--i
  - docs/verification.md#validator-registry-and-execution-points
---

> **Approved 2026-09-24** on the user's delegation for this session (plan 004, deviation V6).
> Process 0 for this block is the programme's: spec 004 rows S01, S02 and decision D11.

## Motivation

The exam (§ 5b) asks for two semantic validators: an LLM-as-judge with a rubric scoring
continuity, tone, narrative quality and natural personalisation, with a score and a
justification per criterion; and a human review of at least one full novel with the same
rubric, compared with the judge. Decision D11 of spec 004: personalisation and quality
weigh the same, so a chapter that only "contains the brief" does not pass. Nothing today
judges prose ([verification.md](../../docs/verification.md#llm-as-judge-and-human-review--i)).

## Scope

**In.** One rubric in code (`app/judge/rubric.py`), rendered in Spanish for the human; the
`judge_chapter` validator at `chapter_close` and `judge_novel` at `pre_publish` (role
`judge`, read-only, K3); per-criterion Langfuse scores; the human-review protocol, a blank
YAML template and a comparison script human vs judge.

**Out.** Routing the judge's feedback back to the editor (the pipeline, B3, reads
`explanation`); calibration beyond one comparison table; multi-judge or debate; any store
write by the judge other than the `validator_result` and `llm_call` rows that `run_point`
and `traced_complete` already make.

## Design

- Rubric: `continuidad`, `tono`, `calidad_narrativa`, `personalizacion_natural`, 1–5 with
  anchors; the novel judge adds `final_satisfactorio` and a `contradicciones` list. The
  rubric text is appended to the judge prompts, so one definition serves model and human.
- Pass rule (D11): every criterion ≥ 3 **and** mean ≥ 3.5 **and** no blocking issue (the
  named defects fail a chapter whatever its score; for the novel, a contradiction is one).
- Chapter input (kept cheap): chapter text, the chapter's plan entry, **summaries** of the
  previous chapters of this version, a brief summary. Novel input: every chapter summary,
  first 300 words of chapter 1, last 400 words of the last chapter, the brief summary.
- Output: a validated pydantic schema via `traced_complete` (K2), prompt versioned by
  `load_prompt`. `run_point` persists and scores `validator:<name>`; the judge also scores
  `judge:<criterion>` (1–5) with the justification as comment.
- Evidence lines `"<criterion>: <n>/5 — <justification>"` are the persisted per-criterion
  scores; `compare.py` reads them back through `BibleRepository`.
- `ctx.extra["client"]` supplies the model client (default `ClaudeCodeModelClient()`);
  `ctx.extra["judge_enabled"] is False` skips with a pass, for fast runs.

## Acceptance criteria

| # | Criterion | Letter |
|---|---|---|
| AC 1 — S01, D11 | The pass rule fails a judgement with any criterion < 3, a mean < 3.5 or a blocking issue, and passes otherwise. | **T** |
| AC 2 — S01 | A live judge call on a Spanish sample chapter returns a schema-valid judgement with a score and a justification per criterion. | **D** (manual run, recorded in the commit body) |
| AC 3 — S02 | `compare.py` turns a filled review YAML and the judge results in the DB into a Markdown table per criterion with differences and mean absolute error. | **T** |
| AC 4 — S02 | `evals/human-review/` holds the protocol, the Spanish rubric and a blank template, both generated from `rubric.py`. | **I** |
| AC 5 | `ruff` and `mypy --strict` clean on `app/judge`. | **A** |

*Clarified (red-team R2): the judge's `brief/summary.json` never includes the raw `free_text`; its extracted facts reach the judge through the bible (`test_brief_summary_drops_free_text`, **T**).*

## Verification plan

| AC | Where |
|---|---|
| 1, 3 | `backend/app/judge/tests/test_judge.py` (`# spec 011 / AC n`) |
| 2 | Manual live call with Haiku; result in the `backend:` commit body |
| 4 | Review of `evals/human-review/` |
| 5 | Gate output in the commit body |

## Open questions

None. Judge reliability stays in the accepted-risk register ("Judge-model reliability").
