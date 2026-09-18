# Spec 2 — Self-improvement of the Orchestrator → Writer channel

Companion to [Spec1.md](../../Specs/Spec1.md). Spec1 defines what the harness does; this spec
defines how one part of it gets measurably better without a human judging prose. When the two
disagree, Spec1 wins until the edits listed in §2.4 are applied to it.

Everything the loop produces lives next to this file, in `auto-improve/autoimprove-orquestrator-writer/`:
the dataset (`dataset/`), the scripts (`scripts/`), one folder per bench run (`runs/`) and the
iteration log (`CHANGELOG.md`). Paths below are relative to that folder unless they start with
`books/`, `Specs/` or `.claude/`.

## 1. Intent

The Writer is designed to work from a curated context window and nothing else (Spec1 §4.3,
§5.2). In practice the orchestrator does not always hand it that window intact, and the Writer,
having a `Read` tool, compensates by going to look for what is missing. The result is a Writer
that spends most of its time and tokens not writing.

Evidence, session `7fd325fc` (trace `b49a12b93ba8a0e079eec332311e8e89`, 2026-09-17, Haiku 4.5):

| Fragment | What the Writer received | What it did | Cost |
|---|---|---|---|
| Ch.1 frag 1 | Full Spirit view, no `language`, no fragment size | Read `config.json` before writing | 2 LLM calls, 24 s, ~1 000 thinking tokens on a lookup |
| Ch.1 frag 2 | Recent as `"...[3 párrafos que establecen ...]"` — a summary, not text | Guessed 15 paths for the manuscript (12 `Read` errors), read `web/data/books.js` and `books.json`, wrote anyway from the summary | 15 LLM calls, 48 s, 32 s of them before the first word of prose |

And from a finished run (`books/el-custodio-de-aurora`, Sonnet 5, 29 verdicts): 4 of 8 rejections
are **contract** failures, not prose failures — 2 for fragment length over `max_paragraphs`, 2 for
English words leaking into Spanish prose (`converging`, and `beat`, a schema word from the prompt).

Both problems are in the same channel, and both are checkable by a script. This spec makes that
channel a contract with machine-checkable invariants, builds a fixed bench to exercise it, and
defines the loop that changes one thing at a time until the invariants hold.

**In scope**: everything between `build_context` in the loop of Spec1 §6 and the fragment the
Writer returns — what the prompt contains, which tools the Writer has, how many calls it makes,
whether its output honours the contract.
**Out of scope**: prose quality, the Spirit Creator, the Reviewer. The Reviewer has the same
`tools: Read` and the same temptation; it is the next spec, not this one.

## 2. The contract, made checkable

### 2.1 The Writer prompt template

The orchestrator builds every Writer prompt from this template. Section headings are fixed and
in English (they are schema, like beat ids); content is in `config.language`.

```markdown
# Writer task: chapter {chapter_id}, fragment {fragment_index}, attempt {attempt}

## Spirit view
### Main thread
{introduction / development / resolution of the novel, verbatim from spirit.md}
### Current chapter: {id} — {title}
{introduction / development / resolution of this chapter, verbatim}
### Characters
{characters.md content, verbatim}

## Recent
{last N paragraphs of manuscript/, verbatim, N = config.context.recent_paragraphs}
{or exactly the line: (empty — this is the first fragment of the novel)}

## Distant
{summaries/chapter-NN.md of the last M closed chapters, oldest first}
{or exactly the line: (empty — no closed chapters yet)}

## Future
{ordered beats not yet done, starting with the current one, each as "- {id} (current|pending): {description}"}

## Budget
- paragraphs approved in this chapter: {n}
- chapter target_paragraphs: {t}
- beats not yet done: {k}

## Constraints
- language: {config.language}
- tone_and_style: {spirit.tone_and_style, or "(none)"}
- fragment length: {min}–{max} paragraphs

## Rejection reasons            ← only on a retry
- {reason 1}
```

The orchestrator persists each prompt as `books/<slug>/prompts/writer-c{CC}-f{FF}-a{A}.md` before
calling the Agent tool, so every prompt is inspectable and diffable.

### 2.2 Invariants

Each invariant has a mechanical check. "Mechanical" means a script computes it from files on
disk with no model call.

