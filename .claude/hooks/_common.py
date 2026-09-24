"""Shared, stdlib-only helpers of the two Claude Code hooks (spec 009, H03 and H04).

Kept free of third-party imports so a hook on an ordinary code edit costs a few
milliseconds. Anything that needs the harness's own code (forbidden words, chapter length,
the policy log in the database) is delegated to `python -m app.policy.hooks` in the
backend's environment, and only for chapter files or denials.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HOOKS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR") or HOOKS_DIR.parents[1])
BACKEND_DIR = PROJECT_DIR / "backend"
AUDIT_LOG = HOOKS_DIR / "policy-audit.log"

_CHAPTER_NAME = re.compile(r"(?i)^(cap[ií]tulo|chapter)[-_ ]?\d+.*\.md$")
_CHAPTER_DIRS = {"chapters", "capitulos", "capítulos"}
_NOVEL_DIR = re.compile(r"(?:^|/)data/novels/([^/]+)/")


def read_event() -> dict[str, Any]:
    """The hook's JSON from stdin ({} when it is not valid JSON)."""
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}
    return event if isinstance(event, dict) else {}


def is_chapter_path(path: str) -> bool:
    """A chapter export: `capitulo-3.md`, `chapter_03-title.md`, or `chapters/*.md`."""
    if not path:
        return False
    candidate = Path(path)
    if candidate.suffix.lower() != ".md" or candidate.name.lower() == "readme.md":
        return False
    return bool(_CHAPTER_NAME.match(candidate.name)) or (
        candidate.parent.name.lower() in _CHAPTER_DIRS
    )


def novel_id_from_path(path: str) -> str | None:
    match = _NOVEL_DIR.search(Path(path).as_posix())
    return match.group(1) if match else None


def harness_db() -> Path:
    configured = os.environ.get("HARNESS_DB")
    if configured:
        path = Path(configured)
        return path if path.is_absolute() else PROJECT_DIR / path
    return PROJECT_DIR / "data" / "harness.sqlite"


def backend_command(*args: str) -> list[str]:
    """`python -m app.policy.hooks ARGS` in the backend's venv (uv as a fallback)."""
    venv_python = BACKEND_DIR / ".venv" / "bin" / "python"
    if venv_python.is_file():
        return [str(venv_python), "-m", "app.policy.hooks", *args]
    return [
        "uv",
        "run",
        "--project",
        str(BACKEND_DIR),
        "--no-sync",
        "python",
        "-m",
        "app.policy.hooks",
        *args,
    ]


def run_backend(*args: str, stdin: str | None = None, timeout: float = 15) -> tuple[int, str]:
    """Run the backend's hook entry point. Returns (exit code, stderr); (-1, why) on failure."""
    try:
        done = subprocess.run(  # noqa: S603 - fixed argv, no shell
            backend_command(*args),
            input=stdin,
            capture_output=True,
            text=True,
            cwd=BACKEND_DIR,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return -1, f"{type(error).__name__}: {error}"
    return done.returncode, done.stderr


def audit(hook: str, tool: str, decision: str, reason: str = "", path: str = "") -> None:
    """Append one decision to the git-ignored JSONL audit log; never raises."""
    record = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "hook": hook,
        "tool": tool,
        "decision": decision,
        "reason": reason,
        "path": path,
    }
    try:
        with AUDIT_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def log_to_db(policy: str, decision: str, detail: str, term: str | None = None) -> bool:
    """A policy decision into the harness DB's policy log, when the DB exists."""
    if not harness_db().is_file():
        return False
    args = [
        "log",
        "--policy",
        policy,
        "--decision",
        decision,
        "--detail",
        detail[:900],
        "--db",
        str(harness_db()),
    ]
    if term:
        args += ["--term", term]
    code, _ = run_backend(*args, timeout=10)
    return code == 0
