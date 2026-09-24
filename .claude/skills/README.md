# Vendored skills

Skills committed into this repository, with their provenance. Every entry says where it
came from and under which licence, so a reader can tell an official upstream skill from a
third-party one.

| Skill | Source | Official? | Licence | Added |
|---|---|---|---|---|
| ~~`fastapi/`~~ | **Moved.** Now a managed install under `backend/`, see below | Yes, by the FastAPI project | MIT | 2026-09-21, replaced 2026-09-22 |
| `react/` | Written for this repository | No, ours | This repo | 2026-09-21 |
| `sqlite/` | Written for this repository | No, ours | This repo | 2026-09-21 |
| `sqlite-vec/` | MCPmarket installer payload, skill files only (see below) | No, third party | Not stated | 2026-09-21 |
| `verification/` | Written for this repository, around a third-party reference sheet (see below) | No, ours | This repo | 2026-09-21 |
| `gift-novel-run/` | Created in this repository (spec 016, block B12) | No, ours | This repo | 2026-09-24 |
| `security-review-harness/` | Created in this repository (programme 004, exam X04) | No, ours | This repo | 2026-09-24 |

## FastAPI

The FastAPI skill is shipped **inside the Python package**, not in the GitHub repository,
and is versioned in lockstep with the library. Upstream distributes it through
[library-skills](https://github.com/tiangolo/library-skills), which reconciles the skill
against the installed dependency.

**The vendored copy is gone.** `backend/` now exists and pins `fastapi==0.141.1`, so the
skill is a managed install taken from that pinned wheel:

```bash
cd backend
uvx library-skills --no-tool-skill install --claude --copy -s fastapi -y
```

It lands in two places, which is the tool's own layout: `backend/.agents/skills/fastapi/`
(the cross-agent standard location) and `backend/.claude/skills/fastapi/` (what Claude Code
reads). Being under `backend/` is not an accident of where the virtualenv lives — it is
correct: the skill applies to the backend and Claude Code picks it up as a directory-scoped
skill, so it does not advertise itself while someone is working in `frontend/`.

`--copy` rather than the default symlink, deliberately. A symlink would point into
`backend/.venv/`, which is git-ignored: the skill would be present for whoever ran
`uv sync` and a dangling link for everyone else, including CI. Copies are committed,
reviewable and diffable, which is the property every other skill here has.

The copy is byte-identical to the vendored one it replaced, which is the evidence that the
hand-vendoring had been accurate. Drift is prevented by re-running the command and checking
that git reports no change; CI does exactly that (plan step 19). When `fastapi` is bumped in
`pyproject.toml`, re-run the command in the same commit.

`LICENSE` is the one file in those directories that the wheel does not provide. It is added
by us so the MIT terms travel with the copied files, and a drift check ignores it.

## sqlite-vec, and why only part of it was installed

`sqlite-vec/` came from an MCPmarket install link of the form
`curl -sSL https://app.mcpmarket.com/install/<token> | bash`. **The script was not run.** It
was downloaded, decoded and inspected, and only the five skill files were taken.

The script does considerably more than add a skill. Had it run, it would have:

- installed a plugin into `~/.claude/plugins/mcpmarket-me`, outside this repository and
  affecting every project on the machine;
- registered an MCP server pointing at a remote MCPmarket gateway, authenticated with a
  personal bearer token embedded in the script;
- installed **hooks**: one on `SessionStart` (startup, resume, clear and compact) and one
  after every `Skill` call, each executing a bundled shell script;
- run a 33 KB `sync.sh` on every session start, which pulls skill content from the remote
  service, so the installed skills could change later without review;
- modified the global `settings.json` and plugin registries through the `claude` CLI.

None of that is needed to use a skill, and all of it is persistent, global and outside
version control. Skills in this repository are committed, reviewed and diffable, which a
remotely synced skill is not.

The skill files themselves were checked and contain no credentials, no scripts and no
network calls. They are plain reference documentation and are committed byte-identical to
the payload, so they can be diffed against the source.

**The token.** The installer embedded a live personal API token for the MCPmarket account,
in plain text, together with a personalised gateway URL. Anyone holding the install link
can retrieve that token by fetching it, exactly as was done here. Treat any such link as a
secret, and rotate the token if the link has been shared. No token was written into this
repository.

If the MCPmarket integration is wanted for its own sake, install it deliberately and with
the hooks understood, not as a side effect of adding one skill.

## Verification

`verification/` replaced an earlier skill of the same name that was a raw prompt with no
frontmatter — it could not be invoked and it duplicated `docs/verification.md` instead of
saying how to build it. The procedure in `SKILL.md` is ours.

`verification/references/methodologies.md` is the list of methodologies, definitions and
source links from a public Claude artifact, "Verification Methodologies — Reference Sheet"
(`claude.ai/artifact/Rass3RVfaN5KSJDdG2FQhR`), authored outside this organisation. It was
read as data, not executed, and it contains only prose, tables and links to Wikipedia,
arXiv, ACM, OpenTelemetry, NIST, OWASP and martinfowler.com. No licence is stated on it.
The definitions are short and factual, but if that matters for redistribution, rewrite them
rather than assuming permission.

The links were transcribed as the artifact gave them and have not been fetched. Check one
before citing it as authority.

## React and SQLite

**No official agent skill exists for either**, as of 2026-09-21, so `react/` and `sqlite/`
were written for this repository against the official documentation. They are ours. Do not
describe them as upstream.

Why there was nothing to vendor:

- The `react` npm package ships no skill. The React repository does contain
  `.claude/skills/`, but those exist to develop React itself: they run `yarn linc`, Flow
  type checks and the React test suite. They are wrong for an application that merely
  consumes React.
- SQLite is a public-domain project that publishes no agent tooling. Everything available
  is third party.

### Maintaining the two we wrote

Both state the versions they were written against, in a table at the top of their
`SKILL.md`. Those versions are the expiry date. When the project upgrades past them, re-check
the skill against the current documentation rather than trusting it.

| Skill | Written against |
|---|---|
| `react/` | react 19.3.0, three 0.186.0, @react-three/fiber 9.7.0, @react-three/drei 10.7.8 |
| `sqlite/` | sqlite-vec 0.1.9, aiosqlite 0.22.1, Python 3.12+ |

`sqlite-vec` is pre-v1 and its authors say to expect breaking changes, so it is the entry
most likely to go stale.

`sqlite/references/vectors.md` used to carry an **assumption**, flagged in its own text:
that vector search was a secondary tool and not the retrieval path for `assemble_context`,
because `architecture.md` was read as ruling out semantic similarity for context assembly.

**That reading was wrong and the page has been corrected.** `architecture.md` splits
assembly into a semantic `select_entities` and a deterministic as-of load: vector search,
fused with FTS5, *is* the selection path, and what it returns is identifiers, never text.
The line it may not cross is the load. The page now states that split, the two hard
constraints that come with it (the extension is optional; 384 dimensions fixed), and why
unreproducible selection is an accepted risk rather than a defect. The docs did not change;
the skill had been arguing with them.

## gift-novel-run

The harness's own reusable skill (exam § 3, requirement H02), created in this repository
under spec 016. It runs and inspects one generation end to end: brief validation,
generation, checkpoints, validator results in the SQLite story bible, the Langfuse trace,
the web reader through Playwright MCP (`.mcp.json`) and the PDF export. It wraps
operations other blocks provide and changes nothing itself. Its steps name the CLI and
tables of plan 004's contracts; refresh them when blocks B3 and B10 merge.

## security-review-harness

The harness's security-analysis skill (exam, optional item X04), created in this repository
under programme 004. It re-runs the review recorded in
[`docs/security-report.md`](../../docs/security-report.md): secrets in the git history,
dependency audits (`pip-audit`, `npm audit`), prompt injection through the brief's free text
and the reader's change requests, exfiltration between novels through the reader API, the
tools and the MCP server, the Claude Code policy hooks, and an API-hardening pass. The
probes it drives live in [`security/`](../../security/); none of them opens `HARNESS_DB` or
calls a model.