| # | Invariant | Check |
|---|---|---|
| I1 | **Recent is verbatim.** The `## Recent` section equals the last N paragraphs of `manuscript/` byte for byte (after normalising line endings and trailing whitespace). | String equality against the paragraphs recomputed from `manuscript/`. Also fails on any of `...`, `[...]`, `[N párrafos`, `etc.` inside the section. |
| I2 | **The prompt is complete.** All eight headings of §2.1 present, in order; `## Constraints` names `language` and both fragment bounds. | Header parse of the persisted prompt. |
| I3 | **The Writer makes no tool calls.** | Count of `tool_use` blocks in the Writer's subagent transcript = 0. |
| I4 | **The Writer answers in one generation.** | Count of `assistant` rows in the transcript ≤ 2 (two allows one thinking-only turn). |
| I5 | **The output parses.** A single ```yaml block, `fragment.text` non-empty, `beats_completed` ⊆ ids listed in `## Future`, `present_advanced` boolean. | YAML parse + set check. |
| I6 | **Length is within contract.** Paragraph count of `fragment.text` ∈ [`min_paragraphs`, `max_paragraphs`]. Paragraph = block separated by a blank line. | Count. |
| I7 | **No schema leak.** `fragment.text` contains none of: `beat`, `fragment`, `Spirit`, `Writer`, `Reviewer`, `present_advanced`, `beats_completed`, and no `##` headings. | Case-insensitive word-boundary regex. (Motivated by Aurora ch.4: `"cada beat que su corazón daba"`.) |
| I8 | **Incomplete context is reported, not repaired.** If Recent or Constraints are missing or abridged, the Writer returns `error: recent_context_incomplete` / `error: constraints_missing` and no prose. | Presence of the `error` field on the fault-injection items of §3.1. |

I1–I2 are the orchestrator's obligations. I3–I8 are the Writer's. The bench measures both sides
of the channel on every run.

### 2.3 Changes to `writer.md`

```diff
 ---
 name: writer
 description: ...
 model: inherit
-tools: Read
+tools:
 ---
```

```diff
 ## Input

-The Writer context window:
+Everything you need arrives in the prompt, under fixed headings. You have no tools and you must
+not look for files: the harness has already selected what you need. Do not ask for more and do
+not invent what you were not given.
+
+If `## Recent` is missing, or is abridged in any way (ellipses, brackets, a description of the
+paragraphs instead of the paragraphs), or `## Constraints` does not name the language and the
+fragment length, do not write. Return only:
+
+```yaml
+fragment:
+  error: recent_context_incomplete   # or constraints_missing
+```
+
+The Writer context window:
```

```diff
-4. Write in `config.language`. Respect tone_and_style and the characters' current state.
-5. Fragment length between `fragment.min_paragraphs` and `fragment.max_paragraphs`.
+4. Write in the language given under `## Constraints`. Respect its tone_and_style and the
+   characters' current state.
+5. Fragment length within the bounds given under `## Constraints`. A paragraph is a block
+   separated by a blank line; dialogue lines without a blank line between them are one paragraph.
+7. The prose is for a reader who has never seen this prompt. Never use the words of the schema
+   (beat, fragment, Spirit, Writer, Reviewer) or any heading inside `fragment.text`.
```

The Output schema gains one optional field:

```yaml
fragment:
  text: string
  beats_completed: [string]
  present_advanced: bool
  error: string                  # optional; when present, no other field is set
```

### 2.4 Changes to `Spec1.md`

Applied only after the bench shows the variant that introduces them meets §4.3. Listed here so
the edits are known in advance.

| Section | Edit |
|---|---|
| §2.2 layout | Add `prompts/` to the folder tree: `writer-cCC-fFF-aA.md`, one per Writer call. Row in the table: "The exact prompt handed to the Writer. Kept so the context rebuild (4.3) can be audited without re-running." |
| §4.3 table | Add row **Constraints**: `language`, `tone_and_style`, `fragment.min_paragraphs`, `fragment.max_paragraphs` — Source: config + Spirit. Add below the table: "Recent is copied from `manuscript/` byte for byte. The harness never summarises, elides or paraphrases it. When fewer than N paragraphs exist it contains what exists; before the first fragment it is empty and says so." |
| §5.2 Input | Replace the first bullet with: "The Writer prompt of Spec 2 §2.1, persisted to `prompts/` before the call. The Writer has no tools." Add the optional `error` field to the output schema with the sentence: "An `error` is a harness fault, not a Writer failure: it does not consume a fragment attempt. The harness rebuilds the context and calls again; two consecutive errors on the same fragment abort the run." |
| §6 pseudocode | After `ctx = build_context(...)` add `persist_prompt(ctx)`. After `fragment = writer(...)` add: `if fragment.error: rebuild ctx, retry once, else stop_with_error("writer context fault")` — before `reviewer(...)`, outside the attempt counter. |
| §7 scenarios | 11. **Recent verbatim**: given a chapter with 7 approved paragraphs and N = 5, the persisted prompt's `## Recent` equals paragraphs 3–7 of `manuscript/chapter-NN.md`. 12. **Context fault**: given a prompt whose Recent contains `[...]`, the Writer returns `error: recent_context_incomplete` and no prose, and `fragment_attempts` does not increase. 13. **No tools**: on any run, no Writer transcript contains a tool call. |

