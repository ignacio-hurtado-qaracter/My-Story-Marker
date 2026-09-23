# `backend/`

The only process that reads and writes the harness stores. Everything in
[`docs/architecture.md`](../docs/architecture.md) that describes a permission, an operation
or a turn is enforced here, not in the client and not in a prompt.

Built under [`specs/001-backend-foundation.md`](../specs/001-backend-foundation.md), to
[its implementation plan](../specs/001-backend-foundation-plan.md).

---

## Running it

The environment is managed by [`uv`](https://docs.astral.sh/uv/). Python 3.12 is pinned; on
this machine `python3` resolves to the Microsoft Store stub, so use `uv run` or `py -3.12`
and never bare `python3`.

```bash
uv sync --all-groups          # create .venv and install, from uv.lock
cp .env.example .env          # then edit STORY_ROOT
uv run uvicorn app.main:app --reload
```

The backend **refuses to start** when `STORY_ROOT` does not contain `canon/project.md`
(FR-STORE-01). That is deliberate: starting against the wrong directory would create a
plausible-looking tree somewhere nobody meant, and the provenance log would faithfully
record it.

A single worker is the supported deployment. A turn holds a lock file under `.index/`
(FR-TURN-05), so a second worker buys nothing.

## The gate

One command, and the thing to paste into a PR (AC 30):

```powershell
.\gate.ps1      # Windows
```

```bash
./gate.sh       # POSIX, and what CI runs
```

Stages: `ruff` → `mypy --strict` → `bandit` → `import-linter` → `semgrep` → JSON Schema
freshness → OpenAPI freshness → `pytest`. Every stage runs even after one fails, so a run
shows everything that is wrong rather than the first thing.

**A stage whose inputs do not exist yet is reported as `SKIPPED` by name.** A gate that
quietly checked less than it looks like it did is worse than a red one.

`semgrep` runs through `uvx`, pinned to one version in both gate scripts, on Windows as on
Linux (plan decision P8, amended by correction C10). It runs twice: `semgrep --test` holds
each rule of record for AC 3, 13 and 17 to its annotated fixture under `semgrep/tests/`, then
a scan of `app/` must be clean. The first run downloads it once. `tools/check_boundaries.py`
mirrors the same rules with the stdlib `ast` module and runs inside `pytest` against the same
annotated fixtures, so a disagreement between the two fails one side or the other.

### Tests

```bash
uv run pytest                    # the offline suite; no network, fake model and embedder
uv run pytest -m model           # needs the real 384-d embedding weights on disk
uv run pytest --live             # a real model through `claude -p`; uses your Claude Code login
```

The offline suite runs with outbound network blocked at the socket layer (NFR-06). Loopback
stays open because the ASGI test client needs it; anything reaching off the machine raises.

Every test that satisfies an acceptance criterion carries `# spec 001 / AC n` (NFR-08), so
the commit that closes the spec can list them.

## Layout

Package by feature, per
[architecture.md](../docs/architecture.md#code-architecture--package-by-feature). A feature
owns its router, service, models, repository and tests. `commons/` holds only what genuinely
crosses features and never imports a feature.

```
app/
  main.py          composes; implements nothing
  commons/
    stores/        the ONLY path to the store tree, and where Figure 3 is enforced
    permissions/   the six roles, the write table, the input table, the tool sets
    schemas/       shared Pydantic models; JSON Schemas exported to ../schemas/
    db/            SQLite, migrations, FTS5, optional sqlite-vec
    embeddings/    fastembed behind a Protocol, with a deterministic fake
    llm/           the `claude -p` client behind a Protocol, with a scripted fake
    errors/        the error types and the IF-07 status-code mapping
    config.py      settings, and the constants no setting may move
  canon/ cast/ scenes/ manuscript/ ledger/ agents/
tests/             cross-feature and end-to-end only; feature tests live in the feature
conftest.py        the shared fixtures (root, so `app/*/tests/` sees them)
```

These boundaries are build failures, not conventions (NFR-04, enforced by `import-linter`):
a feature reaches another only through its `service` and `models`, never its `repository` or
`router`; feature dependencies point downward only (`agents` above `scenes` above `ledger`
above `canon`, `cast` and `manuscript`), so there are no cycles; `commons/` imports no
feature; only `commons.llm` spawns a subprocess; only `commons.embeddings` names `fastembed`;
and only `commons.db` speaks SQLite.

## Configuration

Every key, its default and why it exists are in [`.env.example`](./.env.example). Three are
worth knowing before the first run:

| Key | Why it matters |
|---|---|
| `STORY_ROOT` | The tree. Without `canon/project.md` under it the process will not start. |
| `EMBED_MODEL` | Only 384-d models are accepted. If the prose is Spanish, switch to the multilingual 384-d MiniLM **before** the first `rebuild()` and you avoid a forced re-index later (Decision R2-3). |
| `MODEL_<ROLE>` | Defaults to `claude-haiku-4-5` for every role. Raise one role when a live run shows it missing things; raising the default is a spec change. |

Two numbers are **module constants** in `app/commons/config.py` and deliberately have no
environment key: the 100 000-token context cap (NFR-05) and `TURN_MAX_REVISIONS = 3`
(FR-TURN-02). A setting that could raise either would be a hole in the design.

**No API key is used, anywhere.** Model calls go through the Claude Code CLI (`claude -p`)
under your own Claude Code login (spec FR-LLM-01, decision R3-1), so the CLI must be installed
and logged in on the machine that runs a turn. The backend removes `ANTHROPIC_API_KEY` and
`ANTHROPIC_AUTH_TOKEN` from the CLI's environment even if your shell sets them, so a key can
never silently take over. The CLI is found on `PATH`; on Windows the npm shim is resolved to
the native `claude.exe` it forwards to, and `CLAUDE_CLI` overrides the lookup if that fails.
With `EMBED_OFFLINE=1`, a model missing from the cache stops the start and names the
directory to populate (FR-EMB-03). The offline test suite needs neither the CLI nor a model:
it uses scripted fakes.

## `.index/`

Next to the tree and never committed: the derived index, the embedding-model cache, the
per-turn records and the append-only provenance log. **Nothing under `.index/` is a store**
— it is not governed by Figure 3 and no agent reads it (Decision R2-1).

The index is rebuildable from the tree at will. The turn and provenance records are **not**:
losing `.index/` loses the history of how the tree came to be, though not the tree. That is
a registered accepted risk (AC 31), open until tracing moves those records to Langfuse.
