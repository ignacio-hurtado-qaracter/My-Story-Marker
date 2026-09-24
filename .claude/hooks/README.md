# Claude Code hooks (spec 009)

Two hooks, registered in [`../settings.json`](../settings.json), run the **same code as the
pipeline** on hand edits, so editing a chapter outside the pipeline cannot skip validation
([`docs/verification.md`, Guardrails](../../docs/verification.md#guardrails--a-structural--t-behavioural)).

| Hook | Event · matcher | What it does | Blocks with |
|---|---|---|---|
| `policy_guard.py` | `PreToolUse` · `Write\|Edit\|MultiEdit\|Bash` | Denies `.env` files other than `.env.example`; content or commands with a real-looking key (`sk-ant-`, `sk-lf-`, `pk-lf-` + 16 key characters; placeholders such as `xxxx…` pass); direct writes to `data/harness.sqlite*` (read-only `sqlite3 … "select …"` passes); forbidden words in a chapter file | exit 2, reason on stderr |
| `validate_chapter.py` | `PostToolUse` · `Write\|Edit\|MultiEdit` | On a chapter export only: 1000–1500 words (Markdown headings excluded) and the forbidden-word guardrail | exit 2, problems on stderr (fed back to Claude) |

**Chapter files** are `capitulo-N*.md`, `chapter-N*.md`, or any `.md` under a `chapters/` or
`capitulos/` folder (`README.md` excluded). A path `data/novels/<novel_id>/…` also brings in
that novel's own forbidden terms.

**Where the terms come from.** The authoritative DB at `HARNESS_DB` (default
`data/harness.sqlite`) when it exists; otherwise an in-memory DB with the migrations
applied, so the global seed list lives only in migration
`backend/app/commons/db/authoritative/migrations/1300_forbidden_terms_global.sql`.

**Speed.** Both scripts are stdlib-only (`python3`, 3.11+). A non-chapter edit or a Bash
command costs ~0.05 s. Only chapter files call into the backend
(`backend/.venv/bin/python -m app.policy.hooks`, or `uv run --no-sync` if there is no venv),
~1 s. If the backend cannot run, the hook warns and does not block.

**Audit.** Every decision is appended as a JSON line to `policy-audit.log` in this folder
(git-ignored). A denial is also written to the `policy_decision` table through
`BibleRepository` when the DB exists (`policy = "claude_code_policy_hook"`).

## Trying them by hand

From the repository root, pipe a hook event into each script and read the exit code:

```bash
export CLAUDE_PROJECT_DIR=$PWD

# policy guard: a code edit passes (exit 0)
echo '{"tool_name":"Edit","tool_input":{"file_path":"backend/app/main.py","new_string":"x = 1"}}' \
  | python3 .claude/hooks/policy_guard.py; echo "exit=$?"

# policy guard: a .env write is blocked (exit 2)
echo '{"tool_name":"Write","tool_input":{"file_path":"backend/.env","content":"A=1"}}' \
  | python3 .claude/hooks/policy_guard.py; echo "exit=$?"

# policy guard: a key-shaped value is blocked (the key is assembled so this file holds none)
KEY="sk-ant-api03$(printf 'Q9wZ7rT2mB4kL8pN6vC1')"
printf '{"tool_name":"Write","tool_input":{"file_path":"notes.txt","content":"K=%s"}}' "$KEY" \
  | python3 .claude/hooks/policy_guard.py; echo "exit=$?"

# policy guard: shell writes to the harness DB are blocked, reads pass
echo '{"tool_name":"Bash","tool_input":{"command":"sqlite3 data/harness.sqlite \"delete from novel\""}}' \
  | python3 .claude/hooks/policy_guard.py; echo "exit=$?"

# policy guard: forbidden words (leetspeak) in a chapter file are blocked
echo '{"tool_name":"Write","tool_input":{"file_path":"ejemplos/capitulo-4.md","content":"Era un c4br0n."}}' \
  | python3 .claude/hooks/policy_guard.py; echo "exit=$?"

# chapter validator: a two-word chapter fails on length (exit 2)
mkdir -p /tmp/msm && printf '# Capítulo 3\n\nMuy corto.\n' > /tmp/msm/capitulo-3.md
echo '{"tool_name":"Write","tool_input":{"file_path":"/tmp/msm/capitulo-3.md"}}' \
  | python3 .claude/hooks/validate_chapter.py; echo "exit=$?"
```

The same check without Claude Code, straight from the backend:

```bash
cd backend
printf 'Le llamó estúpidos.' | uv run python -m app.policy.hooks check-text; echo "exit=$?"
```
