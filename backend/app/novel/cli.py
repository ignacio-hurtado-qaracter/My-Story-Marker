"""CLI of the gift-novel pipeline (spec 007, contract K4).

    cd backend
    uv run python -m app.novel.cli generate --brief PATH [--novel-id ID] [--chapters N]
    uv run python -m app.novel.cli resume --novel-id ID
    uv run python -m app.novel.cli change-fact --novel-id ID --fact KEY --value V
    uv run python -m app.novel.cli status --novel-id ID

The database is `HARNESS_DB` (default `data/harness.sqlite` at the repository root).
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import cast

from pydantic import JsonValue

from app.bible import BibleNotFoundError, BibleRepository
from app.novel import _ingest_fallback
from app.novel.models import RunResult
from app.novel.pipeline import change_fact, generate


def _echo(line: str) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _say(line: str) -> None:
    _echo(f"[{time.strftime('%H:%M:%S')}] {line}")


def _ingest(repo: BibleRepository, brief: Mapping[str, JsonValue], novel_id: str | None) -> str:
    try:
        service = importlib.import_module("app.interview.service")
        ingest: Callable[..., str] = service.ingest_brief  # type: ignore[explicit-any]  # B2 optional; spec 007
    except (ImportError, AttributeError):
        _say("app.interview not available: using the local ingest fallback")
        return _ingest_fallback.ingest_brief(repo, brief, novel_id=novel_id)
    try:
        brief_type = importlib.import_module("app.interview.brief").Brief
        parsed = brief_type.model_validate(dict(brief))
    except (ImportError, AttributeError):
        parsed = dict(brief)
    return ingest(repo, parsed, novel_id=novel_id)


def cmd_generate(args: argparse.Namespace) -> int:
    brief = json.loads(Path(args.brief).read_text(encoding="utf-8"))
    if not isinstance(brief, dict):
        _say("the brief must be a JSON object")
        return 2
    if args.chapters:
        length = brief.get("length")
        base: dict[str, object] = dict(length) if isinstance(length, dict) else {}
        brief["length"] = {**base, "chapters": args.chapters}
    with BibleRepository.open() as repo:
        novel_id = args.novel_id
        existing = None
        if novel_id:
            try:
                existing = repo.get_novel(novel_id)
            except BibleNotFoundError:
                existing = None
        if existing is None:
            novel_id = _ingest(repo, brief, novel_id)
            _say(f"novel {novel_id} created from {args.brief}")
        else:
            _say(f"novel {novel_id} exists: resuming")
        return _report(generate(repo, novel_id, chapters=args.chapters, progress=_say))


def cmd_resume(args: argparse.Namespace) -> int:
    with BibleRepository.open() as repo:
        return _report(generate(repo, args.novel_id, progress=_say))


def cmd_change_fact(args: argparse.Namespace) -> int:
    with BibleRepository.open() as repo:
        result = change_fact(repo, args.novel_id, args.fact, args.value, progress=_say)
        _say(
            f"version {result.new_version}: {result.status}; changed chapters "
            f"{result.changed_chapters} {result.detail[:300]}"
        )
        return 0 if result.status == "published" else 1


def cmd_status(args: argparse.Namespace) -> int:
    with BibleRepository.open() as repo:
        novel = repo.get_novel(args.novel_id)
        _echo(f"novel {novel.id}: '{novel.title}' for {novel.recipient_name} — {novel.status}")
        for version in repo.list_versions(novel.id):
            _echo(
                f"  version {version.version} ({version.status}, parent "
                f"{version.parent_version}, repair_rounds {version.repair_rounds}) "
                f"{version.note[:200]}"
            )
            for cp in repo.list_checkpoints(novel.id, version.version):
                chapter = repo.get_chapter(novel.id, version.version, cp.chapter)
                words = chapter.word_count if chapter else 0
                title = chapter.title if chapter else ""
                _echo(f"    ch {cp.chapter}: {cp.status} {words} words  {title}")
            results = repo.list_validator_results(novel.id, version=version.version)
            by_name: dict[str, list[int]] = {}
            for r in results:
                tally = by_name.setdefault(f"{r.point}/{r.name}", [0, 0])
                tally[0 if r.passed else 1] += 1
            for name, (ok, ko) in sorted(by_name.items()):
                _echo(f"    validator {name}: {ok} pass, {ko} fail")
        cost = repo.cost_summary(novel.id)
        _echo(
            f"  cost ${cost.cost_usd:.4f}, {cost.calls} calls, in {cost.input_tokens} / out "
            f"{cost.output_tokens} tokens, cache read {cost.cache_read}, "
            f"{cost.latency_s:.0f}s; by role {cost.by_role}"
        )
    return 0


def _report(result: RunResult) -> int:
    _say(
        f"result: {result.status} (novel {result.novel_id}, version {result.version}) "
        f"{result.detail[:500]}"
    )
    return 0 if result.status == "published" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.novel.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="ingest a brief and generate (or resume) a novel")
    gen.add_argument("--brief", required=True)
    gen.add_argument("--novel-id")
    gen.add_argument("--chapters", type=int)
    gen.set_defaults(func=cmd_generate)
    res = sub.add_parser("resume", help="resume a novel at its first incomplete chapter")
    res.add_argument("--novel-id", required=True)
    res.set_defaults(func=cmd_resume)
    chg = sub.add_parser("change-fact", help="change one fact and regenerate its chapters")
    chg.add_argument("--novel-id", required=True)
    chg.add_argument("--fact", required=True)
    chg.add_argument("--value", required=True)
    chg.set_defaults(func=cmd_change_fact)
    st = sub.add_parser("status", help="checkpoints, validator results and cost")
    st.add_argument("--novel-id", required=True)
    st.set_defaults(func=cmd_status)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    func = cast("Callable[[argparse.Namespace], int]", args.func)
    return func(args)


if __name__ == "__main__":
    sys.exit(main())
