---
spec: 001                 # the approved spec this plan implements
status: draft             # draft · approved · done
---

Implementation plan for [`001-backend-foundation.md`](./001-backend-foundation.md)
(status `draft` since 2026-09-23; last approved 2026-09-22). The spec says *what* and *why*; this file says *how* and
*in what order*. Anything not listed under "Files to touch" is out of scope; a file that
turns out to be needed means this plan is wrong and goes back to `draft`.

> **Returned to `draft` on 2026-09-23, with the spec** (Process 2, rule 10). Model calls go
> through the Claude Code CLI under the user's login and no Anthropic API key is used
> (spec Decision R3-1); input tokens are estimated before each call and pruned per role
> (R3-2, FR-CTX); features cross only through each other's public surface (R3-3). What
> changed here: P7 and P10 rewritten, P14 and P15 added, the `commons/llm/` and
> `.env.example` rows, steps 12, 15, 16, 18 and 20, and the verification rows for AC 22, 26
> and 33-35. Steps 1-8 are done. Steps 9-14 do not touch the model client and proceed
> during review at the user's explicit authorisation; step 15 onward waits for re-approval.
>
> **R3-5, same day.** The cap is whole over the context the system sends; the CLI's overhead
> is not budgeted (P7, step 12, AC 26 and AC 35 rows). `commons/llm/tokens.py` and its
> `test_budget.py`, drafted for step 12 but not yet committed, still add the overhead to the
> estimate; they are brought in line with R3-5 before step 12 is committed.

Branch: `spec/001-backend`. Commit prefixes: `backend:`, `contract:`, `chore:`. Every step
is one commit, small enough to review alone, and names the acceptance criteria it advances.
Every test added carries `# spec 001 / AC n`.

---

## Implementation decisions taken while planning

The spec leaves these open at the level of implementation. Each is resolved here with the
plain default; approving the plan approves them. Any one can be changed before approval
without touching the spec.

| # | Decision | Why |
|---|---|---|
| P1 | **`uv`** manages the environment and lockfile (`pyproject.toml` + `uv.lock`); Python 3.12 via the `py -3.12` launcher already on this machine. `uv` is not yet installed and is installed in step 0 with `py -3.12 -m pip install --user uv`, the user’s choice at approval; no remote installer script is run. | `CLAUDE.md` already assumes `uvx`; one lockfile for the gate. |
| P2 | YAML through **PyYAML `safe_load`/`safe_dump`**; Markdown frontmatter through **`python-frontmatter`**. No `ruamel`. | Spec NFR-03; comment preservation is not a requirement. |
| P3 | **`sqlite-vec`** via its PyPI package (`sqlite_vec.load(conn)`), requiring `sqlite3.enable_load_extension`. The python.org 3.12 Windows build supports it; if a platform does not, FR-IDX-03's fallback path is exactly what runs. | Spec FR-IDX-03. |
| P4 | **`fastembed`** pinned; `EMBED_MODEL` default `sentence-transformers/all-MiniLM-L6-v2`; cache under `.index/models/`. | Spec FR-EMB. |
| P5 | Server-Sent Events via **`sse-starlette`**; the turn runs synchronously inside the request on a **single uvicorn worker**. The lock file makes a second worker pointless. | Spec IF-06, FR-TURN-05. |
| P6 | Provenance is **JSON Lines** (`.index/provenance.jsonl`, one object per write); turn records are **YAML** (`.index/turns/NNN-<n>.yaml`, rewritten after each step). | Append-only vs. update-in-place shapes. |
| P7 | Input tokens are estimated by one local function in `commons/llm/tokens.py`, `ceil(characters / 3)` per text the system sends and nothing else, used identically by the assembler, the orchestrator, the live and the fake client. `CLI_OVERHEAD_TOKENS` lives in the same module but is used only to read the real count for `over_cap`. Tests that need a budget breach lower the cap rather than faking the count. | Spec FR-LLM-07, FR-CTX-02, FR-CTX-06, R3-2, R3-5. |
| P8 | **`semgrep` does not run natively on Windows.** The rules of record for AC 3, 13 and 17 are `semgrep` and run in CI (Linux). A local mirror, `backend/tools/check_boundaries.py` (stdlib `ast`, same three rules), runs inside `pytest` on every platform so the local gate is not blind. Both must pass; a disagreement between them is a bug in the mirror. | Developer is on Windows 11. |
| P9 | The fixture novel is written in **English**, so the default embedder is the right one for the fixture and the docs' language matches. Nothing in the fixture depends on the prose language. | Spec R2-3 note. |
| P10 | Structured output is the CLI's `--json-schema` with the DR-12 model's own JSON Schema; the envelope's `structured_output` is validated with the Pydantic model and never repaired. Role prompts are Markdown files loaded at import time with a `prompt_version` equal to their content hash. | Spec FR-LLM-04, FR-AGENT-10. |
| P11 | `import-linter` contracts are the enforcement of NFR-04; `mypy --strict` runs with `pydantic.mypy` plugin; `bandit` at default profile with `B506`. | Spec NFR-01…04. |
| P12 | The CI file is a single GitHub Actions workflow with a two-cell matrix `vec: [present, absent]`, the `absent` cell uninstalling `sqlite-vec` before tests. Live tests never run in CI. | Spec AC 7, NFR-09. |
| P13 | The stale assumption in `.claude/skills/sqlite/references/vectors.md` (that vector search is not the retrieval path for assembly) is corrected as a `chore:` commit in step 1, so the skill does not argue with the spec while code is written. | `AGENTS.md` layer rule: skill docs must not contradict `docs/`. |
| P14 | `ClaudeCodeModelClient` runs `claude -p` with `subprocess.run`, never a shell: argv `--model`, optional `--effort`, `--tools ""`, `--setting-sources ""`, `--strict-mcp-config`, `--disable-slash-commands`, `--no-session-persistence`, `--output-format json`, `--json-schema`, `--system-prompt-file`; documents and instruction on stdin; a fresh `tempfile.TemporaryDirectory()` as the working directory; the parent environment copied with `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` removed; a timeout per call. The binary is found with `shutil.which("claude")` and its `--version` is recorded per turn. | Spec FR-LLM-01, -05, NFR-01, R3-1. |
| P15 | Feature layers for NFR-04: `agents` above `scenes` above `ledger` above `canon`, `cast` and `manuscript`. A feature may import another's `service` and `models` only; a `forbidden` contract bans every other feature's `repository` and `router`. `TurnRecord` goes to `commons/schemas/turn.py` because `canon`'s `reconcile` and `agents` both read it. | Spec NFR-04, R3-3; `architecture.md` rules 2 and 5. |

