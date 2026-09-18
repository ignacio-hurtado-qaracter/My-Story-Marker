# Changelog — autoimprove: Orchestrator → Writer

One entry per iteration of the loop defined in [the spec](spec-automejora-orquestrator-writer.md) §4.
Entries are appended, never edited. Iteration numbers count against the cap in spec §4.3
(**8 iterations maximum**; the loop stops at 8 whatever the state).

Entry template:

```markdown
## Iteration N — YYYY-MM-DD — Variant X — kept | reverted | aborted
Hypothesis: <one line: which invariant/measure moves, to what value>
Commit: <sha>
Runs: X-1, X-2, X-3 (scorecards in runs/)
| | previous accepted (worst) | X (worst) |
|---|---|---|
| I1 … I8 | | |
| llm_calls max | | |
| latency p50 | | |
| continuity mean | | |
| cost sum | | |
Decision: <why kept / reverted, one or two lines>
Notes: <failures worth remembering, items to watch>
```

---

## Iteration 0 — 2026-09-18 — setup — no variant run

Hypothesis: none yet. Baseline (variant A) is the first thing the loop must measure.

Done:
- Spec written from the analysis of trace `b49a12b93ba8a0e079eec332311e8e89` (session `7fd325fc`,
  Haiku 4.5): Writer ch.1 frag 2 made 15 LLM calls and 12 failed `Read`s hunting for a manuscript
  the orchestrator had summarised instead of pasting.
- Dataset `dataset/writer-contexts.jsonl` built from `books/el-custodio-de-aurora` with
  `scripts/build_writer_dataset.py`: 21 real items + 3 fault-injection items.
- `runs/` created for scorecards.

Pending before iteration 1:
- `scripts/eval_writer.py` (spec §3.3).
- Bench mode of the main agent (spec §3.2): the one-sentence trigger and the renderer per variant.
- Langfuse dataset mirror and the `continuity` evaluator (spec §3.4).

Known numbers (not a bench run, from the trace): frag 1 → 2 calls / 24.5 s; frag 2 → 15 calls,
12 tool errors, 48.2 s, I1 = 0, I3 = 0, I4 = 0.
