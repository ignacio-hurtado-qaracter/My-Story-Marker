# Spec 1 — Story Creator Harness

Status: draft v0.3 · Config: `config.json`

## 1. Intent

Build an agentic harness that writes a complete science fiction novel incrementally, fragment by fragment, so that the finished text is coherent from the first page to the last.

Coherence is the whole point. A single model writing a long novel in one pass loses track of plot, characters and pacing. This harness solves that by:

- Fixing the novel's plan up front in a document called the **Spirit** (main thread, chapter plans, characters).
- Giving the **Writer** a curated context window instead of the whole book: the Spirit plus a small, well-chosen slice of past and upcoming story.
- Putting a **Reviewer** between every fragment and the manuscript, so nothing enters the novel unless it matches the Spirit and respects the story's pacing.
- Refreshing the context after every accepted fragment, so the Writer always works from an accurate picture of "where the story is".
- Discarding and re-planning a whole chapter when it keeps failing review, on the assumption that the chapter plan itself was flawed.

The output is a manuscript that reads as if one author with a clear outline wrote it, produced automatically from an initial premise.

## 2. Inputs and outputs

### 2.1 Input

A single JSON configuration file, `config.json`. Every parameter the spec refers to lives there, so a test run only needs to swap the file. All fields are optional except `chapters.count`; missing fields take the defaults shown.

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `theme` | string or null | null | Optional premise or theme. When null, the Spirit Creator invents one within science fiction. |
| `language` | string | "en" | Language of the novel. Governs the manuscript, the novel title, the Spirit's prose fields and the chapter summaries - everything a reader or the Writer sees. It does not change the schema: field names, beat ids and `status` values stay as written in this spec. |
| `tone_and_style` | string or null | null | Optional voice constraints passed verbatim to the Spirit Creator. |
| `chapters.count` | int | required | Number of chapters in the novel. |
| `chapters.target_paragraphs` | int | 40 | Target length of each chapter in paragraphs. The Spirit Creator sizes beats to fit; the Reviewer treats a strong deviation as a pacing problem. |
| `fragment.min_paragraphs` | int | 3 | Minimum paragraphs per Writer fragment. |
| `fragment.max_paragraphs` | int | 6 | Maximum paragraphs per Writer fragment. |
| `context.recent_paragraphs` | int | 4 | N: paragraphs given verbatim to the Writer as recent context. |
| `context.distant_chapters` | int | 1 | M: number of previous chapters whose summaries are given to the Writer as distant context. |
| `model` | string | "claude-fable-5-1" | Model used by every agent. Writer and Reviewer always share the same model. |
| `retries.max_fragment_retries` | int | 3 | Rejections allowed for one fragment before it counts as a fragment failure. |
| `retries.max_fragment_failures_per_chapter` | int | 2 | Fragment failures allowed inside one chapter before the chapter is discarded and re-planned. |
| `retries.max_chapter_regenerations` | int | 2 | Times a single chapter may be discarded and re-planned before the run stops with an error. |
| `output.books_dir` | string | "books/" | Directory under which each novel gets its own folder. See 2.2. |

### 2.2 Output

Each run creates one folder per novel under `output.books_dir`, named after the novel's title in slug form: lowercase, punctuation dropped, spaces collapsed to hyphens, and diacritics reduced to their base letter so the name stays ASCII. *The Seam* becomes `the-seam/`; *El Último Faro* becomes `el-ultimo-faro/`. When the title is in a script with no Latin form, the slug is a romanisation of it, and the untransliterated title is kept in `spirit.md` and `run.json`. If the folder already exists the run does not overwrite it; it appends a numeric suffix (`the-seam-2/`).

```
books/
  <novel-slug>/
    novel.md              # the deliverable
    spirit.md             # premise, tone, main thread, chapter plans, beats
    characters.md         # the cast: role, description, arc, current state
    manuscript/
      chapter-01.md       # approved fragments of that chapter, in order
      chapter-02.md
      ...
    summaries/
      chapter-01.md       # Distant summary, written when the chapter closes
      ...
    metrics.jsonl         # one record per Reviewer verdict
    run.json              # counters, current position, config snapshot
    rejected/             # optional; rejected attempts with their reasons
```

**The deliverable is `novel.md` alone**: one heading per chapter, the approved fragments in order, assembled from `manuscript/` when the last chapter closes. Everything beside it is working state, kept on disk so a run can be inspected, audited or resumed, and not part of what the process promises to produce.

