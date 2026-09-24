# TLC counterexamples found while developing the model

Spec 013, AC 5 (exam item T05). Every entry below is a real violation reported by TLC on
an earlier draft of [`GiftNovelHarness.tla`](./GiftNovelHarness.tla), with the
configuration in [`GiftNovelHarness.cfg`](./GiftNovelHarness.cfg) (N = 5, SCENES = 3,
MAX_SCENE_RETRIES = 2, MAX_CHAPTER_RETRIES = 2, MAX_REPAIR_ROUNDS = 1, MaxCrashes = 1,
MaxChanges = 1). TLC searches breadth-first, so each trace is a shortest one. None was
planted: each draft modelled the flow as the K1 schema and plan 004 describe it
(`chapter_version` and `checkpoint` are two tables; retry counters are the pipeline's
loop variables), and TLC showed where that reading breaks.

Four drafts failed; the fifth passes (see [`tlc-output.txt`](./tlc-output.txt)).

| # | Draft | Invariant violated | Trace length | States explored before the violation | Cause in one line |
|---|---|---|---|---|---|
| CE1 | 1 | `ResumeNoDupNoLoss` | 18 states | 339 distinct | Crash between writing the chapter row and the checkpoint row |
| CE2 | 2 | `RetriesBounded` | 21 states | 549 distinct | Chapter retry counter lived in memory; a crash reset it |
| CE3 | 3 | `ResumeNoDupNoLoss` | 46 states | 3,327 distinct | The repair round re-inserted a chapter row that already existed |
| CE4 | 4 | `RetriesBounded` | 50 states | 7,488 distinct | Repair-round counter lived in memory; a crash reset it |

---

## CE1 — a crash between the chapter row and its checkpoint duplicates the chapter

**Draft 1.** `chapter_close` passing led to two separate actions, `Persist` (insert the
`chapter_version` row) and then `Checkpoint` (insert the `checkpoint` row), mirroring the
two K1 tables and the two pipeline functions `close_chapter` / `checkpoint`.

**Trace (TLC, 18 states).**

1. `Plan` — version 1 is a draft.
2. `NextChapter` picks chapter 1; three `WriteScene` steps pass `scene_accept`; `Editor`;
   `CloseChapter` passes.
3. `Persist` — `rows[1][1] = 1`, but `ckpt[1] = {}`.
4. `Crash` — memory lost, database kept.
5. `Resume` — latest version is 1, a draft; the first chapter without a checkpoint is
   chapter 1.
6. Chapter 1 is written again (3 scenes, editor, close) and `Persist` inserts a second row:
   `rows[1][1] = 2`.

**Violated.** `ResumeNoDupNoLoss` (`rows[v][c] <= 1`: no chapter stored twice).

**Fix in the model.** `Persist` and `Checkpoint` merged into one action `Checkpoint`: the
chapter text and its checkpoint are written atomically.

**Rule for the code.** *`checkpoint(version, chapter)` writes the `chapter_version` row and
the `checkpoint` row in the same SQLite transaction* (`BibleRepository`, one
`with conn:` block). A chapter is either fully checkpointed or absent after a crash;
`resume` never sees text without a checkpoint.

---

## CE2 — a crash resets the chapter retry budget

**Draft 2** (CE1 fixed). The chapter-rewrite counter `chTry` was a volatile loop variable
of `write_chapter`, reset when the chapter starts. A ghost `chFails[v][c]` counted
`chapter_close` failures since the chapter was last opened, independently of memory.

**Trace (TLC, 21 states).**

1. `Plan`; chapter 1: three scenes, editor, `CloseChapter` **fails** → `chTry = 1`,
   `chFails[1][1] = 1`, rewrite.
2. `Crash` → `chTry = 0` (memory), `chFails[1][1] = 1` (what really happened).
3. `Resume`; chapter 1 restarts with a fresh budget.
4. Two more `CloseChapter` failures → `chTry = 2`, `chFails[1][1] = 3`.

**Violated.** `RetriesBounded` (`chFails[v][c] <= MAX_CHAPTER_RETRIES`): chapter 1 was
rewritten three times against a limit of two, and with more crashes the budget is
unbounded (each crash buys `MAX_CHAPTER_RETRIES` more model calls).

**Fix in the model.** The volatile `chTry` is removed; the rewrite decision reads the
durable `chFails[ver][cur]`, which `Crash` does not touch.

