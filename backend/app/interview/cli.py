"""Interview CLI (spec 006).

    cd backend
    uv run python -m app.interview.cli interview --out brief.json [--novel-id ID] [--brief START]
    uv run python -m app.interview.cli validate --brief brief.json
    uv run python -m app.interview.cli ingest --brief brief.json [--novel-id ID]

`interview` reads answers from stdin, one line per answer. Type `:texto` to paste free
text (an anecdote, a letter) ended by a line `:fin`; it is untrusted and only its extracted
facts reach the story bible. `:salir` stops and writes the draft as it is. The novel id is
minted at the start (or taken from `--novel-id`) and printed, so `ingest --novel-id` and the
later generation share the interview's Langfuse session.

Files are opened through `argparse.FileType`: they are the user's own files, not stores.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import TextIO

from pydantic import JsonValue, TypeAdapter

from app.commons.llm import ClaudeCodeModelClient
from app.commons.observability import get_observer
from app.interview.brief import validate_brief
from app.interview.interviewer import OPENING_QUESTION, Interviewer
from app.interview.service import InvalidBriefError, ingest_brief, new_novel_id, open_bible

_OBJECT: TypeAdapter[dict[str, JsonValue]] = TypeAdapter(dict[str, JsonValue])


def _read_brief(handle: TextIO) -> dict[str, JsonValue]:
    with handle:
        return _OBJECT.validate_json(handle.read())


def _print(text: str) -> None:
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def _read_paste(stdin: TextIO) -> str:
    lines: list[str] = []
    for line in stdin:
        if line.strip() == ":fin":
            break
        lines.append(line.rstrip("\n"))
    return "\n".join(lines).strip()


def cmd_interview(args: argparse.Namespace) -> int:
    novel_id = args.novel_id or new_novel_id()
    draft = _read_brief(args.brief) if args.brief else {}
    observer = get_observer()
    with open_bible() as repo:
        interviewer = Interviewer(ClaudeCodeModelClient(), observer, novel_id=novel_id, repo=repo)
        _print(f"[novela {novel_id}]  (:texto para pegar texto libre, :salir para terminar)")
        _print(OPENING_QUESTION)
        done = False
        for raw in sys.stdin:
            answer = raw.strip()
            if not answer:
                continue
            if answer == ":salir":
                break
            if answer == ":texto":
                _print("Pega el texto y termina con una línea ':fin'.")
                pasted = _read_paste(sys.stdin)
                if pasted:
                    draft = interviewer.add_free_text(draft, pasted)
                _print("Texto guardado. " + interviewer.last_question)
                continue
            result = interviewer.step(draft, answer)
            draft = result.draft
            _print(result.next_question)
            if result.done:
                done = True
                break
    observer.flush()
    with args.out as out:
        out.write(json.dumps(draft, ensure_ascii=False, indent=2) + "\n")
    report = validate_brief(draft)
    _print(report.model_dump_json(indent=2))
    _print(f"novel_id: {novel_id}")
    return 0 if done and report.valid else 1


def cmd_validate(args: argparse.Namespace) -> int:
    report = validate_brief(_read_brief(args.brief))
    _print(report.model_dump_json(indent=2))
    return 0 if report.valid else 1


def cmd_ingest(args: argparse.Namespace) -> int:
    data = _read_brief(args.brief)
    observer = get_observer()
    with open_bible() as repo:
        try:
            novel_id = ingest_brief(repo, data, novel_id=args.novel_id, observer=observer)
        except InvalidBriefError as error:
            _print(error.report.model_dump_json(indent=2))
            return 1
    _print(novel_id)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.interview.cli", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    interview = sub.add_parser("interview", help="interactive interview on stdin")
    interview.add_argument("--out", type=argparse.FileType("w", encoding="utf-8"), required=True)
    interview.add_argument("--novel-id", default=None)
    interview.add_argument("--brief", type=argparse.FileType("r", encoding="utf-8"))
    interview.set_defaults(handler=cmd_interview)
    validate = sub.add_parser("validate", help="validate a brief JSON file")
    validate.add_argument("--brief", type=argparse.FileType("r", encoding="utf-8"), required=True)
    validate.set_defaults(handler=cmd_validate)
    ingest = sub.add_parser("ingest", help="ingest a brief; prints the novel id")
    ingest.add_argument("--brief", type=argparse.FileType("r", encoding="utf-8"), required=True)
    ingest.add_argument("--novel-id", default=None)
    ingest.set_defaults(handler=cmd_ingest)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    code: int = args.handler(args)
    return code


if __name__ == "__main__":
    sys.exit(main())