The rest of the folder follows from how the loop mutates state:

| File | Why it is separate |
|------|--------------------|
| `spirit.md` + `characters.md` | Together they are the Spirit of 4.1. The `characters` list lives in `characters.md`; everything else lives in `spirit.md`. They are split because character `state` is rewritten after almost every approved fragment (6.2), while the rest of the Spirit changes only on chapter advance or re-plan. |
| `manuscript/chapter-NN.md` | One file per chapter, each fragment preceded by a marker comment carrying its id and `beats_completed`. Discarding a chapter (6.3) is then deleting one file, not editing a shared one. |
| `summaries/chapter-NN.md` | The cached Distant summaries 4.3 requires. Generated once at chapter close, read on every later context rebuild. |
| `metrics.jsonl` | The per-attempt record of the four checks required by 5.3, appended on every verdict including rejections. |
| `run.json` | The counters of 4.5, the current chapter and beat, the run status, the config as it was loaded, and the snapshot of character states taken at chapter start that 6.3 needs in order to roll back a discarded chapter. |

`novel.md` is written only when the run completes. A run that stops with an error (6.3) leaves the folder in place with its working state intact and no `novel.md`, which is what scenario 9 of section 7 asserts.

## 3. Flow

```mermaid
flowchart TD
    CFG([config.json]) --> S0[Create Spirit]
    S0 --> SP[(Spirit<br/>main thread · chapters · characters)]

    subgraph CW[Writer context window]
        SPv[Spirit view<br/>main thread · current chapter · characters]
        subgraph SC[Specific context]
            R[Recent<br/>last N paragraphs verbatim]
            D[Distant<br/>summaries of last M chapters]
            F[Future<br/>pending beats from the present onward]
        end
    end

    SP --> SPv
    CW --> W((Writer))
    W -->|fragment| REV((Reviewer))
    SP --> REV

    REV -->|reject + reasons| RC{fragment retries<br/>exhausted?}
    RC -->|no| W
    RC -->|yes| FC{chapter failures<br/>exhausted?}
    FC -->|no| CW
    FC -->|yes| RG{chapter regenerations<br/>exhausted?}
    RG -->|no| REPLAN[Discard chapter text<br/>re-plan chapter in Spirit] --> CW
    RG -->|yes| ERR([Run stops with error])

    REV -->|approve| APP[Append fragment to manuscript]

    APP --> UPD[Update state]
    UPD --> UC[Rebuild specific context]
    UPD --> UCH[Update characters if relevant]
    UPD --> ADV{Advance chapter?}
    ADV -->|no| CW
    ADV -->|yes, more chapters| NEXT[Set next chapter as current] --> CW
    ADV -->|yes, last chapter done| END([Assemble novel.md<br/>in books/novel-slug/])
```

## 4. Domain model

### 4.1 Spirit

The single source of truth for the novel. Created once before the loop, mutated only in controlled places (character state, beat status, the "current chapter" pointer, and a full chapter re-plan on chapter failure).

Every free-text value in it - title, premise, chapter plans, beat descriptions, character fields - is written in `config.language`, because the Writer reads them as its brief and a brief in another language leaks into the prose. The keys and the `status` vocabulary are not translated.

```yaml
spirit:
  title: string                  # invented by the Spirit Creator; slugged for the folder name (2.2)
  premise: string                # from config.theme, or invented
  tone_and_style: string         # from config, or chosen by the Spirit Creator
  main_thread:
    introduction: string
    development: string
    resolution: string
  chapters:                      # ordered, length == config.chapters.count
    - id: int
      title: string
      introduction: string | null   # optional, only when the chapter needs one
      development: string
      resolution: string
      target_paragraphs: int        # from config
      beats:                        # ordered list of things that must happen, derived from the three fields above
        - id: string
          description: string
          status: pending | current | done
  characters:
    - id: string
      name: string
      role: string
      description: string
      arc: string                    # intended development across the novel
      state: string                  # what has happened to them so far (updated by the harness)
  current_chapter_id: int
```

### 4.2 Manuscript

```yaml
manuscript:
  chapters:
    - id: int
      fragments:                  # ordered, approved only
        - id: string
          text: string
          beats_completed: [string]
```

### 4.3 Specific context

