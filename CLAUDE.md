# CLAUDE.md

@AGENTS.md

Everything in `AGENTS.md` applies. What follows is specific to running this project in
Claude Code.

## Process 0 in Claude Code

The interrogation step that `AGENTS.md` calls Process 0 is run with the project skill
`grill-me`, installed in `.claude/skills/grill-me/` (it delegates to
`.claude/skills/grilling/`). Invoke it with the Skill tool, or type `/grill-me`, before
any edit to `docs/`, `specs/`, `backend/` or `frontend/` that is not exempt under
Process 0. Do not start editing until the user has confirmed the written summary.

The skill is a vendored copy of `grill-me` and `grilling` from
[mattpocock/skills](https://github.com/mattpocock/skills), MIT licensed. The LICENSE file
sits next to each `SKILL.md`.

