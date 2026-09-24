"""PDF export CLI (spec 014).

    cd backend
    uv run python -m app.export.cli pdf --novel-id ID [--version V] [--out PATH]

Without `--version`, the latest published version. Without `--out`, the file goes to
`data/pdf/<novel>-v<N>.pdf` at the repository root; the version is always in the default
name, so exporting a new version keeps the previous one's PDF (R07).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.bible import BibleError, BibleRepository
from app.commons.config import REPO_ROOT
from app.export.pdf import export_pdf, pdf_filename
from app.reader import service


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.export.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    pdf = commands.add_parser("pdf", help="export one version of a novel as an interactive PDF")
    pdf.add_argument("--novel-id", required=True)
    pdf.add_argument("--version", type=int, default=None)
    pdf.add_argument("--out", type=Path, default=None)
    pdf.add_argument("--db", type=Path, default=None, help="default: HARNESS_DB")
    args = parser.parse_args(argv)

    try:
        with BibleRepository.open(args.db) as repo:
            version: int | None = args.version
            if version is None:
                version = service.current_version(repo, args.novel_id)
                if version is None:
                    latest = repo.latest_version(args.novel_id)
                    version = None if latest is None else latest.version
            if version is None:
                sys.stderr.write(f"novel {args.novel_id!r} has no version\n")
                return 1
            default = REPO_ROOT / "data" / "pdf" / pdf_filename(args.novel_id, version)
            out: Path = args.out or default
            written = export_pdf(repo, args.novel_id, version, out)
    except BibleError as error:
        sys.stderr.write(f"{error}\n")
        return 1
    sys.stdout.write(f"{written}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