Rebuilt after every approved fragment.

| Part | Content | Source |
|------|---------|--------|
| Recent | Last N paragraphs of the manuscript, verbatim (N = `context.recent_paragraphs`) | Manuscript |
| Distant | Summaries of the last M closed chapters, oldest first, written in `config.language` (M = `context.distant_chapters`; empty in chapter 1, fewer than M while not enough chapters exist) | One summary generated when each chapter closes, cached |
| Future | The ordered list of beats not yet done, starting from the current one, for the current chapter; plus the next chapter's introduction beat if the current chapter is on its last beat | Spirit beats with status `current` or `pending` |
| Budget | Paragraphs already approved in the current chapter, the chapter's `target_paragraphs`, and how many beats are not yet done | Manuscript + Spirit |

### 4.4 The "present"

The present is the beat with status `current` in the current chapter. It is the only place where new narration is expected. The harness, not the Writer, owns the status of beats.

### 4.5 Run counters

Kept by the harness, reset as indicated.

| Counter | Reset when |
|---------|-----------|
| `fragment_attempts` | A fragment is approved, or a fragment failure is declared |
| `chapter_fragment_failures` | A chapter is closed or re-planned |
| `chapter_regenerations[chapter_id]` | Never |

## 5. Agents

All agents run on the model named in `model`. In particular the Writer and the Reviewer share the same model; the separation of roles comes from their prompts and contracts, not from different models.

Each agent's prompt lives in `.claude/agents/`, one file per agent, and **that file is where the agent's behaviour is defined**: its rules, what it judges, how it decides, what it refuses. This section does not restate any of it. What stays here is the wiring - which agents exist, what each one is handed, and the shape of what it returns - because the loop in 6 and the storage layout in 2.2 are written against those shapes.

To change how an agent behaves, change the agent file. To change what it is handed or what it returns, change both.

| Agent | Role | Definition |
|-------|------|------------|
| Spirit Creator | Plans the novel up front; re-plans a chapter that has failed | [`spirit-creator.md`](../.claude/agents/spirit-creator.md) |
| Writer | Writes one fragment from the curated context window | [`writer.md`](../.claude/agents/writer.md) |
| Reviewer | Approves or rejects each fragment against the full Spirit | [`reviewer.md`](../.claude/agents/reviewer.md) |

Two steps of the loop are not agents in this sense and have no file: the character update of 6.2 and the chapter summary generated at chapter close (4.3). Both are single-shot calls owned by the harness.

### 5.1 Spirit Creator

- **Input**: the config (theme, language, tone, chapter count, chapter length).
- **Output**: a complete Spirit as in 4.1, with every chapter broken into beats and all beats `pending` except the first, which is `current`. Written to `spirit.md` and `characters.md` per 2.2.
- **Re-plan mode**: invoked with an existing Spirit, a chapter id and that chapter's collected rejection reasons; returns a new plan for that chapter alone.
- Acceptance criteria, beat sizing and the re-plan constraints: [`spirit-creator.md`](../.claude/agents/spirit-creator.md).

### 5.2 Writer

- **Input**: the Writer context window (Spirit view + the specific context of 4.3) and, on a retry, the Reviewer's rejection reasons.
- **Output**: one fragment of prose plus a self-report:

```yaml
fragment:
  text: string
  beats_completed: [string]      # beats the Writer considers finished by this fragment
  present_advanced: bool         # true if the Writer moved the story into the next beat
```

- The rules the Writer works under: [`writer.md`](../.claude/agents/writer.md).

### 5.3 Reviewer

- **Input**: the fragment, the full Spirit, the specific context.
- **Output**:

```yaml
verdict:
  approved: bool
  checks:
    main_thread: pass | fail
    current_chapter: pass | fail
    characters: pass | fail
    pacing: pass | fail
  reasons: [string]              # required on any fail, specific and actionable
  beats_completed: [string]      # Reviewer's own judgement, may differ from the Writer's
  chapter_closable: bool         # only meaningful when the resolution beat is done, see 6.1
```

- What each check means, and how the decision is made: [`reviewer.md`](../.claude/agents/reviewer.md).
- **Metric**: the harness records the four check results per attempt. This is the "Métrica" box in the diagram and the basis for later evaluation.

## 6. Orchestration loop

