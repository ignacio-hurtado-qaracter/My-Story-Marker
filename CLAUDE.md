# CLAUDE.md

@AGENTS.md

Everything in `AGENTS.md` applies. What follows is specific to running this project in
Claude Code.

## Skills in this repository

Skills live in `.claude/skills/` and are committed. Their origin and licence are recorded
in [`.claude/skills/README.md`](./.claude/skills/README.md); read it before trusting a
skill as upstream-official.

`fastapi` is the official FastAPI skill, vendored from the package wheel. When `backend/`
exists and pins a FastAPI version, replace the vendored copy with the managed install
(`uvx library-skills`) so the skill and the library cannot drift apart.