---

## Files to touch

Paths are relative to the repository root. `backend/app/` is abbreviated `app/`.

### Tooling and root

| Path | Change |
|---|---|
| `backend/pyproject.toml` | Project metadata, pinned dependencies, `ruff`, `mypy --strict` (+ pydantic plugin), `bandit`, `import-linter` contracts, `pytest` markers (`live`, `model`) |
| `backend/uv.lock` | Lockfile |
| `backend/README.md` | Run, test, gate, environment variables |
| `backend/.env.example` | `STORY_ROOT`, `STORY_INDEX`, `EMBED_MODEL`, `EMBED_CACHE_DIR`, `EMBED_OFFLINE`, `MODEL_<ROLE>`, `EFFORT_<ROLE>`, `TURN_REVISE_MAX_CHANGED_RATIO`; no credential of any kind, and a note that none is used |
| `backend/gate.ps1`, `backend/gate.sh` | The one-command local gate (AC 30) |
| `backend/scripts/export_openapi.py` | Writes `backend/openapi.json` from the app |
| `backend/scripts/export_schemas.py` | Writes `backend/schemas/*.v1.json` from the Pydantic models |
| `backend/openapi.json` | Committed contract (IF-08) |
| `backend/schemas/*.v1.json` | Committed JSON Schemas (DR-01) |
| `backend/semgrep/forbidden-store-write.yaml` | AC 3 rule |
| `backend/semgrep/canon-write-outside-promote.yaml` | AC 13 rule |
| `backend/semgrep/hand-written-toolset.yaml` | AC 17 rule |
| `backend/semgrep/tests/{positive,negative}/*.py` | Rule fixtures |
| `backend/tools/check_boundaries.py` | Local AST mirror of the three rules (P8) |
| `.github/workflows/backend.yml` | Static, tests (vec matrix), contract freshness, semgrep |
| `.gitignore` | `.index/`, `.venv/`, `backend/.env` |
| `.claude/skills/sqlite/references/vectors.md` | Correct the stale assumption (P13) |
| `.claude/skills/README.md` | Note the correction; note replacement of the vendored `fastapi` skill by `uvx library-skills` once pinned |

### `app/commons/`