**Rule for the code.** *The chapter retry count is derived from persisted
`validator_result` rows* (point `chapter_close`, this version and chapter, since the
chapter was last opened), not from a loop variable. `close_chapter` reads it before
deciding rewrite vs. `StoppedError`. The count resets when the chapter is checkpointed and
when a repair round reopens it.

---

## CE3 — the repair round inserts a second row for a chapter

**Draft 3** (CE1, CE2 fixed). A failed `pre_publish` marks the version `blocked`, removes
the checkpoints of a non-empty set `R` of chapters and sends them back through the same
chapter loop, which ends in the same `Checkpoint` action. `Checkpoint` still *inserted*
the row.

**Trace (TLC, 46 states).**

1. `Plan`; chapters 1–5 each pass and are checkpointed: `rows[1] = <<1,1,1,1,1>>`,
   `ckpt[1] = 1..5`.
2. `PrePublish` **fails**, repair round 1 with `R = {2}`: `vstatus[1] = "blocked"`,
   `ckpt[1] = {1,3,4,5}`.
3. `NextChapter` picks chapter 2; it is rewritten and passes; `Checkpoint` inserts:
   `rows[1][2] = 2`.

**Violated.** `ResumeNoDupNoLoss` again, this time with no crash at all: the repair path
reuses the insert.

**Fix in the model.** `Checkpoint` sets `rows[ver][cur] = 1` (upsert on the key
`(version, chapter)`) and is enabled only when `vstatus[ver] # "published"`.

**Rule for the code.** *`chapter_version` has primary key `(version, chapter)`, and
`checkpoint` upserts it (`INSERT … ON CONFLICT(version, chapter) DO UPDATE`) only while the
version is `draft` or `blocked`; the repository refuses any write to a chapter of a
`published` version.* If spec 005 wants to keep the rejected draft text too (decision D6,
"nothing is deleted"), it adds an `attempt` column and a "current" flag; the model's
invariant then reads "exactly one current row per `(version, chapter)`". Either way a
repair never leaves two current texts for the same chapter.

---

## CE4 — a crash resets the repair-round budget

**Draft 4** (CE1–CE3 fixed). The repair counter `repairs` was volatile, like `chTry` in
CE2. A ghost `repairTotal[v]` counted repair rounds per version.

**Trace (TLC, 50 states).**

1. Chapters 1–5 checkpointed; `PrePublish` fails; repair round: `repairs = 1`,
   `repairTotal[1] = 1`, one chapter reopened.
2. The reopened chapter is rewritten and checkpointed.
3. `Crash` → `repairs = 0`; `Resume` → version 1 is `blocked`, every chapter checkpointed,
   so `NextChapter` goes to `PrePublish`.
4. `PrePublish` fails again and, seeing `repairs = 0`, opens a **second** repair round:
   `repairTotal[1] = 2`.

**Violated.** `RetriesBounded` (`repairRounds[v] <= MAX_REPAIR_ROUNDS`): the spec allows
one repair round before `StoppedError`.

**Fix in the model.** The volatile counter is removed; the durable `repairRounds[v]` is
incremented in the same step that marks the version `blocked` and reopens the chapters.

**Rule for the code.** *`novel_version` stores the repair round (`repair_round` column,
or the count of `pre_publish` failures in `validator_result` for the version), updated in
the same transaction that sets `status = 'blocked'` and resets the reopened chapters'
`checkpoint.status`.* `publish_version` reads it to choose repair vs. `StoppedError`.

---

## Draft 5 — no error

With the four fixes, TLC explores the full state space with no invariant or property
violated: 1,247,479 states generated, 696,062 distinct, depth 109, about one minute on 4
workers. The run is saved in [`tlc-output.txt`](./tlc-output.txt).

**Not counterexamples, but checks that the properties are not vacuous** (run on scratch
copies, not kept in the repository):

- Reachability: TLC reports states where version 2 is published after a crash and a
  repair round, where version 1 is published after a crash and a repair, and where a
  generation stops with an error after its repair round. So the invariants are checked
  on the paths that matter, not on an empty set.
- Mutation M1 — `ChangeFact` regenerates *in place* (writes version v instead of creating
  v+1): TLC reports `PreviousVersionKept` violated after 954 distinct states.
- Mutation M2 — `NextChapter` jumps to `Publish` without `PrePublish`: TLC reports
  `NoUnvalidatedPublish` violated after 657 distinct states.
