"""What the two Claude Code hooks run (spec 009, H03 and H04): the pipeline's own code.

The hook scripts under `.claude/hooks/` stay stdlib-only for speed and call this module
only for chapter files (and to log a denial):

    python -m app.policy.hooks check-chapter PATH [--novel-id ID] [--db PATH]
    python -m app.policy.hooks check-text [--novel-id ID] [--db PATH]      # text on stdin
    python -m app.policy.hooks log --policy P --decision D [--term T] [--detail S] [--db PATH]

Exit 0 when the text passes, 2 with the problems on stderr when it does not (the Claude
Code convention for "block and feed back"). Terms come from the authoritative database at
`--db` / `HARNESS_DB` when that file exists; otherwise from a throw-away in-memory database
that has only the migrations applied — so the seed list lives in one place, migration 1300.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Final

from app.bible import BibleRepository, word_count
from app.commons.config import get_settings
from app.policy.engine import PolicyEngine

WORDS_MIN: Final[int] = 1000
WORDS_MAX: Final[int] = 1500
HOOK_SOURCE: Final[str] = "claude_code_hook"


def _db_path(db: str | None) -> Path:
    return Path(db) if db else get_settings().harness_db_path


def open_repo(db: str | None = None) -> BibleRepository:
    """The real database when it exists, else an in-memory one with the seed applied."""
    path = _db_path(db)
    return BibleRepository.open(path if path.is_file() else ":memory:")


def prose_words(text: str) -> int:
    """Words of a chapter export, not counting Markdown heading lines."""
    body = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    return word_count(body)


def forbidden_problems(repo: BibleRepository, text: str, novel_id: str | None) -> list[str]:
    known = novel_id if novel_id and _exists(repo, novel_id) else None
    decision = PolicyEngine(repo).check_text(known, text, source=HOOK_SOURCE)
    return [
        f"término prohibido ({m.level}): «{m.term}» aparece como «{m.surface}»"
        for m in decision.matches
    ]


def _exists(repo: BibleRepository, novel_id: str) -> bool:
    return any(novel.id == novel_id for novel in repo.list_novels())


def chapter_problems(
    repo: BibleRepository,
    text: str,
    *,
    novel_id: str | None = None,
    words_min: int = WORDS_MIN,
    words_max: int = WORDS_MAX,
) -> list[str]:
    """Length (1000-1500 words) and forbidden words of one chapter text."""
    problems: list[str] = []
    words = prose_words(text)
    if not words_min <= words <= words_max:
        problems.append(f"longitud: {words} palabras, fuera de {words_min}-{words_max}")
    problems.extend(forbidden_problems(repo, text, novel_id))
    return problems


def _report(problems: list[str], what: str) -> int:
    if not problems:
        return 0
    lines = [f"{what} no pasa los validadores del harness:", *(f"- {p}" for p in problems)]
    lines.append("Corrige el texto (reescribe sin esos términos / ajusta la longitud).")
    sys.stderr.write("\n".join(lines) + "\n")
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.policy.hooks")
    sub = parser.add_subparsers(dest="command", required=True)
    chapter = sub.add_parser("check-chapter")
    chapter.add_argument("path")
    text = sub.add_parser("check-text")
    log = sub.add_parser("log")
    log.add_argument("--policy", required=True)
    log.add_argument("--decision", required=True)
    log.add_argument("--term")
    log.add_argument("--detail", default="")
    for command in (chapter, text, log):
        command.add_argument("--db")
        command.add_argument("--novel-id")
    args = parser.parse_args(argv)

    if args.command == "log":
        path = _db_path(args.db)
        if not path.is_file():
            return 1
        with BibleRepository.open(path) as repo:
            repo.log_policy_decision(
                policy=args.policy,
                decision=args.decision,
                term=args.term,
                detail=args.detail,
                novel_id=args.novel_id,
            )
        return 0

    with open_repo(args.db) as repo:
        if args.command == "check-chapter":
            content = Path(args.path).read_text(encoding="utf-8")
            problems = chapter_problems(repo, content, novel_id=args.novel_id)
            return _report(problems, f"El capítulo {args.path}")
        problems = forbidden_problems(repo, sys.stdin.read(), args.novel_id)
        return _report(problems, "El texto")


if __name__ == "__main__":
    raise SystemExit(main())
