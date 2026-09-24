#!/usr/bin/env python3
"""PostToolUse chapter-validation hook on Write | Edit | MultiEdit (spec 009, H03).

When the edited file is a chapter export (`capitulo-N*.md`, `chapter-N*.md`, or a `.md`
under `chapters/` / `capitulos/`), it runs the pipeline's own code on the file as saved:
length 1000-1500 words (Markdown headings excluded) and the forbidden-word guardrail with
the global list (the harness DB when it exists, else the seed of migration 1300) plus the
novel's own list when the path is `data/novels/<novel_id>/...`. On failure it exits 2 and
the problems go to stderr, which Claude Code shows to Claude so it fixes the chapter.
Any other file returns at once with exit 0.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    audit,
    harness_db,
    is_chapter_path,
    novel_id_from_path,
    read_event,
    run_backend,
)

HOOK = "validate_chapter"


def main() -> int:
    event = read_event()
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    path = str(tool_input.get("file_path") or "")
    if not is_chapter_path(path) or not Path(path).is_file():
        return 0
    args = ["check-chapter", path, "--db", str(harness_db())]
    novel_id = novel_id_from_path(path)
    if novel_id:
        args += ["--novel-id", novel_id]
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    code, stderr = run_backend(*args, stdin=text)
    tool = str(event.get("tool_name") or "")
    if code == 0:
        audit(HOOK, tool, "pass", path=path)
        return 0
    if code == 2:  # noqa: PLR2004 - Claude Code's "feed back to Claude" exit code
        audit(HOOK, tool, "fail", reason=stderr.strip()[:500], path=path)
        sys.stderr.write(stderr)
        return 2
    audit(HOOK, tool, "error", reason=stderr.strip()[:500], path=path)
    sys.stderr.write(f"validate_chapter: no se pudo validar ({stderr.strip()[:300]})\n")
    return 1  # non-blocking: a broken environment never blocks editing


if __name__ == "__main__":
    raise SystemExit(main())