## 3. The bench

The bench is what makes the loop honest: a fixed set of Writer situations, a fixed way of running
one, and a script that scores the result. Nothing in it depends on the Spirit Creator or the
Reviewer, so a change in the channel is the only thing that can move the numbers.

### 3.1 Dataset `writer-contexts`

Source: `books/el-custodio-de-aurora/` — 5 chapters, 21 approved fragments, every one 3
paragraphs, `target_paragraphs` 14, N = 5, M = 2, fragment bounds 1–3, language `es`. It was
written by Sonnet 5, so its manuscript is a clean reference for what "the previous paragraphs"
should look like.

Extraction (`scripts/build_writer_dataset.py`, deterministic, no model):

1. Parse each `manuscript/chapter-NN.md` on its `<!-- fragment: ... beats_completed=[...] -->`
   markers into an ordered list of (chapter, fragment_index, beats_completed, paragraphs).
2. For each approved fragment *i* of chapter *c*, build one item whose context is the state of
   the run **just before** that fragment was written:
   - `recent`: the last 5 paragraphs of everything approved before it, across chapter
     boundaries; empty for c01-f1.
   - `distant`: `summaries/chapter-NN.md` for chapters c−2 and c−1 where they exist.
   - `future`: the beats of chapter *c* from `spirit.md`, minus those in `beats_completed` of
     earlier fragments of the chapter; the first remaining beat is `current`.
   - `budget`: `3 × (i−1)` paragraphs approved, target 14, beats remaining = `len(future)`.
   - `spirit_view`: main thread + chapter *c* plan from `spirit.md`; `characters.md` as it is
     in the folder (final state — a known simplification, see §6).
   - `constraints`: `language: es`, the Spirit's `tone_and_style`, `1–3 paragraphs`.
   - `expected`: the exact `recent` string (for I1), the set of valid beat ids (for I5), the
     bounds (for I6).
3. Add **3 fault-injection items** derived from c02-f2, c04-f1 and c05-f3: one with Recent
   replaced by a one-line summary ending in `[...]`, one with `## Recent` removed, one with
   `## Constraints` removed. Their `expected` is the `error` value of I8.

Total: 24 items. Stored as `dataset/writer-contexts.jsonl` (one item per line, schema above)
and mirrored as a Langfuse dataset of the same name so each bench run is an experiment there.
The dataset is versioned with the repo; it does not change during the loop. Each real item also
carries `expected.reference_fragment`, the paragraphs Sonnet 5 actually wrote at that point — a
reference for the continuity judge of §3.4, never a target for string comparison.

### 3.2 Running the bench

A bench run is a session of the main agent in **bench mode**, asked with one sentence:
"Run the Writer bench, variant {V}, run id {R}". In bench mode the orchestrator does not run
the loop of Spec1 §6. For each item it:

1. Renders the prompt from the item with the template of §2.1 — as the variant under test
   renders it (variant A deliberately reproduces the current, unpersisted, free-form behaviour).
2. Persists it to `runs/{R}/{item_id}/prompt.md`.
3. Calls the Agent tool with `subagent_type: writer` and
   `description: "Bench {V} {R} {item_id}"`. The description becomes the span name in Langfuse
   and the `description` field of the subagent's `.meta.json`, which is how the evaluator finds
   the transcript. This avoids depending on environment variables, which do not reach hooks in
   VS Code sessions.
4. Saves the raw reply to `runs/{R}/{item_id}/output.md`.

The 24 items run in parallel batches of 6. A full run is 24 Writer calls; at Haiku 4.5 prices
and the token counts observed (≈ 8 000 total per call) that is about $0.10, and about 3 minutes.
Every variant is run **3 times** (R = `{V}-1`, `{V}-2`, `{V}-3`); the model is not deterministic
and one run proves nothing.

### 3.3 The evaluator

`scripts/eval_writer.py --run {R}` reads, per item:

- `runs/{R}/{item}/prompt.md` and `output.md`;
- the Writer's transcript, found by scanning
  `~/.claude/projects/<project-dir>/*/subagents/*.meta.json` for
  `agentType == "writer"` and `description == "Bench {V} {R} {item}"`, then reading the
  matching `.jsonl` (it holds every `assistant` row, `tool_use` block, `tool_result` error and
  `usage` object);