```
config = load("config.json")
spirit = create_spirit(config)
while spirit.current_chapter exists:
    ctx = build_context(spirit, manuscript, config)
    fragment_attempts = 0
    previous_reasons = []
    loop:
        fragment = writer(ctx, previous_reasons)
        verdict = reviewer(fragment, spirit, ctx)
        record_metric(verdict)
        if verdict.approved: break
        previous_reasons = verdict.reasons
        fragment_attempts += 1
        if fragment_attempts >= config.retries.max_fragment_retries:
            # fragment failure
            chapter_fragment_failures += 1
            fragment_attempts = 0
            if chapter_fragment_failures >= config.retries.max_fragment_failures_per_chapter:
                # chapter failure
                ch = spirit.current_chapter_id
                chapter_regenerations[ch] += 1
                if chapter_regenerations[ch] > config.retries.max_chapter_regenerations:
                    stop_with_error("chapter {ch} could not be written")
                discard_chapter_text(manuscript, ch)
                replan_chapter(spirit, ch, collected_reasons)
                chapter_fragment_failures = 0
                ctx = build_context(spirit, manuscript, config)
            continue          # new fragment from scratch
    append(manuscript, fragment)
    mark_beats_done(spirit, verdict.beats_completed)   # Reviewer's list wins
    update_characters(spirit, fragment)
    if should_advance_chapter(spirit, verdict):
        close_chapter(spirit, manuscript)               # generate Distant summary
        chapter_fragment_failures = 0
        spirit.current_chapter_id += 1, or finish if it was the last chapter
assemble(manuscript, books_dir/novel_slug/"novel.md")
```

### 6.1 Chapter advance rule

Advance when both hold:

1. The current chapter's resolution beat has status `done`.
2. The last approved paragraph leaves the scene open enough to lead into the next chapter's introduction. Evaluated by the Reviewer through `chapter_closable` once condition 1 is met.

If condition 1 holds but condition 2 does not, the Writer is asked for one more fragment whose explicit goal is to close the chapter.

### 6.2 Character update rule

After each approved fragment, a lightweight step asks: did anything happen in this fragment that changes a character's state or advances their arc? If yes, update `state` for that character. `description` and `arc` are not changed by the loop.

### 6.3 Chapter failure rule

A chapter fails when it accumulates `max_fragment_failures_per_chapter` fragment failures. The interpretation is that the chapter plan itself is flawed, not the prose. The harness then:

1. Deletes every fragment of that chapter from the manuscript.
2. Asks the Spirit Creator to re-plan that chapter using the collected rejection reasons.
3. Restarts the chapter from its first beat.

Character `state` is not rolled back automatically. Because the discarded fragments never became canon, the re-plan step must also revert any state changes that came from them. Implementation note: keep a snapshot of character states at chapter start and restore it on discard.

## 7. Acceptance scenarios

1. **Happy path**: given a config with `chapters.count` = 3 and no theme, the loop produces a Markdown file with 3 chapters, every beat marked `done`, and ends with "Novel complete".
2. **Character consistency**: given a character whose state says "does not know about the signal", when a fragment shows them acting on the signal, then the Reviewer fails `characters` and the reasons mention the character.
3. **Pacing, skipped beat**: given beats A (current), B, C, when the fragment narrates C, then the Reviewer fails `pacing`.
4. **Pacing, legitimate advance**: given beats A (current) and B, when the fragment resolves A and starts B, then `pacing` passes and the Reviewer marks A as done.
5. **Chapter close**: given the resolution beat is done and the last paragraph is a cliffhanger into the next chapter, then the harness advances the chapter and generates the Distant summary.
6. **Retry**: given a rejection, when the Writer is called again, then it receives the reasons and the new fragment addresses them.
7. **Fragment failure**: given `max_fragment_retries` = 3, when a fragment is rejected 3 times, then the chapter failure counter increases by one and the Writer starts a fresh fragment.
8. **Chapter re-plan**: given `max_fragment_failures_per_chapter` = 2, when a chapter reaches 2 fragment failures, then its text is removed from the manuscript, its plan in the Spirit changes, its beats are reset, and character states equal the snapshot taken at chapter start.
9. **Run abort**: given `max_chapter_regenerations` = 2, when the same chapter fails a third time, then the run stops with an error naming the chapter and no output file is written.
10. **Config defaults**: given a config with only `chapters.count`, the run uses every default from section 2.1.
