# `story-maker` — read-only MCP server

Spec [017](../../../specs/017-mcp-tools/017-mcp-tools.md), exam optional X01. It exposes the
gift-novel platform to any MCP client (Claude Code, Claude Desktop, MCP Inspector), built
with [FastMCP](https://gofastmcp.com) over the same validated tool layer (`app/tools/`) the
pipeline uses to build the writer's and editor's context.

## Tools

| Tool | Input | Returns |
|---|---|---|
| `list_novels` | — | every novel with status, latest version and published version |
| `list_versions` | `novel_id` | version history, parent, status and changed chapters per version |
| `get_chapter` | `novel_id`, `version`, `chapter` | title, text, summary, word count, hash |
| `get_chapter_summary` | `novel_id`, `version?`, `chapter` | the chapter digest (latest version if omitted) |
| `query_story_bible` | `novel_id`, `kind` ∈ `characters · places · facts · chronology`, `query?` | the rows of that kind, filtered by substring; facts carry the chapters that use them |
| `download_novel` | `novel_id`, `version?` | the novel as PDF, base64 (`content_base64`, `filename`); latest published version if omitted |

Every tool advertises a JSON Schema for its input **and** its output (pydantic models in
`app/tools/models.py`); arguments are validated before the handler runs and the result is
validated again before it is returned. An invalid call comes back as an MCP error result.

## Guarantees

- **Read-only.** The database is opened with `mode=ro` and `pragma query_only`, no migration
  runs, and every tool is annotated `readOnlyHint: true`. Planner-internal facts (`kind =
  plan`) are never returned. There is no login, so there is no per-user filtering.
- **Traced.** Each call is a Langfuse trace `mcp:<tool>` (session = the novel id, or
  `mcp-server` for `list_novels`) containing the span `tool:<tool>` and a `tool_ok` score
  (1 or 0); a call rejected by the input schema is scored 0 before the database is opened,
  so it has the trace and the score but no span. Langfuse is on when `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` are set (see
  `backend/.env.example`); otherwise the calls run untraced.
- `download_novel` needs the PDF exporter (`app.export.pdf`); without it the tool answers
  with an error saying so.

## Identity (spec 018)

Every tool runs as one owner: the registered user whose email is in `STORY_MAKER_USER`, or
the built-in `local` owner (what the CLI generates) when it is unset. `list_novels` lists
only that owner's novels; every other tool answers "no novel" for anyone else's. An email
that is not registered is an error, never a fallback. Add it to the client's `env`, e.g.
`--env STORY_MAKER_USER=ana@example.com`. The HTTP transport binds `127.0.0.1` and uses the
same identity (token auth for it is deferred).

## Run it

```bash
# from the repository root; HARNESS_DB defaults to data/harness.sqlite
uv run --project backend python -m app.mcp_server            # stdio
uv run --project backend python -m app.mcp_server --http 8765 # streamable HTTP on 127.0.0.1:8765/mcp
```

## Connect a client

**Claude Code.** The repository's `.mcp.json` already declares the server, next to the
Playwright MCP; open Claude Code at the repository root and approve `story-maker`
(`/mcp` lists it). To add it by hand:

```bash
claude mcp add story-maker --env HARNESS_DB=data/harness.sqlite -- \
  uv run --project backend python -m app.mcp_server
```

**Claude Desktop.** Add to `claude_desktop_config.json` (Settings → Developer → Edit
config), with absolute paths because Desktop does not start in the repository:

```json
{
  "mcpServers": {
    "story-maker": {
      "command": "uv",
      "args": ["run", "--project", "/abs/path/My-Story-Marker/backend",
               "python", "-m", "app.mcp_server"],
      "env": { "HARNESS_DB": "/abs/path/My-Story-Marker/data/harness.sqlite" }
    }
  }
}
```

**MCP Inspector.**

```bash
# from the repository root, reusing the .mcp.json entry
npx @modelcontextprotocol/inspector --config .mcp.json --server story-maker          # UI
npx @modelcontextprotocol/inspector --cli --config .mcp.json --server story-maker \
  --method tools/list
npx @modelcontextprotocol/inspector --cli --config .mcp.json --server story-maker \
  --method tools/call --tool-name query_story_bible \
  --tool-arg novel_id=<id> kind=characters
```

Or start it with `--http 8765` and point the Inspector at `http://127.0.0.1:8765/mcp`
(transport "Streamable HTTP").