| Path | Change |
|---|---|
| `app/main.py` | App factory, feature routers, exception handlers, `/health` (`vector`, `embedding_model`, `store_root`) |
| `app/commons/config.py` | Pydantic settings from environment; the 100k cap and `TURN_MAX_REVISIONS = 3` as **module constants**, not settings |
| `app/commons/errors/__init__.py` | `InvalidRecord`, `NotFound`, `PermissionDenied`, `IndexBusy`, `TurnLocked`, `ContextBudgetExceeded`, `MalformedModelOutput`, `ModelRefused`, `OutputTruncated` and the handlers mapping them to IF-07 codes |
| `app/commons/permissions/{__init__,roles,table,inputs,toolsets}.py` | `AgentRole`, `WRITE_TABLE`, `may_write`, `INPUT_TABLE` (Figure 3's `In` column as path globs per role), `toolset_for(role)` derived from the write table |
| `app/commons/permissions/tests/test_table.py` | AC 2 |
| `app/commons/permissions/tests/test_toolsets.py` | AC 17 |
| `app/commons/schemas/{__init__,common,scene,knowledge,setup,thread,proposed,violation,draft,digest,change_event,relationship,lexicon,time,role_outputs}.py` | Shared Pydantic models (DR-01…12) |
| `app/commons/schemas/tests/test_enums.py`, `test_roundtrip.py`, `test_json_schema_export.py` | AC 4, 5 |
| `app/commons/stores/{__init__,paths,reader,writer,provenance,frontmatter}.py` | The only file-touching module: id → path, validate-on-read, atomic role-named writes, provenance append |
| `app/commons/stores/tests/test_paths.py`, `test_validate_on_read.py`, `test_atomic_write.py`, `test_permission_refusal.py`, `test_provenance.py` | AC 2 (integration side), 4, 32 |
| `app/commons/db/{__init__,connection,migrations.py,migrations/0001_init.sql,0002_fts.sql,0003_vec.sql,index,rebuild}.py` | SQLite connection (WAL, busy timeout), migrations, FTS5, optional `vec0`, rebuild, status, incremental update |
| `app/commons/db/tests/test_rebuild.py`, `test_migrations.py`, `test_vec_optional.py`, `test_busy.py` | AC 6, 7, 8 |
| `app/commons/embeddings/{__init__,protocol,fake,fastembed_impl}.py` | `Embedder` protocol, `FakeEmbedder`, `FastEmbedEmbedder` with fallback |
| `app/commons/embeddings/tests/test_fake.py`, `test_fastembed.py` (marker `model`) | AC 9 |
| `app/commons/llm/{__init__,protocol,claude_code_client,fake,tokens,errors}.py` | `ModelClient` protocol, the `claude -p` subprocess client (P14), fake with scripted responses and call log, the input-token estimator (P7), typed error chain |
| `app/commons/llm/tests/test_fake.py`, `test_structured_output.py`, `test_refusal.py`, `test_budget.py`, `test_claude_code_command.py`, `test_over_cap.py` | AC 21, 22 (unit level), 34, 35 |
| `app/commons/schemas/turn.py` | `TurnRecord`, read by `canon`'s `reconcile` and written by `agents` (P15) |

### Features

| Path | Change |
|---|---|
| `app/canon/{router,service,models,repository}.py` | Project, style, kinds, lexicon, time; `reconcile` |
| `app/canon/tests/test_read_write.py`, `test_reconcile.py` | AC 14, 29 |
| `app/cast/{router,service,models,repository}.py` | Dossiers, voice, knowledge, changes, relationships; `dossier(at)` |
| `app/cast/tests/test_dossier.py`, `test_read_write.py` | AC 10 |
| `app/scenes/{router,service,models,repository,select,assemble}.py` | Scene CRUD, structure, `select_entities`, `assemble_context` |
| `app/scenes/tests/test_select.py`, `test_assemble.py` | AC 11, 12 |
| `app/manuscript/{router,service,models,repository}.py` | Drafts, digests, `literal_tail` derivation |
| `app/manuscript/tests/test_read_write.py`, `test_literal_tail.py` | DR-11 |
| `app/ledger/{router,service,models,repository,promote,audit/__init__,audit/inv_01,…,inv_10}.py` | Setups, threads, timeline, proposed, violations; `promote`, `rule`; mechanical audit, one module per invariant |
| `app/ledger/tests/test_promote.py`, `test_audit_writes.py`, `test_audit_01.py` … `test_audit_10.py` | AC 13, 15, 16 |
| `app/agents/{router,service,models,turn,lock,records,roles/__init__,roles/writer,roles/style_editor,roles/canoniser,roles/auditor,prompts/*.md}.py` | Roles as functions, orchestrator, lock, turn records, rulings, resume, SSE, rollup |
| `app/agents/tests/scripts/*.yaml` | Scripted fake-model responses per scenario |
| `app/agents/tests/test_turn_happy.py`, `test_turn_escalation.py`, `test_turn_ruling.py`, `test_turn_malformed.py`, `test_turn_budget.py`, `test_turn_resume.py`, `test_turn_provenance.py`, `test_prompts_as_data.py`, `test_role_inputs.py`, `test_handoff_through_stores.py`, `test_rollup.py`, `test_context_pruning.py` | AC 18–24, 32, 33; FR-AGENT-09, FR-AGENT-11 |

### Cross-feature tests and fixtures

| Path | Change |
|---|---|
| `backend/conftest.py` | Temp copy of the fixture repo per test, fake clients wired, network disabled. **Root**, not `tests/` — see correction C1 |
| `backend/tests/fixtures/repo/**` | The fixture novel: `CLAUDE.md` at the store root (protocol and permission table, as the storage layout lists), `canon/`, `cast/`, `structure/`, `scenes/`, `manuscript/` (scene, chapter and arc digests), `ledger/` (including one paid setup, one resolved violation and one resolved thread, so exclusion from context is testable) |
| `backend/tests/fixtures/repo/README.md` | Planted violations, tempting scene, expected outputs (AC 28) |
| `backend/tests/test_turn_selection_shared.py` | AC 12 (writer and auditor see the same list) |
| `backend/tests/test_schemathesis.py` | AC 29 |
| `backend/tests/test_boundaries_mirror.py` | Runs `tools/check_boundaries.py` (P8) |
| `backend/tests/test_health.py` | Startup contract (FR-STORE-01) and `/health` — see correction C2 |
| `backend/.agents/skills/fastapi/**`, `backend/.claude/skills/fastapi/**` | The managed FastAPI skill step 2 installs — see correction C3 |
| `backend/tests/live/test_turn_live.py`, `test_extract_live.py` | AC 26, 27 (`--live`) |

### Corrections to this list, made while implementing

Three paths this list got wrong or left out. None changes the scope, the steps or an
acceptance criterion, so the plan stays `approved`; they are recorded here rather than
applied quietly, because a file list that disagrees with the tree is the thing this section
exists to prevent.

| # | Correction | Why |
|---|---|---|
| C1 | `backend/tests/conftest.py` → `backend/conftest.py` | pytest loads conftests from the rootdir down to each test file. Shared fixtures under `tests/` never reach the feature suites in `app/*/tests/`, and the spec puts feature tests in the feature. The `pytest_plugins` indirection was tried first and fails: pytest registers the module twice, once as a plugin and once as `tests/`' own conftest. |
| C2 | `backend/tests/test_health.py` added | Step 2 has to leave the gate green, and `pytest` exits non-zero when it collects nothing. The file covers the FR-STORE-01 startup refusal and `/health`, and carries `# spec 001 / AC 30`. |
| C3 | The managed FastAPI skill's files added | Step 2 already said to replace the vendored skill with the managed install; the list named only `.claude/skills/README.md`, not the files the install writes. `--copy` rather than the default symlink, which would point into the git-ignored `backend/.venv/`. |
| C4 | **Decision P2 amended.** Markdown frontmatter is split in `commons/stores/frontmatter.py` with `yaml.safe_load`, not by `python-frontmatter`, which is dropped as a dependency. | The library strips leading and trailing whitespace from the body. For `manuscript/NNN.md` the body *is* the novel: a deliberate blank line at the end of a scene is a beat, an indented opening is a choice, and `literal_tail` exists because summaries lose how it sounded. The loss is invisible - the file still parses and still validates - and the round-trip property of AC 4 is what surfaced it. P2's stated reason (safety, no `ruamel`) is untouched: the frontmatter block is still `safe_load`. |
| C5 | `backend/app/commons/stores/tests/test_frontmatter.py` and `backend/tools/__init__.py` added | The first pins C4's byte-faithfulness with the cases that motivated it; the second makes `tools.check_boundaries` importable from `tests/test_boundaries_mirror.py`. |
| C6 | `backend/app/commons/deps.py` added, and `InvalidRole` added to `commons/errors/` | The FastAPI dependencies every router shares: the one `Store` a request may use, and the `X-Agent-Role` / `X-Actor` headers of IF-02. Each router declaring its own would be a router that could point at another directory or default a role, and a provenance log that records a guessed role is not evidence. `InvalidRole` is the 400 IF-02 requires and IF-07 does not list. |
| C7 | `backend/tests/test_fixture_validates.py` and `backend/tests/test_api_contract.py` added | Both are cross-feature by necessity - they need the feature-owned models and routers as well as the shared ones, and a test inside `app/commons/` may not import a feature (NFR-04). `tests/` is where `architecture.md` puts cross-feature tests. |
| C8 | `backend/app/commons/stores/turns.py` added, with `Store.turn_records()` and `Store.read_mapping()` | `reconcile` (in `canon/`) must read turn records, and `canon/` sits below `agents/` in the NFR-04 layers and may not touch files itself; `commons/stores/` already reads `.index/provenance.jsonl` for the same reason. `read_mapping` gives the derived index text without validation, because the index must build rows from files whose models live in features `commons/` may not import. |

---

## Steps

Each step is one commit. "Advances" names the acceptance criteria the step moves; a
criterion is *satisfied* only when its verification in the mapping below passes.

| # | Commit | What | Advances |
|---|---|---|---|
| 0 | — | Confirm the branch is `spec/001-backend` and the tree is clean. Install `uv`. | — |
| 1 | `chore:` | Correct the stale vector assumption in the `sqlite` skill; note in `.claude/skills/README.md` that the vendored `fastapi` skill is replaced by `uvx library-skills` in step 2. | — |
| 2 | `backend:` | `pyproject.toml` with every pinned dependency, `uv.lock`, tool configuration, `import-linter` contracts (NFR-04), package skeleton with empty feature folders, `app/main.py` with `/health`, `config.py`, `errors/`, `gate.ps1`/`gate.sh`, `.gitignore`, `.env.example`, `README.md`. Gate passes on an empty app. Replace the vendored `fastapi` skill with the managed install. | AC 1, 30 |
| 3 | `backend:` | Shared Pydantic models and enums (`commons/schemas/`), `export_schemas.py`, committed `schemas/*.v1.json`; enum and round-trip tests. | AC 4 (model half), 5 |
| 4 | `backend:` | Fixture repository and its `README.md`: store-root `CLAUDE.md`, three characters, two locations with a parent, four axioms (one pinned by tag), lexicon with forbidden variants and `used_by`, six scenes in non-monotonic discourse order across two chapters, two drafts, scene and chapter digests (one chapter digest whose `povs` excludes a later scene's POV, one covering a scene later in story time than the tempting scene), one registered and one unregistered body change, setups (one overdue, one paid), threads (one over latency, one resolved), one resolved violation, and the tempting scene. | AC 28 (draft), enables 12, 15, 26, 27 |
| 5 | `backend:` | Permission table, `AgentRole`, `may_write`, `INPUT_TABLE` (Figure 3 `In` column), `/permissions` route exporting both tables; table test. | AC 2 |
| 6 | `backend:` | Store layer: paths, frontmatter, validate-on-read, atomic role-named writes, provenance JSONL; `semgrep` rule for forbidden store writes plus the AST mirror; store tests. | AC 3, 4 (read half), 32 (store half) |
| 7 | `backend:` | Feature read and write routers for `canon`, `cast`, `structure`, `scenes`, `manuscript`, `ledger` (IF-03, IF-04) with `X-Agent-Role` / `X-Actor` handling; `export_openapi.py` and first committed `openapi.json`. | AC 29 (partial) |
| 8 | `backend:` | Embedder protocol, fake, `FastEmbedEmbedder` with fallback and cache dir; tests (`model` marker for the real one). | AC 9 |
| 9 | `backend:` | SQLite layer: connection, migrations, FTS5, optional `vec0`, `rebuild` over `canon/` (one row per entity file, and **one row per term** of `lexicon.yaml`), `cast/` and **chapter-level digests only** (scene and arc digests are not rows), incremental update, `/index/rebuild`, `/index/status`, `/health.vector`; rebuild, migration, optional-vec and busy tests, plus a test that a scene digest never becomes a row. | AC 6, 7, 8 |
| 10 | `backend:` | `dossier(character, at)` and `/cast/{id}/dossier?at=`; unit and property tests. | AC 10 |
| 11 | `backend:` | `select_entities` with BM25 + cosine fused by reciprocal rank, pins first, POV excluded; `/scenes/{id}/select`. | AC 11 |
| 12 | `backend:` | `assemble_context`: fixed block, POV dossier, literal tail, ranked as-of loading (chapter digests only when every covered scene is `<= T`, labelled "not witnessed" when `povs` lacks the POV; lexicon through `used_by`; open setups under a *may collect* label; resolved violations, paid setups and closed threads excluded), 100k stop counted with the writer's mandatory part first (spec FR-OPS-03), `truncated_at`, fixed-block warning; token estimate through the pure functions of `commons/llm/tokens.py` (P7), with no overhead in it; `/scenes/{id}/assemble`. Tests include: no raw `manuscript/NNN.md` text in the context except the previous scene's tail. | AC 12 (assembly half) |
| 13 | `backend:` | `promote`, `rule`, `reconcile`; `semgrep` rule and mirror for canon writes outside `promote`/`rule`; routes. | AC 13, 14 |
| 14 | `backend:` | Mechanical audit, one module per invariant, `/scenes/{id}/audit?semantic=false`, persistence only under auditor + `persist=true`; golden tests on the fixture and the write-scope test. | AC 15, 16 |
| 15 | `backend:` | Model client: protocol, `ClaudeCodeModelClient` as P14 (Haiku default through `--model`, optional `--effort`, `--json-schema` structured output, envelope checks of `is_error` / `subtype` / `stop_reason` / `api_error_status`, the input-token estimate before the call and the real count after, `over_cap`, typed error chain), `FakeModelClient` with scripts and call log; unit tests, including the constructed command, working directory and environment. | AC 21, 22 (unit), 34, 35 |
| 16 | `backend:` | Tool sets derived from the write table (the writes the orchestrator performs with a role's output; the model itself holds no tools); prompt assembly with store content as delimited data on stdin, each document tagged with its source path, and nothing from the stores in the system prompt file; the assembler refuses a document whose path is outside the role's `INPUT_TABLE` row; role prompt files (the writer's states dramatic function only and offers setups, never assigns one); `semgrep` rule and mirror against hand-written tool lists. | AC 17, 23; FR-AGENT-09 |
| 17 | `backend:` | Roles as functions: writer `write`/`revise`/`digest`/`rollup`, style editor `polish`, canoniser `extract_facts`, auditor `audit_semantic`; combined `audit`; `/scenes/{id}/audit` full; `/agents/digests/rollup`. Tests with scripted fakes. | AC 15 (skipped list), 21 |
| 18 | `backend:` | Turn orchestrator: state machine, lock, turn records after each step, hand-off **through the stores** (audit reads the draft back from `manuscript/`, revise reads blocking violations back from `ledger/violations.yaml`; the orchestrator passes ids only), revise scope guard, extraction on the accepted draft, promotion followed by `reconcile` on each promoted target, `words` vs `budget` and digest length vs level target on the record, chapter-complete hint, `awaiting_ruling`, `rulings` (also running `reconcile` on `accept`), `resume`, SSE progress, `dry_run`, per-role pruning (FR-CTX-03/-04) with removed ids and `truncated_at` on the record. Scenario tests (happy, escalation after 3, revise rejected, collision and rulings, malformed, refusal, budget, resume, provenance), plus: after a merged turn, a `dry_run` of the next scene in discourse order contains the promoted fact ("canon is updated before the next scene is assembled"); the fake call log shows the revise step's violations equal to the file's content and each role's documents inside its `INPUT_TABLE` row. Cross-feature test that writer and auditor receive the same selected list. | AC 12 (turn half), 18–24, 32, 33; FR-AGENT-09, FR-AGENT-11, FR-TURN-04 |
| 19 | `contract:` | Regenerate `openapi.json`; `schemathesis` test; CI workflow with the `vec` matrix, static gate, `semgrep`, contract freshness. | AC 7 (matrix), 29 |
| 20 | `backend:` | Live tests behind `--live`: one full turn on the tempting scene and one extraction, through `claude -p` under the user's Claude Code login. No API key exists anywhere to run them with. Written and committed by the agent; run by the user, with the output saved to `backend/tests/live/last_run.md` for the PR. | AC 26, 27 |
| 21 | — | Human review of the fixture `README.md` against the actual audit output (AC 28). Run the full gate, paste the output, open the PR `spec(001): Backend v1 — …` listing every criterion with its verification. | AC 28, 30 |
| 22 | `spec(001):` | After merge: spec to `implemented`, this plan to `done`, listing per criterion the test, check or run that satisfied it. | — |

Steps 3–6 can be developed in parallel branches off `spec/001-backend` but are merged in
this order so that every commit passes the gate on its own.

---

## Verification mapping

| AC | Letter | Verification | Lives in |
|---|---|---|---|
| 1 | A | `ruff check`, `mypy --strict`, `bandit -r`, `lint-imports` all zero findings | `pyproject.toml`; CI `static` |
| 2 | T | Parametrised test: 6 roles × 7 store families → exactly Figure 3's outcomes; integration: `PUT` with each forbidden role → `403`, tree unchanged | `commons/permissions/tests/test_table.py`, `commons/stores/tests/test_permission_refusal.py` |
| 3 | A | `semgrep` rule fires on `semgrep/tests/positive/`, silent on `app/`; AST mirror agrees | `semgrep/forbidden-store-write.yaml`, `tests/test_boundaries_mirror.py` |
| 4 | T | Every fixture file validates; mutated copy → `InvalidRecord(file, field)`; `hypothesis` round-trip per model | `commons/schemas/tests/test_roundtrip.py`, `commons/stores/tests/test_validate_on_read.py` |
| 5 | T | Each enum rejects out-of-enum strings and `True`/`False` | `commons/schemas/tests/test_enums.py` |
| 6 | T | Rebuild twice → identical rows and vectors; delete + rebuild → same; orphans 0; migrate v0 copy → schema equals fresh | `commons/db/tests/test_rebuild.py`, `test_migrations.py` |
| 7 | T | With `sqlite_vec` import patched to fail: startup ok, `/health.vector == "unavailable"`, FTS5 results; with it: fused results, `vec0` dim 384. CI matrix runs both cells for real | `commons/db/tests/test_vec_optional.py`; `.github/workflows/backend.yml` |
| 8 | T | Two `multiprocessing` writers, 200 writes each → row count exact, `PRAGMA integrity_check` ok; forced busy → `503` after timeout | `commons/db/tests/test_busy.py` |
| 9 | T | Fake: 384-d, unit norm, deterministic. Real (`model` marker): loads primary or falls back, 384-d, same vector across two processes; changed `embedding_model` metadata forces rebuild | `commons/embeddings/tests/test_fake.py`, `test_fastembed.py` |
| 10 | T | Fixture cases + `hypothesis` over generated knowledge, valence and arc tables: nothing dated after `at`; the arc entry is the latest anchored at or before `at` | `cast/tests/test_dossier.py` |
| 11 | T | Result type has no text field; pins first in order; POV absent | `scenes/tests/test_select.py` |
| 12 | T | Property: no `acquired_in` later than scene; no chapter digest covering a scene later than `T`; "not witnessed" label when `povs` lacks the POV; paid setup, resolved violation and resolved thread absent; no raw manuscript text but the tail; token stop before cap; no partial entry; turn record list == auditor input | `scenes/tests/test_assemble.py`, `tests/test_turn_selection_shared.py` |
| 13 | T, A | Promote non-conflict → record changed, status `promoted`; conflict → `Escalation`, tree byte-identical, `conflict=True`; `semgrep` + mirror: no canon write under `ledger/`/`agents/` outside `promote`/`rule` | `ledger/tests/test_promote.py`, `semgrep/canon-write-outside-promote.yaml` |
| 14 | T | Superset of hand-labelled dependents for the three fixture entities; property over generated scenes | `canon/tests/test_reconcile.py` |
| 15 | T | Golden violations per planted case, correct severities, clean control scene empty; `skipped` list when the model step is disabled | `ledger/tests/test_audit_0N.py`, `agents/tests/test_turn_happy.py` |
| 16 | T | Tree hash before/after: only `ledger/violations.yaml` differs and only under auditor + `persist=true`; other roles → `403`, hash equal | `ledger/tests/test_audit_writes.py` |
| 17 | T, A | Enumerate `toolset_for(role)`: writer has no `canon/**`, auditor only `ledger/violations.yaml`, canoniser nothing under `manuscript/`; `semgrep` + mirror: no literal tool lists in `agents/` | `commons/permissions/tests/test_toolsets.py`, `semgrep/hand-written-toolset.yaml` |
| 18 | T | Fake happy-path script → `merged`; draft, digest, proposed facts, turn record (with `reconcile` results, `words` vs `budget`, chapter hint) on disk; provenance role per file matches Figure 4; next scene's `dry_run` sees the promoted fact | `agents/tests/test_turn_happy.py` |
| FR-AGENT-09 | T | Every document in every fake call has a source path inside the calling role's `INPUT_TABLE` row; a planted out-of-row document is refused by the assembler | `agents/tests/test_role_inputs.py` |
| FR-AGENT-11 | T | The revise call's violations document equals `ledger/violations.yaml` as written by the auditor step; the audit call's draft document equals `manuscript/NNN.md` as written by the writer step; the orchestrator's step inputs are ids only (type check + log) | `agents/tests/test_handoff_through_stores.py` |
| 19 | T | Always-blocking script → `escalated` after exactly 3 revisions, last draft and violations on disk; 60 %-change script → rejected twice → `escalated` | `agents/tests/test_turn_escalation.py` |
| 20 | T | Colliding extraction → `awaiting_ruling`; `accept` → promoted + `merged`; `reject` → `rejected` + `merged`; second turn while pending → `409` | `agents/tests/test_turn_ruling.py` |
| 21 | T | Schema-invalid script → one retry, then `MalformedModelOutput`, `manuscript/` untouched; refusal script → `escalated` with category | `agents/tests/test_turn_malformed.py`, `commons/llm/tests/test_refusal.py` |
| 22 | T | Estimate above the (lowered) cap → zero `complete` calls in the log, `ContextBudgetExceeded`, `escalated` | `agents/tests/test_turn_budget.py`, `commons/llm/tests/test_budget.py` |
| 23 | T | Inspect every recorded fake call: `system` contains no substring of any store file; every document block delimited and labelled with its path; no call carries a previous call's output except as a store-backed document; the writer's instruction offers setups under *may collect* and names none as required | `agents/tests/test_prompts_as_data.py` |
| 24 | T | Kill after write step (script raises), resume → audit onward, exactly one `write` call in the log | `agents/tests/test_turn_resume.py` |
| 25 | U | Registered | `docs/verification.md` U register (`95e0cd5`) |
| 26 | D | `--live` full turn on the tempting scene through `claude -p`, run by the user; assert the axiom violation and the unregistered body change are flagged, the registered one is not; record shows real model ids, cache-read tokens, every step's estimate < 100k and real count minus `CLI_OVERHEAD_TOKENS` < 100k; output committed as evidence | `tests/live/test_turn_live.py`, `tests/live/last_run.md` |
| 27 | D | `--live` extraction returns the two hand-labelled invented facts | `tests/live/test_extract_live.py` |
| 28 | I | Human reads the fixture `README.md` against actual audit output; note in the PR | `tests/fixtures/repo/README.md` |
| 29 | T | `export_openapi.py` output equals committed file (CI fails on diff); `schemathesis` run yields no `5xx` | `tests/test_schemathesis.py`; CI `contract` |
| 30 | D | `gate.ps1` / `gate.sh` green; output pasted in the PR | PR description |
| 31 | U | Registered | `docs/verification.md` U register (`95e0cd5`) |
| 32 | T | After the fake turn, one provenance line per store write with the Figure 4 role and `actor: agent`; `PUT` with `X-Actor: human` → line with `actor: human` | `commons/stores/tests/test_provenance.py`, `agents/tests/test_turn_provenance.py` |
| 33 | T | Cap lowered: whole prunable entries removed lowest rank first per role, none cut; removed ids and `truncated_at` on the record; auditor removals in `skipped`; mandatory overflow → `ContextBudgetExceeded`, no call | `agents/tests/test_context_pruning.py` |
| 34 | T | Recorder in place of the subprocess: argv carries `--tools ""`, `--setting-sources ""`, `--json-schema`, `--no-session-persistence`, never `--bare`; cwd empty and outside the repo and store root; env has no `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN` although the parent's does | `commons/llm/tests/test_claude_code_command.py` |
| 35 | T | Scripted envelope reporting more input tokens than cap + `CLI_OVERHEAD_TOKENS` → step marked `over_cap: true`; one reporting between cap and cap + overhead → not marked; the estimate of an empty call is zero | `commons/llm/tests/test_over_cap.py` |

Every **T** test is shown to fail before its step's code exists (Process 3 rule 15): the
commit message of each step names the test and states that it was red on the parent commit.

---

## Coverage of `architecture.md`

Section by section, where each mechanism the doc describes lands in this plan. The gap the
user asked to drive to zero is the set of rows that are neither *covered* nor *deferred
by name*. Three passes found ten, then four, then zero omissions; two doc tensions the
passes surfaced were resolved in `docs/` (Process 1) rather than worked around here. One
row remains deferred by name, at the end.

| Architecture section | Mechanism | Plan | Status |
|---|---|---|---|
| Governing principle | Manuscript never in context beyond tail and digests | Step 12 test | Covered |
| Governing principle | Prose cannot edit canon | Steps 5, 6, 16; AC 2, 3, 17 | Covered |
| Figure 1 | assemble · write · extract · promote · audit · revise | Step 18 | Covered |
| Figure 1 | "escalate ruling" dotted edge | `PUT /ledger/violations` as auditor + `X-Actor: human` (spec IF-04); step 7 | Covered |
| Figure 1 | Auditor reports, never repairs | AC 16 | Covered |
| L4 · Draft | `words` against budget; `literal_tail` 500 words | Steps 17, 18; `manuscript/tests/test_literal_tail.py` | Covered |
| L4 · SceneDigest | Levels and word targets; `povs` filters; chapter level indexed | Steps 9, 12, 17, 18 | Covered |
| L4 · ProposedFact | No automatic promotion on conflict | AC 13, 20 | Covered |
| L4 · Violation | Evidence with position; severity; resolution | Steps 14, 17; IF-04 | Covered |
| Operations | `dossier` as-of | AC 10 | Covered |
| Operations | `select_entities` ids only, pins first, POV by id | AC 11 | Covered |
| Operations | `select_entities` embeds the architect's `notes` | Scene has `notes`; step 11 embeds it | Covered |
| Operations | `assemble_context` ranked as-of loading to the cap | AC 12 | Covered |
| Operations | `extract_facts` on the accepted draft; writer proposals from every iteration kept | Step 18 (spec FR-TURN-03) | Covered |
| Operations | `promote` escalates collisions | AC 13, 20 | Covered |
| Operations | `reconcile` on retroactive change | Step 13; wired into promotion and rulings, step 18 | Covered |
| Memory tiers | Agents stateless; no transcript between roles | FR-AGENT-11 test; AC 23 | Covered |
| Memory tiers | `promote` the only write into canon during drafting | AC 13, 17 | Covered |
| Memory tiers | Forgetting by rollup at boundaries | Manual `rollup` route + chapter-complete hint on the record | Covered (trigger manual, per spec) |
| Memory tiers | Closed items leave the working tier | Step 12 exclusion tests | Covered |
| Memory tiers | Index derived; orphan = bug | AC 6 | Covered |
| Memory tiers | 100k cap, per call, never accumulated | AC 12, 22 | Covered |
| Memory tiers | Selection not reproducible; ids traced | Turn record; AC 12 | Covered |
| Figure 2 | Fixed block < 800 tokens | FR-OPS-04 warning; step 12 | Covered |
| Figure 2 | Parent chain for locations; lexicon by `used_by` | Step 12 | Covered |
| Figure 2 | Setups offered, not assigned | Step 16 prompt; AC 23 test | Covered |
| Figure 3 | Write table; two inbound edges into canon | AC 2, 13, 17 | Covered |
| Figure 3 | `In` column: nothing else available | `INPUT_TABLE`; FR-AGENT-09 test | Covered |
| Figure 3 | `write` vs `revise` not interchangeable | Revise scope guard; AC 19 | Covered |
| Figure 3 | Architect and world builder | Human under the role via CRUD (spec Decision 5) | Covered, model-invoked deferred |
| Figure 3 | Human ruling on collisions | AC 20 | Covered |
| Figure 4 | Order of steps; audit before extraction | Step 18 | Covered |
| Figure 4 | Canon updated before next scene | Step 18 next-scene `dry_run` test | Covered |
| Figure 4 | Bounded revise loop | AC 19 | Covered |
| Storage layout | Every path; `.index/` | Steps 4, 6; spec FR-STORE, FR-TURN-07 | Covered |
| Storage layout | Stable identifiers; renaming breaks the graph | FR-STORE-05 id grammar; DR-08 no rename; step 6 | Covered |
| Storage layout | Git gives canon versioning and continuity diffs | Tree is a git working tree the human commits; backend runs no git (spec Out) | Covered, automation deferred to branch-per-turn spec |
| Operations · index | One row per entity, including one per lexicon term and per chapter digest | Step 9 | Covered |
| Storage layout | Store-root `CLAUDE.md` | Fixture file, step 4 (informational: enforcement is in the backend) | Covered |
| Stack | Backend the only process on the stores; frontend via API | NFR-04 contracts; frontend deferred to its own spec | Covered |
| Package by feature | Rules 1–5 | `import-linter` contracts (independence, layers, acyclicity); AC 1 | Covered |
| Package by feature | Tests live in the feature; `backend/tests/` cross-feature only | File list follows it; `tests/` holds conftest, fixture, shared-selection, schemathesis, live | Covered |
| Package by feature | Frontend rules 6–8 | Frontend deferred to its own spec | Deferred by name |
| Over-constraint | Flag, don't repair; function, not how | AC 16; writer prompt, step 16; fixture review AC 28 | Covered |
| TemporalSystem (via `transit_matrix`) | `dilation_factor` per character | Not applied in the transit check | **Deferred by name** — later spec |

**Deferred, named so nobody mistakes it for coverage:**

- **Relativistic dilation.** `dilation_factor` exists in `TemporalSystem` but the v1
  transit check compares raw `story_time`. Deferred to the spec that makes invariant 5
  character-relative; the fixture has no relativistic transit, so nothing in v1 is wrong,
  only incomplete.

---

## Risks and stop conditions

What could make this plan wrong, and what the agent does if it happens. Any of the first
group **reopens Process 0**: the plan returns to `draft`, the new fact is asked with a
recommendation, and coding stops until the plan is re-approved.

**Reopen Process 0 if:**

- A role needs to write a path its Figure 3 row does not allow. This is a permission
  change and goes to Process 1, never into code (Process 3 rule 12).
- A store record needs a field `definitions.md` does not list, or a file the storage
  layout does not name.
- A step needs a file outside "Files to touch".
- `sqlite3.enable_load_extension` is unavailable on the developer's Python **and** the
  fallback path is judged insufficient for v1 (the spec says it is sufficient; if the user
  disagrees on seeing it, that is a decision, not a fact).
- `fastembed` cannot load either 384-d model on the developer's machine. The fallback
  chain would then need a third model or a different dimension, which changes FR-IDX-03.
- `claude -p --json-schema` rejects a DR-12 schema shape (for example a deeply nested
  union). Flattening a schema is a spec change to DR-12.
- The Claude Code CLI changes a flag or the shape of its JSON envelope. P14 records its
  version per turn and AC 34 pins the command, so the change is caught; adapting to it is a
  plan change, and dropping an isolation flag is a spec change to FR-LLM-05.
- The organisation's managed instructions visibly alter role output in the live run (for
  example anonymised names in the prose). The backend cannot remove them; how to respond is
  the user's decision.
- The revise scope guard (35 %) rejects every live revision. That is data the spec asked
  for (R2-8) and the threshold is a spec value.

**Handle inside the plan, with a note in the commit:**

- `semgrep` unavailable locally → the AST mirror is the local check; CI is authoritative
  (P8).
- A `hypothesis` property finds an input the fixture did not anticipate → fix the code if
  the property is right, or narrow the strategy with a comment linking the invariant if the
  input is out of domain; never delete the property.
- Live run (AC 26/27) misses a planted item → record the miss in `last_run.md`; the
  criterion is **D** and the miss is the finding. Raising a role's model via
  `MODEL_<ROLE>` is allowed by the spec; changing the default is not.
- The CLI returns an unexpected `stop_reason` or `subtype` → surfaces as a typed error, the
  turn escalates; add the case to the fake scripts.
- The Claude Code login has expired or hits a usage limit → the step fails with the CLI's
  message and the turn escalates; nothing falls back to an API key, because none exists.
- `SQLITE_BUSY` test flaky on CI → increase the busy timeout in the test fixture only,
  never in production config, and record why.

**Known constraints carried from the environment:**

- Windows developer machine: `python3` resolves to the Microsoft Store stub; use
  `py -3.12` or `uv run`. The `gate.ps1` script uses `uv run` throughout.
- `.index/` records are not rebuildable (AC 31). Tests never write to a real `.index/`;
  `conftest.py` points `STORY_INDEX` and `EMBED_CACHE_DIR` at the temp copy, except the
  `model`-marked embedder test, which reuses the real model cache to avoid a download per
  run.