- `dataset/writer-contexts.jsonl` for the item's `expected`.

It computes, per item, every invariant of §2.2 as 0/1 plus these measures from the transcript:

| Measure | Definition |
|---|---|
| `llm_calls` | `assistant` rows |
| `tool_calls`, `tool_errors` | `tool_use` blocks; `tool_result` rows with `is_error` |
| `output_tokens`, `cache_read_tokens`, `cache_write_tokens` | summed `usage` |
| `latency_s` | last row timestamp − first row timestamp |
| `cost_usd` | from tokens at the model's list price (table in the script) |

And writes `runs/{R}/scorecard.json`:

```json
{"run": "C-1", "variant": "C", "items": 24,
 "invariants": {"I1": 1.0, "I2": 1.0, "I3": 1.0, "I4": 0.96, "I5": 1.0, "I6": 0.92, "I7": 1.0, "I8": 1.0},
 "llm_calls": {"mean": 1.04, "max": 2}, "tool_calls": {"sum": 0}, "tool_errors": {"sum": 0},
 "latency_s": {"p50": 14.1, "p90": 18.7, "max": 22.3},
 "output_tokens": {"mean": 1240}, "cost_usd": {"sum": 0.09},
 "failures": [{"item": "aurora-c03-f2", "invariant": "I6", "detail": "4 paragraphs, max 3"}]}
```

With `--push`, each invariant and measure is also written to Langfuse as a score on the item's
Writer span (`createScore`, numeric, name = invariant id or measure, comment = detail), so the
Langfuse dataset view compares runs side by side.

The evaluator is the only judge of I1–I8. It calls no model.

### 3.4 Guardrail: continuity judge

Obedience metrics can be gamed by a Writer that is compliant and worse. One model-based score
guards against that, and it is a guardrail, not an objective: it must **not get worse** than
variant A; it is not required to improve.

`continuity` (0–3), a Langfuse LLM evaluator on the Writer span with a fixed rubric:
"Given `## Recent` and `fragment.text`: 0 = restates or contradicts Recent; 1 = continues but
breaks rhythm or register; 2 = continues cleanly; 3 = continues cleanly and advances the current
beat." Model: the same as the Writer under test. Run once per bench run, mean over the 21
non-fault items.

## 4. The loop

### 4.1 Variants

Cumulative. Each adds exactly one change to the previous one and names the invariant it should
move. If the named invariant does not move, the change is reverted regardless of anything else.

| Variant | Change | Should move |
|---|---|---|
| **A** | Baseline. Current `writer.md` (with `Read`), prompt rendered as the orchestrator does today (free-form, Recent may be abridged). | — |
| **B** | Orchestrator renders the §2.1 template; Recent copied verbatim from the item. `writer.md` unchanged. | I1, I2 → 1.0; I3, I4, latency ↓ |
| **C** | B + `writer.md` with `tools:` empty. | I3 → 1.0; `llm_calls` max → ≤ 2 |
| **D** | C + `writer.md` Input rewrite and `error` field (§2.3). | I8 → 1.0 on fault items |
| **E** | D + rule 5 paragraph definition and rule 7 schema-leak (§2.3). | I6, I7 → 1.0 |

B is a change to the orchestrator's behaviour and, once accepted, to Spec1 (§2.4). C–E are
changes to `writer.md`. Nothing else in the repo changes during the loop.

### 4.2 One iteration

1. Open a new entry in `CHANGELOG.md` with the next iteration number and the hypothesis in one
   line (which variant, which invariant, expected value). If the next number is 9, the loop is
   over (§4.3): write the closing entry instead.
2. Apply the variant's change in a single commit.
3. Run the bench 3 times (§3.2). Run `eval_writer.py --push` on each.
4. Run the continuity judge on each.
5. Compare the 3 scorecards against the previous accepted variant: **worst run** for
   invariants, **mean** for measures.
6. Keep or revert (§4.3). Record the numbers in the log entry.
7. If kept and the variant is B: apply the Spec1 edits of §2.4 in a second commit.

### 4.3 Acceptance and stop rule

A variant is **kept** when, on its worst run:

- every invariant it names in §4.1 reaches the target;
- no invariant already at 1.0 in the previous accepted variant drops below 1.0;
- `continuity` mean ≥ previous accepted variant − 0.2;
- `cost_usd` sum ≤ previous accepted variant (obedience must not cost more).

