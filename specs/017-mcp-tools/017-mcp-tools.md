---
id: 017
title: B3/X — Read-only tools with validated schema and a read-only MCP server
status: implemented      # closed 2026-09-25 on the user's delegation (programme 004 close-out)
supersedes: null
programme: 004
block: B3 (H05) + optional X01
owns:
  - backend/app/tools/**
  - backend/app/mcp_server/**
  - specs/017-mcp-tools/
depends_on: [B1, B6, B3]
provides: [read-only tool layer, MCP server]
consumes: [K1, K2, K5 (app.export, optional)]
closes: [H05, X01]
docs:
  - docs/architecture.md#read-only-tools-for-the-model
  - docs/verification.md#runtime-observability--tracing--d
---

> **Approved 2026-09-24** on the user's delegation for this session (plan 004, deviation V6).
> Process 0 is the programme's: exam brief § 3 "Tools con schema validado" and "Opcional —
> Servidor MCP", and the tool list in `docs/architecture.md` § Read-only tools.

## Motivation

The exam asks for tools with a validated schema (H05) and, optionally, a read-only MCP
server to query and download novels (X01), every call logged to Langfuse. Today the
pipeline reads the bible straight through `BibleRepository`; there is no tool layer, so no
schema at the boundary and no `tool:<name>` span.

## Scope

In:

- `backend/app/tools/`: six read-only tools, each with a pydantic input model and output
  model (their JSON Schemas exported as `input_schema` / `output_schema`); input and output
  are validated on every call; each call runs inside an observer span `tool:<name>`.
  Tools: `list_novels`, `list_versions` (with changed chapters), `get_chapter`,
  `get_chapter_summary`, `query_story_bible` (kind ∈ characters · places · facts ·
  chronology, optional `query` substring filter), `download_novel` (PDF as base64 via
  `app.export.pdf.export_pdf`, imported lazily; a typed error if the module is absent).
- Facts of kind `plan` are never returned (they are the planner's internal notes).
- Writer/editor context: the previous-chapter summaries and a character sheet are assembled
  through `get_chapter_summary` / `query_story_bible` — an in-process call of the same tool
  layer the MCP server exposes (`claude -p` gives the model no native tool calls here).
- `backend/app/mcp_server/`: FastMCP server exposing the six tools, stdio entry point
  `python -m app.mcp_server`, read-only SQLite connection (`mode=ro`), a README on how to
  connect; `.mcp.json` entry `story-maker`.

Out: write tools over MCP (reader change requests), login / per-user identity (there is no
login), HTTP mount under FastAPI (deferred: it changes the API contract and the app
lifespan, and stdio covers every client the exam names), a TLA+ model of the server.

## Design

`app.tools.base.Tool[In, Out]` holds `name`, `description`, the two models and a handler
`(repo, In) -> Out`. `call_tool(name, repo, raw, observer=)` validates `raw` into `In`
(`ToolInputError` on failure, recorded on the span), runs the handler, re-validates the
result against `Out` and returns it. `REGISTRY` maps name → tool. The MCP server registers
one FastMCP tool per registry entry, with the input model's fields as its parameters, opens
the database read-only for each call and wraps it in a Langfuse trace and a `tool:<name>`
span (K2). `docs/architecture.md` says the tools are "served over a local MCP server"; the
pipeline calls the same validated tools in process, which is the same contract without a
subprocess per chapter — recorded here, no doc change.

## Acceptance criteria

1. AC 1 — H05: every tool has a pydantic input and output model with an exported JSON
   Schema; invalid input is rejected before the handler runs. **T**
2. AC 2 — H05: `list_novels` and `get_chapter` return the rows stored through
   `BibleRepository` on a temp DB. **T**
3. AC 3 — H05: the writer's previous summaries and character sheet come through the tool
   layer with a `tool:<name>` span; the pipeline tests still pass. **T · I**
4. AC 4 — X01: `python -m app.mcp_server` answers `tools/list` over stdio with the six
   tools and their schemas; the server never writes (read-only connection). **D · I**
5. AC 5 — X01: each MCP call opens a `tool:<name>` span (Langfuse when keys are set). **I**
6. AC 6 — X01: `app/mcp_server/README.md` explains how to connect Claude Code, Claude
   Desktop and MCP Inspector. **I**
7. AC 7: `ruff` and `mypy --strict` clean on the two packages. **A**

## Verification plan

- AC 1, 2: `backend/app/tools/tests/test_tools.py` (`# spec 017 / AC n`).
- AC 3: `uv run pytest -q app/novel` + review of `app/novel/context.py`.
- AC 4: manual JSON-RPC `initialize` + `tools/list` against the stdio server, result in the
  commit body.
- AC 5, 6: review of `app/mcp_server/server.py` and its README.
- AC 7: `ruff check`, `mypy --strict` output in the commit body.

## Open questions

- HTTP mount at `/mcp` under FastAPI: deferred (see Scope, Out).

## Closing note (2026-09-25)

Closed on the user's delegation (programme 004 close-out, Process 2 step 12). Evidence at
`proyecto-desde-cero` @ `0e8118c`: backend gate `ruff check .` clean, `mypy --strict .`
clean (290 files), `pytest` 1758 passed / 8 skipped / 1 failed. The one failure is
`tests/test_boundaries_mirror.py`, the spec 001 store-boundary guard, which flags file I/O
in the new modules; it is not an acceptance criterion of this spec and is left to the
author (`docs/process/README.md`, "Pendiente para el autor").

| AC | Satisfied by |
|---|---|
| 1 | T — `app/tools/tests/test_tools.py` (pydantic in/out models, invalid input rejected before the handler) |
| 2 | T — `test_tools.py` (`list_novels`, `get_chapter` on a temp DB) |
| 3 | T · I — `app/novel/tests/test_pipeline.py` green; review of `app/novel/context.py` (`tool:<name>` spans) |
| 4 | D · I — JSON-RPC `initialize` + `tools/list` → six tools, recorded in the spec 017 commit body; read-only connection reviewed |
| 5 | I — review of `app/mcp_server/server.py` (`mcp:<tool>` trace, `tool:<tool>` span) |
| 6 | I — `backend/app/mcp_server/README.md` |
| 7 | A — ruff and mypy --strict clean on `app/tools`, `app/mcp_server` |
