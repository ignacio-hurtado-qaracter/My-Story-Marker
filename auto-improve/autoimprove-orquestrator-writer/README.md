# autoimprove: Orchestrator → Writer

Self-improvement loop for the channel between the harness and the Writer agent. What is being
fixed, how it is measured and when it stops: [spec-automejora-orquestrator-writer.md](spec-automejora-orquestrator-writer.md).

```
spec-automejora-orquestrator-writer.md   the spec (contract, bench, loop, stop rule)
CHANGELOG.md                             one entry per iteration, appended, never edited
dataset/writer-contexts.jsonl            24 Writer situations from books/el-custodio-de-aurora (spec §3.1)
scripts/build_writer_dataset.py          regenerates the dataset (deterministic, no model)
scripts/eval_writer.py                   scores a bench run into runs/<run>/scorecard.json (spec §3.3) — pending
runs/<variant>-<n>/                      prompts, outputs and scorecard of one bench run
```

## One iteration

1. Write the hypothesis as a new entry in `CHANGELOG.md` (iteration number, variant, invariant, target).
2. Apply the variant's single change (spec §4.1) in one commit.
3. Ask the main agent: *"Run the Writer bench, variant X, run id X-1"* — three times (X-1, X-2, X-3).
4. `python scripts/eval_writer.py --run X-1 --push` for each run.
5. Fill the entry's table from the three scorecards (worst run for invariants, mean for measures).
6. Keep or revert per spec §4.3; record the decision in the entry.

## Limits

- **8 iterations maximum** (spec §4.3). Variants A–E are 5; the other 3 are for corrections.
- Stop early when I1–I8 = 1.0 on three consecutive runs, or when two consecutive iterations move
  no invariant.
- Nothing outside `.claude/agents/writer.md`, the orchestrator's prompt rendering and (after
  acceptance) `Specs/Spec1.md` changes during the loop.

## Regenerate the dataset

```
python auto-improve/autoimprove-orquestrator-writer/scripts/build_writer_dataset.py
```

Reads `run.json` (config snapshot), `spirit.md`, `characters.md`, `manuscript/`, `summaries/`
from the book folder. The dataset is versioned; regenerate only if the extraction changes, and
say so in the changelog.