The channel is **done** when a kept variant has I1–I8 = 1.0 on all three runs and
`llm_calls` max ≤ 2. Expected at E; if E does not reach it, the log says which invariant is
short and why, and the next iteration is a new single change targeting it.

The loop **stops**, whatever the state, at the first of:

- done, as defined above;
- two consecutive iterations that move no invariant — the remaining gap is not in this channel;
- **iteration 8**. Variants A–E take five iterations; three are left for corrections. A ninth
  change is not an iteration of this loop but a new hypothesis that deserves its own spec, and
  the closing entry of the changelog says what it should be.

An iteration is one variant applied, three runs, one decision. A reverted variant counts.

### 4.4 The changelog

`CHANGELOG.md`, in this folder. One entry per iteration, numbered, appended, never edited.
Iteration 0 is the setup (spec, dataset, scripts); the cap of §4.3 counts from 1. An entry
records the hypothesis before the runs and the decision after them, so a half-written entry
means an iteration in progress.

```markdown
## Iteration 3 — 2026-09-19 — Variant C — kept
Hypothesis: removing `Read` brings I3 to 1.0 and llm_calls max to ≤ 2.
Commit: abc1234
Runs: C-1, C-2, C-3
| | A (worst) | C (worst) |
|---|---|---|
| I1 | 0.38 | 1.00 |
| I3 | 0.71 | 1.00 |
| llm_calls max | 15 | 2 |
| latency p50 | 27.4 s | 14.1 s |
| continuity mean | 2.1 | 2.2 |
| cost sum | 0.31 | 0.09 |
Decision: kept — I3 and llm_calls at target, no invariant regressed, continuity within 0.2, cost down.
Notes: c03-f2 still fails I6 (4 paragraphs); dialogue block counted as 3. Target for E.
```

Scorecards, prompts and outputs of every run stay in `runs/{R}/`, kept or reverted, so any
entry can be re-derived from disk.

## 5. Baseline

Variant A is measured by the bench like any other; the numbers below are what is already known
and what they predict.

From the trace of session `7fd325fc` (Haiku 4.5, 9 Writer calls):

- Ch.1 frag 1: `llm_calls` 2, `tool_calls` 1 (`config.json`), `tool_errors` 0, 24.5 s.
- Ch.1 frag 2: `llm_calls` 15, `tool_calls` 15, `tool_errors` 12, 48.2 s; I1 = 0 (Recent
  abridged), I3 = 0, I4 = 0.
- Writer prompts were not persisted, so I1 and I2 cannot be computed for the other 7 calls
  from that run — which is itself the reason for `prompts/`.

From `el-custodio-de-aurora` (Sonnet 5, 29 verdicts): I6 failed on 2 of 29 verdicts, I7 on 2 of
29 (both language leaks), without any tool-hunting — a stronger model hides I3/I4 and leaves
I6/I7 visible.

Prediction to test: A on the bench shows I1 well below 1.0, I3 below 1.0 with high variance
between runs, and `llm_calls` max ≥ 10 on at least one item. If A already scores 1.0 on I1–I4
the diagnosis in §1 is wrong and the loop stops before B.

## 6. Known limitations

- **Character state is final, not point-in-time.** Aurora keeps only the last `characters.md`;
  items for chapter 3 show characters as they are at the end of chapter 5. This can only make
  `continuity` harsher, never easier, and does not touch I1–I8. A run that persists
  `characters.md` per chapter (a candidate Spec1 change, outside this spec) would remove it.
- **The bench is one novel.** After the loop ends, run the final variant once on a second
  dataset extracted the same way from `books/greenwater/` to check nothing was fitted to Aurora.
- **The Reviewer is not in the bench.** `first_pass_approval_rate` from a real run is the
  outcome metric the harness ultimately cares about; it is measured before and after the loop
  on a full 3-chapter run with the same Spirit, but it is noisy and is reported, not gated.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Model non-determinism makes a variant look good once | 3 runs, worst-run gating for invariants |
| A compliant Writer writes worse prose | `continuity` guardrail; cost ceiling |
| The orchestrator "passes" I1 by pasting Recent but abridges something else | I2 checks every heading; the persisted prompt is read by a human once per kept variant |
| Removing `Read` breaks a retry path that needed it | Spec1 §5.2: the Writer never needed files; rejection reasons arrive in the prompt. Scenario 6 of Spec1 §7 is re-run after C. |
| Bench mode drifts from real orchestration | The renderer used by bench mode is the one the loop uses; B is accepted only when a real 1-chapter run also persists prompts that pass I1–I2 |
