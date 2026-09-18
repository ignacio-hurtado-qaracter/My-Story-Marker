# My-Story-Marker — Story Creator Harness

An agentic harness that writes a complete science-fiction novel fragment by fragment,
keeping it coherent from first page to last. Coherence is the whole point: a fixed plan
(the Spirit), a Writer that only ever sees a curated slice of the book, and a Reviewer
that gates every fragment before it enters the manuscript.

## Source of truth

- `Specs/Spec1.md` is the specification. Flow (§3), domain model (§4), agent wiring (§5),
  the orchestration loop (§6) and acceptance scenarios (§7) are defined there. When this
  file and the spec disagree, the spec wins; fix this file.
- `Specs/config.json` is the only input to a run. Every tunable lives there (§2.1).
- `.claude/agents/*.md` define agent behaviour. To change how an agent acts, edit its
  file. To change what it receives or returns, edit both the agent file and Spec1 §5.

## Layout

```
Specs/            Spec1.md, config.json, diagram
.claude/agents/   spirit-creator.md · writer.md · reviewer.md
books/<slug>/     one folder per novel — layout in Spec1 §2.2
auto-improve/     one folder per self-improvement loop: its spec, dataset, scripts,
                  bench runs and CHANGELOG.md — see auto-improve/*/README.md
```

## Running the harness

A run starts when the user asks for a novel. The main session is the harness: it follows
the loop in Spec1 §6 literally, launching the three agents with the Agent tool and owning
every step that is not an agent (context rebuild, character update, chapter summary,
counters, `run.json`, `metrics.jsonl`, final `novel.md`).

Rules that must hold on every run:

- Read `Specs/Spec1.md` and `Specs/config.json` before the first agent call.
- Never write prose yourself. Only the Writer produces manuscript text; only the Reviewer
  approves it. A rejected fragment never reaches `manuscript/`.
- The Writer receives exactly the context window of Spec1 §4.3 — Spirit view, Recent,
  Distant, Future, Budget — and nothing else. Recent is verbatim manuscript text.
- The Reviewer's `beats_completed` overrides the Writer's.
- Write every state change to disk as it happens (`run.json`, `metrics.jsonl`,
  `manuscript/chapter-NN.md`), so a run can be inspected or resumed.
- Respect the retry ladder (§6.3): fragment retries → fragment failures → chapter
  re-plan → run abort. Do not improvise around it.
- `novel.md` is written only when the last chapter closes. An aborted run leaves the
  folder with its working state and no `novel.md`.

## Conventions

- Novel text, titles, Spirit prose and summaries are in `config.language`. Schema keys,
  beat ids and `status` values stay in English as written in the spec.
- Folder slugs are ASCII: lowercase, diacritics stripped, spaces to hyphens (§2.2).
- Repo documentation and agent files are in English. Talk to the user in their language.
- Finished novels in `books/` are artefacts of past runs. Do not modify or delete them
  unless asked; a new run gets its own folder.

## Environment

- Windows 11, PowerShell. The repo path contains spaces and accents — always quote paths.
- `python` is available; `python3` is not (Microsoft Store stub). Use `python`.
- Sessions are traced to Langfuse via the `langfuse-observability` plugin; nothing to do,
  but be aware that prompts and outputs leave the machine.
