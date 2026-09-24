#!/usr/bin/env bash
# Hook/policy probe (security review, programme 004): pipes sample PreToolUse events into
# `.claude/hooks/policy_guard.py` and prints the exit code of each (0 = allowed, 2 = blocked).
#
#     bash security/hooks_probe.sh          # from the repository root
#
# HARNESS_DB is pointed at a path that does not exist, so a denial is NOT logged into the
# real harness database (the hook only logs to a DB file that exists). Key-shaped values are
# assembled at run time so this file holds none.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export CLAUDE_PROJECT_DIR="$ROOT"
export HARNESS_DB="/nonexistent/security-probe.sqlite"
HOOK="$ROOT/.claude/hooks/policy_guard.py"
KEY_ANT="sk""-ant-api03$(printf 'Q9wZ7rT2mB4kL8pN6vC1')"
KEY_LF="sk""-lf-$(printf '1a2b3c4d')-$(printf '9f8e7d6c5b4a')"

run() {
  local expect="$1" label="$2" json="$3"
  printf '%s' "$json" | python3 "$HOOK" 2>/dev/null
  local code=$?
  local verdict="OK"
  [ "$code" = "$expect" ] || verdict="FINDING"
  printf '%-8s exit=%s (esperado %s)  %s\n' "$verdict" "$code" "$expect" "$label"
}

run 0 "Edit de código normal" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/app/main.py","new_string":"x = 1"}}'
run 2 "Write backend/.env" \
  '{"tool_name":"Write","tool_input":{"file_path":"backend/.env","content":"A=1"}}'
run 2 "Write .env (raíz)" \
  '{"tool_name":"Write","tool_input":{"file_path":".env","content":"A=1"}}'
run 0 "Write .env.example" \
  '{"tool_name":"Write","tool_input":{"file_path":".env.example","content":"LANGFUSE_SECRET_KEY="}}'
run 2 "Write con clave Anthropic" \
  "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"notes.txt\",\"content\":\"K=$KEY_ANT\"}}"
run 2 "Edit con clave Langfuse" \
  "{\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"backend/app/x.py\",\"new_string\":\"S='$KEY_LF'\"}}"
run 0 "Write con placeholder de clave" \
  '{"tool_name":"Write","tool_input":{"file_path":"notes.txt","content":"K=sk''-ant-xxxxxxxxxxxxxxxxxxxxxxxx"}}'
run 2 "Bash: echo clave > .env" \
  "{\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"echo LANGFUSE_SECRET_KEY=$KEY_LF > backend/.env\"}}"
run 2 "Bash: sqlite3 delete en harness.sqlite" \
  '{"tool_name":"Bash","tool_input":{"command":"sqlite3 data/harness.sqlite \"delete from novel\""}}'
run 2 "Bash: sqlite3 update en harness.sqlite" \
  '{"tool_name":"Bash","tool_input":{"command":"sqlite3 /home/user/data/harness.sqlite \"update chapter_version set text=1\""}}'
run 2 "Bash: rm harness.sqlite" \
  '{"tool_name":"Bash","tool_input":{"command":"rm -f data/harness.sqlite"}}'
run 0 "Bash: sqlite3 select (lectura)" \
  '{"tool_name":"Bash","tool_input":{"command":"sqlite3 data/harness.sqlite \"select count(*) from novel\""}}'
run 2 "Write directo a harness.sqlite" \
  '{"tool_name":"Write","tool_input":{"file_path":"data/harness.sqlite","content":"x"}}'
run 2 "Bash: python -c sqlite3 ... insert" \
  '{"tool_name":"Bash","tool_input":{"command":"python3 -c \"import sqlite3; sqlite3.connect(\\\"data/harness.sqlite\\\").execute(\\\"insert into novel values(1)\\\")\""}}'
