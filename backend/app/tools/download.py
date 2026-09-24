"""`download_novel` (spec 017): the whole novel as a PDF, base64-encoded.

The PDF is rendered by `app.export.pdf.export_pdf` (block B10), imported lazily so this
package works, and reports a typed error, when that module is not installed yet.
"""

from __future__ import annotations

import base64
import importlib
import re
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import cast

from app.bible import BibleRepository
from app.tools.base import ToolUnavailableError
from app.tools.models import DownloadNovelInput, DownloadNovelOutput
from app.tools.story import require_novel, resolve_version

ExportPdf = Callable[[BibleRepository, str, int, Path], object]


def _export_pdf() -> ExportPdf:
    try:
        module = importlib.import_module("app.export.pdf")
    except ImportError as exc:
        message = "download_novel: PDF export (app.export.pdf) is not installed"
        raise ToolUnavailableError(message) from exc
    function = getattr(module, "export_pdf", None)
    if not callable(function):
        message = "download_novel: app.export.pdf has no export_pdf()"
        raise ToolUnavailableError(message)
    return cast("ExportPdf", function)


def _default_version(repo: BibleRepository, novel_id: str) -> int:
    published = repo.latest_version(novel_id, status="published")
    if published is not None:
        return published.version
    return resolve_version(repo, novel_id, None).version


def download_novel(repo: BibleRepository, args: DownloadNovelInput) -> DownloadNovelOutput:
    require_novel(repo, args.novel_id)
    version = (
        resolve_version(repo, args.novel_id, args.version).version
        if args.version is not None
        else _default_version(repo, args.novel_id)
    )
    export_pdf = _export_pdf()
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", args.novel_id).strip("-") or "novel"
    filename = f"{slug}-v{version}.pdf"
    with tempfile.TemporaryDirectory(prefix="story-maker-pdf-") as tmp:
        out_path = Path(tmp) / filename
        export_pdf(repo, args.novel_id, version, out_path)
        data = out_path.read_bytes()
    return DownloadNovelOutput(
        novel_id=args.novel_id,
        version=version,
        filename=filename,
        size_bytes=len(data),
        content_base64=base64.b64encode(data).decode("ascii"),
    )


__all__ = ["download_novel"]
