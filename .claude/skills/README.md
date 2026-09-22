# Vendored skills

Skills committed into this repository, with their provenance. Every entry says where it
came from and under which licence, so a reader can tell an official upstream skill from a
third-party one.

| Skill | Source | Official? | Licence | Added |
|---|---|---|---|---|
| `fastapi/` | `fastapi` 0.141.1 PyPI wheel, path `fastapi/.agents/skills/fastapi/` | Yes, by the FastAPI project | MIT | 2026-09-21 |
| `react/` | Written for this repository | No, ours | This repo | 2026-09-21 |
| `sqlite/` | Written for this repository | No, ours | This repo | 2026-09-21 |
| `sqlite-vec/` | MCPmarket installer payload, skill files only (see below) | No, third party | Not stated | 2026-09-21 |
| `verification/` | Written for this repository, around a third-party reference sheet (see below) | No, ours | This repo | 2026-09-21 |

## FastAPI

The FastAPI skill is shipped **inside the Python package**, not in the GitHub repository,
and is versioned in lockstep with the library. Upstream distributes it through
[library-skills](https://github.com/tiangolo/library-skills), which symlinks the skill out
of the installed dependency.

This copy was extracted from the wheel because the project has no `backend/` environment
yet. Once `backend/` exists and declares `fastapi` as a dependency, prefer the managed
route so the skill tracks the pinned version:

```bash
uvx library-skills
```

At that point delete this vendored copy rather than keeping two sources of truth. A
vendored skill pinned to 0.141.1 while the code runs a different version is worse than no
skill, because it states outdated patterns with full confidence.

**Scheduled.** `backend/` is being built under
[`specs/001-backend-foundation.md`](../../specs/001-backend-foundation.md), whose NFR-01
requires exactly this swap once FastAPI is pinned. Step 2 of
[the implementation plan](../../specs/001-backend-foundation-plan.md) replaces the vendored
copy with `uvx library-skills` in the same commit that adds `pyproject.toml`.

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
