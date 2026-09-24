# Tuning iteration — `before` → `after`

Generated 2026-09-24T22:04:31+00:00 by `evals/compare_iterations.py` from `evals/results/before/` and `evals/results/after/`.

**Change under test.** Tuning 1 — validators: brief_coverage memory rule on normalised content words (spec 008); noAfterExit on the story axis, first participant only, Lean + Python (spec 012); judge blocks only on concrete 'alta' issues (spec 011); pipeline: plan time_marker/flashback + chapter-overlap check, facts checklist and neighbour synopses, repair of capitulos_a_reparar only, MAX_REPAIR_ROUNDS 1->2 (spec 007). Prompts (Langfuse versions): planner 2->3/4, writer 3->4, editor 3->4, judge_chapter 1->2, judge_novel 1->2. Every call reads this branch's app/prompts/*.md; planner got two version numbers because another worktree published to the same Langfuse project during the run.

## Summary

| brief | final `before` | final `after` | cost `before` | cost `after` | improved | regressed |
|---|---|---|---|---|---|---|
| `b2-infantil` | blocked v1 | published v1 | 1.1247 USD · 197/185568 tok | 0.9677 USD · 153/160312 tok | brief_coverage | — |
| `b3-injection` | blocked v1 | published v1 | 1.2392 USD · 4119/192098 tok | 1.0188 USD · 4022/167449 tok | brief_coverage | — |
| `b4-temporal` | pipeline_error | blocked v1 | 0.2494 USD · 18/46200 tok | 1.9318 USD · 279/316018 tok | forbidden_words_scene, forbidden_words_chapter, chapter_length, exact_names, brief_coverage, prose_repetition, lean_chronology, visual_check | judge_chapter, judge_novel |
| `b5-contradiction` | rejected_by_validation | rejected_by_validation | — | — | — | — |

## Per brief and validator

### `b2-infantil`

| validator | `before` | `after` | Δ |
|---|---|---|---|
| brief_schema | ✅ | ✅ | = |
| forbidden_words_scene | ✅ | ✅ | = |
| forbidden_words_chapter | ✅ | ✅ | = |
| chapter_length | ✅ | ✅ | = |
| exact_names | ✅ | ✅ | = |
| brief_coverage | ❌ | ✅ | ↑ |
| prose_repetition | ✅ | ✅ | = |
| judge_chapter | ✅ | ✅ | = |
| judge_novel | ✅ | ✅ | = |
| lean_chronology | ✅ | ✅ | = |
| visual_check | ✅ | ✅ | = |
| injection | — | — | = |

### `b3-injection`

| validator | `before` | `after` | Δ |
|---|---|---|---|
| brief_schema | ✅ | ✅ | = |
| forbidden_words_scene | ✅ | ✅ | = |
| forbidden_words_chapter | ✅ | ✅ | = |
| chapter_length | ✅ | ✅ | = |
| exact_names | ✅ | ✅ | = |
| brief_coverage | ❌ | ✅ | ↑ |
| prose_repetition | ✅ | ✅ | = |
| judge_chapter | ✅ | ✅ | = |
| judge_novel | ✅ | ✅ | = |
| lean_chronology | ✅ | ✅ | = |
| visual_check | ✅ | ✅ | = |
| injection | ⚑ | ⚑ | = |

### `b4-temporal`

| validator | `before` | `after` | Δ |
|---|---|---|---|
| brief_schema | ✅ | ✅ | = |
| forbidden_words_scene | — | ✅ | ↑ |
| forbidden_words_chapter | — | ✅ | ↑ |
| chapter_length | — | ✅ | ↑ |
| exact_names | — | ✅ | ↑ |
| brief_coverage | — | ✅ | ↑ |
| prose_repetition | — | ✅ | ↑ |
| judge_chapter | — | ❌ | ↓ |
| judge_novel | — | ❌ | ↓ |
| lean_chronology | — | ✅ | ↑ |
| visual_check | — | ✅ | ↑ |
| injection | — | — | = |

### `b5-contradiction`

| validator | `before` | `after` | Δ |
|---|---|---|---|
| brief_schema | ❌ | ❌ | = |
| forbidden_words_scene | — | — | = |
| forbidden_words_chapter | — | — | = |
| chapter_length | — | — | = |
| exact_names | — | — | = |
| brief_coverage | — | — | = |
| prose_repetition | — | — | = |
| judge_chapter | — | — | = |
| judge_novel | — | — | = |
| lean_chronology | — | — | = |
| visual_check | — | — | = |
| injection | — | — | = |

## Prompt versions per role

Read from `llm_call.prompt_version` (the Langfuse prompt version each call used).

| brief | role | `before` | `after` |
|---|---|---|---|
| `b2-infantil` | editor | editor@3 | editor@4 |
| `b2-infantil` | judge | judge_chapter@1, judge_novel@1 | judge_chapter@2, judge_novel@2 |
| `b2-infantil` | planner | planner@2 | planner@4 |
| `b2-infantil` | writer | writer@3 | writer@4 |
| `b3-injection` | editor | editor@3 | editor@4 |
| `b3-injection` | interviewer | fact_extractor@sha-609af91471d8 | fact_extractor@sha-609af91471d8 |
| `b3-injection` | judge | judge_chapter@1, judge_novel@1 | judge_chapter@2, judge_novel@2 |
| `b3-injection` | planner | planner@2 | planner@4 |
| `b3-injection` | writer | writer@3 | writer@4 |
| `b4-temporal` | editor | — | editor@4 |
| `b4-temporal` | judge | — | judge_chapter@2, judge_novel@2 |
| `b4-temporal` | planner | planner@2 | planner@3 |
| `b4-temporal` | writer | — | writer@4 |
