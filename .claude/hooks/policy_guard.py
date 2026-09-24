#!/usr/bin/env python3
"""PreToolUse policy hook on Write | Edit | MultiEdit | Bash (spec 009, H04).

Blocks, with exit code 2 and the reason on stderr (Claude Code feeds it back to Claude):

1. writing a `.env` file other than `.env.example` (by tool or by shell redirection);
2. content or commands carrying something shaped like a real API key
   (`sk-ant-`, `sk-lf-`, `pk-lf-` followed by 16+ key characters, placeholders excepted);
3. direct writes to the authoritative database `data/harness.sqlite` (only
   `BibleRepository` touches it; read-only `sqlite3 ... "select ..."` stays allowed);
4. forbidden words in a chapter file, checked by the pipeline's own code.

Every decision is appended to `.claude/hooks/policy-audit.log`; a denial is also written to
the policy decision log of the harness DB when that file exists. Ordinary code edits take a
stdlib-only path and never reach the backend.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import audit, is_chapter_path, log_to_db, read_event, run_backend  # noqa: E402

HOOK = "policy_guard"
_KEY = re.compile(r"\b(sk-ant-|sk-lf-|pk-lf-)[A-Za-z0-9_\-]{16,}")
_PLACEHOLDER = re.compile(
    r"(?i)(x{4,}|example|dummy|placeholder|your|tu_clave|changeme|test|\.\.\.)"
)
_ENV_NAME = re.compile(r"^\.env(\..+)?$")
_DB_NAME = re.compile(r"harness\.sqlite(-wal|-shm|-journal)?$")
_SHELL_ENV_WRITE = re.compile(
    r"(?:>>?|\btee\b(?:\s+-a)?|\b(?:cp|mv|install|ln)\b[^;&|]*?|\bsed\s+-i\S*[^;&|]*?)"
    r"\s*[\"']?(?:[\w./~-]*/)?\.env(?:\.(?!example\b)[\w.-]+)?(?=[\"'\s;&|)]|$)"
)
_SHELL_DB_TOUCH = re.compile(r"harness\.sqlite")
_SHELL_DB_WRITE = re.compile(
    r"(?i)(>\s*[\w./~-]*harness\.sqlite|\b(rm|mv|cp|truncate|dd|shred)\b[^;&|]*harness\.sqlite"
    r"|\b(insert|update|delete|drop|alter|create|replace|vacuum|attach|pragma\s+\w+\s*=)\b)"
)


def _secret(text: str) -> str | None:
    for match in _KEY.finditer(text):
        if not _PLACEHOLDER.search(match.group(0)):
            return match.group(1)
    return None


def _texts(tool_input: dict[str, object]) -> list[str]:
    found = [tool_input.get("content"), tool_input.get("new_string")]
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        found += [e.get("new_string") for e in edits if isinstance(e, dict)]
    return [t for t in found if isinstance(t, str)]


def check_file_tool(tool_input: dict[str, object]) -> tuple[str | None, str]:
    path = str(tool_input.get("file_path") or "")
    name = Path(path).name
    if _ENV_NAME.match(name) and name != ".env.example":
        return f"escribir {name} está bloqueado: los secretos no se editan con Claude", path
    if _DB_NAME.search(name):
        return "la base de datos del harness solo se escribe a través de BibleRepository", path
    texts = _texts(tool_input)
    for text in texts:
        prefix = _secret(text)
        if prefix:
            return f"el contenido parece una clave real ({prefix}...): usa un placeholder", path
    if is_chapter_path(path) and texts:
        code, stderr = run_backend("check-text", stdin="\n".join(texts))
        if code == 2:  # noqa: PLR2004 - Claude Code's blocking exit code
            problems = [line for line in stderr.splitlines() if line.startswith("- ")]
            return "palabras prohibidas en el capítulo:\n" + "\n".join(problems), path
        if code not in (0, 2):
            sys.stderr.write(f"policy_guard: comprobación omitida ({stderr.strip()[:200]})\n")
    return None, path


def check_bash(command: str) -> str | None:
    if _SHELL_ENV_WRITE.search(command):
        return "escribir ficheros .env desde la shell está bloqueado (salvo .env.example)"
    prefix = _secret(command)
    if prefix:
        return f"el comando lleva algo con forma de clave real ({prefix}...)"
    if _SHELL_DB_TOUCH.search(command) and _SHELL_DB_WRITE.search(command):
        return "escritura directa en data/harness.sqlite: usa BibleRepository (el backend)"
    return None


def main() -> int:
    event = read_event()
    tool = str(event.get("tool_name") or "")
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    if tool == "Bash":
        path = ""
        reason = check_bash(str(tool_input.get("command") or ""))
    elif tool in {"Write", "Edit", "MultiEdit"}:
        reason, path = check_file_tool(tool_input)
    else:
        return 0
    if reason is None:
        audit(HOOK, tool, "allow", path=path)
        return 0
    audit(HOOK, tool, "deny", reason=reason, path=path)
    log_to_db("claude_code_policy_hook", "deny", f"{tool} {path}: {reason}")
    sys.stderr.write(f"Bloqueado por la policy del harness (spec 009): {reason}\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
